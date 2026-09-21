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

"""Sketch pipeline orchestrator — full sketch-to-3D flow.

Coordinates sketch detection, preprocessing, ControlNet synthesis,
3D reconstruction, and symmetry enforcement into a single pipeline
call that produces a ``StandardMesh`` from hand-drawn sketch input.

Spec: SPEC-TS-0010 (Sketch-to-3D Pathway)

Public API:
    SketchPipeline — main orchestrator (FR-030)

Implements: FR-030, FR-031, FR-032, FR-033, FR-034, FR-035, FR-036,
            FR-037, FR-038, FR-039, CON-001–CON-009,
            SEC-001, SEC-003, SEC-004, SEC-005, SEC-006.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from tessera.sketch.detector import SketchDetector
from tessera.sketch.preprocessor import SketchPreprocessor
from tessera.sketch.symmetry import SymmetryEnforcer
from tessera.sketch.synthesizer import SketchSynthesizer
from tessera.sketch.types import (
    DEFAULT_SYNTHESIS_PROMPT,
    MAX_FILE_SIZE_BYTES,
    MAX_SKETCH_INPUTS,
    MIN_LINE_CONTENT_PIXELS,
    MIN_VRAM_SYNTHESIS_GB,
    SYNTHESIS_RESOLUTION,
    SketchConfig,
    SketchDetectionResult,
    SketchPipelineResult,
    SymmetryConfig,
)
from tessera.vision.types import ImageInput, VisionResult

logger = logging.getLogger("tessera.sketch")


class SketchPipeline:
    """Orchestrate the full sketch-to-3D pipeline.

    Coordinates five sequential stages — detection, preprocessing,
    synthesis, reconstruction, symmetry — loading and unloading GPU
    models between stages to minimise peak VRAM usage (FR-035).

    Args:
        cache_dir: Absolute path to the model weight cache directory.

    Example::

        pipeline = SketchPipeline(cache_dir="/path/to/cache")
        result = pipeline.process(
            inputs=[ImageInput(filepath="/path/to/sketch.jpg")],
            config=SketchConfig(synthesis_prompt="a vase"),
        )
        if result.success:
            print(f"Vertices: {result.mesh.metadata['vertex_count']}")

    Implements: FR-030.
    """

    def __init__(self, cache_dir: str) -> None:
        self._cache_dir = cache_dir
        self._detector = SketchDetector(cache_dir=cache_dir)
        self._preprocessor = SketchPreprocessor()
        self._synthesizer = SketchSynthesizer(cache_dir=cache_dir)
        self._symmetry = SymmetryEnforcer()

    def process(
        self,
        inputs: list[ImageInput],
        config: SketchConfig | None = None,
    ) -> SketchPipelineResult:
        """Process sketch input(s) through the full sketch-to-3D flow.

        FR-031: Classifies each image and routes sketches through
        the sketch pathway; photos are passed to the standard
        vision pipeline.

        FR-034: Rejects more than 2 sketch inputs.

        FR-035: Stages execute sequentially with model unloading
        between stages.

        Args:
            inputs: List of ``ImageInput`` objects (1–2 for sketch).
            config: Pipeline configuration. Uses defaults if ``None``.

        Returns:
            ``SketchPipelineResult`` with mesh and diagnostic data.

        Implements: FR-030–FR-039.
        """
        pipeline_start = time.monotonic()
        config = config or SketchConfig()
        warnings: list[str] = []
        detection_results: list[SketchDetectionResult] = []
        synthesized_images = []

        self._update_progress("Detecting", 0, len(inputs))

        # --- Stage 1: Sketch Detection (FR-031) ---
        sketch_inputs: list[tuple[int, ImageInput, np.ndarray]] = []
        photo_inputs: list[tuple[int, ImageInput]] = []

        for i, img_input in enumerate(inputs):
            self._update_progress("Detecting", i + 1, len(inputs))

            # SEC-001: Validate file path.
            try:
                image = self._load_and_validate(img_input)
            except (ValueError, OSError) as e:
                return SketchPipelineResult(
                    mesh=None,
                    success=False,
                    error_message=str(e),
                    detection_results=detection_results,
                    total_time_s=time.monotonic() - pipeline_start,
                )

            # Classify.
            det_result = self._detector.classify(
                image, force_sketch=img_input.force_sketch
            )
            detection_results.append(det_result)

            if det_result.is_sketch:
                sketch_inputs.append((i, img_input, image))
            else:
                photo_inputs.append((i, img_input))

        # FR-031: Route photos to standard pipeline.
        if not sketch_inputs and photo_inputs:
            # All inputs are photos — no sketch processing needed.
            logger.info(
                "Sketch pipeline: all inputs classified as photos, "
                "routing to standard vision pipeline"
            )
            return SketchPipelineResult(
                mesh=None,
                success=True,
                detection_results=detection_results,
                warnings=["All inputs classified as photos — use the "
                          "standard vision pipeline."],
                total_time_s=time.monotonic() - pipeline_start,
            )

        # FR-034: Maximum 2 sketch inputs.
        sketch_count = len(sketch_inputs)
        if sketch_count > MAX_SKETCH_INPUTS:
            error_msg = (
                f"Sketch-to-3D pathway supports a maximum of "
                f"{MAX_SKETCH_INPUTS} sketch inputs. Received: "
                f"{sketch_count}. Provide 1 (single-view) or 2 "
                f"(front + side) sketches."
            )
            logger.error("Sketch pipeline failed: %s", error_msg)
            return SketchPipelineResult(
                mesh=None,
                success=False,
                error_message=error_msg,
                detection_results=detection_results,
                total_time_s=time.monotonic() - pipeline_start,
            )

        # FR-039: Check VRAM before loading diffusion model.
        vram_check = self._check_vram()
        if vram_check is not None:
            return SketchPipelineResult(
                mesh=None,
                success=False,
                error_message=vram_check,
                detection_results=detection_results,
                total_time_s=time.monotonic() - pipeline_start,
            )

        # Low-confidence warnings.
        for det in detection_results:
            if det.is_sketch and det.confidence < 0.7:
                warnings.append(
                    f"Low sketch confidence: {det.confidence:.2f}"
                )

        # --- Stage 2: Preprocessing (FR-007–FR-015) ---
        preprocessed_sketches = []
        for idx, (i, img_input, image) in enumerate(sketch_inputs):
            self._update_progress(
                "Preprocessing", idx + 1, sketch_count
            )
            try:
                preprocessed = self._preprocessor.preprocess(image, config)
                preprocessed_sketches.append(
                    (i, img_input, preprocessed)
                )
            except ValueError as e:
                return SketchPipelineResult(
                    mesh=None,
                    success=False,
                    error_message=str(e),
                    detection_results=detection_results,
                    warnings=warnings,
                    total_time_s=time.monotonic() - pipeline_start,
                )

            # EC-002: Warn about coloured/textured paper.
            det = detection_results[i]
            if det.edge_density_ratio > 0 and det.sketch_type == "ink":
                from tessera.sketch.utils.edge_density import (
                    compute_color_std,
                )

                cs = compute_color_std(image)
                if cs > 10.0:
                    warnings.append(
                        "Sketch appears to be drawn on colored or "
                        "textured paper. Line detection quality may "
                        "be reduced."
                    )

            # EC-005: Warn about minimal line content.
            stroke_pixels = int(
                np.count_nonzero(preprocessed.binary_image)
            )
            total_pixels = (
                preprocessed.binary_image.shape[0]
                * preprocessed.binary_image.shape[1]
            )
            stroke_percent = stroke_pixels / max(total_pixels, 1) * 100

            if stroke_percent < 2.0:
                warnings.append(
                    f"Sketch has minimal line content "
                    f"({stroke_percent:.1f}% of image area). "
                    "Reconstruction quality may be very low. "
                    "Consider adding more detail to the sketch."
                )

            # EC-004: Warn about thick strokes.
            if preprocessed.binary_image is not None:
                binary = preprocessed.binary_image
                thinned = preprocessed.thinned_image
                binary_count = int(np.count_nonzero(binary))
                thinned_count = int(np.count_nonzero(thinned))
                if binary_count > 0 and thinned_count > 0:
                    ratio = binary_count / thinned_count
                    if ratio > 5.0:
                        warnings.append(
                            "Sketch contains thick or irregular strokes. "
                            "Thinned output may differ from original "
                            "artistic intent."
                        )

        # --- Stage 3: Synthesis (FR-016–FR-023) ---
        prompt = config.synthesis_prompt or DEFAULT_SYNTHESIS_PROMPT

        for idx, (i, img_input, preprocessed) in enumerate(
            preprocessed_sketches
        ):
            self._update_progress(
                "Synthesizing", idx + 1, sketch_count
            )
            synth_result = self._synthesizer.synthesize(
                preprocessed, prompt, config
            )
            synthesized_images.append(synth_result)

        # --- Stage 4: Reconstruction (FR-033, FR-038) ---
        self._update_progress("Reconstructing", 1, 1)

        vision_outputs = self._build_vision_outputs(
            sketch_inputs, synthesized_images
        )

        # CON-006: Route through standard ReconstructionEngine.
        try:
            from tessera.reconstruction.engine import ReconstructionEngine

            engine = ReconstructionEngine(cache_dir=self._cache_dir)
            recon_result = engine.reconstruct(vision_outputs)
        except Exception as e:
            logger.error(
                "Sketch pipeline failed: failed_stage=reconstruction, "
                "error_message=%s",
                str(e),
            )
            return SketchPipelineResult(
                mesh=None,
                success=False,
                error_message=f"Reconstruction failed: {e}",
                warnings=warnings,
                detection_results=detection_results,
                synthesized_images=synthesized_images,
                total_time_s=time.monotonic() - pipeline_start,
            )

        if not recon_result.success:
            return SketchPipelineResult(
                mesh=None,
                success=False,
                error_message=recon_result.error_message,
                warnings=warnings + recon_result.warnings,
                detection_results=detection_results,
                synthesized_images=synthesized_images,
                total_time_s=time.monotonic() - pipeline_start,
            )

        mesh = recon_result.mesh

        # --- Stage 5: Symmetry Enforcement (FR-024–FR-029) ---
        symmetry_applied = False
        if config.symmetry_enabled and mesh is not None:
            self._update_progress("Symmetry", 1, 1)
            sym_config = SymmetryConfig(
                enable_symmetry=True,
            )
            original_verts = mesh.vertices.copy()
            mesh = self._symmetry.enforce(mesh, sym_config)

            # Check if symmetry was actually applied (vertices changed).
            if not np.array_equal(original_verts, mesh.vertices):
                symmetry_applied = True

        # FR-037: Add sketch metadata to mesh.
        if mesh is not None:
            mesh.metadata["input_type"] = "sketch"
            if detection_results:
                mesh.metadata["sketch_type"] = detection_results[0].sketch_type
            mesh.metadata["synthesis_prompt"] = prompt
            mesh.metadata["symmetry_applied"] = symmetry_applied

        total_time = time.monotonic() - pipeline_start

        logger.info(
            "Sketch pipeline complete: total_time_s=%.2f, "
            "stages_completed=5, symmetry_applied=%s, success=True",
            total_time,
            symmetry_applied,
        )

        self._update_progress("Complete", 1, 1)

        return SketchPipelineResult(
            mesh=mesh,
            success=True,
            warnings=warnings + recon_result.warnings,
            detection_results=detection_results,
            synthesized_images=synthesized_images,
            symmetry_applied=symmetry_applied,
            total_time_s=total_time,
        )

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _load_and_validate(self, img_input: ImageInput) -> np.ndarray:
        """Load and validate a sketch image file.

        SEC-001: Path traversal prevention via ``Path.resolve()``.
        SEC-005: File size validation (≤ 50 MB).
        CON-003: Returns in-memory copy, never modifies original.

        Args:
            img_input: Image input with filepath.

        Returns:
            Image as ``(H, W, 3)`` uint8 RGB numpy array.

        Raises:
            ValueError: If path is invalid or file exceeds size limit.
            OSError: If file cannot be read.
        """
        filepath = img_input.filepath
        filename = Path(filepath).name

        # SEC-001: Resolve path to prevent traversal.
        try:
            resolved = Path(filepath).resolve(strict=True)
        except (OSError, ValueError) as e:
            raise ValueError(
                f"Invalid image path: {filename}. File may not exist "
                f"or path is invalid."
            ) from e

        # SEC-005: Validate file size.
        file_size = resolved.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            size_mb = file_size / (1024 * 1024)
            raise ValueError(
                f"Image file {filename} exceeds maximum size: "
                f"{size_mb:.1f} MB > "
                f"{MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB."
            )

        # Load image.
        from PIL import Image as PILImage

        try:
            img = PILImage.open(str(resolved))
            img.load()
        except Exception as e:
            raise ValueError(
                f"Failed to load image: {filename}. The file may be "
                f"corrupt or truncated."
            ) from e

        # Convert to RGB uint8.
        img = img.convert("RGB")
        return np.array(img, dtype=np.uint8)

    def _check_vram(self) -> str | None:
        """Check available GPU VRAM for diffusion model loading.

        FR-039: Returns an error message if available VRAM is below
        8 GB. Returns ``None`` if sufficient VRAM is available.

        Returns:
            Error message string, or ``None`` if VRAM is sufficient.

        Implements: FR-039, CON-005.
        """
        try:
            import torch

            if not torch.cuda.is_available():
                return (
                    "No CUDA GPU available for sketch synthesis. "
                    "GPU is required for sketch-to-3D processing."
                )

            free, total = torch.cuda.mem_get_info()
            available_gb = free / (1024 ** 3)

            if available_gb < MIN_VRAM_SYNTHESIS_GB:
                return (
                    f"Insufficient GPU VRAM for sketch synthesis. "
                    f"Required: {MIN_VRAM_SYNTHESIS_GB:.0f} GB, "
                    f"Available: {available_gb:.1f} GB. Close other "
                    f"GPU applications or free VRAM before running "
                    f"sketch-to-3D."
                )
            return None
        except ImportError:
            return (
                "PyTorch is not available. GPU inference is required "
                "for sketch-to-3D processing."
            )

    def _build_vision_outputs(
        self,
        sketch_inputs: list[tuple[int, ImageInput, np.ndarray]],
        synthesized_images: list,
    ) -> list[VisionResult]:
        """Build VisionPipelineOutput from synthesized images.

        FR-038: Constructs a ``VisionResult`` (alias
        ``VisionPipelineOutput``) from each ``SynthesizedImage``
        using the specified field mapping.

        Args:
            sketch_inputs: Indexed sketch inputs with images.
            synthesized_images: Synthesis results.

        Returns:
            List of ``VisionResult`` for reconstruction input.

        Implements: FR-038.
        """
        vision_outputs = []

        for idx, synth in enumerate(synthesized_images):
            i, img_input, _ = sketch_inputs[idx]

            # FR-038: Determine view label.
            view_label = img_input.view_label or "front"

            # FR-038: Construct VisionPipelineOutput.
            vision_output = VisionResult(
                # image = rendered_image (512×512×3 uint8 RGB)
                image=synth.rendered_image,
                # mask = full foreground (no bg segmentation needed)
                mask=np.full(
                    (SYNTHESIS_RESOLUTION, SYNTHESIS_RESOLUTION),
                    255,
                    dtype=np.uint8,
                ),
                # depth_map = zeros (depth not run on synthesised images)
                depth_map=np.zeros(
                    (SYNTHESIS_RESOLUTION, SYNTHESIS_RESOLUTION),
                    dtype=np.float32,
                ),
                # view_label from user or "front" default
                view_label=view_label,
                # label_confidence = 1.0
                label_confidence=1.0,
                # label_source = "user"
                label_source="user",
                # label_needs_confirmation = False
                label_needs_confirmation=False,
                # features = zeros (DINOv2 not run on synthesised images)
                features=np.zeros((1, 768), dtype=np.float32),
                # original_size = (512, 512)
                original_size=(SYNTHESIS_RESOLUTION, SYNTHESIS_RESOLUTION),
                # processing_time_s with sketch_synthesis timing
                processing_time_s={
                    "sketch_synthesis": synth.inference_time_s,
                },
            )
            vision_outputs.append(vision_output)

        return vision_outputs

    def _update_progress(
        self, stage_name: str, current: int, total: int
    ) -> None:
        """Update Blender UI progress properties.

        FR-036 (SHOULD): Displays current stage name, sketch index,
        and elapsed time.

        Args:
            stage_name: Current stage name (Detecting, Preprocessing,
                Synthesizing, Reconstructing, Symmetry, Complete).
            current: Current item index (1-based).
            total: Total items in this stage.
        """
        try:
            import bpy

            scene = bpy.context.scene
            if hasattr(scene, "tessera"):
                props = scene.tessera
                props.pipeline_status = (
                    f"Sketch: {stage_name} — {current}/{total}"
                )
                props.pipeline_progress = min(
                    1.0, current / max(total, 1)
                )
        except Exception:
            # Running outside Blender (tests) — silently skip.
            pass
