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

"""Core data types and error classes for multi-view pose estimation.

Defines the camera pose representation, pose estimation result wrapper,
and error hierarchy for the multi-view pipeline.

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    CameraPose — estimated camera pose for a single image (FR-012)
    PoseEstimationResult — pose estimation result (FR-013)
    PoseEstimationError — general pose estimation failure
    InsufficientOverlapError — fewer than 3 cameras registered
    InsufficientSeparationError — camera angles too similar
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# Error Types (§10.4)
# ---------------------------------------------------------------------------


class PoseEstimationError(Exception):
    """General pose estimation failure.

    Base exception for all pose estimation errors.
    """

    pass


class InsufficientOverlapError(PoseEstimationError):
    """Fewer than 3 cameras could be registered.

    Raised when feature matching produces insufficient correspondences
    to triangulate camera positions for at least 3 views.

    Implements: FR-014.
    """

    pass


class InsufficientSeparationError(PoseEstimationError):
    """Camera angles are too similar for reliable triangulation.

    Raised when the maximum angular separation between any two
    registered cameras is below the 20° minimum viable threshold.

    Implements: EC-001.
    """

    pass


# ---------------------------------------------------------------------------
# Data Types (§3.6)
# ---------------------------------------------------------------------------


@dataclass
class CameraPose:
    """Estimated camera pose for a single image.

    Attributes:
        rotation: Rotation matrix (world-to-camera), shape ``(3, 3)``
            float64.
        translation: Camera position in world coordinates, shape
            ``(3,)`` float64.
        focal_length: Focal length in pixels.
        principal_point: Principal point ``(cx, cy)`` in pixels.
        image_size: Image dimensions ``(width, height)`` in pixels.
        confidence: Pose estimation confidence in ``[0.0, 1.0]``.

    Implements: FR-012.
    """

    rotation: np.ndarray  # (3, 3) float64 — rotation matrix (world-to-camera)
    translation: np.ndarray  # (3,) float64 — camera position in world coords
    focal_length: float  # Focal length in pixels
    principal_point: tuple[float, float]  # (cx, cy) in pixels
    image_size: tuple[int, int]  # (width, height) in pixels
    confidence: float  # Pose confidence [0.0, 1.0]

    def __post_init__(self) -> None:
        """Validate array shapes and value ranges."""
        self.rotation = np.asarray(self.rotation, dtype=np.float64)
        self.translation = np.asarray(self.translation, dtype=np.float64)

        if self.rotation.shape != (3, 3):
            raise ValueError(
                f"rotation must have shape (3, 3), got {self.rotation.shape}"
            )
        if self.translation.shape != (3,):
            raise ValueError(
                f"translation must have shape (3,), got {self.translation.shape}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0.0, 1.0], got {self.confidence}"
            )


@dataclass
class PoseEstimationResult:
    """Result of multi-view pose estimation.

    Attributes:
        poses: One ``CameraPose`` per input image, ``None`` for images
            whose pose could not be estimated.
        num_registered: Number of images with successfully estimated
            poses.
        inlier_ratio: Fraction of inlier feature matches to total
            matches across all image pairs.
        success: ``True`` if ``num_registered >= 3``.
        error_message: Non-empty on failure; empty string on success.
        feature_match_counts: Maps ``(image_i, image_j)`` to the
            number of inlier matches for that pair.

    Implements: FR-013.
    """

    poses: list[CameraPose | None]  # One per input image; None if pose failed
    num_registered: int  # Number of successfully posed cameras
    inlier_ratio: float  # Fraction of inlier feature matches
    success: bool  # True if num_registered >= 3
    error_message: str = ""  # Non-empty on failure
    feature_match_counts: dict[tuple[int, int], int] = field(default_factory=dict)
    # Maps (image_i, image_j) → number of inlier matches
