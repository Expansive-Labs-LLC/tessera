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

"""Sketch preprocessor — binarisation, thinning, and perspective correction.

Cleans and normalises raw sketch images through adaptive binarisation,
noise removal, line thinning, and optional perspective correction.

Spec: SPEC-TS-0010 (Sketch-to-3D Pathway)

Public API:
    SketchPreprocessor — sketch cleaning and normalisation (FR-007)

Implements: FR-007, FR-008, FR-009, FR-010, FR-011, FR-012, FR-013,
            FR-014, FR-015, CON-003.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from tessera.sketch.types import (
    MIN_LINE_CONTENT_PIXELS,
    PreprocessedSketch,
    SketchConfig,
)
from tessera.sketch.utils.perspective import correct_perspective

logger = logging.getLogger("tessera.sketch")


class SketchPreprocessor:
    """Cleans and normalises raw sketch images for synthesis.

    Processing pipeline:
        1. Perspective correction (FR-012, optional)
        2. Grayscale conversion (FR-008)
        3. Adaptive binarisation (FR-009)
        4. Inversion normalisation (FR-015)
        5. Noise removal via morphological opening (FR-010)
        6. Zhang-Suen line thinning (FR-011)

    CON-003: All operations work on in-memory copies — the
    user's original image files are never modified.

    Example::

        preprocessor = SketchPreprocessor()
        result = preprocessor.preprocess(image, config)
        print(f"Lines: {result.binary_image.shape}")

    Implements: FR-007.
    """

    def preprocess(
        self,
        image: np.ndarray,
        config: SketchConfig,
    ) -> PreprocessedSketch:
        """Clean and normalise a sketch image.

        Args:
            image: Input image, ``(H, W, 3)`` uint8 RGB.
            config: Sketch configuration with preprocessing flags.

        Returns:
            ``PreprocessedSketch`` with binarised and thinned images.

        Raises:
            ValueError: If the input image has insufficient line
                content after binarisation (EC-001).

        Implements: FR-007, FR-008–FR-015.
        """
        filename = "sketch"
        original_size = (image.shape[1], image.shape[0])

        logger.info(
            "Sketch preprocessing started: filename=%s, "
            "perspective_correction_enabled=%s",
            filename,
            config.perspective_correction,
        )

        # CON-003: Work on a copy.
        working = image.copy()
        was_perspective_corrected = False

        # --- Step 1: Perspective correction (FR-012, FR-013) ---
        if config.perspective_correction:
            corrected, was_corrected = correct_perspective(working)
            if was_corrected:
                working = corrected
                was_perspective_corrected = True
                logger.debug(
                    "Perspective correction result: was_corrected=True, "
                    "contour_corners_found=4"
                )

        # --- Step 2: Grayscale conversion (FR-008) ---
        if working.ndim == 3:
            # FR-008: Luminance weighting (0.299*R + 0.587*G + 0.114*B).
            gray = cv2.cvtColor(working, cv2.COLOR_RGB2GRAY)
        else:
            gray = working

        # --- Step 3: Adaptive binarisation (FR-009) ---
        # FR-009: Otsu's method as global threshold.
        _, binary_otsu = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # FR-009: Adaptive threshold with block size 11 and C=2 for
        # local refinement.
        binary_adaptive = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=11,
            C=2,
        )

        # Combine: pixel is a line if either method detects it.
        binary = cv2.bitwise_or(binary_otsu, binary_adaptive)

        # --- Step 4: Inversion normalisation (FR-015) ---
        # Convention: 255 = stroke/line, 0 = background.
        # If > 50% of pixels are 255, the image needs inversion
        # (it has dark background with white lines).
        non_zero_count = int(np.count_nonzero(binary))
        total_pixels = binary.shape[0] * binary.shape[1]

        logger.debug(
            "Binarization complete: non_zero_pixel_count=%d, " "total_pixel_count=%d",
            non_zero_count,
            total_pixels,
        )

        if non_zero_count > total_pixels * 0.5:
            # FR-015: Invert — white strokes on dark bg → dark bg convention.
            binary = cv2.bitwise_not(binary)
            non_zero_count = total_pixels - non_zero_count

        # --- Step 5: Noise removal (FR-010) ---
        # FR-010: Morphological opening with 3×3 kernel, applied once.
        kernel = np.ones((3, 3), dtype=np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # Recount after morphological operation.
        non_zero_count = int(np.count_nonzero(binary))

        # EC-001: Check for insufficient line content.
        if non_zero_count < MIN_LINE_CONTENT_PIXELS:
            raise ValueError(
                "Sketch preprocessing detected insufficient line content "
                f"(< {MIN_LINE_CONTENT_PIXELS} pixels). The sketch may be "
                "too faint. Try using a darker pencil or increasing image "
                "contrast."
            )

        # --- Step 6: Zhang-Suen line thinning (FR-011) ---
        # cv2.ximgproc.thinning expects input where 255 = foreground.
        try:
            thinned = cv2.ximgproc.thinning(
                binary, thinningType=cv2.ximgproc.THINNING_ZHANGSUEN
            )
        except AttributeError:
            # Fallback if cv2.ximgproc is not available — use
            # morphological erosion as an approximation.
            logger.warning(
                "cv2.ximgproc not available — using morphological " "thinning fallback"
            )
            kernel_thin = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
            thinned = binary.copy()
            prev = np.zeros_like(thinned)
            while not np.array_equal(thinned, prev):
                prev = thinned.copy()
                eroded = cv2.erode(thinned, kernel_thin)
                opened = cv2.morphologyEx(eroded, cv2.MORPH_OPEN, kernel_thin)
                subset = eroded - opened
                thinned = cv2.bitwise_or(
                    cv2.bitwise_and(thinned, cv2.bitwise_not(subset)),
                    eroded,
                )

        result = PreprocessedSketch(
            binary_image=binary,
            thinned_image=thinned,
            was_perspective_corrected=was_perspective_corrected,
            original_size=original_size,
        )

        logger.info(
            "Sketch preprocessing complete: binary_shape=%s, "
            "thinned_shape=%s, was_perspective_corrected=%s",
            binary.shape,
            thinned.shape,
            was_perspective_corrected,
        )

        return result
