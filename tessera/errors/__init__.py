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

"""Centralized error handling subsystem for Tessera.

Provides the ``ErrorHandler`` for catching and classifying pipeline
exceptions, the ``ERROR_CATALOG`` with structured error entries,
and the ``UIReporter`` for surfacing errors in Blender's UI.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)
"""

from .catalog import ERROR_CATALOG
from .categories import ErrorCatalogEntry, ErrorCategory, ErrorSeverity
from .handler import ErrorHandler
from .ui_reporter import UIReporter

__all__ = [
    "ERROR_CATALOG",
    "ErrorCatalogEntry",
    "ErrorCategory",
    "ErrorHandler",
    "ErrorSeverity",
    "UIReporter",
]
