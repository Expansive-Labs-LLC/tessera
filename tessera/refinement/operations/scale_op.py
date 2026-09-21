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

"""Scale operations for mesh refinement.

Implements directional and uniform scaling with absolute dimension
support.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-020.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..intent_schema import EditResult

logger = logging.getLogger("tessera.refinement")


def execute_scale(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
) -> EditResult:
    """Execute a scale operation on the mesh.

    FR-020: Supports directional scaling along X, Y, Z, or uniform
    axes. When an absolute dimension is given, calculates the scale
    factor from the current bounding box.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: Operation parameters — ``axis`` (X/Y/Z/UNIFORM),
            ``factor`` (float), or ``absolute_mm`` (float).
        vertex_group_name: Name of the vertex group to scale.

    Returns:
        ``EditResult`` with operation outcome.
    """
    import bpy

    start = time.perf_counter()

    axis = parameters.get("axis", "UNIFORM").upper()
    factor = parameters.get("factor", 1.0)
    absolute_mm = parameters.get("absolute_mm")

    # If absolute dimension given, compute scale factor.
    if absolute_mm is not None:
        axis_idx = {"X": 0, "Y": 1, "Z": 2}.get(axis, 2)
        bbox = obj.bound_box
        coords = [v[axis_idx] for v in bbox]
        current_extent_m = max(coords) - min(coords)
        current_extent_mm = current_extent_m * 1000.0

        if current_extent_mm > 0:
            factor = absolute_mm / current_extent_mm
        else:
            factor = 1.0

    # Build scale vector.
    if axis == "X":
        scale_vec = (factor, 1.0, 1.0)
    elif axis == "Y":
        scale_vec = (1.0, factor, 1.0)
    elif axis == "Z":
        scale_vec = (1.0, 1.0, factor)
    else:  # UNIFORM
        scale_vec = (factor, factor, factor)

    # Select target vertices via vertex group.
    _select_vertex_group(obj, vertex_group_name)

    # Enter edit mode and apply scale.
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.transform.resize(value=scale_vec)
    bpy.ops.object.mode_set(mode="OBJECT")

    elapsed = time.perf_counter() - start

    axis_desc = axis.lower() if axis != "UNIFORM" else "uniformly"
    desc = f"Scaled {axis_desc} by {factor:.2f}x"
    if absolute_mm is not None:
        desc = f"Scaled {axis.lower()} to {absolute_mm:.1f} mm"

    vertex_count = _count_selected(obj, vertex_group_name)

    return EditResult(
        success=True,
        description=desc,
        vertices_modified=vertex_count,
        execution_time_seconds=elapsed,
    )


def _select_vertex_group(obj: Any, vg_name: str) -> None:
    """Select vertices in a vertex group.

    Args:
        obj: Blender mesh object.
        vg_name: Vertex group name.
    """
    import bpy

    # Deselect all first.
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")

    if vg_name == "_bf_all" or not vg_name:
        # Select all vertices.
        for v in obj.data.vertices:
            v.select = True
        return

    if vg_name not in obj.vertex_groups:
        # Fallback: select all.
        for v in obj.data.vertices:
            v.select = True
        return

    # Set active vertex group and select.
    obj.vertex_groups.active = obj.vertex_groups[vg_name]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.object.vertex_group_select()
    bpy.ops.object.mode_set(mode="OBJECT")


def _count_selected(obj: Any, vg_name: str) -> int:
    """Count vertices in a vertex group.

    Args:
        obj: Blender mesh object.
        vg_name: Vertex group name.

    Returns:
        Number of selected vertices.
    """
    try:
        if vg_name == "_bf_all" or not vg_name:
            return len(obj.data.vertices)
        vg_index = obj.vertex_groups[vg_name].index
        count = 0
        for v in obj.data.vertices:
            for g in v.groups:
                if g.group == vg_index:
                    count += 1
                    break
        return count
    except (AttributeError, KeyError):
        return len(obj.data.vertices) if hasattr(obj, "data") else 0
