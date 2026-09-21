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

"""GPU detection for Tessera.

Uses Blender's Cycles device API as the primary detection mechanism,
with subprocess fallback for VRAM queries. See SPEC-TS-0001 §2.3.

Public API:
    get_gpu_info() -> dict
"""

import logging

import bpy

from .utils.gpu_utils import (
    get_amd_vram_gb,
    get_apple_silicon_memory_gb,
    get_nvidia_vram_gb,
    is_apple_silicon,
    is_macos,
)

logger = logging.getLogger("tessera")


def _get_cycles_devices(compute_type):
    """Safely query Cycles for devices of a given compute type.

    Args:
        compute_type: One of 'CUDA', 'HIP', 'METAL'.

    Returns:
        list: List of Cycles device objects, or empty list on failure.
    """
    try:
        cycles_prefs = bpy.context.preferences.addons["cycles"].preferences
        cycles_prefs.get_devices(compute_type)
        return [
            d
            for d in cycles_prefs.devices
            if d.type == compute_type and d.type != "CPU"
        ]
    except (KeyError, AttributeError, RuntimeError) as e:
        logger.debug("Cycles %s device query failed: %s", compute_type, e)
        return []


def _detect_cuda_gpu():
    """Detect CUDA (NVIDIA) GPU via Cycles API.

    Returns:
        dict or None: GPU info dict if found, None otherwise.
    """
    devices = _get_cycles_devices("CUDA")
    if not devices:
        return None

    device = devices[0]
    vram_gb = 0.0

    # Try to get VRAM from Cycles device data
    if hasattr(device, "total_memory") and device.total_memory > 0:
        vram_gb = round(device.total_memory / (1024 ** 3), 1)
    else:
        # Fallback: nvidia-smi subprocess
        vram_gb = get_nvidia_vram_gb()

    return {
        "name": device.name,
        "vram_gb": vram_gb,
        "backend": "CUDA",
        "shared_memory": False,
    }


def _detect_hip_gpu():
    """Detect ROCm/HIP (AMD) GPU via Cycles API.

    Returns:
        dict or None: GPU info dict if found, None otherwise.
    """
    devices = _get_cycles_devices("HIP")
    if not devices:
        return None

    device = devices[0]
    vram_gb = 0.0

    if hasattr(device, "total_memory") and device.total_memory > 0:
        vram_gb = round(device.total_memory / (1024 ** 3), 1)
    else:
        # Fallback: rocm-smi subprocess
        vram_gb = get_amd_vram_gb()

    return {
        "name": device.name,
        "vram_gb": vram_gb,
        "backend": "ROCM",
        "shared_memory": False,
    }


def _detect_metal_gpu():
    """Detect Metal (Apple Silicon) GPU via Cycles API.

    For Apple Silicon, VRAM is shared system memory reported with
    a '(shared)' suffix per FR-009.

    Returns:
        dict or None: GPU info dict if found, None otherwise.
    """
    if not is_macos():
        return None

    devices = _get_cycles_devices("METAL")
    if not devices:
        return None

    device = devices[0]
    shared = is_apple_silicon()

    if shared:
        vram_gb = get_apple_silicon_memory_gb()
    elif hasattr(device, "total_memory") and device.total_memory > 0:
        vram_gb = round(device.total_memory / (1024 ** 3), 1)
    else:
        vram_gb = 0.0

    return {
        "name": device.name,
        "vram_gb": vram_gb,
        "backend": "METAL",
        "shared_memory": shared,
    }


def get_gpu_info():
    """Detect available GPU and return info dict.

    Detection order: CUDA → HIP (ROCm) → Metal.
    Returns the first compatible GPU found.

    Returns:
        dict: GPU information with keys:
            - ``name`` (str or None): GPU device name.
            - ``vram_gb`` (float): VRAM in GB (0 if unknown).
            - ``backend`` (str or None): One of 'CUDA', 'ROCM', 'METAL', or None.
            - ``shared_memory`` (bool): True for Apple Silicon unified memory.

    Example:
        >>> info = get_gpu_info()
        >>> info
        {"name": "NVIDIA GeForce RTX 3060", "vram_gb": 12.0, "backend": "CUDA",
         "shared_memory": False}
    """
    # Try detection in priority order
    for detector in (_detect_cuda_gpu, _detect_hip_gpu, _detect_metal_gpu):
        try:
            result = detector()
            if result is not None:
                logger.info(
                    "GPU detected: %s (%s, %.1f GB%s)",
                    result["name"],
                    result["backend"],
                    result["vram_gb"],
                    " shared" if result.get("shared_memory") else "",
                )
                return result
        except Exception as e:
            logger.warning("GPU detection failed in %s: %s", detector.__name__, e)

    logger.warning("No compatible GPU detected (CUDA, ROCm, or Metal)")
    return {
        "name": None,
        "vram_gb": 0,
        "backend": None,
        "shared_memory": False,
    }
