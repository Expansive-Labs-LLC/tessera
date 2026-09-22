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

"""Process-lifetime state: the cache root, the token, the device.

The **cache root arrives as a launch argument and never moves**. Taking it
from a request would hand any caller the ability to point the engine at
any directory, which is exactly what SEC-003's containment check exists to
prevent — a check against a root the attacker supplies is not a check
(FR-033, CON-011).

The **token is generated per start** and written owner-readable into the
runtime descriptor. The add-on reads it from there. Anything that cannot
read that file cannot talk to the engine, which is the property loopback
alone does not give (FR-032, FR-037, SEC-007).

**Device selection is one replaceable component.** v1 is CUDA-only, but
the boundary is the reason ROCm and Metal become engine builds rather than
an add-on redesign, and that only holds if the device choice sits in one
place (FR-024).

Spec: SPEC-TS-0023 (FR-024, FR-032, FR-033, FR-039, SEC-003, CON-011)

Public API:
    EngineRuntime — the engine's process-lifetime state
    DeviceInfo — what /health reports about the GPU
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import ENGINE_VERSION, PROTOCOL_VERSIONS
from .errors import EngineFault

logger = logging.getLogger("tessera_engine")


@dataclass(frozen=True)
class DeviceInfo:
    """What the engine can say about its compute device.

    Attributes:
        available: Whether inference can run at all.
        name: GPU name, or a reason when unavailable.
        total_vram_gb: Total device memory in GB; 0.0 when unavailable.
        free_vram_gb: Free device memory in GB; 0.0 when unavailable.
    """

    available: bool
    name: str
    total_vram_gb: float
    free_vram_gb: float


def probe_device() -> DeviceInfo:
    """Return what is known about the CUDA device (FR-004, FR-024).

    The single place the engine decides what it is running on. Adding ROCm
    or Metal later replaces this function and nothing else on either side
    of the boundary.

    Returns:
        The device description; ``available=False`` when there is no
        usable CUDA device, including when torch is not installed, which
        is the normal state in CI.
    """
    try:
        import torch
    except ImportError:
        return DeviceInfo(False, "PyTorch is not installed", 0.0, 0.0)

    if not torch.cuda.is_available():
        return DeviceInfo(False, "No CUDA device available", 0.0, 0.0)

    index = torch.cuda.current_device()
    free_b, total_b = torch.cuda.mem_get_info(index)
    return DeviceInfo(
        available=True,
        name=torch.cuda.get_device_name(index),
        total_vram_gb=round(total_b / 1024**3, 2),
        free_vram_gb=round(free_b / 1024**3, 2),
    )


def _descriptor_path() -> Path:
    """Return where the runtime descriptor lives (FR-032).

    Mirrors ``tessera.engine.discovery.runtime_descriptor_path`` on the
    add-on side. The two are separate programs, so the path is part of the
    contract between them rather than a shared import.
    """
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "Tessera" / "engine" / "runtime.json"
    base = (
        os.environ.get("XDG_RUNTIME_DIR")
        or os.environ.get("XDG_STATE_HOME")
        or str(Path.home() / ".local" / "state")
    )
    return Path(base) / "tessera" / "engine" / "runtime.json"


class EngineRuntime:
    """State fixed for the life of the process.

    Args:
        cache_root: The weight cache the add-on governs. Every weight path
            in every request must resolve inside it.
        port: Port the server bound.
        log_path: Where this engine writes its log, reported to the add-on
            so a failure can point at something readable (FR-040).
        descriptor_path: Override for tests.
    """

    def __init__(
        self,
        cache_root: Path,
        port: int,
        log_path: Path,
        descriptor_path: Optional[Path] = None,
    ):
        # resolve() here, once, so every later containment check compares
        # two canonical paths rather than re-deriving one each time.
        self.cache_root = Path(cache_root).expanduser().resolve()
        self.port = int(port)
        self.log_path = Path(log_path)
        self.token = secrets.token_hex(32)
        self._descriptor_path = descriptor_path or _descriptor_path()

    # ------------------------------------------------------------------
    # Weight paths
    # ------------------------------------------------------------------

    def resolve_weight_path(self, raw: str, model_id: str) -> Path:
        """Canonicalise one weight path and confirm it is inside the root.

        Resolution happens before the check, so a symlink or ``..`` cannot
        walk out of the cache root after passing it (SEC-003).

        A path outside the root returns ``weights_missing`` — the same
        slug as one that genuinely does not exist. Distinguishing them
        would let a caller use the engine to probe for files it cannot
        read, and the add-on has no use for the distinction.

        Args:
            raw: The path as it arrived in the request.
            model_id: Model this path is for, named in errors.

        Returns:
            The resolved path.

        Raises:
            EngineFault: ``weights_missing`` if outside the root or absent.
        """
        if not isinstance(raw, str) or not raw:
            raise EngineFault(
                "bad_request",
                f"weight path for {model_id} is not a string",
                field=f"weight_paths.{model_id}",
            )
        try:
            candidate = Path(raw).expanduser().resolve()
        except (OSError, RuntimeError) as exc:
            raise EngineFault(
                "weights_missing",
                f"{model_id}: path could not be resolved ({exc})",
                model_id=model_id,
            ) from exc

        if not candidate.is_relative_to(self.cache_root):
            logger.warning(
                "refused weight path for %s outside the cache root", model_id
            )
            raise EngineFault(
                "weights_missing",
                f"{model_id}: no such weights in the Tessera cache",
                model_id=model_id,
            )
        if not candidate.exists():
            raise EngineFault(
                "weights_missing",
                f"{model_id}: no such weights in the Tessera cache",
                model_id=model_id,
            )
        return candidate

    # ------------------------------------------------------------------
    # Runtime descriptor
    # ------------------------------------------------------------------

    def write_descriptor(self) -> Path:
        """Publish the descriptor the add-on discovers this engine by.

        Written owner-readable: it carries the token, and a token any local
        process can read is not one (FR-032, SEC-007).

        Returns:
            The path written.
        """
        path = self._descriptor_path
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "pid": os.getpid(),
            "port": self.port,
            "protocol_version": max(PROTOCOL_VERSIONS),
            "engine_version": ENGINE_VERSION,
            "log_path": str(self.log_path),
            "cache_root": str(self.cache_root),
            "token": self.token,
        }
        # Write then chmod-then-rename so the token is never briefly
        # world-readable at its final name.
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(body, handle)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        logger.info("engine runtime descriptor at %s", path)
        return path

    def remove_descriptor(self) -> None:
        """Delete the descriptor on clean shutdown (FR-039).

        A descriptor outliving its process is a claim about something that
        is gone. The add-on confirms with a health check, but leaving one
        behind makes every future start look ambiguous for no reason.
        """
        try:
            self._descriptor_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:  # pragma: no cover — defensive
            logger.warning("could not remove runtime descriptor: %s", exc)
