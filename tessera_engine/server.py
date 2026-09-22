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

"""The engine's loopback HTTP server.

Threaded on purpose. Inference is serialised behind one lock because two
reconstructions on one GPU is how you get an out-of-memory failure instead
of two results (FR-021) — but ``/health`` and ``/cancel`` are *not* behind
that lock. A single-threaded server would make a health check wait out a
forty-second reconstruction, and the add-on polls health to decide whether
the engine is alive at all. The status would go stale exactly when it
matters most (FR-034, NFR-011).

Binding is loopback-only and not configurable to anything else. The
add-on refuses a non-loopback host too; enforcing it on both sides means
neither a misconfigured preference nor a modified client turns local
inference into a network transmission (SEC-001, CON-004).

Spec: SPEC-TS-0023 (FR-003 – FR-008, FR-021, FR-034, FR-036 – FR-039,
SEC-001, SEC-003, SEC-007)

Public API:
    EngineServer — the running engine
    build_server — construct one bound to a port
"""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, ClassVar, Optional

from . import (
    DEFAULT_HOST,
    ENGINE_VERSION,
    MAX_REQUEST_BYTES,
    PROTOCOL_HEADER,
    PROTOCOL_VERSIONS,
    REQUEST_ID_HEADER,
    TOKEN_HEADER,
)
from .errors import EngineFault
from .runtime import EngineRuntime, probe_device

logger = logging.getLogger("tessera_engine")

#: Loopback addresses the server will bind. Anything else is refused at
#: construction rather than at request time (CON-004).
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})

#: How long a cancelled or shutting-down request is given to notice.
_DRAIN_TIMEOUT_S = 30.0


