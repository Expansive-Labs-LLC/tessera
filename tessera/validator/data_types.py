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

"""Data types for the print-readiness validator.

Defines enums and dataclasses used across the validator and export
pipeline.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-028 (CheckResult structure).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(Enum):
    """Status of a single validation check.

    Implements: FR-028.
    """

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class CheckResult:
    """Result of a single validation check.

    Attributes:
        check_name: Human-readable name of the check.
        status: One of ``PASS``, ``WARN``, ``FAIL``.
        message: Human-readable description of the result.
        details: Check-specific data (face counts, measurements, etc.).
        repaired: Whether auto-repair was applied.
        repair_message: Description of the repair action, or ``None``.

    Implements: FR-028.
    """

    check_name: str
    status: CheckStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    repaired: bool = False
    repair_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict.

        Returns:
            Dict matching the FR-028 schema.
        """
        return {
            "check_name": self.check_name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "repaired": self.repaired,
            "repair_message": self.repair_message,
        }


@dataclass
class RepairResult:
    """Result of an auto-repair attempt.

    Attributes:
        success: Whether the repair resolved the issue.
        message: Description of the repair action or failure reason.
    """

    success: bool
    message: str


@dataclass
class ExportResult:
    """Result of the export pipeline execution.

    Attributes:
        report: The validation report generated during export.
        exported_files: Absolute paths to exported files.
        success: ``True`` if exported (no failures or ``force_export``).

    Implements: §10.2 API contract.
    """

    report: Any  # ValidationReport — forward reference to avoid circular import
    exported_files: list[str] = field(default_factory=list)
    success: bool = False
