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

"""VRAM-aware model variant selection for Tessera.

Selects the best model variant based on available GPU VRAM.

Implements: FR-012, EC-005.

Public API:
    select_variant(model_entry, available_vram_gb) -> tuple[ModelVariant, str]
"""

import logging
from typing import Optional

from .registry import ModelEntry, ModelVariant

logger = logging.getLogger("tessera.models")


def select_variant(
    model_entry: ModelEntry,
    available_vram_gb: float,
) -> tuple[ModelVariant, Optional[str]]:
    """Select the best model variant for the available VRAM.

    Selection logic (FR-012):
    1. If ``model_entry.variants`` is empty, return a default variant
       constructed from the model's top-level fields with
       ``variant_id="default"``.
    2. Sort variants by ``min_vram_gb`` descending (highest quality first).
    3. Select the first variant whose ``min_vram_gb <= available_vram_gb``.
    4. If no variant fits (EC-005), select the smallest variant and return
       a warning message.

    Args:
        model_entry: The model entry from the registry.
        available_vram_gb: GPU VRAM available in GB.

    Returns:
        tuple: (ModelVariant, Optional[str]) — the selected variant and
            an optional warning message (None if no warning).

    Example:
        >>> variant, warning = select_variant(entry, 6.0)
        >>> variant.variant_id
        'fp16'
        >>> warning is None
        True
    """
    # FR-012: Empty variants → return default constructed from top-level fields
    if not model_entry.variants:
        default_variant = ModelVariant(
            variant_id="default",
            min_vram_gb=model_entry.min_vram_gb,
            size_bytes=model_entry.size_bytes,
            files=list(model_entry.files),
        )
        logger.info(
            "VRAM variant selected: model=%s, variant=%s, "
            "available_vram_gb=%.1f, required_vram_gb=%.1f",
            model_entry.model_id,
            default_variant.variant_id,
            available_vram_gb,
            default_variant.min_vram_gb,
        )
        return default_variant, None

    # Sort by min_vram_gb descending (highest quality first)
    sorted_variants = sorted(
        model_entry.variants,
        key=lambda v: v.min_vram_gb,
        reverse=True,
    )

    # Select the highest-quality variant that fits
    for variant in sorted_variants:
        if variant.min_vram_gb <= available_vram_gb:
            logger.info(
                "VRAM variant selected: model=%s, variant=%s, "
                "available_vram_gb=%.1f, required_vram_gb=%.1f",
                model_entry.model_id,
                variant.variant_id,
                available_vram_gb,
                variant.min_vram_gb,
            )
            return variant, None

    # EC-005: VRAM below all variants — select smallest, return warning
    smallest = sorted_variants[-1]  # Last after desc sort = smallest
    warning = (
        f"Your GPU has {available_vram_gb:.1f} GB VRAM. "
        f"Model {model_entry.model_id} requires at least "
        f"{smallest.min_vram_gb:.0f} GB. "
        f"Inference may fail or fall back to CPU."
    )
    logger.warning(
        "VRAM variant selected (insufficient VRAM): model=%s, variant=%s, "
        "available_vram_gb=%.1f, required_vram_gb=%.1f",
        model_entry.model_id,
        smallest.variant_id,
        available_vram_gb,
        smallest.min_vram_gb,
    )
    return smallest, warning
