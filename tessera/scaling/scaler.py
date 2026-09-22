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

"""Mesh scaler — transforms bounding box to target mm dimensions.

Applies uniform or per-axis scaling to match user-specified real-world
dimensions, then applies the Blender transform so vertex data contains
final mm coordinates.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-002–FR-006, EC-003, EC-004, EC-005, SEC-001.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Tuple

import bpy

from .dimension_input import DimensionSpec
from .exceptions import ScalingError

logger = logging.getLogger("tessera.scaling")

# EC-004: Extreme aspect ratio threshold.
_EXTREME_RATIO_THRESHOLD = 5.0

# FR-020: Small object warning threshold in mm.
_SMALL_OBJECT_THRESHOLD_MM = 5.0

# FR-006: Post-scaling accuracy tolerance in mm.
_ACCURACY_TOLERANCE_MM = 0.01


class MeshScaler:
    """Transforms a mesh's bounding box to target mm dimensions.

    Implements scaling via ``bpy.ops.transform.resize()`` followed by
    ``bpy.ops.object.transform_apply(scale=True)`` so that the mesh
    vertices contain final mm coordinates.

    Implements: FR-002–FR-006, EC-003, EC-004, EC-005.
    """

    def apply(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        dimension_spec: DimensionSpec,
        printer_technology: str = "FDM",
    ) -> Dict[str, Any]:
        """Apply scaling transform to match target dimensions.

        Args:
            context: Blender context.
            obj: Target mesh object.
            dimension_spec: Resolved target dimensions.
            printer_technology: ``"FDM"`` or ``"SLA"`` for warnings.

        Returns:
            Dict with scaling diagnostics keys.

        Raises:
            ScalingError: If a zero-extent axis is detected (EC-003)
                or post-scaling accuracy check fails (FR-006).

        Implements: FR-002–FR-006, EC-003, EC-004, EC-005.
        """
        start_time = time.perf_counter()

        # FR-005: Set scene units to metric/mm.
        self._configure_scene_units(context)

        # Get current bounding-box dimensions.
        original_dims = self._get_dimensions(obj)
        logger.debug(
            "Original bounding-box dimensions: (%.4f, %.4f, %.4f)",
            *original_dims,
        )

        # EC-003: Check for zero-extent axes.
        axis_names = ("X", "Y", "Z")
        for i, dim in enumerate(original_dims):
            if dim == 0.0:
                raise ScalingError(
                    f"Mesh has zero extent along the {axis_names[i]} axis. "
                    f"Cannot compute scale factor for a zero-dimension axis. "
                    f"The mesh may be a flat plane, which is not printable."
                )

        # Resolve target dimensions (fills unset axes proportionally).
        target_dims = dimension_spec.resolve(original_dims)
        logger.debug("Target dimensions: (%.4f, %.4f, %.4f) mm", *target_dims)

        # Compute per-axis scale factors.
        scale_factors = tuple(target_dims[i] / original_dims[i] for i in range(3))
        logger.debug("Scale factors: (%.6f, %.6f, %.6f)", *scale_factors)

        # EC-004: Extreme aspect ratio warning.
        warnings: List[str] = []
        if dimension_spec.specified_count() >= 2:
            max_sf = max(scale_factors)
            min_sf = min(scale_factors)
            if min_sf > 0.0:
                ratio = max_sf / min_sf
                if ratio > _EXTREME_RATIO_THRESHOLD:
                    msg = (
                        f"Non-uniform scaling is extreme "
                        f"(max/min scale ratio = {ratio:.1f}). "
                        f"The object will be significantly distorted "
                        f"from its original proportions."
                    )
                    warnings.append(msg)
                    logger.warning(msg)

        # Ensure the object is selected and active.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        # FR-002/FR-003: Apply scaling.
        specified = dimension_spec.specified_count()
        if specified <= 1:
            # FR-002: Uniform scaling — all axes get the same factor.
            uniform_factor = scale_factors[0]
            if dimension_spec.height_mm > 0.0:
                uniform_factor = scale_factors[1]
            elif dimension_spec.depth_mm > 0.0:
                uniform_factor = scale_factors[2]

            bpy.ops.transform.resize(
                value=(uniform_factor, uniform_factor, uniform_factor)
            )
        else:
            # FR-003: Per-axis scaling.
            bpy.ops.transform.resize(value=scale_factors)

        # FR-004: Apply the scale transform to mesh data.
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        # Get actual post-scaling dimensions.
        actual_dims = self._get_dimensions(obj)

        # FR-006: Verify post-scaling accuracy.
        dimension_axes = [
            ("X", dimension_spec.width_mm, actual_dims[0]),
            ("Y", dimension_spec.height_mm, actual_dims[1]),
            ("Z", dimension_spec.depth_mm, actual_dims[2]),
        ]
        for axis, expected, actual in dimension_axes:
            if expected > 0.0:
                deviation = abs(actual - expected)
                logger.debug(
                    "Dimension accuracy: %s expected=%.4f mm, "
                    "actual=%.4f mm, deviation=%.4f mm",
                    axis,
                    expected,
                    actual,
                    deviation,
                )
                if deviation > _ACCURACY_TOLERANCE_MM:
                    raise ScalingError(
                        f"Post-scaling dimension mismatch: axis={axis}, "
                        f"expected={expected}mm, actual={actual}mm"
                    )

        # EC-005/FR-020: Small object warning.
        smallest_dim = min(actual_dims)
        if smallest_dim < _SMALL_OBJECT_THRESHOLD_MM:
            if printer_technology == "FDM":
                msg = (
                    f"Smallest dimension is {smallest_dim:.1f}mm — "
                    f"object may be too small to print reliably on "
                    f"FDM printers."
                )
            else:
                msg = (
                    f"Smallest dimension is {smallest_dim:.1f}mm — "
                    f"object may be too small to print reliably on "
                    f"{printer_technology} printers."
                )
            warnings.append(msg)
            logger.warning(msg)

        # EC-005: Very small height warning for FDM.
        if (
            printer_technology == "FDM"
            and actual_dims[2] > 0.0  # Z = height in Blender
            and actual_dims[2] < 5.0
        ):
            layers = int(actual_dims[2] / 0.2)
            msg = (
                f"Target height ({actual_dims[2]:.1f}mm) is very small "
                f"for FDM printing. At a typical 0.2mm layer height, "
                f"the object would be only {layers} layers tall. "
                f"Consider SLA printing for small objects."
            )
            # Avoid duplicate if already added.
            if msg not in warnings:
                warnings.append(msg)
                logger.warning(msg)

        elapsed = time.perf_counter() - start_time

        logger.info(
            "Scaling transform applied: (%.2f, %.2f, %.2f) → "
            "(%.2f, %.2f, %.2f) mm in %.3f s",
            *original_dims,
            *actual_dims,
            elapsed,
        )

        return {
            "original_dimensions_mm": original_dims,
            "target_dimensions_mm": target_dims,
            "scaled_dimensions_mm": actual_dims,
            "scale_factors": scale_factors,
            "scaling_time_seconds": elapsed,
            "warnings": warnings,
        }

    def _configure_scene_units(self, context: "bpy.types.Context") -> None:
        """Set the Blender scene to metric with mm scale.

        Sets ``unit_system`` to ``'METRIC'``, ``unit_scale`` to
        ``0.001``, and ``length_unit`` to ``'MILLIMETERS'``.

        Implements: FR-005.
        """
        scene = context.scene
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 0.001
        scene.unit_settings.length_unit = "MILLIMETERS"

        logger.debug(
            "Scene units configured: system=%s, scale=%.4f, unit=%s",
            scene.unit_settings.system,
            scene.unit_settings.scale_length,
            scene.unit_settings.length_unit,
        )

    def _get_dimensions(self, obj: "bpy.types.Object") -> Tuple[float, float, float]:
        """Get the current bounding-box dimensions of an object.

        Args:
            obj: Blender object.

        Returns:
            Tuple of ``(width, height, depth)`` from
            ``obj.dimensions``.
        """
        dims = obj.dimensions
        return (dims[0], dims[1], dims[2])
