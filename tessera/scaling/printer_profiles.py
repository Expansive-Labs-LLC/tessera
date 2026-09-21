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

"""Printer profile presets for build volume validation.

Defines the ``PrinterProfile`` dataclass and built-in presets for
common FDM and SLA printers.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-013, FR-014, FR-015, FR-016.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

logger = logging.getLogger("tessera.scaling")


class PrinterTechnology(Enum):
    """Printer technology type.

    Implements: FR-013.
    """

    FDM = "FDM"
    SLA = "SLA"


@dataclass(frozen=True)
class PrinterProfile:
    """Printer build volume and technology definition.

    Attributes:
        name: Human-readable profile name.
        build_width_mm: Build volume X dimension in mm.
        build_depth_mm: Build volume Y dimension in mm.
        build_height_mm: Build volume Z dimension in mm.
        technology: Printer technology (FDM or SLA).
        default_wall_thickness_mm: Default minimum wall thickness
            in mm for the printer technology.

    Implements: FR-013.
    """

    name: str
    build_width_mm: float
    build_depth_mm: float
    build_height_mm: float
    technology: str  # "FDM" or "SLA"
    default_wall_thickness_mm: float


# FR-014: Built-in printer profiles.
_BUILTIN_PROFILES: List[PrinterProfile] = [
    PrinterProfile(
        name="Generic FDM",
        build_width_mm=220.0,
        build_depth_mm=220.0,
        build_height_mm=250.0,
        technology="FDM",
        default_wall_thickness_mm=1.2,
    ),
    PrinterProfile(
        name="Ender 3",
        build_width_mm=220.0,
        build_depth_mm=220.0,
        build_height_mm=250.0,
        technology="FDM",
        default_wall_thickness_mm=1.2,
    ),
    PrinterProfile(
        name="Prusa MK4",
        build_width_mm=250.0,
        build_depth_mm=210.0,
        build_height_mm=220.0,
        technology="FDM",
        default_wall_thickness_mm=1.2,
    ),
    PrinterProfile(
        name="Bambu Lab P1S",
        build_width_mm=256.0,
        build_depth_mm=256.0,
        build_height_mm=256.0,
        technology="FDM",
        default_wall_thickness_mm=1.2,
    ),
    PrinterProfile(
        name="Elegoo Mars 3",
        build_width_mm=143.0,
        build_depth_mm=89.0,
        build_height_mm=175.0,
        technology="SLA",
        default_wall_thickness_mm=0.5,
    ),
    PrinterProfile(
        name="Elegoo Saturn 3",
        build_width_mm=218.0,
        build_depth_mm=123.0,
        build_height_mm=250.0,
        technology="SLA",
        default_wall_thickness_mm=0.5,
    ),
    PrinterProfile(
        name="Custom",
        build_width_mm=220.0,
        build_depth_mm=220.0,
        build_height_mm=250.0,
        technology="FDM",
        default_wall_thickness_mm=1.2,
    ),
]


def get_builtin_profiles() -> List[PrinterProfile]:
    """Return a copy of the built-in printer profiles list.

    Returns:
        List of ``PrinterProfile`` instances.

    Implements: FR-014.
    """
    return list(_BUILTIN_PROFILES)


def get_profile_by_name(name: str) -> Optional[PrinterProfile]:
    """Look up a built-in printer profile by name.

    Args:
        name: Profile name (case-sensitive).

    Returns:
        Matching ``PrinterProfile`` or ``None`` if not found.
    """
    for profile in _BUILTIN_PROFILES:
        if profile.name == name:
            return profile
    return None


def get_printer_profile_enum_items():
    """Return EnumProperty items for printer profile selection.

    Each item is a tuple of ``(identifier, name, description)``.

    Returns:
        List of enum item tuples for ``bpy.props.EnumProperty``.

    Implements: FR-015.
    """
    items = []
    for profile in _BUILTIN_PROFILES:
        tech = profile.technology
        dims = (
            f"{profile.build_width_mm:.0f}×"
            f"{profile.build_depth_mm:.0f}×"
            f"{profile.build_height_mm:.0f} mm"
        )
        description = f"{tech} — {dims}"
        # Identifier is the name with spaces replaced by underscores.
        identifier = profile.name.upper().replace(" ", "_")
        items.append((identifier, profile.name, description))
    return items
