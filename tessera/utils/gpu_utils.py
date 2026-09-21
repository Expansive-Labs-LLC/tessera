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

"""GPU query helper functions for Tessera.

Provides platform-specific VRAM detection via subprocess fallback when
Blender's Cycles device API does not report memory information.
"""

import logging
import os
import platform
import subprocess

logger = logging.getLogger("tessera")


def get_nvidia_vram_gb():
    """Query NVIDIA GPU VRAM via nvidia-smi.

    Returns:
        float: VRAM in GB, or 0.0 if nvidia-smi is unavailable or fails.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            # nvidia-smi reports in MiB
            vram_mib = float(result.stdout.strip().split("\n")[0])
            return round(vram_mib / 1024.0, 1)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
        logger.debug("nvidia-smi VRAM query failed: %s", e)
    return 0.0


def get_amd_vram_gb():
    """Query AMD GPU VRAM via rocm-smi.

    Returns:
        float: VRAM in GB, or 0.0 if rocm-smi is unavailable or fails.
    """
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Parse "Total" line from rocm-smi output
            for line in result.stdout.split("\n"):
                if "Total" in line:
                    # Extract numeric value (in bytes typically)
                    parts = line.split()
                    for part in parts:
                        try:
                            value = float(part)
                            # Heuristic: if value > 1_000_000, assume bytes
                            if value > 1_000_000:
                                return round(value / (1024 ** 3), 1)
                            # If value > 1000, assume MiB
                            elif value > 1000:
                                return round(value / 1024.0, 1)
                            else:
                                return round(value, 1)
                        except ValueError:
                            continue
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
        logger.debug("rocm-smi VRAM query failed: %s", e)
    return 0.0


def get_apple_silicon_memory_gb():
    """Get total system memory on Apple Silicon (shared with GPU).

    Returns:
        float: Total system memory in GB, or 0.0 if unavailable.
    """
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
        total_bytes = page_size * page_count
        return round(total_bytes / (1024 ** 3), 1)
    except (ValueError, OSError) as e:
        logger.debug("Apple Silicon memory query failed: %s", e)
    return 0.0


def is_macos():
    """Check if the current platform is macOS.

    Returns:
        bool: True if running on macOS.
    """
    return platform.system() == "Darwin"


def is_apple_silicon():
    """Check if the current platform is Apple Silicon (ARM64 macOS).

    Returns:
        bool: True if running on Apple Silicon Mac.
    """
    return is_macos() and platform.machine() == "arm64"
