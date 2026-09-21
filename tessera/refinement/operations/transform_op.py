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

"""Move and rotate operations for mesh refinement.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-021, FR-022.
"""

from __future__ import annotations

import math
import logging
import time
from typing import Any

from ..intent_schema import EditResult

logger = logging.getLogger("tessera.refinement")

#: FR-021: Direction to vector mapping (in Blender coordinates).
_DIRECTION_VECTORS = {
    "UP": (0.0, 0.0, 1.0),
    "DOWN": (0.0, 0.0, -1.0),
    "LEFT": (-1.0, 0.0, 0.0),
    "RIGHT": (1.0, 0.0, 0.0),
    "FORWARD": (0.0, 1.0, 0.0),
    "BACK": (0.0, -1.0, 0.0),
}


def execute_move(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
) -> EditResult:
    """Execute a move/translate operation on selected vertices.

    FR-021: Translates by direction enum or explicit vector.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: ``direction`` (enum or (x,y,z)), ``distance`` (mm).
        vertex_group_name: Target vertex group.

    Returns:
        ``EditResult``.
    """
    import bpy
    from .scale_op import _select_vertex_group, _count_selected

    start = time.perf_counter()

    direction = parameters.get("direction", "UP")
    distance_mm = parameters.get("distance", 0.0)
    distance_m = distance_mm / 1000.0

    # Get direction vector.
    if isinstance(direction, (list, tuple)) and len(direction) == 3:
        vec = tuple(float(v) for v in direction)
        # Normalize and scale.
        mag = math.sqrt(sum(v * v for v in vec))
        if mag > 0:
            vec = tuple(v / mag * distance_m for v in vec)
        dir_desc = f"({vec[0]:.1f}, {vec[1]:.1f}, {vec[2]:.1f})"
    else:
        direction_upper = str(direction).upper()
        base_vec = _DIRECTION_VECTORS.get(direction_upper, (0, 0, 1))
        vec = tuple(v * distance_m for v in base_vec)
        dir_desc = direction_upper.lower()

    _select_vertex_group(obj, vertex_group_name)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.transform.translate(value=vec)
    bpy.ops.object.mode_set(mode="OBJECT")

    elapsed = time.perf_counter() - start
    vertex_count = _count_selected(obj, vertex_group_name)

    return EditResult(
        success=True,
        description=f"Moved {dir_desc} by {distance_mm:.1f} mm",
        vertices_modified=vertex_count,
        execution_time_seconds=elapsed,
    )


def execute_rotate(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
) -> EditResult:
    """Execute a rotate operation on selected vertices.

    FR-022: Rotates around an axis with configurable pivot.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: ``axis`` (X/Y/Z), ``angle_degrees``, ``pivot``.
        vertex_group_name: Target vertex group.

    Returns:
        ``EditResult``.
    """
    import bpy
    from .scale_op import _select_vertex_group, _count_selected

    start = time.perf_counter()

    axis = parameters.get("axis", "Z").upper()
    angle_deg = parameters.get("angle_degrees", 0.0)
    pivot = parameters.get("pivot", "MEDIAN_POINT")
    angle_rad = math.radians(angle_deg)

    # Build axis constraint.
    constraint_axis = (axis == "X", axis == "Y", axis == "Z")

    _select_vertex_group(obj, vertex_group_name)

    # Set pivot point.
    bpy.context.scene.tool_settings.transform_pivot_point = pivot

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.transform.rotate(
        value=angle_rad,
        orient_axis=axis,
        constraint_axis=constraint_axis,
    )
    bpy.ops.object.mode_set(mode="OBJECT")

    elapsed = time.perf_counter() - start
    vertex_count = _count_selected(obj, vertex_group_name)

    return EditResult(
        success=True,
        description=f"Rotated {angle_deg:.1f}° around {axis}-axis",
        vertices_modified=vertex_count,
        execution_time_seconds=elapsed,
    )
