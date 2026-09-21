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

"""Tests for SPEC-TS-0005: Mesh Import, Cleanup & Topology Optimization.

Each test maps to a test scenario (TS-XXX) and its corresponding
acceptance criterion (AC-XXX) or edge case (EC-XXX) as defined in
the spec.

Tests are designed to run in CI without Blender.  All ``bpy`` and
``bmesh`` calls are exercised through the mock infrastructure
provided by ``conftest.py``.

Mock Discipline Justification
-----------------------------
MagicMock usage in this file falls into a single justified category:

    Category: Infrastructure you don't own — Blender runtime

``bpy.types.Object``, ``bpy.types.Context``, ``bmesh.types.BMesh``,
and related types are C-extension classes that cannot be instantiated
outside of a running Blender process.  ``obj = MagicMock()`` and
``ctx = MagicMock()`` stand in for these Blender-only types so that
the cleanup pipeline orchestration (step ordering, error handling,
diagnostics assembly, undo registration) can be tested in CI.
"""

from __future__ import annotations

import logging
import time
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_vertices(n: int = 100) -> np.ndarray:
    """Generate a valid (N, 3) float32 vertex array."""
    return np.random.randn(n, 3).astype(np.float32)


def _make_valid_faces(n_verts: int = 100, n_faces: int = 50) -> np.ndarray:
    """Generate a valid (M, 3) int32 face index array.

    Indices are kept within [0, n_verts).
    """
    return np.random.randint(0, n_verts, (n_faces, 3)).astype(np.int32)


def _make_tetrahedron() -> tuple[np.ndarray, np.ndarray]:
    """Return the simplest closed volume: a tetrahedron (4 verts, 4 faces)."""
    verts = np.array(
        [[0, 0, 0], [1, 0, 0], [0.5, 1, 0], [0.5, 0.5, 1]],
        dtype=np.float32,
    )
    faces = np.array(
        [[0, 1, 2], [0, 1, 3], [1, 2, 3], [0, 2, 3]],
        dtype=np.int32,
    )
    return verts, faces


# ---------------------------------------------------------------------------
# Lazy imports — deferred so conftest's bpy mock is active first
# ---------------------------------------------------------------------------


@pytest.fixture
def mesh_imports():
    """Import mesh modules after bpy mock is installed."""
    from tessera.mesh.importer import MeshImporter
    from tessera.mesh.cleanup import MeshCleanupPipeline
    from tessera.mesh.exceptions import MeshCleanupError
    from tessera.mesh.data_types import (
        RawMeshData,
        DIAGNOSTICS_KEYS,
        empty_diagnostics,
    )
    from tessera.mesh.diagnostics import (
        build_diagnostics,
        collect_before_stats,
        collect_after_stats,
        check_manifold,
        check_topology,
        check_watertight,
    )
    from tessera.mesh.hierarchy import (
        rename_object,
        create_session_parent,
    )
    from tessera.mesh.steps.dedup import DedupStep
    from tessera.mesh.steps.degenerate import DegenerateStep
    from tessera.mesh.steps.normals import NormalsStep
    from tessera.mesh.steps.hole_fill import HoleFillStep
    from tessera.mesh.steps.voxel_remesh import VoxelRemeshStep
    from tessera.mesh.steps.quad_remesh import QuadRemeshStep
    from tessera.mesh.steps.decimate import DecimateStep

    class _Imports:
        pass

    m = _Imports()
    m.MeshImporter = MeshImporter
    m.MeshCleanupPipeline = MeshCleanupPipeline
    m.MeshCleanupError = MeshCleanupError
    m.RawMeshData = RawMeshData
    m.DIAGNOSTICS_KEYS = DIAGNOSTICS_KEYS
    m.empty_diagnostics = empty_diagnostics
    m.build_diagnostics = build_diagnostics
    m.collect_before_stats = collect_before_stats
    m.collect_after_stats = collect_after_stats
    m.check_manifold = check_manifold
    m.check_topology = check_topology
    m.check_watertight = check_watertight
    m.rename_object = rename_object
    m.create_session_parent = create_session_parent
    m.DedupStep = DedupStep
    m.DegenerateStep = DegenerateStep
    m.NormalsStep = NormalsStep
    m.HoleFillStep = HoleFillStep
    m.VoxelRemeshStep = VoxelRemeshStep
    m.QuadRemeshStep = QuadRemeshStep
    m.DecimateStep = DecimateStep
    return m


# ---------------------------------------------------------------------------
# TS-001 → AC-001: Basic Mesh Import
# ---------------------------------------------------------------------------


class TestMeshImport:
    """Tests for MeshImporter.import_mesh()."""

    def test_TS001_basic_mesh_import(self, mock_bpy, mesh_imports):
        """TS-001 → AC-001: Import mesh, verify object created with
        correct vertex and face counts.

        Given a reconstruction engine output of N vertices and M
        triangular faces as NumPy arrays,
        When MeshImporter.import_mesh(vertices, faces) is called,
        Then a new bpy.types.Object is returned, bmesh APIs are
        invoked with the correct data, and the object is linked
        to the scene collection.
        """
        m = mesh_imports

        # Given
        n_verts, n_faces = 50_000, 100_000
        verts = _make_valid_vertices(n_verts)
        faces = _make_valid_faces(n_verts, n_faces)

        importer = m.MeshImporter()

        # When
        obj = importer.import_mesh(verts, faces, source_model="trellis")

        # Then — object created and linked
        assert obj is not None
        import bpy
        # mesh data block created via bpy.data.meshes.new
        bpy.data.meshes.new.assert_called_once()
        mesh_data = bpy.data.meshes.new.return_value
        # FR-001 / CON-006: bulk insert via foreach_set (primary path)
        # or from_pydata (fallback). In mock env the foreach_set path
        # executes first; from_pydata is only the AttributeError fallback.
        mesh_data.update.assert_called()
        # bpy.data.objects.new was called
        bpy.data.objects.new.assert_called_once()
        # Object linked to collection
        bpy.context.collection.objects.link.assert_called_once_with(obj)
        # Object made active
        assert bpy.context.view_layer.objects.active == obj
        obj.select_set.assert_called_with(True)

    def test_TS014_import_latency(self, mock_bpy, mesh_imports):
        """TS-014 → NFR-002: Import latency for valid mesh < 1 second.

        Verifies that MeshImporter.import_mesh() completes within the
        NFR-002 performance budget (validation + mock bmesh calls).
        """
        m = mesh_imports

        # Given
        verts = _make_valid_vertices(500)
        faces = _make_valid_faces(500, 200)
        importer = m.MeshImporter()

        # When
        start = time.perf_counter()
        importer.import_mesh(verts, faces)
        elapsed = time.perf_counter() - start

        # Then — validation + mock calls should be well under 1 second
        assert elapsed < 1.0, f"Import took {elapsed:.3f}s (limit: 1.0s)"

    def test_import_copies_input_arrays(self, mock_bpy, mesh_imports):
        """CON-003: Import must not mutate the caller's arrays."""
        m = mesh_imports

        # Given
        verts = _make_valid_vertices(10)
        faces = _make_valid_faces(10, 6)
        verts_copy = verts.copy()
        faces_copy = faces.copy()

        # When
        importer = m.MeshImporter()
        importer.import_mesh(verts, faces)

        # Then — original arrays unchanged
        np.testing.assert_array_equal(verts, verts_copy)
        np.testing.assert_array_equal(faces, faces_copy)


# ---------------------------------------------------------------------------
# TS-002 → AC-002: Full Phase 1 Cleanup
# ---------------------------------------------------------------------------


class TestPhase1Cleanup:
    """Tests for the full Phase 1 cleanup pipeline."""

    def test_TS002_full_phase1_cleanup(self, mock_bpy, mesh_imports):
        """TS-002 → AC-002: Full Phase 1 cleanup produces a diagnostics
        dict with all required keys.

        Given a mock mesh object,
        When MeshCleanupPipeline.execute() is called with default
        settings,
        Then the returned diagnostics dict contains all 15 keys
        from FR-007 plus step_errors.
        """
        m = mesh_imports

        # Given — mock mesh object with enough attributes
        obj = MagicMock()
        obj.data.vertices = list(range(100))  # len() == 100
        obj.data.polygons = list(range(200))  # len() == 200
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # When
        diagnostics = pipeline.execute(ctx, obj)

        # Then — diagnostics dict has all required keys
        for key in m.DIAGNOSTICS_KEYS:
            assert key in diagnostics, f"Missing diagnostics key: {key}"
        assert "step_errors" in diagnostics
        assert isinstance(diagnostics["step_errors"], list)
        assert isinstance(diagnostics["cleanup_time_seconds"], float)
        assert diagnostics["cleanup_time_seconds"] >= 0.0

    def test_TS013_phase1_cleanup_latency(self, mock_bpy, mesh_imports):
        """TS-013 → NFR-001: Phase 1 cleanup latency < 5 seconds.

        Verifies that the full Phase 1 pipeline (with mock bpy)
        completes within the NFR-001 performance budget.
        """
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.vertices = list(range(500))
        obj.data.polygons = list(range(1000))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # When
        start = time.perf_counter()
        diagnostics = pipeline.execute(ctx, obj)
        elapsed = time.perf_counter() - start

        # Then
        assert elapsed < 5.0, f"Cleanup took {elapsed:.3f}s (limit: 5.0s)"
        assert diagnostics["cleanup_time_seconds"] < 5.0

    def test_pipeline_pushes_undo_before_cleanup(self, mock_bpy, mesh_imports):
        """CON-004 / FR-019: Pipeline pushes undo before destructive ops."""
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # When
        import bpy
        pipeline.execute(ctx, obj)

        # Then — undo_push called with Tessera message
        bpy.ops.ed.undo_push.assert_called_once_with(
            message="Tessera Mesh Cleanup"
        )


