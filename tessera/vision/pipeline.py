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

"""Vision pipeline orchestrator for the Tessera vision pipeline.

Processes a batch of user-uploaded reference images through four
sequential stages: segmentation, depth estimation, view classification,
and feature extraction. Each stage uses an adapter pattern for model
swapping.

Spec: SPEC-TS-0003 (Vision Analysis Pipeline)

Public API:
    VisionPipeline — main pipeline entry point.
    VisionPipeline.process(images) -> list[VisionResult]

Implements: FR-001, FR-015, FR-016, FR-017, FR-019, FR-020, FR-022,
            CON-001–CON-008, SEC-003, SEC-004.
"""

import logging
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .depth.base import DepthAdapter
from .depth.depth_anything_adapter import DepthAnythingAdapter
from .features.base import FeatureAdapter
from .features.dinov2_adapter import DINOv2Adapter
from .preprocessing import load_and_preprocess
from .segmentation.base import SegmentationAdapter
from .segmentation.sam2_adapter import SAM2Adapter
from .types import (
    MAX_BATCH_SIZE,
    GPUNotAvailableError,
    ImageInput,
    ImageLoadError,
    PipelineError,
    VisionResult,
)
from .view_classifier.base import ViewClassifierAdapter
from .view_classifier.silhouette_classifier import (
    SilhouetteClassifier,
    resolve_view_label,
)

logger = logging.getLogger("tessera.vision")


