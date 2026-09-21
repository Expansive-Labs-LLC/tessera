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

"""Abstract LLM backend interface for intent parsing.

Defines the pluggable backend contract used by ``IntentParser``.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-009.
"""

from __future__ import annotations

import abc
from typing import Any


class LLMBackend(abc.ABC):
    """Abstract base class for LLM inference backends.

    Subclasses provide either local model inference or remote API
    access. All implementations must be safe to call from a
    background thread (CON-002: no ``bpy`` access).

    Implements: FR-009.
    """

    @abc.abstractmethod
    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        """Generate a completion from the LLM.

        Args:
            system_prompt: The system prompt containing operation
                definitions, mesh context, and output format.
            messages: Conversation history as a list of
                ``{"role": "user"|"assistant", "content": str}`` dicts.

        Returns:
            Raw text response from the LLM.

        Raises:
            LLMBackendError: If inference fails.
        """

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check whether this backend is ready for inference.

        Returns:
            ``True`` if the backend can generate completions.
        """


class LLMBackendError(Exception):
    """Raised when an LLM backend fails to generate a response."""
