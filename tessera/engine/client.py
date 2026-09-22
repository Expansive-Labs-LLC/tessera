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

"""HTTP client for the local inference engine.

Uses only the standard library: the add-on must not gain a dependency to
talk to the engine, since keeping the archive small is the reason the
engine exists at all (ADR-0001 D3).

Every call is blocking and runs on the background threads pipeline work
already uses. ``bpy`` is never touched from here (SPEC-TS-0023 CON-003);
results reach the UI through the existing timer queue.

Spec: SPEC-TS-0023 (FR-010, FR-011, FR-017, FR-022, FR-035, FR-036,
FR-037, SEC-006, SEC-007)

Public API:
    EngineClient — discovery, health, and the inference endpoints
"""

import json
import logging
import socket
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Optional

from . import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    PROTOCOL_HEADER,
    PROTOCOL_VERSIONS,
    REQUEST_ID_HEADER,
    TOKEN_HEADER,
    EngineError,
    EngineRequestError,
    EngineTimeoutError,
    EngineUnavailableError,
    EngineVersionError,
)
from .discovery import read_runtime_descriptor

logger = logging.getLogger("tessera.engine")

#: Per-endpoint socket timeouts (SPEC-TS-0023 FR-035). These bound a
#: *wedged* engine, not an absent one: nothing listening is refused by the
#: kernel immediately, which is what keeps NFR-002's 500 ms detection
#: budget independent of these values.
_HEALTH_TIMEOUT_S = 5.0
_VISION_TIMEOUT_S = 300.0
_RECONSTRUCT_TIMEOUT_S = 900.0

#: Cancelling is best-effort cleanup on a path that has already failed, so
#: it gets a short bound of its own rather than inheriting the caller's.
_CANCEL_TIMEOUT_S = 5.0


