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

"""VRAM availability guard for reconstruction inference.

Checks available GPU memory before loading model weights or running
inference to fail fast with an actionable error message rather than
crashing mid-inference.

Spec: SPEC-TS-0004 (Single-Image 3D Reconstruction Engine)

Public API:
    VRAMGuard — VRAM availability checker (FR-012, CON-004)
"""

from __future__ import annotations

import logging

logger = logging.getLogger("tessera.reconstruction")


class VRAMGuard:
    """Check GPU VRAM availability before reconstruction.

    Uses PyTorch's CUDA memory API to query free GPU memory and
    compare against the adapter's declared minimum requirement.

    Implements: FR-012, CON-004.
    """

    @staticmethod
    def check(required_gb: float) -> tuple[bool, float]:
        """Check whether sufficient VRAM is available.

        Args:
            required_gb: Minimum VRAM required in GB.

        Returns:
            Tuple of ``(ok, available_gb)`` where ``ok`` is ``True``
            if ``available_gb >= required_gb``.
        """
        available_gb = VRAMGuard.get_available_vram_gb()
        ok = available_gb >= required_gb
        if ok:
            logger.debug(
                "VRAM check passed: required=%.1f GB, available=%.1f GB",
                required_gb,
                available_gb,
            )
        else:
            logger.error(
                "VRAM check failed: required=%.1f GB, available=%.1f GB",
                required_gb,
                available_gb,
            )
        return ok, available_gb

    @staticmethod
    def get_available_vram_gb() -> float:
        """Query current available GPU VRAM in GB.

        Attempts CUDA first, then ROCm (HIP).  Returns ``0.0`` if
        no GPU is available or PyTorch is not installed with GPU
        support.

        Returns:
            Available VRAM in GB.
        """
        try:
            import torch

            if torch.cuda.is_available():
                # torch.cuda.mem_get_info() returns (free, total) in bytes
                free_bytes, _total_bytes = torch.cuda.mem_get_info()
                return free_bytes / (1024**3)

            # ROCm devices also expose via torch.cuda on AMD GPUs
            # when PyTorch is built with ROCm support
        except (ImportError, RuntimeError, AssertionError) as exc:
            logger.debug("VRAM query failed: %s", exc)

        return 0.0

    @staticmethod
    def cleanup_gpu() -> float:
        """Release all GPU tensors and clear the CUDA/ROCm cache.

        Should be called after reconstruction completes (both
        success and failure) to prevent VRAM leaks.

        Returns:
            Approximate MB of memory freed.

        Implements: FR-015, CON-003.
        """
        freed_mb = 0.0
        try:
            import torch

            if torch.cuda.is_available():
                before = torch.cuda.memory_allocated()
                # Synchronise to ensure all kernels are complete
                torch.cuda.synchronize()
                # Clear the cache
                torch.cuda.empty_cache()
                after = torch.cuda.memory_allocated()
                freed_mb = (before - after) / (1024**2)
                logger.debug("VRAM cleanup completed: freed %.1f MB", freed_mb)
        except (ImportError, RuntimeError) as exc:
            logger.debug("VRAM cleanup skipped: %s", exc)

        return freed_mb
