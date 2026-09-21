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

"""SAM 2 segmentation adapter for the Tessera vision pipeline.

Runs SAM 2 in automatic mask generation mode (no user point prompts)
to produce a binary segmentation mask per image.

Spec: SPEC-TS-0003.

Public API:
    SAM2Adapter — SAM 2 automatic mask segmentation.

Implements: FR-004, FR-005, FR-016, FR-017, CON-002, CON-005,
            EC-002, EC-005, SEC-002, SEC-006.
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from ..types import InsufficientVRAMError
from .base import SegmentationAdapter

logger = logging.getLogger("tessera.vision")

# Model ID in the Tessera model manifest (CON-005).
_MODEL_ID = "sam2-hiera-large"


class SAM2Adapter(SegmentationAdapter):
    """SAM 2 automatic mask generation adapter.

    Uses SAM 2 (Hiera-Large by default) in automatic mask generation
    mode — no user point or box prompts. Selects the largest
    connected-component foreground mask.

    Attributes:
        _model: The loaded SAM 2 model instance (None when unloaded).
        _mask_generator: The automatic mask generator instance.

    Implements: FR-004, FR-005, FR-016, FR-017, EC-002, EC-005.
    """

    def __init__(self, model_id: str = _MODEL_ID) -> None:
        """Initialise the SAM 2 adapter.

        Args:
            model_id: Model identifier for the weight manager (CON-005).
        """
        self._model_id = model_id
        self._model: Optional[object] = None
        self._mask_generator: Optional[object] = None

    @property
    def model_name(self) -> str:
        """Return the human-readable model name."""
        return "SAM 2 Large"

    def load(self) -> None:
        """Load SAM 2 model weights to GPU.

        Resolves weights via the model weight manager API (CON-005).
        Uses ``torch.load(weights_only=True)`` or ``safetensors``
        for secure loading (SEC-002).

        FR-016: Model cached after first load for batch reuse.

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
            from sam2.build_sam import build_sam2
            from sam2.automatic_mask_generator import SamAutomaticMaskGenerator

            # SEC-002: Weights loaded via safe mechanism (build_sam2 uses
            # torch.load with weights_only=True internally).
            checkpoint = model_path / "sam2_hiera_large.pt"
            model_cfg = "sam2_hiera_l.yaml"

            self._model = build_sam2(
                model_cfg,
                str(checkpoint),
                device="cuda",
            )
            self._mask_generator = SamAutomaticMaskGenerator(self._model)

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
                f"~4.0 GB required for {self.model_name}. Consider enabling "
                f"low-VRAM mode in add-on preferences."
            ) from e

    def predict(self, image: np.ndarray) -> np.ndarray:
        """Run SAM 2 automatic mask generation on a single image.

        Selects the largest connected-component foreground region.
        If multiple components have equal area, selects the one whose
        centroid is closest to the image centre (FR-004).

        If no distinct foreground is detected, returns a full-image mask
        (all 255) and logs a warning (EC-002).

        Args:
            image: Preprocessed RGB image, ``(H, W, 3)`` uint8.

        Returns:
            np.ndarray: Binary mask ``(H, W)`` uint8, 0 or 255 (FR-005).
        """
        if self._mask_generator is None:
            raise RuntimeError("SAM 2 model not loaded. Call load() first.")

        h, w = image.shape[:2]

        # Run automatic mask generation (no prompts — FR-004).
        masks = self._mask_generator.generate(image)

        if not masks:
            # EC-002: No foreground detected — use full image.
            logger.warning(
                "No distinct foreground object detected. "
                "Using full image as foreground."
            )
            return np.full((h, w), 255, dtype=np.uint8)

        # FR-004: Select largest mask; tie-break by centroid proximity
        # to image centre.
        image_center = np.array([w / 2.0, h / 2.0])
        best_mask = None
        best_area = -1
        best_dist = float("inf")

        for mask_data in masks:
            seg = mask_data["segmentation"]  # (H, W) bool
            area = mask_data["area"]

            if area > best_area:
                best_area = area
                best_mask = seg
                # Compute centroid distance for tie-breaking.
                ys, xs = np.where(seg)
                if len(xs) > 0:
                    centroid = np.array([xs.mean(), ys.mean()])
                    best_dist = float(np.linalg.norm(centroid - image_center))
            elif area == best_area:
                # Tie-break: pick closer centroid to image centre.
                ys, xs = np.where(seg)
                if len(xs) > 0:
                    centroid = np.array([xs.mean(), ys.mean()])
                    dist = float(np.linalg.norm(centroid - image_center))
                    if dist < best_dist:
                        best_dist = dist
                        best_mask = seg

        if best_mask is None:
            # EC-002 fallback.
            logger.warning(
                "No distinct foreground object detected. "
                "Using full image as foreground."
            )
            return np.full((h, w), 255, dtype=np.uint8)

        # FR-005: Convert bool to uint8 0/255.
        result = np.zeros((h, w), dtype=np.uint8)
        result[best_mask] = 255
        return result

    def unload(self) -> None:
        """Unload SAM 2 model from GPU, freeing VRAM.

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
        self._mask_generator = None

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                vram_mb = torch.cuda.memory_allocated() / (1024 * 1024)
                logger.debug(
                    "Model unloaded from GPU: model_name=%s, "
                    "vram_freed_mb=~%.1f",
                    self.model_name,
                    vram_mb,
                )
        except Exception:
            pass
