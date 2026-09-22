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

"""HTTP API LLM backend for user-provided API keys.

Supports OpenAI-compatible HTTP endpoints via ``httpx``.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-009b, SEC-001, SEC-003, SEC-006, CON-001.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import LLMBackend, LLMBackendError

logger = logging.getLogger("tessera.refinement")


def _mask_api_key(key: str) -> str:
    """Mask an API key for safe logging.

    SEC-003: Only shows the last 4 characters.

    Args:
        key: The API key to mask.

    Returns:
        Masked key string, e.g., ``"sk-****abcd"``.
    """
    if len(key) <= 4:
        return "****"
    return f"sk-****{key[-4:]}"


class APILLMBackend(LLMBackend):
    """HTTP API backend for OpenAI-compatible LLM endpoints.

    Sends only: system prompt text, user command text, and message
    history text. Never transmits mesh geometry, file paths, image
    data, or PII (CON-001, SEC-001).

    Implements: FR-009b, SEC-001, SEC-003, SEC-006, CON-001.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model_name: str = "gpt-4",
    ) -> None:
        """Initialize the API backend.

        Args:
            endpoint: The API endpoint URL (must be HTTPS).
            api_key: The API key for authentication.
            model_name: The model name to use in API requests.

        Raises:
            LLMBackendError: If the endpoint is not HTTPS (SEC-006).
        """
        # SEC-006: Enforce HTTPS-only.
        if not endpoint.startswith("https://"):
            raise LLMBackendError("API endpoints must use HTTPS for security.")

        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._model_name = model_name

    def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
    ) -> str:
        """Generate a completion via the remote API.

        The request body contains only the system prompt, user
        command text, and message history text. No mesh data,
        file paths, or images are transmitted (CON-001, SEC-001).

        Args:
            system_prompt: System prompt with operation definitions
                and mesh context (bounding box + vertex group names only).
            messages: Conversation history (text only).

        Returns:
            Raw text response from the API.

        Raises:
            LLMBackendError: If the API request fails.

        Implements: FR-009b, SEC-001, CON-001.
        """
        try:
            import httpx
        except ImportError:
            raise LLMBackendError(
                "httpx is not installed. The API LLM backend requires "
                "httpx >= 0.27.0. Switch to the local backend in "
                "Preferences → Tessera → LLM Backend, or install httpx."
            )

        if not self._api_key:
            raise LLMBackendError(
                "API key not configured. Enter your API key in "
                "Preferences → Tessera → LLM Backend."
            )

        # Build request body — text only (SEC-001, CON-001).
        chat_messages = [{"role": "system", "content": system_prompt}]
        chat_messages.extend(messages)

        request_body: dict[str, Any] = {
            "model": self._model_name,
            "messages": chat_messages,
            "max_tokens": 512,
            "temperature": 0.1,
        }

        # SEC-003: Log endpoint without API key.
        logger.debug(
            "LLM API request sent: endpoint=%s, request_size_bytes=%d",
            self._endpoint.split("/")[2] if "/" in self._endpoint else self._endpoint,
            len(str(request_body)),
        )

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self._endpoint}/chat/completions",
                    json=request_body,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
        except Exception as exc:
            # SEC-003: Mask API key in error messages.
            error_msg = str(exc)
            if self._api_key in error_msg:
                error_msg = error_msg.replace(
                    self._api_key, _mask_api_key(self._api_key)
                )
            raise LLMBackendError(f"API request failed: {error_msg}") from exc

        data = response.json()

        logger.debug(
            "LLM API response received: response_time_seconds=%.2f, " "token_count=%s",
            response.elapsed.total_seconds() if hasattr(response, "elapsed") else 0.0,
            data.get("usage", {}).get("total_tokens", "N/A"),
        )

        try:
            content = data["choices"][0]["message"]["content"]
            return content.strip() if content else ""
        except (KeyError, IndexError) as exc:
            raise LLMBackendError(f"Unexpected API response format: {exc}") from exc

    def is_available(self) -> bool:
        """Check if the API backend is configured.

        Returns:
            ``True`` if endpoint and API key are set and httpx
            is importable.
        """
        if not self._api_key or not self._endpoint:
            return False
        try:
            import httpx  # noqa: F401

            return True
        except ImportError:
            return False
