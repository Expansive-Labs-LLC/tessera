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

"""Validation check: non-manifold edge detection and repair.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-001, FR-002.
"""

from __future__ import annotations

import logging
from typing import Any

import bmesh

from ..data_types import CheckResult, CheckStatus, RepairResult
from .base import BaseCheck

logger = logging.getLogger("tessera.validator")

# FR-002: Maximum boundary loop size for triangle fill repair.
_MAX_FILL_LOOP_EDGES = 500


class ManifoldCheck(BaseCheck):
    """Detect and repair non-manifold edges.

    Non-manifold edges include boundary edges (1 face), wire edges
    (0 faces), and edges shared by more than 2 faces.

    Implements: FR-001, FR-002.
    """

    @property
    def name(self) -> str:
        """Human-readable check name."""
        return "Non-Manifold Edges"

    def check(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> CheckResult:
        """Detect non-manifold edges using ``bmesh``.

        Args:
            obj: ``bpy.types.Object`` with mesh data.
            settings: Validator settings dict.

        Returns:
            ``CheckResult`` with non-manifold edge count in details.

        Implements: FR-001.
        """
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.edges.ensure_lookup_table()

            non_manifold = [e for e in bm.edges if not e.is_manifold]
            count = len(non_manifold)
        finally:
            bm.free()

        if count == 0:
            return CheckResult(
                check_name=self.name,
                status=CheckStatus.PASS,
                message="No non-manifold edges detected.",
                details={"non_manifold_edge_count": 0},
            )

        return CheckResult(
            check_name=self.name,
            status=CheckStatus.FAIL,
            message=f"{count} non-manifold edge(s) detected.",
            details={"non_manifold_edge_count": count},
        )

    def repair(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> RepairResult:
        """Auto-repair non-manifold edges.

        Strategy:
        1. Merge vertices within configurable distance using
           ``bmesh.ops.remove_doubles()``.
        2. Fill boundary holes with ``bmesh.ops.triangle_fill()``
           for loops with ≤ 500 edges.

        Args:
            obj: ``bpy.types.Object`` (the ``_print`` duplicate).
            settings: Validator settings dict.

        Returns:
            ``RepairResult`` with success status and description.

        Implements: FR-002.
        """
        merge_dist = settings.get("merge_distance", 0.0001)

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)

            # Step (a): Merge close vertices.
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)

            # Step (b): Fill boundary holes.
            bm.edges.ensure_lookup_table()
            boundary_edges = [e for e in bm.edges if e.is_boundary]

            # Group boundary edges into loops by walking connected edges.
            filled_holes = 0
            visited: set[int] = set()

            for edge in boundary_edges:
                if edge.index in visited:
                    continue

                # Walk the boundary loop.
                loop_edges: list = []
                loop_verts: list = []
                current = edge
                start_vert = edge.verts[0]
                current_vert = start_vert

                while True:
                    if current.index in visited:
                        break
                    visited.add(current.index)
                    loop_edges.append(current)
                    loop_verts.append(current_vert)

                    # Find next boundary edge.
                    other_vert = (
                        current.verts[1]
                        if current.verts[0] == current_vert
                        else current.verts[0]
                    )
                    current_vert = other_vert

                    if current_vert == start_vert:
                        break

                    next_edge = None
                    for linked in current_vert.link_edges:
                        if linked.is_boundary and linked.index not in visited:
                            next_edge = linked
                            break

                    if next_edge is None:
                        break
                    current = next_edge

                # Fill if loop is closed and within size limit.
                if (
                    len(loop_edges) >= 3
                    and len(loop_edges) <= _MAX_FILL_LOOP_EDGES
                    and current_vert == start_vert
                ):
                    try:
                        bmesh.ops.triangle_fill(bm, use_beauty=True, edges=loop_edges)
                        filled_holes += 1
                    except Exception:
                        logger.debug(
                            "Failed to fill boundary loop with %d edges",
                            len(loop_edges),
                        )

            bm.to_mesh(obj.data)
        finally:
            bm.free()

        obj.data.update()

        msg = (
            f"Merged vertices within {merge_dist}m. "
            f"Filled {filled_holes} boundary hole(s)."
        )
        logger.info("Auto-repair (manifold): %s", msg)

        return RepairResult(success=True, message=msg)
