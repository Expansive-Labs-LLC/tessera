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

"""Chat session manager for the refinement loop.

Manages message history, session state, and image data block
lifecycle for the chat UI.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-001, FR-002, FR-042.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("tessera.refinement")

#: FR-042: Maximum message history length.
MAX_HISTORY_LENGTH = 200


@dataclass
class ChatMessage:
    """A single chat message in the refinement session.

    Attributes:
        role: ``"user"``, ``"assistant"``, or ``"system"``.
        text: Display text content.
        image_name: Optional name of a ``bpy.data.images`` data block
            for preview thumbnails (FR-003).
        version: Optional undo version number associated with this
            message (FR-030).
        timestamp: Unix timestamp when the message was created.
    """

    role: str
    text: str
    image_name: Optional[str] = None
    version: Optional[int] = None
    timestamp: float = field(default_factory=time.time)


class ChatManager:
    """Manages the chat message history and session state.

    Provides FIFO message management with a 200-message limit
    (FR-042). When old messages are discarded, associated preview
    image data blocks are also cleaned up.

    Implements: FR-001, FR-002, FR-042.
    """

    def __init__(self) -> None:
        """Initialize an empty chat session."""
        self._messages: list[ChatMessage] = []
        self._session_active: bool = False

    @property
    def is_active(self) -> bool:
        """Whether a refinement session is currently active."""
        return self._session_active

    @property
    def message_count(self) -> int:
        """Number of messages in history."""
        return len(self._messages)

    def start_session(self) -> None:
        """Start a new refinement session.

        Clears any existing message history.
        """
        self._messages.clear()
        self._session_active = True
        logger.info("Refinement session started")

    def end_session(self) -> None:
        """End the current refinement session.

        Preserves message history for review.
        """
        self._session_active = False
        logger.info(
            "Refinement session ended: message_count=%d",
            len(self._messages),
        )

    def add_message(
        self,
        role: str,
        text: str,
        image_name: Optional[str] = None,
        version: Optional[int] = None,
    ) -> ChatMessage:
        """Add a message to the chat history.

        FR-042: If the history exceeds ``MAX_HISTORY_LENGTH``,
        the oldest messages are removed (FIFO), and any associated
        preview image data blocks are cleaned up.

        Args:
            role: ``"user"``, ``"assistant"``, or ``"system"``.
            text: Display text content.
            image_name: Optional image data block name.
            version: Optional associated undo version.

        Returns:
            The created ``ChatMessage``.
        """
        msg = ChatMessage(
            role=role,
            text=text,
            image_name=image_name,
            version=version,
        )
        self._messages.append(msg)

        # FR-042: FIFO cleanup.
        while len(self._messages) > MAX_HISTORY_LENGTH:
            old = self._messages.pop(0)
            if old.image_name:
                self._cleanup_image(old.image_name)
            logger.debug(
                "Message history overflow: removed oldest " "message (role=%s)",
                old.role,
            )

        return msg

    def get_messages(self) -> list[ChatMessage]:
        """Get all messages in the history.

        Returns:
            List of ``ChatMessage`` objects in chronological order.
        """
        return list(self._messages)

    def get_llm_history(self) -> list[dict[str, str]]:
        """Get message history formatted for LLM context.

        Returns only user and assistant messages, text-only
        (CON-001: no image data sent to LLM).

        Returns:
            List of ``{"role": str, "content": str}`` dicts.
        """
        return [
            {"role": msg.role, "content": msg.text}
            for msg in self._messages
            if msg.role in ("user", "assistant")
        ]

    def clear(self) -> None:
        """Clear all message history and clean up images.

        Removes all associated preview image data blocks.
        """
        for msg in self._messages:
            if msg.image_name:
                self._cleanup_image(msg.image_name)

        self._messages.clear()
        logger.debug("Chat history cleared")

    def _cleanup_image(self, image_name: str) -> None:
        """Remove a preview image data block.

        Args:
            image_name: Name of the ``bpy.data.images`` entry.
        """
        try:
            import bpy

            img = bpy.data.images.get(image_name)
            if img is not None:
                bpy.data.images.remove(img)
                logger.debug(
                    "Cleaned up preview image: %s",
                    image_name,
                )
        except Exception:
            pass  # bpy may not be available (e.g., in tests).
