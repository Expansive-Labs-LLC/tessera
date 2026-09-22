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

"""Cache manager for Tessera model weights.

Tracks disk usage, model download status, and provides per-model
cache management (delete, clear, integrity verification).

Implements: FR-007, FR-008, FR-011, FR-013, FR-015, EC-002, SEC-001, SEC-005.

Public API:
    CacheManager — disk usage tracking and per-model cache management
    get_global_cache_manager() -> Optional[CacheManager]
"""

import hashlib
import logging
import shutil
from pathlib import Path
from typing import Optional

from .registry import ModelRegistry

logger = logging.getLogger("tessera.models")

# Module-level global cache manager instance
_global_cache_manager: Optional["CacheManager"] = None

# Allowed file extensions for downloaded model files (CON-006, SEC-004)
ALLOWED_EXTENSIONS = {
    ".safetensors",
    ".bin",
    ".pt",
    ".pth",
    ".onnx",
    ".json",
    ".ckpt",
    ".yaml",
}

# Buffer size for SHA256 hashing (64 KB chunks)
_HASH_BUFFER_SIZE = 65536


def get_global_cache_manager() -> Optional["CacheManager"]:
    """Get the global CacheManager instance.

    Returns:
        Optional[CacheManager]: The global instance, or None if not initialized.
    """
    return _global_cache_manager


def set_global_cache_manager(manager: Optional["CacheManager"]) -> None:
    """Set the global CacheManager instance.

    Args:
        manager: The CacheManager to use globally, or None to clear.
    """
    global _global_cache_manager
    _global_cache_manager = manager