class _Inference:
    """The one inference slot, and whoever currently holds it.

    Separate from the server so the cancellation state has one owner. The
    defect this prevents: a cancel arriving for a request that already
    finished, and silently cancelling the *next* one.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: Optional[str] = None
        self._cancelled: Optional[str] = None

    def acquire(self, request_id: str) -> bool:
        """Take the slot for ``request_id``, or report it is taken."""
        if not self._lock.acquire(blocking=False):
            return False
        self._current = request_id
        self._cancelled = None
        return True

    def release(self) -> None:
        """Give the slot back."""
        self._current = None
        self._cancelled = None
        try:
            self._lock.release()
        except RuntimeError:  # pragma: no cover — defensive
            pass

    def cancel(self, request_id: str) -> bool:
        """Mark ``request_id`` cancelled if it is the one in flight."""
        if request_id and request_id == self._current:
            self._cancelled = request_id
            return True
        return False

    def is_cancelled(self, request_id: str) -> bool:
        """Whether ``request_id`` has been asked to stop."""
        return self._cancelled is not None and self._cancelled == request_id

    @property
    def busy(self) -> bool:
        """Whether an inference is in flight."""
        return self._current is not None


class EngineServer:
    """Holds everything a request handler needs.

    Args:
        runtime: Process-lifetime state.
        reconstruct: Callable run for ``POST /reconstruct``.
        vision: Callable run for ``POST /vision``.
    """

    def __init__(
        self,
        runtime: EngineRuntime,
        reconstruct: Callable[..., dict],
        vision: Callable[..., dict],
    ):
        self.runtime = runtime
        self.reconstruct = reconstruct
        self.vision = vision
        self.inference = _Inference()
        self.stopping = threading.Event()

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    def health(self) -> dict:
        """Return the health payload (FR-004).

        Answers while an inference is running, which is the whole reason
        the server is threaded.
        """
        device = probe_device()
        return {
            "protocol_version": max(PROTOCOL_VERSIONS),
            "protocol_versions": sorted(PROTOCOL_VERSIONS),
            "engine_version": ENGINE_VERSION,
            "cuda": device.available,
            "gpu": device.name,
            "vram_gb": device.total_vram_gb,
            "busy": self.inference.busy,
            "log_path": str(self.runtime.log_path),
            "cache_root": str(self.runtime.cache_root),
        }

    def run_inference(self, kind: str, payload: dict, request_id: str) -> dict:
        """Run one inference, holding the single slot for its duration.

        Args:
            kind: ``"reconstruct"`` or ``"vision"``.
            payload: The decoded request body.
            request_id: Identity of this request.

        Returns:
            The response body.

        Raises:
            EngineFault: ``busy`` when another inference holds the slot,
                ``cancelled`` when this one was abandoned.
        """
        if self.stopping.is_set():
            raise EngineFault("busy", "The engine is shutting down.")
        if not self.inference.acquire(request_id):
            raise EngineFault("busy", "The engine is already running an inference.")
        started = time.monotonic()
        try:
            handler = self.reconstruct if kind == "reconstruct" else self.vision
            body = handler(self.runtime, payload, request_id)
            if self.inference.is_cancelled(request_id):
                # It finished, but nobody is waiting for it. Report the
                # cancellation rather than a result the caller discarded.
                raise EngineFault("cancelled", "Request was cancelled.")
            body["duration_s"] = round(time.monotonic() - started, 3)
            return body
        finally:
            # FR-020: free GPU memory whether this succeeded or failed.
            _free_gpu_memory()
            self.inference.release()

    def shutdown_gracefully(self, stop: Callable[[], None]) -> None:
        """Stop accepting inference, drain, then stop the server (FR-039).

        Args:
            stop: Callable that stops the HTTP server loop.
        """
        self.stopping.set()
        deadline = time.monotonic() + _DRAIN_TIMEOUT_S
        while self.inference.busy and time.monotonic() < deadline:
            time.sleep(0.05)
        _free_gpu_memory()
        self.runtime.remove_descriptor()
        threading.Thread(target=stop, daemon=True).start()


def _free_gpu_memory() -> None:
    """Release cached GPU memory (FR-020, NFR-007).

    Called after every request, successful or not. A failed inference is
    the case that leaks: the tensors are still referenced by a traceback
    until the frame goes away, and the caching allocator holds the blocks
    until it is told not to.
    """
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():  # pragma: no cover — needs a GPU
        torch.cuda.empty_cache()


class _Handler(BaseHTTPRequestHandler):
    """Routes one request, having first established it is allowed to."""

    server_version = f"TesseraEngine/{ENGINE_VERSION}"
    #: Bound by :func:`build_server` on a per-server subclass, so two
    #: engines in one process (tests do this) never share a handler.
    engine: ClassVar[Optional[EngineServer]] = None

    @property
    def bound(self) -> EngineServer:
        """Return the engine this handler subclass was bound to.

        :func:`build_server` always binds one. Failing loudly here beats
        an attribute error three frames deeper if that ever stops being
        true.
        """
        engine = type(self).engine
        if engine is None:  # pragma: no cover — build_server always binds
            raise RuntimeError("handler was not bound to an engine")
        return engine

    def log_message(self, fmt, *args):
        logger.debug("%s - %s", self.address_string(), fmt % args)

    # -- plumbing ------------------------------------------------------

    def _send(self, code: int, body: dict, extra_headers: Optional[dict] = None):
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def _fail(self, fault: EngineFault, request_id: str = ""):
        headers = {"Retry-After": "5"} if fault.slug == "busy" else None
        self._send(fault.status, fault.body(request_id), headers)

    def _authenticate(self) -> str:
        """Confirm the caller is the add-on, and return the request id.

        Three checks, each closing a different door (FR-037, SEC-007):

        * the token proves the caller can read the runtime descriptor,
          which no other local process has reason to be able to do;
        * ``Origin`` present at all means a browser sent this, and no
          browser has business here — this is what defeats DNS rebinding,
          where the hostname looks right but the page is not ours;
        * ``Host`` must name what we bound, so a rebound name is refused
          even when the request reaches us.

        Raises:
            EngineFault: ``unauthorized``, carrying nothing from the body.
        """
        engine = self.bound
        if self.headers.get("Origin") is not None:
            raise EngineFault("unauthorized", "Cross-origin requests are refused.")

        host = (self.headers.get("Host") or "").strip()
        expected = {
            f"{name}:{engine.runtime.port}" for name in ("127.0.0.1", "localhost")
        } | {f"[::1]:{engine.runtime.port}"}
        if host not in expected:
            raise EngineFault("unauthorized", "Unexpected Host header.")

        presented = self.headers.get(TOKEN_HEADER) or ""
        # compare_digest: the comparison itself must not leak the token
        # one byte at a time to a local process that can time it.
        import hmac

        if not hmac.compare_digest(presented, engine.runtime.token):
            raise EngineFault("unauthorized", "Missing or incorrect engine token.")

        version = self.headers.get(PROTOCOL_HEADER) or ""
        try:
            spoken = int(version)
        except (TypeError, ValueError):
            raise EngineFault(
                "protocol_mismatch",
                "Request did not state a protocol version.",
                engine_protocol=max(PROTOCOL_VERSIONS),
                requested=version,
            ) from None
        if spoken not in PROTOCOL_VERSIONS:
            raise EngineFault(
                "protocol_mismatch",
                f"This engine speaks protocol {max(PROTOCOL_VERSIONS)}.",
                engine_protocol=max(PROTOCOL_VERSIONS),
                requested=spoken,
            )
        return self.headers.get(REQUEST_ID_HEADER) or ""

    def _read_body(self) -> dict:
        """Read and decode the JSON body, refusing an oversized one.

        The size is decided from ``Content-Length`` before anything is
        read, so a hostile body cannot be absorbed into memory first and
        rejected second (FR-038).
        """
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            raise EngineFault("bad_request", "Content-Length is not a number") from None
        if length > MAX_REQUEST_BYTES:
            raise EngineFault(
                "payload_too_large",
                f"Request body exceeds {MAX_REQUEST_BYTES} bytes.",
                limit_bytes=MAX_REQUEST_BYTES,
            )
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EngineFault("bad_request", "Body is not valid JSON") from exc

    # -- routes --------------------------------------------------------

    def do_GET(self):
        engine = self.bound
        request_id = ""
        try:
            request_id = self._authenticate()
            if self.path == "/health":
                self._send(200, engine.health())
            else:
                self._fail(
                    EngineFault("bad_request", f"No route {self.path}"), request_id
                )
        except EngineFault as fault:
            self._fail(fault, request_id)
        except Exception:  # pragma: no cover — defensive
            logger.exception("unhandled error on GET %s", self.path)
            self._fail(EngineFault("internal", "Unhandled engine error."), request_id)

    def do_POST(self):
        engine = self.bound
        request_id = ""
        try:
            request_id = self._authenticate()
            payload = self._read_body()

            if self.path == "/cancel":
                target = payload.get("request_id") or ""
                self._send(200, {"cancelled": engine.inference.cancel(target)})
                return
            if self.path == "/shutdown":
                self._send(202, {"stopping": True})
                engine.shutdown_gracefully(self.server.shutdown)
                return
            if self.path == "/reconstruct":
                self._send(
                    200, engine.run_inference("reconstruct", payload, request_id)
                )
                return
            if self.path == "/vision":
                self._send(200, engine.run_inference("vision", payload, request_id))
                return
            self._fail(EngineFault("bad_request", f"No route {self.path}"), request_id)
        except EngineFault as fault:
            self._fail(fault, request_id)
        except Exception:  # pragma: no cover — defensive
            logger.exception("unhandled error on POST %s", self.path)
            self._fail(EngineFault("internal", "Unhandled engine error."), request_id)


def build_server(
    engine: EngineServer, host: str = DEFAULT_HOST, port: int = 0
) -> ThreadingHTTPServer:
    """Bind a threaded HTTP server for ``engine``.

    Args:
        engine: The engine to serve.
        host: Must be a loopback address (CON-004).
        port: Port to bind; 0 picks a free one.

    Returns:
        The bound server, not yet serving.

    Raises:
        ValueError: If ``host`` is not loopback. Refused here rather than
            per request, so a misconfigured engine never starts listening
            where it should not.
    """
    if host not in _LOOPBACK:
        raise ValueError(
            f"Refusing to bind {host!r}: the Tessera engine is loopback-only."
        )
    handler = type("_BoundHandler", (_Handler,), {"engine": engine})
    return ThreadingHTTPServer((host, port), handler)
