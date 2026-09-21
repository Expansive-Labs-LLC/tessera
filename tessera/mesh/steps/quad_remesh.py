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

"""Cleanup step: QuadriFlow quad remesh (Phase 2).

Converts a triangle mesh to quad-dominant topology using Blender's
built-in QuadriFlow remesh operator.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-010, FR-016.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import bpy

logger = logging.getLogger("tessera.mesh")

# Step classification for error handling (FR-020).
IS_CRITICAL = False


class QuadRemeshStep:
    """Convert a triangle mesh to quad-dominant topology.

    Uses ``bpy.ops.object.quadriflow_remesh()`` with a configurable
    target face count.  This step is **opt-in** (disabled by default)
    and SHALL NOT execute unless explicitly enabled (FR-016).

    This is a **non-critical** step — exceptions are caught by
    the pipeline.

    Implements: FR-010, FR-016.
    """

    name = "QuadRemeshStep"

    def execute(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute QuadriFlow quad remesh.

        Args:
            context: Blender context.
            obj: Target mesh object.
            settings: Pipeline settings dict.  Uses keys:
                ``enable_quad_remesh`` (bool, default ``False``),
                ``quad_target_faces`` (int, default ``10000``).

        Returns:
            Report dict with key ``quad_remesh_applied`` (bool).
        """
        enable = settings.get("enable_quad_remesh", False)

        # FR-016: Opt-in only — do not execute unless explicitly enabled.
        if not enable:
            return {"quad_remesh_applied": False}

        target_faces = settings.get("quad_target_faces", 10000)

        logger.debug(
            "Cleanup step started: step_name=%s, face_count_before=%d",
            self.name,
            len(obj.data.polygons),
        )

        start = time.perf_counter()

        # Ensure object is active and selected.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        # Execute QuadriFlow remesh operator.
        bpy.ops.object.quadriflow_remesh(
            target_faces=target_faces,
            use_mesh_symmetry=False,
            use_preserve_sharp=True,
            use_preserve_boundary=True,
            seed=0,
        )

        elapsed = time.perf_counter() - start
        logger.debug(
            "Cleanup step completed: step_name=%s, items_modified=1, "
            "step_time_seconds=%.3f",
            self.name,
            elapsed,
        )

        return {"quad_remesh_applied": True}
