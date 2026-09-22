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

"""Local LLM backend using llama-cpp-python for GGUF model inference.

Loads the intent-parser model via the model weight management system
(SPEC-TS-0002) and runs inference locally.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-009a, FR-010.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .base import LLMBackend, LLMBackendError

logger = logging.getLogger("tessera.refinement")


class LocalLLMBackend(LLMBackend):
    """Local GGUF model inference backend via ``llama-cpp-python``.

    The model is loaded on first use via ``ensure_model()`` from the
    model weight management system (SPEC-TS-0002). This call occurs
    within the LLM inference background thread, consistent with
    SPEC-TS-0002's threading contract (FR-010).

    Implements: FR-009a, FR-010.
    """

    def __init__(self) -> None:
        """Initialize the local LLM backend."""
        self._model: Any = None
        self._model_path: Optional[str] = None

    def _ensure_loaded(self) -> None:
        """Load the LLM model if not already loaded.

        Uses ``ensure_model("tessera-intent-parser")`` from
        SPEC-TS-0002 to download/cache model weights, then
        initializes ``llama_cpp.Llama``.

        This MUST be called from a background thread (FR-010).

        Raises:
            LLMBackendError: If the model cannot be loaded.
        """
        if self._model is not None:
            return

        try:
            from llama_cpp import Llama
        except ImportError:
            raise LLMBackendError(
                "llama-cpp-python is not installed. The local LLM "
                "backend requires llama-cpp-python >= 0.2.0. "
                "Switch to the API backend in Preferences → Tessera "
                "→ LLM Backend, or install llama-cpp-python."
            )

        # FR-010: Load model via SPEC-TS-0002 weight management.
        try:
            from ...models.download_manager import get_global_download_manager

            dm = get_global_download_manager()
            if dm is None:
                raise LLMBackendError(
                    "Model management system not initialized. "
                    "Ensure the Tessera add-on is properly registered."
                )
            model_path = dm.ensure_model("tessera-intent-parser")
            self._model_path = str(model_path)
        except Exception as exc:
            raise LLMBackendError(f"Failed to load intent parser model: {exc}") from exc

        # Initialize the Llama model.
        try:
            self._model = Llama(
                model_path=self._model_path,
                n_ctx=2048,
                n_threads=4,
                verbose=False,
            )
        except Exception as exc:
            raise LLMBackendError(f"Failed to initialize Llama model: {exc}") from exc

        logger.info(
            "Local LLM model loaded: path=%s",
            self._model_path,
        )

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        """Generate a completion using the local GGUF model.

        Args:
            system_prompt: System prompt with operation definitions
                and mesh context.
            messages: Conversation history.

        Returns:
            Raw text response from the model.

        Raises:
            LLMBackendError: If inference fails.

        Implements: FR-009a.
        """
        self._ensure_loaded()

        # Build prompt in chat format.
        chat_messages = [{"role": "system", "content": system_prompt}]
        chat_messages.extend(messages)

        try:
            response = self._model.create_chat_completion(
                messages=chat_messages,
                max_tokens=512,
                temperature=0.1,
            )
            content = response["choices"][0]["message"]["content"]
            return content.strip() if content else ""
        except Exception as exc:
            raise LLMBackendError(f"Local LLM inference failed: {exc}") from exc

    def is_available(self) -> bool:
        """Check if the local backend can be used.

        Returns:
            ``True`` if ``llama-cpp-python`` is importable.
        """
        try:
            import llama_cpp  # noqa: F401

            return True
        except ImportError:
            return False
