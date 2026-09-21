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

"""Silhouette-based view-direction classifier for the Tessera vision pipeline.

A lightweight heuristic classifier that infers canonical view labels
from the segmentation mask silhouette shape and spatial features.
No GPU model required — runs on CPU.

Spec: SPEC-TS-0003.

Public API:
    SilhouetteClassifier — silhouette + up-vector heuristic view classifier.

Implements: FR-008, FR-009, FR-010, FR-011, FR-012, EC-004.
"""

import logging
from typing import Optional

import numpy as np

from .base import ViewClassifierAdapter

logger = logging.getLogger("tessera.vision")

# FR-011 / FR-012: Confidence threshold for automatic acceptance.
_AUTO_ACCEPT_THRESHOLD = 0.80


class SilhouetteClassifier(ViewClassifierAdapter):
    """Silhouette-based view-direction classifier.

    Analyses the segmentation mask to infer a canonical view label
    using geometric heuristics:

    1. Compute the bounding-box aspect ratio of the mask.
    2. Compute the centroid position relative to the bounding box.
    3. Compute the vertical symmetry score.
    4. Map these features to a predicted view label with confidence.

    This is a lightweight CPU-only classifier — no neural network
    weights are required.

    Implements: FR-009, FR-010, EC-004.
    """

    def __init__(self) -> None:
        """Initialise the silhouette classifier."""
        self._loaded = False

    @property
    def model_name(self) -> str:
        """Return the human-readable model name."""
        return "Silhouette Classifier"

    def load(self) -> None:
        """Load classifier resources (no-op for heuristic classifier)."""
        self._loaded = True
        logger.debug("Model loaded to GPU: model_name=%s", self.model_name)

    def predict(
        self, image: np.ndarray, mask: np.ndarray
    ) -> tuple[str, float]:
        """Classify view direction from segmentation mask silhouette.

        Args:
            image: Preprocessed RGB image, ``(H, W, 3)`` uint8.
            mask: Binary segmentation mask, ``(H, W)`` uint8, 0/255.

        Returns:
            tuple: ``(label, confidence)`` where ``label`` is a PRD §6
                vocabulary string and ``confidence`` is in ``[0.0, 1.0]``.

        Implements: FR-009, FR-010.
        """
        h, w = mask.shape[:2]

        # Find foreground pixels.
        fg_ys, fg_xs = np.where(mask > 0)

        if len(fg_xs) == 0:
            # No foreground — low confidence default.
            return "front", 0.3

        # Compute bounding box.
        x_min, x_max = int(fg_xs.min()), int(fg_xs.max())
        y_min, y_max = int(fg_ys.min()), int(fg_ys.max())
        bb_w = max(x_max - x_min, 1)
        bb_h = max(y_max - y_min, 1)
        aspect_ratio = bb_w / bb_h

        # Compute centroid relative position within image.
        cx = fg_xs.mean() / max(w, 1)
        cy = fg_ys.mean() / max(h, 1)

        # Compute vertical symmetry score.
        mid_x = (x_min + x_max) // 2
        left_half = mask[:, x_min:mid_x]
        right_half = mask[:, mid_x : x_max + 1]
        right_flipped = np.fliplr(right_half)

        # Pad to same width for comparison.
        min_w = min(left_half.shape[1], right_flipped.shape[1])
        if min_w > 0:
            left_half = left_half[:, :min_w]
            right_flipped = right_flipped[:, :min_w]
            symmetry = float(
                np.mean(left_half == right_flipped)
            )
        else:
            symmetry = 0.5

        # Compute fill ratio (foreground area / bounding box area).
        fill_ratio = len(fg_xs) / max(bb_w * bb_h, 1)

        # Heuristic classification based on geometric features.
        label, confidence = self._classify_from_features(
            aspect_ratio, cx, cy, symmetry, fill_ratio
        )

        return label, confidence

    def unload(self) -> None:
        """Release classifier resources (no-op for heuristic classifier)."""
        self._loaded = False
        logger.debug("Model unloaded from GPU: model_name=%s", self.model_name)

    def _classify_from_features(
        self,
        aspect_ratio: float,
        cx: float,
        cy: float,
        symmetry: float,
        fill_ratio: float,
    ) -> tuple[str, float]:
        """Map geometric features to a view label prediction.

        Uses a rule-based classifier with confidence estimation based on
        how strongly features match expected view characteristics.

        Args:
            aspect_ratio: Bounding box width/height ratio.
            cx: Centroid x position normalised to [0, 1].
            cy: Centroid y position normalised to [0, 1].
            symmetry: Vertical symmetry score [0, 1].
            fill_ratio: Foreground fill ratio within bounding box.

        Returns:
            tuple: ``(label, confidence)``.
        """
        # Top view: very wide aspect ratio, high cy (top of image = low cy
        # for overhead shots where object is foreshortened).
        if aspect_ratio > 1.5 and cy < 0.4:
            return "top", min(0.65 + symmetry * 0.2, 1.0)

        # Bottom view: wide aspect ratio, centroid in lower half.
        if aspect_ratio > 1.5 and cy > 0.6:
            return "bottom", min(0.55 + symmetry * 0.15, 1.0)

        # Highly symmetrical and roughly centred — likely front or back.
        if symmetry > 0.85 and 0.4 < cx < 0.6:
            # Front is more common default.
            return "front", min(0.7 + symmetry * 0.15, 1.0)

        # Left: centroid skewed right (object seen from left shows
        # more mass on the right).
        if cx > 0.55 and symmetry < 0.7:
            return "left", min(0.5 + (cx - 0.5) * 2, 1.0)

        # Right: centroid skewed left.
        if cx < 0.45 and symmetry < 0.7:
            return "right", min(0.5 + (0.5 - cx) * 2, 1.0)

        # Isometric: moderate aspect ratio with lower symmetry.
        if 0.7 < aspect_ratio < 1.3 and 0.5 < symmetry < 0.8:
            return "isometric", min(0.45 + fill_ratio * 0.2, 1.0)

        # Front-left / front-right based on slight centroid offset.
        if cx > 0.52:
            return "front-left", 0.45
        if cx < 0.48:
            return "front-right", 0.45

        # Default: front with modest confidence.
        return "front", 0.5


