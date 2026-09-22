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

"""Validation check: zero-area / degenerate face detection and repair.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-005, FR-006.
"""

from __future__ import annotations

import logging
from typing import Any

import bmesh

from ..data_types import CheckResult, CheckStatus, RepairResult
from .base import BaseCheck

logger = logging.getLogger("tessera.validator")

# FR-005: Area threshold for degenerate face detection.
_DEGENERATE_AREA_THRESHOLD = 1e-8


class DegenerateFacesCheck(BaseCheck):
    """Detect and repair zero-area (degenerate) faces.

    Implements: FR-005, FR-006.
    """

    @property
    def name(self) -> str:
        """Human-readable check name."""
        return "Zero-Area Faces"

    def check(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> CheckResult:
        """Detect faces with area < 1e-8 square meters.

        Args:
            obj: ``bpy.types.Object`` with mesh data.
            settings: Validator settings dict.

        Returns:
            ``CheckResult`` with degenerate face count.

        Implements: FR-005.
        """
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()

            degenerate = [
                f for f in bm.faces if f.calc_area() < _DEGENERATE_AREA_THRESHOLD
            ]
            count = len(degenerate)
        finally:
            bm.free()

        if count == 0:
            return CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message="No zero-area faces detected.",
                details={"degenerate_face_count": 0},
            )

        return CheckResult(
            check_name=self.name,
            status=CheckStatus.FAIL,
            message=f"{count} zero-area face(s) detected.",
            details={"degenerate_face_count": count},
        )

    def repair(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> RepairResult:
        """Auto-repair degenerate faces via dissolve.

        Uses ``bmesh.ops.dissolve_degenerate()`` with the
        degenerate area threshold.

        Args:
            obj: ``bpy.types.Object`` (the ``_print`` duplicate).
            settings: Validator settings dict.

        Returns:
            ``RepairResult`` with repair description.

        Implements: FR-006.
        """
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)

            faces_before = len(bm.faces)
            bmesh.ops.dissolve_degenerate(
                bm,
                dist=_DEGENERATE_AREA_THRESHOLD,
                edges=bm.edges,
            )
            faces_after = len(bm.faces)
            dissolved = faces_before - faces_after

            bm.to_mesh(obj.data)
        finally:
            bm.free()

        obj.data.update()

        msg = f"Dissolved {dissolved} degenerate face(s)."
        logger.info("Auto-repair (degenerate faces): %s", msg)
        return RepairResult(success=True, message=msg)