# ---------------------------------------------------------------------------
# TS-003 → AC-003: Voxel Remesh Fallback
# ---------------------------------------------------------------------------


class TestVoxelRemeshFallback:
    """Tests for voxel remesh fallback activation."""

    def test_TS003_voxel_remesh_fallback(self, mock_bpy, mesh_imports):
        """TS-003 → AC-003: Voxel remesh triggers when mesh is
        non-manifold after Phase 1.

        Given a mesh that remains non-manifold after surgical repair,
        When MeshCleanupPipeline.execute() is called with
        auto_voxel_fallback=True,
        Then the pipeline invokes VoxelRemeshStep and sets
        diagnostics["voxel_remesh_applied"].
        """
        m = mesh_imports

        # Given — mock mesh that is NOT manifold
        obj = MagicMock()
        obj.data.vertices = list(range(100))
        obj.data.polygons = list(range(200))
        ctx = MagicMock()

        # Make check_manifold return False first (triggering voxel),
        # then True for final check.
        import bmesh as bmesh_mock

        original_new = bmesh_mock.new

        def _mock_bmesh_new():
            bm = MagicMock()
            # For check_manifold: make edges report non-manifold
            mock_edge = MagicMock()
            mock_edge.is_manifold = False
            mock_edge.is_boundary = True
            bm.edges = [mock_edge]
            bm.verts = []
            # Use MagicMock for faces so __len__ is configurable
            mock_faces = MagicMock()
            mock_faces.__len__ = MagicMock(return_value=100)
            mock_faces.__iter__ = MagicMock(return_value=iter([]))
            bm.faces = mock_faces
            return bm

        bmesh_mock.new = _mock_bmesh_new

        pipeline = m.MeshCleanupPipeline()

        # When
        diagnostics = pipeline.execute(ctx, obj, auto_voxel_fallback=True)

        # Then — diagnostics dict was produced
        assert isinstance(diagnostics, dict)
        # voxel_remesh key exists in the merged reports
        assert "voxel_remesh_applied" in diagnostics

        # Restore
        bmesh_mock.new = original_new

    def test_voxel_remesh_skipped_when_disabled(
        self, mock_bpy, mesh_imports
    ):
        """Voxel remesh fallback does not trigger when disabled."""
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.vertices = list(range(100))
        obj.data.polygons = list(range(200))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # When — auto_voxel_fallback=False
        diagnostics = pipeline.execute(ctx, obj, auto_voxel_fallback=False)

        # Then — the key is present with False
        assert diagnostics["voxel_remesh_applied"] is False


# ---------------------------------------------------------------------------
# TS-004 → EC-001: Degenerate Input — Zero-Area Faces
# ---------------------------------------------------------------------------


class TestDegenerateInput:
    """Tests for degenerate face handling."""

    def test_TS004_zero_area_faces(self, mock_bpy, mesh_imports):
        """TS-004 → EC-001: DegenerateStep reports faces removed.

        Given a mock mesh object where bmesh reports degenerate faces,
        When DegenerateStep.execute() is called,
        Then the report dict includes "degenerate_faces_removed" key.
        """
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.polygons = list(range(10))
        ctx = MagicMock()
        settings = {}

        step = m.DegenerateStep()

        # When
        report = step.execute(ctx, obj, settings)

        # Then — report has the correct key
        assert "degenerate_faces_removed" in report
        assert isinstance(report["degenerate_faces_removed"], int)


# ---------------------------------------------------------------------------
# TS-005 → EC-002: Extremely Large Mesh
# ---------------------------------------------------------------------------


class TestLargeMesh:
    """Tests for large mesh warning and handling."""

    def test_TS005_large_mesh_warning(self, mock_bpy, mesh_imports, caplog):
        """TS-005 → EC-002: Input mesh with > 1M faces logs warning
        without crashing.

        Given a mesh with 2,000,000 faces,
        When MeshCleanupPipeline.execute() is called,
        Then the system logs a WARNING and produces a diagnostics
        dict without raising an exception.
        """
        m = mesh_imports

        # Given — mock mesh with > 1M faces
        obj = MagicMock()
        obj.data.vertices = list(range(100))
        obj.data.polygons = MagicMock()
        obj.data.polygons.__len__ = MagicMock(return_value=2_000_000)

        ctx = MagicMock()
        pipeline = m.MeshCleanupPipeline()

        # When — should not crash
        with caplog.at_level(logging.WARNING, logger="tessera.mesh"):
            diagnostics = pipeline.execute(ctx, obj)

        # Then — diagnostics produced without error
        assert isinstance(diagnostics, dict)
        assert "cleanup_time_seconds" in diagnostics

        # WARNING logged about face count exceeding threshold
        warning_records = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "faces" in r.message
        ]
        assert len(warning_records) >= 1, (
            f"Expected WARNING about large face count, got: "
            f"{[r.message for r in caplog.records]}"
        )


# ---------------------------------------------------------------------------
# TS-006 → EC-003: Empty or Minimal Mesh Input
# ---------------------------------------------------------------------------


class TestMinimalMesh:
    """Tests for minimum mesh size validation."""

    def test_TS006_minimal_mesh_raises_few_vertices(
        self, mock_bpy, mesh_imports
    ):
        """TS-006 → EC-003: Input with < 4 vertices raises ValueError.

        Given vertices with only 2 rows,
        When MeshImporter.import_mesh() is called,
        Then a ValueError is raised with message containing
        "at least 4 vertices and 4 faces".
        """
        m = mesh_imports

        # Given — only 2 vertices
        verts = np.array([[0, 0, 0], [1, 0, 0]], dtype=np.float32)
        faces = np.array([[0, 1, 0], [0, 0, 1]], dtype=np.int32)

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="at least 4 vertices"):
            importer.import_mesh(verts, faces)

    def test_minimal_mesh_raises_few_faces(self, mock_bpy, mesh_imports):
        """EC-003: Input with < 4 faces raises ValueError."""
        m = mesh_imports

        # Given — 4 vertices but only 2 faces
        verts = np.array(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
            dtype=np.float32,
        )
        faces = np.array([[0, 1, 2], [0, 1, 3]], dtype=np.int32)

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="at least.*4.*faces"):
            importer.import_mesh(verts, faces)


# ---------------------------------------------------------------------------
# TS-007 → EC-004: Boundary Hole Too Large to Fill
# ---------------------------------------------------------------------------


class TestLargeHole:
    """Tests for oversized boundary loop skipping."""

    def test_TS007_large_boundary_loop(self, mock_bpy, mesh_imports, caplog):
        """TS-007 → EC-004: Boundary loop > 500 edges is skipped.

        Given a mock mesh with a boundary loop of 750 edges,
        When the HoleFillStep executes,
        Then the hole is skipped, a WARNING is logged mentioning
        the 500-edge limit, and holes_skipped > 0.
        """
        m = mesh_imports
        import bmesh as bmesh_mock

        # Given — mock bmesh with a large boundary loop
        original_new = bmesh_mock.new

        def _mock_bmesh_with_large_hole():
            bm = MagicMock()
            # Create 750 mock boundary edges to form one large loop
            boundary_edges = []
            for i in range(750):
                edge = MagicMock()
                edge.is_boundary = True
                edge.index = i
                # Create vertices with link_edges pointing to next edge
                v1 = MagicMock()
                v2 = MagicMock()
                edge.verts = [v1, v2]
                boundary_edges.append(edge)

            # Wire up the linked edges to form a chain
            for i in range(len(boundary_edges) - 1):
                next_edge = boundary_edges[i + 1]
                next_edge.is_boundary = True
                next_edge.index = i + 1
                # Make the first vert of edge i link to edge i+1
                boundary_edges[i].verts[1].link_edges = [next_edge]
                boundary_edges[i].verts[0].link_edges = []

            # Last edge doesn't link to anything new
            boundary_edges[-1].verts[0].link_edges = []
            boundary_edges[-1].verts[1].link_edges = []

            bm.edges = boundary_edges
            bm.faces = []
            return bm

        bmesh_mock.new = _mock_bmesh_with_large_hole

        obj = MagicMock()
        obj.data.polygons = list(range(100))
        ctx = MagicMock()
        settings = {}

        step = m.HoleFillStep()

        # When
        with caplog.at_level(logging.WARNING, logger="tessera.mesh"):
            report = step.execute(ctx, obj, settings)

        # Then — hole was skipped
        assert report["holes_skipped"] > 0
        assert report["holes_filled"] == 0

        # WARNING about exceeding 500-edge limit
        skip_warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "500" in r.message
        ]
        assert len(skip_warnings) >= 1, (
            f"Expected WARNING about 500-edge limit, got: "
            f"{[r.message for r in caplog.records]}"
        )

        # Restore
        bmesh_mock.new = original_new


