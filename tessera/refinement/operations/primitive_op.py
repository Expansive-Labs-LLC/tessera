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

"""Primitive geometry add/remove operations for mesh refinement.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-027, FR-028.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..intent_schema import EditResult

logger = logging.getLogger("tessera.refinement")

#: FR-027: Supported primitive shapes.
_PRIMITIVE_OPS = {
    "CUBE": "mesh.primitive_cube_add",
    "SPHERE": "mesh.primitive_uv_sphere_add",
    "CYLINDER": "mesh.primitive_cylinder_add",
    "CONE": "mesh.primitive_cone_add",
}

#: FR-027: Location presets relative to mesh bounding box.
_LOCATION_PRESETS = {
    "on_top": lambda bb: (0, 0, bb[2]),
    "at_bottom": lambda bb: (0, 0, 0),
    "centered": lambda bb: (0, 0, bb[2] / 2),
}


def execute_add_geometry(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
) -> EditResult:
    """Add a primitive shape and boolean-union with the mesh.

    FR-027: Supports CUBE, SPHERE, CYLINDER, CONE. If boolean union
    fails (modifier produces zero faces or raises RuntimeError), the
    primitive is removed and a warning is shown.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: ``shape`` (enum), ``size_mm`` (float),
            ``location`` (preset string or (x,y,z)).
        vertex_group_name: Not used for add geometry.

    Returns:
        ``EditResult``. On boolean failure, ``success=False``.
    """
    import bpy

    start = time.perf_counter()

    shape = parameters.get("shape", "CUBE").upper()
    size_mm = float(parameters.get("size_mm", 10.0))
    location = parameters.get("location", "centered")
    size_m = size_mm / 1000.0

    if shape not in _PRIMITIVE_OPS:
        return EditResult(
            success=False,
            description=f"Unknown shape: {shape}",
            vertices_modified=0,
            execution_time_seconds=time.perf_counter() - start,
        )

    # Compute location.
    if isinstance(location, (list, tuple)) and len(location) == 3:
        loc = tuple(float(v) / 1000.0 for v in location)
    elif isinstance(location, str) and location in _LOCATION_PRESETS:
        bb = obj.dimensions.copy()
        bb_tuple = (bb[0], bb[1], bb[2])
        loc = _LOCATION_PRESETS[location](bb_tuple)
        # Offset by object location.
        loc = (
            loc[0] + obj.location[0],
            loc[1] + obj.location[1],
            loc[2] + obj.location[2],
        )
    else:
        loc = obj.location[:]

    # Add primitive.
    op_func = getattr(bpy.ops, _PRIMITIVE_OPS[shape].split(".")[0])
    op_method = getattr(op_func, _PRIMITIVE_OPS[shape].split(".")[1])
    op_method(size=size_m * 2, location=loc)

    primitive = bpy.context.active_object
    if primitive is None:
        return EditResult(
            success=False,
            description="Failed to create primitive",
            vertices_modified=0,
            execution_time_seconds=time.perf_counter() - start,
        )

    # Boolean union with original mesh.
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    mod = obj.modifiers.new(name="Tessera_Boolean", type="BOOLEAN")
    mod.operation = "UNION"
    mod.object = primitive

    face_count_before = len(obj.data.polygons)

    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
        face_count_after = len(obj.data.polygons)

        # FR-027: Check for boolean failure.
        if face_count_after == 0:
            raise RuntimeError("Boolean union produced zero faces")

    except RuntimeError as exc:
        # FR-027: Remove primitive, show warning, no undo snapshot.
        logger.warning(
            "Boolean union failed: shape=%s, error=%s",
            shape, str(exc),
        )
        bpy.data.objects.remove(primitive, do_unlink=True)
        return EditResult(
            success=False,
            description=(
                "Boolean union failed. The mesh may need cleanup "
                "before adding geometry. Try running mesh cleanup first."
            ),
            vertices_modified=0,
            execution_time_seconds=time.perf_counter() - start,
        )

    # Remove the primitive object.
    bpy.data.objects.remove(primitive, do_unlink=True)

    elapsed = time.perf_counter() - start

    return EditResult(
        success=True,
        description=(
            f"Added {shape.lower()} ({size_mm:.1f} mm) "
            f"and boolean-unioned"
        ),
        vertices_modified=len(obj.data.vertices),
        execution_time_seconds=elapsed,
    )


def execute_remove_geometry(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
) -> EditResult:
    """Delete selected vertices and fill holes.

    FR-028: Uses ``bpy.ops.mesh.delete(type='VERT')`` followed
    by ``bpy.ops.mesh.fill()`` on boundary edges.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: Not used.
        vertex_group_name: Target vertex group to delete.

    Returns:
        ``EditResult``.
    """
    import bpy
    from .scale_op import _select_vertex_group, _count_selected

    start = time.perf_counter()

    vertex_count = _count_selected(obj, vertex_group_name)
    _select_vertex_group(obj, vertex_group_name)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")

    # Delete selected vertices.
    bpy.ops.mesh.delete(type="VERT")

    # Fill boundary holes.
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.mesh.select_non_manifold()
    try:
        bpy.ops.mesh.fill()
    except RuntimeError:
        # May fail if no boundary edges remain.
        pass

    bpy.ops.object.mode_set(mode="OBJECT")

    elapsed = time.perf_counter() - start

    return EditResult(
        success=True,
        description=f"Removed {vertex_count} vertices and filled holes",
        vertices_modified=vertex_count,
        execution_time_seconds=elapsed,
    )
