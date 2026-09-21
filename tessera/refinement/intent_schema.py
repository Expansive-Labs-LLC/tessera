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

"""Data models for the natural-language refinement loop.

Defines the core data structures used across the refinement pipeline:
``OperationType``, ``EditIntent``, ``AmbiguityResponse``, ``RegionResult``,
``EditResult``, and parameter validation utilities.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-007, FR-008, FR-044, SEC-004.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("tessera.refinement")


class OperationType(enum.Enum):
    """Supported edit operation types.

    Implements: FR-007.
    """

    SCALE = "SCALE"
    MOVE = "MOVE"
    ROTATE = "ROTATE"
    SOLIDIFY = "SOLIDIFY"
    SMOOTH = "SMOOTH"
    SHARPEN = "SHARPEN"
    BEVEL = "BEVEL"
    ADD_GEOMETRY = "ADD_GEOMETRY"
    REMOVE_GEOMETRY = "REMOVE_GEOMETRY"
    UNDO = "UNDO"
    REDO = "REDO"


@dataclass
class EditIntent:
    """A structured edit intent parsed from natural language.

    Attributes:
        operation: The edit operation to perform.
        target_region: Target region name (part name or spatial descriptor).
        parameters: Operation-specific key-value pairs.
        confidence: Parser confidence score (0.0–1.0).
        raw_response: Raw LLM response text for debugging.

    Implements: FR-007.
    """

    operation: OperationType
    target_region: str = "all"
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    raw_response: str = ""


@dataclass
class AmbiguityResponse:
    """Response when intent parsing confidence is below threshold.

    Attributes:
        candidates: List of (operation_description, confidence) tuples,
            sorted by confidence descending. Up to 3 candidates.
        original_command: The user's original text command.

    Implements: FR-017.
    """

    candidates: list[tuple[str, float]] = field(default_factory=list)
    original_command: str = ""


@dataclass
class RegionResult:
    """Result of resolving a target region name to a vertex selection.

    Attributes:
        method: Resolution method used — ``"vertex_group"``,
            ``"spatial_heuristic"``, or ``"user_selection"``.
        vertex_group_name: Name of the vertex group used or created.
        vertex_count: Number of vertices in the selection.
        confidence: Resolution confidence (1.0 for exact matches).

    Implements: FR-013.
    """

    method: str = ""
    vertex_group_name: str = ""
    vertex_count: int = 0
    confidence: float = 1.0


@dataclass
class EditResult:
    """Result of executing an edit operation.

    Attributes:
        success: Whether the operation completed successfully.
        description: Human-readable summary of what was done.
        vertices_modified: Number of vertices affected.
        execution_time_seconds: Wall-clock execution time.
        warning: Optional warning message (e.g., parameter clamping).

    Implements: FR-019.
    """

    success: bool = False
    description: str = ""
    vertices_modified: int = 0
    execution_time_seconds: float = 0.0
    warning: Optional[str] = None


# ---------------------------------------------------------------------------
# FR-044 / SEC-004: Parameter range table and validation
# ---------------------------------------------------------------------------

#: Parameter range definitions per operation type.
#: Each entry maps a parameter name to (min, max, default).
PARAMETER_RANGES: dict[str, dict[str, tuple[float, float, float]]] = {
    "SCALE": {
        "factor": (0.01, 100.0, 1.0),
    },
    "MOVE": {
        "distance": (0.0, 1000.0, 0.0),
    },
    "ROTATE": {
        "angle_degrees": (-360.0, 360.0, 0.0),
    },
    "SOLIDIFY": {
        "thickness_mm": (0.1, 50.0, 2.0),
        "offset": (-1.0, 1.0, -1.0),
    },
    "SMOOTH": {
        "iterations": (1, 100, 5),
        "factor": (0.0, 1.0, 0.5),
    },
    "SHARPEN": {
        "angle_threshold_degrees": (0, 180, 30),
    },
    "BEVEL": {
        "width_mm": (0.1, 20.0, 1.0),
        "segments": (1, 10, 2),
    },
    "ADD_GEOMETRY": {
        "size_mm": (0.1, 500.0, 10.0),
    },
}

#: FR-008: Default percentage mappings for dimensionless adjectives.
DIMENSIONLESS_DEFAULTS: dict[str, float] = {
    "taller": 10.0,
    "bigger": 10.0,
    "wider": 10.0,
    "longer": 10.0,
    "thicker": 10.0,
    "shorter": -10.0,
    "smaller": -10.0,
    "narrower": -10.0,
    "thinner": -10.0,
}


def clamp_parameters(
    operation: OperationType,
    parameters: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Validate and clamp edit parameters to allowed ranges.

    Args:
        operation: The operation type to validate against.
        parameters: Mutable dict of parameter key-value pairs.

    Returns:
        Tuple of (clamped parameters dict, list of warning messages).
        Warning messages follow the format from FR-044:
        ``"Parameter '{name}' was {value}, clamped to {clamped_value}
        (allowed range: {min}–{max})."``

    Implements: FR-044, SEC-004.
    """
    ranges = PARAMETER_RANGES.get(operation.value, {})
    warnings: list[str] = []
    clamped = dict(parameters)

    for param_name, (min_val, max_val, _default) in ranges.items():
        if param_name not in clamped:
            continue

        value = clamped[param_name]
        if not isinstance(value, (int, float)):
            continue

        if value < min_val:
            warnings.append(
                f"Parameter '{param_name}' was {value}, clamped to "
                f"{min_val} (allowed range: {min_val}–{max_val})."
            )
            clamped[param_name] = type(value)(min_val)
        elif value > max_val:
            warnings.append(
                f"Parameter '{param_name}' was {value}, clamped to "
                f"{max_val} (allowed range: {min_val}–{max_val})."
            )
            clamped[param_name] = type(value)(max_val)

    return clamped, warnings
