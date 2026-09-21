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

"""Abstract base class for pose estimators.

Defines the ``PoseEstimator`` interface that all pose estimation
backends must implement.

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    PoseEstimator — abstract base class (FR-005)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from tessera.multiview.pose_estimation.types import PoseEstimationResult
import importlib.util as _importlib_util
import os as _os

# Load VisionResult directly from the types.py file to avoid
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
VisionResult = _vision_types.VisionResult  # noqa: F401
del _vision_types, _spec, _types_path, _importlib_util, _os


class PoseEstimator(ABC):
    """Abstract base class for multi-view pose estimation.

    Each concrete estimator wraps a specific SfM pipeline
    (hloc, COLMAP, custom) behind this uniform interface.
    The ``StrategySelector`` interacts only with this interface.

    Subclasses must implement:
        - ``estimate_poses()`` — run SfM and return camera poses

    Implements: FR-005, CON-002.
    """

    @abstractmethod
    def estimate_poses(
        self, vision_results: list[VisionResult]
    ) -> PoseEstimationResult:
        """Estimate camera poses from multiple images.

        Args:
            vision_results: 3 or more processed images from the vision
                pipeline.  Each entry contains the RGB image,
                segmentation mask, depth map, view label, and
                feature embeddings.

        Returns:
            ``PoseEstimationResult`` with estimated camera poses for
            each image.  Images whose pose could not be estimated
            have ``None`` in the poses list.
        """
