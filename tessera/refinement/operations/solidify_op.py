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

"""Solidify operation for mesh refinement.

Adds wall thickness via Blender's Solidify modifier.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-023.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..intent_schema import EditResult

logger = logging.getLogger("tessera.refinement")


def execute_solidify(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
) -> EditResult:
    """Execute a solidify operation via Blender's Solidify modifier.

    FR-023: Adds wall thickness. When applied to a subset of
    vertices, uses a vertex group to limit influence.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: ``thickness_mm`` (float, default 2.0),
            ``offset`` (float -1.0 to 1.0, default -1.0).
        vertex_group_name: Target vertex group.

    Returns:
        ``EditResult``.
    """
    import bpy

    start = time.perf_counter()

    thickness_mm = parameters.get("thickness_mm", 2.0)
    offset = parameters.get("offset", -1.0)
    thickness_m = thickness_mm / 1000.0

    # Add Solidify modifier.
    mod = obj.modifiers.new(name="Tessera_Solidify", type="SOLIDIFY")
    mod.thickness = thickness_m
    mod.offset = offset
    mod.use_even_offset = True

    # Limit to vertex group if not whole mesh.
    if vertex_group_name and vertex_group_name not in ("_bf_all", ""):
        mod.vertex_group = vertex_group_name

    # Apply the modifier.
    bpy.context.view_layer.objects.active = obj
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except RuntimeError as exc:
        # Clean up on failure.
        obj.modifiers.remove(mod)
        return EditResult(
            success=False,
            description=f"Solidify failed: {exc}",
            vertices_modified=0,
            execution_time_seconds=time.perf_counter() - start,
        )

    elapsed = time.perf_counter() - start
    region_desc = vertex_group_name.replace("_bf_spatial_", "").replace("_bf_", "")
    if not region_desc or region_desc == "all":
        region_desc = "mesh"

    return EditResult(
        success=True,
        description=f"Solidified '{region_desc}' region by {thickness_mm:.1f} mm",
        vertices_modified=len(obj.data.vertices),
        execution_time_seconds=elapsed,
    )
