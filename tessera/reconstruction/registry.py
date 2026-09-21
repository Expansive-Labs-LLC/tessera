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

"""Adapter registry for the reconstruction engine.

Discovers, registers, and selects reconstruction adapters using the
selection algorithm defined in SPEC-TS-0004 §2.3.

Spec: SPEC-TS-0004 (Single-Image 3D Reconstruction Engine)

Public API:
    AdapterRegistry — discovers, registers, selects adapters (FR-006)
"""

from __future__ import annotations

import logging
import time

from tessera.reconstruction.adapter import ReconstructionAdapter
from tessera.reconstruction.adapters.stub_adapter import StubAdapter
from tessera.reconstruction.mesh_output import AdapterCapabilities

logger = logging.getLogger("tessera.reconstruction")


class AdapterRegistry:
    """Discovers, registers, and selects reconstruction adapters.

    Implements the six-step selection algorithm from §2.3:

    1. Filter by input compatibility (min/max images)
    2. Filter by weight availability (model files exist in cache)
    3. Filter by VRAM (min_vram_gb ≤ available)
    4. Exclude ``StubAdapter`` unless it's the only candidate
    5. Rank by highest ``min_vram_gb`` (prefer most capable)
    6. Fallback to ``StubAdapter`` or ``None``

    Implements: FR-006.
    """

    def __init__(self) -> None:
        """Initialise an empty adapter registry."""
        self._adapters: dict[str, ReconstructionAdapter] = {}

    def register(self, adapter: ReconstructionAdapter) -> None:
        """Register a concrete adapter instance.

        Args:
            adapter: An initialised ``ReconstructionAdapter`` subclass.
        """
        caps = adapter.capabilities()
        self._adapters[caps.model_name] = adapter
        logger.debug("Adapter registered: %s", caps.model_name)

    def list_all(self) -> list[AdapterCapabilities]:
        """List capabilities of all registered adapters.

        Returns:
            List of ``AdapterCapabilities`` from every registered
            adapter.
        """
        return [a.capabilities() for a in self._adapters.values()]

    def list_available(self, cache_dir: str) -> list[AdapterCapabilities]:
        """List adapters whose model weights are available.

        Args:
            cache_dir: Path to the model weight cache directory.

        Returns:
            Capabilities of adapters with weights present on disk.
        """
        result = []
        for adapter in self._adapters.values():
            if hasattr(adapter, "weights_available"):
                if adapter.weights_available():
                    result.append(adapter.capabilities())
            else:
                # Adapters without weight requirements (e.g. StubAdapter)
                result.append(adapter.capabilities())
        return result

    def get_capabilities(self, model_name: str) -> AdapterCapabilities | None:
        """Get capabilities of a specific adapter by model name.

        Args:
            model_name: The ``model_name`` from the adapter's
                capabilities.

        Returns:
            ``AdapterCapabilities`` or ``None`` if not found.
        """
        adapter = self._adapters.get(model_name)
        if adapter is not None:
            return adapter.capabilities()
        return None

    def select(
        self,
        input_count: int,
        cache_dir: str,
        available_vram_gb: float,
    ) -> ReconstructionAdapter | None:
        """Select the best adapter for the given conditions.

        Implements the six-step selection algorithm from §2.3.

        Args:
            input_count: Number of input images.
            cache_dir: Path to the model weight cache directory.
            available_vram_gb: Available GPU VRAM in GB.

        Returns:
            The best matching adapter, or ``None`` if no adapter
            can handle the request.
        """
        start = time.monotonic()
        candidates: list[tuple[float, str, ReconstructionAdapter]] = []

        for name, adapter in self._adapters.items():
            caps = adapter.capabilities()

            # Step 1: Filter by input compatibility
            if not (caps.min_images <= input_count <= caps.max_images):
                logger.debug(
                    "Adapter %s excluded: input_count=%d not in [%d, %d]",
                    name,
                    input_count,
                    caps.min_images,
                    caps.max_images,
                )
                continue

            # Step 2: Filter by weight availability
            if hasattr(adapter, "weights_available"):
                if not adapter.weights_available():
                    logger.debug(
                        "Adapter %s excluded: weights not available",
                        name,
                    )
                    continue

            # Step 3: Filter by VRAM
            if caps.min_vram_gb > available_vram_gb and caps.min_vram_gb > 0:
                logger.debug(
                    "Adapter %s excluded: requires %.1f GB VRAM, " "available %.1f GB",
                    name,
                    caps.min_vram_gb,
                    available_vram_gb,
                )
                continue

            candidates.append((caps.min_vram_gb, name, adapter))

        # Step 4: Exclude StubAdapter unless it's the only candidate
        non_stub = [
            (vram, n, a) for vram, n, a in candidates if not isinstance(a, StubAdapter)
        ]
        stub_candidates = [
            (vram, n, a) for vram, n, a in candidates if isinstance(a, StubAdapter)
        ]

        if non_stub:
            # Step 5: Rank by highest min_vram_gb
            non_stub.sort(key=lambda t: t[0], reverse=True)
            selected = non_stub[0]
        elif stub_candidates:
            # Step 6: Fallback to StubAdapter
            selected = stub_candidates[0]
        else:
            # No adapter available
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.debug(
                "Adapter selection completed in %.1f ms: no adapter found",
                elapsed_ms,
            )
            return None

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.debug(
            "Adapter selection completed in %.1f ms: selected %s",
            elapsed_ms,
            selected[1],
        )
        return selected[2]

    def __len__(self) -> int:
        """Return the number of registered adapters."""
        return len(self._adapters)

    def __contains__(self, model_name: str) -> bool:
        """Check if an adapter with the given model name is registered."""
        return model_name in self._adapters
