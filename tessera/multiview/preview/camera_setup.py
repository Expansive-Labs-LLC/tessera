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

"""Canonical camera placement and preview image types for preview renders.

Defines the ``PreviewImage`` dataclass and utilities for computing
camera positions for the 4 canonical preview views (front, right,
top, isometric).

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    PreviewImage — rendered preview image dataclass (FR-033)
    PREVIEW_VIEWS — canonical view definitions
    compute_camera_position — camera placement from azimuth/elevation
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class PreviewImage:
    """A rendered preview image.

    Attributes:
        view_label: One of ``"front"``, ``"right"``, ``"top"``,
            ``"isometric"``.
        filepath: Absolute path to the PNG file.
        resolution: Image dimensions ``(width, height)`` — always
            ``(512, 512)``.
        camera_pose: Camera orientation as
            ``{"azimuth": float, "elevation": float}`` in degrees.

    Implements: FR-033.
    """

    view_label: str  # "front", "right", "top", "isometric"
    filepath: str  # Absolute path to PNG file
    resolution: tuple[int, int]  # (width, height) — always (512, 512)
    camera_pose: dict  # {"azimuth": float, "elevation": float}


# FR-029: Canonical preview views.
PREVIEW_VIEWS: list[dict] = [
    {"label": "front", "azimuth": 0.0, "elevation": 0.0},
    {"label": "right", "azimuth": 90.0, "elevation": 0.0},
    {"label": "top", "azimuth": 0.0, "elevation": 90.0},
    {"label": "isometric", "azimuth": 45.0, "elevation": 35.0},
]

# FR-030: Preview render resolution.
PREVIEW_RESOLUTION = (512, 512)

# FR-031: Bounding box padding factor.
CAMERA_PADDING_FACTOR = 1.15  # 15% padding


def compute_camera_position(
    azimuth_deg: float,
    elevation_deg: float,
    distance: float,
) -> tuple[float, float, float]:
    """Compute camera position from azimuth, elevation, and distance.

    The camera looks at the world origin from the computed position.

    Args:
        azimuth_deg: Azimuth angle in degrees (0 = front, 90 = right).
        elevation_deg: Elevation angle in degrees (0 = horizon,
            90 = top-down).
        distance: Distance from the origin.

    Returns:
        ``(x, y, z)`` camera position in world coordinates.
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)

    x = distance * math.cos(el) * math.sin(az)
    y = -distance * math.cos(el) * math.cos(az)
    z = distance * math.sin(el)

    return (x, y, z)


def compute_framing_distance(
    bbox_dimensions: tuple[float, float, float],
    fov_deg: float = 50.0,
) -> float:
    """Compute camera distance to frame an object's bounding box.

    Calculates the distance such that the object's bounding box
    fills the viewport with the specified padding factor.

    Args:
        bbox_dimensions: ``(width, depth, height)`` of the object's
            bounding box.
        fov_deg: Camera field of view in degrees.

    Returns:
        Camera distance from origin.

    Implements: FR-031.
    """
    max_dim = max(bbox_dimensions)
    # Distance = half the diagonal / tan(fov/2), with padding
    half_fov = math.radians(fov_deg / 2.0)
    distance = (max_dim * CAMERA_PADDING_FACTOR) / (2.0 * math.tan(half_fov))
    return max(distance, 0.5)  # Minimum distance to avoid clipping
