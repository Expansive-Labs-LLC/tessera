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

"""Region resolver for mapping target names to vertex selections.

Uses a three-tier fallback strategy: named vertex groups, spatial
heuristics, and user click-selection.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-013, FR-014, FR-015, FR-016, FR-043, EC-002, EC-003, EC-006.
"""

from __future__ import annotations

import difflib
import logging
from typing import Any, Optional

from .intent_schema import RegionResult

logger = logging.getLogger("tessera.refinement")

#: FR-015: Fuzzy match threshold for named vertex groups.
FUZZY_MATCH_THRESHOLD = 0.80

#: EC-006: Minimum vertex count for edit operations.
MIN_VERTEX_COUNT = 3

#: FR-014: Spatial heuristic region mappings.
#: Each entry maps region name(s) to an axis, range_start, range_end
#: (as fractions of the bounding box extent on that axis).
SPATIAL_HEURISTICS: dict[str, tuple[str, float, float]] = {
    "base": ("Z", 0.0, 0.2),
    "bottom": ("Z", 0.0, 0.2),
    "top": ("Z", 0.8, 1.0),
    "middle": ("Z", 0.3, 0.7),
    "center": ("Z", 0.3, 0.7),
    "left": ("X", 0.0, 0.5),
    "right": ("X", 0.5, 1.0),
    "front": ("Y", 0.5, 1.0),
    "back": ("Y", 0.0, 0.5),
}

#: FR-014: Whole-mesh aliases.
_WHOLE_MESH_ALIASES = {"all", "whole", "entire"}


