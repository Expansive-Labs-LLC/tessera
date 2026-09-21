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

"""Exception types for the Tessera mesh cleanup pipeline.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-020.
"""


class MeshCleanupError(Exception):
    """Raised when a critical cleanup step fails.

    Wraps the original exception with the step name so the caller
    can identify which pipeline stage caused the failure.  The undo
    step remains intact so the scene can be reverted via Ctrl+Z.

    Attributes:
        step_name: Name of the pipeline step that failed.
        original_exception: The underlying exception that triggered
            the failure.

    Implements: FR-020.
    """

    def __init__(self, step_name: str, original_exception: Exception) -> None:
        self.step_name = step_name
        self.original_exception = original_exception
        super().__init__(
            f"Critical cleanup step '{step_name}' failed: {original_exception}"
        )
