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

"""Dimension input specification and resolution.

Provides ``DimensionSpec`` for user-specified or auto-inferred target
dimensions, and ``DimensionSuggestion`` for auto-inference results that
require user confirmation.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-001, FR-007, FR-009, SEC-001, EC-006, EC-007.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Tuple

logger = logging.getLogger("tessera.scaling")

# SEC-001: Maximum allowed dimension value in mm.
_MAX_DIMENSION_MM = 1e6


def _validate_dimension(value: float, axis: str) -> None:
    """Validate a single dimension value.

    Rejects NaN, Inf, negative, and values exceeding 1e6 mm.

    Args:
        value: The dimension value in mm.
        axis: Axis name for error messages (e.g. ``"width"``).

    Raises:
        ValueError: If the value is invalid.

    Implements: SEC-001, EC-006.
    """
    if math.isnan(value):
        raise ValueError(f"Target dimension must not be NaN: {axis}")
    if math.isinf(value):
        raise ValueError(f"Target dimension must not be Inf: {axis}")
    if value < 0.0:
        raise ValueError(f"Target dimension must be positive: {axis}={value}mm")
    if value > _MAX_DIMENSION_MM:
        raise ValueError(
            f"Target dimension exceeds maximum ({_MAX_DIMENSION_MM}mm): "
            f"{axis}={value}mm"
        )


@dataclass
class DimensionSuggestion:
    """Auto-inferred dimension suggestion requiring user confirmation.

    Returned by ``AutoDimensionInfer.infer()`` when auto-inference
    mode is active.  Dimensions are NOT applied until the user
    confirms via the ``on_confirm`` callback.

    Attributes:
        suggested_width_mm: Suggested width in mm (0.0 = unset).
        suggested_height_mm: Suggested height in mm (0.0 = unset).
        suggested_depth_mm: Suggested depth in mm (0.0 = unset).
        confidence: ``"high"`` if the object class is recognized
            and unambiguous, ``"low"`` otherwise.
        message: Human-readable explanation of the suggestion.
        requires_confirmation: Always ``True`` — auto-inferred
            dimensions are never applied automatically (CON-006).

    Implements: FR-009, FR-011.
    """

    suggested_width_mm: float = 0.0
    suggested_height_mm: float = 0.0
    suggested_depth_mm: float = 0.0
    confidence: str = "low"
    message: str = ""
    requires_confirmation: bool = True


@dataclass
class DimensionSpec:
    """User-specified or auto-inferred target dimensions.

    At least one of ``width_mm``, ``height_mm``, or ``depth_mm``
    must be positive when ``auto`` is ``False``.  A value of ``0.0``
    means "unset — compute proportionally from the specified axis".

    Attributes:
        width_mm: Target width in mm (0.0 = unset).
        height_mm: Target height in mm (0.0 = unset).
        depth_mm: Target depth in mm (0.0 = unset).
        auto: If ``True``, triggers auto-inference mode.
        object_class_label: Object class label for auto-inference
            (e.g. ``"mug"``).  Ignored when ``auto`` is ``False``.

    Implements: FR-001, FR-007.
    """

    width_mm: float = 0.0
    height_mm: float = 0.0
    depth_mm: float = 0.0
    auto: bool = False
    object_class_label: str = ""

    def __post_init__(self) -> None:
        """Validate dimension values on construction.

        Implements: SEC-001, EC-006, EC-007.
        """
        # Validate each specified dimension.
        if self.width_mm != 0.0:
            _validate_dimension(self.width_mm, "width")
        if self.height_mm != 0.0:
            _validate_dimension(self.height_mm, "height")
        if self.depth_mm != 0.0:
            _validate_dimension(self.depth_mm, "depth")

        # EC-007: No dimensions with auto=False.
        if not self.auto and not self.has_any_dimension():
            raise ValueError(
                "At least one target dimension must be specified when "
                "auto_infer is disabled. Set target_width_mm, "
                "target_height_mm, or target_depth_mm to a positive "
                "value, or enable auto_infer."
            )

    def has_any_dimension(self) -> bool:
        """Return ``True`` if at least one target dimension is set."""
        return self.width_mm > 0.0 or self.height_mm > 0.0 or self.depth_mm > 0.0

    def specified_count(self) -> int:
        """Return the number of explicitly specified dimensions."""
        count = 0
        if self.width_mm > 0.0:
            count += 1
        if self.height_mm > 0.0:
            count += 1
        if self.depth_mm > 0.0:
            count += 1
        return count

    def resolve(
        self, current_bbox: Tuple[float, float, float]
    ) -> Tuple[float, float, float]:
        """Resolve target dimensions, filling unset axes proportionally.

        When only one or two axes are specified, the remaining axes
        are computed by preserving the mesh's original aspect ratio.

        Args:
            current_bbox: Current bounding-box dimensions as
                ``(width, height, depth)`` in Blender units.

        Returns:
            Tuple of ``(target_width_mm, target_height_mm,
            target_depth_mm)`` — all three axes resolved.

        Implements: FR-001.
        """
        w, h, d = current_bbox
        tw, th, td = self.width_mm, self.height_mm, self.depth_mm

        specified = self.specified_count()

        if specified == 1:
            # FR-002: Uniform scaling from the single specified axis.
            if tw > 0.0:
                ratio = tw / w if w > 0.0 else 1.0
            elif th > 0.0:
                ratio = th / h if h > 0.0 else 1.0
            else:
                ratio = td / d if d > 0.0 else 1.0

            return (
                tw if tw > 0.0 else w * ratio,
                th if th > 0.0 else h * ratio,
                td if td > 0.0 else d * ratio,
            )

        elif specified == 2:
            # Two axes specified — compute the third proportionally
            # from the average scale factor of the two specified axes.
            if tw <= 0.0:
                # Width unset — compute from height/depth average.
                avg_ratio = 0.0
                count = 0
                if th > 0.0 and h > 0.0:
                    avg_ratio += th / h
                    count += 1
                if td > 0.0 and d > 0.0:
                    avg_ratio += td / d
                    count += 1
                avg_ratio = avg_ratio / count if count > 0 else 1.0
                tw = w * avg_ratio
            elif th <= 0.0:
                avg_ratio = 0.0
                count = 0
                if tw > 0.0 and w > 0.0:
                    avg_ratio += tw / w
                    count += 1
                if td > 0.0 and d > 0.0:
                    avg_ratio += td / d
                    count += 1
                avg_ratio = avg_ratio / count if count > 0 else 1.0
                th = h * avg_ratio
            else:
                avg_ratio = 0.0
                count = 0
                if tw > 0.0 and w > 0.0:
                    avg_ratio += tw / w
                    count += 1
                if th > 0.0 and h > 0.0:
                    avg_ratio += th / h
                    count += 1
                avg_ratio = avg_ratio / count if count > 0 else 1.0
                td = d * avg_ratio

            return (tw, th, td)

        else:
            # All three specified (specified == 3).
            return (tw, th, td)
