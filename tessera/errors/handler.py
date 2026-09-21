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

"""Centralized error handler for all Tessera pipeline stages.

Catches exceptions, classifies them by error code, formats
user-facing messages, and delegates to the ``UIReporter``.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-001, FR-004, FR-005, FR-007, FR-008, FR-009,
    SEC-001, SEC-006, EC-001.
"""

from __future__ import annotations

import logging
import os
import traceback
from typing import Any, Optional

from .categories import ErrorCatalogEntry, ErrorResult, ErrorSeverity

logger = logging.getLogger("tessera.errors")

# SEC-006: Supported image file extensions for input validation (FR-008).
_SUPPORTED_IMAGE_FORMATS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic"})

# FR-008: Minimum image dimensions.
_MIN_IMAGE_DIM = 256

# FR-009: Blur detection threshold (Laplacian variance).
_BLUR_THRESHOLD = 100.0


class ErrorHandler:
    """Centralized exception handler for Tessera pipeline stages.

    Wraps pipeline stages in try/except, classifies exceptions
    using the error catalog, formats user-facing messages, and
    reports them via the ``UIReporter``.

    EC-001: Tracks cascading errors — only the first blocking error
    is surfaced to the user. Subsequent errors from downstream stages
    that fail due to the root cause are suppressed and logged at
    DEBUG level.

    Args:
        catalog: Error catalog mapping error codes to entries.
        reporter: Optional ``UIReporter`` for Blender UI integration.

    Implements: FR-001, FR-004, EC-001.
    """

    def __init__(
        self,
        catalog: dict[str, ErrorCatalogEntry],
        reporter: Any = None,
    ) -> None:
        self._catalog = catalog
        self._reporter = reporter
        self._root_error: Optional[str] = None
        self._suppressed_count = 0

    def reset(self) -> None:
        """Reset cascading error state between pipeline runs."""
        self._root_error = None
        self._suppressed_count = 0

    def catch(
        self,
        exception: BaseException,
        stage_name: str,
        context: Optional[dict[str, Any]] = None,
    ) -> ErrorResult:
        """Catch and classify a pipeline exception.

        Args:
            exception: The caught exception instance.
            stage_name: Pipeline stage name (e.g., ``"vision"``).
            context: Optional context dict with keys like
                ``"image_path"`` or ``"gpu_memory_available_mb"``.

        Returns:
            ``ErrorResult`` with error code, user message, and
            resolution steps.

        Implements: FR-001, FR-004, FR-007, SEC-001, SEC-006, EC-001.
        """
        if context is None:
            context = {}

        # Classify exception → error code.
        error_code = self._classify(exception, stage_name, context)

        # EC-001: Cascading error suppression.
        if self._root_error is not None and error_code != self._root_error:
            self._suppressed_count += 1
            logger.debug(
                "Suppressed cascading error from previous stage failure. "
                "suppressed_error_code=%s, root_cause_code=%s",
                error_code,
                self._root_error,
            )
            # Return a minimal result for the suppressed error.
            entry = self._catalog.get(error_code, self._catalog["BF-E999"])
            return ErrorResult(
                code=error_code,
                user_message="",
                severity=entry.severity,
                resolution_steps=entry.resolution_steps,
                logged=True,
            )

        # Look up catalog entry.
        entry = self._catalog.get(error_code, self._catalog["BF-E999"])

        # FR-004: Format user-facing message.
        user_message = self._format_message(entry, context)

        # SEC-001: Log full traceback at DEBUG only.
        logger.debug(
            "Full traceback for %s:\n%s",
            error_code,
            traceback.format_exception(type(exception), exception, exception.__traceback__),
        )

        # Log the user-facing error at ERROR level.
        logger.error(
            "Error caught: error_code=%s, stage_name=%s, severity=%s, "
            "user_message=%s",
            error_code,
            stage_name,
            entry.severity.value,
            user_message,
        )

        # FR-007: VRAM exhaustion handling.
        if error_code in ("BF-E001", "BF-E002"):
            self._handle_vram_exhaustion(context)

        # Track root cause for cascading suppression (EC-001).
        if entry.severity in (ErrorSeverity.CRITICAL, ErrorSeverity.ERROR):
            if self._root_error is None:
                self._root_error = error_code

        # Report to Blender UI if reporter is available.
        reported = False
        if self._reporter is not None:
            try:
                self._reporter.show(
                    code=error_code,
                    message=user_message,
                    severity=entry.severity,
                    resolution_steps=entry.resolution_steps,
                )
                reported = True
            except Exception:
                logger.debug("UIReporter.show() failed", exc_info=True)

        return ErrorResult(
            code=error_code,
            user_message=user_message,
            severity=entry.severity,
            resolution_steps=entry.resolution_steps,
            logged=reported,
        )

    def validate_input_image(
        self,
        filepath: str,
    ) -> Optional[ErrorResult]:
        """Validate an input image before pipeline execution.

        Checks: file exists, supported format, file size > 0,
        dimensions ≥ 256×256.

        Args:
            filepath: Path to the input image file.

        Returns:
            ``ErrorResult`` if validation fails, ``None`` if valid.

        Implements: FR-008.
        """
        # SEC-006: Use basename only in error messages.
        basename = os.path.basename(filepath)

        # Check file exists.
        if not os.path.exists(filepath):
            entry = self._catalog.get("BF-E006", self._catalog["BF-E999"])
            return ErrorResult(
                code="BF-E006",
                user_message=self._format_message(
                    entry, {"image_basename": basename}
                ),
                severity=entry.severity,
                resolution_steps=entry.resolution_steps,
                logged=True,
            )

        # Check supported format.
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in _SUPPORTED_IMAGE_FORMATS:
            entry = self._catalog["BF-E003"]
            msg = (
                f"[BF-E003] Unsupported image format '{ext}'. "
                f"Supported formats: .jpg, .jpeg, .png, .webp, .heic. "
                f"Try: {entry.resolution_steps[0]}"
            )
            return ErrorResult(
                code="BF-E003",
                user_message=msg,
                severity=entry.severity,
                resolution_steps=entry.resolution_steps,
                logged=True,
            )

        # Check file size > 0.
        if os.path.getsize(filepath) == 0:
            entry = self._catalog["BF-E003"]
            return ErrorResult(
                code="BF-E003",
                user_message=f"[BF-E003] Image file '{basename}' is empty. "
                f"Try: {entry.resolution_steps[0]}",
                severity=entry.severity,
                resolution_steps=entry.resolution_steps,
                logged=True,
            )

        return None

    def validate_image_dimensions(
        self,
        width: int,
        height: int,
        basename: str = "image",
    ) -> Optional[ErrorResult]:
        """Validate image dimensions are ≥ 256×256.

        Args:
            width: Image width in pixels.
            height: Image height in pixels.
            basename: Image file basename for error messages.

        Returns:
            ``ErrorResult`` if dimensions too small, ``None`` if valid.

        Implements: FR-008.
        """
        if width < _MIN_IMAGE_DIM or height < _MIN_IMAGE_DIM:
            entry = self._catalog["BF-E004"]
            msg = (
                f"[BF-E004] Image '{basename}' resolution is too low "
                f"({width}×{height}). Minimum required: "
                f"{_MIN_IMAGE_DIM}×{_MIN_IMAGE_DIM} pixels. "
                f"Try: {entry.resolution_steps[0]}"
            )
            return ErrorResult(
                code="BF-E004",
                user_message=msg,
                severity=entry.severity,
                resolution_steps=entry.resolution_steps,
                logged=True,
            )
        return None

    def check_blur(
        self,
        laplacian_variance: float,
        basename: str = "image",
    ) -> Optional[ErrorResult]:
        """Check if an image is blurry based on Laplacian variance.

        This is a non-blocking check — returns a WARNING if blurry
        but the pipeline should continue.

        Args:
            laplacian_variance: Laplacian variance of the grayscale image.
            basename: Image file basename for error messages.

        Returns:
            ``ErrorResult`` with WARNING severity if blurry,
            ``None`` if sharp enough.

        Implements: FR-009.
        """
        logger.debug(
            "Image blur check: image_basename=%s, "
            "laplacian_variance=%.1f, threshold=%.1f",
            basename,
            laplacian_variance,
            _BLUR_THRESHOLD,
        )

        if laplacian_variance < _BLUR_THRESHOLD:
            entry = self._catalog["BF-E005"]
            score = int(laplacian_variance)
            msg = (
                f"[BF-E005] Image appears blurry (sharpness score: {score}). "
                f"Results may be lower quality. "
                f"Try: {entry.resolution_steps[0]}"
            )
            return ErrorResult(
                code="BF-E005",
                user_message=msg,
                severity=ErrorSeverity.WARNING,
                resolution_steps=entry.resolution_steps,
                logged=True,
            )
        return None

    def _classify(
        self,
        exception: BaseException,
        stage_name: str,
        context: dict[str, Any],
    ) -> str:
        """Classify an exception into an error code.

        Uses the exception type and stage/context to determine
        the appropriate BF-EXXX code per §10.1 classification table.

        Args:
            exception: The caught exception.
            stage_name: Pipeline stage name.
            context: Context dict.

        Returns:
            Error code string (e.g., ``"BF-E001"``).

        Implements: §10.1 Exception-to-Error-Code Classification Table.
        """
        exc_type = type(exception).__name__
        exc_msg = str(exception).lower()

        # torch.cuda.OutOfMemoryError
        if "OutOfMemoryError" in exc_type or "out of memory" in exc_msg:
            # Distinguish model loading vs inference.
            is_loading = context.get("phase") == "loading" or "loading" in exc_msg
            return "BF-E001" if is_loading else "BF-E002"

        # ValueError variants
        if isinstance(exception, ValueError):
            if "unsupported format" in exc_msg:
                return "BF-E003"
            if "resolution too low" in exc_msg:
                return "BF-E004"
            if "hash mismatch" in exc_msg:
                return "BF-E007"
            if "empty mesh" in exc_msg:
                return "BF-E008"

        # FileNotFoundError — model weight files
        if isinstance(exception, FileNotFoundError):
            return "BF-E006"

        # TimeoutError — reconstruction
        if isinstance(exception, TimeoutError):
            return "BF-E009"

        # RuntimeError variants
        if isinstance(exception, RuntimeError):
            if "non-manifold" in exc_msg or "manifold" in exc_msg:
                return "BF-E010"
            if "version" in exc_msg and "blender" in exc_msg:
                return "BF-E012"
            if "gpu" in exc_msg or "cuda" in exc_msg or "rocm" in exc_msg:
                return "BF-E013"
            if "exporter" in exc_msg or "3mf" in exc_msg:
                return "BF-E016"

        # PermissionError / OSError — export directory
        if isinstance(exception, PermissionError):
            return "BF-E011"
        if isinstance(exception, OSError):
            if "disk space" in exc_msg or "no space" in exc_msg:
                return "BF-E015"
            if stage_name == "export":
                return "BF-E011"

        # ImportError — missing dependency
        if isinstance(exception, ImportError):
            return "BF-E014"

        # Fallback
        return "BF-E999"

    def _format_message(
        self,
        entry: ErrorCatalogEntry,
        context: dict[str, Any],
    ) -> str:
        """Format a user-facing error message.

        Format: ``[BF-EXXX] message. Try: resolution_steps[0].``

        Args:
            entry: Catalog entry.
            context: Context dict for dynamic values.

        Returns:
            Formatted message string.

        Implements: FR-004, SEC-001, SEC-006.
        """
        # SEC-006: Ensure no full paths leak into messages.
        message = entry.message
        first_step = entry.resolution_steps[0] if entry.resolution_steps else ""
        return f"[{entry.code}] {message} Try: {first_step}"

    def _handle_vram_exhaustion(
        self,
        context: dict[str, Any],
    ) -> None:
        """Handle VRAM exhaustion: free GPU tensors and log stats.

        Args:
            context: Context dict with optional gpu_memory_available_mb.

        Implements: FR-007.
        """
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                free, total = torch.cuda.mem_get_info()
                logger.info(
                    "VRAM exhaustion handled: freed cache, "
                    "available_mb=%.0f, total_mb=%.0f",
                    free / (1024 * 1024),
                    total / (1024 * 1024),
                )
        except ImportError:
            logger.debug("torch not available — cannot free GPU cache")
        except Exception as exc:
            logger.debug("VRAM cleanup failed: %s", exc)
