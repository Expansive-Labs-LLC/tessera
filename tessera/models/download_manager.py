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

"""Download manager for Tessera model weights.

Handles background model downloading with progress reporting,
resume support, retry logic, and SHA256 integrity verification.

Implements: FR-002, FR-003, FR-004, FR-006, FR-007, FR-009, FR-014,
            FR-019, EC-001, EC-003, EC-004, CON-001, CON-003, CON-006,
            CON-008, SEC-001, SEC-002, SEC-003, SEC-004, SEC-005.

Public API:
    DownloadManager — background download engine with progress
    get_global_download_manager() -> Optional[DownloadManager]
"""

import logging
import queue
import shutil
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .cache_manager import ALLOWED_EXTENSIONS, CacheManager
from .registry import ModelEntry, ModelRegistry
from .variant_selector import select_variant

logger = logging.getLogger("tessera.models")

# Retry constants (EC-004)
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 2
BACKOFF_MULTIPLIER = 2

# Module-level global download manager instance
_global_download_manager: Optional["DownloadManager"] = None


def get_global_download_manager() -> Optional["DownloadManager"]:
    """Get the global DownloadManager instance.

    Returns:
        Optional[DownloadManager]: The global instance, or None if not initialized.
    """
    return _global_download_manager


def set_global_download_manager(manager: Optional["DownloadManager"]) -> None:
    """Set the global DownloadManager instance.

    Args:
        manager: The DownloadManager to use globally, or None to clear.
    """
    global _global_download_manager
    _global_download_manager = manager


def _validate_file_extension(filename: str) -> bool:
    """Check if a filename has an allowed extension.

    CON-006, SEC-004: Only allow .safetensors, .bin, .pt, .pth, .onnx, .json.

    Args:
        filename: The filename to check.

    Returns:
        bool: True if the extension is allowed.
    """
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


