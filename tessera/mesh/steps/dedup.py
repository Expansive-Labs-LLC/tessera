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

"""Cleanup step: duplicate vertex removal (merge by distance).

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-003.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import bmesh
import bpy

logger = logging.getLogger("tessera.mesh")

# Step classification for error handling (FR-020).
IS_CRITICAL = True


class DedupStep:
    """Remove duplicate vertices by merging within a distance threshold.

    Uses ``bmesh.ops.remove_doubles()`` with a configurable merge
    distance.  This is a **critical** step — exceptions propagate
    as ``MeshCleanupError``.

    Implements: FR-003.
    """

    name = "DedupStep"

    def execute(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute duplicate vertex removal.

        Args:
            context: Blender context.
            obj: Target mesh object.
            settings: Pipeline settings dict.  Uses key
                ``merge_distance`` (float, default ``0.0001``).

        Returns:
            Report dict with key ``doubles_removed`` (int).
        """
        merge_distance = settings.get("merge_distance", 0.0001)

        logger.debug(
            "Cleanup step started: step_name=%s, face_count_before=%d",
            self.name,
            len(obj.data.polygons),
        )

        start = time.perf_counter()

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)

            verts_before = len(bm.verts)

            bmesh.ops.remove_doubles(
                bm, verts=bm.verts, dist=merge_distance
            )

            verts_after = len(bm.verts)
            doubles_removed = verts_before - verts_after

            bm.to_mesh(obj.data)
        finally:
            bm.free()

        obj.data.update()

        elapsed = time.perf_counter() - start
        logger.debug(
            "Cleanup step completed: step_name=%s, items_modified=%d, "
            "step_time_seconds=%.3f",
            self.name,
            doubles_removed,
            elapsed,
        )

        return {"doubles_removed": doubles_removed}
