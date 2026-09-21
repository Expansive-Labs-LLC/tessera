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

"""Abstract base class for print-readiness validation checks.

Each concrete check must implement ``check()`` and ``repair()``.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)
"""

from __future__ import annotations

import abc
from typing import Any


class BaseCheck(abc.ABC):
    """Abstract base class for a single validation check.

    Subclasses must define ``name`` and implement ``check()`` and
    ``repair()``.

    See §10.4 for the per-check API contract.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable check name (e.g. ``'Non-Manifold Edges'``)."""

    @abc.abstractmethod
    def check(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> "CheckResult":  # noqa: F821
        """Run the validation check on *obj*.

        Args:
            obj: ``bpy.types.Object`` with mesh data.
            settings: Validator settings dict.

        Returns:
            A ``CheckResult`` with status, message, and details.
        """

    @abc.abstractmethod
    def repair(
        self,
        obj: Any,
        settings: dict[str, Any],
    ) -> "RepairResult":  # noqa: F821
        """Attempt to auto-repair the issue on *obj*.

        Args:
            obj: ``bpy.types.Object`` with mesh data (the ``_print``
                duplicate).
            settings: Validator settings dict.

        Returns:
            A ``RepairResult`` indicating success and description.
        """
