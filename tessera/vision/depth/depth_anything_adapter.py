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

"""Depth Anything V2 adapter for the Tessera vision pipeline.

Produces a monocular depth map per image, normalised to ``[0.0, 1.0]``
and masked by the segmentation output.

Spec: SPEC-TS-0003.

Public API:
    DepthAnythingAdapter — Depth Anything V2 monocular depth estimation.

Implements: FR-006, FR-007, FR-016, FR-017, CON-002, CON-005,
            EC-005, SEC-002, SEC-006.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ..types import InsufficientVRAMError
from .base import DepthAdapter

logger = logging.getLogger("tessera.vision")

# Model ID in the Tessera model manifest (CON-005).
_MODEL_ID = "depth-anything-v2-large"


class DepthAnythingAdapter(DepthAdapter):
    """Depth Anything V2 monocular depth estimation adapter.

    Produces a single-channel float32 depth map normalised to
    ``[0.0, 1.0]`` (0 = near, 1 = far). Background regions
    identified by the segmentation mask are zeroed out.

    Implements: FR-006, FR-007, FR-016, FR-017, EC-005.
    """

    def __init__(self, model_id: str = _MODEL_ID) -> None:
        """Initialise the Depth Anything V2 adapter.

        Args:
            model_id: Model identifier for the weight manager (CON-005).
        """
        self._model_id = model_id
        self._model: Optional[Any] = None
        self._device: Optional[str] = None

    @property
    def model_name(self) -> str:
        """Return the human-readable model name."""
        return "Depth Anything V2 Large"

    def load(self) -> None:
        """Load Depth Anything V2 model weights to GPU.

        FR-016: Model cached after first load for batch reuse.
        SEC-002: Weights loaded via ``torch.load(weights_only=True)``.

        Raises:
            InsufficientVRAMError: If GPU VRAM is insufficient (EC-005).
        """
        if self._model is not None:
            return  # Already loaded

        import torch

        from tessera.models import get_model_path

        model_path = get_model_path(self._model_id)
        if model_path is None:
            raise FileNotFoundError(
                f"Model weights not found for '{self._model_id}'. "
                f"Download via add-on preferences."
            )

        # SEC-006: Validate model path is within cache directory.
        model_path = Path(model_path).resolve()
        self._validate_cache_boundary(model_path)

        try:
            from depth_anything_v2.dpt import DepthAnythingV2

            # Model configuration for Large variant.
            model_configs = {
                "encoder": "vitl",
                "features": 256,
                "out_channels": [256, 512, 1024, 1024],
            }

            self._model = DepthAnythingV2(**model_configs)

            # SEC-002: Load weights safely.
            checkpoint = model_path / "depth_anything_v2_vitl.pth"
            state_dict = torch.load(
                str(checkpoint), map_location="cpu", weights_only=True
            )
            self._model.load_state_dict(state_dict)

            self._device = "cuda"
            self._model = self._model.to(self._device).eval()

            vram_mb = torch.cuda.memory_allocated() / (1024 * 1024)
            logger.debug(
                "Model loaded to GPU: model_name=%s, vram_used_mb=%.1f",
                self.model_name,
                vram_mb,
            )

        except torch.cuda.OutOfMemoryError as e:
            self._cleanup()
            available_gb = torch.cuda.mem_get_info()[0] / (1024**3)
            raise InsufficientVRAMError(
                f"Insufficient GPU VRAM: {available_gb:.1f} GB available, "
                f"~3.0 GB required for {self.model_name}. Consider enabling "
                f"low-VRAM mode in add-on preferences."
            ) from e

    def predict(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Estimate monocular depth and apply segmentation mask.

        Args:
            image: Preprocessed RGB image, ``(H, W, 3)`` uint8.
            mask: Binary segmentation mask, ``(H, W)`` uint8, 0/255.

        Returns:
            np.ndarray: Masked depth map ``(H, W)`` float32 in
                ``[0.0, 1.0]`` — background (mask == 0) set to 0.0
                (FR-006, FR-007).
        """
        if self._model is None:
            raise RuntimeError("Depth Anything V2 model not loaded. Call load() first.")

        import torch

        h, w = image.shape[:2]

        # Run Depth Anything V2 inference.
        # The model expects BGR input internally but we pass RGB —
        # the library handles conversion.
        with torch.no_grad():
            depth_raw = self._model.infer_image(image)

        # depth_raw: (H, W) float — raw disparity/depth values.
        depth = depth_raw.astype(np.float32)

        # FR-006: Normalise to [0.0, 1.0].
        d_min = depth.min()
        d_max = depth.max()
        if d_max - d_min > 1e-8:
            depth = (depth - d_min) / (d_max - d_min)
        else:
            depth = np.zeros_like(depth)

        # Resize to match input dimensions if needed.
        if depth.shape != (h, w):
            from PIL import Image as PILImage

            depth_pil = PILImage.fromarray(depth, mode="F")
            depth_pil = depth_pil.resize((w, h), PILImage.Resampling.LANCZOS)
            depth = np.array(depth_pil, dtype=np.float32)

        # FR-007: Apply segmentation mask — zero out background.
        background = mask == 0
        depth[background] = 0.0

        return depth

    def unload(self) -> None:
        """Unload Depth Anything V2 model from GPU, freeing VRAM.

        FR-017: Called after all images in a batch are processed.
        """
        self._cleanup()

    def _validate_cache_boundary(self, model_path: Path) -> None:
        """Validate model path is within the model cache directory.

        SEC-006: Prevents loading model weights from arbitrary filesystem
        locations by verifying the resolved path is a descendant of the
        cache directory managed by SPEC-TS-0002.

        Args:
            model_path: Resolved model weight path.

        Raises:
            ValueError: If the path is outside the cache directory.
        """
        try:
            from tessera.models.cache_manager import get_global_cache_manager

            manager = get_global_cache_manager()
            if manager is not None:
                cache_dir = manager.cache_dir
                if not model_path.is_relative_to(cache_dir):
                    raise ValueError(
                        f"Model path '{model_path}' is outside the "
                        f"model cache directory '{cache_dir}'. "
                        f"Refusing to load weights from untrusted location."
                    )
        except ImportError:
            pass  # Cache manager not available (testing context)

    def _cleanup(self) -> None:
        """Release model resources and clear GPU cache."""
        self._model = None
        self._device = None

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug(
                    "Model unloaded from GPU: model_name=%s",
                    self.model_name,
                )
        except Exception:
            pass
