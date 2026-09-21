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

"""Auto-dimension inference from object class labels.

Uses a JSON lookup table (``dimension_defaults.json``) to suggest
real-world dimensions for recognized object classes.  Unknown classes
receive a low-confidence fallback.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-007–FR-012, SEC-002, SEC-003.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Callable, Dict, Optional

from .dimension_input import DimensionSpec, DimensionSuggestion

logger = logging.getLogger("tessera.scaling")

# SEC-002: Allowed characters in object class labels.
_LABEL_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_\- ]")

# Hardcoded fallback defaults if JSON is malformed (SEC-003).
_HARDCODED_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "mug": {"primary_axis": "height", "min_mm": 80, "max_mm": 100},
    "vase": {"primary_axis": "height", "min_mm": 150, "max_mm": 250},
    "figurine": {"primary_axis": "height", "min_mm": 50, "max_mm": 150},
    "phone_case": {"primary_axis": "height", "min_mm": 140, "max_mm": 160},
    "bottle": {"primary_axis": "height", "min_mm": 200, "max_mm": 300},
    "bowl": {"primary_axis": "diameter", "min_mm": 150, "max_mm": 200},
    "box": {"primary_axis": "width", "min_mm": 100, "max_mm": 200},
}

# FR-011: Generic fallback height for unrecognized object classes.
_FALLBACK_HEIGHT_MM = 100.0


def _sanitize_label(label: str) -> str:
    """Sanitize an object class label.

    Strips characters not matching ``[a-zA-Z0-9_\\- ]`` and
    converts to lowercase for lookup.

    Args:
        label: Raw object class label.

    Returns:
        Sanitized, lowercase label string.

    Implements: SEC-002.
    """
    sanitized = _LABEL_SANITIZE_RE.sub("", label)
    return sanitized.strip().lower()


def _load_defaults() -> Dict[str, Dict[str, Any]]:
    """Load dimension defaults from JSON file.

    Falls back to hardcoded defaults if the JSON file is missing,
    malformed, or contains unexpected types.

    Returns:
        Dict mapping object class labels to dimension ranges.

    Implements: FR-012, SEC-003.
    """
    json_path = os.path.join(os.path.dirname(__file__), "dimension_defaults.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # SEC-003: Validate structure.
        if not isinstance(data, dict):
            raise TypeError(
                f"Expected dict at top level, got {type(data).__name__}"
            )

        for key, value in data.items():
            if not isinstance(key, str):
                raise TypeError(f"Expected str key, got {type(key).__name__}")
            if not isinstance(value, dict):
                raise TypeError(
                    f"Expected dict value for '{key}', "
                    f"got {type(value).__name__}"
                )
            for field in ("primary_axis", "min_mm", "max_mm"):
                if field not in value:
                    raise KeyError(
                        f"Missing required field '{field}' in entry '{key}'"
                    )

        logger.debug(
            "Loaded dimension defaults from %s (%d entries)",
            json_path,
            len(data),
        )
        return data

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        TypeError,
        KeyError,
    ) as exc:
        logger.error(
            "Failed to load dimension defaults from %s: %s. "
            "Using hardcoded fallback defaults.",
            json_path,
            exc,
        )
        return _HARDCODED_DEFAULTS.copy()


class AutoDimensionInfer:
    """Auto-dimension inference engine.

    Looks up object class labels in a JSON table and returns
    ``DimensionSuggestion`` results that require user confirmation
    before application.

    Attributes:
        _defaults: Loaded dimension defaults table.
        on_confirm: Optional callback invoked when the user confirms
            the suggested dimensions.

    Implements: FR-007–FR-012.
    """

    def __init__(
        self,
        on_confirm: Optional[Callable[[DimensionSpec], None]] = None,
    ) -> None:
        self._defaults = _load_defaults()
        self.on_confirm = on_confirm

    def infer(self, object_class: str) -> DimensionSuggestion:
        """Infer dimensions for a given object class.

        Args:
            object_class: Raw object class label (e.g. ``"mug"``).

        Returns:
            ``DimensionSuggestion`` with inferred dimensions and
            confidence level.  Always requires user confirmation.

        Implements: FR-007–FR-011.
        """
        # SEC-002: Sanitize label.
        label = _sanitize_label(object_class)

        logger.info(
            "Auto-inference requested for object class '%s' "
            "(sanitized: '%s')",
            object_class,
            label,
        )

        entry = self._defaults.get(label)

        if entry is None:
            # FR-011: Unknown class — low-confidence fallback.
            suggestion = DimensionSuggestion(
                suggested_height_mm=_FALLBACK_HEIGHT_MM,
                confidence="low",
                message=(
                    f"Object class '{label}' not recognized. Please "
                    f"specify target dimensions manually or confirm "
                    f"the {_FALLBACK_HEIGHT_MM:.0f} mm height default."
                ),
                requires_confirmation=True,
            )
            logger.info(
                "Unknown object class '%s': returning low-confidence "
                "fallback (height=%.0f mm)",
                label,
                _FALLBACK_HEIGHT_MM,
            )
            return suggestion

        # FR-008: Compute midpoint of the dimension range.
        min_mm = float(entry["min_mm"])
        max_mm = float(entry["max_mm"])
        midpoint = (min_mm + max_mm) / 2.0
        primary_axis = entry.get("primary_axis", "height")

        # Build suggestion based on primary axis.
        suggestion = DimensionSuggestion(
            confidence="high",
            message=(
                f"Object class '{label}' recognized. Suggested "
                f"{primary_axis}: {midpoint:.0f} mm "
                f"(range: {min_mm:.0f}–{max_mm:.0f} mm)."
            ),
            requires_confirmation=True,
        )

        if primary_axis == "height":
            suggestion.suggested_height_mm = midpoint
        elif primary_axis == "width":
            suggestion.suggested_width_mm = midpoint
        elif primary_axis == "diameter":
            # Diameter maps to width (X axis).
            suggestion.suggested_width_mm = midpoint
        else:
            suggestion.suggested_height_mm = midpoint

        logger.info(
            "Auto-inference for '%s': %s=%.0f mm, confidence=%s",
            label,
            primary_axis,
            midpoint,
            suggestion.confidence,
        )

        return suggestion

    def confirm(self, dimension_spec: DimensionSpec) -> None:
        """Invoke the confirmation callback with user-approved dimensions.

        Args:
            dimension_spec: The confirmed dimension spec.

        Implements: FR-010.
        """
        if self.on_confirm is not None:
            self.on_confirm(dimension_spec)
            logger.info("User confirmed auto-inferred dimensions: %s", dimension_spec)
