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

"""Error category, severity enumerations and catalog entry dataclass.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-002.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ErrorCategory(Enum):
    """Classification category for Tessera errors.

    Implements: FR-002.
    """

    VRAM = "VRAM"
    INPUT = "INPUT"
    MODEL = "MODEL"
    EXPORT = "EXPORT"
    BLENDER = "BLENDER"
    SYSTEM = "SYSTEM"


class ErrorSeverity(Enum):
    """Severity level for Tessera errors.

    Implements: FR-002.
    """

    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ErrorCatalogEntry:
    """A structured error definition in the Tessera error catalog.

    Attributes:
        code: Error code in format ``"BF-EXXX"``.
        message: User-facing error message (≥20 characters).
        severity: Severity level for UI reporting.
        category: Classification category for grouping.
        resolution_steps: List of concrete actions the user can take.

    Implements: FR-002.
    """

    code: str
    message: str
    severity: ErrorSeverity
    category: ErrorCategory
    resolution_steps: list[str] = field(default_factory=list)


@dataclass
class ErrorResult:
    """Result returned by ``ErrorHandler.catch()``.

    Attributes:
        code: The matched error code (e.g., ``"BF-E001"``).
        user_message: Formatted user-facing message.
        severity: The error's severity level.
        resolution_steps: List of resolution actions.
        logged: Whether the error was successfully logged.

    Implements: §10.1 ErrorHandler API.
    """

    code: str
    user_message: str
    severity: ErrorSeverity
    resolution_steps: list[str] = field(default_factory=list)
    logged: bool = False