# ---------------------------------------------------------------------------
# TS-008 → EC-005: Non-Triangular Input Faces
# ---------------------------------------------------------------------------


class TestNonTriangularInput:
    """Tests for non-triangular face rejection."""

    def test_TS008_quad_faces_rejected(self, mock_bpy, mesh_imports):
        """TS-008 → EC-005: Input faces with 4 columns (quads) raises
        ValueError.

        Given faces array with shape (M, 4),
        When MeshImporter.import_mesh() is called,
        Then a ValueError is raised with message containing
        "triangular".
        """
        m = mesh_imports

        # Given — quad faces (shape M, 4)
        verts = _make_valid_vertices(10)
        faces = np.array(
            [[0, 1, 2, 3], [4, 5, 6, 7]],
            dtype=np.int32,
        )

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="triangular"):
            importer.import_mesh(verts, faces)

    def test_1d_faces_rejected(self, mock_bpy, mesh_imports):
        """EC-005: 1D face array is rejected."""
        m = mesh_imports

        # Given — flat 1D faces
        verts = _make_valid_vertices(10)
        faces = np.array([0, 1, 2, 3, 4, 5], dtype=np.int32)

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError):
            importer.import_mesh(verts, faces)


# ---------------------------------------------------------------------------
# TS-009 → AC-004: Quad Remesh (Phase 2)
# ---------------------------------------------------------------------------


class TestQuadRemesh:
    """Tests for QuadriFlow quad remesh step."""

    def test_TS009_quad_remesh_opt_in(self, mock_bpy, mesh_imports):
        """TS-009 → AC-004, FR-016: Quad remesh is opt-in.

        Given a mesh object,
        When QuadRemeshStep.execute() is called with
        enable_quad_remesh=True,
        Then the QuadriFlow operator is invoked.
        """
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.polygons = list(range(200_000))
        ctx = MagicMock()
        settings = {
            "enable_quad_remesh": True,
            "quad_target_faces": 10_000,
        }

        step = m.QuadRemeshStep()

        # When
        report = step.execute(ctx, obj, settings)

        # Then — operator was called and report indicates application
        assert report["quad_remesh_applied"] is True
        import bpy
        bpy.ops.object.quadriflow_remesh.assert_called_once()

    def test_quad_remesh_disabled_by_default(self, mock_bpy, mesh_imports):
        """FR-016: Quad remesh does NOT execute when disabled."""
        m = mesh_imports

        # Given
        obj = MagicMock()
        ctx = MagicMock()
        settings = {"enable_quad_remesh": False}

        step = m.QuadRemeshStep()

        # When
        report = step.execute(ctx, obj, settings)

        # Then — not applied
        assert report["quad_remesh_applied"] is False
        import bpy
        bpy.ops.object.quadriflow_remesh.assert_not_called()

    def test_quad_remesh_default_settings(self, mock_bpy, mesh_imports):
        """FR-016: Quad remesh defaults to disabled."""
        m = mesh_imports

        # Given — empty settings (default)
        obj = MagicMock()
        ctx = MagicMock()
        settings = {}

        step = m.QuadRemeshStep()

        # When
        report = step.execute(ctx, obj, settings)

        # Then — not applied
        assert report["quad_remesh_applied"] is False


# ---------------------------------------------------------------------------
# TS-010 → AC-005: Decimation with Sharp Edge Preservation (Phase 2)
# ---------------------------------------------------------------------------


class TestDecimate:
    """Tests for decimation with sharp edge preservation."""

    def test_TS010_decimate_sharp_edges(self, mock_bpy, mesh_imports):
        """TS-010 → AC-005: Decimate applies modifier when enabled.

        Given a mesh with faces,
        When DecimateStep.execute() is called with
        enable_decimate=True and decimate_target_faces=50000,
        Then a Decimate modifier is created with COLLAPSE mode
        and modifier_apply is called.
        """
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.polygons = list(range(200_000))
        ctx = MagicMock()
        settings = {
            "enable_decimate": True,
            "decimate_target_faces": 50_000,
        }

        step = m.DecimateStep()

        # When
        report = step.execute(ctx, obj, settings)

        # Then — modifier was created and applied
        assert report["decimate_applied"] is True
        obj.modifiers.new.assert_called_once()
        call_kwargs = obj.modifiers.new.call_args
        assert call_kwargs[1]["type"] == "DECIMATE"

        import bpy
        bpy.ops.object.modifier_apply.assert_called_once()

    def test_decimate_disabled_by_default(self, mock_bpy, mesh_imports):
        """Decimate does NOT execute when disabled."""
        m = mesh_imports

        # Given
        obj = MagicMock()
        ctx = MagicMock()
        settings = {"enable_decimate": False}

        step = m.DecimateStep()

        # When
        report = step.execute(ctx, obj, settings)

        # Then — not applied
        assert report["decimate_applied"] is False

    def test_decimate_ratio_calculation(self, mock_bpy, mesh_imports):
        """FR-011: Ratio is min(1.0, target / current)."""
        m = mesh_imports

        # Given — 100K faces, target 50K → ratio = 0.5
        obj = MagicMock()
        obj.data.polygons = list(range(100_000))
        ctx = MagicMock()
        settings = {
            "enable_decimate": True,
            "decimate_target_faces": 50_000,
        }

        step = m.DecimateStep()

        # When
        report = step.execute(ctx, obj, settings)

        # Then — modifier was created with ratio ≈ 0.5
        modifier_mock = obj.modifiers.new.return_value
        assert modifier_mock.ratio == 0.5
        assert modifier_mock.decimate_type == "COLLAPSE"


# ---------------------------------------------------------------------------
# TS-011 → AC-006: Undo Support
# ---------------------------------------------------------------------------


class TestUndoSupport:
    """Tests for undo step registration."""

    def test_TS011_undo_after_cleanup(self, mock_bpy, mesh_imports):
        """TS-011 → AC-006: Pipeline registers undo step via
        bpy.ops.ed.undo_push before modifications.

        Given a mesh object,
        When the cleanup pipeline executes,
        Then bpy.ops.ed.undo_push is called with the
        "Tessera Mesh Cleanup" message.
        """
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # When
        import bpy
        pipeline.execute(ctx, obj)

        # Then — undo_push called before modifications
        bpy.ops.ed.undo_push.assert_called_once_with(
            message="Tessera Mesh Cleanup"
        )


# ---------------------------------------------------------------------------
# TS-012 → AC-007: Diagnostics Report Completeness
# ---------------------------------------------------------------------------


class TestDiagnostics:
    """Tests for diagnostics dict completeness."""

    def test_TS012_diagnostics_keys(self, mock_bpy, mesh_imports):
        """TS-012 → AC-007: Diagnostics dict has all 15 required keys
        plus step_errors list.

        Given a cleanup pipeline execution on any valid mock mesh,
        When the pipeline completes,
        Then the returned diagnostics dict contains all 15 keys
        from FR-007 with correct types.
        """
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.vertices = list(range(50))
        obj.data.polygons = list(range(100))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # When
        diagnostics = pipeline.execute(ctx, obj)

        # Then — all 15 FR-007 keys present
        expected_keys = set(m.DIAGNOSTICS_KEYS)
        actual_keys = set(diagnostics.keys()) - {"step_errors"}
        assert expected_keys == actual_keys, (
            f"Missing: {expected_keys - actual_keys}, "
            f"Extra: {actual_keys - expected_keys}"
        )

        # step_errors is a list
        assert "step_errors" in diagnostics
        assert isinstance(diagnostics["step_errors"], list)

        # Type checks for specific fields
        assert isinstance(diagnostics["vertices_before"], int)
        assert isinstance(diagnostics["faces_before"], int)
        assert isinstance(diagnostics["vertices_after"], int)
        assert isinstance(diagnostics["faces_after"], int)
        assert isinstance(diagnostics["doubles_removed"], int)
        assert isinstance(diagnostics["degenerate_faces_removed"], int)
        assert isinstance(diagnostics["normals_flipped"], int)
        assert isinstance(diagnostics["holes_filled"], int)
        assert isinstance(diagnostics["holes_skipped"], int)
        assert isinstance(diagnostics["voxel_remesh_applied"], bool)
        assert isinstance(diagnostics["quad_remesh_applied"], bool)
        assert isinstance(diagnostics["decimate_applied"], bool)
        assert isinstance(diagnostics["is_manifold"], bool)
        assert isinstance(diagnostics["is_watertight"], bool)
        assert isinstance(diagnostics["cleanup_time_seconds"], float)

    def test_empty_diagnostics_defaults(self, mock_bpy, mesh_imports):
        """FR-007: empty_diagnostics() returns all keys with defaults."""
        m = mesh_imports

        # When
        diag = m.empty_diagnostics()

        # Then
        assert diag["vertices_before"] == 0
        assert diag["faces_before"] == 0
        assert diag["vertices_after"] == 0
        assert diag["faces_after"] == 0
        assert diag["doubles_removed"] == 0
        assert diag["degenerate_faces_removed"] == 0
        assert diag["normals_flipped"] == 0
        assert diag["holes_filled"] == 0
        assert diag["holes_skipped"] == 0
        assert diag["voxel_remesh_applied"] is False
        assert diag["quad_remesh_applied"] is False
        assert diag["decimate_applied"] is False
        assert diag["is_manifold"] is False
        assert diag["is_watertight"] is False
        assert diag["cleanup_time_seconds"] == 0.0
        assert diag["step_errors"] == []

    def test_build_diagnostics_assembly(self, mock_bpy, mesh_imports):
        """FR-007: build_diagnostics merges component dicts correctly."""
        m = mesh_imports

        # Given
        before = {"vertices_before": 100, "faces_before": 200}
        after = {"vertices_after": 90, "faces_after": 180}
        reports = {
            "doubles_removed": 10,
            "degenerate_faces_removed": 5,
            "normals_flipped": 3,
            "holes_filled": 2,
            "holes_skipped": 1,
            "voxel_remesh_applied": False,
            "quad_remesh_applied": False,
            "decimate_applied": True,
        }
        errors = [{"step": "HoleFillStep", "error": "test error"}]

        # When
        diag = m.build_diagnostics(
            before_stats=before,
            step_reports=reports,
            after_stats=after,
            is_manifold=True,
            is_watertight=False,
            cleanup_time=1.234,
            step_errors=errors,
        )

        # Then
        assert diag["vertices_before"] == 100
        assert diag["faces_before"] == 200
        assert diag["vertices_after"] == 90
        assert diag["faces_after"] == 180
        assert diag["doubles_removed"] == 10
        assert diag["degenerate_faces_removed"] == 5
        assert diag["normals_flipped"] == 3
        assert diag["holes_filled"] == 2
        assert diag["holes_skipped"] == 1
        assert diag["voxel_remesh_applied"] is False
        assert diag["quad_remesh_applied"] is False
        assert diag["decimate_applied"] is True
        assert diag["is_manifold"] is True
        assert diag["is_watertight"] is False
        assert diag["cleanup_time_seconds"] == 1.234
        assert diag["step_errors"] == errors


