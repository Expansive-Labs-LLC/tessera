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

"""Model registry for Tessera.

Loads and validates the embedded manifest.json that declares all
required AI model weights with their metadata.

Implements: FR-001, EC-006.

Public API:
    ModelVariant — dataclass for a model variant (fp16/fp32)
    ModelEntry — dataclass for a manifest model entry
    ModelRegistry — loads, validates, and queries the manifest
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tessera.models")

# Path to the embedded manifest file (same directory as this module)
_MANIFEST_PATH = Path(__file__).parent / "manifest.json"

# Required fields for a valid manifest model entry (FR-001)
_REQUIRED_MODEL_FIELDS = {
    "model_id",
    "repo_id",
    "revision",
    "files",
    "sha256",
    "size_bytes",
    "min_vram_gb",
    "description",
}


@dataclass
class ModelVariant:
    """A model variant for a specific VRAM tier.

    Attributes:
        variant_id: Identifier such as ``"fp16"`` or ``"fp32"``.
        min_vram_gb: Minimum GPU VRAM required in GB.
        size_bytes: Download size for this variant.
        files: Relative file paths within the repo for this variant.
    """

    variant_id: str
    min_vram_gb: float
    size_bytes: int
    files: list[str] = field(default_factory=list)


@dataclass
class ModelEntry:
    """A model entry from the manifest.

    Attributes:
        model_id: Unique identifier (alphanumeric + hyphens, max 64 chars).
        repo_id: HuggingFace repository ID.
        revision: Pinned Git commit hash or tag.
        description: Human-readable purpose.
        files: Default file list (used when no variants).
        sha256: Mapping of filename to expected SHA256 hex digest.
        size_bytes: Total download size in bytes.
        min_vram_gb: Minimum VRAM for default variant.
        license: SPDX-style licence identifier for the *weights* (not for
            Tessera itself), e.g. ``"Apache-2.0"``. Weights are third-party
            and are not covered by Tessera's GPL licence.
        license_url: Where those terms are published.
        commercial_use: One of ``"allowed"``, ``"restricted"``,
            ``"prohibited"`` or ``"unknown"``. Anything other than
            ``"allowed"`` is gated behind an explicit opt-in — see
            :mod:`tessera.models.licensing`.
        family: Architecture family id (:mod:`tessera.models.families`).
            Required for user-added models so an adapter knows how to load
            them; empty for bundled entries that adapters address directly.
        variant: Optional variant within the family, e.g. ``"vitb"``.
        source: ``"bundled"`` for the shipped manifest, ``"user"`` for a
            model the user added from Hugging Face.
        variants: Optional list of VRAM-tiered variants.
    """

    model_id: str
    repo_id: str
    revision: str
    description: str
    files: list[str]
    sha256: dict[str, str]
    size_bytes: int
    min_vram_gb: float
    license: str = "unknown"
    license_url: str = ""
    commercial_use: str = "unknown"
    family: str = ""
    variant: str = ""
    source: str = "bundled"
    variants: list[ModelVariant] = field(default_factory=list)


def _parse_variant(data: dict) -> Optional[ModelVariant]:
    """Parse a variant dict into a ModelVariant dataclass.

    Args:
        data: Variant dict from manifest JSON.

    Returns:
        ModelVariant if valid, None if missing required fields.
    """
    required = {"variant_id", "min_vram_gb", "size_bytes"}
    missing = required - set(data.keys())
    if missing:
        logger.error("Variant missing required fields: %s", missing)
        return None

    return ModelVariant(
        variant_id=str(data["variant_id"]),
        min_vram_gb=float(data["min_vram_gb"]),
        size_bytes=int(data["size_bytes"]),
        files=list(data.get("files", [])),
    )


def _parse_model_entry(data: dict) -> Optional[ModelEntry]:
    """Parse a model entry dict into a ModelEntry dataclass.

    Validates that all required fields are present (FR-001).
    If fields are missing, logs ERROR and returns None (EC-006).

    Args:
        data: Model entry dict from manifest JSON.

    Returns:
        ModelEntry if valid, None if missing required fields.
    """
    missing = _REQUIRED_MODEL_FIELDS - set(data.keys())
    if missing:
        model_id = data.get("model_id", "<unknown>")
        logger.error(
            "Model entry '%s' missing required fields: %s — skipping",
            model_id,
            missing,
        )
        return None

    # Licence metadata is optional in the schema so that older manifests
    # still load, but a missing classification fails closed as "unknown"
    # and is therefore gated from download (licensing.check_download_allowed).
    if "commercial_use" not in data:
        logger.warning(
            "Model entry '%s' declares no commercial_use classification — "
            "treating as 'unknown' and gating downloads. See MODEL-LICENSES.md.",
            data.get("model_id", "<unknown>"),
        )

    # Parse variants (may be empty list)
    variants = []
    for v_data in data.get("variants", []):
        variant = _parse_variant(v_data)
        if variant is not None:
            variants.append(variant)

    return ModelEntry(
        model_id=str(data["model_id"]),
        repo_id=str(data["repo_id"]),
        revision=str(data["revision"]),
        description=str(data["description"]),
        files=list(data["files"]),
        sha256=dict(data["sha256"]),
        size_bytes=int(data["size_bytes"]),
        min_vram_gb=float(data["min_vram_gb"]),
        license=str(data.get("license", "unknown")),
        license_url=str(data.get("license_url", "")),
        commercial_use=str(data.get("commercial_use", "unknown")),
        family=str(data.get("family", "")),
        variant=str(data.get("variant", "")),
        source=str(data.get("source", "bundled")),
        variants=variants,
    )


def _entry_to_dict(entry: ModelEntry) -> dict:
    """Serialise a model entry back to its manifest representation.

    Args:
        entry: The entry to serialise.

    Returns:
        dict: JSON-serialisable manifest entry.
    """
    data = {
        "model_id": entry.model_id,
        "repo_id": entry.repo_id,
        "revision": entry.revision,
        "description": entry.description,
        "license": entry.license,
        "license_url": entry.license_url,
        "commercial_use": entry.commercial_use,
        "files": list(entry.files),
        "sha256": dict(entry.sha256),
        "size_bytes": entry.size_bytes,
        "min_vram_gb": entry.min_vram_gb,
        "family": entry.family,
        "source": entry.source,
        "variants": [
            {
                "variant_id": v.variant_id,
                "min_vram_gb": v.min_vram_gb,
                "size_bytes": v.size_bytes,
                "files": list(v.files),
            }
            for v in entry.variants
        ],
    }
    if entry.variant:
        data["variant"] = entry.variant
    return data


class ModelRegistry:
    """Model registry that loads and queries the embedded manifest.

    Loads ``manifest.json`` on initialization, validates each entry
    against the ``ModelEntry`` schema, and provides query methods.

    Implements: FR-001, EC-006.

    Raises:
        ManifestLoadError: If the manifest file is missing or unparseable.

    Example:
        >>> registry = ModelRegistry()
        >>> models = registry.list_models()
        >>> entry = registry.get_model("depth-anything-v2-large")
    """

    def __init__(
        self,
        manifest_path: Optional[Path] = None,
        user_manifest_path: Optional[Path] = None,
    ):
        """Initialize the registry by loading the manifest.

        Args:
            manifest_path: Optional override for the manifest file path.
                Defaults to the embedded ``manifest.json``.
            user_manifest_path: Optional path to the user-added model file
                (FR-025). It lives outside the add-on directory — normally
                ``<cache_dir>/user_models.json`` — so that user additions
                survive an add-on update. A missing file is not an error.

        Raises:
            ManifestLoadError: If the bundled manifest is missing or
                contains invalid JSON. A malformed *user* manifest is
                logged and skipped rather than disabling model management.
        """
        from . import ManifestLoadError

        path = manifest_path or _MANIFEST_PATH

        if not path.exists():
            raise ManifestLoadError(
                f"Failed to load model manifest: file not found at {path}. "
                "Tessera model management is disabled until the manifest is restored."
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ManifestLoadError(
                f"Failed to load model manifest: {e}. "
                "Tessera model management is disabled until the manifest is restored."
            ) from e

        if not isinstance(raw, dict) or "models" not in raw:
            raise ManifestLoadError(
                "Failed to load model manifest: missing 'models' key. "
                "Tessera model management is disabled until the manifest is restored."
            )

        self._models: dict[str, ModelEntry] = {}
        for entry_data in raw["models"]:
            entry = _parse_model_entry(entry_data)
            if entry is not None:
                self._models[entry.model_id] = entry

        self._bundled_ids = set(self._models)
        self._user_manifest_path = user_manifest_path
        self._load_user_manifest()

        logger.info(
            "Model registry loaded: %d bundled, %d user-added",
            len(self._bundled_ids),
            len(self._models) - len(self._bundled_ids),
        )

    # ------------------------------------------------------------------
    # User-added models (FR-025 – FR-032)
    # ------------------------------------------------------------------

    def _load_user_manifest(self) -> None:
        """Merge user-added models over the bundled manifest.

        A malformed user manifest never takes model management down with
        it: the problem is logged and the bundled models still load.
        """
        path = self._user_manifest_path
        if path is None or not path.exists():
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                "Could not read user model list at %s: %s — "
                "user-added models are unavailable until it is fixed.",
                path,
                e,
            )
            return

        for entry_data in (raw or {}).get("models", []):
            entry_data = dict(entry_data)
            entry_data["source"] = "user"
            entry = _parse_model_entry(entry_data)
            if entry is None:
                continue
            if entry.model_id in self._bundled_ids:
                logger.warning(
                    "User model '%s' shadows a bundled model — ignoring the "
                    "user entry.",
                    entry.model_id,
                )
                continue
            self._models[entry.model_id] = entry

    def _save_user_manifest(self) -> None:
        """Write the user-added models back to disk atomically.

        Raises:
            ManifestLoadError: If no user manifest path is configured or the
                file cannot be written.
        """
        from . import ManifestLoadError

        path = self._user_manifest_path
        if path is None:
            raise ManifestLoadError(
                "No user model list is configured, so custom models cannot " "be saved."
            )

        payload = {
            "version": "1.0",
            "models": [_entry_to_dict(entry) for entry in self.list_user_models()],
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.write("\n")
            tmp.replace(path)
        except OSError as e:
            raise ManifestLoadError(f"Could not save the user model list: {e}") from e

    def is_user_model(self, model_id: str) -> bool:
        """Return whether a model was added by the user.

        Args:
            model_id: Unique model identifier.
        """
        entry = self._models.get(model_id)
        return entry is not None and entry.source == "user"

    def list_user_models(self) -> list[ModelEntry]:
        """Return every user-added model entry."""
        return [e for e in self._models.values() if e.source == "user"]

    def add_user_model(self, entry_data: dict) -> ModelEntry:
        """Register and persist a user-added model.

        Args:
            entry_data: A manifest entry, typically from
                :func:`tessera.models.hf_metadata.build_user_entry`.

        Returns:
            ModelEntry: The registered entry.

        Raises:
            ManifestLoadError: If the entry is invalid, collides with an
                existing model, or cannot be saved.
        """
        from . import ManifestLoadError

        entry_data = dict(entry_data)
        entry_data["source"] = "user"
        entry = _parse_model_entry(entry_data)
        if entry is None:
            raise ManifestLoadError(
                "That model entry is missing required fields and was not added."
            )
        if entry.model_id in self._models:
            raise ManifestLoadError(
                f"A model named '{entry.model_id}' is already registered. "
                f"Remove it first, or choose a different name."
            )

        self._models[entry.model_id] = entry
        try:
            self._save_user_manifest()
        except Exception:
            del self._models[entry.model_id]
            raise

        logger.info(
            "User model added: model_id=%s, repo=%s, license=%s (%s)",
            entry.model_id,
            entry.repo_id,
            entry.license,
            entry.commercial_use,
        )
        return entry

    def remove_user_model(self, model_id: str) -> bool:
        """Unregister a user-added model and persist the change.

        Cached weight files are left on disk — deleting them is the cache
        manager's job, and the user may want to re-add the model.

        Args:
            model_id: Unique model identifier.

        Returns:
            bool: ``True`` if a user model was removed.

        Raises:
            ManifestLoadError: If the model is bundled rather than
                user-added, or the change cannot be saved.
        """
        from . import ManifestLoadError

        if model_id in self._bundled_ids:
            raise ManifestLoadError(
                f"'{model_id}' ships with Tessera and cannot be removed."
            )
        if model_id not in self._models:
            return False

        entry = self._models.pop(model_id)
        try:
            self._save_user_manifest()
        except Exception:
            self._models[model_id] = entry
            raise

        logger.info("User model removed: model_id=%s", model_id)
        return True

    def list_models(self) -> list[ModelEntry]:
        """List all registered models.

        Returns:
            list[ModelEntry]: All valid model entries from the manifest.
        """
        return list(self._models.values())

    def get_model(self, model_id: str) -> ModelEntry:
        """Get a specific model entry by ID.

        Args:
            model_id: Unique model identifier.

        Returns:
            ModelEntry: The requested model entry.

        Raises:
            ModelNotFoundError: If the model_id is not in the registry.
        """
        from . import ModelNotFoundError

        if model_id not in self._models:
            raise ModelNotFoundError(
                f"Model '{model_id}' not found in registry. "
                f"Available models: {list(self._models.keys())}"
            )
        return self._models[model_id]

    def __len__(self) -> int:
        """Return the number of registered models."""
        return len(self._models)

    def __contains__(self, model_id: str) -> bool:
        """Check if a model_id exists in the registry."""
        return model_id in self._models
