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

"""Tessera vision analysis pipeline package.

Processes user-uploaded reference images through four sequential stages:
segmentation, depth estimation, view classification, and feature
extraction. Produces a ``VisionResult`` per image consumed by the
3D reconstruction engine (TASK-TS-0004).

Spec: SPEC-TS-0003 (Vision Analysis Pipeline)

Public API:
    VisionPipeline — main pipeline entry point
    ImageInput — pipeline input per image
    VisionResult — pipeline output per image
    GPUNotAvailableError — no CUDA/ROCm GPU
    ImageLoadError — corrupt/unreadable image
    InsufficientVRAMError — not enough GPU memory
    PipelineError — general pipeline failure
    VIEW_LABEL_POSES — canonical camera-pose mapping
"""

from .pipeline import VisionPipeline
from .types import (
    GPUNotAvailableError,
    ImageInput,
    ImageLoadError,
    InsufficientVRAMError,
    PipelineError,
    VIEW_LABEL_POSES,
    VisionResult,
)

__all__ = [
    "GPUNotAvailableError",
    "ImageInput",
    "ImageLoadError",
    "InsufficientVRAMError",
    "PipelineError",
    "VIEW_LABEL_POSES",
    "VisionPipeline",
    "VisionResult",
]