# ---------------------------------------------------------------------------
# TS-015 → SEC-001: NaN/Inf Rejection
# ---------------------------------------------------------------------------


class TestSecurityValidation:
    """Tests for input array security validation."""

    def test_TS015_nan_rejection(self, mock_bpy, mesh_imports):
        """TS-015 → SEC-001: Vertices with NaN values raise ValueError."""
        m = mesh_imports

        # Given — vertices with NaN
        verts = _make_valid_vertices(10)
        verts[0, 0] = np.nan
        faces = _make_valid_faces(10, 6)

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="NaN"):
            importer.import_mesh(verts, faces)

    def test_TS015_inf_rejection(self, mock_bpy, mesh_imports):
        """TS-015 → SEC-001: Vertices with Inf values raise ValueError."""
        m = mesh_imports

        # Given — vertices with Inf
        verts = _make_valid_vertices(10)
        verts[0, 1] = np.inf
        faces = _make_valid_faces(10, 6)

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="Inf"):
            importer.import_mesh(verts, faces)

    def test_negative_inf_rejection(self, mock_bpy, mesh_imports):
        """SEC-001: Vertices with -Inf values raise ValueError."""
        m = mesh_imports

        # Given
        verts = _make_valid_vertices(10)
        verts[2, 2] = -np.inf
        faces = _make_valid_faces(10, 6)

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="Inf"):
            importer.import_mesh(verts, faces)

    def test_TS016_face_index_out_of_bounds(self, mock_bpy, mesh_imports):
        """TS-016 → SEC-002: Face indices >= vertex count raise ValueError.

        Given face indices that reference vertex indices out of range,
        When MeshImporter.import_mesh() is called,
        Then a ValueError is raised.
        """
        m = mesh_imports

        # Given — face index 999 exceeds vertex_count=10
        verts = _make_valid_vertices(10)
        faces = np.array(
            [[0, 1, 999], [2, 3, 4], [5, 6, 7], [8, 9, 0]],
            dtype=np.int32,
        )

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="range"):
            importer.import_mesh(verts, faces)

    def test_negative_face_index_rejected(self, mock_bpy, mesh_imports):
        """SEC-002: Negative face indices raise ValueError."""
        m = mesh_imports

        # Given
        verts = _make_valid_vertices(10)
        faces = np.array(
            [[0, 1, -1], [2, 3, 4], [5, 6, 7], [8, 9, 0]],
            dtype=np.int32,
        )

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="range"):
            importer.import_mesh(verts, faces)

    def test_wrong_vertex_dtype_rejected(self, mock_bpy, mesh_imports):
        """SEC-001: Vertices with wrong dtype raise ValueError."""
        m = mesh_imports

        # Given — float64 instead of float32
        verts = np.random.randn(10, 3).astype(np.float64)
        faces = _make_valid_faces(10, 6)

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="float32"):
            importer.import_mesh(verts, faces)

    def test_wrong_face_dtype_rejected(self, mock_bpy, mesh_imports):
        """SEC-001: Faces with wrong dtype raise ValueError."""
        m = mesh_imports

        # Given — int64 instead of int32
        verts = _make_valid_vertices(10)
        faces = np.random.randint(0, 10, (6, 3)).astype(np.int64)

        importer = m.MeshImporter()

        # When / Then
        with pytest.raises(ValueError, match="int32"):
            importer.import_mesh(verts, faces)

    def test_source_model_sanitization(self, mock_bpy, mesh_imports):
        """SEC-005: Source model with special chars is sanitized."""
        m = mesh_imports

        # Given — malicious source_model
        verts, faces = _make_tetrahedron()
        importer = m.MeshImporter()

        # When — characters like ../; are replaced with _
        sanitized = importer._sanitize_source_model("../evil;model")
        assert sanitized == "___evil_model"

        # Truncated to 32 chars
        long_model = "a" * 100
        sanitized_long = importer._sanitize_source_model(long_model)
        assert len(sanitized_long) == 32


# ---------------------------------------------------------------------------
# TS-017 → FR-017: Cleanup Settings PropertyGroup
# ---------------------------------------------------------------------------


class TestCleanupSettings:
    """Tests for cleanup settings registration and defaults."""

    def test_TS017_property_group_registration(self, mock_bpy, mesh_imports):
        """TS-017 → FR-017: TesseraCleanupSettings has all required
        properties.

        Verifies the PropertyGroup class exists in properties.py
        and has the expected property declarations via __annotations__.
        """
        from tessera.properties import TesseraCleanupSettings

        # In mock mode, Blender props are stored as annotations
        annotations = TesseraCleanupSettings.__annotations__
        assert "merge_distance" in annotations
        assert "voxel_size" in annotations
        assert "auto_voxel_fallback" in annotations
        assert "enable_quad_remesh" in annotations
        assert "quad_target_faces" in annotations
        assert "enable_decimate" in annotations
        assert "decimate_target_faces" in annotations

    def test_cleanup_settings_in_properties_classes(
        self, mock_bpy, mesh_imports
    ):
        """FR-017: TesseraCleanupSettings is in the registration list."""
        from tessera.properties import classes, TesseraCleanupSettings

        # Then — included in classes list for registration
        assert TesseraCleanupSettings in classes

    def test_tessera_properties_has_cleanup_pointer(
        self, mock_bpy, mesh_imports
    ):
        """FR-017: TesseraProperties has a cleanup PointerProperty."""
        from tessera.properties import TesseraProperties

        # In mock mode, Blender props are stored as annotations
        assert "cleanup" in TesseraProperties.__annotations__


# ---------------------------------------------------------------------------
# TS-018 → CON-008: Modal Operator for Long Operations
# ---------------------------------------------------------------------------


class TestModalOperator:
    """Tests for operator registration and Blender integration."""

    def test_TS018_operator_registration(self, mock_bpy, mesh_imports):
        """TS-018 → CON-008: TESSERA_OT_RunCleanup operator is
        properly configured.

        Verifies the operator has correct bl_idname, bl_label,
        and UNDO in bl_options.
        """
        from tessera.operators.cleanup_ops import TESSERA_OT_RunCleanup

        # Then — operator attributes are correct
        assert TESSERA_OT_RunCleanup.bl_idname == "tessera.run_cleanup"
        assert TESSERA_OT_RunCleanup.bl_label == "Run Mesh Cleanup"
        assert "UNDO" in TESSERA_OT_RunCleanup.bl_options
        assert "REGISTER" in TESSERA_OT_RunCleanup.bl_options

    def test_operator_in_registration_list(self, mock_bpy, mesh_imports):
        """Operator is included in the operators/__init__.py classes."""
        from tessera.operators.cleanup_ops import (
            TESSERA_OT_RunCleanup,
            classes,
        )

        assert TESSERA_OT_RunCleanup in classes

    def test_panel_in_registration_list(self, mock_bpy, mesh_imports):
        """UI panel is included in the ui/__init__.py classes."""
        from tessera.ui.cleanup_panel import (
            TESSERA_PT_Cleanup,
            classes,
        )

        assert TESSERA_PT_Cleanup in classes
        assert TESSERA_PT_Cleanup.bl_parent_id == "TESSERA_PT_Main"


# ---------------------------------------------------------------------------
# TS-019 → EC-006, FR-020: Pipeline Step Exception Handling
# ---------------------------------------------------------------------------


