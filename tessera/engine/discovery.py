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

"""Finding the engine on disk, without probing the port.

Two files carry everything the add-on needs to know about an engine it
did not start:

*Installation marker* — written by the installer, removed by the
uninstaller. Its presence is the definition of *installed*. Probing the
port cannot answer that question: nothing listening means stopped or
absent, and those want opposite advice. Telling someone to install
software they already have is worse than saying nothing
(SPEC-TS-0023 FR-031, EC-001).

*Runtime descriptor* — written at startup, deleted on clean shutdown. It
carries the port, the log path to show when something fails, the cache
root the engine was launched with, and the per-start token every request
must present. Loopback is not a trust boundary on a desktop, so the token
is what separates the add-on from any other local process — including a
page in the user's own browser (SPEC-TS-0023 FR-032, FR-037, SEC-007).

Both files may be absent, stale or unreadable at any moment. Every
function here returns ``None`` rather than raising: a missing engine is a
UI state, not an error.

Spec: SPEC-TS-0023 (FR-031, FR-032, FR-033, FR-037, EC-001)

Public API:
    install_marker_path — where the installer records itself
    runtime_descriptor_path — where a running engine records itself
    read_install_marker — the marker, or None
    read_runtime_descriptor — the descriptor, or None
    is_installed — whether an engine is installed
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tessera.engine")

#: Directory name used under every platform's base directory.
_VENDOR_DIR = Path("tessera") / "engine"

#: Windows uses one directory for both files; POSIX separates durable
#: state from runtime state, so the marker and descriptor differ there.
_INSTALL_MARKER = "install.json"
_RUNTIME_DESCRIPTOR = "runtime.json"


def _windows_base() -> Path:
    """Return ``%LOCALAPPDATA%\\Tessera``, falling back to the profile."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Tessera" / "engine"
    return Path.home() / "AppData" / "Local" / "Tessera" / "engine"


def install_marker_path() -> Path:
    """Return the path the installer writes its marker to (FR-031).

    Returns:
        ``%LOCALAPPDATA%\\Tessera\\engine\\install.json`` on Windows,
        ``${XDG_DATA_HOME:-~/.local/share}/tessera/engine/install.json``
        elsewhere.
    """
    if sys.platform == "win32":
        return _windows_base() / _INSTALL_MARKER
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / _VENDOR_DIR / _INSTALL_MARKER


def runtime_descriptor_path() -> Path:
    """Return the path a running engine writes its descriptor to (FR-032).

    Returns:
        ``%LOCALAPPDATA%\\Tessera\\engine\\runtime.json`` on Windows;
        otherwise ``$XDG_RUNTIME_DIR``, then ``$XDG_STATE_HOME``, then
        ``~/.local/state``, under ``tessera/engine/runtime.json``.
    """
    if sys.platform == "win32":
        return _windows_base() / _RUNTIME_DESCRIPTOR
    base = (
        os.environ.get("XDG_RUNTIME_DIR")
        or os.environ.get("XDG_STATE_HOME")
        or str(Path.home() / ".local" / "state")
    )
    return Path(base) / _VENDOR_DIR / _RUNTIME_DESCRIPTOR


def _read_json(path: Path, what: str) -> Optional[dict]:
    """Read one JSON object, returning None for every failure mode.

    A truncated descriptor is the normal result of reading while the
    engine is still writing it, and an unreadable marker is the normal
    result of a half-removed install. Neither is worth an exception on a
    status poll that runs on every panel redraw.

    Args:
        path: File to read.
        what: Noun used in the debug log.

    Returns:
        The decoded object, or ``None`` if it is absent, unreadable, or
        not a JSON object.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            body = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("engine %s at %s unreadable: %s", what, path, exc)
        return None
    if not isinstance(body, dict):
        logger.debug("engine %s at %s is not a JSON object", what, path)
        return None
    return body


def read_install_marker() -> Optional[dict]:
    """Return the installation marker, or ``None`` if not installed.

    Returns:
        ``{"engine_version", "protocol_versions", "executable"}`` as the
        installer wrote it, or ``None``.
    """
    return _read_json(install_marker_path(), "installation marker")


def read_runtime_descriptor() -> Optional[dict]:
    """Return the runtime descriptor, or ``None`` if no engine is running.

    A descriptor left behind by a crashed engine will still be returned —
    it is a claim about a process, not proof of one. Callers confirm with
    a health check; the port is the authority on whether it is alive.

    Returns:
        ``{"pid", "port", "protocol_version", "engine_version",
        "log_path", "cache_root", "token"}``, or ``None``.
    """
    return _read_json(runtime_descriptor_path(), "runtime descriptor")


def is_installed() -> bool:
    """Return whether an engine installation exists (FR-031, EC-001).

    Answers from the marker alone. Whether the engine is *running* is a
    separate question, and conflating them is what produces advice to
    install something already installed.
    """
    return read_install_marker() is not None
