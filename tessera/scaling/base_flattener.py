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

"""Base flattener — aligns the flattest bottom region to Z=0.

After orientation optimization, translates the object so that its
lowest vertex sits on the build plate (Z=0) and reports the flatness
of the bottom region.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-027–FR-030.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import numpy as np

logger = logging.getLogger("tessera.scaling")

# FR-028: Flatness variance threshold in mm².
_FLAT_VARIANCE_THRESHOLD = 0.01

# FR-030: Non-flat bottom warning threshold in mm².
_NONFLAT_WARNING_THRESHOLD = 1.0

# FR-027: Bottom region percentage of bounding-box height.
_BOTTOM_REGION_PCT = 0.10


class BaseFlattener:
    """Aligns the flattest bottom region to the build plate (Z=0).

    Identifies the bottom face region, computes its flatness, and
    translates the object so the minimum vertex is at Z=0.

    Implements: FR-027–FR-030.
    """

    def flatten(
        self,
        context: Any,
        obj: Any,
    ) -> Dict[str, Any]:
        """Flatten the bottom of the mesh to the build plate.

        Args:
            context: Blender context.
            obj: Target mesh object.

        Returns:
            Dict with flattening diagnostics:
            - ``bottom_flatness_variance_mm2`` (float)
            - ``base_z_offset_mm`` (float)
            - ``bottom_is_flat`` (bool)
            - ``warnings`` (list[str])

        Implements: FR-027–FR-030.
        """
        mesh = obj.data
        warnings: list[str] = []

        # Collect all vertex Z coordinates.
        verts = mesh.vertices
        num_verts = len(verts)

        if num_verts == 0:
            return {
                "bottom_flatness_variance_mm2": 0.0,
                "base_z_offset_mm": 0.0,
                "bottom_is_flat": True,
                "warnings": [],
            }

        z_coords = np.zeros(num_verts, dtype=np.float64)
        for i, v in enumerate(verts):
            z_coords[i] = v.co[2]

        # Apply object transform to get world-space Z.
        # (After transform_apply, obj.matrix_world should be identity
        # for location, but add location offset for safety.)
        z_coords += obj.location[2]

        min_z = float(np.min(z_coords))
        max_z = float(np.max(z_coords))
        bbox_height = max_z - min_z

        if bbox_height <= 0.0:
            # Flat plane — already at build plate.
            z_offset = -min_z
            obj.location.z -= min_z

            return {
                "bottom_flatness_variance_mm2": 0.0,
                "base_z_offset_mm": abs(z_offset),
                "bottom_is_flat": True,
                "warnings": [],
            }

        # FR-027: Bottom region = faces within 10% of bbox height
        # from the minimum Z.
        bottom_threshold = min_z + bbox_height * _BOTTOM_REGION_PCT

        # Collect Z-coordinates of vertices belonging to bottom faces.
        bottom_face_vert_z: list[float] = []
        polys = mesh.polygons

        for poly in polys:
            # Face center Z.
            center_z = poly.center[2] + obj.location[2]
            if center_z <= bottom_threshold:
                for vi in poly.vertices:
                    bottom_face_vert_z.append(z_coords[vi])

        if len(bottom_face_vert_z) == 0:
            # No bottom faces found — use all vertices near the bottom.
            bottom_mask = z_coords <= bottom_threshold
            bottom_face_vert_z = z_coords[bottom_mask].tolist()

        if len(bottom_face_vert_z) == 0:
            # Extreme case: just use the minimum vertex.
            variance = 0.0
        else:
            # FR-028: Compute flatness as variance of Z-coordinates.
            variance = float(np.var(bottom_face_vert_z))

        is_flat = variance < _FLAT_VARIANCE_THRESHOLD

        # FR-030: Non-flat bottom warning.
        if variance > _NONFLAT_WARNING_THRESHOLD:
            msg = (
                f"Bottom region is not flat (variance={variance:.2f}mm²). "
                f"The object may not sit stably on the build plate. "
                f"Consider manual orientation."
            )
            warnings.append(msg)
            logger.warning(msg)

        # FR-029: Translate to Z=0.
        z_offset = min_z
        obj.location.z -= min_z

        logger.info(
            "Base flattened to build plate: z_offset=%.3f mm, "
            "flatness_variance=%.4f mm²",
            abs(z_offset),
            variance,
        )

        return {
            "bottom_flatness_variance_mm2": variance,
            "base_z_offset_mm": abs(z_offset),
            "bottom_is_flat": is_flat,
            "warnings": warnings,
        }
