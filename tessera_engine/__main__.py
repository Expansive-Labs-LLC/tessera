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

"""Engine entry point: ``python -m tessera_engine --cache-root ...``.

The cache root is required and has no default. An engine that guesses
where the weights are is an engine that can be pointed somewhere else,
and the containment check in SEC-003 is only worth anything if the root
it checks against came from the add-on that owns the licence gate
(FR-033, CON-011).

``SIGTERM`` shuts down the same way ``POST /shutdown`` does: stop taking
work, drain what is running, free the GPU, remove the descriptor, exit 0.
The add-on sends one when Blender closes (FR-039).

Spec: SPEC-TS-0023 (FR-030, FR-032, FR-033, FR-039)
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from . import DEFAULT_HOST, DEFAULT_PORT, ENGINE_VERSION
from .inference import reconstruct, vision
from .runtime import EngineRuntime
from .server import EngineServer, build_server

logger = logging.getLogger("tessera_engine")


def _default_log_path() -> Path:
    """Return where the engine logs, beside its runtime descriptor."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "Tessera" / "engine" / "engine.log"
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "tessera" / "engine" / "engine.log"


def _configure_logging(log_path: Path) -> None:
    """Send engine logs to a file the add-on can point a user at (FR-040).

    No image data, no mesh data, weight basenames only — this is the file
    someone pastes into a support thread, so it has to be safe to share
    unedited (SEC-008).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main(argv=None) -> int:
    """Start the engine and serve until told to stop.

    Args:
        argv: Argument list; defaults to ``sys.argv[1:]``.

    Returns:
        Process exit status.
    """
    parser = argparse.ArgumentParser(
        prog="tessera-engine",
        description="Tessera local inference engine (SPEC-TS-0023).",
    )
    parser.add_argument(
        "--cache-root",
        required=True,
        type=Path,
        help="Absolute path to the weight cache the add-on governs. "
        "Every weight path in every request must resolve inside it.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="Loopback address only.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--version", action="version", version=ENGINE_VERSION)
    args = parser.parse_args(argv)

    log_path = args.log_file or _default_log_path()
    _configure_logging(log_path)

    cache_root = args.cache_root.expanduser().resolve()
    if not cache_root.is_dir():
        logger.error("cache root %s is not a directory", cache_root)
        return 2

    runtime = EngineRuntime(cache_root, args.port, log_path)
    engine = EngineServer(runtime, reconstruct, vision)

    try:
        httpd = build_server(engine, args.host, args.port)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    except OSError as exc:
        # EC-003: the port is taken. Name it — the add-on points the user
        # at the port preference from here.
        logger.error("could not bind %s:%s — %s", args.host, args.port, exc)
        return 3

    # The bound port, not the requested one: --port 0 picks a free one and
    # the descriptor must say which.
    runtime.port = httpd.server_address[1]
    runtime.write_descriptor()
    logger.info(
        "engine %s serving on %s:%s (cache root %s)",
        ENGINE_VERSION,
        args.host,
        runtime.port,
        cache_root,
    )

    def _on_signal(signum, _frame):
        logger.info("received signal %s, shutting down", signum)
        engine.shutdown_gracefully(httpd.shutdown)

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        runtime.remove_descriptor()
    logger.info("engine stopped")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