class EngineClient:
    """Talks to the local inference engine over loopback HTTP.

    Args:
        host: Engine host. Loopback only — see :meth:`_url`.
        port: Engine port.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self._host = host or DEFAULT_HOST
        self._port = int(port or DEFAULT_PORT)

    def _token(self) -> Optional[str]:
        """Return the running engine's per-start token, if one is on disk.

        Absent when no engine is running, which is not an error here — the
        request will fail on the transport instead, with a message about
        reaching the engine rather than about authentication.
        """
        descriptor = read_runtime_descriptor() or {}
        token = descriptor.get("token")
        return token if isinstance(token, str) and token else None

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        """Build an endpoint URL, refusing any non-loopback host.

        The engine is a local process by design (SPEC-TS-0023 SEC-001). A
        misconfigured host preference must not turn image data into a
        network transmission, so this refuses rather than trusting the
        value.

        Args:
            path: Endpoint path beginning with ``/``.

        Returns:
            The absolute URL.

        Raises:
            EngineUnavailableError: If the configured host is not loopback.
        """
        if self._host not in ("127.0.0.1", "localhost", "::1"):
            raise EngineUnavailableError(
                f"Engine host {self._host!r} is not a loopback address. "
                "Tessera only talks to an engine on this machine."
            )
        return f"http://{self._host}:{self._port}{path}"

    def _request(
        self,
        path: str,
        payload: Optional[dict] = None,
        timeout: float = _HEALTH_TIMEOUT_S,
        request_id: Optional[str] = None,
    ) -> dict:
        """Perform one request and decode the response.

        Args:
            path: Endpoint path.
            payload: JSON body; ``None`` issues a GET.
            timeout: Socket timeout in seconds (FR-035). Never unbounded —
                a wedged engine must not hold a worker thread forever.
            request_id: Identifier to send; generated when omitted.

        Returns:
            The decoded JSON response.

        Raises:
            EngineUnavailableError: Engine unreachable, or died mid-request.
            EngineTimeoutError: Engine alive but not answering.
            EngineRequestError: Engine returned a structured error.
        """
        url = self._url(path)
        data = None
        headers = {
            "Accept": "application/json",
            REQUEST_ID_HEADER: request_id or uuid.uuid4().hex,
            PROTOCOL_HEADER: str(max(PROTOCOL_VERSIONS)),
        }
        token = self._token()
        if token:
            headers[TOKEN_HEADER] = token
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers)
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # A structured engine error, not a transport failure.
            raise self._decode_error(exc) from exc
        except (socket.timeout, TimeoutError) as exc:
            # EC-006: alive but wedged. Distinct from a dead engine, and
            # distinct in what it asks the user to do.
            raise EngineTimeoutError(path, time.monotonic() - started) from exc
        except (urllib.error.URLError, OSError) as exc:
            # A timeout can arrive wrapped in URLError depending on where
            # in the exchange it happened; classify on the cause, not on
            # which layer surfaced it.
            if isinstance(getattr(exc, "reason", None), (socket.timeout, TimeoutError)):
                raise EngineTimeoutError(path, time.monotonic() - started) from exc
            # EC-002: a request in flight when the engine dies lands here
            # rather than hanging.
            raise EngineUnavailableError(
                f"Could not reach the Tessera engine at {self._host}:"
                f"{self._port} ({exc}). Check that it is installed and "
                "running."
            ) from exc
        except json.JSONDecodeError as exc:
            raise EngineUnavailableError(
                f"Engine at {self._host}:{self._port} returned a response "
                "that is not valid JSON. Another process may be using this "
                "port."
            ) from exc

        logger.debug(
            "engine %s ok in %.0f ms", path, (time.monotonic() - started) * 1000
        )
        return body

    @staticmethod
    def _decode_error(exc: urllib.error.HTTPError) -> EngineError:
        """Turn an HTTP error response into an EngineRequestError."""
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {}
        slug = body.get("error") or f"http_{exc.code}"
        return EngineRequestError(
            slug=slug,
            detail=body.get("detail", ""),
            retryable=bool(body.get("retryable", False)),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def health(self) -> dict:
        """Return the engine's health payload.

        Returns:
            The engine's health dict, including ``protocol_version``.

        Raises:
            EngineUnavailableError: Engine unreachable.
            EngineVersionError: Engine speaks an unsupported protocol.
        """
        body = self._request("/health", timeout=_HEALTH_TIMEOUT_S)

        version = body.get("protocol_version")
        if version is None:
            # SEC-006: something is listening, but it did not identify as a
            # Tessera engine. Do not send it image data (EC-003).
            raise EngineUnavailableError(
                f"The process on {self._host}:{self._port} did not identify "
                "itself as a Tessera engine. Check the engine port in "
                "add-on preferences."
            )
        if version not in PROTOCOL_VERSIONS:
            supported = ", ".join(str(v) for v in sorted(PROTOCOL_VERSIONS))
            behind = "add-on" if version > max(PROTOCOL_VERSIONS) else "engine"
            raise EngineVersionError(
                f"Engine speaks protocol {version}; this add-on supports "
                f"{supported}. The {behind} is behind — update it to "
                "continue."
            )
        return body

    def is_available(self) -> bool:
        """Return whether a compatible engine is reachable right now.

        Never raises: this is called from status polling where an
        exception would be noise rather than information.
        """
        try:
            self.health()
        except EngineError:
            return False
        except Exception:  # pragma: no cover — defensive
            logger.exception("Unexpected failure during engine health check")
            return False
        return True

    def _inference(self, path: str, payload: dict, timeout: float) -> dict:
        """Run one inference request, cancelling it if it wedges.

        A timed-out request is still holding the engine's single inference
        lock (FR-021). Walking away without cancelling would make the next
        request wait behind one nobody is listening for, so the cancel is
        part of giving up, not an optional courtesy (FR-035).

        Args:
            path: Endpoint path.
            payload: JSON body, without the identity fields — those travel
                as headers on every request (FR-036).
            timeout: Socket timeout in seconds.

        Returns:
            The decoded response.

        Raises:
            EngineTimeoutError: After the cancel has been issued.
        """
        self.health()  # fail fast on skew before sending image data
        request_id = uuid.uuid4().hex
        try:
            return self._request(path, payload, timeout, request_id=request_id)
        except EngineTimeoutError:
            self.cancel(request_id)
            raise

    def reconstruct(self, weight_paths: dict, inputs: list) -> dict:
        """Run reconstruction in the engine.

        Args:
            weight_paths: Absolute paths to weights the add-on has already
                resolved, verified and licence-checked (FR-009).
            inputs: Per-view payloads, each the full wire projection of a
                ``VisionPipelineOutput`` (FR-025).

        Returns:
            The fields ``StandardMesh`` and ``ReconstructionResult`` need
            (FR-026).

        Raises:
            EngineUnavailableError, EngineVersionError, EngineTimeoutError,
            EngineRequestError.
        """
        return self._inference(
            "/reconstruct",
            {"weight_paths": weight_paths, "inputs": inputs},
            _RECONSTRUCT_TIMEOUT_S,
        )

    def vision(self, stage: str, weight_paths: dict, image: Any) -> dict:
        """Run one vision stage in the engine.

        Args:
            stage: ``"segment"``, ``"depth"`` or ``"features"``.
            weight_paths: Verified absolute paths (FR-009).
            image: Encoded image payload.

        Returns:
            The per-stage result of FR-029.

        Raises:
            EngineUnavailableError, EngineVersionError, EngineTimeoutError,
            EngineRequestError.
        """
        return self._inference(
            "/vision",
            {"stage": stage, "weight_paths": weight_paths, "image": image},
            _VISION_TIMEOUT_S,
        )

    def cancel(self, request_id: str) -> bool:
        """Ask the engine to abandon one in-flight request (FR-036).

        Never raises. This runs on a path that has already failed, and a
        cancel that cannot be delivered must not replace the original
        failure with a less useful one.

        Args:
            request_id: The request to abandon.

        Returns:
            Whether the engine reported cancelling it. ``False`` also
            covers "could not ask", which is indistinguishable from here
            and calls for the same thing: report the original failure.
        """
        try:
            body = self._request(
                "/cancel", {"request_id": request_id}, _CANCEL_TIMEOUT_S
            )
        except EngineError as exc:
            logger.debug("engine cancel for %s failed: %s", request_id, exc)
            return False
        except Exception:  # pragma: no cover — defensive
            logger.exception("Unexpected failure cancelling %s", request_id)
            return False
        return bool(body.get("cancelled", False))

    def shutdown(self) -> bool:
        """Ask the engine to stop cleanly (FR-039).

        Called when Blender exits, for an engine this add-on spawned. Never
        raises: an engine that is already gone is the outcome wanted, and
        one that refuses to stop is not something a closing application can
        do anything about.

        Returns:
            Whether the engine acknowledged the request.
        """
        try:
            self._request("/shutdown", {}, _CANCEL_TIMEOUT_S)
        except EngineError as exc:
            logger.debug("engine shutdown request failed: %s", exc)
            return False
        except Exception:  # pragma: no cover — defensive
            logger.exception("Unexpected failure shutting the engine down")
            return False
        return True
