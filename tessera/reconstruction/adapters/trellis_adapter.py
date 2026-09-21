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

"""Trellis reconstruction adapter.

Wraps Microsoft's Trellis image-to-3D model behind the
``ReconstructionAdapter`` interface.  Loads weights from the local
cache, runs in-process PyTorch inference, and normalises output
to a ``StandardMesh``.

Spec: SPEC-TS-0004 (Single-Image 3D Reconstruction Engine)

Public API:
    TrellisAdapter — primary reconstruction adapter (FR-004)
"""

from __future__ import annotations

import hashlib
import logging
import os
import time

import numpy as np

from tessera.reconstruction.adapter import (
    ReconstructionAdapter,
    VisionPipelineOutput,
)
from tessera.reconstruction.mesh_output import (
    AdapterCapabilities,
    ReconstructionResult,
)
from tessera.reconstruction.utils.mesh_conversion import normalize_to_standard_mesh
from tessera.reconstruction.utils.vram_guard import VRAMGuard

logger = logging.getLogger("tessera.reconstruction")

# Model metadata — mirrors the manifest entry for Trellis.
_MODEL_NAME = "trellis-v1.0"
_MIN_VRAM_GB = 6.0
_WEIGHT_FILES = ["trellis_pipeline.safetensors"]

# Expected SHA-256 checksums keyed by filename.
# These SHALL match the checksums in the manifest maintained by
# SPEC-TS-0002 (SEC-004).
_EXPECTED_CHECKSUMS: dict[str, str] = {
    # Populated from the model weight manifest.
    # Placeholder — actual hash set after model spike.
    "trellis_pipeline.safetensors": "",
}


def _compute_sha256(filepath: str) -> str:
    """Compute SHA-256 hex digest of a file.

    Reads in 8 KB chunks to limit peak memory usage.

    Args:
        filepath: Absolute path to the file.

    Returns:
        Lowercase hex digest string.
    """
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


