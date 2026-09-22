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

"""View-label to camera pose prior converter.

Converts view labels (e.g. ``"front"``, ``"right"``) into initial
camera extrinsic matrices using the canonical azimuth/elevation
mapping from PRD §6 (provided by ``VIEW_LABEL_POSES``).

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    label_to_rotation_matrix — convert azimuth/elevation to 3×3 rotation
    get_prior_pose — build a prior CameraPose from a view label
    compute_angular_separation — angle between two rotation matrices
"""

from __future__ import annotations

import importlib.util as _importlib_util
import logging
import math
import os as _os
from typing import TYPE_CHECKING

import numpy as np

from tessera.multiview.pose_estimation.types import CameraPose

if TYPE_CHECKING:
    from tessera.vision.types import VIEW_LABEL_POSES
else:
    # Load VIEW_LABEL_POSES directly from the types.py file to avoid
    # triggering tessera.vision.__init__ which eagerly imports the
    # full pipeline and its heavy dependencies (PIL, etc.).
    _types_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))),
        "vision",
        "types.py",
    )
    _spec = _importlib_util.spec_from_file_location("tessera.vision.types", _types_path)
    _vision_types = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_vision_types)
    VIEW_LABEL_POSES = _vision_types.VIEW_LABEL_POSES  # noqa: F401
    del _vision_types, _spec, _types_path, _importlib_util, _os

logger = logging.getLogger("tessera.multiview")


def label_to_rotation_matrix(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    """Convert azimuth and elevation angles to a 3×3 rotation matrix.

    Produces a world-to-camera rotation matrix using the convention:
    - Azimuth rotates around the Y (up) axis.
    - Elevation tilts around the X (right) axis.
    - Camera looks along the -Z axis by default.

    Args:
        azimuth_deg: Azimuth angle in degrees (0–360).
        elevation_deg: Elevation angle in degrees (-90 to 90).

    Returns:
        A ``(3, 3)`` float64 rotation matrix.
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)

    # Rotation around Y axis (azimuth)
    cos_az = math.cos(az)
    sin_az = math.sin(az)
    r_y = np.array(
        [
            [cos_az, 0.0, sin_az],
            [0.0, 1.0, 0.0],
            [-sin_az, 0.0, cos_az],
        ],
        dtype=np.float64,
    )

    # Rotation around X axis (elevation)
    cos_el = math.cos(el)
    sin_el = math.sin(el)
    r_x = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, cos_el, -sin_el],
            [0.0, sin_el, cos_el],
        ],
        dtype=np.float64,
    )

    # Combined: first azimuth, then elevation
    return r_x @ r_y


def get_prior_pose(
    view_label: str,
    image_size: tuple[int, int],
    camera_distance: float = 2.0,
    focal_length: float = 525.0,
) -> CameraPose | None:
    """Build a prior ``CameraPose`` from a view label.

    Uses the canonical azimuth/elevation mapping from
    ``VIEW_LABEL_POSES`` (PRD §6) to generate an initial camera
    pose estimate.

    Args:
        view_label: A PRD §6 view label (e.g. ``"front"``).
        image_size: Image dimensions ``(width, height)``.
        camera_distance: Distance from the camera to the world origin.
        focal_length: Default focal length in pixels.

    Returns:
        A ``CameraPose`` with the canonical orientation, or ``None``
        if the label is not in the known vocabulary (e.g. ``"custom"``).

    Implements: FR-009 (strong priors from user-supplied labels).
    """
    pose_angles = VIEW_LABEL_POSES.get(view_label)
    if pose_angles is None or view_label == "custom":
        logger.debug(
            "No canonical pose for view label '%s'; skipping prior",
            view_label,
        )
        return None

    azimuth_deg, elevation_deg = pose_angles
    rotation = label_to_rotation_matrix(azimuth_deg, elevation_deg)

    # Place camera at `camera_distance` along the viewing direction
    # Camera looks at origin; position = R^T @ [0, 0, distance]
    camera_pos = rotation.T @ np.array([0.0, 0.0, camera_distance], dtype=np.float64)

    w, h = image_size
    principal_point = (w / 2.0, h / 2.0)

    logger.debug(
        "View-label prior: label=%s, azimuth=%.1f°, elevation=%.1f°",
        view_label,
        azimuth_deg,
        elevation_deg,
    )

    return CameraPose(
        rotation=rotation,
        translation=camera_pos,
        focal_length=focal_length,
        principal_point=principal_point,
        image_size=image_size,
        confidence=1.0,  # Full confidence for canonical priors
    )


def compute_angular_separation(r1: np.ndarray, r2: np.ndarray) -> float:
    """Compute the angular separation between two rotation matrices.

    Uses the geodesic distance on SO(3):
        angle = arccos((trace(R1^T @ R2) - 1) / 2)

    Args:
        r1: First rotation matrix, shape ``(3, 3)``.
        r2: Second rotation matrix, shape ``(3, 3)``.

    Returns:
        Angular separation in degrees.
    """
    r_rel = r1.T @ r2
    trace_val = np.trace(r_rel)
    # Clamp to valid range for arccos (numerical stability)
    cos_angle = np.clip((trace_val - 1.0) / 2.0, -1.0, 1.0)
    angle_rad = math.acos(float(cos_angle))
    return math.degrees(angle_rad)
