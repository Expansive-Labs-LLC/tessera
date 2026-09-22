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

"""Starting, supervising and stopping the engine.

The add-on spawns the engine rather than asking the user to run a service
(SPEC-TS-0023 FR-018). For an audience of artists that is the difference
between an add-on that works and one that needs a terminal open beside it.
An engine already answering on the port is attached to instead, so someone
debugging with a hand-started engine keeps that engine.

**Startup failure reports the engine's own stderr, not a timeout.** "The
engine did not start" tells a user nothing they can act on; the first
lines of a CUDA driver error tell them everything. Capped at
:data:`_STDERR_LINES`, because a Blender report dialog truncates badly and
the log path is there for the rest (FR-040).

**The cache root is a launch argument.** The engine is never told where
weights live by a request, because a containment check against a root the
caller supplied is not a check (FR-033, CON-011).

Spec: SPEC-TS-0023 (FR-018, FR-033, FR-039, FR-040, EC-003)

Public API:
    EngineLaunchError — the engine was asked to start and did not
    spawn_engine — start a locally installed engine
    stop_engine — stop one this add-on started
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

from . import DEFAULT_HOST, DEFAULT_PORT, EngineError
from .client import EngineClient
from .discovery import read_install_marker, read_runtime_descriptor

logger = logging.getLogger("tessera.engine")

#: How long the engine has to answer /health after being spawned (FR-040).
#: NFR-005 budgets 30 s for a cold start; this is the point at which we
#: stop believing it is merely slow.
_START_TIMEOUT_S = 60.0

#: Poll interval while waiting for the engine to come up.
_POLL_INTERVAL_S = 0.25

#: Lines of the engine's stderr carried into the failure report. Enough to
#: contain a driver or import error; short enough to read in a dialog.
_STDERR_LINES = 40


class EngineLaunchError(EngineError):
    """The engine was asked to start and did not become ready.

    Attributes:
        stderr_head: First lines of the engine's standard error.
        log_path: Where the engine's own log is, if it got far enough to
            say.
    """

    def __init__(self, message: str, stderr_head: str = "", log_path: str = ""):
        detail = message
        if stderr_head:
            detail += f"\n\nEngine output:\n{stderr_head}"
        if log_path:
            detail += f"\n\nFull log: {log_path}"
        super().__init__(detail)
        self.stderr_head = stderr_head
        self.log_path = log_path


def _head(stream, limit: int = _STDERR_LINES) -> str:
    """Return the first ``limit`` lines of a captured stream."""
    if not stream:
        return ""
    text = stream if isinstance(stream, str) else stream.decode("utf-8", "replace")
    lines = text.splitlines()
    head = "\n".join(lines[:limit])
    if len(lines) > limit:
        head += f"\n… {len(lines) - limit} more lines in the engine log"
    return head


def spawn_engine(
    cache_root: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout_s: float = _START_TIMEOUT_S,
) -> Optional[subprocess.Popen]:
    """Start the installed engine, or attach to one already running.

    Args:
        cache_root: The weight cache this add-on governs. Passed as a
            launch argument and fixed for the engine's lifetime.
        host: Loopback address to serve on.
        port: Port to serve on.
        timeout_s: How long to wait for ``/health`` to answer.

    Returns:
        The spawned process, or ``None`` when an engine was already
        running and has been attached to instead.

    Raises:
        EngineLaunchError: No installation, or the engine did not become
            ready inside ``timeout_s``.
    """
    client = EngineClient(host=host, port=port)
    if client.is_available():
        logger.info("attaching to the engine already serving on %s:%s", host, port)
        return None

    marker = read_install_marker()
    if marker is None:
        raise EngineLaunchError(
            "The Tessera engine is not installed. Generation needs it to "
            "run the AI models; the add-on alone cannot."
        )
    executable = marker.get("executable")
    if not executable or not Path(executable).exists():
        raise EngineLaunchError(
            "The Tessera engine installation is incomplete — its "
            f"executable is not where the installer recorded it "
            f"({executable!r}). Reinstall the engine."
        )

    command = [
        str(executable),
        "--cache-root",
        str(Path(cache_root).expanduser().resolve()),
        "--host",
        host,
        "--port",
        str(port),
    ]
    logger.info("starting the Tessera engine on %s:%s", host, port)
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # Detached enough that closing Blender does not SIGKILL an
            # engine mid-request; stop_engine ends it deliberately.
            start_new_session=True,
        )
    except OSError as exc:
        raise EngineLaunchError(f"Could not start the Tessera engine: {exc}") from exc

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            # It exited on its own — the reason is in what it printed.
            _, stderr = process.communicate(timeout=5)
            raise EngineLaunchError(
                f"The Tessera engine exited immediately (status "
                f"{process.returncode}).",
                stderr_head=_head(stderr),
                log_path=(read_runtime_descriptor() or {}).get("log_path", ""),
            )
        if client.is_available():
            logger.info("engine ready on %s:%s", host, port)
            return process
        time.sleep(_POLL_INTERVAL_S)

    # Alive but never answered. Stop what we started rather than leaving a
    # process holding the port for the next attempt (EC-003).
    stderr = _terminate(process)
    raise EngineLaunchError(
        f"The Tessera engine did not become ready within {timeout_s:.0f} " "seconds.",
        stderr_head=_head(stderr),
        log_path=(read_runtime_descriptor() or {}).get("log_path", ""),
    )


def _terminate(process: subprocess.Popen, grace_s: float = 5.0) -> str:
    """Terminate a process, returning whatever it printed."""
    process.terminate()
    try:
        _, stderr = process.communicate(timeout=grace_s)
        return stderr or ""
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            _, stderr = process.communicate(timeout=grace_s)
            return stderr or ""
        except Exception:  # pragma: no cover — defensive
            return ""


def stop_engine(
    process: Optional[subprocess.Popen] = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    grace_s: float = 35.0,
) -> bool:
    """Stop the engine cleanly, escalating only if it will not go (FR-039).

    Asks over HTTP first so the engine can finish or cancel what it is
    doing, free GPU memory and remove its descriptor. Only an engine that
    ignores that is signalled.

    Args:
        process: The process this add-on spawned, if any. ``None`` when we
            attached to an engine someone else started — which is then
            asked to stop but never signalled, because it is not ours.
        host: Engine host.
        port: Engine port.
        grace_s: How long to wait for a clean exit. Slightly longer than
            the engine's own 30 s drain, so the polite path wins the race.

    Returns:
        Whether the engine stopped.
    """
    client = EngineClient(host=host, port=port)
    asked = client.shutdown()

    if process is None:
        # Not ours to kill. Report whether it took the request.
        return asked

    deadline = time.monotonic() + grace_s
    while time.monotonic() < deadline:
        if process.poll() is not None:
            logger.info("engine stopped cleanly")
            return True
        time.sleep(_POLL_INTERVAL_S)

    logger.warning("engine did not stop when asked; terminating it")
    _terminate(process)
    return process.poll() is not None
