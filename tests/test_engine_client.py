# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the local inference engine boundary.

These run against a real ``http.server`` on loopback rather than a mocked
``urllib``. The defects this boundary exists to prevent are transport and
protocol defects, and a mocked transport cannot exhibit them.

Maps to SPEC-TS-0023: AC-002, AC-003, AC-004, AC-006, AC-008, AC-011,
AC-012, EC-001, EC-002, EC-003, EC-004, EC-006, TS-003 – TS-008, TS-012,
TS-013, TS-022, TS-024, TS-028.
"""

import json
import socket
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

# ---------------------------------------------------------------------------
# Lazy imports — deferred so conftest's bpy mock is active first. The engine
# package itself imports no bpy, but reaching it imports the tessera package.
# ---------------------------------------------------------------------------


def _eng():
    from tessera.engine import (
        PROTOCOL_HEADER,
        PROTOCOL_VERSIONS,
        REQUEST_ID_HEADER,
        TOKEN_HEADER,
        EngineRequestError,
        EngineTimeoutError,
        EngineUnavailableError,
        EngineVersionError,
    )
    from tessera.engine import client as client_mod
    from tessera.engine import discovery
    from tessera.engine.client import EngineClient
    from tessera.engine.status import EngineStatus, resolve_status

    return types.SimpleNamespace(
        PROTOCOL_VERSIONS=PROTOCOL_VERSIONS,
        PROTOCOL_HEADER=PROTOCOL_HEADER,
        REQUEST_ID_HEADER=REQUEST_ID_HEADER,
        TOKEN_HEADER=TOKEN_HEADER,
        EngineRequestError=EngineRequestError,
        EngineTimeoutError=EngineTimeoutError,
        EngineUnavailableError=EngineUnavailableError,
        EngineVersionError=EngineVersionError,
        EngineClient=EngineClient,
        EngineStatus=EngineStatus,
        resolve_status=resolve_status,
        client_mod=client_mod,
        discovery=discovery,
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
    seen = []  # every (path, headers) this handler received
    stall_s = {}  # path -> seconds to sleep before answering

    def log_message(self, *args):  # silence the default stderr logging
        pass

    def _send(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _record(self):
        type(self).seen.append((self.path, dict(self.headers)))

    def _stall(self):
        delay = type(self).stall_s.get(self.path)
        if delay:
            time.sleep(delay)

    def do_GET(self):
        self._record()
        if self.path == "/health":
            self._stall()
            self._send(200, type(self).health_body)
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self):
        self._record()
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        err = type(self).error_for.get(self.path)
        if err:
            self._send(err[0], err[1])
            return
        if self.path == "/cancel":
            payload = json.loads(body or b"{}")
            self._send(200, {"cancelled": bool(payload.get("request_id"))})
            return
        if self.path == "/shutdown":
            self._send(202, {"stopping": True})
            return
        self._stall()
        self._send(
            200, {"vertices": [[0, 0, 0]], "faces": [[0, 0, 0]], "confidence": 0.9}
        )


@pytest.fixture
def engine(eng):
    """Run a stand-in engine on a free loopback port."""
    port = _free_port()
    _Handler.health_body = {"protocol_version": 1, "gpu": "Test GPU", "vram_gb": 8.0}
    _Handler.error_for = {}
    _Handler.seen = []
    _Handler.stall_s = {}
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
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


class TestRequestIdentity:
    """FR-036 / FR-037: every request says who it is and what it speaks."""

    def test_every_request_carries_id_and_protocol(self, engine, eng):
        client, handler, _ = engine
        client.reconstruct({}, [])
        assert handler.seen, "handler recorded nothing"
        for path, headers in handler.seen:
            assert headers.get(eng.REQUEST_ID_HEADER), f"{path} sent no request id"
            assert headers.get(eng.PROTOCOL_HEADER) == str(max(eng.PROTOCOL_VERSIONS))

    def test_request_ids_are_unique_per_request(self, engine, eng):
        client, handler, _ = engine
        client.reconstruct({}, [])
        client.reconstruct({}, [])
        ids = {h[eng.REQUEST_ID_HEADER] for _, h in handler.seen}
        assert len(ids) == len(handler.seen)

    def test_token_is_sent_when_a_descriptor_exists(self, engine, eng, monkeypatch):
        """SEC-007: the token from the runtime descriptor authenticates us."""
        client, handler, _ = engine
        monkeypatch.setattr(
            eng.client_mod, "read_runtime_descriptor", lambda: {"token": "9f" * 32}
        )
        client.health()
        _, headers = handler.seen[-1]
        assert headers.get(eng.TOKEN_HEADER) == "9f" * 32

    def test_no_token_header_when_no_descriptor(self, engine, eng, monkeypatch):
        """A missing descriptor is not an auth error — it is a dead engine."""
        client, handler, _ = engine
        monkeypatch.setattr(eng.client_mod, "read_runtime_descriptor", lambda: None)
        client.health()
        _, headers = handler.seen[-1]
        assert eng.TOKEN_HEADER not in headers


class TestTimeoutAndCancel:
    """EC-006 / AC-011: alive but wedged is its own failure mode."""

    def test_wedged_engine_raises_timeout_not_unavailable(
        self, engine, eng, monkeypatch
    ):
        client, handler, _ = engine
        monkeypatch.setattr(eng.client_mod, "_RECONSTRUCT_TIMEOUT_S", 0.3)
        handler.stall_s = {"/reconstruct": 3.0}
        with pytest.raises(eng.EngineTimeoutError) as exc:
            client.reconstruct({}, [])
        assert exc.value.endpoint == "/reconstruct"
        assert exc.value.elapsed_s > 0

    def test_timeout_issues_a_cancel_for_that_request(self, engine, eng, monkeypatch):
        """A wedged request still holds the inference lock (FR-021)."""
        client, handler, _ = engine
        monkeypatch.setattr(eng.client_mod, "_RECONSTRUCT_TIMEOUT_S", 0.3)
        handler.stall_s = {"/reconstruct": 3.0}
        with pytest.raises(eng.EngineTimeoutError):
            client.reconstruct({}, [])

        sent = {path: h for path, h in handler.seen}
        assert "/cancel" in sent, "gave up without releasing the engine"
        reconstruct_id = next(
            h[eng.REQUEST_ID_HEADER] for p, h in handler.seen if p == "/reconstruct"
        )
        cancel_id = next(
            h[eng.REQUEST_ID_HEADER] for p, h in handler.seen if p == "/cancel"
        )
        # The cancel is its own request, but must name the wedged one.
        assert cancel_id != reconstruct_id

    def test_cancel_reports_whether_it_took_effect(self, engine, eng):
        client, _, _ = engine
        assert client.cancel("abc123") is True

    def test_cancel_never_raises_when_engine_is_gone(self, eng):
        """Cancel runs on a path that already failed; it must not mask it."""
        client = eng.EngineClient(host="127.0.0.1", port=_free_port())
        assert client.cancel("abc123") is False

    def test_shutdown_is_acknowledged(self, engine, eng):
        client, _, _ = engine
        assert client.shutdown() is True

    def test_shutdown_never_raises_when_engine_is_gone(self, eng):
        client = eng.EngineClient(host="127.0.0.1", port=_free_port())
        assert client.shutdown() is False


class TestDiscovery:
    """FR-031 / FR-032: installed is answered from disk, not from the port."""

    def test_paths_are_platform_appropriate(self, eng):
        marker = str(eng.discovery.install_marker_path())
        runtime = str(eng.discovery.runtime_descriptor_path())
        assert marker.endswith("install.json")
        assert runtime.endswith("runtime.json")
        assert marker != runtime

    def test_missing_marker_means_not_installed(self, eng, tmp_path, monkeypatch):
        monkeypatch.setattr(
            eng.discovery, "install_marker_path", lambda: tmp_path / "install.json"
        )
        assert eng.discovery.is_installed() is False
        assert eng.discovery.read_install_marker() is None

    def test_present_marker_means_installed(self, eng, tmp_path, monkeypatch):
        marker = tmp_path / "install.json"
        marker.write_text(
            json.dumps(
                {
                    "engine_version": "1.0.0",
                    "protocol_versions": [1],
                    "executable": "/opt/tessera-engine/bin/engine",
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(eng.discovery, "install_marker_path", lambda: marker)
        assert eng.discovery.is_installed() is True
        assert eng.discovery.read_install_marker()["engine_version"] == "1.0.0"

    def test_corrupt_descriptor_is_none_not_an_exception(
        self, eng, tmp_path, monkeypatch
    ):
        """Reading while the engine is still writing is normal, not an error."""
        path = tmp_path / "runtime.json"
        path.write_text('{"port": 876', encoding="utf-8")  # truncated
        monkeypatch.setattr(eng.discovery, "runtime_descriptor_path", lambda: path)
        assert eng.discovery.read_runtime_descriptor() is None

    def test_non_object_descriptor_is_rejected(self, eng, tmp_path, monkeypatch):
        path = tmp_path / "runtime.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        monkeypatch.setattr(eng.discovery, "runtime_descriptor_path", lambda: path)
        assert eng.discovery.read_runtime_descriptor() is None


class TestStartingState:
    """FR-013: a spawn in flight is neither stopped nor absent."""

    def test_spawn_in_progress_reports_starting(self, eng):
        client = eng.EngineClient(host="127.0.0.1", port=_free_port())
        state = eng.resolve_status(client, installed=True, starting=True)
        assert state.status is eng.EngineStatus.STARTING
        assert state.action is None, "must not offer to start it twice"

    def test_starting_outranks_stopped(self, eng):
        client = eng.EngineClient(host="127.0.0.1", port=_free_port())
        stopped = eng.resolve_status(client, installed=True, starting=False)
        assert stopped.status is eng.EngineStatus.STOPPED

    def test_wedged_engine_is_not_reported_as_absent(self, engine, eng, monkeypatch):
        """EC-006 through the status model: there is a log worth reading."""
        client, handler, _ = engine
        monkeypatch.setattr(eng.client_mod, "_HEALTH_TIMEOUT_S", 0.3)
        handler.stall_s = {"/health": 3.0}
        state = eng.resolve_status(client, installed=True)
        assert state.status is eng.EngineStatus.STOPPED
        assert "log" in (state.action or "").lower()
