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

"""Undo/redo operations for mesh refinement.

Delegates to the UndoManager for snapshot-based undo/redo.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-029.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..intent_schema import EditResult

logger = logging.getLogger("tessera.refinement")


def execute_undo(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
    undo_manager: Any = None,
) -> EditResult:
    """Execute an undo operation.

    FR-029: Restores the mesh to the previous snapshot, or to a
    specific version if ``target_version`` is provided (FR-033).

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: Optional ``target_version`` (int) for
            version-addressed undo (FR-033).
        vertex_group_name: Not used.
        undo_manager: The ``UndoManager`` instance.

    Returns:
        ``EditResult``.
    """
    if undo_manager is None:
        return EditResult(
            success=False,
            description="Undo manager not available",
        )

    start = time.perf_counter()
    target_version = parameters.get("target_version")

    try:
        if target_version is not None:
            # FR-033: Version-addressed undo.
            from_version = undo_manager.current_version
            undo_manager.goto_version(obj, int(target_version))
            elapsed = time.perf_counter() - start
            return EditResult(
                success=True,
                description=(
                    f"Restored to version {target_version} "
                    f"(from version {from_version})"
                ),
                vertices_modified=len(obj.data.vertices),
                execution_time_seconds=elapsed,
            )
        else:
            from_version = undo_manager.current_version
            undo_manager.undo(obj)
            to_version = undo_manager.current_version
            elapsed = time.perf_counter() - start
            return EditResult(
                success=True,
                description=(f"Undone (version {from_version} → {to_version})"),
                vertices_modified=len(obj.data.vertices),
                execution_time_seconds=elapsed,
            )
    except Exception as exc:
        return EditResult(
            success=False,
            description=f"Undo failed: {exc}",
            execution_time_seconds=time.perf_counter() - start,
        )


def execute_redo(
    context: Any,
    obj: Any,
    parameters: dict[str, Any],
    vertex_group_name: str,
    undo_manager: Any = None,
) -> EditResult:
    """Execute a redo operation.

    FR-029: Re-applies the most recently undone operation.

    Args:
        context: Blender context.
        obj: Target mesh object.
        parameters: Not used.
        vertex_group_name: Not used.
        undo_manager: The ``UndoManager`` instance.

    Returns:
        ``EditResult``.
    """
    if undo_manager is None:
        return EditResult(
            success=False,
            description="Undo manager not available",
        )

    start = time.perf_counter()

    try:
        from_version = undo_manager.current_version
        undo_manager.redo(obj)
        to_version = undo_manager.current_version
        elapsed = time.perf_counter() - start
        return EditResult(
            success=True,
            description=(f"Redone (version {from_version} → {to_version})"),
            vertices_modified=len(obj.data.vertices),
            execution_time_seconds=elapsed,
        )
    except Exception as exc:
        return EditResult(
            success=False,
            description=f"Redo failed: {exc}",
            execution_time_seconds=time.perf_counter() - start,
        )
