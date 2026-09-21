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

"""UI error reporter for surfacing errors in Blender's interface.

Shows errors in the Info area via ``self.report()`` and maintains
a scrollable error log in a dedicated sidebar panel.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-005, FR-006.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .categories import ErrorSeverity

logger = logging.getLogger("tessera.errors")

# FR-006: Maximum number of entries in the error log.
_MAX_ERROR_LOG_SIZE = 50

# Severity → Blender report level mapping (FR-005).
_SEVERITY_TO_REPORT_LEVEL = {
    ErrorSeverity.CRITICAL: "ERROR",
    ErrorSeverity.ERROR: "ERROR",
    ErrorSeverity.WARNING: "WARNING",
    ErrorSeverity.INFO: "INFO",
}

# Severity → icon mapping for the error panel.
_SEVERITY_ICONS = {
    ErrorSeverity.CRITICAL: "CANCEL",
    ErrorSeverity.ERROR: "ERROR",
    ErrorSeverity.WARNING: "ERROR",
    ErrorSeverity.INFO: "INFO",
}


@dataclass
class ErrorLogEntry:
    """A single entry in the error log.

    Attributes:
        timestamp: Unix timestamp when the error occurred.
        code: Error code (e.g., ``"BF-E001"``).
        severity: Error severity level.
        message: User-facing error message.
        resolution_steps: List of resolution actions.
        expanded: Whether the entry is expanded in the UI.
    """

    timestamp: float
    code: str
    severity: ErrorSeverity
    message: str
    resolution_steps: list[str] = field(default_factory=list)
    expanded: bool = False

    @property
    def timestamp_str(self) -> str:
        """Format timestamp as HH:MM:SS."""
        return time.strftime("%H:%M:%S", time.localtime(self.timestamp))

    @property
    def truncated_message(self) -> str:
        """Truncate message to 80 characters for list display."""
        if len(self.message) <= 80:
            return self.message
        return self.message[:77] + "..."


class UIReporter:
    """Reports errors to the Blender UI.

    Maintains a log of the last 50 errors (FR-006) and provides
    methods for showing errors in the Info area (FR-005).

    Implements: FR-005, FR-006.
    """

    def __init__(self) -> None:
        self._error_log: deque[ErrorLogEntry] = deque(maxlen=_MAX_ERROR_LOG_SIZE)

    @property
    def error_log(self) -> list[ErrorLogEntry]:
        """Return the error log as a list (most recent first)."""
        return list(reversed(self._error_log))

    @property
    def error_count(self) -> int:
        """Return the total number of errors in the log."""
        return len(self._error_log)

    def show(
        self,
        code: str,
        message: str,
        severity: ErrorSeverity,
        resolution_steps: Optional[list[str]] = None,
        operator: Optional[object] = None,
    ) -> None:
        """Show an error in Blender's UI and append to the log.

        Args:
            code: Error code (e.g., ``"BF-E001"``).
            message: Formatted user-facing message.
            severity: Error severity level.
            resolution_steps: Optional resolution steps list.
            operator: Optional Blender operator instance for
                ``self.report()`` calls.

        Implements: FR-005, FR-006.
        """
        if resolution_steps is None:
            resolution_steps = []

        # FR-006: Append to error log.
        entry = ErrorLogEntry(
            timestamp=time.time(),
            code=code,
            severity=severity,
            message=message,
            resolution_steps=resolution_steps,
        )
        self._error_log.append(entry)

        # FR-005: Report to Blender Info area if operator provided.
        if operator is not None:
            report_level = _SEVERITY_TO_REPORT_LEVEL.get(severity, "ERROR")
            try:
                operator.report({report_level}, message)
            except Exception:
                logger.debug("operator.report() failed", exc_info=True)

        logger.debug(
            "Error reported to UI: code=%s, severity=%s, log_size=%d",
            code,
            severity.value,
            len(self._error_log),
        )

    def clear(self) -> None:
        """Clear the error log."""
        self._error_log.clear()

    def get_icon(self, severity: ErrorSeverity) -> str:
        """Get the Blender icon name for a severity level.

        Args:
            severity: Error severity level.

        Returns:
            Blender icon identifier string.
        """
        return _SEVERITY_ICONS.get(severity, "INFO")


# Global UIReporter instance — initialized during add-on registration.
_global_reporter: Optional[UIReporter] = None


def get_global_reporter() -> Optional[UIReporter]:
    """Get the global UIReporter instance."""
    return _global_reporter


def set_global_reporter(reporter: Optional[UIReporter]) -> None:
    """Set the global UIReporter instance."""
    global _global_reporter
    _global_reporter = reporter
