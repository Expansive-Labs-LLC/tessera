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

"""Multi-view reconstruction adapter using NeuS2.

Implements the ``ReconstructionAdapter`` interface (SPEC-TS-0004)
for multi-view neural surface reconstruction.  Accepts ≥3 images
with estimated camera poses and produces a ``StandardMesh`` via
the NeuS2 backend.

Camera poses are passed by enriching each ``VisionPipelineOutput``
with an optional ``camera_pose`` attribute before invoking the
adapter.  This preserves the existing interface without modification
(CON-006).

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    MultiViewAdapter — ReconstructionAdapter for multi-view (FR-016)
"""

from __future__ import annotations

import logging
import time

import numpy as np

from ...multiview.pose_estimation.types import CameraPose
from ...multiview.reconstruction.neus2_backend import NeuS2Backend
from ...reconstruction.adapter import (
    ReconstructionAdapter,
    VisionPipelineOutput,
)
from ...reconstruction.mesh_output import (
    AdapterCapabilities,
    ReconstructionResult,
)
from ...reconstruction.utils.mesh_conversion import normalize_to_standard_mesh
from ...reconstruction.utils.vram_guard import VRAMGuard

logger = logging.getLogger("tessera.multiview")

# FR-017: Adapter capabilities.
_MODEL_NAME = "neus2-v1.0"
_MIN_IMAGES = 3
_MAX_IMAGES = 12
_MIN_VRAM_GB = 8.0

# FR-020: Valid marching cubes resolutions.
_VALID_MC_RESOLUTIONS = {128, 256, 512}


