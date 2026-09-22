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

"""Strategy selector for single-image vs. multi-view reconstruction.

Routes reconstruction requests to the optimal pipeline based on
input count and view-label quality:
    - 0 images → error (FR-036)
    - 1–2 images → single-image adapter (FR-001)
    - 3–12 images → multi-view adapter (FR-001)
    - >12 images → error (FR-036)

For multi-view: runs pose estimation, enriches inputs, invokes
``MultiViewAdapter``.  On failure, falls back to the best single
image selected by mask area (FR-025 through FR-027).

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    StrategySelector — central reconstruction routing (FR-001)
"""

from __future__ import annotations

import importlib.util as _importlib_util
import logging
import os as _os
import time
from typing import TYPE_CHECKING

import numpy as np

from tessera.multiview.pose_estimation.base import PoseEstimator
from tessera.multiview.pose_estimation.types import CameraPose
from tessera.multiview.reconstruction.multiview_adapter import MultiViewAdapter
from tessera.reconstruction.adapter import (
    ReconstructionAdapter,
    VisionPipelineOutput,
)
from tessera.reconstruction.mesh_output import ReconstructionResult

if TYPE_CHECKING:
    from tessera.vision.types import VisionResult
else:
    # Load VisionResult directly from the types.py file to avoid
    # triggering tessera.vision.__init__ which eagerly imports the
    # full pipeline and its heavy dependencies (PIL, etc.).
    _types_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(__file__)),
        "vision",
        "types.py",
    )
    _spec = _importlib_util.spec_from_file_location("tessera.vision.types", _types_path)
    _vision_types = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_vision_types)
    VisionResult = _vision_types.VisionResult  # noqa: F401
    del _vision_types, _spec, _types_path, _importlib_util, _os

logger = logging.getLogger("tessera.multiview")

# FR-001: Input thresholds.
_SINGLE_IMAGE_MAX = 2
_MULTI_VIEW_MIN = 3
_MAX_IMAGES = 12

# FR-002: Minimum images for multi-view path.
_MIN_FOR_MULTIVIEW = 3


