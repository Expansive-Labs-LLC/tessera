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

Spec: SPEC-TS-0023 (FR-010, FR-011, FR-017, FR-022, SEC-006)

Public API:
    EngineClient — discovery, health, and the inference endpoints
"""

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from . import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    PROTOCOL_VERSIONS,
    EngineError,
    EngineRequestError,
    EngineUnavailableError,
    EngineVersionError,
)

logger = logging.getLogger("tessera.engine")

#: Health checks must fail fast so the UI can report "not installed"
#: without stalling a redraw (SPEC-TS-0023 NFR-002: < 500 ms).
_HEALTH_TIMEOUT_S = 0.4

#: Inference is measured in seconds to minutes; this bounds a hung engine
#: rather than a slow one.
_INFERENCE_TIMEOUT_S = 600.0


class EngineClient:
    """Talks to the local inference engine over loopback HTTP.

    Args:
        host: Engine host. Loopback only — see :meth:`_url`.
        port: Engine port.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self._host = host or DEFAULT_HOST
        self._port = int(port or DEFAULT_PORT)

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
        self, path: str, payload: Optional[dict] = None, timeout: float = 10.0
    ) -> dict:
        """Perform one request and decode the response.

        Args:
            path: Endpoint path.
            payload: JSON body; ``None`` issues a GET.
            timeout: Socket timeout in seconds.

        Returns:
            The decoded JSON response.

        Raises:
            EngineUnavailableError: Engine unreachable, or died mid-request.
            EngineRequestError: Engine returned a structured error.
        """
        url = self._url(path)
        data = None
        headers = {"Accept": "application/json"}
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
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
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

    def reconstruct(self, weight_paths: dict, inputs: list) -> dict:
        """Run reconstruction in the engine.

        Args:
            weight_paths: Absolute paths to weights the add-on has already
                resolved, verified and licence-checked (FR-009).
            inputs: Per-view payloads.

        Returns:
            ``{"vertices", "faces", "vertex_colors", "confidence"}``.

        Raises:
            EngineUnavailableError, EngineVersionError, EngineRequestError.
        """
        self.health()  # fail fast on skew before sending image data
        return self._request(
            "/reconstruct",
            {"weight_paths": weight_paths, "inputs": inputs},
            timeout=_INFERENCE_TIMEOUT_S,
        )

    def vision(self, stage: str, weight_paths: dict, image: Any) -> dict:
        """Run one vision stage in the engine.

        Args:
            stage: ``"segment"``, ``"depth"`` or ``"features"``.
            weight_paths: Verified absolute paths (FR-009).
            image: Encoded image payload.

        Returns:
            The stage result.

        Raises:
            EngineUnavailableError, EngineVersionError, EngineRequestError.
        """
        self.health()
        return self._request(
            "/vision",
            {"stage": stage, "weight_paths": weight_paths, "image": image},
            timeout=_INFERENCE_TIMEOUT_S,
        )