class TrellisAdapter(ReconstructionAdapter):
    """Trellis image-to-3D reconstruction adapter.

    Loads the Trellis model from locally cached weights (FR-013),
    verifies checksums (SEC-004), applies segmentation masks to
    zero-out background (FR-009), runs inference via in-process
    PyTorch (CON-008), and normalises output to ``StandardMesh``
    (FR-010).

    This adapter supports both single-image (FR-007) and
    few-image (FR-008, 2 views) reconstruction paths.

    Implements: FR-004, FR-007–FR-010, FR-013, FR-014, FR-015,
        FR-016, FR-018, SEC-002, SEC-004, SEC-005.
    """

    def __init__(self, cache_dir: str) -> None:
        """Initialise the Trellis adapter.

        Args:
            cache_dir: Absolute path to the model weight cache
                directory.  Weight files are expected at
                ``<cache_dir>/trellis/<filename>``.
        """
        self._cache_dir = cache_dir
        self._model = None  # Lazy-loaded on first reconstruct()

    # ------------------------------------------------------------------
    # Weight management
    # ------------------------------------------------------------------

    def _weight_dir(self) -> str:
        """Return the directory containing Trellis weight files."""
        return os.path.join(self._cache_dir, "trellis")

    def weights_available(self) -> bool:
        """Check whether all required weight files exist on disk.

        Returns:
            ``True`` if every file in ``_WEIGHT_FILES`` exists.

        Implements: FR-014 (existence check).
        """
        for fname in _WEIGHT_FILES:
            if not os.path.isfile(os.path.join(self._weight_dir(), fname)):
                return False
        return True

    def _verify_checksums(self) -> tuple[bool, str]:
        """Verify SHA-256 checksums of all weight files.

        Skips verification for files whose expected checksum is
        empty (placeholder during development).

        Returns:
            ``(ok, error_message)`` — error_message is empty on success.

        Implements: SEC-004.
        """
        for fname, expected in _EXPECTED_CHECKSUMS.items():
            if not expected:
                # Placeholder checksum — skip during development.
                logger.debug(
                    "Skipping checksum verification for %s (placeholder)",
                    fname,
                )
                continue

            filepath = os.path.join(self._weight_dir(), fname)
            if not os.path.isfile(filepath):
                return False, (
                    f"Model weight file not found: {fname}. "
                    "Run weight download from Add-on Preferences → "
                    "Tessera → Download Models."
                )

            actual = _compute_sha256(filepath)
            if actual != expected:
                msg = (
                    f"Model weight checksum mismatch for {fname}. "
                    f"Expected: {expected}, Got: {actual}. "
                    "Re-download weights from Add-on Preferences."
                )
                logger.error(msg)
                return False, msg

            logger.debug("Checksum verified for %s: %s", fname, actual[:16] + "...")

        return True, ""

    def _load_model(self) -> tuple[bool, str]:
        """Load the Trellis model into GPU memory.

        Uses ``torch.load(weights_only=True)`` per SEC-002 to
        prevent pickle deserialization attacks.

        Returns:
            ``(ok, error_message)`` — error_message is empty on success.

        Implements: FR-013, SEC-002.
        """
        if self._model is not None:
            return True, ""

        try:
            import torch

            weight_path = os.path.join(self._weight_dir(), _WEIGHT_FILES[0])
            logger.info(
                "Loading model weights: %s from %s",
                _MODEL_NAME,
                os.path.basename(self._weight_dir()),
            )

            # SEC-002: weights_only=True prevents arbitrary code execution
            self._model = torch.load(
                weight_path,
                map_location="cuda",
                weights_only=True,
            )

            logger.info("Model weights loaded: %s", _MODEL_NAME)
            return True, ""

        except FileNotFoundError:
            msg = (
                f"Model weights not found for {_MODEL_NAME}. "
                "Run weight download from Add-on Preferences → "
                "Tessera → Download Models."
            )
            logger.error(msg)
            return False, msg
        except Exception as exc:
            msg = f"Failed to load model weights for {_MODEL_NAME}: {exc}"
            logger.error(msg)
            return False, msg

    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_mask(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Zero out background pixels using the segmentation mask.

        Args:
            image: RGB image, shape ``(H, W, 3)`` uint8.
            mask: Binary mask, shape ``(H, W)`` uint8, 0 or 255.

        Returns:
            Masked image with background pixels set to 0.

        Implements: FR-009.
        """
        # Expand mask to 3 channels for broadcasting
        mask_3ch = (mask > 0).astype(np.uint8)[..., np.newaxis]
        return image * mask_3ch

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _run_inference(
        self, inputs: list[VisionPipelineOutput]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, float]:
        """Run Trellis model inference.

        This method isolates all model-specific code behind a clear
        boundary.  When the real Trellis package is bundled, this
        method contains the actual inference calls.  In development
        (without the Trellis wheel), it raises ``RuntimeError``.

        Args:
            inputs: Preprocessed vision pipeline outputs.

        Returns:
            Tuple of ``(vertices, faces, vertex_colors, confidence)``.

        Raises:
            RuntimeError: If the Trellis package is not available.

        Implements: FR-007, FR-008, CON-008.
        """
        # Apply masks (FR-009)
        masked_images = []
        for inp in inputs:
            masked = self._apply_mask(inp.image, inp.mask)
            masked_images.append(masked)

        # ---- Model-specific inference boundary ----
        # In production, this calls into the Trellis pipeline:
        #   from trellis.pipeline import TrellisPipeline
        #   pipeline = TrellisPipeline(self._model)
        #   result = pipeline(masked_images, depth_maps, view_labels)
        #
        # For development without the Trellis wheel, generate a
        # synthetic mesh from the input structure so downstream
        # stages can be tested.

        try:
            # Attempt to import the real Trellis pipeline
            from trellis.pipeline import (
                TrellisPipeline,  # type: ignore[import-not-found]
            )

            pipeline = TrellisPipeline(self._model)
            depth_maps = [inp.depth_map for inp in inputs]
            view_labels = [inp.view_label for inp in inputs]
            result = pipeline(
                images=masked_images,
                depth_maps=depth_maps,
                view_labels=view_labels,
            )
            return (
                result.vertices,
                result.faces,
                getattr(result, "vertex_colors", None),
                getattr(result, "confidence", 0.5),
            )

        except ImportError:
            raise RuntimeError(
                "Trellis model package is not installed. "
                "Bundle the trellis wheel or use the StubAdapter "
                "for development."
            )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def reconstruct(self, inputs: list[VisionPipelineOutput]) -> ReconstructionResult:
        """Reconstruct a 3D mesh from vision pipeline outputs.

        Performs weight verification, model loading, inference,
        and GPU cleanup.

        Args:
            inputs: 1–2 processed images from the vision pipeline.

        Returns:
            ReconstructionResult with mesh on success or
            actionable error on failure.
        """
        warnings: list[str] = []
        start = time.monotonic()

        try:
            # --- Weight verification (FR-014, SEC-004) ---
            if not self.weights_available():
                return ReconstructionResult(
                    mesh=None,
                    success=False,
                    error_message=(
                        f"Model weights not found for {_MODEL_NAME}. "
                        "Run weight download from Add-on Preferences → "
                        "Tessera → Download Models."
                    ),
                    source_adapter=_MODEL_NAME,
                )

            ok, err = self._verify_checksums()
            if not ok:
                return ReconstructionResult(
                    mesh=None,
                    success=False,
                    error_message=err,
                    source_adapter=_MODEL_NAME,
                )

            # --- VRAM check (FR-012, CON-004) ---
            vram_ok, available_gb = VRAMGuard.check(_MIN_VRAM_GB)
            if not vram_ok:
                return ReconstructionResult(
                    mesh=None,
                    success=False,
                    error_message=(
                        f"Insufficient GPU VRAM. Required: {_MIN_VRAM_GB} GB, "
                        f"Available: {available_gb:.1f} GB. Close other GPU "
                        "applications or select a lighter model."
                    ),
                    source_adapter=_MODEL_NAME,
                )

            # --- Load model (FR-013) ---
            ok, err = self._load_model()
            if not ok:
                return ReconstructionResult(
                    mesh=None,
                    success=False,
                    error_message=err,
                    source_adapter=_MODEL_NAME,
                )

            # --- Run inference (FR-007, FR-008) ---
            # SEC-005: Log by index only, no pixel data
            resolutions = [
                f"input[{i}]={inp.image.shape[1]}x{inp.image.shape[0]}"
                for i, inp in enumerate(inputs)
            ]
            logger.info(
                "Reconstruction started: adapter=%s, input_count=%d, "
                "image_resolutions=%s",
                _MODEL_NAME,
                len(inputs),
                resolutions,
            )

            vertices, faces, colors, confidence = self._run_inference(inputs)

            # --- Normalise output (FR-010, FR-018) ---
            elapsed = time.monotonic() - start
            mesh = normalize_to_standard_mesh(
                vertices=vertices,
                faces=faces,
                vertex_colors=colors,
                metadata={
                    "model_name": _MODEL_NAME,
                    "inference_time_s": elapsed,
                    "confidence": confidence,
                },
            )

            # FR-016, FR-017: Low confidence warning
            if confidence < 0.5:
                warn_msg = (
                    f"Low reconstruction confidence ({confidence:.2f}). "
                    "Consider adding more reference images or trying "
                    "a different angle."
                )
                warnings.append(warn_msg)
                logger.warning(warn_msg)

            logger.info(
                "Reconstruction completed: adapter=%s, "
                "inference_time_s=%.1f, vertex_count=%d, "
                "face_count=%d, confidence=%.2f",
                _MODEL_NAME,
                elapsed,
                mesh.metadata["vertex_count"],
                mesh.metadata["face_count"],
                confidence,
            )

            return ReconstructionResult(
                mesh=mesh,
                success=True,
                warnings=warnings,
                source_adapter=_MODEL_NAME,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            msg = f"Reconstruction failed ({_MODEL_NAME}): {exc}"
            logger.error(msg)
            return ReconstructionResult(
                mesh=None,
                success=False,
                error_message=msg,
                warnings=warnings,
                source_adapter=_MODEL_NAME,
            )

        finally:
            # FR-015, CON-003: Always clean up GPU memory
            VRAMGuard.cleanup_gpu()

    def capabilities(self) -> AdapterCapabilities:
        """Declare Trellis adapter capabilities."""
        return AdapterCapabilities(
            model_name=_MODEL_NAME,
            min_images=1,
            max_images=2,
            requires_depth=True,
            requires_mask=True,
            min_vram_gb=_MIN_VRAM_GB,
            supported_view_labels=[
                "front",
                "back",
                "left",
                "right",
                "top",
                "bottom",
                "front-left",
                "front-right",
                "isometric",
                "unlabeled",
            ],
            output_types=["mesh"],
        )
