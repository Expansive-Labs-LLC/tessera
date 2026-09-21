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

"""Print-readiness validator module for Tessera.

Provides the ``PrintValidator`` orchestrator and ``ValidationReport``
for validating meshes against 7 print-readiness checks.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)
"""

from .data_types import CheckResult, CheckStatus, ExportResult, RepairResult
from .print_validator import PrintValidator
from .report import ValidationReport

__all__ = [
    "CheckResult",
    "CheckStatus",
    "ExportResult",
    "PrintValidator",
    "RepairResult",
    "ValidationReport",
]
