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

"""Cleanup step: Decimate modifier with sharp edge preservation (Phase 2).

Applies a Blender Decimate modifier in COLLAPSE mode, preserving
edges with high dihedral angles.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-011, FR-012.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any

import bmesh
import bpy

logger = logging.getLogger("tessera.mesh")

# Step classification for error handling (FR-020).
IS_CRITICAL = False

# FR-012: Dihedral angle threshold for sharp edge marking (degrees).
_SHARP_ANGLE_THRESHOLD_DEG = 30.0
_SHARP_ANGLE_THRESHOLD_RAD = math.radians(_SHARP_ANGLE_THRESHOLD_DEG)


class DecimateStep:
    """Decimate mesh topology while preserving sharp edges.

    Applies a Blender Decimate modifier in ``COLLAPSE`` mode with
    ``use_collapse_triangulate = False``.  Before decimation, marks
    edges with dihedral angle > 30° as sharp (FR-012).

    This is a **non-critical** step — exceptions are caught by
    the pipeline.

    Implements: FR-011, FR-012.
    """

    name = "DecimateStep"

    def execute(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute decimation with sharp edge preservation.

        Args:
            context: Blender context.
            obj: Target mesh object.
            settings: Pipeline settings dict.  Uses keys:
                ``enable_decimate`` (bool, default ``False``),
                ``decimate_target_faces`` (int, default ``50000``).

        Returns:
            Report dict with key ``decimate_applied`` (bool).
        """
        enable = settings.get("enable_decimate", False)

        if not enable:
            return {"decimate_applied": False}

        target_faces = settings.get("decimate_target_faces", 50000)

        logger.debug(
            "Cleanup step started: step_name=%s, face_count_before=%d",
            self.name,
            len(obj.data.polygons),
        )

        start = time.perf_counter()

        # FR-012: Mark sharp edges before decimation.
        self._mark_sharp_edges(obj)

        # Calculate decimation ratio.
        current_faces = len(obj.data.polygons)
        if current_faces > 0:
            ratio = min(1.0, target_faces / current_faces)
        else:
            ratio = 1.0

        # Ensure object is active and selected.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        # Apply Decimate modifier.
        modifier = obj.modifiers.new(
            name="TesseraDecimate", type="DECIMATE"
        )
        modifier.decimate_type = "COLLAPSE"
        modifier.ratio = ratio
        modifier.use_collapse_triangulate = False
        # FR-012: Preserve sharp boundaries.
        modifier.use_dissolve_boundaries = False

        bpy.ops.object.modifier_apply(modifier=modifier.name)

        elapsed = time.perf_counter() - start
        logger.debug(
            "Cleanup step completed: step_name=%s, items_modified=1, "
            "step_time_seconds=%.3f",
            self.name,
            elapsed,
        )

        return {"decimate_applied": True}

    @staticmethod
    def _mark_sharp_edges(obj: "bpy.types.Object") -> None:
        """Mark edges with dihedral angle > 30° as sharp.

        Uses the ``bmesh`` API for efficient edge iteration
        (CON-006).

        Args:
            obj: Target mesh object.

        Implements: FR-012.
        """
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)

            for edge in bm.edges:
                if len(edge.link_faces) == 2:
                    angle = edge.calc_face_angle(0.0)
                    if angle > _SHARP_ANGLE_THRESHOLD_RAD:
                        edge.smooth = False

            bm.to_mesh(obj.data)
        finally:
            bm.free()

        obj.data.update()
