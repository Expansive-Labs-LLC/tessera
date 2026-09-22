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

"""Cleanup step: detect and fill boundary holes.

Identifies boundary edges (edges belonging to only one face) and
fills holes by triangulating boundary loops.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-005, EC-004.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import bmesh
import bpy

logger = logging.getLogger("tessera.mesh")

# Step classification for error handling (FR-020).
IS_CRITICAL = False

# FR-005 / EC-004: Maximum boundary loop edge count for hole filling.
_MAX_BOUNDARY_LOOP_EDGES = 500


class HoleFillStep:
    """Fill boundary holes in the mesh.

    Detects boundary edges (edges with only one adjacent face),
    groups them into loops, and fills each loop with ≤ 500 edges
    via ``bmesh.ops.triangle_fill()``.  Loops exceeding the limit
    are skipped with a warning.

    This is a **non-critical** step — exceptions are caught by
    the pipeline.

    Implements: FR-005, EC-004.
    """

    name = "HoleFillStep"

    def execute(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute boundary hole filling.

        Args:
            context: Blender context.
            obj: Target mesh object.
            settings: Pipeline settings dict (unused by this step).

        Returns:
            Report dict with keys ``holes_filled`` (int) and
            ``holes_skipped`` (int).
        """
        logger.debug(
            "Cleanup step started: step_name=%s, face_count_before=%d",
            self.name,
            len(obj.data.polygons),
        )

        start = time.perf_counter()

        holes_filled = 0
        holes_skipped = 0

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)

            # Find boundary edges.
            boundary_edges = [e for e in bm.edges if e.is_boundary]

            if not boundary_edges:
                bm.to_mesh(obj.data)
                elapsed = time.perf_counter() - start
                logger.debug(
                    "Cleanup step completed: step_name=%s, "
                    "items_modified=0, step_time_seconds=%.3f",
                    self.name,
                    elapsed,
                )
                return {"holes_filled": 0, "holes_skipped": 0}

            # Group boundary edges into loops.
            loops = self._find_boundary_loops(boundary_edges)

            for loop_edges in loops:
                edge_count = len(loop_edges)

                if edge_count > _MAX_BOUNDARY_LOOP_EDGES:
                    # EC-004: Skip oversized loops.
                    logger.warning(
                        "Boundary loop with %d edges exceeds %d-edge "
                        "limit. Skipping fill — consider voxel remesh.",
                        edge_count,
                        _MAX_BOUNDARY_LOOP_EDGES,
                    )
                    holes_skipped += 1
                    continue

                try:
                    bmesh.ops.triangle_fill(bm, edges=loop_edges, use_beauty=True)
                    holes_filled += 1
                except Exception:
                    # Individual hole fill failure is non-critical.
                    logger.debug(
                        "Failed to fill boundary loop with %d edges",
                        edge_count,
                    )
                    holes_skipped += 1

            bm.to_mesh(obj.data)
        finally:
            bm.free()

        obj.data.update()

        elapsed = time.perf_counter() - start
        logger.debug(
            "Cleanup step completed: step_name=%s, "
            "items_modified=%d, step_time_seconds=%.3f",
            self.name,
            holes_filled,
            elapsed,
        )

        return {"holes_filled": holes_filled, "holes_skipped": holes_skipped}

    @staticmethod
    def _find_boundary_loops(
        boundary_edges: list,
    ) -> list[list]:
        """Group boundary edges into connected loops.

        Walks along boundary edges to form closed loops.

        Args:
            boundary_edges: List of boundary ``bmesh.types.BMEdge``.

        Returns:
            List of edge lists, each representing one boundary loop.
        """
        visited = set()
        loops = []

        for start_edge in boundary_edges:
            if start_edge.index in visited:
                continue

            loop = []
            current_edge = start_edge

            # Walk along connected boundary edges.
            while current_edge and current_edge.index not in visited:
                visited.add(current_edge.index)
                loop.append(current_edge)

                # Find next boundary edge connected to this one.
                next_edge = None
                for vert in current_edge.verts:
                    for linked_edge in vert.link_edges:
                        if linked_edge.is_boundary and linked_edge.index not in visited:
                            next_edge = linked_edge
                            break
                    if next_edge:
                        break

                current_edge = next_edge

            if loop:
                loops.append(loop)

        return loops
