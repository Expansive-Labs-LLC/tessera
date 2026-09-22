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

"""Edit operations registry for mesh refinement.

Maps ``OperationType`` enum values to their handler functions.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-019.
"""

from __future__ import annotations

from typing import Callable

from ..intent_schema import EditResult, OperationType
from .primitive_op import execute_add_geometry, execute_remove_geometry
from .scale_op import execute_scale
from .smooth_op import execute_bevel, execute_sharpen, execute_smooth
from .solidify_op import execute_solidify
from .transform_op import execute_move, execute_rotate
from .undo_op import execute_redo, execute_undo

#: Registry mapping operation types to handler functions.
#: Each handler has signature:
#:   (context, obj, parameters, vertex_group_name) -> EditResult
#: Except UNDO/REDO which also accept undo_manager= kwarg.
OPERATION_HANDLERS: dict[OperationType, Callable[..., EditResult]] = {
    OperationType.SCALE: execute_scale,
    OperationType.MOVE: execute_move,
    OperationType.ROTATE: execute_rotate,
    OperationType.SOLIDIFY: execute_solidify,
    OperationType.SMOOTH: execute_smooth,
    OperationType.SHARPEN: execute_sharpen,
    OperationType.BEVEL: execute_bevel,
    OperationType.ADD_GEOMETRY: execute_add_geometry,
    OperationType.REMOVE_GEOMETRY: execute_remove_geometry,
    OperationType.UNDO: execute_undo,
    OperationType.REDO: execute_redo,
}

__all__ = [
    "OPERATION_HANDLERS",
    "execute_add_geometry",
    "execute_bevel",
    "execute_move",
    "execute_redo",
    "execute_remove_geometry",
    "execute_rotate",
    "execute_scale",
    "execute_sharpen",
    "execute_smooth",
    "execute_solidify",
    "execute_undo",
]
