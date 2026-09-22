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

from ...models.families import DEPTH_ANYTHING_V2_VARIANTS
from ..types import InsufficientVRAMError
from .base import DepthAdapter

logger = logging.getLogger("tessera.vision")

# Model ID in the Tessera model manifest (CON-005).
#
# The Small checkpoint is the default because it is the only Depth Anything
# V2 checkpoint published under Apache-2.0. Base/Large/Giant are
# CC-BY-NC-4.0 (non-commercial only) and are licence-gated by
# tessera.models.licensing — see MODEL-LICENSES.md.
_MODEL_ID = "depth-anything-v2-small"


# Architecture configs live in tessera.models.families so that a
# user-added checkpoint (FR-025) resolves to the same table the bundled
# models use. Bundled ids map to their encoder here.
_BUNDLED_VARIANTS = {
    "depth-anything-v2-small": "vits",
    "depth-anything-v2-large": "vitl",
}

_FAMILY_ID = "depth-anything-v2"


def _resolve_variant(model_id: str, variant_id: Optional[str]) -> str:
    """Resolve which Depth Anything V2 encoder a model id refers to.

    Args:
        model_id: Manifest model id.
        variant_id: Explicit variant, if the caller knows it.

    Returns:
        str: Encoder id such as ``"vits"``.

    Raises:
        ValueError: If the variant cannot be determined.
    """
    if variant_id:
        return variant_id
    if model_id in _BUNDLED_VARIANTS:
        return _BUNDLED_VARIANTS[model_id]

    # A user-added checkpoint records its variant in the manifest entry.
    try:
        from ...models.cache_manager import get_global_cache_manager

        cache_manager = get_global_cache_manager()
        if cache_manager is not None:
            entry = cache_manager._registry.get_model(model_id)
            if entry.family == _FAMILY_ID and entry.variant:
                return entry.variant
    except Exception:  # pragma: no cover — registry unavailable
        logger.debug("Could not resolve variant for '%s' from registry", model_id)

    raise ValueError(
        f"Unknown depth model '{model_id}'. Add it as a "
        f"'{_FAMILY_ID}' model and choose its encoder "
        f"({', '.join(sorted(DEPTH_ANYTHING_V2_VARIANTS))}), or use one of "
        f"{sorted(_BUNDLED_VARIANTS)}."
    )


class DepthAnythingAdapter(DepthAdapter):
    """Depth Anything V2 monocular depth estimation adapter.

    Produces a single-channel float32 depth map normalised to
    ``[0.0, 1.0]`` (0 = near, 1 = far). Background regions
    identified by the segmentation mask are zeroed out.

    Implements: FR-006, FR-007, FR-016, FR-017, EC-005.
    """

    def __init__(
        self, model_id: str = _MODEL_ID, variant_id: Optional[str] = None
    ) -> None:
        """Initialise the Depth Anything V2 adapter.

        Args:
            model_id: Model identifier for the weight manager (CON-005).
            variant_id: Encoder to load (``"vits"``, ``"vitb"``, ``"vitl"``
                or ``"vitg"``). Resolved from the model id or the manifest
                entry when omitted.

        Raises:
            ValueError: If the variant cannot be resolved or is unknown.
        """
        variant = _resolve_variant(model_id, variant_id)
        config = DEPTH_ANYTHING_V2_VARIANTS.get(variant)
        if config is None:
            raise ValueError(
                f"Unknown Depth Anything V2 encoder '{variant}'. Known "
                f"encoders: {sorted(DEPTH_ANYTHING_V2_VARIANTS)}."
            )
        self._model_id = model_id
        self._variant = variant
        self._config: dict = config
        self._model: Optional[Any] = None
        self._device: Optional[str] = None

    @property
    def model_name(self) -> str:
        """Return the human-readable model name."""
        return self._config["display_name"]

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

        from ...models import get_model_path

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

            # Architecture configuration for the selected checkpoint.
            self._model = DepthAnythingV2(
                encoder=self._config["encoder"],
                features=self._config["features"],
                out_channels=self._config["out_channels"],
            )

            # SEC-002: Load weights safely.
            checkpoint = model_path / self._config["checkpoint"]
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
                f"~{self._config['vram_gb']:.1f} GB required for "
                f"{self.model_name}. Consider enabling low-VRAM mode in "
                f"add-on preferences."
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
            from ...models.cache_manager import get_global_cache_manager

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
