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

"""Print-readiness validation checks for Tessera.

Each check class implements ``BaseCheck`` with ``check()`` and
``repair()`` methods.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)
"""

from .base import BaseCheck
from .degenerate_faces import DegenerateFacesCheck
from .manifold import ManifoldCheck
from .overhang import OverhangCheck
from .scale_sanity import ScaleSanityCheck
from .self_intersection import SelfIntersectionCheck
from .volume import VolumeCheck
from .wall_thickness import WallThicknessCheck

# Ordered list of all checks, executed in this sequence.
ALL_CHECKS: list[type[BaseCheck]] = [
    ManifoldCheck,
    SelfIntersectionCheck,
    DegenerateFacesCheck,
    WallThicknessCheck,
    OverhangCheck,
    VolumeCheck,
    ScaleSanityCheck,
]

__all__ = [
    "ALL_CHECKS",
    "DegenerateFacesCheck",
    "ManifoldCheck",
    "OverhangCheck",
    "ScaleSanityCheck",
    "SelfIntersectionCheck",
    "VolumeCheck",
    "WallThicknessCheck",
]
