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

"""Pre/post cleanup mesh diagnostics collection.

Captures vertex/face counts before and after cleanup and assembles
the 15-key diagnostics dict required by FR-007.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-007.
"""

from __future__ import annotations

from typing import Any

import bmesh
import bpy


def collect_before_stats(obj: "bpy.types.Object") -> dict[str, int]:
    """Capture mesh statistics before cleanup.

    Args:
        obj: Blender mesh object.

    Returns:
        Dict with ``vertices_before`` and ``faces_before``.
    """
    return {
        "vertices_before": len(obj.data.vertices),
        "faces_before": len(obj.data.polygons),
    }


def collect_after_stats(obj: "bpy.types.Object") -> dict[str, int]:
    """Capture mesh statistics after cleanup.

    Args:
        obj: Blender mesh object.

    Returns:
        Dict with ``vertices_after`` and ``faces_after``.
    """
    return {
        "vertices_after": len(obj.data.vertices),
        "faces_after": len(obj.data.polygons),
    }


def check_topology(
    obj: "bpy.types.Object",
) -> tuple[bool, bool]:
    """Check manifold and watertight status in a single pass.

    Performs both checks using one bmesh round-trip, avoiding the
    overhead of creating and parsing the mesh structure twice.

    A mesh is manifold when every edge belongs to exactly two faces
    and every vertex is manifold.  A watertight mesh is manifold
    and has no boundary edges.

    Args:
        obj: Blender mesh object.

    Returns:
        Tuple of ``(is_manifold, is_watertight)``.
    """
    is_manifold = True
    is_watertight = True

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)

        for edge in bm.edges:
            if edge.is_boundary:
                is_watertight = False
            if not edge.is_manifold:
                is_manifold = False
                is_watertight = False

        if is_manifold:
            for vert in bm.verts:
                if not vert.is_manifold:
                    is_manifold = False
                    is_watertight = False
                    break
    finally:
        bm.free()

    return is_manifold, is_watertight


def check_manifold(obj: "bpy.types.Object") -> bool:
    """Check whether the mesh is manifold.

    Convenience wrapper around :func:`check_topology`.

    Args:
        obj: Blender mesh object.

    Returns:
        ``True`` if the mesh is manifold.
    """
    is_manifold, _ = check_topology(obj)
    return is_manifold


def check_watertight(obj: "bpy.types.Object") -> bool:
    """Check whether the mesh is watertight.

    Convenience wrapper around :func:`check_topology`.

    Args:
        obj: Blender mesh object.

    Returns:
        ``True`` if the mesh is watertight.
    """
    _, is_watertight = check_topology(obj)
    return is_watertight


def build_diagnostics(
    before_stats: dict[str, int],
    step_reports: dict[str, Any],
    after_stats: dict[str, int],
    is_manifold: bool,
    is_watertight: bool,
    cleanup_time: float,
    step_errors: list[dict[str, str]],
) -> dict[str, Any]:
    """Assemble the full diagnostics dict from component data.

    Merges before/after stats, individual step reports, and
    validation results into the 15-key + ``step_errors`` dict
    defined by FR-007.

    Args:
        before_stats: Output of ``collect_before_stats()``.
        step_reports: Merged dict of all step report dicts.
        after_stats: Output of ``collect_after_stats()``.
        is_manifold: Result of ``check_manifold()``.
        is_watertight: Result of ``check_watertight()``.
        cleanup_time: Total pipeline execution time in seconds.
        step_errors: List of ``{"step": str, "error": str}`` dicts.

    Returns:
        Complete diagnostics dict per FR-007.

    Implements: FR-007.
    """
    from .data_types import empty_diagnostics

    diag = empty_diagnostics()

    # Before stats
    diag["vertices_before"] = before_stats.get("vertices_before", 0)
    diag["faces_before"] = before_stats.get("faces_before", 0)

    # After stats
    diag["vertices_after"] = after_stats.get("vertices_after", 0)
    diag["faces_after"] = after_stats.get("faces_after", 0)

    # Step reports
    diag["doubles_removed"] = step_reports.get("doubles_removed", 0)
    diag["degenerate_faces_removed"] = step_reports.get("degenerate_faces_removed", 0)
    diag["normals_flipped"] = step_reports.get("normals_flipped", 0)
    diag["holes_filled"] = step_reports.get("holes_filled", 0)
    diag["holes_skipped"] = step_reports.get("holes_skipped", 0)
    diag["voxel_remesh_applied"] = step_reports.get("voxel_remesh_applied", False)
    diag["quad_remesh_applied"] = step_reports.get("quad_remesh_applied", False)
    diag["decimate_applied"] = step_reports.get("decimate_applied", False)

    # Validation
    diag["is_manifold"] = is_manifold
    diag["is_watertight"] = is_watertight
    diag["cleanup_time_seconds"] = cleanup_time

    # Errors
    diag["step_errors"] = step_errors

    return diag
