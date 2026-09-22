# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the local inference engine boundary.

These run against a real ``http.server`` on loopback rather than a mocked
``urllib``. The defects this boundary exists to prevent are transport and
protocol defects, and a mocked transport cannot exhibit them.

Maps to SPEC-TS-0023: AC-002, AC-003, AC-004, AC-006, AC-008,
EC-001, EC-002, EC-003, EC-004, TS-003 – TS-008, TS-012, TS-013.
"""

import json
import socket
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

# ---------------------------------------------------------------------------
# Lazy imports — deferred so conftest's bpy mock is active first. The engine
# package itself imports no bpy, but reaching it imports the tessera package.
# ---------------------------------------------------------------------------


def _eng():
    from tessera.engine import (
        PROTOCOL_VERSIONS,
        EngineRequestError,
        EngineUnavailableError,
        EngineVersionError,
    )
    from tessera.engine.client import EngineClient
    from tessera.engine.status import EngineStatus, resolve_status

    return types.SimpleNamespace(
        PROTOCOL_VERSIONS=PROTOCOL_VERSIONS,
        EngineRequestError=EngineRequestError,
        EngineUnavailableError=EngineUnavailableError,
        EngineVersionError=EngineVersionError,
        EngineClient=EngineClient,
        EngineStatus=EngineStatus,
        resolve_status=resolve_status,
    )


@pytest.fixture
def eng(mock_bpy):
    """Engine package symbols, imported after the bpy mock is installed."""
    return _eng()


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Handler(BaseHTTPRequestHandler):
    """Serves whatever the active test configured."""

    health_body = {"protocol_version": 1, "gpu": "Test GPU", "vram_gb": 8.0}
    error_for = {}

    def log_message(self, *args):  # silence the default stderr logging
        pass

    def _send(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, type(self).health_body)
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        err = type(self).error_for.get(self.path)
        if err:
            self._send(err[0], err[1])
        else:
            self._send(
                200, {"vertices": [[0, 0, 0]], "faces": [[0, 0, 0]], "confidence": 0.9}
            )


@pytest.fixture
def engine(eng):
    """Run a stand-in engine on a free loopback port."""
    port = _free_port()
    _Handler.health_body = {"protocol_version": 1, "gpu": "Test GPU", "vram_gb": 8.0}
    _Handler.error_for = {}
    srv = HTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield eng.EngineClient(host="127.0.0.1", port=port), _Handler, srv
    finally:
        srv.shutdown()
        srv.server_close()


class TestHealthAndAvailability:
    def test_health_returns_payload(self, engine, eng):
        client, _, _ = engine
        health = client.health()
        assert health["protocol_version"] in eng.PROTOCOL_VERSIONS
        assert health["gpu"] == "Test GPU"

    def test_is_available_true_when_running(self, engine, eng):
        client, _, _ = engine
        assert client.is_available() is True

    def test_is_available_false_when_absent_and_never_raises(self, eng):
        """AC-002: engine absent is a state, not an exception."""
        client = eng.EngineClient(host="127.0.0.1", port=_free_port())
        assert client.is_available() is False

    def test_unreachable_raises_unavailable(self, eng):
        client = eng.EngineClient(host="127.0.0.1", port=_free_port())
        with pytest.raises(eng.EngineUnavailableError):
            client.health()


class TestProtocolNegotiation:
    def test_unsupported_version_is_refused(self, engine, eng):
        """AC-003: skew is refused, never guessed at."""
        client, handler, _ = engine
        handler.health_body = {"protocol_version": 99, "gpu": "Test GPU"}
        with pytest.raises(eng.EngineVersionError) as exc:
            client.health()
        assert "99" in str(exc.value)

    def test_mismatch_names_which_side_is_behind(self, engine, eng):
        """EC-004: the user must know what to update."""
        client, handler, _ = engine
        handler.health_body = {"protocol_version": 99}
        with pytest.raises(eng.EngineVersionError) as exc:
            client.health()
        assert "add-on is behind" in str(exc.value)

        handler.health_body = {"protocol_version": 0}
        with pytest.raises(eng.EngineVersionError) as exc:
            client.health()
        assert "engine is behind" in str(exc.value)

    def test_foreign_listener_is_not_sent_data(self, engine, eng):
        """EC-003 / SEC-006: something is listening, but it is not ours."""
        client, handler, _ = engine
        handler.health_body = {"service": "something-else"}
        with pytest.raises(eng.EngineUnavailableError) as exc:
            client.health()
        assert "did not identify itself" in str(exc.value)

    def test_reconstruct_checks_version_before_sending(self, engine, eng):
        """Image data must not reach a skewed engine."""
        client, handler, _ = engine
        handler.health_body = {"protocol_version": 99}
        with pytest.raises(eng.EngineVersionError):
            client.reconstruct({"trellis": "/abs/path"}, [{"image": "x"}])


class TestStructuredErrors:
    def test_insufficient_vram_surfaces_slug(self, engine, eng):
        """AC-006: a documented slug, not a crash."""
        client, handler, _ = engine
        handler.error_for = {
            "/reconstruct": (
                507,
                {
                    "error": "insufficient_vram",
                    "detail": "Required 8.0 GB, available 2.0 GB",
                    "retryable": False,
                },
            )
        }
        with pytest.raises(eng.EngineRequestError) as exc:
            client.reconstruct({"trellis": "/abs"}, [])
        assert exc.value.slug == "insufficient_vram"
        assert exc.value.retryable is False
        assert "2.0 GB" in exc.value.detail

    def test_busy_is_retryable(self, engine, eng):
        """AC-008: a concurrent request is refused cleanly."""
        client, handler, _ = engine
        handler.error_for = {
            "/reconstruct": (
                409,
                {"error": "busy", "detail": "in progress", "retryable": True},
            )
        }
        with pytest.raises(eng.EngineRequestError) as exc:
            client.reconstruct({}, [])
        assert exc.value.slug == "busy"
        assert exc.value.retryable is True

    def test_missing_weights_is_reported_not_fetched(self, engine, eng):
        """AC-004: the engine never acquires weights."""
        client, handler, _ = engine
        handler.error_for = {
            "/reconstruct": (
                400,
                {"error": "weights_missing", "detail": "/abs/nope", "retryable": False},
            )
        }
        with pytest.raises(eng.EngineRequestError) as exc:
            client.reconstruct({"trellis": "/abs/nope"}, [])
        assert exc.value.slug == "weights_missing"


class TestLoopbackOnly:
    @pytest.mark.parametrize("host", ["10.0.0.5", "example.com", "0.0.0.0"])
    def test_non_loopback_host_is_refused(self, eng, host):
        """SEC-001 / TS-013: never send image data off the machine."""
        client = eng.EngineClient(host=host, port=9999)
        with pytest.raises(eng.EngineUnavailableError) as exc:
            client.health()
        assert "loopback" in str(exc.value)


class TestStatusResolution:
    def test_ready_when_engine_healthy(self, engine, eng):
        client, _, _ = engine
        state = eng.resolve_status(client)
        assert state.status is eng.EngineStatus.READY
        assert state.is_ready is True
        assert "Test GPU" in state.message

    def test_not_installed_when_absent_and_unknown(self, eng):
        """AC-002: actionable state with installation guidance."""
        client = eng.EngineClient(host="127.0.0.1", port=_free_port())
        state = eng.resolve_status(client, installed=False)
        assert state.status is eng.EngineStatus.NOT_INSTALLED
        assert state.is_ready is False
        assert "Install" in (state.action or "")

    def test_stopped_is_distinguished_from_not_installed(self, eng):
        """EC-001: do not tell someone to install what they installed."""
        client = eng.EngineClient(host="127.0.0.1", port=_free_port())
        state = eng.resolve_status(client, installed=True)
        assert state.status is eng.EngineStatus.STOPPED
        assert "Start" in (state.action or "")
        assert "Install" not in (state.action or "")

    def test_version_mismatch_state(self, engine, eng):
        client, handler, _ = engine
        handler.health_body = {"protocol_version": 99}
        state = eng.resolve_status(client)
        assert state.status is eng.EngineStatus.VERSION_MISMATCH
        assert state.is_ready is False

    def test_foreign_listener_state_points_at_port(self, engine, eng):
        client, handler, _ = engine
        handler.health_body = {"service": "other"}
        state = eng.resolve_status(client)
        assert state.status is eng.EngineStatus.UNKNOWN_LISTENER
        assert "port" in (state.action or "").lower()

    def test_resolve_status_never_raises(self, eng):
        for installed in (True, False, None):
            state = eng.resolve_status(
                eng.EngineClient(host="127.0.0.1", port=_free_port()),
                installed=installed,
            )
            assert state.status in eng.EngineStatus


class TestEngineDiesMidRequest:
    def test_shutdown_mid_flight_raises_unavailable(self, engine, eng):
        """EC-002: a dead engine must not hang the caller."""
        client, _, srv = engine
        srv.shutdown()
        srv.server_close()
        with pytest.raises(eng.EngineUnavailableError):
            client.reconstruct({}, [])


class TestNoHeavyDependency:
    def test_engine_client_imports_no_ml_stack(self, eng):
        """The add-on half must stay free of the heavy runtime."""
        import pathlib

        src = pathlib.Path(__file__).resolve().parent.parent / "tessera" / "engine"
        for path in src.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for banned in ("import torch", "import safetensors", "import bpy"):
                assert banned not in text, f"{path.name} imports {banned}"