class RegionResolver:
    """Resolves target region names to vertex group selections.

    Three-tier fallback strategy (FR-013):
      1. Named vertex groups — exact or fuzzy match (FR-015).
      2. Spatial heuristics — predefined spatial rules (FR-014).
      3. User click-selection — prompt for manual selection (FR-016).

    Implements: FR-013, FR-014, FR-015, FR-016, FR-043, EC-006.
    """

    def resolve(
        self,
        target_region: str,
        obj: Any,
    ) -> RegionResult:
        """Resolve a target region name to a vertex selection.

        Args:
            target_region: The region name from the ``EditIntent``
                (e.g., ``"base"``, ``"handle"``, ``"top"``).
            obj: The Blender mesh object (``bpy.types.Object``).

        Returns:
            ``RegionResult`` with the resolution method and details.
            If the region cannot be resolved automatically, the
            result will have ``method="user_selection"`` indicating
            the user must be prompted (FR-016).

        Implements: FR-013, FR-043.
        """
        region_lower = target_region.strip().lower()

        logger.debug(
            "Region resolution started: region_name=%s, "
            "vertex_group_count=%d",
            region_lower,
            len(obj.vertex_groups) if hasattr(obj, "vertex_groups") and obj.vertex_groups else 0,
        )

        # FR-014: Whole-mesh aliases.
        if region_lower in _WHOLE_MESH_ALIASES:
            vertex_count = self._get_total_vertex_count(obj)
            logger.debug(
                "Region resolved: method=whole_mesh, "
                "vertex_count=%d, region_name=%s",
                vertex_count,
                region_lower,
            )
            return RegionResult(
                method="spatial_heuristic",
                vertex_group_name="_bf_all",
                vertex_count=vertex_count,
                confidence=1.0,
            )

        # Tier 1: Named vertex group match (FR-015, FR-043).
        vg_result = self._try_vertex_group_match(region_lower, obj)
        if vg_result is not None:
            return vg_result

        # Tier 2: Spatial heuristics (FR-014).
        spatial_result = self._try_spatial_heuristic(region_lower, obj)
        if spatial_result is not None:
            return spatial_result

        # Tier 3: User click-selection fallback (FR-016).
        logger.info(
            "Region resolution failed: region_name=%s, "
            "fallback_triggered=user_selection",
            region_lower,
        )
        return RegionResult(
            method="user_selection",
            vertex_group_name="",
            vertex_count=0,
            confidence=0.0,
        )

    def _try_vertex_group_match(
        self,
        region_lower: str,
        obj: Any,
    ) -> Optional[RegionResult]:
        """Attempt to match region name to a named vertex group.

        FR-043: Operates without assuming vertex groups exist.
        FR-015: Uses ``difflib.SequenceMatcher`` with 80% threshold.

        Args:
            region_lower: Lowercased region name.
            obj: Blender mesh object.

        Returns:
            ``RegionResult`` if a match is found, ``None`` otherwise.
        """
        # FR-043: Handle meshes with zero vertex groups.
        if not hasattr(obj, "vertex_groups") or not obj.vertex_groups:
            return None

        vgroup_names = [vg.name for vg in obj.vertex_groups]
        if not vgroup_names:
            return None

        # Try exact match first.
        for name in vgroup_names:
            if name.lower() == region_lower:
                vertex_count = self._count_vgroup_vertices(obj, name)
                logger.debug(
                    "Region resolved: method=vertex_group, "
                    "vertex_count=%d, region_name=%s",
                    vertex_count,
                    name,
                )
                return RegionResult(
                    method="vertex_group",
                    vertex_group_name=name,
                    vertex_count=vertex_count,
                    confidence=1.0,
                )

        # FR-015: Fuzzy match.
        best_match = None
        best_ratio = 0.0

        for name in vgroup_names:
            ratio = difflib.SequenceMatcher(
                None, region_lower, name.lower()
            ).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = name

        if best_match is not None and best_ratio >= FUZZY_MATCH_THRESHOLD:
            vertex_count = self._count_vgroup_vertices(obj, best_match)
            logger.debug(
                "Region resolved: method=vertex_group (fuzzy %.0f%%), "
                "vertex_count=%d, region_name=%s",
                best_ratio * 100,
                vertex_count,
                best_match,
            )
            return RegionResult(
                method="vertex_group",
                vertex_group_name=best_match,
                vertex_count=vertex_count,
                confidence=best_ratio,
            )

        return None

    def _try_spatial_heuristic(
        self,
        region_lower: str,
        obj: Any,
    ) -> Optional[RegionResult]:
        """Attempt to resolve using spatial heuristic mappings.

        FR-014: Maps common terms to mesh regions based on the
        local bounding box.

        Args:
            region_lower: Lowercased region name.
            obj: Blender mesh object.

        Returns:
            ``RegionResult`` if a heuristic matches, ``None`` otherwise.
        """
        heuristic = SPATIAL_HEURISTICS.get(region_lower)
        if heuristic is None:
            return None

        axis, range_start, range_end = heuristic

        # Count vertices in the spatial range.
        vertex_count = self._count_spatial_vertices(
            obj, axis, range_start, range_end
        )

        # EC-006: Check minimum vertex count.
        if vertex_count < MIN_VERTEX_COUNT:
            logger.debug(
                "Region resolved but too few vertices: "
                "method=spatial_heuristic, vertex_count=%d, "
                "region_name=%s (min=%d)",
                vertex_count,
                region_lower,
                MIN_VERTEX_COUNT,
            )
            return RegionResult(
                method="spatial_heuristic",
                vertex_group_name=f"_bf_spatial_{region_lower}",
                vertex_count=vertex_count,
                confidence=1.0,
            )

        logger.debug(
            "Region resolved: method=spatial_heuristic, "
            "vertex_count=%d, region_name=%s",
            vertex_count,
            region_lower,
        )
        return RegionResult(
            method="spatial_heuristic",
            vertex_group_name=f"_bf_spatial_{region_lower}",
            vertex_count=vertex_count,
            confidence=1.0,
        )

    def _get_total_vertex_count(self, obj: Any) -> int:
        """Get total vertex count of the mesh.

        Args:
            obj: Blender mesh object.

        Returns:
            Number of vertices.
        """
        try:
            return len(obj.data.vertices)
        except (AttributeError, TypeError):
            return 0

    def _count_vgroup_vertices(self, obj: Any, vgroup_name: str) -> int:
        """Count vertices in a named vertex group.

        Args:
            obj: Blender mesh object.
            vgroup_name: Vertex group name.

        Returns:
            Number of vertices in the group.
        """
        try:
            vg_index = obj.vertex_groups[vgroup_name].index
            count = 0
            for v in obj.data.vertices:
                for g in v.groups:
                    if g.group == vg_index:
                        count += 1
                        break
            return count
        except (AttributeError, KeyError, TypeError):
            return 0

    def _count_spatial_vertices(
        self,
        obj: Any,
        axis: str,
        range_start: float,
        range_end: float,
    ) -> int:
        """Count vertices in a spatial bounding box range.

        FR-014: Selects vertices based on their position relative
        to the mesh's local bounding box.

        Args:
            obj: Blender mesh object.
            axis: ``"X"``, ``"Y"``, or ``"Z"``.
            range_start: Start of range as fraction (0.0–1.0).
            range_end: End of range as fraction (0.0–1.0).

        Returns:
            Number of vertices in the range.
        """
        try:
            axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]
            verts = obj.data.vertices

            if not verts:
                return 0

            # Compute bounding box extent on the axis.
            coords = [v.co[axis_idx] for v in verts]
            min_val = min(coords)
            max_val = max(coords)
            extent = max_val - min_val

            if extent <= 0:
                return len(verts) if range_start == 0.0 and range_end == 1.0 else 0

            threshold_min = min_val + extent * range_start
            threshold_max = min_val + extent * range_end

            count = sum(
                1 for c in coords
                if threshold_min <= c <= threshold_max
            )
            return count
        except (AttributeError, TypeError, KeyError):
            return 0

    def create_selection_from_spatial(
        self,
        obj: Any,
        region_name: str,
    ) -> Optional[str]:
        """Create a temporary vertex group from spatial heuristics.

        Used by the edit executor to apply operations to spatially
        resolved regions.

        Args:
            obj: Blender mesh object.
            region_name: The spatial region name (e.g., ``"top"``).

        Returns:
            Vertex group name if created, ``None`` if no heuristic matches.
        """
        import bpy

        heuristic = SPATIAL_HEURISTICS.get(region_name.lower())
        if heuristic is None and region_name.lower() in _WHOLE_MESH_ALIASES:
            # Select all vertices.
            vg_name = "_bf_all"
            if vg_name not in obj.vertex_groups:
                vg = obj.vertex_groups.new(name=vg_name)
                indices = [v.index for v in obj.data.vertices]
                vg.add(indices, 1.0, "REPLACE")
            return vg_name

        if heuristic is None:
            return None

        axis, range_start, range_end = heuristic
        axis_idx = {"X": 0, "Y": 1, "Z": 2}[axis]

        vg_name = f"_bf_spatial_{region_name.lower()}"

        # Remove old temp group if exists.
        if vg_name in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[vg_name])

        vg = obj.vertex_groups.new(name=vg_name)

        verts = obj.data.vertices
        coords = [v.co[axis_idx] for v in verts]
        min_val = min(coords) if coords else 0
        max_val = max(coords) if coords else 0
        extent = max_val - min_val

        if extent > 0:
            threshold_min = min_val + extent * range_start
            threshold_max = min_val + extent * range_end
            indices = [
                v.index for v, c in zip(verts, coords)
                if threshold_min <= c <= threshold_max
            ]
            if indices:
                vg.add(indices, 1.0, "REPLACE")

        return vg_name

    def create_user_selection_group(self, obj: Any) -> str:
        """Create a vertex group from the user's current selection.

        EC-003: Creates a temporary vertex group named
        ``"_bf_user_selection"`` from currently selected vertices.

        Args:
            obj: Blender mesh object (in edit mode or with selection).

        Returns:
            Vertex group name.
        """
        import bpy

        vg_name = "_bf_user_selection"

        # Remove old user selection group if exists.
        if vg_name in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[vg_name])

        vg = obj.vertex_groups.new(name=vg_name)

        # Get selected vertices (requires object mode to read selection).
        selected = [v.index for v in obj.data.vertices if v.select]
        if selected:
            vg.add(selected, 1.0, "REPLACE")

        return vg_name