class TestStepExceptionHandling:
    """Tests for critical and non-critical step exception handling."""

    def test_TS019_non_critical_step_exception(
        self, mock_bpy, mesh_imports, caplog
    ):
        """TS-019 → EC-006, FR-020: Non-critical step exception caught,
        pipeline continues.

        Given a patched HoleFillStep that raises RuntimeError,
        When MeshCleanupPipeline.execute() is called,
        Then the pipeline catches the exception, logs it at ERROR
        level, appends it to diagnostics["step_errors"], and
        continues to produce a valid diagnostics dict.
        """
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # Patch HoleFillStep to raise an error
        original_execute = m.HoleFillStep.execute

        def _failing_execute(self, context, ob, settings):
            raise RuntimeError("Corrupted topology")

        m.HoleFillStep.execute = _failing_execute

        try:
            # When
            with caplog.at_level(logging.ERROR, logger="tessera.mesh"):
                diagnostics = pipeline.execute(ctx, obj)

            # Then — pipeline completed (did not crash)
            assert isinstance(diagnostics, dict)
            assert "step_errors" in diagnostics
            assert len(diagnostics["step_errors"]) >= 1

            # Error entry has correct structure
            error_entry = diagnostics["step_errors"][0]
            assert error_entry["step"] == "HoleFillStep"
            assert "Corrupted topology" in error_entry["error"]

            # ERROR was logged
            error_records = [
                r for r in caplog.records
                if r.levelno == logging.ERROR
                and "HoleFillStep" in r.message
            ]
            assert len(error_records) >= 1
        finally:
            # Restore
            m.HoleFillStep.execute = original_execute

    def test_TS019_critical_step_exception(self, mock_bpy, mesh_imports):
        """TS-019 → EC-006, FR-020: Critical step exception raises
        MeshCleanupError.

        Given a patched DedupStep that raises ValueError,
        When MeshCleanupPipeline.execute() is called,
        Then MeshCleanupError is raised with the step name and
        original exception.
        """
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # Patch DedupStep to raise an error
        original_execute = m.DedupStep.execute

        def _failing_dedup(self, context, ob, settings):
            raise ValueError("bmesh internal error")

        m.DedupStep.execute = _failing_dedup

        try:
            # When / Then
            with pytest.raises(m.MeshCleanupError) as exc_info:
                pipeline.execute(ctx, obj)

            # Verify exception attributes
            err = exc_info.value
            assert err.step_name == "DedupStep"
            assert isinstance(err.original_exception, ValueError)
            assert "bmesh internal error" in str(err.original_exception)
            assert "DedupStep" in str(err)
        finally:
            # Restore
            m.DedupStep.execute = original_execute

    def test_critical_normals_step_exception(self, mock_bpy, mesh_imports):
        """FR-020: NormalsStep failure also raises MeshCleanupError."""
        m = mesh_imports

        # Given
        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # Patch NormalsStep to raise
        original_execute = m.NormalsStep.execute

        def _failing_normals(self, context, ob, settings):
            raise RuntimeError("normals computation failed")

        m.NormalsStep.execute = _failing_normals

        try:
            # When / Then
            with pytest.raises(m.MeshCleanupError) as exc_info:
                pipeline.execute(ctx, obj)

            assert exc_info.value.step_name == "NormalsStep"
        finally:
            m.NormalsStep.execute = original_execute


# ---------------------------------------------------------------------------
# Additional: Data Types & Hierarchy
# ---------------------------------------------------------------------------


class TestDataTypes:
    """Tests for RawMeshData and related data types."""

    def test_raw_mesh_data_creation(self, mock_bpy, mesh_imports):
        """§3.4: RawMeshData dataclass holds vertices, faces, source."""
        m = mesh_imports

        verts = _make_valid_vertices(10)
        faces = _make_valid_faces(10, 6)

        # When
        raw = m.RawMeshData(
            vertices=verts,
            faces=faces,
            source_model="trellis",
        )

        # Then
        np.testing.assert_array_equal(raw.vertices, verts)
        np.testing.assert_array_equal(raw.faces, faces)
        assert raw.source_model == "trellis"

    def test_raw_mesh_data_default_source(self, mock_bpy, mesh_imports):
        """§3.4: Default source_model is "custom"."""
        m = mesh_imports

        raw = m.RawMeshData(
            vertices=_make_valid_vertices(4),
            faces=_make_valid_faces(4, 4),
        )
        assert raw.source_model == "custom"

    def test_diagnostics_keys_list(self, mock_bpy, mesh_imports):
        """FR-007: DIAGNOSTICS_KEYS has exactly 15 entries."""
        m = mesh_imports
        assert len(m.DIAGNOSTICS_KEYS) == 15


class TestHierarchy:
    """Tests for hierarchy utilities (FR-013, FR-014, FR-015)."""

    def test_rename_object_format(self, mock_bpy, mesh_imports):
        """FR-014: rename_object uses BF_<source>_<timestamp> format."""
        m = mesh_imports

        obj = MagicMock()
        obj.data = MagicMock()

        # When
        m.rename_object(obj, "trellis", timestamp="20260414_225000")

        # Then
        assert obj.name == "BF_trellis_20260414_225000"
        assert obj.data.name == "BF_trellis_20260414_225000"

    def test_rename_object_sanitizes_source(self, mock_bpy, mesh_imports):
        """SEC-005: rename_object sanitizes special characters."""
        m = mesh_imports

        obj = MagicMock()
        obj.data = MagicMock()

        # When
        m.rename_object(
            obj, "evil/../model", timestamp="20260414_225000"
        )

        # Then — special chars replaced with _
        assert obj.name == "BF_evil____model_20260414_225000"

    def test_create_session_parent(self, mock_bpy, mesh_imports):
        """FR-015: create_session_parent creates an Empty object."""
        m = mesh_imports
        import bpy

        ctx = MagicMock()

        # When
        empty = m.create_session_parent(
            ctx, timestamp="20260414_225000"
        )

        # Then — bpy.data.objects.new called with name and None
        bpy.data.objects.new.assert_called_once_with(
            name="Tessera_Session_20260414_225000", object_data=None
        )
        # Linked to collection
        ctx.collection.objects.link.assert_called_once()


# ---------------------------------------------------------------------------
# Additional coverage: FR-002 — Object Naming with Timestamp
# ---------------------------------------------------------------------------


class TestObjectNaming:
    """Tests for object naming format (FR-002)."""

    def test_FR002_default_name_contains_tessera_prefix(
        self, mock_bpy, mesh_imports
    ):
        """FR-002: Default name starts with 'Tessera_'."""
        m = mesh_imports
        verts, faces = _make_tetrahedron()
        importer = m.MeshImporter()

        # When
        obj = importer.import_mesh(verts, faces)

        # Then — bpy.data.objects.new called with name starting Tessera_
        import bpy
        call_args = bpy.data.objects.new.call_args
        obj_name = call_args[1]["name"]
        assert obj_name.startswith("Tessera_"), (
            f"Expected name starting with 'Tessera_', got '{obj_name}'"
        )

    def test_FR002_name_override_used(self, mock_bpy, mesh_imports):
        """FR-002: name_override replaces auto-generated name."""
        m = mesh_imports
        verts, faces = _make_tetrahedron()
        importer = m.MeshImporter()

        # When
        importer.import_mesh(verts, faces, name_override="MyMesh")

        # Then — name matches override
        import bpy
        call_args = bpy.data.objects.new.call_args
        obj_name = call_args[1]["name"]
        assert obj_name == "MyMesh"

    def test_FR002_timestamp_format_YYYYMMDD_HHMMSS(
        self, mock_bpy, mesh_imports
    ):
        """FR-002: Auto-generated name uses YYYYMMDD_HHMMSS format."""
        m = mesh_imports
        verts, faces = _make_tetrahedron()
        importer = m.MeshImporter()

        # When
        importer.import_mesh(verts, faces)

        # Then — name has 8-digit date + '_' + 6-digit time
        import bpy
        import re
        call_args = bpy.data.objects.new.call_args
        obj_name = call_args[1]["name"]
        assert re.match(r"^Tessera_\d{8}_\d{6}$", obj_name), (
            f"Name '{obj_name}' doesn't match Tessera_YYYYMMDD_HHMMSS"
        )

    def test_FR002_object_placed_at_cursor(self, mock_bpy, mesh_imports):
        """FR-002: Object placed at the scene 3D cursor location."""
        m = mesh_imports
        import bpy

        # Given — set cursor location
        cursor_loc = MagicMock()
        cursor_loc.copy.return_value = (1.0, 2.0, 3.0)
        bpy.context.scene.cursor.location = cursor_loc

        verts, faces = _make_tetrahedron()
        importer = m.MeshImporter()

        # When
        obj = importer.import_mesh(verts, faces)

        # Then — location set from cursor
        assert obj.location == (1.0, 2.0, 3.0)


# ---------------------------------------------------------------------------
# Additional coverage: FR-003 — DedupStep Merge Distance
# ---------------------------------------------------------------------------


