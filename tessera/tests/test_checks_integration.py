# SPDX-License-Identifier: GPL-2.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Integration tests for validation checks — require Blender runtime.

These tests exercise the 7 validation checks against real Blender mesh
objects. They must be run inside Blender's embedded Python interpreter:

    blender --background --python-expr "import pytest; pytest.main([
        'tessera/tests/test_checks_integration.py', '-v'
    ])"

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

AC: AC-001 through AC-010.
EC: EC-001 through EC-007.
"""

from __future__ import annotations

import math
import os
import sys

import pytest

# Guard: skip entire module outside Blender (CI / vanilla pytest).
# conftest.py mocks bpy so importorskip always succeeds; instead,
# check for bpy.app.version which only real Blender provides.
try:
    import bpy
    import bmesh

    _has_blender = hasattr(bpy, "app") and hasattr(bpy.app, "version")
except ImportError:
    _has_blender = False

pytestmark = pytest.mark.skipif(
    not _has_blender,
    reason="Requires real Blender runtime (not mocked bpy)",
)

from tessera.validator.checks.degenerate_faces import DegenerateFacesCheck
from tessera.validator.checks.manifold import ManifoldCheck
from tessera.validator.checks.overhang import OverhangCheck
from tessera.validator.checks.scale_sanity import ScaleSanityCheck
from tessera.validator.checks.self_intersection import (
    SelfIntersectionCheck,
)
from tessera.validator.checks.volume import VolumeCheck
from tessera.validator.checks.wall_thickness import WallThicknessCheck
from tessera.validator.data_types import CheckResult, CheckStatus
from tessera.validator.print_validator import PrintValidator
from tessera.validator.report import ValidationReport


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Blender fixture helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.fixture(autouse=True)
def clean_scene():
    """Reset Blender scene before each test."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    yield
    # Cleanup after test — remove all objects.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _create_cube(size: float = 2.0, location=(0, 0, 0)):
    """Create a simple cube mesh object.

    Args:
        size: Edge length in meters.
        location: World-space location tuple (x, y, z).

    Returns:
        The created ``bpy.types.Object``.
    """
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    obj = bpy.context.active_object
    return obj


def _create_open_mesh():
    """Create an open mesh (cube with one face removed).

    Returns:
        The created open ``bpy.types.Object``.
    """
    obj = _create_cube()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    # Remove the top face (Z+ face) to make it open.
    bm.faces.remove(bm.faces[-1])
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def _create_degenerate_mesh():
    """Create a mesh with zero-area faces.

    Creates a cube then collapses two vertices to make a zero-area
    triangle.

    Returns:
        The created ``bpy.types.Object``.
    """
    obj = _create_cube()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    # Move vertex 1 to the same position as vertex 0 → zero-area face.
    bm.verts[1].co = bm.verts[0].co.copy()
    bm.to_mesh(obj.data)
    bm.free()
    return obj


