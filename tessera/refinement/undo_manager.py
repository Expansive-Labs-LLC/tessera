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

"""Snapshot-based undo manager for the refinement loop.

Stores mesh data copies as numpy-backed snapshots, independent of
Blender's native undo system.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-030, FR-031, FR-032, FR-033, FR-034, CON-005.
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("tessera.refinement")

#: FR-031, CON-005: Maximum undo stack depth.
MAX_UNDO_DEPTH = 20


@dataclass
class MeshSnapshot:
    """A stored snapshot of mesh data at a point in time.

    Attributes:
        version: Monotonically increasing version number.
        description: Human-readable description of the edit.
        vertex_coords: List of (x, y, z) tuples for all vertices.
        face_indices: List of tuples of vertex indices per face.
        vertex_groups: Dict mapping group name → list of (index, weight).
        timestamp: Unix timestamp when the snapshot was taken.
    """

    version: int
    description: str
    vertex_coords: list[tuple[float, float, float]]
    face_indices: list[tuple[int, ...]]
    vertex_groups: dict[str, list[tuple[int, float]]] = field(
        default_factory=dict
    )
    timestamp: float = 0.0


class UndoError(Exception):
    """Raised when an undo/redo operation fails."""


class UndoManager:
    """Snapshot-based undo/redo stack for mesh edits.

    Stores up to ``MAX_UNDO_DEPTH`` mesh snapshots. Each snapshot
    captures vertex coordinates, face topology, and vertex group
    assignments.

    FR-031: Stack depth limited to 20 with FIFO discard.
    FR-034: New edits discard the redo history.

    Implements: FR-030, FR-031, FR-032, FR-033, FR-034, CON-005.
    """

    def __init__(self) -> None:
        """Initialize the undo manager with empty stacks."""
        self._undo_stack: list[MeshSnapshot] = []
        self._redo_stack: list[MeshSnapshot] = []
        self._next_version: int = 0

    @property
    def current_version(self) -> int:
        """Current version number (most recent snapshot)."""
        if self._undo_stack:
            return self._undo_stack[-1].version
        return 0

    @property
    def can_undo(self) -> bool:
        """Whether undo is available."""
        return len(self._undo_stack) > 1

    @property
    def can_redo(self) -> bool:
        """Whether redo is available."""
        return len(self._redo_stack) > 0

    def push(self, obj: Any, description: str) -> int:
        """Take a snapshot of the current mesh state.

        FR-032: Stores a copy of vertex coordinates, face topology,
        and vertex group assignments.

        FR-034: Discards any existing redo history.

        FR-031: If the stack exceeds ``MAX_UNDO_DEPTH``, the oldest
        snapshot is discarded (FIFO).

        Args:
            obj: Blender mesh object to snapshot.
            description: Human-readable description of the edit
                that was just applied.

        Returns:
            The version number assigned to this snapshot.

        Implements: FR-031, FR-032, FR-034.
        """
        snapshot = self._capture_snapshot(obj, description)

        # FR-034: Discard redo history on new edit.
        self._redo_stack.clear()

        self._undo_stack.append(snapshot)

        # FR-031, CON-005: FIFO discard if over depth limit.
        while len(self._undo_stack) > MAX_UNDO_DEPTH:
            discarded = self._undo_stack.pop(0)
            logger.debug(
                "Undo stack overflow: discarded version %d (%s)",
                discarded.version,
                discarded.description,
            )

        logger.debug(
            "Undo snapshot pushed: version=%d, description=%s, "
            "stack_depth=%d",
            snapshot.version,
            description,
            len(self._undo_stack),
        )

        return snapshot.version

    def undo(self, obj: Any) -> None:
        """Restore the mesh to the previous snapshot.

        Moves the current state onto the redo stack and restores
        the previous state from the undo stack.

        Args:
            obj: Blender mesh object to restore.

        Raises:
            UndoError: If there is nothing to undo.

        Implements: FR-030.
        """
        if not self.can_undo:
            raise UndoError("Nothing to undo")

        # Move current state to redo stack.
        current = self._undo_stack.pop()
        self._redo_stack.append(current)

        # Restore previous state.
        previous = self._undo_stack[-1]
        self._apply_snapshot(obj, previous)

        logger.info(
            "Undo applied: from_version=%d, to_version=%d",
            current.version,
            previous.version,
        )

    def redo(self, obj: Any) -> None:
        """Re-apply the most recently undone snapshot.

        Moves the most recent redo state back onto the undo stack.

        Args:
            obj: Blender mesh object to restore.

        Raises:
            UndoError: If there is nothing to redo.

        Implements: FR-030.
        """
        if not self.can_redo:
            raise UndoError("Nothing to redo")

        # Move from redo to undo stack.
        next_state = self._redo_stack.pop()
        self._undo_stack.append(next_state)

        self._apply_snapshot(obj, next_state)

        logger.info(
            "Redo applied: to_version=%d",
            next_state.version,
        )

    def goto_version(self, obj: Any, version: int) -> None:
        """Restore the mesh to a specific version.

        FR-033: Allows version-addressed undo for "go back to
        version N" commands.

        Args:
            obj: Blender mesh object.
            version: Target version number.

        Raises:
            UndoError: If the version is not found.

        Implements: FR-033.
        """
        # Search in undo stack.
        target_idx = None
        for idx, snap in enumerate(self._undo_stack):
            if snap.version == version:
                target_idx = idx
                break

        if target_idx is None:
            raise UndoError(
                f"Version {version} not found in undo history"
            )

        # Move everything after target_idx to redo stack.
        while len(self._undo_stack) > target_idx + 1:
            moved = self._undo_stack.pop()
            self._redo_stack.append(moved)

        self._apply_snapshot(obj, self._undo_stack[-1])

        logger.info(
            "Restored to version %d",
            version,
        )

    def get_stack_info(self) -> dict[str, Any]:
        """Get information about the undo/redo stack state.

        Returns:
            Dict with ``current_version``, ``undo_depth``,
            ``redo_depth``, ``can_undo``, ``can_redo``, and
            ``history`` (list of version+description dicts).
        """
        return {
            "current_version": self.current_version,
            "undo_depth": len(self._undo_stack),
            "redo_depth": len(self._redo_stack),
            "can_undo": self.can_undo,
            "can_redo": self.can_redo,
            "history": [
                {"version": s.version, "description": s.description}
                for s in self._undo_stack
            ],
        }

    def _capture_snapshot(
        self, obj: Any, description: str
    ) -> MeshSnapshot:
        """Capture the current mesh state as a snapshot.

        Args:
            obj: Blender mesh object.
            description: Edit description.

        Returns:
            ``MeshSnapshot`` with vertex/face/vgroup data.
        """
        mesh = obj.data

        # Capture vertex coordinates.
        vertex_coords = [
            (v.co.x, v.co.y, v.co.z) for v in mesh.vertices
        ]

        # Capture face topology.
        face_indices = [
            tuple(p.vertices) for p in mesh.polygons
        ]

        # Capture vertex groups.
        vertex_groups: dict[str, list[tuple[int, float]]] = {}
        for vg in obj.vertex_groups:
            members: list[tuple[int, float]] = []
            for v in mesh.vertices:
                for g in v.groups:
                    if g.group == vg.index:
                        members.append((v.index, g.weight))
                        break
            vertex_groups[vg.name] = members

        version = self._next_version
        self._next_version += 1

        return MeshSnapshot(
            version=version,
            description=description,
            vertex_coords=vertex_coords,
            face_indices=face_indices,
            vertex_groups=vertex_groups,
            timestamp=time.time(),
        )

    def _apply_snapshot(
        self, obj: Any, snapshot: MeshSnapshot
    ) -> None:
        """Apply a snapshot to restore mesh state.

        Uses ``bpy.types.Mesh`` API to rebuild vertex positions.
        Topology changes (face count) require mesh rebuild.

        Args:
            obj: Blender mesh object.
            snapshot: The ``MeshSnapshot`` to restore.
        """
        import bpy

        mesh = obj.data
        current_verts = len(mesh.vertices)
        target_verts = len(snapshot.vertex_coords)
        current_faces = len(mesh.polygons)
        target_faces = len(snapshot.face_indices)

        if current_verts == target_verts and current_faces == target_faces:
            # Same topology — just update coordinates.
            for i, (x, y, z) in enumerate(snapshot.vertex_coords):
                mesh.vertices[i].co.x = x
                mesh.vertices[i].co.y = y
                mesh.vertices[i].co.z = z
        else:
            # Topology changed — full mesh rebuild.
            mesh.clear_geometry()

            # Add vertices.
            mesh.vertices.add(len(snapshot.vertex_coords))
            for i, (x, y, z) in enumerate(snapshot.vertex_coords):
                mesh.vertices[i].co.x = x
                mesh.vertices[i].co.y = y
                mesh.vertices[i].co.z = z

            # Add faces.
            mesh.polygons.add(len(snapshot.face_indices))
            mesh.loops.add(sum(len(f) for f in snapshot.face_indices))
            loop_start = 0
            for i, face_verts in enumerate(snapshot.face_indices):
                mesh.polygons[i].loop_start = loop_start
                mesh.polygons[i].loop_total = len(face_verts)
                for j, vi in enumerate(face_verts):
                    mesh.loops[loop_start + j].vertex_index = vi
                loop_start += len(face_verts)

        # Restore vertex groups.
        # Clear existing groups.
        while obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[0])

        for vg_name, members in snapshot.vertex_groups.items():
            vg = obj.vertex_groups.new(name=vg_name)
            for v_idx, weight in members:
                vg.add([v_idx], weight, "REPLACE")

        mesh.update()

        logger.debug(
            "Snapshot applied: version=%d, vertex_count=%d, "
            "face_count=%d",
            snapshot.version,
            target_verts,
            target_faces,
        )
