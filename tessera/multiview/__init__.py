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

"""Tessera multi-view alignment and enhanced reconstruction.

Provides multi-view camera pose estimation, NeuS2-based neural surface
reconstruction, automatic strategy selection (single-image vs. multi-view),
and a 4-view preview render pipeline.

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    StrategySelector — routes 1–12 images to optimal reconstruction path
    PoseEstimator — abstract base class for pose estimation
    HlocPoseEstimator — hloc-based SfM implementation
    MultiViewAdapter — multi-view ReconstructionAdapter
    PreviewRenderer — 4-view Workbench preview renders
    CameraPose — estimated camera pose dataclass
    PoseEstimationResult — pose estimation result dataclass
    PreviewImage — rendered preview image dataclass
"""

from tessera.multiview.pose_estimation.base import PoseEstimator
from tessera.multiview.pose_estimation.hloc_estimator import HlocPoseEstimator
from tessera.multiview.pose_estimation.types import (
    CameraPose,
    InsufficientOverlapError,
    InsufficientSeparationError,
    PoseEstimationError,
    PoseEstimationResult,
)
from tessera.multiview.preview.camera_setup import PreviewImage
from tessera.multiview.preview.renderer import PreviewRenderer
from tessera.multiview.reconstruction.multiview_adapter import MultiViewAdapter
from tessera.multiview.strategy import StrategySelector

__all__ = [
    "CameraPose",
    "HlocPoseEstimator",
    "InsufficientOverlapError",
    "InsufficientSeparationError",
    "MultiViewAdapter",
    "PoseEstimationError",
    "PoseEstimationResult",
    "PoseEstimator",
    "PreviewImage",
    "PreviewRenderer",
    "StrategySelector",
]
