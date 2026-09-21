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

"""Model cache with LRU eviction and lazy loading support.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-012, FR-013, FR-014.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("tessera.perf")

# FR-013: Maximum number of models in the cache.
_MAX_CACHE_SIZE = 3


@dataclass
class CachedModel:
    """A model entry in the LRU cache.

    Attributes:
        name: Human-readable model name.
        model: The loaded model object.
        loaded_at: Timestamp when the model was loaded.
        last_used: Timestamp of last access.
        gpu_memory_mb: Estimated GPU memory usage in MB.
        active: Whether the model is currently in an inference call.
    """

    name: str
    model: Any
    loaded_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    gpu_memory_mb: float = 0.0
    active: bool = False


class ModelCache:
    """LRU model cache for lazy loading and VRAM management.

    Models are loaded on first use (lazy loading, FR-012) and
    remain cached until VRAM pressure triggers LRU eviction
    (FR-013). The cache holds a maximum of 3 models. Active
    models (in-use for inference) are never evicted.

    Usage::

        cache = ModelCache()
        model = cache.get_or_load("sam2", loader_fn)

        with cache.active_inference("sam2"):
            result = model.predict(input_data)

    Implements: FR-012, FR-013, FR-014.
    """

    def __init__(self, max_size: int = _MAX_CACHE_SIZE) -> None:
        self._cache: OrderedDict[str, CachedModel] = OrderedDict()
        self._max_size = max_size

    @property
    def size(self) -> int:
        """Number of models currently in the cache."""
        return len(self._cache)

    @property
    def model_names(self) -> list[str]:
        """Names of all cached models."""
        return list(self._cache.keys())

    def get(self, name: str) -> Optional[Any]:
        """Get a cached model by name without loading.

        Args:
            name: Model name.

        Returns:
            The model object if cached, ``None`` otherwise.
        """
        entry = self._cache.get(name)
        if entry is not None:
            entry.last_used = time.time()
            # Move to end (most recently used).
            self._cache.move_to_end(name)
            return entry.model
        return None

    def get_or_load(
        self,
        name: str,
        loader: Any,
        estimated_gpu_mb: float = 0.0,
    ) -> Any:
        """Get a cached model or load it if not present.

        Implements lazy loading (FR-012): the model is only loaded
        when this method is first called. If the cache is full,
        the least-recently-used non-active model is evicted (FR-013).

        Args:
            name: Model name identifier.
            loader: Callable that returns the loaded model.
            estimated_gpu_mb: Estimated GPU memory usage in MB.

        Returns:
            The loaded model object.

        Raises:
            RuntimeError: If all cached models are active and a new
                model needs to be loaded (BF-E002 scenario, FR-013).

        Implements: FR-012, FR-013.
        """
        # Check if already cached.
        existing = self.get(name)
        if existing is not None:
            logger.debug(
                "Model cache hit: model_name=%s, cache_size=%d",
                name,
                self.size,
            )
            return existing

        # Evict if cache is full.
        if self.size >= self._max_size:
            evicted = self._evict_lru()
            if not evicted:
                raise RuntimeError(
                    f"Cannot load model '{name}': all {self._max_size} "
                    f"cached models are in active use. "
                    f"Wait for a current operation to complete."
                )

        # Load the model.
        logger.info(
            "Model loading (lazy): model_name=%s, "
            "estimated_gpu_memory_mb=%.0f",
            name,
            estimated_gpu_mb,
        )
        load_start = time.perf_counter()
        model = loader()
        load_time = time.perf_counter() - load_start

        entry = CachedModel(
            name=name,
            model=model,
            gpu_memory_mb=estimated_gpu_mb,
        )
        self._cache[name] = entry

        logger.info(
            "Model loaded: model_name=%s, load_time_seconds=%.2f, "
            "gpu_memory_used_mb=%.0f",
            name,
            load_time,
            estimated_gpu_mb,
        )

        return model

    def mark_active(self, name: str) -> None:
        """Mark a model as actively in use for inference.

        Active models are protected from LRU eviction.

        Args:
            name: Model name.
        """
        entry = self._cache.get(name)
        if entry is not None:
            entry.active = True

    def mark_inactive(self, name: str) -> None:
        """Mark a model as no longer in active use.

        Args:
            name: Model name.
        """
        entry = self._cache.get(name)
        if entry is not None:
            entry.active = False

    def evict(self, name: str) -> bool:
        """Explicitly evict a model from the cache.

        Args:
            name: Model name to evict.

        Returns:
            ``True`` if the model was evicted, ``False`` if not found
            or active.
        """
        entry = self._cache.get(name)
        if entry is None:
            return False
        if entry.active:
            logger.warning(
                "Cannot evict active model: model_name=%s", name
            )
            return False

        del self._cache[name]
        logger.info(
            "Model evicted: model_name=%s, reason=explicit",
            name,
        )
        return True

    def clear(self) -> None:
        """Clear all models from the cache."""
        for name in list(self._cache.keys()):
            self.evict(name)
        self._cache.clear()

    def _evict_lru(self) -> bool:
        """Evict the least-recently-used non-active model.

        Returns:
            ``True`` if a model was evicted, ``False`` if all are
            active (FR-013 guard).
        """
        for name, entry in self._cache.items():
            if not entry.active:
                del self._cache[name]
                logger.info(
                    "Model evicted: model_name=%s, reason=LRU",
                    name,
                )
                return True

        logger.warning(
            "LRU eviction failed: all %d cached models are active",
            self.size,
        )
        return False
