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

"""Validation check: overhang angle detection.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-010, FR-011, FR-012.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import bmesh
from mathutils import Vector

from ..data_types import CheckResult, CheckStatus, RepairResult
from .base import BaseCheck

logger = logging.getLogger("tessera.validator")

# Build plate normal (upward direction).
_UP_VECTOR = Vector((0.0, 0.0, 1.0))

# FR-012: Percentage threshold for escalation from WARN to FAIL.
_OVERHANG_FAIL_PERCENT = 50.0


class OverhangCheck(BaseCheck):
    """Detect faces with overhang angles exceeding the threshold.

    Overhangs are faces whose normal deviates significantly from
    the upward direction, indicating the surface faces downward
    beyond the configured angle.

    Implements: FR-010, FR-011, FR-012.
    """

    @property
    def name(self) -> str:
        """Human-readable check name."""
        return "Overhang Angle"

    def check(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> CheckResult:
        """Detect overhang faces exceeding the angle threshold.

        Args:
            obj: ``bpy.types.Object`` with mesh data.
            settings: Validator settings dict. Uses key:
                - ``overhang_angle_deg`` (float, default ``45.0``)

        Returns:
            ``CheckResult`` with overhang face count and percentage.

        Implements: FR-010, FR-011, FR-012.
        """
        threshold_deg = settings.get("overhang_angle_deg", 45.0)
        threshold_rad = math.radians(threshold_deg)

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()

            face_count = len(bm.faces)
            overhang_count = 0
            max_overhang_deg = 0.0

            for face in bm.faces:
                normal = face.normal

                # Compute angle from up vector.
                angle_from_up = normal.angle(_UP_VECTOR)

                # A face is overhanging if its normal points downward
                # beyond the threshold. The angle from up > (180° - threshold)
                # means the face is more than threshold degrees past horizontal.
                # Equivalently: angle from down < (90° - threshold).
                # We detect when the face normal makes an angle > threshold
                # from up when the face points downward.
                if angle_from_up > (math.pi - threshold_rad):
                    overhang_count += 1
                    overhang_deg = math.degrees(angle_from_up - (math.pi / 2))
                    if overhang_deg > max_overhang_deg:
                        max_overhang_deg = overhang_deg

        finally:
            bm.free()

        if overhang_count == 0:
            return CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=(f"No faces exceed {threshold_deg}° overhang threshold."),
                details={
                    "overhang_face_count": 0,
                    "overhang_face_percentage": 0.0,
                    "max_overhang_deg": 0.0,
                    "threshold_deg": threshold_deg,
                },
            )

        overhang_pct = round((overhang_count / face_count) * 100.0, 1)
        max_overhang_deg = round(max_overhang_deg, 1)

        # FR-012: Severity escalation.
        if overhang_pct > _OVERHANG_FAIL_PERCENT:
            return CheckResult(
                check_name=self.name,
                status=CheckStatus.FAIL,
                message=(
                    f"{overhang_count} faces ({overhang_pct}%) exceed "
                    f"{threshold_deg}° overhang threshold. Object may be "
                    f"misoriented. Consider using auto-orient."
                ),
                details={
                    "overhang_face_count": overhang_count,
                    "overhang_face_percentage": overhang_pct,
                    "max_overhang_deg": max_overhang_deg,
                    "threshold_deg": threshold_deg,
                },
            )

        return CheckResult(
            check_name=self.name,
            status=CheckStatus.WARN,
            message=(
                f"{overhang_count} faces ({overhang_pct}%) exceed "
                f"{threshold_deg}° overhang threshold."
            ),
            details={
                "overhang_face_count": overhang_count,
                "overhang_face_percentage": overhang_pct,
                "max_overhang_deg": max_overhang_deg,
                "threshold_deg": threshold_deg,
            },
        )

    def repair(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> RepairResult:
        """Overhang check does NOT auto-repair.

        Per FR-012, overhang detection produces WARN/FAIL only.
        Auto-orient is offered as a separate optional step (FR-025).

        Args:
            obj: ``bpy.types.Object``.
            settings: Validator settings dict.

        Returns:
            ``RepairResult`` indicating no repair was applied.

        Implements: FR-012 (no auto-repair).
        """
        return RepairResult(
            success=False,
            message="Overhang auto-repair is not supported. "
            "Consider using auto-orient (FR-025).",
        )
