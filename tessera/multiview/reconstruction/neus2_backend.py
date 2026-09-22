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

"""NeuS2 neural surface reconstruction backend.

Wraps the NeuS2 model for training an implicit surface representation
from multiple posed images and extracting a triangle mesh via
marching cubes.

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    NeuS2Backend — NeuS2 inference wrapper
"""

from __future__ import annotations

import logging
import os
import time

import numpy as np

from tessera.multiview.pose_estimation.types import CameraPose

logger = logging.getLogger("tessera.multiview")

# Model metadata — mirrors manifest entry for NeuS2.
_MODEL_NAME = "neus2-v1.0"
_WEIGHT_FILE = "neus2_v1.pth"

# FR-019: Default resolution ramp stages.
_RESOLUTION_RAMP = [64, 128]

# FR-019: Convergence criterion — mean absolute loss change.
_CONVERGENCE_THRESHOLD = 1e-5
_CONVERGENCE_WINDOW = 500

# FR-019: Logging interval for training progress.
_LOG_INTERVAL_STEPS = 2000


class NeuS2Backend:
    """NeuS2 neural surface reconstruction backend.

    Loads NeuS2 model weights, trains an implicit surface from
    multiple posed images with depth supervision, and extracts a
    triangle mesh via marching cubes.

    Args:
        cache_dir: Absolute path to the model weight cache directory.
            NeuS2 weights are expected at ``<cache_dir>/neus2/<filename>``.

    Implements: FR-018, FR-019, FR-020, CON-001, CON-005, CON-009,
        SEC-002.
    """

    def __init__(self, cache_dir: str) -> None:
        """Initialise the NeuS2 backend.

        Args:
            cache_dir: Path to model weight cache directory.
        """
        self._cache_dir = cache_dir
        self._model = None

    def _weight_path(self) -> str:
        """Return path to NeuS2 weight file."""
        return os.path.join(self._cache_dir, "neus2", _WEIGHT_FILE)

    def weights_available(self) -> bool:
        """Check whether the NeuS2 weight file exists on disk.

        Returns:
            ``True`` if the weight file exists.
        """
        return os.path.isfile(self._weight_path())

    def train_and_extract(
        self,
        images: list[np.ndarray],
        masks: list[np.ndarray],
        depth_maps: list[np.ndarray],
        camera_poses: list[CameraPose],
        marching_cubes_resolution: int = 256,
        max_optimization_steps: int = 20000,
    ) -> tuple[np.ndarray, np.ndarray, float, int]:
        """Train NeuS2 and extract mesh via marching cubes.

        Trains the implicit surface using a progressive resolution
        ramp (64³ → 128³ → target), then extracts the mesh at the
        specified grid resolution.

        Args:
            images: Masked RGB images, each ``(H, W, 3)`` uint8.
            masks: Binary masks, each ``(H, W)`` uint8.
            depth_maps: Depth maps, each ``(H, W)`` float32.
            camera_poses: Camera poses for each image.
            marching_cubes_resolution: Grid resolution for mesh
                extraction (128, 256, or 512).
            max_optimization_steps: Maximum training steps.

        Returns:
            Tuple of ``(vertices, faces, final_loss, actual_steps)``
            where vertices is ``(N, 3)`` float32 and faces is
            ``(M, 3)`` int32.

        Raises:
            RuntimeError: If the NeuS2 package is not available.
            FileNotFoundError: If weight files are missing.

        Implements: FR-018, FR-019, FR-020.
        """
        weight_path = self._weight_path()
        if not os.path.isfile(weight_path):
            raise FileNotFoundError(
                f"NeuS2 weights not found at "
                f"{os.path.basename(weight_path)}. "
                "Download via Add-on Preferences → Tessera → "
                "Download Models."
            )

        try:
            import torch  # type: ignore[import-not-found]
        except ImportError:
            raise RuntimeError(
                "PyTorch is not available. Install PyTorch with CUDA "
                "support for NeuS2 reconstruction."
            )

        logger.info(
            "NeuS2 training started: num_views=%d, "
            "marching_cubes_resolution=%d, max_steps=%d",
            len(images),
            marching_cubes_resolution,
            max_optimization_steps,
        )
        start = time.monotonic()

        try:
            # Attempt to import the NeuS2 package
            from neus2 import NeuS2Model  # type: ignore[import-not-found]

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            # SEC-002: Load weights safely
            state_dict = torch.load(weight_path, map_location=device, weights_only=True)
            model = NeuS2Model()
            model.load_state_dict(state_dict)
            model = model.to(device)

            # Prepare camera data for NeuS2
            intrinsics = []
            extrinsics = []
            for pose in camera_poses:
                K = np.array(
                    [
                        [pose.focal_length, 0, pose.principal_point[0]],
                        [0, pose.focal_length, pose.principal_point[1]],
                        [0, 0, 1],
                    ],
                    dtype=np.float32,
                )
                intrinsics.append(K)
                # Build 4×4 extrinsic matrix
                ext = np.eye(4, dtype=np.float32)
                ext[:3, :3] = pose.rotation.astype(np.float32)
                ext[:3, 3] = pose.translation.astype(np.float32)
                extrinsics.append(ext)

            # Convert images to tensors
            img_tensors = [
                torch.from_numpy(img.astype(np.float32) / 255.0)
                .permute(2, 0, 1)
                .to(device)
                for img in images
            ]
            mask_tensors = [
                torch.from_numpy((m > 0).astype(np.float32)).unsqueeze(0).to(device)
                for m in masks
            ]
            depth_tensors = [
                torch.from_numpy(d).unsqueeze(0).to(device) for d in depth_maps
            ]

            # FR-019: Resolution ramp training
            full_ramp = _RESOLUTION_RAMP + [marching_cubes_resolution]
            steps_per_stage = max_optimization_steps // len(full_ramp)
            actual_steps = 0
            final_loss = float("inf")
            recent_losses: list[float] = []

            for stage_res in full_ramp:
                model.set_resolution(stage_res)
                for step in range(steps_per_stage):
                    loss = model.train_step(
                        images=img_tensors,
                        masks=mask_tensors,
                        depths=depth_tensors,
                        intrinsics=intrinsics,
                        extrinsics=extrinsics,
                    )
                    actual_steps += 1
                    final_loss = float(loss)
                    recent_losses.append(final_loss)

                    # Training progress logging
                    if actual_steps % _LOG_INTERVAL_STEPS == 0:
                        elapsed = time.monotonic() - start
                        logger.debug(
                            "Training progress: step=%d, loss=%.6f, " "elapsed_s=%.1f",
                            actual_steps,
                            final_loss,
                            elapsed,
                        )

                    # Convergence check
                    if len(recent_losses) >= _CONVERGENCE_WINDOW:
                        window = recent_losses[-_CONVERGENCE_WINDOW:]
                        mean_change = abs(
                            np.mean(window[: _CONVERGENCE_WINDOW // 2])
                            - np.mean(window[_CONVERGENCE_WINDOW // 2 :])
                        )
                        if mean_change < _CONVERGENCE_THRESHOLD:
                            logger.info(
                                "Convergence reached at step %d "
                                "(mean_change=%.2e < %.2e)",
                                actual_steps,
                                mean_change,
                                _CONVERGENCE_THRESHOLD,
                            )
                            break

            # FR-020: Extract mesh via marching cubes
            logger.info(
                "Marching cubes extraction: grid_resolution=%d",
                marching_cubes_resolution,
            )
            mc_start = time.monotonic()
            mesh_result = model.extract_mesh(resolution=marching_cubes_resolution)
            vertices = mesh_result.vertices.cpu().numpy().astype(np.float32)
            faces = mesh_result.faces.cpu().numpy().astype(np.int32)
            mc_duration = time.monotonic() - mc_start

            logger.info(
                "Marching cubes extraction complete: "
                "grid_resolution=%d, vertex_count=%d, face_count=%d, "
                "duration_s=%.2f",
                marching_cubes_resolution,
                len(vertices),
                len(faces),
                mc_duration,
            )

            # Cleanup model
            del model
            torch.cuda.empty_cache()

            return vertices, faces, final_loss, actual_steps

        except ImportError:
            raise RuntimeError(
                "NeuS2 package is not installed. Bundle the NeuS2 "
                "module or install via pip for multi-view "
                "reconstruction."
            )
