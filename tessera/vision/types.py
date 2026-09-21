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

"""Core data types and error classes for the Tessera vision pipeline.

Defines the pipeline's input/output contracts, error hierarchy, and
canonical view-label camera-pose mapping.

Spec: SPEC-TS-0003 (Vision Analysis Pipeline)

Public API:
    ImageInput — pipeline input per image (§3.2)
    VisionResult — pipeline output per image (§3.3)
    GPUNotAvailableError — no CUDA/ROCm GPU (FR-022)
    ImageLoadError — corrupt/unreadable image (EC-003)
    InsufficientVRAMError — not enough GPU memory (EC-005)
    PipelineError — general pipeline failure (FR-001)
    VIEW_LABEL_POSES — canonical camera-pose mapping (§10.4)
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# FR-001: Maximum images per batch.
MAX_BATCH_SIZE = 6

# FR-003: Maximum dimension for input images (preserving aspect ratio).
MAX_IMAGE_DIMENSION = 1024

# EC-001: Minimum dimension — images smaller than this are upscaled.
MIN_IMAGE_DIMENSION = 256

# SEC-005: Maximum file size in bytes (50 MB).
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# FR-002: Supported image file extensions.
VALID_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic"})

# FR-008: Valid view labels from PRD §6 vocabulary.
VALID_VIEW_LABELS = frozenset(
    {
        "front",
        "back",
        "left",
        "right",
        "top",
        "bottom",
        "front-left",
        "front-right",
        "isometric",
        "custom",
    }
)

# §10.4: Canonical camera poses per view label (azimuth°, elevation°).
# Used by the reconstruction engine (TASK-TS-0004) to initialise camera poses.
VIEW_LABEL_POSES: dict[str, tuple[float, float]] = {
    "front": (0.0, 0.0),
    "back": (180.0, 0.0),
    "left": (270.0, 0.0),
    "right": (90.0, 0.0),
    "top": (0.0, 90.0),
    "bottom": (0.0, -90.0),
    "front-left": (315.0, 0.0),
    "front-right": (45.0, 0.0),
    "isometric": (45.0, 35.0),
    # "custom:<az>,<el>" — parsed from label string at runtime
}


# ---------------------------------------------------------------------------
# Error Types (§10.3)
# ---------------------------------------------------------------------------


class PipelineError(Exception):
    """General pipeline failure.

    Raised for batch validation errors and unrecoverable pipeline issues.

    FR-001: Raised when image list is empty or exceeds MAX_BATCH_SIZE.
    """

    pass


class GPUNotAvailableError(PipelineError):
    """No CUDA or ROCm GPU detected.

    FR-022: Raised before any model loading or inference is attempted.
    """

    pass


class ImageLoadError(PipelineError):
    """Cannot decode an image file.

    EC-003: Raised when an image is corrupt, truncated, or unreadable.
    """

    pass


class InsufficientVRAMError(PipelineError):
    """Not enough GPU memory to load a model.

    EC-005: Raised when ``torch.cuda.OutOfMemoryError`` is caught
    during model loading, with available vs. required VRAM details.
    """

    pass


# ---------------------------------------------------------------------------
# Input Specification (§3.2)
# ---------------------------------------------------------------------------


@dataclass
class ImageInput:
    """A single image input to the vision pipeline.

    Attributes:
        filepath: Absolute path to the image file.
        view_label: PRD §6 label or ``None`` for auto-detect.
        custom_azimuth: Degrees 0–360, only when ``view_label == "custom"``.
        custom_elevation: Degrees -90–90, only when ``view_label == "custom"``.
        force_sketch: Override sketch auto-detection (SPEC-TS-0010).

    Implements: FR-002, FR-008, §3.2.
    """

    filepath: str
    view_label: Optional[str] = None
    custom_azimuth: Optional[float] = None
    custom_elevation: Optional[float] = None
    force_sketch: bool = False


# ---------------------------------------------------------------------------
# Output Specification (§3.3)
# ---------------------------------------------------------------------------


@dataclass
class VisionResult:
    """Pipeline output for a single processed image.

    Attributes:
        image: Preprocessed RGB image, ``(H, W, 3)`` uint8.
        mask: Binary segmentation mask, ``(H, W)`` uint8, values 0 or 255.
        depth_map: Masked monocular depth, ``(H, W)`` float32, ``[0.0, 1.0]``.
        view_label: Predicted or user-supplied view label (PRD §6).
        label_confidence: Confidence in ``[0.0, 1.0]``.
        label_source: ``"user"`` or ``"auto"``.
        label_needs_confirmation: ``True`` if auto-detected with low confidence.
        features: DINOv2 CLS token embedding, ``(1, D)`` float32.
        original_size: ``(width, height)`` in pixels before any resizing.
        processing_time_s: Stage name → wall-clock seconds.

    Implements: FR-014, §3.3.
    """

    image: np.ndarray
    mask: np.ndarray
    depth_map: np.ndarray
    view_label: str
    label_confidence: float
    label_source: str
    label_needs_confirmation: bool
    features: np.ndarray
    original_size: tuple[int, int]
    processing_time_s: dict[str, float] = field(default_factory=dict)
