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
    licensing — weight-licence gating (see MODEL-LICENSES.md)
    families — architecture families adapters can load
    hf_metadata — resolve a user-chosen Hugging Face model into an entry
    get_model_path — get local path to a cached model
    ensure_model — download model if not cached, return path
"""

from . import families, hf_metadata, licensing
from .cache_manager import CacheManager
from .download_manager import DownloadManager
from .families import FAMILIES, ModelFamily, family_choices, get_family
from .hf_metadata import (
    HFModelMetadata,
    MetadataError,
    build_user_entry,
    fetch_model_metadata,
    suggest_model_id,
)
from .licensing import (
    COMMERCIAL_USE_ALLOWED,
    COMMERCIAL_USE_PROHIBITED,
    COMMERCIAL_USE_RESTRICTED,
    COMMERCIAL_USE_UNKNOWN,
    classify_license,
    is_gated,
    license_summary,
    restricted_models_allowed,
    set_restricted_models_allowed,
    sync_from_preferences,
)
from .registry import ModelEntry, ModelRegistry, ModelVariant
from .variant_selector import select_variant


class ManifestLoadError(Exception):
    """Raised when the model manifest cannot be loaded or parsed.

    EC-006: Covers missing file, invalid JSON, and missing required fields.
    """


class ModelNotFoundError(Exception):
    """Raised when a requested model_id is not found in the registry."""


class ModelLicenseError(Exception):
    """Raised when a model's weight licence forbids downloading it.

    Model weights are third-party and are not covered by Tessera's
    GPL-2.0-or-later licence. Weights whose terms restrict or prohibit
    commercial use — or that declare no terms at all — are gated behind
    the ``allow_restricted_license_models`` add-on preference.

    See ``MODEL-LICENSES.md`` and :mod:`tessera.models.licensing`.
    """


class ModelDownloadError(Exception):
    """Raised when a model download fails after all retries.

    EC-004: Covers network errors, server errors, and timeout failures.
    """


class IntegrityError(Exception):
    """Raised when SHA256 verification fails for a downloaded file.

    FR-007, SEC-001: Integrity check failure with expected vs actual hash.
    """


__all__ = [
    "COMMERCIAL_USE_ALLOWED",
    "COMMERCIAL_USE_PROHIBITED",
    "COMMERCIAL_USE_RESTRICTED",
    "COMMERCIAL_USE_UNKNOWN",
    "FAMILIES",
    "CacheManager",
    "DownloadManager",
    "HFModelMetadata",
    "MetadataError",
    "ModelFamily",
    "IntegrityError",
    "ManifestLoadError",
    "ModelDownloadError",
    "ModelEntry",
    "ModelLicenseError",
    "ModelNotFoundError",
    "ModelRegistry",
    "ModelVariant",
    "build_user_entry",
    "classify_license",
    "ensure_model",
    "families",
    "family_choices",
    "fetch_model_metadata",
    "get_family",
    "get_model_path",
    "hf_metadata",
    "is_gated",
    "license_summary",
    "licensing",
    "restricted_models_allowed",
    "select_variant",
    "set_restricted_models_allowed",
    "suggest_model_id",
    "sync_from_preferences",
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
