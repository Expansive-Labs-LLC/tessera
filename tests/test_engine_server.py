# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the engine side of the boundary.

These import ``tessera_engine`` directly and never touch ``bpy`` — the
engine is a separate program, and a test that needed Blender to exercise
it would be testing the wrong thing.

No GPU and no PyTorch are required. Every failure mode below except the
inference itself is reachable without them, which is the point of keeping
transport, authentication and validation above the adapter layer.

Maps to SPEC-TS-0023: AC-004, AC-006, AC-008, AC-012, AC-013, EC-003,
EC-005, TS-006, TS-008, TS-012, TS-013, TS-014, TS-024, TS-026, TS-030,
TS-031, TS-035, TS-036, TS-037.
"""

import json
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pytest

from tessera_engine import (
    MAX_REQUEST_BYTES,
    PROTOCOL_HEADER,
    REQUEST_ID_HEADER,
    TOKEN_HEADER,
)
from tessera_engine import inference as inf
from tessera_engine.codec import encode_array, encode_png
from tessera_engine.errors import SLUG_STATUS, EngineFault
from tessera_engine.runtime import EngineRuntime
from tessera_engine.server import EngineServer, build_server


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def cache_root(tmp_path):
    root = tmp_path / "cache"
    (root / "trellis").mkdir(parents=True)
    (root / "trellis" / "model.safetensors").write_bytes(b"not really weights")
    return root


@pytest.fixture
def engine(cache_root, tmp_path):
    """A running engine on a free loopback port."""
    runtime = EngineRuntime(
        cache_root, 0, tmp_path / "engine.log", descriptor_path=tmp_path / "rt.json"
    )
    server = EngineServer(runtime, inf.reconstruct, inf.vision)
    httpd = build_server(server, "127.0.0.1", 0)
    runtime.port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, httpd, runtime
    finally:
        httpd.shutdown()
        httpd.server_close()


def _call(runtime, path, payload=None, *, token=None, headers=None, method=None):
    """Issue one request the way the add-on would, returning (status, body)."""
    url = f"http://127.0.0.1:{runtime.port}{path}"
    hdrs = {
        REQUEST_ID_HEADER: "req-1",
        PROTOCOL_HEADER: "1",
        TOKEN_HEADER: runtime.token if token is None else token,
    }
    hdrs.update(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


class TestAuthentication:
    """SEC-007 / AC-012: loopback is not a trust boundary."""

    def test_health_succeeds_with_the_token(self, engine):
        _, _, runtime = engine
        status, body = _call(runtime, "/health")
        assert status == 200
        assert body["protocol_version"] == 1

    def test_missing_token_is_refused(self, engine):
        _, _, runtime = engine
        status, body = _call(runtime, "/health", token="")
        assert status == 401
        assert body["error"] == "unauthorized"

    def test_wrong_token_is_refused(self, engine):
        _, _, runtime = engine
        status, body = _call(runtime, "/health", token="0" * 64)
        assert status == 401

    def test_origin_header_is_refused_outright(self, engine):
        """Defeats a page in the user's own browser, DNS rebinding included."""
        _, _, runtime = engine
        status, body = _call(
            runtime, "/health", headers={"Origin": "https://example.com"}
        )
        assert status == 401
        assert "Cross-origin" in body["detail"]

    def test_foreign_host_header_is_refused(self, engine):
        _, _, runtime = engine
        status, _ = _call(runtime, "/health", headers={"Host": "attacker.test"})
        assert status == 401

    def test_unauthorised_request_body_is_never_read(self, engine):
        """A refused caller must not get the engine to absorb its payload."""
        _, _, runtime = engine
        status, body = _call(
            runtime, "/reconstruct", {"weight_paths": {}}, token="0" * 64
        )
        assert status == 401
        assert "weight_paths" not in json.dumps(body)


class TestProtocolNegotiation:
    def test_unspoken_protocol_is_refused(self, engine):
        _, _, runtime = engine
        status, body = _call(runtime, "/health", headers={PROTOCOL_HEADER: "99"})
        assert status == 400
        assert body["error"] == "protocol_mismatch"
        assert body["engine_protocol"] == 1

    def test_absent_protocol_header_is_refused(self, engine):
        _, _, runtime = engine
        status, body = _call(runtime, "/health", headers={PROTOCOL_HEADER: ""})
        assert status == 400
        assert body["error"] == "protocol_mismatch"


