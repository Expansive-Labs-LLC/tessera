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

"""Validation check: minimum wall thickness via ray-casting.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-007, FR-008, FR-009, CON-008, EC-002.
"""

from __future__ import annotations

import logging
import random
from typing import Any

import bmesh
from mathutils.bvhtree import BVHTree

from ..data_types import CheckResult, CheckStatus, RepairResult
from .base import BaseCheck

logger = logging.getLogger("tessera.validator")

# CON-008: Maximum sample count for stratified sampling.
_MAX_SAMPLE_COUNT = 10_000

# CON-008: Face count threshold for sampling mode.
_SAMPLING_THRESHOLD = 100_000

# EC-002: Percentage threshold for uniformly thin detection.
_UNIFORMLY_THIN_PERCENT = 80.0


class WallThicknessCheck(BaseCheck):
    """Detect and repair insufficient wall thickness.

    Casts rays inward from face sample points to measure the
    distance to the nearest opposing surface.

    Implements: FR-007, FR-008, FR-009, CON-008, EC-002.
    """

    @property
    def name(self) -> str:
        """Human-readable check name."""
        return "Wall Thickness"

    def check(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> CheckResult:
        """Detect faces with wall thickness below threshold.

        Args:
            obj: ``bpy.types.Object`` with mesh data.
            settings: Validator settings dict. Uses keys:
                - ``wall_thickness_mm`` (float, default ``1.2``)
                - ``printer_type`` (str, default ``"FDM"``)

        Returns:
            ``CheckResult`` with thin face count and minimum thickness.

        Implements: FR-007, FR-008, CON-008.
        """
        threshold_mm = settings.get("wall_thickness_mm", 1.2)
        # Convert mm threshold to meters for Blender internal units.
        threshold_m = threshold_mm / 1000.0

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()

            face_count = len(bm.faces)

            # CON-008: Stratified sampling for large meshes.
            if face_count > _SAMPLING_THRESHOLD:
                sample_count = min(face_count, _MAX_SAMPLE_COUNT)
                sample_indices = set(random.sample(range(face_count), sample_count))
                logger.debug(
                    "Wall thickness sampling enabled: "
                    "total_faces=%d, sample_count=%d",
                    face_count,
                    sample_count,
                )
            else:
                sample_indices = None  # Check all faces.
                sample_count = face_count

            # Build BVH tree for ray-casting.
            tree = BVHTree.FromBMesh(bm, epsilon=0.0001)

            thin_faces = 0
            min_thickness = float("inf")

            for i, face in enumerate(bm.faces):
                if sample_indices is not None and i not in sample_indices:
                    continue

                # Cast ray inward (opposite to face normal).
                origin = face.calc_center_median()
                direction = -face.normal

                # Small offset to avoid self-hit.
                origin = origin + direction * 0.0001

                hit_location, hit_normal, hit_index, hit_dist = tree.ray_cast(
                    origin, direction
                )

                if hit_location is not None and hit_dist < threshold_m:
                    thin_faces += 1
                    if hit_dist < min_thickness:
                        min_thickness = hit_dist

        finally:
            bm.free()

        if thin_faces == 0:
            return CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=(
                    f"All sampled faces meet {threshold_mm} mm "
                    f"wall thickness threshold."
                ),
                details={
                    "thin_face_count": 0,
                    "thin_face_percentage": 0.0,
                    "min_thickness_mm": threshold_mm,
                    "threshold_mm": threshold_mm,
                },
            )

        # Convert measurements back to mm for reporting.
        min_thickness_mm = round(min_thickness * 1000.0, 2)
        thin_pct = round((thin_faces / sample_count) * 100.0, 1)

        return CheckResult(
            check_name=self.name,
            status=CheckStatus.FAIL,
            message=(
                f"{thin_faces} faces ({thin_pct}%) below "
                f"{threshold_mm} mm threshold. "
                f"Minimum: {min_thickness_mm} mm."
            ),
            details={
                "thin_face_count": thin_faces,
                "thin_face_percentage": thin_pct,
                "min_thickness_mm": min_thickness_mm,
                "threshold_mm": threshold_mm,
            },
        )

    def repair(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> RepairResult:
        """Auto-repair thin walls via Solidify modifier.

        Applies a ``SOLIDIFY`` modifier with thickness equal to
        ``(threshold - measured_minimum) + 0.1 mm`` margin.

        Skips repair when >80% of faces fail (uniformly thin model).

        Args:
            obj: ``bpy.types.Object`` (the ``_print`` duplicate).
            settings: Validator settings dict.

        Returns:
            ``RepairResult`` with repair outcome.

        Implements: FR-009, EC-002.
        """
        import bpy

        threshold_mm = settings.get("wall_thickness_mm", 1.2)

        # Re-check to get current stats on the duplicate.
        result = self.check(obj, settings)
        thin_pct = result.details.get("thin_face_percentage", 0.0)
        min_thickness_mm = result.details.get("min_thickness_mm", threshold_mm)

        # EC-002: Skip solidify if model is uniformly thin.
        if thin_pct > _UNIFORMLY_THIN_PERCENT:
            msg = (
                f"Model is uniformly thin ({min_thickness_mm} mm). "
                f"Auto-repair (Solidify) would significantly alter "
                f"geometry. Manual adjustment recommended."
            )
            logger.warning("Auto-repair (wall thickness): %s", msg)
            return RepairResult(success=False, message=msg)

        # FR-009: Compute solidify thickness.
        solidify_mm = (threshold_mm - min_thickness_mm) + 0.1
        solidify_m = solidify_mm / 1000.0

        try:
            mod = obj.modifiers.new(name="WallThicknessFix", type="SOLIDIFY")
            mod.thickness = solidify_m
            mod.offset = -1  # Solidify inward.
            mod.use_complex_solver = True

            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)

            msg = f"Applied Solidify modifier with " f"{solidify_mm:.1f} mm offset."
            logger.info("Auto-repair (wall thickness): %s", msg)
            return RepairResult(success=True, message=msg)

        except Exception as exc:
            msg = f"Solidify modifier repair failed: {exc}"
            logger.warning("Auto-repair (wall thickness): %s", msg)
            return RepairResult(success=False, message=msg)