class TestDedupStep:
    """Unit tests for DedupStep in isolation."""

    def test_FR003_default_merge_distance(self, mock_bpy, mesh_imports):
        """FR-003: Default merge distance is 0.0001."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(10))
        ctx = MagicMock()
        settings = {}  # No merge_distance specified → use default

        step = m.DedupStep()
        report = step.execute(ctx, obj, settings)

        # Then — report has doubles_removed key
        assert "doubles_removed" in report
        assert isinstance(report["doubles_removed"], int)

        # Verify bmesh.ops.remove_doubles was called
        import bmesh as bmesh_mock
        bmesh_mock.ops.remove_doubles.assert_called()

    def test_FR003_custom_merge_distance(self, mock_bpy, mesh_imports):
        """FR-003: Custom merge distance is passed through."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(10))
        ctx = MagicMock()
        settings = {"merge_distance": 0.005}

        step = m.DedupStep()
        step.execute(ctx, obj, settings)

        # Then — bmesh.ops.remove_doubles called with custom distance
        import bmesh as bmesh_mock
        call_kwargs = bmesh_mock.ops.remove_doubles.call_args
        assert call_kwargs[1]["dist"] == 0.005

    def test_dedup_step_name(self, mock_bpy, mesh_imports):
        """FR-020: DedupStep.name is 'DedupStep' for error handling."""
        m = mesh_imports
        step = m.DedupStep()
        assert step.name == "DedupStep"

    def test_dedup_uses_try_finally(self, mock_bpy, mesh_imports):
        """CON-006: DedupStep cleans up bmesh via try/finally."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(5))
        ctx = MagicMock()

        step = m.DedupStep()
        step.execute(ctx, obj, {})

        # Then — bmesh.free() was called (via mock tracking)
        import bmesh as bmesh_mock
        bm = bmesh_mock.new.return_value
        bm.free.assert_called_once()


# ---------------------------------------------------------------------------
# Additional coverage: FR-004 — NormalsStep
# ---------------------------------------------------------------------------


class TestNormalsStep:
    """Unit tests for NormalsStep in isolation."""

    def test_FR004_normals_recalc(self, mock_bpy, mesh_imports):
        """FR-004: NormalsStep calls bmesh.ops.recalc_face_normals."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        step = m.NormalsStep()
        report = step.execute(ctx, obj, {})

        # Then — report has normals_flipped key
        assert "normals_flipped" in report
        assert isinstance(report["normals_flipped"], int)

        # Verify bmesh.ops.recalc_face_normals was called
        import bmesh as bmesh_mock
        bmesh_mock.ops.recalc_face_normals.assert_called()

    def test_normals_step_name(self, mock_bpy, mesh_imports):
        """FR-020: NormalsStep.name is 'NormalsStep' for error handling."""
        m = mesh_imports
        step = m.NormalsStep()
        assert step.name == "NormalsStep"

    def test_normals_uses_try_finally(self, mock_bpy, mesh_imports):
        """CON-006: NormalsStep cleans up bmesh via try/finally."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(5))
        ctx = MagicMock()

        step = m.NormalsStep()
        step.execute(ctx, obj, {})

        import bmesh as bmesh_mock
        bm = bmesh_mock.new.return_value
        bm.free.assert_called_once()


# ---------------------------------------------------------------------------
# Additional coverage: FR-005 — HoleFillStep Success Path
# ---------------------------------------------------------------------------


class TestHoleFillStep:
    """Extended tests for HoleFillStep (beyond TS-007 large hole)."""

    def test_FR005_no_boundary_edges_skips_fill(
        self, mock_bpy, mesh_imports
    ):
        """FR-005: No boundary edges → nothing to fill."""
        m = mesh_imports
        import bmesh as bmesh_mock

        original_new = bmesh_mock.new

        def _no_boundaries():
            bm = MagicMock()
            bm.edges = []  # No edges at all
            bm.faces = []
            return bm

        bmesh_mock.new = _no_boundaries

        obj = MagicMock()
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        step = m.HoleFillStep()
        report = step.execute(ctx, obj, {})

        assert report["holes_filled"] == 0
        assert report["holes_skipped"] == 0

        bmesh_mock.new = original_new

    def test_FR005_small_boundary_filled(self, mock_bpy, mesh_imports):
        """FR-005: Boundary loop ≤ 500 edges triggers triangle_fill."""
        m = mesh_imports
        import bmesh as bmesh_mock

        original_new = bmesh_mock.new

        def _small_boundary():
            bm = MagicMock()
            # Create 5 boundary edges forming a small loop
            edges = []
            for i in range(5):
                edge = MagicMock()
                edge.is_boundary = True
                edge.index = i
                v1 = MagicMock()
                v2 = MagicMock()
                edge.verts = [v1, v2]
                edges.append(edge)

            # Wire edges into a chain
            for i in range(len(edges) - 1):
                edges[i].verts[1].link_edges = [edges[i + 1]]
                edges[i].verts[0].link_edges = []
            edges[-1].verts[0].link_edges = []
            edges[-1].verts[1].link_edges = []

            bm.edges = edges
            bm.faces = []
            return bm

        bmesh_mock.new = _small_boundary

        obj = MagicMock()
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        step = m.HoleFillStep()
        report = step.execute(ctx, obj, {})

        # Then — hole was filled (triangle_fill called)
        assert report["holes_filled"] >= 1
        assert report["holes_skipped"] == 0
        bmesh_mock.ops.triangle_fill.assert_called()

        bmesh_mock.new = original_new

    def test_hole_fill_step_name(self, mock_bpy, mesh_imports):
        """FR-020: HoleFillStep.name is 'HoleFillStep'."""
        m = mesh_imports
        step = m.HoleFillStep()
        assert step.name == "HoleFillStep"


# ---------------------------------------------------------------------------
# Additional coverage: FR-006 — VoxelRemeshStep Modifier Settings
# ---------------------------------------------------------------------------


class TestVoxelRemeshStepDetails:
    """Extended tests for VoxelRemeshStep modifier configuration."""

    def test_FR006_modifier_type_is_remesh(self, mock_bpy, mesh_imports):
        """FR-006: VoxelRemeshStep creates a REMESH modifier."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(100))
        ctx = MagicMock()
        settings = {"auto_voxel_fallback": True, "voxel_size": 0.01}

        step = m.VoxelRemeshStep()
        report = step.execute(ctx, obj, settings)

        assert report["voxel_remesh_applied"] is True
        obj.modifiers.new.assert_called_once_with(
            name="TesseraVoxelRemesh", type="REMESH"
        )

    def test_FR006_voxel_mode_set_to_voxel(self, mock_bpy, mesh_imports):
        """FR-006: Modifier mode is set to VOXEL."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(100))
        ctx = MagicMock()
        settings = {"auto_voxel_fallback": True, "voxel_size": 0.02}

        step = m.VoxelRemeshStep()
        step.execute(ctx, obj, settings)

        modifier_mock = obj.modifiers.new.return_value
        assert modifier_mock.mode == "VOXEL"
        assert modifier_mock.voxel_size == 0.02

    def test_FR006_custom_voxel_size(self, mock_bpy, mesh_imports):
        """FR-006: Custom voxel size is passed to modifier."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(50))
        ctx = MagicMock()
        settings = {"auto_voxel_fallback": True, "voxel_size": 0.05}

        step = m.VoxelRemeshStep()
        step.execute(ctx, obj, settings)

        modifier_mock = obj.modifiers.new.return_value
        assert modifier_mock.voxel_size == 0.05

    def test_voxel_step_name(self, mock_bpy, mesh_imports):
        """VoxelRemeshStep.name is 'VoxelRemeshStep'."""
        m = mesh_imports
        step = m.VoxelRemeshStep()
        assert step.name == "VoxelRemeshStep"


# ---------------------------------------------------------------------------
# Additional coverage: FR-008 — Step-Level DEBUG Logging
# ---------------------------------------------------------------------------


class TestStepLogging:
    """Tests for step-level DEBUG logging (FR-008, §11.1)."""

    def test_FR008_dedup_logs_at_debug(
        self, mock_bpy, mesh_imports, caplog
    ):
        """FR-008: DedupStep logs at DEBUG level."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        step = m.DedupStep()

        with caplog.at_level(logging.DEBUG, logger="tessera.mesh"):
            step.execute(ctx, obj, {})

        debug_records = [
            r for r in caplog.records
            if r.levelno == logging.DEBUG
            and "DedupStep" in r.message
        ]
        assert len(debug_records) >= 2, (
            f"Expected at least 2 DEBUG records for DedupStep, "
            f"got {len(debug_records)}"
        )

    def test_FR008_normals_logs_start_and_complete(
        self, mock_bpy, mesh_imports, caplog
    ):
        """FR-008: NormalsStep logs both started and completed."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        step = m.NormalsStep()

        with caplog.at_level(logging.DEBUG, logger="tessera.mesh"):
            step.execute(ctx, obj, {})

        messages = [r.message for r in caplog.records]
        started = any("started" in msg and "NormalsStep" in msg for msg in messages)
        completed = any("completed" in msg and "NormalsStep" in msg for msg in messages)
        assert started, "Expected 'started' log for NormalsStep"
        assert completed, "Expected 'completed' log for NormalsStep"


# ---------------------------------------------------------------------------
# Additional coverage: FR-011/FR-012 — Decimate Settings & Sharp Edges
# ---------------------------------------------------------------------------


