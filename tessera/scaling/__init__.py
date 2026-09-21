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

"""Real-world scaling and print orientation pipeline.

Provides the ``ScalingOrientationPipeline`` that transforms unitless AI
meshes into physically correct, print-optimized geometry with mm-accurate
dimensions and minimized overhangs.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Public API:
    ScalingOrientationPipeline — orchestrates scaling + orientation.
    DimensionSpec — user-specified or auto-inferred target dimensions.
    PrinterProfile — printer build-volume and technology definition.
"""

from .dimension_input import DimensionSpec, DimensionSuggestion
from .exceptions import ScalingError
from .pipeline import ScalingOrientationPipeline
from .printer_profiles import PrinterProfile, get_builtin_profiles, get_profile_by_name

__all__ = [
    "DimensionSpec",
    "DimensionSuggestion",
    "ScalingError",
    "ScalingOrientationPipeline",
    "PrinterProfile",
    "get_builtin_profiles",
    "get_profile_by_name",
]
