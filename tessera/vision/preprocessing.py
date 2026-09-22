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

"""Image preprocessing for the Tessera vision pipeline.

Handles image loading, path validation, size checks, format conversion,
and resizing before pipeline inference stages.

Spec: SPEC-TS-0003 (Vision Analysis Pipeline)

Public API:
    load_and_preprocess(image_input) -> tuple[np.ndarray, tuple[int, int]]

Implements: FR-002, FR-003, SEC-001, SEC-004, SEC-005, EC-001, EC-003.
"""

import logging
from pathlib import Path

import numpy as np
from PIL import Image

from .types import (
    MAX_FILE_SIZE_BYTES,
    MAX_IMAGE_DIMENSION,
    MIN_IMAGE_DIMENSION,
    VALID_EXTENSIONS,
    ImageInput,
    ImageLoadError,
)

logger = logging.getLogger("tessera.vision")


def load_and_preprocess(
    image_input: ImageInput,
) -> tuple[np.ndarray, tuple[int, int]]:
    """Load, validate, and preprocess a single image for pipeline input.

    Steps:
        1. Validate and resolve file path (SEC-001).
        2. Check file size ≤ 50 MB (SEC-005).
        3. Validate file extension (FR-002).
        4. Load image data — HEIC via ``pillow-heif`` (AC-005).
        5. Convert to RGB uint8 ``(H, W, 3)``.
        6. Record original dimensions.
        7. Upscale if below 256 px minimum (EC-001).
        8. Downscale if above 1024 px maximum (FR-003).

    Args:
        image_input: An ``ImageInput`` instance with ``filepath`` set.

    Returns:
        tuple: ``(image_array, original_size)`` where ``image_array`` is
            ``(H, W, 3)`` uint8 RGB and ``original_size`` is
            ``(width, height)`` of the original image before any resizing.

    Raises:
        ImageLoadError: If the file cannot be read, decoded, or fails
            any validation check (EC-003, SEC-001, SEC-005).

    Implements: FR-002, FR-003, SEC-001, SEC-004, SEC-005, EC-001, EC-003.
    """
    filepath = image_input.filepath
    filename = Path(filepath).name  # basename only for logging (§11.1)

    # SEC-001: Resolve path to prevent traversal attacks.
    try:
        resolved = Path(filepath).resolve(strict=True)
    except (OSError, ValueError) as e:
        raise ImageLoadError(
            f"Failed to load image: {filename}. The file may be corrupt "
            f"or truncated."
        ) from e

    # FR-002: Validate extension.
    ext = resolved.suffix.lower()
    if ext not in VALID_EXTENSIONS:
        raise ImageLoadError(
            f"Failed to load image: {filename}. Unsupported format "
            f"'{ext}'. Supported: {', '.join(sorted(VALID_EXTENSIONS))}."
        )

    # SEC-005: Validate file size ≤ 50 MB.
    try:
        file_size = resolved.stat().st_size
    except OSError as e:
        raise ImageLoadError(
            f"Failed to load image: {filename}. The file may be corrupt "
            f"or truncated."
        ) from e

    if file_size > MAX_FILE_SIZE_BYTES:
        size_mb = file_size / (1024 * 1024)
        raise ImageLoadError(
            f"Failed to load image: {filename}. File size {size_mb:.1f} MB "
            f"exceeds maximum of {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB."
        )

    # Load image — HEIC support via pillow-heif.
    if ext == ".heic":
        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
        except ImportError as e:
            raise ImageLoadError(
                f"Failed to load image: {filename}. HEIC support requires "
                f"the 'pillow-heif' package."
            ) from e

    # EC-003: Catch corrupt / unreadable files.
    try:
        img: Image.Image = Image.open(str(resolved))
        img.load()  # Force full decode to catch truncation
    except Exception as e:
        raise ImageLoadError(
            f"Failed to load image: {filename}. The file may be corrupt "
            f"or truncated."
        ) from e

    # Convert to RGB uint8.
    img = img.convert("RGB")
    original_size = (img.width, img.height)  # (width, height)

    logger.debug(
        "Preprocessing complete: filename=%s, original_size=%s",
        filename,
        original_size,
    )

    # SEC-004: All processing on in-memory copies only — no temp files.

    # EC-001: Upscale tiny images to minimum dimension 256 px.
    w, h = img.size
    max_dim = max(w, h)
    if max_dim < MIN_IMAGE_DIMENSION:
        scale = MIN_IMAGE_DIMENSION / max_dim
        new_w = max(1, round(w * scale))
        new_h = max(1, round(h * scale))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        logger.debug(
            "Upscaled small image: filename=%s, from=%s, to=%s",
            filename,
            (w, h),
            (new_w, new_h),
        )

    # FR-003: Downscale to max dimension 1024 px.
    w, h = img.size
    max_dim = max(w, h)
    if max_dim > MAX_IMAGE_DIMENSION:
        scale = MAX_IMAGE_DIMENSION / max_dim
        new_w = max(1, round(w * scale))
        new_h = max(1, round(h * scale))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        logger.debug(
            "Resized image: filename=%s, resized_size=%s",
            filename,
            (new_w, new_h),
        )

    image_array = np.array(img, dtype=np.uint8)
    return image_array, original_size