def resolve_view_label(
    image_input_view_label: Optional[str],
    image_input_custom_azimuth: Optional[float],
    image_input_custom_elevation: Optional[float],
    auto_label: str,
    auto_confidence: float,
) -> tuple[str, float, str, bool]:
    """Resolve final view label from user input and auto-classification.

    Handles user-supplied labels, custom angles (EC-004), and
    auto-detection with confidence thresholding (FR-011, FR-012).

    Args:
        image_input_view_label: User's label or ``None`` for auto.
        image_input_custom_azimuth: Custom azimuth degrees (EC-004).
        image_input_custom_elevation: Custom elevation degrees (EC-004).
        auto_label: Auto-classifier predicted label.
        auto_confidence: Auto-classifier confidence ``[0.0, 1.0]``.

    Returns:
        tuple: ``(view_label, label_confidence, label_source,
            label_needs_confirmation)``.

    Implements: FR-008, FR-009, FR-011, FR-012, EC-004.
    """
    if image_input_view_label is not None:
        # User-supplied label.
        if image_input_view_label == "custom":
            # EC-004: Normalise custom angles.
            az = image_input_custom_azimuth or 0.0
            el = image_input_custom_elevation or 0.0
            az = az % 360.0  # Normalise to [0, 360)
            el = max(-90.0, min(90.0, el))  # Clamp to [-90, 90]
            label = f"custom:{az},{el}"
        else:
            label = image_input_view_label

        return label, 1.0, "user", False

    # Auto-detected label.
    if auto_confidence >= _AUTO_ACCEPT_THRESHOLD:
        # FR-011: High confidence — accept automatically.
        return auto_label, auto_confidence, "auto", False
    else:
        # FR-012: Low confidence — flag for user confirmation.
        return auto_label, auto_confidence, "auto", True
