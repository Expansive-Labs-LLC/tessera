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

"""Build volume validation against printer profiles.

Checks that a scaled mesh fits within the selected printer's build
volume and reports violations with suggested corrective scale factors.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-017–FR-020, EC-002.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .printer_profiles import PrinterProfile

logger = logging.getLogger("tessera.scaling")

# FR-020: Small object warning threshold in mm.
_SMALL_OBJECT_THRESHOLD_MM = 5.0


@dataclass
class BuildVolumeViolation:
    """A single axis build-volume violation.

    Attributes:
        axis: Axis name (``"X"``, ``"Y"``, or ``"Z"``).
        mesh_dimension_mm: Mesh dimension on this axis in mm.
        build_limit_mm: Printer build volume limit on this axis in mm.
        overflow_mm: Amount exceeding the build limit in mm.
        suggested_scale_factor: Uniform scale factor to fit this axis.

    Implements: FR-018.
    """

    axis: str
    mesh_dimension_mm: float
    build_limit_mm: float
    overflow_mm: float
    suggested_scale_factor: float


class BuildVolumeCheck:
    """Validates that a mesh fits within a printer's build volume.

    Does NOT automatically scale down oversized meshes (FR-019,
    CON-006).  Reports violations and suggested scale factors for
    user confirmation.

    Implements: FR-017–FR-020, EC-002.
    """

    def validate(
        self,
        obj: Any,
        profile: PrinterProfile,
    ) -> Dict[str, Any]:
        """Check the mesh against the printer build volume.

        Args:
            obj: Blender object (must have ``dimensions`` attribute).
            profile: Printer profile with build volume dimensions.

        Returns:
            Dict with keys:
            - ``build_volume_fit`` (bool): ``True`` if mesh fits.
            - ``build_volume_violations`` (list): List of violation
              dicts, empty if mesh fits.
            - ``warnings`` (list): Warning messages.

        Implements: FR-017–FR-020, EC-002.
        """
        start_time = time.perf_counter()

        dims = obj.dimensions
        mesh_dims = (float(dims[0]), float(dims[1]), float(dims[2]))

        build_limits = (
            profile.build_width_mm,
            profile.build_depth_mm,
            profile.build_height_mm,
        )
        axis_names = ("X", "Y", "Z")

        violations: List[BuildVolumeViolation] = []
        warnings: List[str] = []

        # FR-017: Check each axis.
        for i in range(3):
            if mesh_dims[i] > build_limits[i]:
                overflow = mesh_dims[i] - build_limits[i]
                suggested = build_limits[i] / mesh_dims[i]
                violation = BuildVolumeViolation(
                    axis=axis_names[i],
                    mesh_dimension_mm=mesh_dims[i],
                    build_limit_mm=build_limits[i],
                    overflow_mm=overflow,
                    suggested_scale_factor=suggested,
                )
                violations.append(violation)
                logger.warning(
                    "Build volume violation on %s axis: "
                    "mesh=%.1f mm, limit=%.1f mm, overflow=%.1f mm",
                    axis_names[i],
                    mesh_dims[i],
                    build_limits[i],
                    overflow,
                )

        # EC-002: When multiple axes overflow, the suggested scale
        # factor is the minimum across all violated axes so that
        # all axes fit if applied uniformly.
        if len(violations) > 1:
            min_factor = min(v.suggested_scale_factor for v in violations)
            for v in violations:
                v.suggested_scale_factor = min_factor

        fit = len(violations) == 0

        if fit:
            logger.info(
                "Build volume check passed: mesh (%.1f, %.1f, %.1f) mm "
                "fits within %s (%.1f, %.1f, %.1f) mm",
                *mesh_dims,
                profile.name,
                *build_limits,
            )
        else:
            # FR-019: Report violation but do NOT auto-scale.
            suggested = violations[0].suggested_scale_factor
            logger.warning(
                "Build volume check FAILED: %d axis violation(s). "
                "Suggested uniform scale factor: %.3f. "
                "Awaiting user confirmation before corrective scaling.",
                len(violations),
                suggested,
            )

        # FR-020: Small object warning.
        smallest_dim = min(mesh_dims)
        if smallest_dim < _SMALL_OBJECT_THRESHOLD_MM:
            msg = (
                f"Smallest dimension is {smallest_dim:.1f}mm — "
                f"object may be too small to print reliably on "
                f"{profile.technology} printers."
            )
            warnings.append(msg)
            logger.warning(msg)

        elapsed = time.perf_counter() - start_time
        logger.debug("Build volume check completed in %.3f s", elapsed)

        return {
            "build_volume_fit": fit,
            "build_volume_violations": [
                {
                    "axis": v.axis,
                    "mesh_dimension_mm": v.mesh_dimension_mm,
                    "build_limit_mm": v.build_limit_mm,
                    "overflow_mm": v.overflow_mm,
                    "suggested_scale_factor": v.suggested_scale_factor,
                }
                for v in violations
            ],
            "build_volume_warnings": warnings,
        }
