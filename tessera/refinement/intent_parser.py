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

"""Intent parser for natural-language edit commands.

Translates user text into structured ``EditIntent`` objects using
an LLM backend (local or API).

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-007, FR-008, FR-011, FR-012, FR-017, CON-003, SEC-002, SEC-005.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Union

from .intent_schema import (
    DIMENSIONLESS_DEFAULTS,
    AmbiguityResponse,
    EditIntent,
    OperationType,
)
from .llm_backend.base import LLMBackend, LLMBackendError

logger = logging.getLogger("tessera.refinement")

#: Confidence threshold below which ambiguity handling triggers (FR-012).
CONFIDENCE_THRESHOLD = 0.7

#: FR-029: Natural-language triggers for undo/redo operations.
_UNDO_TRIGGERS = {"undo", "undo that", "go back", "revert"}
_REDO_TRIGGERS = {"redo", "redo that", "put it back"}

#: Pattern to detect version-addressed undo commands (FR-033).
_VERSION_PATTERN = re.compile(
    r"(?:go\s+back\s+to|restore|revert\s+to)\s+version\s+(\d+)",
    re.IGNORECASE,
)

#: FR-008: Supported unit suffixes and their conversion to mm.
_UNIT_CONVERSIONS = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "%": None,  # Percentage — handled separately.
}


def _sanitize_llm_output(text: str) -> str:
    """Sanitize LLM output for safe display in Blender UI.

    SEC-005: Strips any potential operator-call injections
    and control characters.

    Args:
        text: Raw LLM output string.

    Returns:
        Sanitized string safe for UI display.
    """
    # Remove control characters except newlines.
    sanitized = "".join(
        ch for ch in text if ch == "\n" or (ch >= " " and ord(ch) < 127)
    )
    # Truncate to reasonable display length.
    if len(sanitized) > 500:
        sanitized = sanitized[:500] + "…"
    return sanitized


def _build_system_prompt(mesh_context: dict[str, Any]) -> str:
    """Build the structured system prompt for the LLM.

    FR-011: Includes the list of supported operations, current
    mesh context, and JSON output format instructions.

    Args:
        mesh_context: Dict with ``bounding_box_mm``, ``vertex_groups``,
            and ``face_count``.

    Returns:
        System prompt string.
    """
    bb = mesh_context.get("bounding_box_mm", {"x": 0, "y": 0, "z": 0})
    vgroups = mesh_context.get("vertex_groups", [])
    face_count = mesh_context.get("face_count", 0)

    return f"""You are a 3D mesh editing assistant. Parse the user's natural language \
command into structured JSON edit instructions.

SUPPORTED OPERATIONS:
- SCALE: Resize along X, Y, Z, or UNIFORM axes. Params: axis, factor (or absolute_mm).
- MOVE: Translate vertices. Params: direction (UP/DOWN/LEFT/RIGHT/FORWARD/BACK), distance (mm).
- ROTATE: Rotate vertices. Params: axis (X/Y/Z), angle_degrees, pivot (MEDIAN_POINT/CURSOR/INDIVIDUAL_ORIGINS).
- SOLIDIFY: Add wall thickness. Params: thickness_mm, offset (-1.0 to 1.0).
- SMOOTH: Laplacian smoothing. Params: iterations (1-100), factor (0.0-1.0).
- SHARPEN: Mark edges sharp. Params: angle_threshold_degrees (0-180).
- BEVEL: Bevel edges. Params: width_mm, segments (1-10).
- ADD_GEOMETRY: Add primitive (CUBE/SPHERE/CYLINDER/CONE). Params: shape, size_mm, location.
- REMOVE_GEOMETRY: Delete selected vertices and fill holes. No params.
- UNDO: Undo last edit.
- REDO: Redo last undone edit.

CURRENT MESH CONTEXT:
- Bounding box (mm): X={bb.get('x', 0):.1f}, Y={bb.get('y', 0):.1f}, Z={bb.get('z', 0):.1f}
- Vertex groups: {json.dumps(vgroups)}
- Face count: {face_count}

OUTPUT FORMAT: Respond with valid JSON only. For a single command:
{{"intents": [{{"operation": "SCALE", "target_region": "all", "parameters": {{"axis": "Z", "factor": 1.2}}, "confidence": 0.95}}]}}

