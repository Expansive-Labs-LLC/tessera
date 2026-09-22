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
        variants=variants,
    )


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

    def __init__(self, manifest_path: Optional[Path] = None):
        """Initialize the registry by loading the manifest.

        Args:
            manifest_path: Optional override for the manifest file path.
                Defaults to the embedded ``manifest.json``.

        Raises:
            ManifestLoadError: If the file is missing or contains invalid JSON.
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

        logger.info("Model registry loaded: %d models from manifest", len(self._models))

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