class MultiViewAdapter(ReconstructionAdapter):
    """Multi-view reconstruction adapter using NeuS2.

    Accepts ≥3 images with estimated camera poses (passed via
    enriched ``VisionPipelineOutput`` objects with an optional
    ``camera_pose`` attribute) and runs NeuS2 neural surface
    reconstruction with marching cubes mesh extraction.

    The adapter produces a ``StandardMesh`` via the existing
    normalisation pipeline, preserving the ``ReconstructionAdapter``
    interface from SPEC-TS-0004 (CON-006).

    Args:
        cache_dir: Absolute path to the model weight cache directory.
        marching_cubes_resolution: Grid resolution for mesh extraction
            (128, 256, or 512).  Default: 256.
        max_optimization_steps: Maximum NeuS2 training steps.
            Default: 20,000.

    Implements: FR-016 through FR-024, CON-001 through CON-006,
        CON-009, SEC-002, SEC-005.
    """

    def __init__(
        self,
        cache_dir: str,
        marching_cubes_resolution: int = 256,
        max_optimization_steps: int = 20000,
    ) -> None:
        """Initialise the multi-view adapter.

        Args:
            cache_dir: Path to model weight cache directory.
            marching_cubes_resolution: Marching cubes grid resolution.
            max_optimization_steps: Max NeuS2 training steps.
        """
        if marching_cubes_resolution not in _VALID_MC_RESOLUTIONS:
            raise ValueError(
                f"marching_cubes_resolution must be one of "
                f"{sorted(_VALID_MC_RESOLUTIONS)}, "
                f"got {marching_cubes_resolution}"
            )
        if not 5000 <= max_optimization_steps <= 50000:
            raise ValueError(
                f"max_optimization_steps must be in [5000, 50000], "
                f"got {max_optimization_steps}"
            )

        self._cache_dir = cache_dir
        self._mc_resolution = marching_cubes_resolution
        self._max_steps = max_optimization_steps
        self._backend = NeuS2Backend(cache_dir)

    def weights_available(self) -> bool:
        """Check whether NeuS2 weight files exist on disk.

        Returns:
            ``True`` if all required weight files are present.
        """
        return self._backend.weights_available()

    def _extract_poses(self, inputs: list[VisionPipelineOutput]) -> list[CameraPose]:
        """Extract camera poses from enriched VisionPipelineOutput objects.

        Camera poses are attached as an optional ``camera_pose``
        attribute by the ``StrategySelector`` before invoking this
        adapter.

        Args:
            inputs: Enriched vision pipeline outputs.

        Returns:
            List of ``CameraPose`` objects for inputs that have poses.

        Raises:
            ValueError: If fewer than 3 inputs have camera poses.
        """
        poses = []
        for i, inp in enumerate(inputs):
            pose = getattr(inp, "camera_pose", None)
            if pose is not None and isinstance(pose, CameraPose):
                poses.append(pose)
            else:
                logger.debug(
                    "Input[%d] has no camera_pose; excluded from "
                    "multi-view reconstruction",
                    i,
                )

        if len(poses) < _MIN_IMAGES:
            raise ValueError(
                f"Multi-view reconstruction requires at least "
                f"{_MIN_IMAGES} inputs with camera poses, "
                f"got {len(poses)}"
            )

        return poses

    @staticmethod
    def _compute_confidence(
        num_registered: int,
        total_cameras: int,
        inlier_ratio: float,
        final_loss: float,
    ) -> float:
        """Compute reconstruction confidence score.

        The score is a weighted combination of:
        - Camera registration ratio (40%)
        - Feature match inlier ratio (30%)
        - Inverse training loss (30%)

        Args:
            num_registered: Number of registered cameras.
            total_cameras: Total number of input cameras.
            inlier_ratio: Feature match inlier ratio.
            final_loss: Final NeuS2 training loss.

        Returns:
            Confidence score in ``[0.0, 1.0]``.

        Implements: FR-022.
        """
        reg_ratio = num_registered / max(total_cameras, 1)
        # Map loss to [0, 1] — lower loss = higher confidence
        loss_conf = max(0.0, 1.0 - min(final_loss, 1.0))

        confidence = 0.4 * reg_ratio + 0.3 * min(inlier_ratio, 1.0) + 0.3 * loss_conf
        return float(np.clip(confidence, 0.0, 1.0))

    def reconstruct(self, inputs: list[VisionPipelineOutput]) -> ReconstructionResult:
        """Run multi-view reconstruction from posed images.

        Extracts camera poses from enriched inputs, prepares masked
        images and depth maps, runs NeuS2 training + marching cubes
        extraction, and normalises the result to ``StandardMesh``.

        Args:
            inputs: 3–12 enriched ``VisionPipelineOutput`` entries
                with ``camera_pose`` attributes.

        Returns:
            ``ReconstructionResult`` with mesh on success or
            actionable error on failure.

        Implements: FR-016 through FR-024.
        """
        warnings: list[str] = []
        start = time.monotonic()

        logger.info(
            "Multi-view reconstruction started: adapter_name=%s, "
            "num_views=%d, marching_cubes_resolution=%d",
            _MODEL_NAME,
            len(inputs),
            self._mc_resolution,
        )

        try:
            # Extract camera poses from enriched inputs
            try:
                camera_poses = self._extract_poses(inputs)
            except ValueError as exc:
                return ReconstructionResult(
                    mesh=None,
                    success=False,
                    error_message=str(exc),
                    source_adapter=_MODEL_NAME,
                )

            # Filter inputs to only those with poses
            posed_inputs = [
                inp for inp in inputs if getattr(inp, "camera_pose", None) is not None
            ]

            # Prepare masked images (FR-018)
            masked_images = []
            masks = []
            depth_maps = []
            for inp in posed_inputs:
                mask_3ch = (inp.mask > 0).astype(np.uint8)[..., np.newaxis]
                masked_img = inp.image * mask_3ch
                masked_images.append(masked_img)
                masks.append(inp.mask)
                depth_maps.append(inp.depth_map)

            # SEC-005: Log by index only
            logger.info(
                "Multi-view reconstruction: %d posed images prepared",
                len(masked_images),
            )

            # VRAM check (CON-003)
            vram_ok, available_gb = VRAMGuard.check(_MIN_VRAM_GB)
            if not vram_ok:
                return ReconstructionResult(
                    mesh=None,
                    success=False,
                    error_message=(
                        f"Insufficient GPU VRAM for multi-view "
                        f"reconstruction. Required: {_MIN_VRAM_GB} GB, "
                        f"Available: {available_gb:.1f} GB. Close "
                        "other GPU applications or reduce "
                        "marching_cubes_resolution."
                    ),
                    source_adapter=_MODEL_NAME,
                )

            # Run NeuS2 (FR-018, FR-019, FR-020)
            vertices, faces, final_loss, actual_steps = self._backend.train_and_extract(
                images=masked_images,
                masks=masks,
                depth_maps=depth_maps,
                camera_poses=camera_poses,
                marching_cubes_resolution=self._mc_resolution,
                max_optimization_steps=self._max_steps,
            )

            # FR-021: Normalise to StandardMesh (center + unit-cube scale)
            elapsed = time.monotonic() - start

            # Retrieve pose estimation metadata from strategy enrichment
            pose_inlier_ratio = 0.0
            num_views_used = len(camera_poses)
            for inp in posed_inputs:
                if hasattr(inp, "_pose_inlier_ratio"):
                    pose_inlier_ratio = inp._pose_inlier_ratio
                    break

            # FR-022: Compute confidence
            confidence = self._compute_confidence(
                num_registered=num_views_used,
                total_cameras=len(inputs),
                inlier_ratio=pose_inlier_ratio,
                final_loss=final_loss,
            )

            mesh = normalize_to_standard_mesh(
                vertices=vertices,
                faces=faces,
                metadata={
                    "model_name": _MODEL_NAME,
                    "inference_time_s": elapsed,
                    "confidence": confidence,
                    "strategy": "multi_view",
                    "num_views_used": num_views_used,
                    "pose_inlier_ratio": pose_inlier_ratio,
                    "marching_cubes_resolution": self._mc_resolution,
                    "optimization_steps": actual_steps,
                },
            )

            logger.info(
                "Multi-view reconstruction complete: adapter_name=%s, "
                "total_time_s=%.1f, vertex_count=%d, face_count=%d, "
                "confidence=%.2f",
                _MODEL_NAME,
                elapsed,
                mesh.metadata["vertex_count"],
                mesh.metadata["face_count"],
                confidence,
            )

            return ReconstructionResult(
                mesh=mesh,
                success=True,
                warnings=warnings,
                source_adapter=_MODEL_NAME,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            msg = f"Multi-view reconstruction failed ({_MODEL_NAME}): {exc}"
            logger.error(msg)
            return ReconstructionResult(
                mesh=None,
                success=False,
                error_message=msg,
                warnings=warnings,
                source_adapter=_MODEL_NAME,
            )

        finally:
            # FR-023, CON-004: Release all GPU tensors
            freed_mb = VRAMGuard.cleanup_gpu()
            logger.debug("VRAM cleanup completed: memory_freed_mb=%.1f", freed_mb)

    def capabilities(self) -> AdapterCapabilities:
        """Declare multi-view adapter capabilities.

        Implements: FR-017, FR-024.
        """
        return AdapterCapabilities(
            model_name=_MODEL_NAME,
            min_images=_MIN_IMAGES,
            max_images=_MAX_IMAGES,
            requires_depth=True,
            requires_mask=True,
            min_vram_gb=_MIN_VRAM_GB,
            supported_view_labels=[
                "front",
                "back",
                "left",
                "right",
                "top",
                "bottom",
                "front-left",
                "front-right",
                "isometric",
            ],
            output_types=["mesh"],
        )
