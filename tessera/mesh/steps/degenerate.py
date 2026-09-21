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

"""Cleanup step: degenerate face removal.

Dissolves degenerate geometry (edges shorter than 1e-8 m) using
``bmesh.ops.dissolve_degenerate()``.  This effectively removes
zero-area triangles whose vertices are collinear, since the
shortest edge in such faces approaches zero length.

Note: The ``dist`` parameter of ``dissolve_degenerate`` is an
**edge-length** threshold, not a face-area threshold.  Using
1e-8 m catches edges that are sub-nanometer in length, which
reliably collapses degenerate faces in practice.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: EC-001.
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

# EC-001: Edge-length threshold for dissolve_degenerate (m).
# Edges shorter than this are dissolved, collapsing zero-area faces.
_DEGENERATE_EDGE_THRESHOLD = 1e-8


class DegenerateStep:
    """Remove degenerate (zero-area) faces from the mesh.

    Uses ``bmesh.ops.dissolve_degenerate()`` with an edge-length
    threshold of 1e-8 m to collapse edges that are effectively
    zero-length, which dissolves degenerate faces.  This is a
    **non-critical** step — exceptions are caught by the pipeline.

    Implements: EC-001.
    """

    name = "DegenerateStep"

    def execute(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute degenerate face removal.

        Args:
            context: Blender context.
            obj: Target mesh object.
            settings: Pipeline settings dict (unused by this step).

        Returns:
            Report dict with key ``degenerate_faces_removed`` (int).
        """
        logger.debug(
            "Cleanup step started: step_name=%s, face_count_before=%d",
            self.name,
            len(obj.data.polygons),
        )

        start = time.perf_counter()

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)

            faces_before = len(bm.faces)

            # dissolve_degenerate removes edges shorter than the
            # given distance, which collapses zero-area triangles.
            bmesh.ops.dissolve_degenerate(
                bm, edges=bm.edges, dist=_DEGENERATE_EDGE_THRESHOLD
            )

            faces_after = len(bm.faces)
            degenerate_removed = faces_before - faces_after

            bm.to_mesh(obj.data)
        finally:
            bm.free()

        obj.data.update()

        elapsed = time.perf_counter() - start
        logger.debug(
            "Cleanup step completed: step_name=%s, items_modified=%d, "
            "step_time_seconds=%.3f",
            self.name,
            degenerate_removed,
            elapsed,
        )

        return {"degenerate_faces_removed": degenerate_removed}