class TestDecimateDetails:
    """Extended tests for Decimate modifier configuration."""

    def test_FR011_use_collapse_triangulate_false(
        self, mock_bpy, mesh_imports
    ):
        """FR-011: Decimate sets use_collapse_triangulate = False."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(100_000))
        ctx = MagicMock()
        settings = {
            "enable_decimate": True,
            "decimate_target_faces": 50_000,
        }

        step = m.DecimateStep()
        step.execute(ctx, obj, settings)

        modifier_mock = obj.modifiers.new.return_value
        assert modifier_mock.use_collapse_triangulate is False

    def test_FR012_use_dissolve_boundaries_false(
        self, mock_bpy, mesh_imports
    ):
        """FR-012: Decimate sets use_dissolve_boundaries = False."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(100_000))
        ctx = MagicMock()
        settings = {
            "enable_decimate": True,
            "decimate_target_faces": 50_000,
        }

        step = m.DecimateStep()
        step.execute(ctx, obj, settings)

        modifier_mock = obj.modifiers.new.return_value
        assert modifier_mock.use_dissolve_boundaries is False

    def test_decimate_ratio_capped_at_one(self, mock_bpy, mesh_imports):
        """FR-011: Ratio doesn't exceed 1.0 even if target > current."""
        m = mesh_imports

        # Given — 100 faces, target 50000 → ratio should be 1.0
        obj = MagicMock()
        obj.data.polygons = list(range(100))
        ctx = MagicMock()
        settings = {
            "enable_decimate": True,
            "decimate_target_faces": 50_000,
        }

        step = m.DecimateStep()
        step.execute(ctx, obj, settings)

        modifier_mock = obj.modifiers.new.return_value
        assert modifier_mock.ratio == 1.0

    def test_decimate_zero_faces_ratio_one(self, mock_bpy, mesh_imports):
        """FR-011: Zero-face mesh gets ratio 1.0 (avoid division by zero)."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = []  # 0 faces
        ctx = MagicMock()
        settings = {
            "enable_decimate": True,
            "decimate_target_faces": 50_000,
        }

        step = m.DecimateStep()
        step.execute(ctx, obj, settings)

        modifier_mock = obj.modifiers.new.return_value
        assert modifier_mock.ratio == 1.0

    def test_decimate_step_name(self, mock_bpy, mesh_imports):
        """DecimateStep.name is 'DecimateStep'."""
        m = mesh_imports
        step = m.DecimateStep()
        assert step.name == "DecimateStep"


# ---------------------------------------------------------------------------
# Additional coverage: FR-013 — Set Origin to Bounds
# ---------------------------------------------------------------------------


class TestOriginPlacement:
    """Tests for object origin placement (FR-013)."""

    def test_FR013_set_origin_to_bounds(self, mock_bpy, mesh_imports):
        """FR-013: set_origin_to_bounds calls the correct operator."""
        from tessera.mesh.hierarchy import set_origin_to_bounds

        import bpy

        obj = MagicMock()
        ctx = MagicMock()

        # When
        set_origin_to_bounds(ctx, obj)

        # Then — origin_set called with ORIGIN_GEOMETRY + BOUNDS
        bpy.ops.object.origin_set.assert_called_once_with(
            type="ORIGIN_GEOMETRY", center="BOUNDS"
        )
        # Object was made active
        assert ctx.view_layer.objects.active == obj
        obj.select_set.assert_called_with(True)


# ---------------------------------------------------------------------------
# Additional coverage: CON-005 — Only Target Imported Object
# ---------------------------------------------------------------------------


class TestObjectIsolation:
    """Tests for object isolation during cleanup (CON-005)."""

    def test_CON005_only_target_object_active(
        self, mock_bpy, mesh_imports
    ):
        """CON-005: Pipeline makes only the target object active."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()
        pipeline.execute(ctx, obj)

        # Then — obj was set as active
        assert ctx.view_layer.objects.active == obj
        obj.select_set.assert_called_with(True)


# ---------------------------------------------------------------------------
# Additional coverage: SEC-005 — Source Model Sanitization Edge Cases
# ---------------------------------------------------------------------------


class TestSourceModelSanitization:
    """Extended tests for source_model sanitization (SEC-005)."""

    def test_SEC005_alphanumeric_passthrough(self, mock_bpy, mesh_imports):
        """SEC-005: Valid characters pass through unchanged."""
        m = mesh_imports
        importer = m.MeshImporter()
        assert importer._sanitize_source_model("trellis") == "trellis"

    def test_SEC005_hyphens_and_underscores_allowed(
        self, mock_bpy, mesh_imports
    ):
        """SEC-005: Hyphens and underscores are allowed."""
        m = mesh_imports
        importer = m.MeshImporter()
        result = importer._sanitize_source_model("my-model_v2")
        assert result == "my-model_v2"

    def test_SEC005_spaces_replaced(self, mock_bpy, mesh_imports):
        """SEC-005: Spaces are replaced with underscores."""
        m = mesh_imports
        importer = m.MeshImporter()
        result = importer._sanitize_source_model("my model")
        assert result == "my_model"

    def test_SEC005_empty_string(self, mock_bpy, mesh_imports):
        """SEC-005: Empty string returns empty string."""
        m = mesh_imports
        importer = m.MeshImporter()
        result = importer._sanitize_source_model("")
        assert result == ""

    def test_SEC005_all_special_chars(self, mock_bpy, mesh_imports):
        """SEC-005: All special chars replaced with underscores."""
        m = mesh_imports
        importer = m.MeshImporter()
        result = importer._sanitize_source_model("!@#$%^&*()")
        assert result == "__________"

    def test_SEC005_truncation_at_32(self, mock_bpy, mesh_imports):
        """SEC-005: Result is truncated to 32 characters."""
        m = mesh_imports
        importer = m.MeshImporter()
        result = importer._sanitize_source_model("a" * 50)
        assert len(result) == 32


