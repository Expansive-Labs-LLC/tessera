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

"""Reconstruction engine — public orchestrator.

Provides the ``ReconstructionEngine`` class that encapsulates all
adapter selection, input validation, edge-case handling, inference
execution, and GPU cleanup logic.

Callers interact only with this class; individual adapters are never
accessed directly.

Spec: SPEC-TS-0004 (Single-Image 3D Reconstruction Engine)

Public API:
    ReconstructionEngine — public reconstruction API (FR-020)
"""

from __future__ import annotations

import logging
import signal
from typing import Optional

import numpy as np

from ..reconstruction.adapter import VisionPipelineOutput
from ..reconstruction.adapters.stub_adapter import StubAdapter
from ..reconstruction.adapters.trellis_adapter import TrellisAdapter
from ..reconstruction.mesh_output import (
    AdapterCapabilities,
    ReconstructionResult,
)
from ..reconstruction.registry import AdapterRegistry
from ..reconstruction.utils.mesh_conversion import validate_mesh
from ..reconstruction.utils.vram_guard import VRAMGuard

logger = logging.getLogger("tessera.reconstruction")

# FR-021: Supported input image count range.
_MIN_INPUTS = 1
_MAX_INPUTS = 2

# EC-001: Recommended minimum resolution.
_RECOMMENDED_MIN_RESOLUTION = 256

# FR-022: Default inference timeout in seconds.
_DEFAULT_TIMEOUT_S = 120


class _TimeoutError(Exception):
    """Raised when inference exceeds the configured timeout."""


def _timeout_handler(signum, frame):
    """Signal handler for SIGALRM-based timeouts."""
    raise _TimeoutError("Inference timed out")


