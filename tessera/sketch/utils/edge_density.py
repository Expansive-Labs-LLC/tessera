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

"""Edge-density heuristic for sketch vs. photo classification.

Computes the ratio of Canny edge pixels to total pixels and the
colour-channel standard deviation to distinguish sketches (high edge
density, low colour variation) from photographs.

Spec: SPEC-TS-0010 (Sketch-to-3D Pathway)

Public API:
    compute_edge_density — Canny edge density ratio (FR-003)
    compute_color_std — colour channel standard deviation (FR-004)
    heuristic_classify — combined heuristic classification (FR-004)

Implements: FR-003, FR-004.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from tessera.sketch.types import (
    COLOR_STD_THRESHOLD,
    EDGE_DENSITY_THRESHOLD,
)

logger = logging.getLogger("tessera.sketch")


def compute_edge_density(image: np.ndarray) -> float:
    """Compute the ratio of Canny edge pixels to total pixels.

    Applies Canny edge detection on a grayscale version of the input
    image and returns the fraction of pixels that are edges.

    Args:
        image: Input image, ``(H, W, 3)`` uint8 RGB or ``(H, W)``
            uint8 grayscale.

    Returns:
        Edge density ratio in ``[0.0, 1.0]``.

    Implements: FR-003(a).
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    edges = cv2.Canny(gray, 50, 150)
    total_pixels = edges.shape[0] * edges.shape[1]
    edge_pixels = int(np.count_nonzero(edges))

    ratio = edge_pixels / max(total_pixels, 1)
    logger.debug(
        "Edge density computed: edge_pixels=%d, total_pixels=%d, "
        "edge_density_ratio=%.4f",
        edge_pixels,
        total_pixels,
        ratio,
    )
    return ratio


def compute_color_std(image: np.ndarray) -> float:
    """Compute the standard deviation across colour channels.

    For each pixel, computes the standard deviation across R, G, B
    channels, then returns the mean of those per-pixel std values.
    Low values indicate a near-grayscale image (typical of sketches).

    Args:
        image: Input image, ``(H, W, 3)`` uint8 RGB.

    Returns:
        Mean per-pixel colour channel standard deviation.

    Implements: FR-004.
    """
    if image.ndim != 3 or image.shape[2] != 3:
        return 0.0

    # Per-pixel std across channels, then mean over all pixels.
    per_pixel_std = np.std(image.astype(np.float32), axis=2)
    color_std = float(np.mean(per_pixel_std))
    logger.debug("Color std computed: color_std=%.2f", color_std)
    return color_std


def heuristic_classify(
    image: np.ndarray,
) -> tuple[bool, float, float, float]:
    """Heuristic sketch classification using edge density and colour.

    Applies the two-feature heuristic from FR-004:
    - Sketch if edge_density ≥ 0.15 AND colour_std ≤ 30.0
    - Confidence = min(1.0, edge_density * 3.0 + (1 - colour_std / 128) * 0.5)

    Args:
        image: Input image, ``(H, W, 3)`` uint8 RGB.

    Returns:
        Tuple of ``(is_sketch, confidence, edge_density_ratio, color_std)``.

    Implements: FR-004.
    """
    edge_density = compute_edge_density(image)
    color_std = compute_color_std(image)

    is_sketch = (
        edge_density >= EDGE_DENSITY_THRESHOLD
        and color_std <= COLOR_STD_THRESHOLD
    )

    if is_sketch:
        confidence = min(
            1.0,
            edge_density * 3.0 + (1.0 - color_std / 128.0) * 0.5,
        )
    else:
        # Confidence that it is NOT a sketch — invert for sketch confidence.
        confidence = max(
            0.0,
            min(
                1.0,
                edge_density * 3.0 + (1.0 - color_std / 128.0) * 0.5,
            ),
        )

    logger.debug(
        "Heuristic classification: is_sketch=%s, confidence=%.3f, "
        "edge_density_ratio=%.4f, color_std=%.2f",
        is_sketch,
        confidence,
        edge_density,
        color_std,
    )
    return is_sketch, confidence, edge_density, color_std
