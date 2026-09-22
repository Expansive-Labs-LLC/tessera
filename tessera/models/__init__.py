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

"""Tessera model weight management package.

Provides model registry, download manager, cache manager, and
VRAM-aware variant selection for local model weight management.

Spec: SPEC-TS-0002 (Local Model Weight Management)

Public API:
    ModelRegistry — loads and queries the embedded manifest
    CacheManager — disk usage tracking, per-model cache management
    DownloadManager — background download with progress and resume
    select_variant — VRAM-aware model variant selection
    get_model_path — get local path to a cached model
    ensure_model — download model if not cached, return path
"""

from .cache_manager import CacheManager
from .download_manager import DownloadManager
from .registry import ModelEntry, ModelRegistry, ModelVariant
from .variant_selector import select_variant


class ManifestLoadError(Exception):
    """Raised when the model manifest cannot be loaded or parsed.

    EC-006: Covers missing file, invalid JSON, and missing required fields.
    """


class ModelNotFoundError(Exception):
    """Raised when a requested model_id is not found in the registry."""


class ModelDownloadError(Exception):
    """Raised when a model download fails after all retries.

    EC-004: Covers network errors, server errors, and timeout failures.
    """


class IntegrityError(Exception):
    """Raised when SHA256 verification fails for a downloaded file.

    FR-007, SEC-001: Integrity check failure with expected vs actual hash.
    """


__all__ = [
    "CacheManager",
    "DownloadManager",
    "IntegrityError",
    "ManifestLoadError",
    "ModelDownloadError",
    "ModelEntry",
    "ModelNotFoundError",
    "ModelRegistry",
    "ModelVariant",
    "ensure_model",
    "get_model_path",
    "select_variant",
]


def get_model_path(model_id: str):
    """Get the local path to a cached model.

    Convenience function that delegates to the global CacheManager instance.

    Args:
        model_id: Unique model identifier from manifest.json.

    Returns:
        Optional[Path]: Path to cached model directory, or None if not downloaded.

    Implements: FR-013.
    """
    from .cache_manager import get_global_cache_manager

    manager = get_global_cache_manager()
    if manager is None:
        return None
    return manager.get_model_path(model_id)


def ensure_model(model_id: str, callback=None):
    """Download model if not cached, return local path.

    Blocking call designed for use in pipeline background threads only.
    SHALL NOT be called from the Blender main thread (FR-014).

    Args:
        model_id: Unique model identifier from manifest.json.
        callback: Optional progress callback receiving dict with keys:
            model_id, bytes_downloaded, total_bytes, speed_bps, eta_seconds.

    Returns:
        Path: Path to cached model directory.

    Raises:
        ModelDownloadError: If download fails after all retries.
        ModelNotFoundError: If model_id is not in the registry.

    Implements: FR-014.
    """
    from .download_manager import get_global_download_manager

    manager = get_global_download_manager()
    if manager is None:
        raise ModelDownloadError(
            "Download manager not initialized. Is the Tessera add-on enabled?"
        )
    return manager.ensure_model(model_id, callback=callback)
