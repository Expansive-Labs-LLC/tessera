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

"""Cleanup step: voxel remesh fallback.

Applies a Blender Voxel Remesh modifier when the mesh remains
non-manifold after surgical repair steps.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-006.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import bpy

logger = logging.getLogger("tessera.mesh")

# Step classification for error handling (FR-020).
IS_CRITICAL = False


class VoxelRemeshStep:
    """Apply voxel remesh as a fallback for non-manifold meshes.

    Adds a Blender Voxel Remesh modifier with a configurable voxel
    size and applies it.  Only activates when the mesh remains
    non-manifold after prior cleanup steps.

    Uses ``bpy.ops`` because there is no ``bmesh`` equivalent for
    voxel remeshing (CON-006 permits this).

    This is a **non-critical** step — exceptions are caught by
    the pipeline.

    Implements: FR-006.
    """

    name = "VoxelRemeshStep"

    def execute(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute voxel remesh fallback.

        Args:
            context: Blender context.
            obj: Target mesh object.
            settings: Pipeline settings dict.  Uses keys:
                ``voxel_size`` (float, default ``0.01``),
                ``auto_voxel_fallback`` (bool, default ``True``).

        Returns:
            Report dict with key ``voxel_remesh_applied`` (bool).
        """
        voxel_size = settings.get("voxel_size", 0.01)
        auto_fallback = settings.get("auto_voxel_fallback", True)

        if not auto_fallback:
            return {"voxel_remesh_applied": False}

        logger.debug(
            "Cleanup step started: step_name=%s, face_count_before=%d",
            self.name,
            len(obj.data.polygons),
        )

        start = time.perf_counter()

        # §11.1: Log fallback activation.
        logger.warning(
            "Voxel remesh fallback activated: reason=%s",
            "mesh still non-manifold after surgical repair",
        )

        # Ensure object is active and selected.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        # Apply voxel remesh via modifier.
        modifier = obj.modifiers.new(name="TesseraVoxelRemesh", type="REMESH")
        modifier.mode = "VOXEL"
        modifier.voxel_size = voxel_size

        # Apply the modifier.
        bpy.ops.object.modifier_apply(modifier=modifier.name)

        elapsed = time.perf_counter() - start
        logger.debug(
            "Cleanup step completed: step_name=%s, items_modified=1, "
            "step_time_seconds=%.3f",
            self.name,
            elapsed,
        )

        return {"voxel_remesh_applied": True}
