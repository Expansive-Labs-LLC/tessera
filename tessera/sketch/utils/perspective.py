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

"""Contour-based perspective correction for photographed paper sketches.

Detects the largest quadrilateral contour (paper boundary) and applies
a perspective warp to produce a rectangular output image.

Spec: SPEC-TS-0010 (Sketch-to-3D Pathway)

Public API:
    correct_perspective — detect paper boundary and warp (FR-012, FR-013)

Implements: FR-012, FR-013.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger("tessera.sketch")


def correct_perspective(
    image: np.ndarray,
) -> tuple[np.ndarray, bool]:
    """Attempt perspective correction on a photographed paper sketch.

    Detects the largest quadrilateral contour in the image (assumed to
    be the paper boundary), computes a perspective transform, and warps
    the image to a rectangular output.

    If no suitable quadrilateral is found, the original image is
    returned unchanged with ``corrected=False`` (FR-013).

    Args:
        image: Input image, ``(H, W)`` uint8 grayscale or
            ``(H, W, 3)`` uint8 RGB.

    Returns:
        Tuple of ``(corrected_image, was_corrected)``.

    Implements: FR-012, FR-013.
    """
    # Work on grayscale for contour detection.
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image.copy()

    # Apply Gaussian blur to reduce noise before edge detection.
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # Dilate to close gaps in contours.
    kernel = np.ones((3, 3), dtype=np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=2)

    # Find contours.
    contours, _ = cv2.findContours(
        edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        logger.debug(
            "Perspective correction skipped: no paper boundary detected"
        )
        return image, False

    # Sort contours by area, largest first.
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    quad = None
    for contour in contours:
        # Approximate the contour to a polygon.
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        # FR-012(a): Detect the largest quadrilateral contour.
        if len(approx) == 4:
            # Check that the contour is large enough (≥ 10% of image area).
            contour_area = cv2.contourArea(approx)
            image_area = gray.shape[0] * gray.shape[1]
            if contour_area >= 0.1 * image_area:
                quad = approx
                break

    if quad is None:
        # FR-013: No quadrilateral found.
        logger.debug(
            "Perspective correction skipped: no paper boundary detected"
        )
        return image, False

    logger.debug(
        "Perspective correction: contour_corners_found=%d",
        len(quad),
    )

    # Order points: top-left, top-right, bottom-right, bottom-left.
    pts = quad.reshape(4, 2).astype(np.float32)
    ordered = _order_points(pts)

    # Compute output dimensions from the ordered quadrilateral.
    width_a = np.linalg.norm(ordered[2] - ordered[3])
    width_b = np.linalg.norm(ordered[1] - ordered[0])
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(ordered[1] - ordered[2])
    height_b = np.linalg.norm(ordered[0] - ordered[3])
    max_height = int(max(height_a, height_b))

    if max_width < 64 or max_height < 64:
        logger.debug(
            "Perspective correction skipped: detected quad too small "
            "(%dx%d)",
            max_width,
            max_height,
        )
        return image, False

    # FR-012(b): Compute perspective transform.
    dst = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(ordered, dst)

    # FR-012(c): Warp the image.
    warped = cv2.warpPerspective(image, transform, (max_width, max_height))

    return warped, True


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order four points as top-left, top-right, bottom-right, bottom-left.

    Uses the sum and difference of coordinates to determine corner
    positions.

    Args:
        pts: Array of shape ``(4, 2)`` with ``(x, y)`` coordinates.

    Returns:
        Ordered array of shape ``(4, 2)`` float32.
    """
    ordered = np.zeros((4, 2), dtype=np.float32)

    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).flatten()

    ordered[0] = pts[np.argmin(s)]   # Top-left: smallest sum
    ordered[2] = pts[np.argmax(s)]   # Bottom-right: largest sum
    ordered[1] = pts[np.argmin(d)]   # Top-right: smallest difference
    ordered[3] = pts[np.argmax(d)]   # Bottom-left: largest difference

    return ordered