class StrategySelector:
    """Routes reconstruction to single-image or multi-view pipeline.

    Analyses the input images, their view labels, and label
    confirmation status to decide the optimal reconstruction path.
    When multi-view is selected, runs pose estimation to enrich
    inputs with camera poses before invoking the
    ``MultiViewAdapter``.

    If multi-view reconstruction fails (e.g. insufficient overlap),
    automatically falls back to single-image reconstruction using
    the best image selected by mask area (FR-025 through FR-027).

    Args:
        single_adapter: Adapter for 1–2 image reconstruction
            (``TrellisAdapter``).
        multi_adapter: Adapter for 3–12 image reconstruction
            (``MultiViewAdapter``).
        pose_estimator: Pose estimation backend
            (``HlocPoseEstimator``).

    Implements: FR-001 through FR-004, FR-025 through FR-027,
        FR-035, FR-036, EC-002, EC-004, EC-005, EC-006.
    """

    def __init__(
        self,
        single_adapter: ReconstructionAdapter,
        multi_adapter: MultiViewAdapter,
        pose_estimator: PoseEstimator,
    ) -> None:
        """Initialise the strategy selector.

        Args:
            single_adapter: Single-image reconstruction adapter.
            multi_adapter: Multi-view reconstruction adapter.
            pose_estimator: Camera pose estimation backend.
        """
        self._single = single_adapter
        self._multi = multi_adapter
        self._estimator = pose_estimator

    def _count_confirmed_labels(self, vision_results: list[VisionResult]) -> int:
        """Count images with confirmed (non-provisional) view labels.

        A label is confirmed when ``label_needs_confirmation`` is
        ``False``, meaning the user has either supplied or explicitly
        accepted the label.

        Args:
            vision_results: Vision pipeline outputs.

        Returns:
            Number of images with confirmed labels.

        Implements: FR-002.
        """
        return sum(1 for vr in vision_results if not vr.label_needs_confirmation)

    def _select_best_single_image(self, vision_results: list[VisionResult]) -> int:
        """Select the best image for single-image reconstruction.

        Ranks images by foreground mask area (largest = best),
        breaking ties by label confidence.

        Args:
            vision_results: Vision pipeline outputs.

        Returns:
            Index of the best image.

        Implements: FR-025, FR-026, FR-027.
        """
        best_idx = 0
        best_score = -1.0

        for i, vr in enumerate(vision_results):
            # FR-026: Score by mask area (percentage of non-zero pixels)
            mask_area = np.sum(vr.mask > 0) / max(vr.mask.size, 1)
            # Tiebreaker: label confidence
            score = mask_area + vr.label_confidence * 0.01
            if score > best_score:
                best_score = score
                best_idx = i

        logger.debug(
            "Best single image: index=%d, mask_area_score=%.3f",
            best_idx,
            best_score,
        )
        return best_idx

    def _to_pipeline_outputs(
        self, vision_results: list[VisionResult]
    ) -> list[VisionPipelineOutput]:
        """Convert VisionResult objects to VisionPipelineOutput.

        Creates ``VisionPipelineOutput`` objects from ``VisionResult``
        for compatibility with the ``ReconstructionAdapter`` interface.

        Args:
            vision_results: Vision pipeline outputs.

        Returns:
            List of ``VisionPipelineOutput`` objects.
        """
        outputs = []
        for vr in vision_results:
            output = VisionPipelineOutput(
                image=vr.image,
                mask=vr.mask,
                depth_map=vr.depth_map,
                view_label=vr.view_label,
                label_source=vr.label_source,
                label_confidence=vr.label_confidence,
                label_needs_confirmation=vr.label_needs_confirmation,
                features=vr.features,
                original_size=vr.original_size,
            )
            outputs.append(output)
        return outputs

    def _enrich_with_poses(
        self,
        outputs: list[VisionPipelineOutput],
        poses: list[CameraPose | None],
        inlier_ratio: float,
    ) -> list[VisionPipelineOutput]:
        """Enrich VisionPipelineOutput objects with camera poses.

        Attaches the ``camera_pose`` attribute to each output for
        consumption by the ``MultiViewAdapter``.  This preserves
        the existing interface without modification (CON-006).

        Args:
            outputs: Vision pipeline outputs.
            poses: Camera poses (``None`` for unregistered cameras).
            inlier_ratio: Overall pose estimation inlier ratio.

        Returns:
            The enriched outputs (modified in-place).
        """
        for output, pose in zip(outputs, poses):
            output.camera_pose = pose  # type: ignore[attr-defined]
            output._pose_inlier_ratio = inlier_ratio  # type: ignore[attr-defined]
        return outputs

    def _determine_strategy(
        self,
        n_images: int,
        n_confirmed: int,
    ) -> str:
        """Determine which reconstruction strategy to use.

        Args:
            n_images: Number of input images.
            n_confirmed: Number of confirmed view labels.

        Returns:
            Strategy name: ``"single_image"`` or ``"multi_view"``.

        Implements: FR-001, FR-002, FR-003.
        """
        if n_images <= _SINGLE_IMAGE_MAX:
            logger.info(
                "Strategy: single_image (num_images=%d <= %d)",
                n_images,
                _SINGLE_IMAGE_MAX,
            )
            return "single_image"

        if n_images >= _MIN_FOR_MULTIVIEW:
            logger.info(
                "Strategy: multi_view (num_images=%d, " "confirmed_labels=%d)",
                n_images,
                n_confirmed,
            )
            return "multi_view"

        # Should not reach here; kept for completeness
        return "single_image"

    def reconstruct(self, vision_results: list[VisionResult]) -> ReconstructionResult:
        """Run reconstruction using the optimal strategy.

        Routes to single-image or multi-view based on input count,
        handles pose estimation for multi-view, and falls back to
        single-image on multi-view failure.

        Args:
            vision_results: Vision pipeline outputs (1–12 images).

        Returns:
            ``ReconstructionResult`` with strategy metadata.

        Implements: FR-001 through FR-004, FR-025 through FR-027,
            FR-035, FR-036, EC-002, EC-004, EC-005, EC-006.
        """
        n_images = len(vision_results)
        start = time.monotonic()

        # FR-036: Input validation
        if n_images == 0:
            return ReconstructionResult(
                mesh=None,
                success=False,
                error_message=(
                    "No input images provided. Provide at least "
                    "1 image for reconstruction."
                ),
                source_adapter="strategy_selector",
            )

        if n_images > _MAX_IMAGES:
            return ReconstructionResult(
                mesh=None,
                success=False,
                error_message=(
                    f"Too many input images ({n_images}). "
                    f"Maximum supported: {_MAX_IMAGES}."
                ),
                source_adapter="strategy_selector",
            )

        n_confirmed = self._count_confirmed_labels(vision_results)

        # EC-002: Warn if many labels are unconfirmed
        unconfirmed_count = n_images - n_confirmed
        if unconfirmed_count > n_images // 2:
            logger.warning(
                "Many unconfirmed view labels (%d of %d). "
                "Reconstruction quality may be reduced. "
                "Consider confirming or correcting view labels.",
                unconfirmed_count,
                n_images,
            )

        strategy = self._determine_strategy(n_images, n_confirmed)

        # --- Single-image path ---
        if strategy == "single_image":
            best_idx = self._select_best_single_image(vision_results)
            selected = [vision_results[best_idx]]
            outputs = self._to_pipeline_outputs(selected)

            result = self._single.reconstruct(outputs)

            # FR-004: Add strategy metadata
            if result.mesh is not None:
                result.mesh.metadata["strategy"] = "single_image"
                result.mesh.metadata["strategy_reason"] = (
                    f"Input count ({n_images}) <= {_SINGLE_IMAGE_MAX}"
                )

            elapsed = time.monotonic() - start
            logger.info(
                "Reconstruction complete: strategy=single_image, "
                "success=%s, elapsed_s=%.1f",
                result.success,
                elapsed,
            )
            return result

        # --- Multi-view path ---
        logger.info(
            "Multi-view path selected: running pose estimation " "for %d images",
            n_images,
        )

        # EC-004: Warn if using minimum viable image count
        if n_images == _MIN_FOR_MULTIVIEW:
            logger.warning(
                "Using minimum image count for multi-view (%d). "
                "Reconstruction quality improves with 5+ images.",
                n_images,
            )

        # Step 1: Pose estimation
        try:
            pose_result = self._estimator.estimate_poses(vision_results)
        except Exception as exc:
            logger.warning(
                "Pose estimation failed: %s. Falling back to " "single-image path.",
                exc,
            )
            return self._fallback_single_image(vision_results, str(exc), start)

        # Check pose estimation success
        if not pose_result.success:
            logger.warning(
                "Pose estimation unsuccessful: %s. Falling back "
                "to single-image path.",
                pose_result.error_message,
            )
            return self._fallback_single_image(
                vision_results, pose_result.error_message, start
            )

        # Step 2: Enrich inputs with camera poses
        outputs = self._to_pipeline_outputs(vision_results)
        outputs = self._enrich_with_poses(
            outputs, pose_result.poses, pose_result.inlier_ratio
        )

        # Step 3: Run multi-view reconstruction
        try:
            result = self._multi.reconstruct(outputs)
        except Exception as exc:
            logger.warning(
                "Multi-view reconstruction failed: %s. Falling "
                "back to single-image path.",
                exc,
            )
            return self._fallback_single_image(vision_results, str(exc), start)

        # FR-004: Add strategy metadata
        if result.mesh is not None:
            result.mesh.metadata["strategy"] = "multi_view"
            result.mesh.metadata["strategy_reason"] = (
                f"Input count ({n_images}) >= {_MIN_FOR_MULTIVIEW}"
            )
            result.mesh.metadata["pose_estimation_inlier_ratio"] = (
                pose_result.inlier_ratio
            )
            result.mesh.metadata["pose_estimation_registered"] = (
                pose_result.num_registered
            )

        elapsed = time.monotonic() - start
        logger.info(
            "Reconstruction complete: strategy=multi_view, "
            "success=%s, elapsed_s=%.1f, registered_cameras=%d",
            result.success,
            elapsed,
            pose_result.num_registered,
        )
        return result

    def _fallback_single_image(
        self,
        vision_results: list[VisionResult],
        original_error: str,
        start_time: float,
    ) -> ReconstructionResult:
        """Fall back to single-image reconstruction.

        Selects the best image by mask area and runs single-image
        reconstruction.  Records the fallback reason in metadata.

        Args:
            vision_results: All vision pipeline outputs.
            original_error: Error from the failed multi-view attempt.
            start_time: Monotonic start time for total elapsed.

        Returns:
            ``ReconstructionResult`` with fallback metadata.

        Implements: FR-025 through FR-027.
        """
        best_idx = self._select_best_single_image(vision_results)
        selected = [vision_results[best_idx]]
        outputs = self._to_pipeline_outputs(selected)

        logger.info(
            "Fallback to single-image: selected image_index=%d",
            best_idx,
        )

        result = self._single.reconstruct(outputs)

        # FR-004, FR-035: Record strategy and fallback metadata
        if result.mesh is not None:
            result.mesh.metadata["strategy"] = "single_image_fallback"
            result.mesh.metadata["strategy_reason"] = (
                f"Multi-view failed: {original_error}"
            )
            result.mesh.metadata["fallback_from"] = "multi_view"
            result.mesh.metadata["fallback_image_index"] = best_idx

        # Add warning about fallback
        if result.warnings is None:
            result.warnings = []
        result.warnings.append(
            f"Multi-view reconstruction unavailable. "
            f"Using single-image fallback. Reason: {original_error}"
        )

        elapsed = time.monotonic() - start_time
        logger.info(
            "Fallback reconstruction complete: strategy=single_image_fallback, "
            "success=%s, elapsed_s=%.1f",
            result.success,
            elapsed,
        )
        return result
