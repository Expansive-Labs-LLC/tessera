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

"""Validation check: mesh volume (closed surface) verification.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-013, FR-014, EC-001.
"""

from __future__ import annotations

import logging
from typing import Any

import bmesh

from ..data_types import CheckResult, CheckStatus, RepairResult
from .base import BaseCheck

logger = logging.getLogger("tessera.validator")


class VolumeCheck(BaseCheck):
    """Verify mesh volume is positive (closed surface).

    Computes signed volume using the tetrahedron method:
    ``V = Σ (v1 · (v2 × v3)) / 6``.

    Implements: FR-013, FR-014, EC-001.
    """

    @property
    def name(self) -> str:
        """Human-readable check name."""
        return "Mesh Volume"

    def check(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> CheckResult:
        """Compute mesh volume using signed tetrahedron method.

        Args:
            obj: ``bpy.types.Object`` with mesh data.
            settings: Validator settings dict.

        Returns:
            ``CheckResult`` with volume in mm³.

        Implements: FR-013.
        """
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()

            volume = self._compute_volume(bm)
        finally:
            bm.free()

        # Convert from m³ to mm³.
        volume_mm3 = round(volume * 1e9, 1)

        if volume > 0:
            return CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=(
                    f"Mesh volume is {volume_mm3} mm³ " f"(closed surface confirmed)."
                ),
                details={"volume_mm3": volume_mm3},
            )

        return CheckResult(
            check_name=self.name,
            status=CheckStatus.FAIL,
            message=(
                f"Mesh volume is {volume_mm3} mm³. "
                f"Surface is not closed or normals are inverted."
            ),
            details={"volume_mm3": volume_mm3},
        )

    def repair(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> RepairResult:
        """Auto-repair negative/zero volume.

        Strategy:
        1. Recalculate normals outward.
        2. If volume is still ≤ 0, apply voxel remesh fallback.

        Args:
            obj: ``bpy.types.Object`` (the ``_print`` duplicate).
            settings: Validator settings dict. Uses key:
                - ``voxel_size_mm`` (float, default ``0.5``)

        Returns:
            ``RepairResult`` with repair outcome.

        Implements: FR-014, EC-001.
        """
        import bpy

        # Step (a): Recalculate normals outward.
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(obj.data)

            volume = self._compute_volume(bm)
        finally:
            bm.free()

        obj.data.update()

        if volume > 0:
            msg = (
                "Recalculated face normals outward. "
                f"Volume is now {round(volume * 1e9, 1)} mm³."
            )
            logger.info("Auto-repair (volume): %s", msg)
            return RepairResult(success=True, message=msg)

        # Step (b): Voxel remesh fallback.
        voxel_size_mm = settings.get("voxel_size_mm", 0.5)
        voxel_size_m = voxel_size_mm / 1000.0

        try:
            mod = obj.modifiers.new(name="VolumeRemesh", type="REMESH")
            mod.mode = "VOXEL"
            mod.voxel_size = voxel_size_m

            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)

            # Re-check volume after remesh.
            bm2 = bmesh.new()
            try:
                bm2.from_mesh(obj.data)
                new_volume = self._compute_volume(bm2)
            finally:
                bm2.free()

            volume_mm3 = round(new_volume * 1e9, 1)
            msg = (
                f"Volume was 0 mm³ (open surface). "
                f"Applied voxel remesh to close. "
                f"Volume is now {volume_mm3} mm³."
            )
            logger.info("Auto-repair (volume): %s", msg)
            return RepairResult(success=new_volume > 0, message=msg)

        except Exception as exc:
            msg = f"Voxel remesh fallback failed: {exc}"
            logger.warning("Auto-repair (volume): %s", msg)
            return RepairResult(success=False, message=msg)

    @staticmethod
    def _compute_volume(bm: bmesh.types.BMesh) -> float:
        """Compute signed volume via the tetrahedron method.

        ``V = Σ (v1 · (v2 × v3)) / 6`` for each triangulated face.

        Args:
            bm: ``BMesh`` instance.

        Returns:
            Signed volume in cubic meters.

        Implements: FR-013.
        """
        volume = 0.0

        for face in bm.faces:
            verts = face.verts
            if len(verts) < 3:
                continue

            # Triangulate the face if it has more than 3 verts.
            v0 = verts[0].co
            for i in range(1, len(verts) - 1):
                v1 = verts[i].co
                v2 = verts[i + 1].co
                volume += v0.dot(v1.cross(v2)) / 6.0

        return volume