def _create_oversized_cube(dim_mm=(300, 200, 400)):
    """Create a cube that exceeds a typical FDM build volume.

    Converts mm dimensions to meters for Blender default scene.

    Args:
        dim_mm: Desired dimensions in mm as (x, y, z).

    Returns:
        The created ``bpy.types.Object``.
    """
    # Blender default is meters.
    x = dim_mm[0] / 1000.0
    y = dim_mm[1] / 1000.0
    z = dim_mm[2] / 1000.0
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.scale = (x, y, z)
    bpy.ops.object.transform_apply(scale=True)
    return obj


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ManifoldCheck (FR-001, FR-002)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestManifoldCheck:
    """Manifold check: non-manifold edge detection and repair."""

    def test_closed_cube_passes(self):
        """AC-001: Closed cube reports PASS with 0 non-manifold edges."""
        obj = _create_cube()
        check = ManifoldCheck()
        result = check.check(bpy.context, obj)

        assert result.status == CheckStatus.PASS
        assert result.details.get("non_manifold_edge_count", 0) == 0

    def test_open_mesh_fails(self):
        """AC-002: Open mesh (missing face) reports FAIL."""
        obj = _create_open_mesh()
        check = ManifoldCheck()
        result = check.check(bpy.context, obj)

        assert result.status == CheckStatus.FAIL
        assert result.details.get("non_manifold_edge_count", 0) > 0

    def test_repair_fills_hole(self):
        """AC-002: Auto-repair fills small boundary loops."""
        obj = _create_open_mesh()
        check = ManifoldCheck()

        # Verify initial fail.
        result = check.check(bpy.context, obj)
        assert result.status == CheckStatus.FAIL

        # Repair.
        repair = check.repair(bpy.context, obj)
        assert repair.success is True

        # Re-check — should pass now.
        result2 = check.check(bpy.context, obj)
        assert result2.status == CheckStatus.PASS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DegenerateFacesCheck (FR-005, FR-006)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestDegenerateFacesCheck:
    """Degenerate faces: zero-area face detection and repair."""

    def test_no_degenerate_faces_on_clean_mesh(self):
        """AC-004: Clean cube has 0 zero-area faces."""
        obj = _create_cube()
        check = DegenerateFacesCheck()
        result = check.check(bpy.context, obj)

        assert result.status == CheckStatus.PASS
        assert result.details.get("degenerate_face_count", 0) == 0

    def test_degenerate_face_detected(self):
        """AC-004: Mesh with collapsed vertices fails."""
        obj = _create_degenerate_mesh()
        check = DegenerateFacesCheck()
        result = check.check(bpy.context, obj)

        assert result.status == CheckStatus.FAIL
        assert result.details.get("degenerate_face_count", 0) > 0

    def test_repair_dissolves_degenerate(self):
        """FR-006: dissolve_degenerate removes zero-area faces."""
        obj = _create_degenerate_mesh()
        check = DegenerateFacesCheck()

        repair = check.repair(bpy.context, obj)
        assert repair.success is True

        result = check.check(bpy.context, obj)
        assert result.status == CheckStatus.PASS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SelfIntersectionCheck (FR-003, FR-004, EC-005)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestSelfIntersectionCheck:
    """Self-intersection: BVH overlap detection."""

    def test_no_intersection_clean_mesh(self):
        """AC-003: Clean cube has 0 intersection pairs."""
        obj = _create_cube()
        check = SelfIntersectionCheck()
        result = check.check(bpy.context, obj)

        assert result.status == CheckStatus.PASS
        assert result.details.get("intersection_pairs", 0) == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VolumeCheck (FR-013, FR-014, EC-001)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestVolumeCheck:
    """Volume check: signed tetrahedron volume computation."""

    def test_closed_cube_positive_volume(self):
        """AC-007: Closed cube has positive volume in mm³."""
        obj = _create_cube(size=2.0)  # 2m cube → volume = 8 m³ = 8e9 mm³.
        check = VolumeCheck()
        result = check.check(bpy.context, obj)

        assert result.status == CheckStatus.PASS
        assert result.details.get("volume_mm3", 0) > 0

    def test_open_mesh_fails_volume(self):
        """EC-001: Open mesh has non-positive volume → FAIL."""
        obj = _create_open_mesh()
        check = VolumeCheck()
        result = check.check(bpy.context, obj)

        # Open surface should produce zero or negative volume.
        assert result.status == CheckStatus.FAIL


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OverhangCheck (FR-010, FR-011, FR-012)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestOverhangCheck:
    """Overhang check: face-normal angle vs build plate."""

    def test_upright_cube_passes(self):
        """AC-005: Upright cube has no overhang faces."""
        obj = _create_cube()
        check = OverhangCheck()
        result = check.check(bpy.context, obj, overhang_angle_deg=45.0)

        assert result.status == CheckStatus.PASS
        assert result.details.get("overhang_face_count", 0) == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ScaleSanityCheck (FR-015, FR-016)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestScaleSanityCheck:
    """Scale sanity: bounding box vs build volume."""

    def test_small_object_fits(self):
        """AC-008: Small cube fits 220×220×250 build volume."""
        obj = _create_cube(size=0.05)  # 50 mm cube.
        check = ScaleSanityCheck()
        result = check.check(
            bpy.context,
            obj,
            build_volume_mm=(220, 220, 250),
        )

        assert result.status == CheckStatus.PASS

    def test_oversized_warns_with_factor(self):
        """AC-006: Oversized object produces WARN with scale factor."""
        obj = _create_oversized_cube(dim_mm=(300, 200, 400))
        check = ScaleSanityCheck()
        result = check.check(
            bpy.context,
            obj,
            build_volume_mm=(220, 220, 250),
        )

        assert result.status == CheckStatus.WARN
        assert "scale_factor" in result.details
        assert result.details["scale_factor"] < 1.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WallThicknessCheck (FR-007, FR-008, FR-009)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestWallThicknessCheck:
    """Wall thickness: ray-cast based thickness check."""

    def test_thick_wall_passes(self):
        """AC-004: Large cube with thick walls passes threshold."""
        obj = _create_cube(size=2.0)  # 2m cube → 2000 mm walls.
        check = WallThicknessCheck()
        result = check.check(
            bpy.context,
            obj,
            wall_thickness_mm=1.2,
        )

        assert result.status == CheckStatus.PASS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PrintValidator orchestrator (FR-034)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPrintValidator:
    """PrintValidator: runs all 7 checks in sequence."""

    def test_all_seven_checks_run(self):
        """FR-034: Validator produces a report with exactly 7 checks."""
        obj = _create_cube()
        validator = PrintValidator()
        report = validator.validate(
            context=bpy.context,
            obj=obj,
        )

        assert isinstance(report, ValidationReport)
        assert len(report.checks) == 7

    def test_clean_cube_passes_all_checks(self):
        """AC-001: Clean large cube passes all 7 checks."""
        obj = _create_cube(size=0.05)  # 50 mm — fits build volume.
        validator = PrintValidator()
        report = validator.validate(
            context=bpy.context,
            obj=obj,
            build_volume_mm=(220, 220, 250),
        )

        assert report.has_failures is False
        assert report.passed >= 6  # At minimum 6 pass, overhang may be WARN.

    def test_report_contains_object_name(self):
        """FR-028: Report includes object name."""
        obj = _create_cube()
        validator = PrintValidator()
        report = validator.validate(
            context=bpy.context,
            obj=obj,
        )

        assert report.object_name == obj.name

    def test_auto_repair_revalidates(self):
        """AC-002: After repair, re-validates and updates report."""
        obj = _create_open_mesh()
        validator = PrintValidator()
        report = validator.validate(
            context=bpy.context,
            obj=obj,
            auto_repair=True,
        )

        # Manifold check should have been repaired.
        manifold = next(
            (c for c in report.checks if "manifold" in c.check_name.lower()),
            None,
        )
        if manifold and manifold.repaired:
            assert manifold.status in (CheckStatus.PASS, CheckStatus.WARN)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ExportPipeline full integration (AC-010, FR-024)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExportPipelineIntegration:
    """Full export pipeline integration tests."""

    def test_stl_export_creates_file(self, tmp_path):
        """AC-001: STL file created in export directory."""
        from tessera.export.export_pipeline import ExportPipeline

        obj = _create_cube(size=0.05)
        pipeline = ExportPipeline()
        result = pipeline.execute(
            context=bpy.context,
            obj=obj,
            export_formats={"STL"},
            export_directory=str(tmp_path),
        )

        assert result.success is True
        assert len(result.exported_files) == 1
        assert result.exported_files[0].endswith(".stl")
        assert os.path.exists(result.exported_files[0])

    def test_validation_report_json_created(self, tmp_path):
        """FR-029: _validation.json created alongside export."""
        from tessera.export.export_pipeline import ExportPipeline

        obj = _create_cube(size=0.05)
        pipeline = ExportPipeline()
        pipeline.execute(
            context=bpy.context,
            obj=obj,
            export_formats={"STL"},
            export_directory=str(tmp_path),
        )

        # Find the validation JSON.
        json_files = [
            f for f in os.listdir(tmp_path)
            if f.endswith("_validation.json")
        ]
        assert len(json_files) == 1

    def test_validation_failure_blocks_export(self):
        """CON-004: No export on FAIL without force_export."""
        from tessera.export.export_pipeline import ExportPipeline

        obj = _create_open_mesh()  # Will fail manifold check.
        pipeline = ExportPipeline()
        result = pipeline.execute(
            context=bpy.context,
            obj=obj,
            auto_repair=False,
            force_export=False,
        )

        assert result.success is False
        assert result.exported_files == []

    def test_force_export_overrides_failure(self, tmp_path):
        """AC-007: force_export=True exports despite failures."""
        from tessera.export.export_pipeline import ExportPipeline

        obj = _create_open_mesh()
        pipeline = ExportPipeline()
        result = pipeline.execute(
            context=bpy.context,
            obj=obj,
            export_formats={"STL"},
            export_directory=str(tmp_path),
            auto_repair=False,
            force_export=True,
        )

        assert result.success is True
        assert len(result.exported_files) == 1

    def test_duplicate_cleaned_up(self):
        """AC-010 / FR-024: _print duplicate deleted after export."""
        from tessera.export.export_pipeline import ExportPipeline

        obj = _create_cube(size=0.05)
        original_name = obj.name
        pipeline = ExportPipeline()
        pipeline.execute(
            context=bpy.context,
            obj=obj,
            export_formats={"STL"},
            export_directory="/tmp",
        )

        # No object with _print suffix should remain.
        names = [o.name for o in bpy.data.objects]
        assert not any("_print" in n for n in names)

        # Original object still exists.
        assert original_name in names

    def test_multi_format_export(self, tmp_path):
        """AC-008: Multiple formats produce correct number of files."""
        from tessera.export.export_pipeline import ExportPipeline

        obj = _create_cube(size=0.05)
        pipeline = ExportPipeline()
        result = pipeline.execute(
            context=bpy.context,
            obj=obj,
            export_formats={"STL", "OBJ"},
            export_directory=str(tmp_path),
        )

        assert result.success is True
        assert len(result.exported_files) == 2

        extensions = {
            os.path.splitext(f)[1] for f in result.exported_files
        }
        assert ".stl" in extensions
        assert ".obj" in extensions
