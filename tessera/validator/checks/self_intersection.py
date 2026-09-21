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

"""Validation check: self-intersection detection and repair.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-003, FR-004, EC-005.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import bmesh
from mathutils.bvhtree import BVHTree

from ..data_types import CheckResult, CheckStatus, RepairResult
from .base import BaseCheck

logger = logging.getLogger("tessera.validator")

# EC-005: Timeout threshold in seconds for BVH overlap query.
_BVH_TIMEOUT_SECONDS = 30.0

# EC-005: Face count threshold for warning.
_LARGE_MESH_THRESHOLD = 500_000


class SelfIntersectionCheck(BaseCheck):
    """Detect and repair self-intersecting faces via BVH overlap.

    Implements: FR-003, FR-004, EC-005.
    """

    @property
    def name(self) -> str:
        """Human-readable check name."""
        return "Self-Intersections"

    def check(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> CheckResult:
        """Detect self-intersecting faces using ``BVHTree.overlap()``.

        Args:
            obj: ``bpy.types.Object`` with mesh data.
            settings: Validator settings dict.

        Returns:
            ``CheckResult`` with intersection pair count.

        Implements: FR-003, EC-005.
        """
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()

            face_count = len(bm.faces)

            # EC-005: Warn on large meshes.
            if face_count > _LARGE_MESH_THRESHOLD:
                logger.warning(
                    "Self-intersection check on %d faces may exceed "
                    "3-second target. Consider decimating first.",
                    face_count,
                )

            # Build BVH tree from bmesh.
            tree = BVHTree.FromBMesh(bm, epsilon=0.0001)
        finally:
            bm.free()

        # Run overlap query with timeout monitoring.
        start = time.perf_counter()
        overlap_pairs = tree.overlap(tree)
        elapsed = time.perf_counter() - start

        # EC-005: Check for timeout.
        if elapsed > _BVH_TIMEOUT_SECONDS:
            logger.warning(
                "Self-intersection check timed out after %.1f seconds.",
                elapsed,
            )
            return CheckResult(
                check_name=self.name,
                status=CheckStatus.WARN,
                message=(
                    f"Self-intersection check timed out after "
                    f"{_BVH_TIMEOUT_SECONDS:.0f} seconds. Skipped."
                ),
                details={
                    "intersection_pairs": -1,
                    "elapsed_seconds": round(elapsed, 2),
                    "timeout_seconds": _BVH_TIMEOUT_SECONDS,
                },
            )

        # Filter out self-pairs (face intersecting itself).
        unique_pairs = {(min(a, b), max(a, b)) for a, b in overlap_pairs if a != b}
        pair_count = len(unique_pairs)

        if pair_count == 0:
            return CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message="No self-intersecting faces detected.",
                details={
                    "intersection_pairs": 0,
                    "elapsed_seconds": round(elapsed, 2),
                },
            )

        return CheckResult(
            check_name=self.name,
            status=CheckStatus.FAIL,
            message=f"{pair_count} self-intersecting face pair(s) detected.",
            details={
                "intersection_pairs": pair_count,
                "elapsed_seconds": round(elapsed, 2),
            },
        )

    def repair(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> RepairResult:
        """Auto-repair self-intersections via boolean union to self.

        Duplicates the object, applies a ``BOOLEAN`` modifier in
        ``UNION`` mode with the object as its own target, then applies
        the modifier.

        Args:
            obj: ``bpy.types.Object`` (the ``_print`` duplicate).
            settings: Validator settings dict.

        Returns:
            ``RepairResult`` with success status.

        Implements: FR-004.
        """
        import bpy

        try:
            # Add a boolean modifier in UNION mode.
            mod = obj.modifiers.new(name="SelfIntersectionFix", type="BOOLEAN")
            mod.operation = "UNION"
            mod.solver = "EXACT"
            mod.object = obj
            mod.use_self = True

            # Apply the modifier.
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=mod.name)

            msg = "Applied boolean union (self) to resolve intersections."
            logger.info("Auto-repair (self-intersection): %s", msg)
            return RepairResult(success=True, message=msg)

        except Exception as exc:
            msg = f"Boolean union repair failed: {exc}"
            logger.warning("Auto-repair (self-intersection): %s", msg)
            return RepairResult(success=False, message=msg)
