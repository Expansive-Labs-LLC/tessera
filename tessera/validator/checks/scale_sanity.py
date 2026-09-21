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

"""Validation check: scale sanity (bounding box vs build volume).

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-015, FR-016.
"""

from __future__ import annotations

import logging
from typing import Any

from ..data_types import CheckResult, CheckStatus, RepairResult
from .base import BaseCheck

logger = logging.getLogger("tessera.validator")


class ScaleSanityCheck(BaseCheck):
    """Verify object fits within the printer's build volume.

    Implements: FR-015, FR-016.
    """

    @property
    def name(self) -> str:
        """Human-readable check name."""
        return "Scale Sanity"

    def check(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> CheckResult:
        """Check bounding box against configured build volume.

        Args:
            obj: ``bpy.types.Object`` with mesh data.
            settings: Validator settings dict. Uses keys:
                - ``build_x_mm`` (float, default ``220.0``)
                - ``build_y_mm`` (float, default ``220.0``)
                - ``build_z_mm`` (float, default ``250.0``)

        Returns:
            ``CheckResult`` with bounding box dimensions and
            scale factor if oversized.

        Implements: FR-015, FR-016.
        """
        build_x = settings.get("build_x_mm", 220.0)
        build_y = settings.get("build_y_mm", 220.0)
        build_z = settings.get("build_z_mm", 250.0)

        # Get world-space bounding box.
        bbox = [obj.matrix_world @ v for v in _get_bbox_corners(obj)]

        xs = [v.x for v in bbox]
        ys = [v.y for v in bbox]
        zs = [v.z for v in bbox]

        # Dimensions in meters → convert to mm.
        dim_x_mm = round((max(xs) - min(xs)) * 1000.0, 1)
        dim_y_mm = round((max(ys) - min(ys)) * 1000.0, 1)
        dim_z_mm = round((max(zs) - min(zs)) * 1000.0, 1)

        details = {
            "bbox_x_mm": dim_x_mm,
            "bbox_y_mm": dim_y_mm,
            "bbox_z_mm": dim_z_mm,
            "build_x_mm": build_x,
            "build_y_mm": build_y,
            "build_z_mm": build_z,
        }

        # Check if object fits.
        fits = (
            dim_x_mm <= build_x
            and dim_y_mm <= build_y
            and dim_z_mm <= build_z
        )

        if fits:
            return CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message=(
                    f"Bounding box {dim_x_mm}×{dim_y_mm}×{dim_z_mm} mm "
                    f"fits within {build_x}×{build_y}×{build_z} mm "
                    f"build volume."
                ),
                details=details,
            )

        # FR-016: Compute uniform scale factor.
        factor = min(
            build_x / dim_x_mm if dim_x_mm > 0 else 1.0,
            build_y / dim_y_mm if dim_y_mm > 0 else 1.0,
            build_z / dim_z_mm if dim_z_mm > 0 else 1.0,
        )
        factor = round(factor, 2)
        details["scale_factor"] = factor

        return CheckResult(
            check_name=self.name,
            status=CheckStatus.WARN,
            message=(
                f"Object bounding box ({dim_x_mm}×{dim_y_mm}×{dim_z_mm} mm) "
                f"exceeds build volume "
                f"({build_x}×{build_y}×{build_z} mm). "
                f"Scale factor {factor}× required to fit."
            ),
            details=details,
        )

    def repair(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> RepairResult:
        """Auto-scale object to fit build volume (if enabled).

        Only applies when ``auto_scale`` is ``True`` in settings.

        Args:
            obj: ``bpy.types.Object`` (the ``_print`` duplicate).
            settings: Validator settings dict. Uses key:
                - ``auto_scale`` (bool, default ``False``)

        Returns:
            ``RepairResult`` with scaling outcome.

        Implements: FR-016.
        """
        import bpy

        auto_scale = settings.get("auto_scale", False)
        if not auto_scale:
            return RepairResult(
                success=False,
                message="Auto-scale is disabled. Enable auto_scale to fit "
                "object within build volume.",
            )

        # Re-run check to get current factor.
        result = self.check(obj, settings)
        factor = result.details.get("scale_factor", 1.0)

        if factor >= 1.0:
            return RepairResult(
                success=True,
                message="Object already fits within build volume.",
            )

        try:
            obj.scale *= factor
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(scale=True)

            msg = f"Scaled object by {factor}× to fit build volume."
            logger.info("Auto-repair (scale sanity): %s", msg)
            return RepairResult(success=True, message=msg)

        except Exception as exc:
            msg = f"Auto-scale failed: {exc}"
            logger.warning("Auto-repair (scale sanity): %s", msg)
            return RepairResult(success=False, message=msg)


def _get_bbox_corners(obj: Any) -> list:
    """Get the 8 bounding box corners as ``Vector`` instances.

    Args:
        obj: ``bpy.types.Object``.

    Returns:
        List of 8 ``mathutils.Vector`` corners.
    """
    from mathutils import Vector

    return [Vector(corner) for corner in obj.bound_box]
