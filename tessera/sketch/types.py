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

"""Core data types for the Tessera sketch-to-3D pathway.

Defines configuration, intermediate results, and pipeline output
contracts used across all sketch pipeline components.

Spec: SPEC-TS-0010 (Sketch-to-3D Pathway)

Public API:
    SketchConfig — pipeline configuration (§3.6)
    SymmetryConfig — symmetry enforcement configuration (FR-025)
    SketchDetectionResult — detection output (FR-002)
    PreprocessedSketch — preprocessing output (FR-014)
    SynthesizedImage — synthesis output (FR-022)
    SketchPipelineResult — full pipeline output (FR-032)

Constants:
    DEFAULT_SYNTHESIS_PROMPT — fallback prompt (FR-018)
    MIN_VRAM_SYNTHESIS_GB — minimum VRAM for diffusion (FR-039)
    MAX_SKETCH_INPUTS — maximum sketch inputs per request (FR-034)
    MAX_FILE_SIZE_BYTES — maximum input file size (SEC-005)
    MIN_LINE_CONTENT_PIXELS — minimum non-zero pixels (EC-001)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from tessera.reconstruction.mesh_output import StandardMesh

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# FR-018: Default synthesis prompt when no user prompt is provided.
DEFAULT_SYNTHESIS_PROMPT = (
    "a 3D object, studio lighting, white background, product photography"
)

# FR-039: Minimum available VRAM in GB for diffusion model loading.
MIN_VRAM_SYNTHESIS_GB = 8.0

# FR-034: Maximum number of sketch inputs per reconstruction request.
MAX_SKETCH_INPUTS = 2

# SEC-005: Maximum input file size in bytes (50 MB).
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# EC-001: Minimum number of non-zero pixels after binarisation.
MIN_LINE_CONTENT_PIXELS = 100

# FR-041: ImageNet normalisation statistics for CNN classifier.
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# FR-041: CNN classifier input size.
CNN_INPUT_SIZE = 224

# FR-019: Synthesis output resolution.
SYNTHESIS_RESOLUTION = 512

# FR-003/FR-004: Heuristic thresholds for sketch detection.
EDGE_DENSITY_THRESHOLD = 0.15
COLOR_STD_THRESHOLD = 30.0
HEURISTIC_LOW_CONFIDENCE = 0.40
HEURISTIC_HIGH_CONFIDENCE = 0.85
CNN_SKETCH_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Configuration Dataclasses (§3.6)
# ---------------------------------------------------------------------------


@dataclass
class SketchConfig:
    """Configuration for the sketch-to-3D pipeline.

    Attributes:
        symmetry_enabled: Enable bilateral symmetry enforcement (FR-025).
        perspective_correction: Attempt perspective correction on paper
            sketches (FR-012).
        guidance_scale: ControlNet conditioning strength, range 1.0–20.0
            (FR-021).
        num_inference_steps: Diffusion steps for synthesis, range 10–100
            (FR-021).
        synthesis_seed: Random seed for deterministic synthesis (FR-020).
        synthesis_prompt: Text prompt describing the sketched object.
            ``None`` uses ``DEFAULT_SYNTHESIS_PROMPT`` (FR-018).

    Implements: §3.6 input specification.
    """

    symmetry_enabled: bool = True
    perspective_correction: bool = True
    guidance_scale: float = 7.5
    num_inference_steps: int = 30
    synthesis_seed: int = 42
    synthesis_prompt: Optional[str] = None  # None → use default prompt


@dataclass
class SymmetryConfig:
    """Configuration for symmetry enforcement.

    Attributes:
        enable_symmetry: Enable bilateral symmetry (FR-025).
        merge_tolerance: Vertex merge distance at symmetry plane
            in normalised mesh space (FR-027).
        min_axis_spread_ratio: Skip symmetry if axis spread is below
            this fraction of the bounding box diagonal (FR-028).

    Implements: FR-025, FR-027, FR-028.
    """

    enable_symmetry: bool = True
    merge_tolerance: float = 0.001
    min_axis_spread_ratio: float = 0.05


# ---------------------------------------------------------------------------
# Result Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SketchDetectionResult:
    """Result of sketch vs. photo classification.

    Attributes:
        is_sketch: ``True`` if the image is classified as a sketch.
        confidence: Classification confidence in ``[0.0, 1.0]``.
        sketch_type: Detected sketch medium — ``"pencil"``,
            ``"ink"``, ``"digital"``, or ``"unknown"`` (FR-040).
        edge_density_ratio: Ratio of Canny edge pixels to total
            pixels, in ``[0.0, 1.0]`` (FR-003).
        detection_method: Classification method used — ``"heuristic"``,
            ``"cnn"``, or ``"user_override"`` (FR-002).

    Implements: FR-002.
    """

    is_sketch: bool
    confidence: float
    sketch_type: str
    edge_density_ratio: float
    detection_method: str


@dataclass
class PreprocessedSketch:
    """Output of sketch preprocessing.

    Attributes:
        binary_image: Binarised sketch, ``(H, W)`` uint8, values
            0 (background) or 255 (line) (FR-015).
        thinned_image: Skeletonised sketch, ``(H, W)`` uint8, values
            0 or 255 (FR-011).
        was_perspective_corrected: Whether perspective correction was
            applied (FR-012).
        original_size: Original image dimensions ``(width, height)``
            before any preprocessing.

    Implements: FR-014.
    """

    binary_image: np.ndarray  # (H, W) uint8, 0 or 255
    thinned_image: np.ndarray  # (H, W) uint8, 0 or 255
    was_perspective_corrected: bool
    original_size: tuple[int, int]  # (width, height)


@dataclass
class SynthesizedImage:
    """Output of ControlNet sketch-to-rendered-image synthesis.

    Attributes:
        rendered_image: Photo-realistic rendering, ``(512, 512, 3)``
            uint8 RGB (FR-019).
        prompt_used: The text prompt used for synthesis (FR-018).
        seed: The random seed used (FR-020).
        inference_time_s: Wall-clock seconds for diffusion inference.
        guidance_scale: ControlNet conditioning strength used (FR-021).

    Implements: FR-022.
    """

    rendered_image: np.ndarray  # (512, 512, 3) uint8 RGB
    prompt_used: str
    seed: int
    inference_time_s: float
    guidance_scale: float


@dataclass
class SketchPipelineResult:
    """Result of the full sketch-to-3D pipeline.

    Attributes:
        mesh: Normalised mesh data, ``None`` on failure.
        success: ``True`` if the pipeline produced a valid mesh.
        error_message: Empty on success; actionable message on failure.
        warnings: Non-fatal issues encountered during processing.
        detection_results: One ``SketchDetectionResult`` per input image.
        synthesized_images: One ``SynthesizedImage`` per sketch input.
        symmetry_applied: Whether symmetry enforcement was applied.
        total_time_s: End-to-end wall-clock time in seconds.

    Implements: FR-032.
    """

    mesh: "StandardMesh | None"  # None on failure
    success: bool
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)
    detection_results: list[SketchDetectionResult] = field(default_factory=list)
    synthesized_images: list[SynthesizedImage] = field(default_factory=list)
    symmetry_applied: bool = False
    total_time_s: float = 0.0