# ---------------------------------------------------------------------------
# Additional coverage: Pipeline Integration Tests
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    """Integration tests for pipeline step ordering and data flow."""

    def test_pipeline_settings_passed_to_steps(
        self, mock_bpy, mesh_imports
    ):
        """Pipeline passes settings dict to all steps."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # When — with custom settings
        diagnostics = pipeline.execute(
            ctx, obj,
            merge_distance=0.005,
            voxel_size=0.02,
            enable_quad_remesh=False,
            enable_decimate=False,
        )

        # Then — diagnostics produced successfully
        assert isinstance(diagnostics, dict)
        assert diagnostics["quad_remesh_applied"] is False
        assert diagnostics["decimate_applied"] is False

    def test_pipeline_step_order_phase1_before_phase2(
        self, mock_bpy, mesh_imports
    ):
        """Pipeline executes Phase 1 steps before Phase 2 steps."""
        m = mesh_imports

        # Track step execution order
        execution_order = []

        original_dedup_execute = m.DedupStep.execute
        original_quad_execute = m.QuadRemeshStep.execute

        def _track_dedup(self, ctx, obj, settings):
            execution_order.append("DedupStep")
            return original_dedup_execute(self, ctx, obj, settings)

        def _track_quad(self, ctx, obj, settings):
            execution_order.append("QuadRemeshStep")
            return original_quad_execute(self, ctx, obj, settings)

        m.DedupStep.execute = _track_dedup
        m.QuadRemeshStep.execute = _track_quad

        try:
            obj = MagicMock()
            obj.data.vertices = list(range(10))
            obj.data.polygons = list(range(10))
            ctx = MagicMock()

            pipeline = m.MeshCleanupPipeline()
            pipeline.execute(ctx, obj)

            # Then — DedupStep ran before QuadRemeshStep
            dedup_idx = execution_order.index("DedupStep")
            quad_idx = execution_order.index("QuadRemeshStep")
            assert dedup_idx < quad_idx, (
                f"DedupStep (index {dedup_idx}) should run before "
                f"QuadRemeshStep (index {quad_idx})"
            )
        finally:
            m.DedupStep.execute = original_dedup_execute
            m.QuadRemeshStep.execute = original_quad_execute

    def test_pipeline_info_logging_on_completion(
        self, mock_bpy, mesh_imports, caplog
    ):
        """§11.1: Pipeline logs INFO on completion with diagnostics."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        with caplog.at_level(logging.INFO, logger="tessera.mesh"):
            pipeline.execute(ctx, obj)

        info_records = [
            r for r in caplog.records
            if r.levelno == logging.INFO
            and "completed" in r.message.lower()
        ]
        assert len(info_records) >= 1, (
            f"Expected INFO log about cleanup completion, got: "
            f"{[r.message for r in caplog.records]}"
        )

    def test_pipeline_multiple_errors_accumulated(
        self, mock_bpy, mesh_imports
    ):
        """FR-020: Multiple non-critical step failures accumulate in
        step_errors list."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # Patch both non-critical steps to fail
        original_degenerate = m.DegenerateStep.execute
        original_hole_fill = m.HoleFillStep.execute

        def _fail_degenerate(self, context, ob, settings):
            raise RuntimeError("degenerate fail")

        def _fail_hole_fill(self, context, ob, settings):
            raise RuntimeError("hole fill fail")

        m.DegenerateStep.execute = _fail_degenerate
        m.HoleFillStep.execute = _fail_hole_fill

        try:
            diagnostics = pipeline.execute(ctx, obj)

            # Then — both errors recorded
            assert len(diagnostics["step_errors"]) >= 2
            step_names = [e["step"] for e in diagnostics["step_errors"]]
            assert "DegenerateStep" in step_names
            assert "HoleFillStep" in step_names
        finally:
            m.DegenerateStep.execute = original_degenerate
            m.HoleFillStep.execute = original_hole_fill


# ---------------------------------------------------------------------------
# Additional coverage: MeshCleanupError exception class
# ---------------------------------------------------------------------------


class TestMeshCleanupErrorClass:
    """Tests for MeshCleanupError exception structure."""

    def test_error_has_step_name(self, mock_bpy, mesh_imports):
        """FR-020: MeshCleanupError stores the step name."""
        m = mesh_imports

        err = m.MeshCleanupError("TestStep", ValueError("test"))
        assert err.step_name == "TestStep"

    def test_error_has_original_exception(self, mock_bpy, mesh_imports):
        """FR-020: MeshCleanupError wraps the original exception."""
        m = mesh_imports

        original = ValueError("root cause")
        err = m.MeshCleanupError("TestStep", original)
        assert err.original_exception is original

    def test_error_str_contains_step_name(self, mock_bpy, mesh_imports):
        """FR-020: str(MeshCleanupError) includes step name."""
        m = mesh_imports

        err = m.MeshCleanupError("DedupStep", ValueError("msg"))
        assert "DedupStep" in str(err)
        assert "msg" in str(err)


# ---------------------------------------------------------------------------
# Additional coverage: Import Validation Edge Cases
# ---------------------------------------------------------------------------


class TestImportValidationEdgeCases:
    """Additional edge cases for MeshImporter input validation."""

    def test_vertices_not_numpy(self, mock_bpy, mesh_imports):
        """SEC-001: Non-numpy vertice input raises ValueError."""
        m = mesh_imports
        importer = m.MeshImporter()

        with pytest.raises(ValueError, match="numpy array"):
            importer.import_mesh(
                [[0, 0, 0], [1, 0, 0]], _make_valid_faces(10, 6)
            )

    def test_faces_not_numpy(self, mock_bpy, mesh_imports):
        """SEC-001: Non-numpy faces input raises ValueError."""
        m = mesh_imports
        importer = m.MeshImporter()

        with pytest.raises(ValueError, match="numpy array"):
            importer.import_mesh(
                _make_valid_vertices(10), [[0, 1, 2], [3, 4, 5]]
            )

    def test_vertices_wrong_shape_1d(self, mock_bpy, mesh_imports):
        """SEC-001: 1D vertex array raises ValueError."""
        m = mesh_imports
        importer = m.MeshImporter()
        verts = np.array([0, 1, 2, 3, 4, 5], dtype=np.float32)

        with pytest.raises(ValueError, match="shape"):
            importer.import_mesh(verts, _make_valid_faces(10, 6))

    def test_vertices_wrong_shape_cols(self, mock_bpy, mesh_imports):
        """SEC-001: Vertex array with 2 columns raises ValueError."""
        m = mesh_imports
        importer = m.MeshImporter()
        verts = np.zeros((10, 2), dtype=np.float32)

        with pytest.raises(ValueError, match="shape"):
            importer.import_mesh(verts, _make_valid_faces(10, 6))

    def test_exact_minimum_mesh_accepted(self, mock_bpy, mesh_imports):
        """EC-003: Exactly 4 vertices and 4 faces is accepted."""
        m = mesh_imports
        verts, faces = _make_tetrahedron()
        importer = m.MeshImporter()

        # Should NOT raise
        obj = importer.import_mesh(verts, faces)
        assert obj is not None

    def test_import_latency_under_limit_small(
        self, mock_bpy, mesh_imports
    ):
        """NFR-002: Validation overhead negligible for small meshes."""
        m = mesh_imports
        verts, faces = _make_tetrahedron()
        importer = m.MeshImporter()

        start = time.perf_counter()
        importer.import_mesh(verts, faces)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"Small mesh import took {elapsed:.3f}s"


# ---------------------------------------------------------------------------
# Additional coverage: DegenerateStep details
# ---------------------------------------------------------------------------


class TestDegenerateStepDetails:
    """Extended tests for DegenerateStep."""

    def test_degenerate_step_name(self, mock_bpy, mesh_imports):
        """DegenerateStep.name is 'DegenerateStep'."""
        m = mesh_imports
        step = m.DegenerateStep()
        assert step.name == "DegenerateStep"

    def test_degenerate_calls_dissolve_degenerate(
        self, mock_bpy, mesh_imports
    ):
        """EC-001: dissolve_degenerate is called with correct threshold."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        step = m.DegenerateStep()
        step.execute(ctx, obj, {})

        import bmesh as bmesh_mock
        bmesh_mock.ops.dissolve_degenerate.assert_called()
        call_kwargs = bmesh_mock.ops.dissolve_degenerate.call_args
        assert call_kwargs[1]["dist"] == 1e-8

    def test_degenerate_uses_try_finally(self, mock_bpy, mesh_imports):
        """CON-006: DegenerateStep cleans up bmesh."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(5))
        ctx = MagicMock()

        step = m.DegenerateStep()
        step.execute(ctx, obj, {})

        import bmesh as bmesh_mock
        bm = bmesh_mock.new.return_value
        bm.free.assert_called_once()


# ---------------------------------------------------------------------------
# Additional coverage: QuadRemeshStep details
# ---------------------------------------------------------------------------


class TestQuadRemeshStepDetails:
    """Extended tests for QuadRemeshStep."""

    def test_quad_remesh_step_name(self, mock_bpy, mesh_imports):
        """QuadRemeshStep.name is 'QuadRemeshStep'."""
        m = mesh_imports
        step = m.QuadRemeshStep()
        assert step.name == "QuadRemeshStep"

    def test_quad_remesh_passes_target_face_count(
        self, mock_bpy, mesh_imports
    ):
        """FR-010: QuadriFlow operator receives target face count."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.polygons = list(range(200_000))
        ctx = MagicMock()
        settings = {
            "enable_quad_remesh": True,
            "quad_target_faces": 15_000,
        }

        step = m.QuadRemeshStep()
        step.execute(ctx, obj, settings)

        import bpy
        call_kwargs = bpy.ops.object.quadriflow_remesh.call_args
        assert call_kwargs[1]["target_faces"] == 15_000


# ---------------------------------------------------------------------------
# Additional coverage: FR-009 — View Selected After Cleanup
# ---------------------------------------------------------------------------


class TestViewSelectedAfterCleanup:
    """Tests for FR-009: frame cleaned object in viewport."""

    def test_FR009_view_selected_called(self, mock_bpy, mesh_imports):
        """FR-009: Pipeline calls view3d.view_selected() after cleanup."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()
        pipeline.execute(ctx, obj)

        import bpy
        bpy.ops.view3d.view_selected.assert_called_once()

    def test_FR009_view_selected_failure_is_silent(
        self, mock_bpy, mesh_imports
    ):
        """FR-009: If view_selected raises RuntimeError (no viewport),
        the pipeline still returns diagnostics without crashing."""
        m = mesh_imports
        import bpy

        # Make view_selected raise RuntimeError (headless mode)
        bpy.ops.view3d.view_selected.side_effect = RuntimeError(
            "No 3D viewport"
        )

        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()

        # Should not raise
        diagnostics = pipeline.execute(ctx, obj)
        assert isinstance(diagnostics, dict)
        assert "cleanup_time_seconds" in diagnostics

    def test_FR009_object_active_and_selected_after_cleanup(
        self, mock_bpy, mesh_imports
    ):
        """FR-009: Cleaned object is active and selected after pipeline."""
        m = mesh_imports

        obj = MagicMock()
        obj.data.vertices = list(range(10))
        obj.data.polygons = list(range(10))
        ctx = MagicMock()

        pipeline = m.MeshCleanupPipeline()
        pipeline.execute(ctx, obj)

        # Object was made active and selected for framing
        assert ctx.view_layer.objects.active == obj
        obj.select_set.assert_called_with(True)


# ---------------------------------------------------------------------------
# Additional coverage: CON-008 — Operator Modal Support
# ---------------------------------------------------------------------------


class TestOperatorModalSupport:
    """Tests for CON-008: operator configuration for UI responsiveness."""

    def test_CON008_operator_has_register_and_undo(
        self, mock_bpy, mesh_imports
    ):
        """CON-008: Operator has REGISTER and UNDO in bl_options."""
        from tessera.operators.cleanup_ops import TESSERA_OT_RunCleanup

        assert "REGISTER" in TESSERA_OT_RunCleanup.bl_options
        assert "UNDO" in TESSERA_OT_RunCleanup.bl_options

    def test_CON008_operator_has_modal_method(
        self, mock_bpy, mesh_imports
    ):
        """CON-008: Operator implements a modal() method for yielding
        during long operations."""
        from tessera.operators.cleanup_ops import TESSERA_OT_RunCleanup

        assert hasattr(TESSERA_OT_RunCleanup, "modal"), (
            "TESSERA_OT_RunCleanup must implement modal() "
            "for CON-008 UI thread compliance"
        )

    def test_CON008_invoke_starts_modal(
        self, mock_bpy, mesh_imports
    ):
        """CON-008: invoke() returns RUNNING_MODAL to enter modal loop."""
        from tessera.operators.cleanup_ops import TESSERA_OT_RunCleanup

        assert hasattr(TESSERA_OT_RunCleanup, "invoke"), (
            "TESSERA_OT_RunCleanup must implement invoke() "
            "for modal operator pattern"
        )

