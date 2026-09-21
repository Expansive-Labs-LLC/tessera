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

"""Sketch detector — photo vs. sketch/line-drawing classification.

Implements a two-stage classification approach: edge-density heuristic
followed by a lightweight CNN classifier (MobileNetV3-Small) for
confirmation when heuristic confidence is ambiguous.

Spec: SPEC-TS-0010 (Sketch-to-3D Pathway)

Public API:
    SketchDetector — binary classifier for photo vs. sketch (FR-001)

Implements: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-040,
            FR-041, CON-001, CON-004, CON-008, SEC-002, SEC-006.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from tessera.sketch.types import (
    CNN_INPUT_SIZE,
    CNN_SKETCH_THRESHOLD,
    HEURISTIC_HIGH_CONFIDENCE,
    HEURISTIC_LOW_CONFIDENCE,
    IMAGENET_MEAN,
    IMAGENET_STD,
    SketchDetectionResult,
)
from tessera.sketch.utils.edge_density import (
    compute_color_std,
    compute_edge_density,
    heuristic_classify,
)

logger = logging.getLogger("tessera.sketch")


class SketchDetector:
    """Binary classifier: photograph vs. sketch/line drawing.

    Uses a two-stage approach:
        1. Edge-density heuristic (fast, CPU-only).
        2. MobileNetV3-Small CNN classifier (GPU, loaded on demand)
           when heuristic confidence is between 0.40 and 0.85.

    The detector also determines ``sketch_type`` using heuristic
    rules (FR-040) after classification is confirmed.

    Args:
        cache_dir: Absolute path to the model weight cache directory.
            Used to resolve CNN classifier weight path via the model
            weight manager (CON-004).

    Example::

        detector = SketchDetector(cache_dir="/path/to/cache")
        result = detector.classify(image)
        print(f"Is sketch: {result.is_sketch}")

    Implements: FR-001, FR-002, FR-003, FR-005.
    """

    def __init__(self, cache_dir: str) -> None:
        self._cache_dir = cache_dir
        self._cnn_model = None

    def classify(
        self,
        image: np.ndarray,
        force_sketch: bool = False,
    ) -> SketchDetectionResult:
        """Classify an image as a photograph or sketch.

        FR-006: When ``force_sketch`` is ``True``, skips classification
        and returns a user-override result.

        FR-003: Two-stage approach — heuristic first, CNN for
        confirmation in the ambiguous confidence range [0.40, 0.85].

        Args:
            image: Input image, ``(H, W, 3)`` uint8 RGB.
            force_sketch: Override auto-detection (FR-006).

        Returns:
            ``SketchDetectionResult`` with classification outcome.

        Implements: FR-001, FR-003, FR-005, FR-006.
        """
        filename = "input_image"
        logger.info(
            "Sketch detection started: filename=%s, image_size=%s",
            filename,
            f"{image.shape[1]}x{image.shape[0]}",
        )

        # FR-006: User override bypass.
        if force_sketch:
            result = SketchDetectionResult(
                is_sketch=True,
                confidence=1.0,
                sketch_type="unknown",
                edge_density_ratio=0.0,
                detection_method="user_override",
            )
            logger.info(
                "Sketch detection result: is_sketch=%s, confidence=%.2f, "
                "sketch_type=%s, detection_method=%s",
                result.is_sketch,
                result.confidence,
                result.sketch_type,
                result.detection_method,
            )
            return result

        # FR-003(a): Edge-density heuristic.
        is_sketch, confidence, edge_density, color_std = heuristic_classify(
            image
        )

        detection_method = "heuristic"

        # FR-005: CNN confirmation when heuristic is ambiguous.
        if HEURISTIC_LOW_CONFIDENCE <= confidence <= HEURISTIC_HIGH_CONFIDENCE:
            logger.debug(
                "CNN classifier invoked: heuristic_confidence=%.3f",
                confidence,
            )
            cnn_confidence = self._classify_cnn(image)
            logger.debug(
                "CNN classifier result: heuristic_confidence=%.3f, "
                "cnn_confidence=%.3f",
                confidence,
                cnn_confidence,
            )
            is_sketch = cnn_confidence >= CNN_SKETCH_THRESHOLD
            confidence = cnn_confidence
            detection_method = "cnn"

        # FR-040: Determine sketch_type.
        sketch_type = self._determine_sketch_type(
            image, is_sketch, edge_density, color_std
        )

        result = SketchDetectionResult(
            is_sketch=is_sketch,
            confidence=confidence,
            sketch_type=sketch_type,
            edge_density_ratio=edge_density,
            detection_method=detection_method,
        )

        logger.info(
            "Sketch detection result: is_sketch=%s, confidence=%.2f, "
            "sketch_type=%s, detection_method=%s",
            result.is_sketch,
            result.confidence,
            result.sketch_type,
            result.detection_method,
        )
        return result

    # ------------------------------------------------------------------
    # CNN Classification (FR-005, FR-041)
    # ------------------------------------------------------------------

    def _classify_cnn(self, image: np.ndarray) -> float:
        """Run MobileNetV3-Small CNN classifier on the input image.

        FR-041: Resizes to 224×224, normalises with ImageNet stats,
        and produces a sigmoid score in [0.0, 1.0].

        Args:
            image: Input image, ``(H, W, 3)`` uint8 RGB.

        Returns:
            Sigmoid score where ≥ 0.5 indicates sketch.

        Implements: FR-041, CON-001, SEC-002, SEC-006.
        """
        try:
            import torch
        except ImportError:
            logger.warning(
                "PyTorch not available — falling back to heuristic-only "
                "detection"
            )
            return 0.5

        # Load CNN model if not already loaded.
        if self._cnn_model is None:
            self._cnn_model = self._load_cnn_model()

        if self._cnn_model is None:
            logger.warning(
                "CNN classifier weights not found — falling back to "
                "heuristic-only detection"
            )
            return 0.5

        # FR-041: Resize to 224×224 using bilinear interpolation.
        resized = cv2.resize(
            image,
            (CNN_INPUT_SIZE, CNN_INPUT_SIZE),
            interpolation=cv2.INTER_LINEAR,
        )

        # FR-041: Convert to float32 tensor and normalise with ImageNet stats.
        tensor = resized.astype(np.float32) / 255.0
        for c in range(3):
            tensor[:, :, c] = (
                (tensor[:, :, c] - IMAGENET_MEAN[c]) / IMAGENET_STD[c]
            )

        # Convert to (1, 3, 224, 224) tensor.
        tensor = np.transpose(tensor, (2, 0, 1))  # (3, H, W)
        tensor = np.expand_dims(tensor, axis=0)    # (1, 3, H, W)

        input_tensor = torch.from_numpy(tensor).float()

        # Run inference.
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._cnn_model.to(device)
        input_tensor = input_tensor.to(device)

        with torch.no_grad():
            output = self._cnn_model(input_tensor)

        # FR-041: Sigmoid output in [0.0, 1.0].
        score = float(torch.sigmoid(output.squeeze()).cpu())

        # Unload from GPU.
        self._cnn_model.cpu()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return score

    def _load_cnn_model(self):
        """Load MobileNetV3-Small classifier weights.

        SEC-002: Loads via ``torch.load(path, weights_only=True)``
        — never executes downloaded weights as Python code.

        SEC-006: Validates that weight path resides within the
        model cache directory.

        CON-004: Resolves path via model weight manager directory.

        Returns:
            Loaded PyTorch model, or ``None`` if weights not found.
        """
        try:
            import torch
            import torch.nn as nn
            from torchvision.models import mobilenet_v3_small
        except ImportError:
            logger.warning(
                "torchvision not available — CNN classifier disabled"
            )
            return None

        # CON-004: Resolve weight path within cache directory.
        weight_path = Path(self._cache_dir) / "mobilenetv3-sketch-classifier"

        # Look for weight files with common extensions.
        candidates = [
            weight_path / "model.safetensors",
            weight_path / "model.pt",
            weight_path / "pytorch_model.bin",
        ]

        found_path = None
        for candidate in candidates:
            if candidate.exists():
                found_path = candidate
                break

        if found_path is None:
            logger.warning(
                "CNN classifier weights not found in cache: %s",
                weight_path,
            )
            return None

        # SEC-006: Validate path resides within cache directory.
        resolved_cache = Path(self._cache_dir).resolve()
        resolved_weight = found_path.resolve()
        if not str(resolved_weight).startswith(str(resolved_cache)):
            logger.error(
                "CNN classifier weight path outside cache directory: %s",
                resolved_weight,
            )
            return None

        # Build model architecture.
        model = mobilenet_v3_small(weights=None)
        # Replace classifier head for binary classification.
        in_features = model.classifier[-1].in_features
        model.classifier[-1] = nn.Linear(in_features, 1)

        # SEC-002: Load weights safely.
        if str(found_path).endswith(".safetensors"):
            try:
                from safetensors.torch import load_file

                state_dict = load_file(str(found_path))
            except ImportError:
                logger.warning(
                    "safetensors not available — trying torch.load"
                )
                state_dict = torch.load(
                    str(found_path), weights_only=True, map_location="cpu"
                )
        else:
            state_dict = torch.load(
                str(found_path), weights_only=True, map_location="cpu"
            )

        model.load_state_dict(state_dict)
        model.eval()

        logger.debug("CNN classifier loaded from: %s", found_path.name)
        return model

    # ------------------------------------------------------------------
    # Sketch Type Determination (FR-040)
    # ------------------------------------------------------------------

    def _determine_sketch_type(
        self,
        image: np.ndarray,
        is_sketch: bool,
        edge_density: float,
        color_std: float,
    ) -> str:
        """Determine sketch medium type using heuristic rules.

        FR-040 rules:
            (a) "digital" — ≤ 4 unique grayscale values (8-level quant)
                AND no perspective correction needed.
            (b) "pencil" — grayscale (color_std ≤ 5.0) AND mean stroke
                intensity 100–200 on binarised image.
            (c) "ink" — near-grayscale (color_std ≤ 30.0) AND mean
                stroke intensity ≥ 200.
            (d) "unknown" — none of the above.

        Args:
            image: Input image, ``(H, W, 3)`` uint8 RGB.
            is_sketch: Whether the image was classified as a sketch.
            edge_density: Computed edge density ratio.
            color_std: Computed colour channel standard deviation.

        Returns:
            Sketch type string.

        Implements: FR-040.
        """
        if not is_sketch:
            return "unknown"

        # Convert to grayscale for analysis.
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image

        # FR-040(a): Check for digital sketch — ≤ 4 unique grayscale
        # values after 8-level quantisation.
        quantized = (gray // 32) * 32  # 8-level quantisation
        unique_levels = len(np.unique(quantized))
        if unique_levels <= 4:
            return "digital"

        # Compute mean stroke intensity on binarised image.
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        stroke_pixels = binary > 0
        if np.any(stroke_pixels):
            mean_stroke_intensity = float(np.mean(gray[stroke_pixels]))
        else:
            mean_stroke_intensity = 0.0

        # FR-040(b): Pencil detection.
        if color_std <= 5.0 and 100 <= mean_stroke_intensity <= 200:
            return "pencil"

        # FR-040(c): Ink detection.
        if color_std <= 30.0 and mean_stroke_intensity >= 200:
            return "ink"

        # FR-040(d): Unknown type.
        return "unknown"