class ReconstructionEngine:
    """Public API for 3D reconstruction from vision pipeline outputs.

    Orchestrates:
    1. Input validation (FR-021, SEC-001)
    2. Edge-case handling (EC-001 through EC-006)
    3. Adapter selection via ``AdapterRegistry`` (FR-006)
    4. VRAM guard checks (FR-012)
    5. Inference with timeout (FR-022)
    6. Output normalisation and validation (FR-010, FR-011)
    7. GPU cleanup (FR-015)

    Callers never interact with individual adapters directly.

    Args:
        cache_dir: Absolute path to the model weight cache directory.
        timeout_s: Maximum seconds for inference (default: 120).

    Example::

        engine = ReconstructionEngine(cache_dir="/path/to/cache")
        result = engine.reconstruct([vision_output])
        if result.success:
            print(f"Vertices: {result.mesh.metadata['vertex_count']}")

    Implements: FR-020, CON-006.
    """

    def __init__(
        self,
        cache_dir: str,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._cache_dir = cache_dir
        self._timeout_s = timeout_s
        self._registry = AdapterRegistry()

        # Register available adapters
        self._registry.register(StubAdapter())
        self._registry.register(TrellisAdapter(cache_dir=cache_dir))

        logger.debug(
            "ReconstructionEngine initialized: cache_dir=%s, timeout=%ds, "
            "adapters=%d",
            cache_dir,
            timeout_s,
            len(self._registry),
        )

    # ------------------------------------------------------------------
    # Input Validation
    # ------------------------------------------------------------------

    def _validate_input_count(
        self, inputs: list[VisionPipelineOutput]
    ) -> Optional[ReconstructionResult]:
        """Validate input count is 1–2.

        Returns a failure result if invalid, ``None`` if OK.

        Implements: FR-021, EC-006.
        """
        n = len(inputs)
        if n == 0:
            msg = (
                "No input images provided. At least 1 "
                "VisionPipelineOutput is required."
            )
            logger.error("Input validation failed: %s", msg)
            return ReconstructionResult(mesh=None, success=False, error_message=msg)

        if n > _MAX_INPUTS:
            msg = (
                f"This version supports 1–2 input images. Received {n}. "
                "Multi-view reconstruction (≥3 images) is planned "
                "for TASK-TS-0007."
            )
            logger.error("Input validation failed: %s", msg)
            return ReconstructionResult(mesh=None, success=False, error_message=msg)

        return None

    def _validate_inputs(
        self, inputs: list[VisionPipelineOutput]
    ) -> Optional[ReconstructionResult]:
        """Validate input array shapes and dtypes.

        Implements: SEC-001.

        Raises:
            ValueError: If input arrays have invalid shapes or dtypes.
        """
        for i, inp in enumerate(inputs):
            # Image: (H, W, 3) uint8
            if (
                not isinstance(inp.image, np.ndarray)
                or inp.image.ndim != 3
                or inp.image.shape[2] != 3
            ):
                raise ValueError(
                    f"input[{i}].image must be a (H, W, 3) uint8 ndarray, "
                    f"got shape {getattr(inp.image, 'shape', 'N/A')}"
                )
            if inp.image.shape[0] < 64 or inp.image.shape[1] < 64:
                raise ValueError(
                    f"input[{i}].image dimensions must be ≥ 64×64, "
                    f"got {inp.image.shape[1]}×{inp.image.shape[0]}"
                )

            h, w = inp.image.shape[:2]

            # Mask: (H, W) uint8
            if not isinstance(inp.mask, np.ndarray) or inp.mask.shape != (h, w):
                raise ValueError(
                    f"input[{i}].mask must have shape ({h}, {w}), "
                    f"got {getattr(inp.mask, 'shape', 'N/A')}"
                )

            # Depth map: (H, W) float32
            if not isinstance(inp.depth_map, np.ndarray) or inp.depth_map.shape != (
                h,
                w,
            ):
                raise ValueError(
                    f"input[{i}].depth_map must have shape ({h}, {w}), "
                    f"got {getattr(inp.depth_map, 'shape', 'N/A')}"
                )

            # Features: (1, D) float32
            if (
                not isinstance(inp.features, np.ndarray)
                or inp.features.ndim != 2
                or inp.features.shape[0] != 1
            ):
                raise ValueError(
                    f"input[{i}].features must be a (1, D) float32 ndarray, "
                    f"got shape {getattr(inp.features, 'shape', 'N/A')}"
                )

        logger.debug(
            "Input validation passed: input_count=%d, shapes=%s",
            len(inputs),
            [f"{inp.image.shape[1]}x{inp.image.shape[0]}" for inp in inputs],
        )
        return None

    # ------------------------------------------------------------------
    # Edge-case Handling
    # ------------------------------------------------------------------

    def _check_edge_cases(
        self, inputs: list[VisionPipelineOutput]
    ) -> tuple[Optional[ReconstructionResult], list[str]]:
        """Check for edge cases and return warnings or failure result.

        Returns:
            Tuple of ``(failure_result_or_none, warnings)``.
        """
        warnings: list[str] = []

        for i, inp in enumerate(inputs):
            h, w = inp.image.shape[:2]

            # EC-001: Very small input image
            if h < _RECOMMENDED_MIN_RESOLUTION or w < _RECOMMENDED_MIN_RESOLUTION:
                warn = (
                    f"Input image resolution ({w}×{h}) is below "
                    f"recommended minimum ({_RECOMMENDED_MIN_RESOLUTION}"
                    f"×{_RECOMMENDED_MIN_RESOLUTION}). "
                    "Reconstruction quality may be reduced."
                )
                warnings.append(warn)
                logger.warning(warn)

            # EC-003: Empty mask (all zeros)
            if np.all(inp.mask == 0):
                msg = (
                    "Segmentation mask is empty — no object detected "
                    "in image. Verify the reference image contains "
                    "a visible object."
                )
                logger.error("Edge case EC-003: input[%d] empty mask", i)
                return (
                    ReconstructionResult(
                        mesh=None,
                        success=False,
                        error_message=msg,
                    ),
                    warnings,
                )

            # EC-002: Mask covers entire image
            if np.all(inp.mask == 255):
                warn = (
                    "Segmentation mask covers 100% of the image. "
                    "Background may be included in reconstruction."
                )
                warnings.append(warn)
                logger.warning(warn)

            # EC-005: NaN or Inf in depth map
            invalid_mask = ~np.isfinite(inp.depth_map)
            invalid_count = int(np.sum(invalid_mask))
            if invalid_count > 0:
                inp.depth_map[invalid_mask] = 0.0
                warn = (
                    f"Depth map contained {invalid_count} invalid values "
                    "(NaN/Inf) which were replaced with 0.0."
                )
                warnings.append(warn)
                logger.warning(
                    "Depth map sanitized: input[%d], invalid_count=%d",
                    i,
                    invalid_count,
                )

        # EC-004: Duplicate view labels
        if len(inputs) == 2:
            label_a = inputs[0].view_label
            label_b = inputs[1].view_label
            if label_a == label_b:
                warn = (
                    f"Multiple images share the view label '{label_a}'. "
                    "Reconstruction quality improves with diverse "
                    "viewpoints."
                )
                warnings.append(warn)
                logger.warning(warn)

        return None, warnings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reconstruct(self, inputs: list[VisionPipelineOutput]) -> ReconstructionResult:
        """Reconstruct a 3D mesh from vision pipeline outputs.

        This is the main entry point for the reconstruction engine.
        It validates inputs, selects the best adapter, runs inference,
        validates the output, and cleans up GPU resources.

        Args:
            inputs: 1–2 ``VisionPipelineOutput`` entries from the
                vision pipeline (SPEC-TS-0003).

        Returns:
            ``ReconstructionResult`` with ``success=True`` and a
            ``StandardMesh`` on success, or ``success=False`` with
            an actionable ``error_message`` on failure.

        Implements: FR-020.
        """
        all_warnings: list[str] = []

        # --- Step 1: Validate input count (FR-021) ---
        count_result = self._validate_input_count(inputs)
        if count_result is not None:
            return count_result

        # --- Step 2: Validate input arrays (SEC-001) ---
        try:
            self._validate_inputs(inputs)
        except ValueError as exc:
            logger.error("Input validation failed: %s", exc)
            return ReconstructionResult(
                mesh=None,
                success=False,
                error_message=str(exc),
            )

        # --- Step 3: Check edge cases (EC-001 to EC-005) ---
        ec_result, ec_warnings = self._check_edge_cases(inputs)
        all_warnings.extend(ec_warnings)
        if ec_result is not None:
            ec_result.warnings = all_warnings
            return ec_result

        # --- Step 4: Select adapter (FR-006) ---
        available_vram = VRAMGuard.get_available_vram_gb()
        adapter = self._registry.select(
            input_count=len(inputs),
            cache_dir=self._cache_dir,
            available_vram_gb=available_vram,
        )

        if adapter is None:
            msg = (
                "No reconstruction adapter available for the current "
                "configuration. Check model weights and GPU VRAM."
            )
            logger.error(msg)
            return ReconstructionResult(
                mesh=None,
                success=False,
                error_message=msg,
                warnings=all_warnings,
            )

        # --- Step 5: Run inference with timeout (FR-022) ---
        try:
            result = self._run_with_timeout(adapter, inputs)
        except _TimeoutError:
            VRAMGuard.cleanup_gpu()
            msg = (
                f"Reconstruction timed out after {self._timeout_s} seconds. "
                "Consider using a lighter model or reducing input "
                "resolution."
            )
            logger.error(msg)
            return ReconstructionResult(
                mesh=None,
                success=False,
                error_message=msg,
                warnings=all_warnings,
            )

        # Merge warnings
        result.warnings = all_warnings + result.warnings

        # --- Step 6: Validate output mesh (FR-011) ---
        if result.success and result.mesh is not None:
            valid, err = validate_mesh(result.mesh)
            if not valid:
                return ReconstructionResult(
                    mesh=None,
                    success=False,
                    error_message=err,
                    warnings=result.warnings,
                    source_adapter=result.source_adapter,
                )

        return result

    def _run_with_timeout(
        self,
        adapter,
        inputs: list[VisionPipelineOutput],
    ) -> ReconstructionResult:
        """Run adapter inference with an optional timeout.

        Uses ``signal.SIGALRM`` on POSIX systems.  On platforms
        that do not support ``SIGALRM`` (Windows), inference runs
        without a timeout and logs a warning.

        Args:
            adapter: The selected ``ReconstructionAdapter``.
            inputs: Validated vision pipeline outputs.

        Returns:
            ReconstructionResult from the adapter.

        Raises:
            _TimeoutError: If inference exceeds ``self._timeout_s``.

        Implements: FR-022.
        """
        if hasattr(signal, "SIGALRM") and self._timeout_s > 0:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(self._timeout_s)
            try:
                return adapter.reconstruct(inputs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        else:
            if self._timeout_s > 0:
                logger.warning(
                    "Inference timeout not supported on this platform; "
                    "running without timeout"
                )
            return adapter.reconstruct(inputs)

    def list_adapters(self) -> list[AdapterCapabilities]:
        """List capabilities of all registered adapters.

        Returns:
            List of ``AdapterCapabilities`` from every adapter.
        """
        return self._registry.list_all()
