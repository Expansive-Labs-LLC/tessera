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

"""Natural-Language Refinement Loop package for Tessera.

Provides the four-layer architecture for plain-English mesh editing:

1. **Chat UI** — User-facing chat panel in the 3D Viewport sidebar.
2. **Intent Parser** — LLM-based NL-to-structured-intent translation.
3. **Region Resolver** — Maps target region names to vertex selections.
4. **Edit Executor** — Dispatches safe ``bpy.ops`` sequences.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)
"""

from .chat_manager import ChatManager, ChatMessage
from .edit_executor import EditExecutor
from .intent_parser import IntentParser
from .intent_schema import (
    AmbiguityResponse,
    EditIntent,
    EditResult,
    OperationType,
    RegionResult,
)
from .preview_renderer import PreviewRenderer
from .region_resolver import RegionResolver
from .undo_manager import UndoManager

__all__ = [
    "AmbiguityResponse",
    "ChatManager",
    "ChatMessage",
    "EditExecutor",
    "EditIntent",
    "EditResult",
    "IntentParser",
    "OperationType",
    "PreviewRenderer",
    "RegionResolver",
    "RegionResult",
    "UndoManager",
]
