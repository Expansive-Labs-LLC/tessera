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

"""Validation report generation for the print-readiness validator.

Produces JSON and human-readable reports from validation check results.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-028, FR-029, FR-030, FR-032.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .data_types import CheckResult, CheckStatus

logger = logging.getLogger("tessera.validator")


class ValidationReport:
    """Aggregates validation check results into a structured report.

    Attributes:
        object_name: Name of the validated object.
        printer_type: Printer profile used for validation.
        checks: Ordered list of ``CheckResult`` instances.
        validation_time_seconds: Wall-clock time for all checks.
        export_time_seconds: Wall-clock time for export (0 if no export).

    Implements: FR-028, FR-029, FR-030, FR-032.
    """

    def __init__(
        self,
        object_name: str,
        printer_type: str = "FDM",
    ) -> None:
        self.object_name = object_name
        self.printer_type = printer_type
        self.checks: list[CheckResult] = []
        self.validation_time_seconds: float = 0.0
        self.export_time_seconds: float = 0.0
        self._timestamp = datetime.now(timezone.utc).isoformat()

    def add_check(self, result: CheckResult) -> None:
        """Add a check result to the report.

        Args:
            result: The ``CheckResult`` to append.
        """
        self.checks.append(result)

    @property
    def passed(self) -> int:
        """Count of checks with ``PASS`` status."""
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)

    @property
    def warnings(self) -> int:
        """Count of checks with ``WARN`` status."""
        return sum(1 for c in self.checks if c.status == CheckStatus.WARN)

    @property
    def failures(self) -> int:
        """Count of checks with ``FAIL`` status."""
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)

    @property
    def auto_repairs_applied(self) -> int:
        """Count of checks where auto-repair was applied."""
        return sum(1 for c in self.checks if c.repaired)

    @property
    def has_failures(self) -> bool:
        """``True`` if any check has ``FAIL`` status."""
        return self.failures > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full report to a JSON-compatible dict.

        Returns:
            Dict matching FR-028 and FR-032 schema.

        Implements: FR-028, FR-032.
        """
        return {
            "object_name": self.object_name,
            "timestamp": self._timestamp,
            "printer_type": self.printer_type,
            "checks": [c.to_dict() for c in self.checks],
            "summary": {
                "total_checks": len(self.checks),
                "passed": self.passed,
                "warnings": self.warnings,
                "failures": self.failures,
                "auto_repairs_applied": self.auto_repairs_applied,
                "validation_time_seconds": round(
                    self.validation_time_seconds, 2
                ),
                "export_time_seconds": round(self.export_time_seconds, 2),
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the report to a JSON string.

        Args:
            indent: Number of spaces for JSON indentation.

        Returns:
            JSON string.
        """
        return json.dumps(self.to_dict(), indent=indent)

    def save_json(self, path: str) -> None:
        """Write the validation report to a JSON file.

        Args:
            path: Absolute path to the output ``.json`` file.

        Implements: FR-029.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Validation report written to %s", path)

    def to_text(self) -> str:
        """Generate a human-readable summary string.

        Returns:
            Multi-line summary per FR-030 format.

        Implements: FR-030.
        """
        lines = [
            "=== Tessera Print Validation Report ===",
            f"Object: {self.object_name}",
            f"Printer: {self.printer_type}",
            "",
        ]

        for check in self.checks:
            tag = f"[{check.status.value}]"
            if check.status == CheckStatus.PASS:
                lines.append(f"{tag} {check.check_name}")
            else:
                suffix = ""
                if check.repaired:
                    suffix = " (Auto-repaired)"
                lines.append(
                    f"{tag} {check.check_name}: {check.message}{suffix}"
                )

        lines.append("")
        lines.append(
            f"Result: {self.passed}/{len(self.checks)} checks passed, "
            f"{self.warnings} warnings, {self.failures} failures."
        )

        return "\n".join(lines)
