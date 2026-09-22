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

import logging
import os
import time

import numpy as np

from ...reconstruction.adapter import (
    ReconstructionAdapter,
    VisionPipelineOutput,
)
from ...reconstruction.mesh_output import (
    AdapterCapabilities,
    ReconstructionResult,
)
from ...reconstruction.utils.mesh_conversion import normalize_to_standard_mesh
from ...reconstruction.utils.vram_guard import VRAMGuard

logger = logging.getLogger("tessera.reconstruction")

# Display name for this adapter, reported as ``source_adapter``.
_MODEL_NAME = "trellis-v1.0"
_MIN_VRAM_GB = 6.0

# Manifest entry that owns this adapter's weights (SPEC-TS-0002).
# The manifest is the single source of truth for the file list, the
# pinned revision and the SHA-256 digests — this adapter does not keep
# its own copy of any of them.
_MODEL_ID = "trellis-image-large"

# Pipeline configuration file at the root of the upstream repository.
_PIPELINE_CONFIG = "pipeline.json"


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

    def __init__(self, cache_dir: str, cache_manager: object | None = None) -> None:
        """Initialise the Trellis adapter.

        Args:
            cache_dir: Absolute path to the model weight cache
                directory — the same directory the download manager
                writes to (SPEC-TS-0002 FR-002).
            cache_manager: Optional pre-built ``CacheManager``. When
                omitted, one is constructed lazily over ``cache_dir``.
        """
        self._cache_dir = cache_dir
        self._cache_manager = cache_manager
        self._model = None  # Lazy-loaded on first reconstruct()
        self._model_dir: str | None = None

    # ------------------------------------------------------------------
    # Weight management
    # ------------------------------------------------------------------

    def _cache(self):
        """Return the ``CacheManager`` used to resolve and verify weights.

        Built lazily so that constructing the adapter — which the
        registry does eagerly for capability queries — does not read
        the manifest from disk.
        """
        if self._cache_manager is None:
            from ...models.cache_manager import CacheManager
            from ...models.registry import ModelRegistry

            self._cache_manager = CacheManager(
                cache_dir=self._cache_dir, registry=ModelRegistry()
            )
        return self._cache_manager

    def _weight_dir(self) -> str | None:
        """Return the resolved snapshot directory for the Trellis weights.

        Returns:
            Absolute path to the cached snapshot, or ``None`` when the
            weights have not been downloaded.
        """
        try:
            path = self._cache().get_model_path(_MODEL_ID)
        except Exception as exc:  # manifest unreadable, entry absent
            logger.error("Could not resolve weights for %s: %s", _MODEL_ID, exc)
            return None
        return str(path) if path is not None else None

    def weights_available(self) -> bool:
        """Check whether the Trellis weights are present in the cache.

        Delegates to the model cache, which checks every file the
        manifest declares for this entry — not a single filename.

        Implements: FR-014 (existence check).
        """
        return self._weight_dir() is not None

    def _verify_checksums(self) -> tuple[bool, str]:
        """Verify the SHA-256 digest of every cached Trellis weight file.

        Delegates to ``CacheManager.verify_integrity()``, which holds
        the manifest digests and fails closed on an absent, empty,
        placeholder or malformed digest (SPEC-TS-0002 FR-007a). This
        adapter deliberately keeps no digest table of its own — a
        second copy is a second thing to go stale.

        Returns:
            ``(ok, error_message)`` — error_message is empty on success.

        Implements: SEC-004.
        """
        try:
            ok, err = self._cache().verify_integrity(_MODEL_ID)
        except Exception as exc:
            msg = f"Could not verify weights for {_MODEL_ID}: {exc}"
            logger.error(msg)
            return False, msg

        if not ok:
            msg = (
                f"{err or 'Weight verification failed.'} "
                "Re-download weights from Add-on Preferences → "
                "Tessera → Download Models."
            )
            logger.error(msg)
            return False, msg

        logger.debug("Weight integrity verified for %s", _MODEL_ID)
        return True, ""

    def _load_model(self) -> tuple[bool, str]:
        """Resolve the verified weight directory for inference.

        TRELLIS is a multi-file pipeline — ``pipeline.json`` plus a
        ``ckpts/`` tree of ``.safetensors`` — loaded by the upstream
        pipeline loader, not by a single deserialisation call. This
        method therefore resolves and validates the snapshot directory;
        the pipeline itself is constructed at the inference boundary.

        No ``torch.load()`` or ``pickle`` is used on any downloaded file
        (SEC-002, CON-008).

        Returns:
            ``(ok, error_message)`` — error_message is empty on success.

        Implements: FR-013, SEC-002.
        """
        if self._model_dir is not None:
            return True, ""

        model_dir = self._weight_dir()
        if model_dir is None:
            msg = (
                f"Model weights not found for {_MODEL_NAME}. "
                "Run weight download from Add-on Preferences → "
                "Tessera → Download Models."
            )
            logger.error(msg)
            return False, msg

        config = os.path.join(model_dir, _PIPELINE_CONFIG)
        if not os.path.isfile(config):
            msg = (
                f"Weight cache for {_MODEL_NAME} is missing "
                f"{_PIPELINE_CONFIG}. Re-download weights from Add-on "
                "Preferences → Tessera → Download Models."
            )
            logger.error(msg)
            return False, msg

        self._model_dir = model_dir
        logger.info("Weight directory resolved for %s", _MODEL_NAME)
        return True, ""

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
        # The weights are downloaded, verified and resolved by this
        # point; what is missing is the *runtime*. TRELLIS needs torch
        # built for the host CUDA version plus compiled CUDA extensions
        # (sparse-voxel rasterisation and attention kernels). How that
        # runtime is delivered is an open architectural decision —
        # see TASK-TS-0017. Until it resolves, the registry falls back
        # to StubAdapter rather than this adapter returning a fake mesh.
        try:
            from trellis.pipeline import (
                TrellisPipeline,  # type: ignore[import-not-found]
            )
        except ImportError:
            raise RuntimeError(
                "The TRELLIS inference runtime is not available. Weights "
                f"for {_MODEL_ID} are downloaded and verified, but the "
                "runtime (torch built for this machine's CUDA version, "
                "plus TRELLIS's compiled CUDA extensions) is not "
                "installed. See TASK-TS-0017."
            )

        pipeline = TrellisPipeline.from_pretrained(self._model_dir)
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