class TestWeightPathContainment:
    """SEC-003 / AC-004: the engine never acquires or wanders to weights."""

    def test_path_inside_the_root_resolves(self, engine, cache_root):
        _, _, runtime = engine
        resolved = runtime.resolve_weight_path(str(cache_root / "trellis"), "trellis")
        assert resolved == (cache_root / "trellis").resolve()

    def test_path_outside_the_root_is_refused(self, engine):
        _, _, runtime = engine
        with pytest.raises(EngineFault) as exc:
            runtime.resolve_weight_path("/etc/passwd", "trellis")
        assert exc.value.slug == "weights_missing"

    def test_traversal_out_of_the_root_is_refused(self, engine, cache_root):
        _, _, runtime = engine
        with pytest.raises(EngineFault) as exc:
            runtime.resolve_weight_path(
                str(cache_root / "trellis" / ".." / ".." / ".." / "etc"), "trellis"
            )
        assert exc.value.slug == "weights_missing"

    def test_symlink_out_of_the_root_is_refused(self, engine, cache_root, tmp_path):
        """resolve() before the check, so a symlink cannot walk out after it."""
        _, _, runtime = engine
        outside = tmp_path / "outside"
        outside.mkdir()
        link = cache_root / "escape"
        link.symlink_to(outside)
        with pytest.raises(EngineFault) as exc:
            runtime.resolve_weight_path(str(link), "trellis")
        assert exc.value.slug == "weights_missing"

    def test_absent_and_forbidden_are_indistinguishable(self, engine, cache_root):
        """Otherwise the engine becomes a file-existence oracle."""
        _, _, runtime = engine
        absent = runtime_fault(runtime, str(cache_root / "nope"))
        forbidden = runtime_fault(runtime, "/root/.ssh/id_rsa")
        assert absent.slug == forbidden.slug == "weights_missing"
        assert absent.detail == forbidden.detail

    def test_engine_never_downloads(self, engine, cache_root):
        """AC-004: a missing path is an error, not a reason to fetch."""
        _, _, runtime = engine
        status, body = _call(
            runtime,
            "/reconstruct",
            {"weight_paths": {"trellis": str(cache_root / "absent")}, "inputs": [{}]},
        )
        assert status == 400
        assert body["error"] == "weights_missing"


def runtime_fault(runtime, path):
    try:
        runtime.resolve_weight_path(path, "trellis")
    except EngineFault as exc:
        return exc
    raise AssertionError("expected a fault")


class TestConcurrency:
    """FR-021 / FR-034: one inference, but health is always answerable."""

    def test_second_inference_gets_busy_with_retry_after(self, engine, cache_root):
        server, _, runtime = engine
        assert server.inference.acquire("holder") is True
        try:
            status, body = _call(
                runtime,
                "/reconstruct",
                {
                    "weight_paths": {"trellis": str(cache_root / "trellis")},
                    "inputs": [{}],
                },
            )
        finally:
            server.inference.release()
        assert status == 409
        assert body["error"] == "busy"
        assert body["retryable"] is True

    def test_health_answers_while_an_inference_holds_the_slot(self, engine):
        """NFR-011: a status poll must not queue behind a 40-second job."""
        server, _, runtime = engine
        assert server.inference.acquire("holder") is True
        try:
            status, body = _call(runtime, "/health")
        finally:
            server.inference.release()
        assert status == 200
        assert body["busy"] is True

    def test_cancel_only_affects_the_request_in_flight(self, engine):
        server, _, runtime = engine
        server.inference.acquire("in-flight")
        try:
            _, body = _call(runtime, "/cancel", {"request_id": "something-else"})
            assert body["cancelled"] is False
            _, body = _call(runtime, "/cancel", {"request_id": "in-flight"})
            assert body["cancelled"] is True
        finally:
            server.inference.release()

    def test_cancel_with_nothing_in_flight_is_not_an_error(self, engine):
        _, _, runtime = engine
        status, body = _call(runtime, "/cancel", {"request_id": "whatever"})
        assert status == 200
        assert body["cancelled"] is False


