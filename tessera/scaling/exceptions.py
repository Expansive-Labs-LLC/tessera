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

"""Exception types for the Tessera scaling and orientation pipeline.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-006, EC-003.
"""


class ScalingError(Exception):
    """Raised when a scaling operation fails.

    Used for post-scaling dimension mismatches (FR-006) and
    zero-extent axis detection (EC-003).

    Attributes:
        message: Human-readable error description.

    Implements: FR-006, EC-003.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
