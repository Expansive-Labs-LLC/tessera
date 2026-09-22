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

"""Smooth, sharpen, and bevel operations for mesh refinement.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-024, FR-025, FR-026.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..intent_schema import EditResult

logger = logging.getLogger("tessera.refinement")


def execute_smooth(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
) -> EditResult:
    """Apply Laplacian smoothing to selected vertices.

    FR-024: Uses ``bpy.ops.mesh.vertices_smooth_laplacian()``.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: ``iterations`` (int, 1–100, default 5),
            ``factor`` (float, 0.0–1.0, default 0.5).
        vertex_group_name: Target vertex group.

    Returns:
        ``EditResult``.
    """
    import bpy

    from .scale_op import _count_selected, _select_vertex_group

    start = time.perf_counter()

    iterations = int(parameters.get("iterations", 5))
    factor = float(parameters.get("factor", 0.5))

    _select_vertex_group(obj, vertex_group_name)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.vertices_smooth_laplacian(
        repeat=iterations,
        lambda_factor=factor,
    )
    bpy.ops.object.mode_set(mode="OBJECT")

    elapsed = time.perf_counter() - start
    vertex_count = _count_selected(obj, vertex_group_name)

    return EditResult(
        success=True,
        description=(
            f"Smoothed with {iterations} iterations " f"(factor {factor:.1f})"
        ),
        vertices_modified=vertex_count,
        execution_time_seconds=elapsed,
    )


def execute_sharpen(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
) -> EditResult:
    """Mark edges as sharp and apply Edge Split modifier.

    FR-025: Applies edge sharpening with configurable angle threshold.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: ``angle_threshold_degrees`` (float, 0–180, default 30).
        vertex_group_name: Target vertex group.

    Returns:
        ``EditResult``.
    """
    import math

    import bpy

    from .scale_op import _count_selected, _select_vertex_group

    start = time.perf_counter()

    angle_deg = float(parameters.get("angle_threshold_degrees", 30.0))
    angle_rad = math.radians(angle_deg)

    _select_vertex_group(obj, vertex_group_name)

    # Mark sharp edges.
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.edges_select_sharp(sharpness=angle_rad)
    bpy.ops.mesh.mark_sharp()
    bpy.ops.object.mode_set(mode="OBJECT")

    # Apply Edge Split modifier.
    mod = obj.modifiers.new(name="Tessera_EdgeSplit", type="EDGE_SPLIT")
    mod.split_angle = angle_rad
    bpy.ops.object.modifier_apply(modifier=mod.name)

    elapsed = time.perf_counter() - start
    vertex_count = _count_selected(obj, vertex_group_name)

    return EditResult(
        success=True,
        description=f"Sharpened edges at {angle_deg:.0f}° threshold",
        vertices_modified=vertex_count,
        execution_time_seconds=elapsed,
    )


def execute_bevel(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
) -> EditResult:
    """Apply bevel to selected edges.

    FR-026: Uses ``bpy.ops.mesh.bevel()``.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: ``width_mm`` (float, 0.1–20.0, default 1.0),
            ``segments`` (int, 1–10, default 2).
        vertex_group_name: Target vertex group.

    Returns:
        ``EditResult``.
    """
    import bpy

    from .scale_op import _count_selected, _select_vertex_group

    start = time.perf_counter()

    width_mm = float(parameters.get("width_mm", 1.0))
    segments = int(parameters.get("segments", 2))
    width_m = width_mm / 1000.0

    _select_vertex_group(obj, vertex_group_name)

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.bevel(
        offset=width_m,
        segments=segments,
        affect="EDGES",
    )
    bpy.ops.object.mode_set(mode="OBJECT")

    elapsed = time.perf_counter() - start
    vertex_count = _count_selected(obj, vertex_group_name)

    return EditResult(
        success=True,
        description=(
            f"Beveled edges: {width_mm:.1f} mm width, " f"{segments} segments"
        ),
        vertices_modified=vertex_count,
        execution_time_seconds=elapsed,
    )