class TestPayloadLimits:
    def test_oversized_body_is_refused_from_content_length(self, engine):
        """FR-038: decided before the body is read, not after."""
        _, _, runtime = engine
        url = f"http://127.0.0.1:{runtime.port}/reconstruct"
        req = urllib.request.Request(
            url,
            data=b"{}",
            headers={
                REQUEST_ID_HEADER: "req-1",
                PROTOCOL_HEADER: "1",
                TOKEN_HEADER: runtime.token,
                "Content-Type": "application/json",
                "Content-Length": str(MAX_REQUEST_BYTES + 1),
            },
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            raise AssertionError("expected a refusal")
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode())
            assert exc.code == 413
            assert body["error"] == "payload_too_large"
            assert body["limit_bytes"] == MAX_REQUEST_BYTES

    def test_malformed_json_is_bad_request(self, engine):
        _, _, runtime = engine
        url = f"http://127.0.0.1:{runtime.port}/reconstruct"
        raw = b"{not json"
        req = urllib.request.Request(
            url,
            data=raw,
            headers={
                REQUEST_ID_HEADER: "req-1",
                PROTOCOL_HEADER: "1",
                TOKEN_HEADER: runtime.token,
                "Content-Type": "application/json",
            },
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            raise AssertionError("expected a refusal")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            assert json.loads(exc.read().decode())["error"] == "bad_request"


class TestVisionStages:
    def test_unknown_stage_is_named_in_the_refusal(self, engine, cache_root):
        _, _, runtime = engine
        status, body = _call(
            runtime,
            "/vision",
            {
                "stage": "telepathy",
                "weight_paths": {"sam2": str(cache_root / "trellis")},
            },
        )
        assert status == 400
        assert body["error"] == "unsupported_stage"
        assert body["stage"] == "telepathy"

    def test_known_stage_without_an_adapter_is_load_failed(self, engine, cache_root):
        _, _, runtime = engine
        status, body = _call(
            runtime,
            "/vision",
            {
                "stage": "depth",
                "weight_paths": {"depth_anything": str(cache_root / "trellis")},
            },
        )
        assert status == 422
        assert body["error"] == "load_failed"


class TestResultCeiling:
    def test_oversized_mesh_is_refused_not_truncated(
        self, engine, cache_root, monkeypatch
    ):
        """FR-028: a silently truncated mesh is worse than an error."""
        _, _, runtime = engine

        def _huge(path, inputs):
            return {
                "vertices": np.zeros((5, 3), "float32"),
                "faces": np.zeros((3, 3), "int32"),
                "metadata": {
                    "model_name": "t",
                    "inference_time_s": 1.0,
                    "confidence": 0.5,
                },
            }

        monkeypatch.setitem(inf._RECONSTRUCTION, "trellis", _huge)
        monkeypatch.setattr(inf, "MAX_VERTICES", 4)
        monkeypatch.setattr(inf, "_check_vram", lambda *_: None)
        status, body = _call(
            runtime,
            "/reconstruct",
            {
                "weight_paths": {"trellis": str(cache_root / "trellis")},
                "inputs": [_vision_input()],
            },
        )
        assert status == 422
        assert body["error"] == "mesh_too_large"
        assert body["vertex_count"] == 5


class TestEndToEndRoundTrip:
    def test_a_reconstruction_returns_every_field_standardmesh_needs(
        self, engine, cache_root, monkeypatch
    ):
        """AC-010 / FR-026: nothing the add-on needs is defaulted."""
        _, _, runtime = engine
        seen = {}

        def _adapter(path, inputs):
            seen["inputs"] = inputs
            return {
                "vertices": np.array([[0, 0, 0], [1, 1, 1]], "float32"),
                "faces": np.array([[0, 1, 0]], "int32"),
                "vertex_colors": np.array([[1, 0, 0], [0, 1, 0]], "float32"),
                "metadata": {
                    "model_name": "trellis-v1",
                    "inference_time_s": 2.5,
                    "confidence": 0.77,
                },
                "warnings": ["low texture detail"],
            }

        monkeypatch.setitem(inf._RECONSTRUCTION, "trellis", _adapter)
        monkeypatch.setattr(inf, "_check_vram", lambda *_: None)
        status, body = _call(
            runtime,
            "/reconstruct",
            {
                "weight_paths": {"trellis": str(cache_root / "trellis")},
                "inputs": [_vision_input()],
            },
        )
        assert status == 200
        for key in (
            "model_name",
            "inference_time_s",
            "confidence",
            "vertex_count",
            "face_count",
            "warnings",
            "source_adapter",
        ):
            assert key in body, f"{key} missing — the add-on would have to invent it"
        assert body["vertex_count"] == 2
        assert body["warnings"] == ["low texture detail"]
        assert "duration_s" in body

        # AC-009: the fields a thinner payload would have dropped.
        decoded = seen["inputs"][0]
        assert decoded["features"].shape == (1, 8)
        assert decoded["camera_pose"].shape == (4, 4)
        assert decoded["original_size"] == (640, 480)

    def test_malformed_input_names_the_field(self, engine, cache_root, monkeypatch):
        _, _, runtime = engine
        monkeypatch.setitem(inf._RECONSTRUCTION, "trellis", lambda p, i: {})
        bad = _vision_input()
        del bad["features"]
        status, body = _call(
            runtime,
            "/reconstruct",
            {"weight_paths": {"trellis": str(cache_root / "trellis")}, "inputs": [bad]},
        )
        assert status == 400
        assert body["error"] == "bad_request"
        assert "features" in body["field"]


def _vision_input():
    """One wire input carrying every field FR-025 requires."""
    return {
        "image": encode_png(np.zeros((4, 4, 3), "uint8"), "image"),
        "mask": encode_png(np.zeros((4, 4), "uint8"), "mask"),
        "depth_map": encode_array(np.zeros((4, 4), "float32"), "float32"),
        "features": encode_array(np.zeros((1, 8), "float32"), "float32"),
        "view_label": "front",
        "label_confidence": 0.9,
        "label_source": "user",
        "label_needs_confirmation": False,
        "original_size": [640, 480],
        "camera_pose": encode_array(np.eye(4, dtype="float32"), "float32"),
    }


class TestShutdown:
    def test_shutdown_removes_the_descriptor_and_stops(self, engine, tmp_path):
        """AC-013 / FR-039."""
        _, _, runtime = engine
        runtime.write_descriptor()
        assert (tmp_path / "rt.json").exists()
        status, body = _call(runtime, "/shutdown", {})
        assert status == 202 and body["stopping"] is True
        for _ in range(100):
            if not (tmp_path / "rt.json").exists():
                break
            import time as _t

            _t.sleep(0.02)
        assert not (tmp_path / "rt.json").exists()

    def test_descriptor_is_owner_readable_only(self, engine, tmp_path):
        """SEC-007: a token every local process can read is not a token."""
        _, _, runtime = engine
        path = runtime.write_descriptor()
        import stat as _stat

        mode = _stat.S_IMODE(path.stat().st_mode)
        assert mode & 0o077 == 0, f"descriptor is group/world accessible: {oct(mode)}"
        assert json.loads(path.read_text())["token"] == runtime.token


class TestBindingRefusal:
    @pytest.mark.parametrize("host", ["0.0.0.0", "10.0.0.5", "example.com"])
    def test_non_loopback_bind_is_refused(self, cache_root, tmp_path, host):
        """SEC-001 / TS-013: refused at construction, not per request."""
        runtime = EngineRuntime(
            cache_root, 0, tmp_path / "e.log", descriptor_path=tmp_path / "rt.json"
        )
        server = EngineServer(runtime, inf.reconstruct, inf.vision)
        with pytest.raises(ValueError) as exc:
            build_server(server, host, 0)
        assert "loopback" in str(exc.value)


class TestErrorContract:
    def test_every_slug_has_a_documented_status(self):
        for slug, (status, retryable) in SLUG_STATUS.items():
            assert 400 <= status <= 599, slug
            assert isinstance(retryable, bool), slug

    def test_only_busy_is_retryable(self):
        """Nothing else succeeds on an unchanged retry."""
        retryable = {s for s, (_, r) in SLUG_STATUS.items() if r}
        assert retryable == {"busy"}

    def test_an_undocumented_slug_degrades_to_internal(self):
        """A new slug is an engine bug, not a contract the add-on knows."""
        fault = EngineFault("something_new", "oops")
        assert fault.slug == "internal"
        assert fault.status == 500


class TestEngineIsStandalone:
    def test_engine_imports_no_bpy(self):
        """CON-002 / TS-015: the engine must not need Blender."""
        root = Path(__file__).resolve().parent.parent / "tessera_engine"
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "import bpy" not in text, f"{path.name} imports bpy"

    def test_wire_contract_is_identical_on_both_sides(self):
        """The codec is duplicated by design; this is what pins it."""
        root = Path(__file__).resolve().parent.parent
        addon = (root / "tessera" / "engine" / "codec.py").read_bytes()
        engine = (root / "tessera_engine" / "codec.py").read_bytes()
        assert addon == engine, (
            "codec.py has drifted between the add-on and the engine — "
            "the two halves would disagree about the wire format"
        )