class VisionPipeline:
    """Orchestrates the four-stage vision analysis pipeline.

    Stages execute sequentially to avoid concurrent GPU memory
    pressure (FR-015, CON-002):

        1. Segmentation (SAM 2)
        2. Depth estimation (Depth Anything V2)
        3. View classification (silhouette heuristic)
        4. Feature extraction (DINOv2)

    Each stage loads its model, processes all images, then unloads
    before the next stage begins (FR-016, FR-017).

    Usage::

        pipeline = VisionPipeline()
        results = pipeline.process([
            ImageInput(filepath="/path/to/img.jpg", view_label="front"),
        ])

    Custom adapters can be injected via the constructor (FR-018, §10.2)::

        pipeline = VisionPipeline(segmentation_adapter=FastSAMAdapter())

    Implements: FR-001, FR-015–FR-020, FR-022, CON-001–CON-008.
    """

    def __init__(
        self,
        segmentation_adapter: Optional[SegmentationAdapter] = None,
        depth_adapter: Optional[DepthAdapter] = None,
        view_classifier_adapter: Optional[ViewClassifierAdapter] = None,
        feature_adapter: Optional[FeatureAdapter] = None,
    ) -> None:
        """Initialise the vision pipeline with optional custom adapters.

        Default adapters: SAM 2 Large, Depth Anything V2 Small,
        Silhouette Classifier, DINOv2 ViT-B/14.

        Args:
            segmentation_adapter: Custom segmentation adapter (FR-018).
            depth_adapter: Custom depth estimation adapter (FR-018).
            view_classifier_adapter: Custom view classifier (FR-018).
            feature_adapter: Custom feature extraction adapter (FR-018).
        """
        self._segmentation = segmentation_adapter or SAM2Adapter()
        self._depth = depth_adapter or DepthAnythingAdapter()
        self._view_classifier = view_classifier_adapter or SilhouetteClassifier()
        self._feature = feature_adapter or DINOv2Adapter()

    def process(self, images: list[ImageInput]) -> list[VisionResult]:
        """Process a batch of images through the full vision pipeline.

        FR-001: Accepts 1–6 images. Raises ``PipelineError`` for empty
        or oversized batches.

        FR-015: Stages execute sequentially — segmentation, depth,
        view classification, feature extraction.

        FR-022: Validates GPU availability before starting.

        Args:
            images: List of ``ImageInput`` objects (1–6 items).

        Returns:
            list[VisionResult]: One result per successfully processed
                image. Images that fail to load (EC-003) are skipped.

        Raises:
            PipelineError: If the image list is empty, exceeds
                ``MAX_BATCH_SIZE``, or all images fail to load.
            GPUNotAvailableError: If no CUDA/ROCm GPU is detected.

        Implements: FR-001, FR-015, FR-022, CON-001–CON-008.
        """
        pipeline_start = time.monotonic()

        # FR-001: Validate batch size.
        if not images:
            raise PipelineError("No images provided.")
        if len(images) > MAX_BATCH_SIZE:
            raise PipelineError(
                f"Batch size {len(images)} exceeds maximum of " f"{MAX_BATCH_SIZE}."
            )

        # FR-022: Check GPU availability.
        self._check_gpu()

        num_images = len(images)

        # §11.1: Log pipeline start.
        gpu_info = self._get_gpu_info()
        logger.info(
            "Pipeline started: num_images=%d, gpu_name=%s, vram_gb=%.1f",
            num_images,
            gpu_info.get("name", "Unknown"),
            gpu_info.get("vram_gb", 0.0),
        )

        # -----------------------------------------------------------
        # Stage 0: Preprocessing
        # -----------------------------------------------------------
        preprocessed: list[dict[str, Any]] = []
        valid_indices = []
        timings_preprocessing: list[float] = []

        for i, img_input in enumerate(images):
            self._update_progress("Preprocessing", i + 1, num_images, num_images)
            t0 = time.monotonic()
            filename = Path(img_input.filepath).name
            try:
                image_array, original_size = load_and_preprocess(img_input)
                dt = time.monotonic() - t0
                timings_preprocessing.append(dt)
                preprocessed.append(
                    {
                        "input": img_input,
                        "image": image_array,
                        "original_size": original_size,
                    }
                )
                valid_indices.append(i)
                logger.debug(
                    "Preprocessing complete: filename=%s, "
                    "original_size=%s, resized_size=%s",
                    filename,
                    original_size,
                    image_array.shape[:2][::-1],
                )
            except ImageLoadError as e:
                logger.error(
                    "Image load failed: filename=%s, error_message=%s",
                    filename,
                    str(e),
                )
                timings_preprocessing.append(time.monotonic() - t0)

        # EC-003: If all images failed, raise PipelineError.
        if not preprocessed:
            raise PipelineError("No valid images could be processed.")

        n_valid = len(preprocessed)
        total_stages = 4  # seg, depth, view, features
        total_steps = total_stages * n_valid

        # -----------------------------------------------------------
        # Stage 1: Segmentation (FR-004, FR-005)
        # -----------------------------------------------------------
        masks: list[np.ndarray] = []
        timings_seg: list[float] = []

        logger.info(
            "Stage started: stage_name=segmentation, image_index=1, "
            "total_images=%d, model_name=%s",
            n_valid,
            self._segmentation.model_name,
        )

        self._segmentation.load()
        try:
            for i, item in enumerate(preprocessed):
                step = i + 1
                self._update_progress("Segmentation", step, n_valid, total_steps)
                t0 = time.monotonic()
                mask = self._segmentation.predict(item["image"])
                dt = time.monotonic() - t0
                timings_seg.append(dt)
                masks.append(mask)
                logger.info(
                    "Stage complete: stage_name=segmentation, "
                    "image_index=%d, duration_s=%.3f",
                    step,
                    dt,
                )
        finally:
            self._segmentation.unload()

        # -----------------------------------------------------------
        # Stage 2: Depth Estimation (FR-006, FR-007)
        # -----------------------------------------------------------
        depth_maps: list[np.ndarray] = []
        timings_depth: list[float] = []

        logger.info(
            "Stage started: stage_name=depth, image_index=1, "
            "total_images=%d, model_name=%s",
            n_valid,
            self._depth.model_name,
        )

        self._depth.load()
        try:
            for i, (item, mask) in enumerate(zip(preprocessed, masks)):
                step = n_valid + i + 1
                self._update_progress("Depth Estimation", i + 1, n_valid, total_steps)
                t0 = time.monotonic()
                depth = self._depth.predict(item["image"], mask)
                dt = time.monotonic() - t0
                timings_depth.append(dt)
                depth_maps.append(depth)
                logger.info(
                    "Stage complete: stage_name=depth, "
                    "image_index=%d, duration_s=%.3f",
                    i + 1,
                    dt,
                )
        finally:
            self._depth.unload()

        # -----------------------------------------------------------
        # Stage 3: View Classification (FR-008–FR-012)
        # -----------------------------------------------------------
        view_results: list[tuple[str, float, str, bool]] = []
        timings_view: list[float] = []

        logger.info(
            "Stage started: stage_name=view_classification, image_index=1, "
            "total_images=%d, model_name=%s",
            n_valid,
            self._view_classifier.model_name,
        )

        self._view_classifier.load()
        try:
            for i, (item, mask) in enumerate(zip(preprocessed, masks)):
                step = 2 * n_valid + i + 1
                self._update_progress(
                    "View Classification", i + 1, n_valid, total_steps
                )
                t0 = time.monotonic()

                img_input = item["input"]

                # FR-009: Auto-classify if no user label.
                auto_label, auto_conf = self._view_classifier.predict(
                    item["image"], mask
                )

                # Resolve final label (FR-008, FR-011, FR-012, EC-004).
                label, conf, source, needs_confirm = resolve_view_label(
                    img_input.view_label,
                    img_input.custom_azimuth,
                    img_input.custom_elevation,
                    auto_label,
                    auto_conf,
                )

                dt = time.monotonic() - t0
                timings_view.append(dt)
                view_results.append((label, conf, source, needs_confirm))

                filename = Path(img_input.filepath).name
                logger.info(
                    "View-label auto-detected: filename=%s, "
                    "predicted_label=%s, confidence=%.2f, "
                    "needs_confirmation=%s",
                    filename,
                    label,
                    conf,
                    needs_confirm,
                )
                logger.info(
                    "Stage complete: stage_name=view_classification, "
                    "image_index=%d, duration_s=%.3f",
                    i + 1,
                    dt,
                )
        finally:
            self._view_classifier.unload()

        # -----------------------------------------------------------
        # Stage 4: Feature Extraction (FR-013)
        # -----------------------------------------------------------
        features_list: list[np.ndarray] = []
        timings_feat: list[float] = []

        logger.info(
            "Stage started: stage_name=feature_extraction, image_index=1, "
            "total_images=%d, model_name=%s",
            n_valid,
            self._feature.model_name,
        )

        self._feature.load()
        try:
            for i, item in enumerate(preprocessed):
                step = 3 * n_valid + i + 1
                self._update_progress("Feature Extraction", i + 1, n_valid, total_steps)
                t0 = time.monotonic()
                feats = self._feature.predict(item["image"])
                dt = time.monotonic() - t0
                timings_feat.append(dt)
                features_list.append(feats)
                logger.info(
                    "Stage complete: stage_name=feature_extraction, "
                    "image_index=%d, duration_s=%.3f",
                    i + 1,
                    dt,
                )
        finally:
            self._feature.unload()

        # -----------------------------------------------------------
        # Assemble VisionResult objects (FR-014, FR-019)
        # -----------------------------------------------------------
        results: list[VisionResult] = []
        confirm_count = 0

        for i in range(n_valid):
            item = preprocessed[i]
            label, conf, source, needs_confirm = view_results[i]
            if needs_confirm:
                confirm_count += 1

            # FR-019: Per-stage timing.
            processing_time_s = {
                "preprocessing": (
                    timings_preprocessing[valid_indices[i]]
                    if i < len(timings_preprocessing)
                    else 0.0
                ),
                "segmentation": timings_seg[i],
                "depth": timings_depth[i],
                "view_classification": timings_view[i],
                "feature_extraction": timings_feat[i],
            }

            result = VisionResult(
                image=item["image"],
                mask=masks[i],
                depth_map=depth_maps[i],
                view_label=label,
                label_confidence=conf,
                label_source=source,
                label_needs_confirmation=needs_confirm,
                features=features_list[i],
                original_size=item["original_size"],
                processing_time_s=processing_time_s,
            )
            results.append(result)

        # §11.1: Log pipeline completion.
        total_time = time.monotonic() - pipeline_start
        logger.info(
            "Pipeline complete: num_images=%d, total_time_s=%.3f, "
            "images_needing_confirmation=%d",
            n_valid,
            total_time,
            confirm_count,
        )

        # Final progress update.
        self._update_progress("Complete", n_valid, n_valid, total_steps)

        return results

    def _check_gpu(self) -> None:
        """Validate that a GPU Tessera can run inference on is available.

        FR-022: Must be called before any model loading.

        In v1 that means NVIDIA CUDA. AMD (ROCm) and Apple Silicon (Metal)
        GPUs are detected by SPEC-TS-0001 FR-008 but no adapter implements
        a device path for them, so they are rejected here with an explicit
        message rather than left to fail inside ``torch`` at model load
        (TASK-TS-0022).

        Raises:
            GPUNotAvailableError: If no usable GPU is detected.
        """
        from ..gpu_detection import get_gpu_info, unsupported_backend_message

        gpu = get_gpu_info()
        message = unsupported_backend_message(gpu)

        if message is not None:
            raise GPUNotAvailableError(f"Vision pipeline cannot start. {message}")

    def _get_gpu_info(self) -> dict:
        """Get GPU info for logging purposes.

        Returns:
            dict: GPU info dict from ``gpu_detection.get_gpu_info()``.
        """
        try:
            from ..gpu_detection import get_gpu_info

            return get_gpu_info()
        except Exception:
            return {"name": "Unknown", "vram_gb": 0.0, "backend": None}

    def _update_progress(
        self,
        stage_name: str,
        image_index: int,
        total_images: int,
        total_steps: int,
    ) -> None:
        """Update Blender UI progress properties.

        FR-020 (SHOULD): Updates ``pipeline_status`` and
        ``pipeline_progress`` on ``bpy.context.scene.tessera``.

        CON-008: Uses thread-safe property updates only — no
        ``bpy.ops`` calls.

        Args:
            stage_name: Human-readable stage name.
            image_index: Current image number (1-based).
            total_images: Total images in batch.
            total_steps: Total processing steps across all stages.
        """
        try:
            import bpy

            scene = bpy.context.scene
            if hasattr(scene, "tessera"):
                props = scene.tessera
                # CON-008: Thread-safe property updates only.
                props.pipeline_status = (
                    f"{stage_name} — Image {image_index}/{total_images}"
                )
                # Compute overall progress as fraction of total steps.
                # The step number is derived from the current stage and
                # image index.
                props.pipeline_progress = min(1.0, image_index / max(total_steps, 1))
        except Exception:
            # Running outside Blender (tests) — silently skip.
            pass
