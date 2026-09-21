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

"""Cleanup step: recalculate face normals to point outward.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-004.
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


class NormalsStep:
    """Recalculate all face normals to point outward.

    Uses ``bmesh.ops.recalc_face_normals()`` to ensure consistent
    winding order across all faces.  This is a **critical** step —
    exceptions propagate as ``MeshCleanupError``.

    Implements: FR-004.
    """

    name = "NormalsStep"

    def execute(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute normal recalculation.

        Args:
            context: Blender context.
            obj: Target mesh object.
            settings: Pipeline settings dict (unused by this step).

        Returns:
            Report dict with key ``normals_flipped`` (int).
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

            # Capture normal directions before recalculation.
            normals_before = [f.normal.copy() for f in bm.faces]

            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

            # Count how many normals changed direction.
            normals_flipped = 0
            for i, face in enumerate(bm.faces):
                if i < len(normals_before):
                    dot = face.normal.dot(normals_before[i])
                    if dot < 0:
                        normals_flipped += 1

            bm.to_mesh(obj.data)
        finally:
            bm.free()

        obj.data.update()

        elapsed = time.perf_counter() - start
        logger.debug(
            "Cleanup step completed: step_name=%s, items_modified=%d, "
            "step_time_seconds=%.3f",
            self.name,
            normals_flipped,
            elapsed,
        )

        return {"normals_flipped": normals_flipped}
