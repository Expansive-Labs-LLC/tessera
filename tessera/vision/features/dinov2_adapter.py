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

"""DINOv2 feature extraction adapter for the Tessera vision pipeline.

Extracts CLS token embeddings from DINOv2 (ViT-B/14) to provide shape
priors and symmetry cues for the reconstruction engine.

Spec: SPEC-TS-0003.

Public API:
    DINOv2Adapter — DINOv2 ViT-B/14 feature extraction.

Implements: FR-013, FR-016, FR-017, CON-002, CON-005,
            EC-005, SEC-002, SEC-006.
"""

import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ..types import InsufficientVRAMError
from .base import FeatureAdapter

logger = logging.getLogger("tessera.vision")

# Model ID in the Tessera model manifest (CON-005).
_MODEL_ID = "dinov2-vit-b14"

# DINOv2 ViT-B/14 input size and embedding dimension.
_INPUT_SIZE = 518  # 14 × 37 patches
_EMBEDDING_DIM = 768


class DINOv2Adapter(FeatureAdapter):
    """DINOv2 ViT-B/14 feature extraction adapter.

    Extracts the CLS token embedding as a ``(1, 768)`` float32 vector
    per image, providing shape priors and symmetry cues for the
    reconstruction engine.

    Implements: FR-013, FR-016, FR-017, EC-005.
    """

    def __init__(self, model_id: str = _MODEL_ID) -> None:
        """Initialise the DINOv2 adapter.

        Args:
            model_id: Model identifier for the weight manager (CON-005).
        """
        self._model_id = model_id
        self._model: Optional[Any] = None
        self._device: Optional[str] = None

    @property
    def model_name(self) -> str:
        """Return the human-readable model name."""
        return "DINOv2 ViT-B/14"

    def load(self) -> None:
        """Load DINOv2 ViT-B/14 model weights to GPU.

        FR-016: Model cached after first load for batch reuse.
        SEC-002: Weights loaded via safe mechanism.

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
            # DINOv2 can be loaded via torch.hub or directly.
            # We load state_dict from cached weights.
            # CON-001: source='local' prevents network requests
            # during pipeline execution.
            self._model = torch.hub.load(
                "facebookresearch/dinov2",
                "dinov2_vitb14",
                pretrained=False,
                source="local",
            )

            # SEC-002: Load weights safely.
            checkpoint = model_path / "dinov2_vitb14_pretrain.pth"
            if checkpoint.exists():
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
                f"~1.5 GB required for {self.model_name}. Consider enabling "
                f"low-VRAM mode in add-on preferences."
            ) from e

    def predict(self, image: np.ndarray) -> np.ndarray:
        """Extract DINOv2 CLS token feature vector from a single image.

        Args:
            image: Preprocessed RGB image, ``(H, W, 3)`` uint8.

        Returns:
            np.ndarray: Feature vector ``(1, 768)`` float32 (FR-013).
        """
        if self._model is None:
            raise RuntimeError("DINOv2 model not loaded. Call load() first.")

        import torch
        from PIL import Image as PILImage
        from torchvision import transforms

        # Resize to DINOv2 input size.
        pil_img = PILImage.fromarray(image)
        transform = transforms.Compose(
            [
                transforms.Resize(
                    (_INPUT_SIZE, _INPUT_SIZE),
                    interpolation=transforms.InterpolationMode.BICUBIC,
                ),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        )

        tensor = transform(pil_img).unsqueeze(0).to(self._device)

        with torch.no_grad():
            features = self._model(tensor)  # (1, D) CLS token

        # Convert to numpy (1, D) float32.
        result = features.cpu().numpy().astype(np.float32)

        # Ensure shape is (1, D).
        if result.ndim == 1:
            result = result.reshape(1, -1)

        return result

    def unload(self) -> None:
        """Unload DINOv2 model from GPU, freeing VRAM.

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
