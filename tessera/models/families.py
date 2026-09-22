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

"""Model architecture families that Tessera's adapters know how to load.

The manifest is user-extensible (SPEC-TS-0002 FR-025 – FR-032): a user can
add a model from Hugging Face and Tessera will licence-check it, verify its
digests and download it. What Tessera cannot do is *load* an arbitrary
architecture — every adapter instantiates a specific model class. A
user-added model therefore declares the **family** it belongs to, and
Tessera only offers families an adapter can consume.

Spec: SPEC-TS-0002 (Local Model Weight Management)

Public API:
    ModelFamily — describes one loadable architecture family
    FAMILIES — the supported families, keyed by ``family_id``
    get_family / list_families / family_choices
    DEPTH_ANYTHING_V2_VARIANTS — architecture configs by encoder
"""

from dataclasses import dataclass, field
from typing import Optional

# Depth Anything V2 architecture configs, keyed by encoder. These mirror the
# upstream reference configs and are the single source of truth for the depth
# adapter — a user-added checkpoint is loadable as long as its encoder is here.
#
# Licence note: only the Small (vits) checkpoint is Apache-2.0. Base, Large
# and Giant are CC-BY-NC-4.0 and are gated by tessera.models.licensing.
DEPTH_ANYTHING_V2_VARIANTS: dict[str, dict] = {
    "vits": {
        "display_name": "Depth Anything V2 Small",
        "checkpoint": "depth_anything_v2_vits.pth",
        "encoder": "vits",
        "features": 64,
        "out_channels": [48, 96, 192, 384],
        "vram_gb": 1.5,
    },
    "vitb": {
        "display_name": "Depth Anything V2 Base",
        "checkpoint": "depth_anything_v2_vitb.pth",
        "encoder": "vitb",
        "features": 128,
        "out_channels": [96, 192, 384, 768],
        "vram_gb": 2.5,
    },
    "vitl": {
        "display_name": "Depth Anything V2 Large",
        "checkpoint": "depth_anything_v2_vitl.pth",
        "encoder": "vitl",
        "features": 256,
        "out_channels": [256, 512, 1024, 1024],
        "vram_gb": 3.0,
    },
    "vitg": {
        "display_name": "Depth Anything V2 Giant",
        "checkpoint": "depth_anything_v2_vitg.pth",
        "encoder": "vitg",
        "features": 384,
        "out_channels": [1536, 1536, 1536, 1536],
        "vram_gb": 6.0,
    },
}


@dataclass(frozen=True)
class ModelFamily:
    """One architecture family an adapter knows how to instantiate.

    Attributes:
        family_id: Stable identifier used in manifest entries.
        display_name: Human-readable name for the UI.
        stage: Which pipeline stage consumes it.
        adapter: Dotted path of the adapter class, for documentation.
        allowed_suffixes: File extensions accepted for this family.
        adapter_ready: Whether the adapter can load an arbitrary variant of
            this family today. When ``False`` a user-added model is still
            downloaded, verified and cached, but the adapter cannot yet be
            pointed at it — see ``pending_task``.
        pending_task: Task that makes ``adapter_ready`` true.
        variants: Optional architecture configs, keyed by variant id.
        notes: Guidance shown next to the family in the UI and docs.
    """

    family_id: str
    display_name: str
    stage: str
    adapter: str
    allowed_suffixes: tuple[str, ...]
    adapter_ready: bool
    pending_task: Optional[str] = None
    variants: dict[str, dict] = field(default_factory=dict)
    notes: str = ""


FAMILIES: dict[str, ModelFamily] = {
    "depth-anything-v2": ModelFamily(
        family_id="depth-anything-v2",
        display_name="Depth Anything V2",
        stage="Depth estimation",
        adapter="tessera.vision.depth.depth_anything_adapter.DepthAnythingAdapter",
        allowed_suffixes=(".pth", ".safetensors"),
        adapter_ready=True,
        variants=DEPTH_ANYTHING_V2_VARIANTS,
        notes=(
            "Any Depth Anything V2 checkpoint whose encoder is vits, vitb, "
            "vitl or vitg. Only the Small (vits) checkpoint is Apache-2.0; "
            "the larger ones are CC-BY-NC-4.0 and are licence-gated."
        ),
    ),
    "sam2": ModelFamily(
        family_id="sam2",
        display_name="Segment Anything 2",
        stage="Segmentation",
        adapter="tessera.vision.segmentation.sam2_adapter.SAM2Adapter",
        allowed_suffixes=(".safetensors", ".pt", ".yaml", ".json"),
        adapter_ready=False,
        pending_task="TASK-TS-0016",
        notes=(
            "Downloadable and verified today, but the adapter still resolves "
            "a fixed checkpoint filename, so it cannot yet be pointed at an "
            "alternative SAM 2 size."
        ),
    ),
    "dinov2": ModelFamily(
        family_id="dinov2",
        display_name="DINOv2",
        stage="Feature extraction",
        adapter="tessera.vision.features.dinov2_adapter.DINOv2Adapter",
        allowed_suffixes=(".safetensors", ".pth", ".json"),
        adapter_ready=False,
        pending_task="TASK-TS-0016",
        notes=(
            "Downloadable and verified today; the adapter's loader is still "
            "pinned to one checkpoint."
        ),
    ),
    "trellis": ModelFamily(
        family_id="trellis",
        display_name="TRELLIS",
        stage="3D reconstruction",
        adapter="tessera.reconstruction.adapters.trellis_adapter.TrellisAdapter",
        allowed_suffixes=(".safetensors", ".json"),
        adapter_ready=False,
        pending_task="TASK-TS-0017",
        notes=(
            "Downloadable and verified today, and the adapter now resolves "
            "and verifies weights through the model cache, so the layout "
            "matches. What remains is the inference runtime: torch built "
            "for the host CUDA version plus TRELLIS's compiled CUDA "
            "extensions (TASK-TS-0017)."
        ),
    ),
}


def get_family(family_id: str) -> Optional[ModelFamily]:
    """Return the family with this id, or ``None`` if unsupported.

    Args:
        family_id: Family identifier from a manifest entry.
    """
    return FAMILIES.get(family_id)


def list_families() -> list[ModelFamily]:
    """Return every supported family, ordered by display name."""
    return sorted(FAMILIES.values(), key=lambda f: f.display_name)


def family_choices() -> list[tuple[str, str, str]]:
    """Return ``(id, label, description)`` triples for a Blender EnumProperty."""
    return [
        (
            f.family_id,
            f.display_name,
            f"{f.stage} — {f.notes}" if f.notes else f.stage,
        )
        for f in list_families()
    ]


def resolve_variant(family_id: str, variant_id: Optional[str]) -> Optional[dict]:
    """Return the architecture config for a family variant.

    Args:
        family_id: Family identifier.
        variant_id: Variant identifier within the family (e.g. ``"vitb"``).

    Returns:
        Optional[dict]: The config, or ``None`` when the family has no
        variant table or the variant is unknown.
    """
    family = get_family(family_id)
    if family is None or not variant_id:
        return None
    return family.variants.get(variant_id)