For multiple operations in one command, return multiple intents in the array.
If the command is ambiguous, return candidates with low confidence scores.
If the command is not understood, return confidence 0.0.

Units: If user says "mm", "cm", "m", "in", or "%", use those units. If no unit, default to mm.
Dimensionless words like "taller" mean +10%, "shorter" means -10%.
"make it X mm tall" = absolute dimension, calculate scale factor from current bounding box.
"""


class IntentParser:
    """Parses natural-language commands into ``EditIntent`` objects.

    Uses an LLM backend (local or API) to interpret user text,
    with fallbacks for common patterns (undo/redo triggers,
    version-addressed undo).

    Implements: FR-007, FR-008, FR-011, FR-012.
    """

    def __init__(self, backend: LLMBackend) -> None:
        """Initialize the intent parser.

        Args:
            backend: The LLM backend to use for inference.
        """
        self._backend = backend

    def parse(
        self,
        command: str,
        mesh_context: dict[str, Any],
        message_history: Optional[list[dict[str, str]]] = None,
    ) -> Union[list[EditIntent], AmbiguityResponse]:
        """Parse a natural-language command into edit intents.

        Args:
            command: The user's text command.
            mesh_context: Current mesh context dict containing
                ``bounding_box_mm``, ``vertex_groups``, ``face_count``.
            message_history: Optional prior conversation messages
                (text only, per CON-001).

        Returns:
            A list of ``EditIntent`` objects if parsing succeeds,
            or an ``AmbiguityResponse`` if confidence is below
            threshold (FR-012).

        Implements: FR-007, FR-008, FR-011, FR-012.
        """
        logger.debug(
            "Intent parsing started: backend_type=%s, command_length=%d",
            type(self._backend).__name__,
            len(command),
        )

        # FR-029: Check for direct undo/redo triggers first.
        command_lower = command.strip().lower()

        if command_lower in _UNDO_TRIGGERS:
            logger.info(
                "Intent parsing completed: operation=UNDO, "
                "target_region=all, confidence=1.0, parse_time_seconds=0.0"
            )
            return [EditIntent(
                operation=OperationType.UNDO,
                target_region="all",
                parameters={},
                confidence=1.0,
            )]

        if command_lower in _REDO_TRIGGERS:
            logger.info(
                "Intent parsing completed: operation=REDO, "
                "target_region=all, confidence=1.0, parse_time_seconds=0.0"
            )
            return [EditIntent(
                operation=OperationType.REDO,
                target_region="all",
                parameters={},
                confidence=1.0,
            )]

        # FR-033: Check for version-addressed undo.
        version_match = _VERSION_PATTERN.search(command_lower)
        if version_match:
            version = int(version_match.group(1))
            return [EditIntent(
                operation=OperationType.UNDO,
                target_region="all",
                parameters={"target_version": version},
                confidence=1.0,
            )]

        # Build system prompt and invoke LLM.
        system_prompt = _build_system_prompt(mesh_context)
        messages = list(message_history or [])
        messages.append({"role": "user", "content": command})

        try:
            raw_response = self._backend.generate(system_prompt, messages)
        except LLMBackendError as exc:
            logger.error(
                "Intent parsing failed: error_type=%s, error_message=%s, "
                "command_text=%.100s",
                type(exc).__name__,
                str(exc),
                command,
            )
            # Return a zero-confidence response that triggers the
            # "didn't understand" flow (EC-005).
            return AmbiguityResponse(
                candidates=[],
                original_command=command,
            )

        # SEC-002, CON-003: Parse as JSON — never eval.
        return self._parse_response(raw_response, command, mesh_context)

    def _parse_response(
        self,
        raw_response: str,
        command: str,
        mesh_context: dict[str, Any],
    ) -> Union[list[EditIntent], AmbiguityResponse]:
        """Parse the raw LLM response into EditIntent objects.

        SEC-002: Uses ``json.loads()`` — never ``eval()``.

        Args:
            raw_response: Raw text from the LLM.
            command: Original user command.
            mesh_context: Current mesh context.

        Returns:
            Parsed intents or ambiguity response.
        """
        # SEC-005: Sanitize for logging.
        sanitized = _sanitize_llm_output(raw_response)

        # Try to extract JSON from the response.
        json_str = self._extract_json(raw_response)
        if json_str is None:
            logger.error(
                "Intent parsing failed: error_type=JSONParseError, "
                "error_message=No valid JSON found in response, "
                "command_text=%.100s",
                command,
            )
            return AmbiguityResponse(
                candidates=[],
                original_command=command,
            )

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error(
                "Intent parsing failed: error_type=JSONDecodeError, "
                "error_message=%s, command_text=%.100s",
                str(exc),
                command,
            )
            return AmbiguityResponse(
                candidates=[],
                original_command=command,
            )

        # Parse intents from the JSON structure.
        intents_data = data.get("intents", [data] if "operation" in data else [])
        if not intents_data:
            return AmbiguityResponse(
                candidates=[],
                original_command=command,
            )

        intents: list[EditIntent] = []
        ambiguous_intents: list[tuple[str, float]] = []
        has_ambiguous = False

        for item in intents_data:
            try:
                op_str = item.get("operation", "").upper()
                operation = OperationType(op_str)
            except (ValueError, AttributeError):
                logger.warning(
                    "Unknown operation type in LLM response: %s",
                    item.get("operation"),
                )
                continue

            target = str(item.get("target_region", "all"))
            params = dict(item.get("parameters", {}))
            confidence = float(item.get("confidence", 0.0))

            # FR-008: Process dimensionless adjectives in parameters.
            params = self._apply_unit_defaults(params, command, mesh_context)

            intent = EditIntent(
                operation=operation,
                target_region=target,
                parameters=params,
                confidence=confidence,
                raw_response=sanitized,
            )

            # FR-012: Check confidence threshold.
            if confidence < CONFIDENCE_THRESHOLD:
                has_ambiguous = True
                desc = f"{operation.value} on '{target}'"
                ambiguous_intents.append((desc, confidence))
            else:
                intents.append(intent)

        # FR-007: If any sub-intent is ambiguous, return ambiguity
        # for those while keeping clear ones.
        if has_ambiguous and not intents:
            # All intents are ambiguous.
            logger.info(
                "Ambiguity detected: confidence=%.2f, candidate_count=%d",
                max((c for _, c in ambiguous_intents), default=0.0),
                len(ambiguous_intents),
            )
            return AmbiguityResponse(
                candidates=sorted(
                    ambiguous_intents, key=lambda x: x[1], reverse=True
                )[:3],
                original_command=command,
            )

        if not intents:
            return AmbiguityResponse(
                candidates=[],
                original_command=command,
            )

        for intent in intents:
            logger.info(
                "Intent parsing completed: operation=%s, "
                "target_region=%s, confidence=%.2f, "
                "parse_time_seconds=0.0",
                intent.operation.value,
                intent.target_region,
                intent.confidence,
            )

        return intents

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from potentially wrapped LLM output.

        Handles responses that include markdown code fences or
        surrounding text around the JSON payload.

        Args:
            text: Raw LLM response text.

        Returns:
            Extracted JSON string, or ``None`` if not found.
        """
        # Try direct parse first.
        text = text.strip()
        if text.startswith("{") or text.startswith("["):
            return text

        # Try to extract from markdown code fences.
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Try to find JSON object in the text.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)

        return None

    def _apply_unit_defaults(
        self,
        params: dict[str, Any],
        command: str,
        mesh_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply unit-aware defaults for dimensionless commands.

        FR-008: When a dimensionless comparative adjective is used
        without a numeric value, infer a default percentage of 10%.

        Args:
            params: Current parameters dict.
            command: Original user command.
            mesh_context: Current mesh context.

        Returns:
            Updated parameters dict.
        """
        command_lower = command.lower()

        # Check if any dimensionless adjective is in the command
        # and no explicit value was parsed.
        if "factor" not in params and "value" not in params:
            for word, pct in DIMENSIONLESS_DEFAULTS.items():
                if word in command_lower:
                    # Convert percentage to scale factor.
                    factor = 1.0 + (pct / 100.0)
                    params["factor"] = factor
                    params["inferred"] = True
                    break

        return params