class CacheManager:
    """Manager for cached model weight files.

    Provides model status checks, disk usage reports, integrity
    verification, and per-model delete/clear operations.

    Implements: FR-007, FR-008, FR-011, FR-013, FR-015,
                EC-002, SEC-001, SEC-005.

    Args:
        cache_dir: Path to the model cache directory.
        registry: The model registry instance.
    """

    def __init__(self, cache_dir: str, registry: ModelRegistry):
        """Initialize the cache manager.

        Args:
            cache_dir: Path to the model cache directory.
            registry: The model registry for model metadata.
        """
        self._cache_dir = Path(cache_dir).resolve()  # SEC-005: canonicalize
        self._registry = registry
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists, creating it if necessary.

        EC-002: If the directory was deleted externally, recreate it.
        """
        if not self._cache_dir.exists():
            try:
                self._cache_dir.mkdir(parents=True, exist_ok=True)
                logger.warning(
                    "Cache directory was removed. "
                    "All models marked as not downloaded."
                )
            except OSError as e:
                logger.error("Failed to create cache directory: %s", e)

    @property
    def cache_dir(self) -> Path:
        """Return the resolved cache directory path."""
        return self._cache_dir

    def get_model_path(self, model_id: str) -> Optional[Path]:
        """Get the local path to a cached model's files.

        Returns the HuggingFace cache snapshot directory for the model
        if all expected files exist locally.

        Args:
            model_id: Unique model identifier from manifest.

        Returns:
            Optional[Path]: Path to cached model directory, or None
                if not downloaded.

        Implements: FR-013, NFR-006 (< 10ms), EC-002.
        """
        # EC-002: Detect missing cache dir
        if not self._cache_dir.exists():
            self._ensure_cache_dir()
            return None

        if model_id not in self._registry:
            return None

        entry = self._registry.get_model(model_id)

        # Look for the HuggingFace hub cache structure:
        # cache_dir/models--{org}--{repo}/snapshots/{revision}/
        repo_dir_name = "models--" + entry.repo_id.replace("/", "--")
        repo_dir = self._cache_dir / repo_dir_name  # SEC-005: resolved base
        repo_dir = repo_dir.resolve()

        if not repo_dir.exists():
            return None

        # Check snapshots directory
        snapshots_dir = repo_dir / "snapshots"
        if not snapshots_dir.exists():
            return None

        # Find the revision snapshot
        # HuggingFace cache may store by commit hash or ref
        for snapshot in snapshots_dir.iterdir():
            if snapshot.is_dir():
                # Check if all expected files exist in this snapshot
                all_files_exist = all(
                    (snapshot / fname).exists() for fname in entry.files
                )
                if all_files_exist:
                    return snapshot

        return None

    def get_model_status(self, model_id: str) -> str:
        """Get the download status of a model.

        Args:
            model_id: Unique model identifier.

        Returns:
            str: One of "Downloaded", "Not Downloaded", "Update Available".

        Implements: FR-008, FR-015.
        """
        path = self.get_model_path(model_id)
        if path is None:
            return "Not Downloaded"

        # FR-015 (SHOULD): Check if a newer revision is available
        try:
            entry = self._registry.get_model(model_id)
            snapshot_name = path.name
            if snapshot_name != entry.revision and entry.revision != "main":
                return "Update Available"
        except Exception:
            pass

        return "Downloaded"

    def get_model_size_on_disk(self, model_id: str) -> int:
        """Get the disk usage of a cached model in bytes.

        Args:
            model_id: Unique model identifier.

        Returns:
            int: Size in bytes, or 0 if not cached.
        """
        path = self.get_model_path(model_id)
        if path is None:
            return 0

        total = 0
        try:
            for file in path.rglob("*"):
                if file.is_file():
                    total += file.stat().st_size
        except OSError:
            pass
        return total

    def get_cache_report(self) -> dict:
        """Get disk usage report for all registered models.

        Returns:
            dict: Report with ``total_bytes`` and ``models`` list.
                Each model entry has ``model_id``, ``status``, ``size_bytes``.

        Implements: FR-011, NFR-003 (< 2s).
        """
        models_report = []
        total_bytes = 0

        for entry in self._registry.list_models():
            status = self.get_model_status(entry.model_id)
            size = self.get_model_size_on_disk(entry.model_id)
            total_bytes += size
            models_report.append(
                {
                    "model_id": entry.model_id,
                    "status": status,
                    "size_bytes": size,
                }
            )

        return {
            "total_bytes": total_bytes,
            "models": models_report,
        }

    def delete_model(self, model_id: str) -> int:
        """Delete a specific model's cached files.

        Args:
            model_id: Unique model identifier.

        Returns:
            int: Number of bytes freed.

        Implements: FR-010.
        """
        entry = self._registry.get_model(model_id)
        repo_dir_name = "models--" + entry.repo_id.replace("/", "--")
        repo_dir = (self._cache_dir / repo_dir_name).resolve()

        # SEC-005: Verify path is within cache directory
        if not repo_dir.is_relative_to(self._cache_dir):
            logger.error(
                "Path traversal detected for model %s — delete aborted",
                model_id,
            )
            return 0

        if not repo_dir.exists():
            return 0

        # Calculate size before deleting
        freed_bytes = 0
        try:
            for file in repo_dir.rglob("*"):
                if file.is_file():
                    freed_bytes += file.stat().st_size
            shutil.rmtree(repo_dir)
            logger.info(
                "Model cache cleared: model=%s, freed_bytes=%d",
                model_id,
                freed_bytes,
            )
        except OSError as e:
            logger.error("Failed to delete model cache for %s: %s", model_id, e)
            return 0

        return freed_bytes

    def clear_all(self) -> int:
        """Delete all cached model files.

        Returns:
            int: Total number of bytes freed.
        """
        total_freed = 0
        for entry in self._registry.list_models():
            total_freed += self.delete_model(entry.model_id)
        return total_freed

    def verify_integrity(self, model_id: str) -> tuple[bool, Optional[str]]:
        """Verify SHA256 integrity of all cached files for a model.

        Args:
            model_id: Unique model identifier.

        Returns:
            tuple: (is_valid, error_message). If valid, error_message is None.

        Implements: FR-007, SEC-001, AC-005.
        """
        path = self.get_model_path(model_id)
        if path is None:
            return False, f"Model {model_id} is not cached."

        entry = self._registry.get_model(model_id)

        for filename, expected_hash in entry.sha256.items():
            # SEC-001: a missing or placeholder digest fails closed. Skipping
            # verification would defeat the control entirely, so an unverifiable
            # entry is treated as a failure rather than a pass (TASK-TS-0018).
            if not expected_hash or expected_hash == "TODO":
                error_msg = (
                    f"No SHA256 digest declared for {filename} in model "
                    f"{model_id}. Downloads cannot be verified — add the "
                    f"digest to manifest.json."
                )
                logger.error(error_msg)
                return False, error_msg

            file_path = (path / filename).resolve()

            # SEC-005: Verify file is within cache directory
            if not file_path.is_relative_to(self._cache_dir):
                error_msg = (
                    f"Path traversal detected for {filename} in model {model_id}."
                )
                logger.error(error_msg)
                return False, error_msg

            if not file_path.exists():
                error_msg = f"File {filename} missing for model {model_id}."
                logger.error(error_msg)
                return False, error_msg

            # Compute SHA256
            sha256 = hashlib.sha256()
            try:
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(_HASH_BUFFER_SIZE)
                        if not chunk:
                            break
                        sha256.update(chunk)
            except OSError as e:
                error_msg = f"Failed to read {filename}: {e}"
                logger.error(error_msg)
                return False, error_msg

            actual_hash = sha256.hexdigest()
            if actual_hash != expected_hash:
                # FR-007: Delete corrupted file and report error
                error_msg = (
                    f"Integrity check failed for {filename}. "
                    f"Expected SHA256: {expected_hash}. "
                    f"File has been deleted. Please retry the download."
                )
                logger.error(
                    "SHA256 verification failed: model=%s, file=%s, "
                    "expected=%s, actual=%s",
                    model_id,
                    filename,
                    expected_hash,
                    actual_hash,
                )
                try:
                    file_path.unlink()
                except OSError:
                    pass
                return False, error_msg

            logger.debug(
                "SHA256 verification passed: model=%s, file=%s",
                model_id,
                filename,
            )

        return True, None

    def get_missing_models_summary(self) -> tuple[int, float]:
        """Get count and total size of models not yet downloaded.

        Returns:
            tuple: (count, total_gb) of missing models.

        Used by FR-017 notification banner.
        """
        count = 0
        total_bytes = 0
        for entry in self._registry.list_models():
            status = self.get_model_status(entry.model_id)
            if status != "Downloaded":
                count += 1
                total_bytes += entry.size_bytes
        return count, total_bytes / (1024**3)