class DownloadManager:
    """Manager for downloading model weights from HuggingFace.

    Runs downloads in background threads with progress reporting
    via a thread-safe queue. Supports resume, retry with exponential
    backoff, and SHA256 integrity verification.

    Threading model (from spec §2.3):
        Downloads run in a ``threading.Thread``. The thread writes
        progress to a ``queue.Queue``. A ``bpy.app.timers`` callback
        polls the queue at 100ms intervals and updates scene properties.

    Implements: FR-002, FR-003, FR-004, FR-006, FR-007, FR-009, FR-014,
                EC-001, EC-003, EC-004.

    Args:
        cache_dir: Path to the model cache directory.
        registry: The model registry instance.
        cache_manager: The cache manager instance.
        available_vram_gb: GPU VRAM available in GB (for variant selection).
    """

    def __init__(
        self,
        cache_dir: str,
        registry: ModelRegistry,
        cache_manager: CacheManager,
        available_vram_gb: float = 0.0,
    ):
        """Initialize the download manager.

        Args:
            cache_dir: Path to the model cache directory.
            registry: The model registry.
            cache_manager: The cache manager.
            available_vram_gb: Available GPU VRAM in GB.
        """
        self._cache_dir = Path(cache_dir).resolve()  # SEC-005
        self._registry = registry
        self._cache_manager = cache_manager
        self._available_vram_gb = available_vram_gb

        # Thread-safe progress queue (FR-004)
        self.progress_queue: queue.Queue = queue.Queue()

        # Per-model locks to prevent duplicate downloads (EC-003)
        self._model_locks: dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()  # Lock for the locks dict

        # Active download state
        self._active_download: Optional[str] = None
        self._download_thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()

    def _get_model_lock(self, model_id: str) -> threading.Lock:
        """Get or create a per-model lock.

        EC-003: Serializes concurrent download requests for the same model.

        Args:
            model_id: Model identifier.

        Returns:
            threading.Lock: The lock for this model.
        """
        with self._locks_lock:
            if model_id not in self._model_locks:
                self._model_locks[model_id] = threading.Lock()
            return self._model_locks[model_id]

    def _download_file(
        self,
        repo_id: str,
        filename: str,
        revision: str,
        callback: Optional[Callable] = None,
    ) -> Path:
        """Download a single file from a HuggingFace repository.

        Uses ``huggingface_hub.hf_hub_download()`` with pinned revision
        and local cache directory.

        Args:
            repo_id: HuggingFace repository ID.
            filename: Relative file path within the repo.
            revision: Git commit hash or tag.
            callback: Optional progress callback.

        Returns:
            Path: Local path to the downloaded file.

        Raises:
            ModelDownloadError: If download fails after all retries.

        Implements: FR-002, FR-006, SEC-002.
        """
        from . import ModelDownloadError

        # CON-006, SEC-004: Validate file extension
        if not _validate_file_extension(filename):
            raise ModelDownloadError(
                f"File extension not allowed: {filename}. "
                f"Allowed: {ALLOWED_EXTENSIONS}"
            )

        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            if self._cancel_event.is_set():
                raise ModelDownloadError("Download cancelled by user.")

            try:
                # FR-002: Use hf_hub_download with pinned revision
                # FR-006: Resume is built into huggingface_hub
                # SEC-002: huggingface_hub connects to huggingface.co over HTTPS
                from huggingface_hub import hf_hub_download

                local_path = hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    revision=revision,
                    cache_dir=str(self._cache_dir),
                    force_download=False,
                )

                downloaded_path = Path(local_path).resolve()

                # SEC-005: Verify path is within cache directory
                if not downloaded_path.is_relative_to(self._cache_dir):
                    raise ModelDownloadError(
                        f"Downloaded file path outside cache directory: "
                        f"{downloaded_path}"
                    )

                return downloaded_path

            except ImportError:
                raise ModelDownloadError(
                    "huggingface_hub is not installed. "
                    "Please install it: pip install huggingface_hub>=0.23.0"
                )

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    backoff = INITIAL_BACKOFF_SECONDS * (
                        BACKOFF_MULTIPLIER ** (attempt - 1)
                    )
                    logger.warning(
                        "Download failed for %s/%s (attempt %d/%d): %s. "
                        "Retrying in %ds...",
                        repo_id,
                        filename,
                        attempt,
                        MAX_RETRIES,
                        e,
                        backoff,
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        "Download failed for %s/%s after %d retries: %s",
                        repo_id,
                        filename,
                        MAX_RETRIES,
                        e,
                    )

        raise ModelDownloadError(
            f"Download failed for {repo_id}/{filename}: "
            f"unable to reach HuggingFace servers. "
            f"Check your internet connection and retry. "
            f"Last error: {last_error}"
        )

    def _download_model(
        self,
        model_id: str,
        callback: Optional[Callable] = None,
    ) -> Path:
        """Download all files for a model with progress reporting.

        This is the core download logic, called within a per-model lock.

        Args:
            model_id: Model identifier.
            callback: Optional progress callback.

        Returns:
            Path: Path to the cached model directory.

        Raises:
            ModelDownloadError: If download or verification fails.
        """
        from . import IntegrityError, ModelDownloadError

        entry = self._registry.get_model(model_id)

        # FR-012: Select variant based on VRAM
        variant, vram_warning = select_variant(entry, self._available_vram_gb)
        files_to_download = variant.files if variant.files else entry.files
        total_size = variant.size_bytes

        logger.info(
            "Download started: model=%s, repo=%s, variant=%s, size_bytes=%d",
            model_id,
            entry.repo_id,
            variant.variant_id,
            total_size,
        )

        # Report initial progress
        progress = {
            "model_id": model_id,
            "bytes_downloaded": 0,
            "total_bytes": total_size,
            "speed_bps": 0.0,
            "eta_seconds": 0.0,
            "status": "downloading",
            "vram_warning": vram_warning,
        }
        self.progress_queue.put(progress.copy())
        if callback:
            callback(progress.copy())

        start_time = time.monotonic()
        bytes_so_far = 0
        model_path = None

        for i, filename in enumerate(files_to_download):
            if self._cancel_event.is_set():
                raise ModelDownloadError("Download cancelled by user.")

            try:
                # EC-001: Catch disk space errors
                file_path = self._download_file(
                    repo_id=entry.repo_id,
                    filename=filename,
                    revision=entry.revision,
                    callback=callback,
                )

                # Track the snapshot directory (parent of downloaded files)
                if model_path is None:
                    # Navigate up to the snapshot directory
                    # File paths may be nested, so find the snapshot root
                    parts = Path(filename).parts
                    model_path = file_path
                    for _ in parts:
                        model_path = model_path.parent

            except OSError as e:
                error_str = str(e).lower()
                if "no space" in error_str or "disk full" in error_str:
                    # EC-001: Disk space exhausted
                    disk_usage = shutil.disk_usage(str(self._cache_dir))
                    available_gb = disk_usage.free / (1024 ** 3)
                    required_gb = total_size / (1024 ** 3)
                    raise ModelDownloadError(
                        f"Download failed: insufficient disk space. "
                        f"{required_gb:.1f} GB required, "
                        f"{available_gb:.1f} GB available. "
                        f"Free up disk space and retry."
                    ) from e
                raise ModelDownloadError(
                    f"Download failed for {model_id}: {e}"
                ) from e

            # Update progress
            # Estimate bytes based on file proportion
            file_proportion = (i + 1) / len(files_to_download)
            bytes_so_far = int(total_size * file_proportion)
            elapsed = time.monotonic() - start_time
            speed = bytes_so_far / elapsed if elapsed > 0 else 0.0
            remaining = total_size - bytes_so_far
            eta = remaining / speed if speed > 0 else 0.0

            progress = {
                "model_id": model_id,
                "bytes_downloaded": bytes_so_far,
                "total_bytes": total_size,
                "speed_bps": speed,
                "eta_seconds": eta,
                "status": "downloading",
                "vram_warning": vram_warning,
            }
            self.progress_queue.put(progress.copy())
            if callback:
                callback(progress.copy())

            # Log progress at 10% intervals (§11.1)
            pct = int(file_proportion * 100)
            if pct % 10 == 0:
                logger.debug(
                    "Download progress: model=%s, percent_complete=%d, "
                    "speed_bps=%.0f",
                    model_id,
                    pct,
                    speed,
                )

        # SHA256 verification (FR-007, SEC-001)
        if model_path:
            is_valid, error_msg = self._cache_manager.verify_integrity(model_id)
            if not is_valid and error_msg and "TODO" not in error_msg:
                raise IntegrityError(error_msg)
            elif is_valid:
                # All hashes are "TODO" placeholders — verification was skipped
                all_todo = all(
                    h == "TODO" for h in entry.sha256.values()
                )
                if all_todo:
                    logger.info(
                        "SHA256 verification skipped: model=%s — all hashes "
                        "are TODO placeholders. Replace before release.",
                        model_id,
                    )

        elapsed_total = time.monotonic() - start_time
        logger.info(
            "Download completed: model=%s, duration_seconds=%.1f, "
            "size_bytes=%d",
            model_id,
            elapsed_total,
            total_size,
        )

        # Report completion
        progress = {
            "model_id": model_id,
            "bytes_downloaded": total_size,
            "total_bytes": total_size,
            "speed_bps": total_size / elapsed_total if elapsed_total > 0 else 0,
            "eta_seconds": 0.0,
            "status": "completed",
            "vram_warning": vram_warning,
        }
        self.progress_queue.put(progress.copy())
        if callback:
            callback(progress.copy())

        # Return the model path from cache manager
        cached_path = self._cache_manager.get_model_path(model_id)
        if cached_path is None:
            raise ModelDownloadError(
                f"Download completed but model path not found for {model_id}"
            )
        return cached_path

    def ensure_model(
        self,
        model_id: str,
        callback: Optional[Callable] = None,
    ) -> Path:
        """Download model if not cached, return local path.

        Blocking call designed for use in pipeline background threads
        only — SHALL NOT be called from the Blender main thread (FR-014).

        EC-003: Uses per-model lock. Second caller waits for first
        download to complete and then returns the cached path.

        Args:
            model_id: Unique model identifier.
            callback: Optional progress callback.

        Returns:
            Path: Path to cached model directory.

        Raises:
            ModelDownloadError: If download fails.
            ModelNotFoundError: If model_id is not in the registry.

        Implements: FR-014, EC-003.
        """
        # Check cache first (fast path)
        cached_path = self._cache_manager.get_model_path(model_id)
        if cached_path is not None:
            return cached_path

        # Acquire per-model lock (EC-003)
        lock = self._get_model_lock(model_id)
        with lock:
            # Double-check after acquiring lock
            cached_path = self._cache_manager.get_model_path(model_id)
            if cached_path is not None:
                return cached_path

            return self._download_model(model_id, callback=callback)

    def start_background_download(
        self,
        model_id: str,
    ) -> None:
        """Start a background download for a model.

        Launches a download thread that reports progress via
        ``self.progress_queue``. Use with ``bpy.app.timers``
        to poll the queue on the main thread.

        Args:
            model_id: Model to download.

        Implements: FR-003, CON-003.
        """
        if self._download_thread is not None and self._download_thread.is_alive():
            logger.warning(
                "Download already in progress. Wait for it to complete."
            )
            return

        self._cancel_event.clear()
        self._active_download = model_id

        def _thread_target():
            try:
                self.ensure_model(model_id)
            except Exception as e:
                # Report error via queue (CON-003: no bpy from thread)
                self.progress_queue.put(
                    {
                        "model_id": model_id,
                        "bytes_downloaded": 0,
                        "total_bytes": 0,
                        "speed_bps": 0.0,
                        "eta_seconds": 0.0,
                        "status": "error",
                        "error": str(e),
                    }
                )
            finally:
                self._active_download = None

        self._download_thread = threading.Thread(
            target=_thread_target,
            name=f"tessera-download-{model_id}",
            daemon=True,
        )
        self._download_thread.start()
        logger.info("Background download started: model=%s", model_id)

    def start_download_all_missing(self) -> None:
        """Start background sequential download of all missing models.

        Implements: FR-009.
        """
        if self._download_thread is not None and self._download_thread.is_alive():
            logger.warning(
                "Download already in progress. Wait for it to complete."
            )
            return

        self._cancel_event.clear()

        def _thread_target():
            for entry in self._registry.list_models():
                if self._cancel_event.is_set():
                    break
                cached = self._cache_manager.get_model_path(entry.model_id)
                if cached is None:
                    try:
                        self._active_download = entry.model_id
                        self.ensure_model(entry.model_id)
                    except Exception as e:
                        self.progress_queue.put(
                            {
                                "model_id": entry.model_id,
                                "bytes_downloaded": 0,
                                "total_bytes": 0,
                                "speed_bps": 0.0,
                                "eta_seconds": 0.0,
                                "status": "error",
                                "error": str(e),
                            }
                        )
            self._active_download = None
            self.progress_queue.put(
                {
                    "model_id": "__all__",
                    "status": "all_completed",
                    "bytes_downloaded": 0,
                    "total_bytes": 0,
                    "speed_bps": 0.0,
                    "eta_seconds": 0.0,
                }
            )

        self._download_thread = threading.Thread(
            target=_thread_target,
            name="tessera-download-all",
            daemon=True,
        )
        self._download_thread.start()
        logger.info("Background download-all started")

    def download_all_missing(
        self,
        callback: Optional[Callable] = None,
    ) -> None:
        """Download all missing models sequentially (blocking).

        Args:
            callback: Optional progress callback.

        Implements: FR-009.
        """
        for entry in self._registry.list_models():
            cached = self._cache_manager.get_model_path(entry.model_id)
            if cached is None:
                self.ensure_model(entry.model_id, callback=callback)

    def cancel_download(self) -> None:
        """Signal the active download to cancel."""
        self._cancel_event.set()
        logger.info("Download cancel requested")

    @property
    def is_downloading(self) -> bool:
        """Whether a download is currently active."""
        return (
            self._download_thread is not None
            and self._download_thread.is_alive()
        )

    @property
    def active_download_id(self) -> Optional[str]:
        """The model_id of the currently downloading model, or None."""
        return self._active_download
