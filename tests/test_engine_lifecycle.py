# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for engine lifecycle and its effect on adapter selection.

Maps to SPEC-TS-0023: AC-001, AC-002, FR-012, FR-018, FR-033, FR-039,
FR-040, TS-002, TS-003, TS-027, TS-029.
"""

import types

import pytest


def _lc():
    from tessera.engine import lifecycle

    return lifecycle


@pytest.fixture
def lifecycle(mock_bpy):
    return _lc()


class _FakeProcess:
    """Stands in for a spawned engine without starting one."""

    def __init__(self, exits_with=None, stderr=""):
        self._exits_with = exits_with
        self.returncode = exits_with
        self._stderr = stderr
        self.terminated = False
        self.killed = False

    def poll(self):
        return self._exits_with

    def communicate(self, timeout=None):
        return ("", self._stderr)

    def terminate(self):
        self.terminated = True
        self._exits_with = self.returncode = -15

    def kill(self):  # pragma: no cover — only on an unresponsive engine
        self.killed = True
        self._exits_with = self.returncode = -9


class TestSpawn:
    def test_attaches_to_a_running_engine_instead_of_starting_a_second(
        self, lifecycle, monkeypatch, tmp_path
    ):
        """FR-018: a hand-started engine is used as it stands."""
        monkeypatch.setattr(lifecycle.EngineClient, "is_available", lambda self: True)
        spawned = []
        monkeypatch.setattr(
            lifecycle.subprocess, "Popen", lambda *a, **k: spawned.append(a)
        )
        assert lifecycle.spawn_engine(tmp_path) is None
        assert spawned == [], "started a second engine on an occupied port"

    def test_no_installation_is_an_actionable_error(
        self, lifecycle, monkeypatch, tmp_path
    ):
        """AC-002: never a traceback from inside torch."""
        monkeypatch.setattr(lifecycle.EngineClient, "is_available", lambda self: False)
        monkeypatch.setattr(lifecycle, "read_install_marker", lambda: None)
        with pytest.raises(lifecycle.EngineLaunchError) as exc:
            lifecycle.spawn_engine(tmp_path)
        assert "not installed" in str(exc.value)

    def test_marker_pointing_at_a_missing_executable_says_so(
        self, lifecycle, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(lifecycle.EngineClient, "is_available", lambda self: False)
        monkeypatch.setattr(
            lifecycle,
            "read_install_marker",
            lambda: {"executable": str(tmp_path / "gone")},
        )
        with pytest.raises(lifecycle.EngineLaunchError) as exc:
            lifecycle.spawn_engine(tmp_path)
        assert "Reinstall" in str(exc.value)

    def test_cache_root_is_passed_as_a_launch_argument(
        self, lifecycle, monkeypatch, tmp_path
    ):
        """FR-033 / CON-011: never taken from a request."""
        exe = tmp_path / "engine"
        exe.write_text("#!/bin/sh\n")
        monkeypatch.setattr(
            lifecycle, "read_install_marker", lambda: {"executable": str(exe)}
        )
        calls = {"n": 0}

        def _available(self):
            calls["n"] += 1
            return calls["n"] > 1  # absent first, ready after the spawn

        monkeypatch.setattr(lifecycle.EngineClient, "is_available", _available)
        recorded = {}

        def _popen(cmd, **kwargs):
            recorded["cmd"] = cmd
            return _FakeProcess()

        monkeypatch.setattr(lifecycle.subprocess, "Popen", _popen)
        lifecycle.spawn_engine(tmp_path / "cache-root")
        assert "--cache-root" in recorded["cmd"]
        idx = recorded["cmd"].index("--cache-root")
        assert recorded["cmd"][idx + 1].endswith("cache-root")

    def test_immediate_exit_reports_the_engines_own_stderr(
        self, lifecycle, monkeypatch, tmp_path
    ):
        """FR-040: a driver error is worth more than 'it did not start'."""
        exe = tmp_path / "engine"
        exe.write_text("#!/bin/sh\n")
        monkeypatch.setattr(lifecycle.EngineClient, "is_available", lambda self: False)
        monkeypatch.setattr(
            lifecycle, "read_install_marker", lambda: {"executable": str(exe)}
        )
        monkeypatch.setattr(
            lifecycle.subprocess,
            "Popen",
            lambda *a, **k: _FakeProcess(
                exits_with=1, stderr="CUDA driver version is insufficient"
            ),
        )
        with pytest.raises(lifecycle.EngineLaunchError) as exc:
            lifecycle.spawn_engine(tmp_path)
        assert "CUDA driver version is insufficient" in str(exc.value)
        assert exc.value.stderr_head

    def test_stderr_is_capped(self, lifecycle):
        head = lifecycle._head("\n".join(f"line {i}" for i in range(200)))
        assert head.count("\n") <= lifecycle._STDERR_LINES
        assert "more lines in the engine log" in head

    def test_engine_that_never_answers_is_terminated(
        self, lifecycle, monkeypatch, tmp_path
    ):
        """FR-040: do not leave it holding the port for the next attempt."""
        exe = tmp_path / "engine"
        exe.write_text("#!/bin/sh\n")
        monkeypatch.setattr(lifecycle.EngineClient, "is_available", lambda self: False)
        monkeypatch.setattr(
            lifecycle, "read_install_marker", lambda: {"executable": str(exe)}
        )
        process = _FakeProcess()
        monkeypatch.setattr(lifecycle.subprocess, "Popen", lambda *a, **k: process)
        monkeypatch.setattr(lifecycle, "_POLL_INTERVAL_S", 0.01)
        with pytest.raises(lifecycle.EngineLaunchError) as exc:
            lifecycle.spawn_engine(tmp_path, timeout_s=0.05)
        assert process.terminated is True
        assert "did not become ready" in str(exc.value)


class TestStop:
    def test_clean_shutdown_is_asked_for_first(self, lifecycle, monkeypatch):
        """FR-039: let it drain and free VRAM before signalling anything."""
        asked = {"n": 0}

        def _shutdown(self):
            asked["n"] += 1
            return True

        monkeypatch.setattr(lifecycle.EngineClient, "shutdown", _shutdown)
        process = _FakeProcess(exits_with=0)
        assert lifecycle.stop_engine(process) is True
        assert asked["n"] == 1
        assert process.terminated is False

    def test_an_attached_engine_is_never_signalled(self, lifecycle, monkeypatch):
        """Not ours to kill — someone is debugging with it."""
        monkeypatch.setattr(lifecycle.EngineClient, "shutdown", lambda self: True)
        assert lifecycle.stop_engine(None) is True

    def test_an_engine_that_ignores_shutdown_is_terminated(
        self, lifecycle, monkeypatch
    ):
        monkeypatch.setattr(lifecycle.EngineClient, "shutdown", lambda self: False)
        monkeypatch.setattr(lifecycle, "_POLL_INTERVAL_S", 0.01)
        process = _FakeProcess()
        assert lifecycle.stop_engine(process, grace_s=0.05) is True
        assert process.terminated is True


class TestAdapterSelectionRespectsTheEngine:
    """FR-012: an unreachable engine excludes engine-backed adapters."""

    @pytest.fixture
    def registry_parts(self, mock_bpy):
        from tessera.reconstruction.adapters.stub_adapter import StubAdapter
        from tessera.reconstruction.registry import AdapterRegistry

        return types.SimpleNamespace(
            AdapterRegistry=AdapterRegistry, StubAdapter=StubAdapter
        )

    def _engine_adapter(self, registry_parts, name="engine-model"):
        from tessera.reconstruction.mesh_output import AdapterCapabilities

        class _EngineBacked(registry_parts.StubAdapter):
            requires_engine = True

            def capabilities(self):
                return AdapterCapabilities(
                    model_name=name,
                    min_images=1,
                    max_images=4,
                    requires_depth=False,
                    requires_mask=False,
                    min_vram_gb=6.0,
                    supported_view_labels=["front"],
                    output_types=["mesh"],
                )

        return _EngineBacked()

    def test_engine_adapter_is_selected_when_the_engine_is_ready(self, registry_parts):
        registry = registry_parts.AdapterRegistry()
        registry.register(self._engine_adapter(registry_parts))
        registry.register(registry_parts.StubAdapter())
        chosen = registry.select(1, "/tmp", 12.0, engine_available=True)
        assert getattr(chosen, "requires_engine", False) is True

    def test_engine_adapter_is_excluded_when_the_engine_is_absent(self, registry_parts):
        """AC-002: fall back to the stub rather than failing at generate."""
        registry = registry_parts.AdapterRegistry()
        registry.register(self._engine_adapter(registry_parts))
        registry.register(registry_parts.StubAdapter())
        chosen = registry.select(1, "/tmp", 12.0, engine_available=False)
        assert isinstance(chosen, registry_parts.StubAdapter)
        assert getattr(chosen, "requires_engine", False) is False

    def test_registry_without_engine_adapters_never_probes(
        self, registry_parts, monkeypatch
    ):
        """Nothing pays for a boundary it does not use."""
        registry = registry_parts.AdapterRegistry()
        registry.register(registry_parts.StubAdapter())
        probed = {"n": 0}
        monkeypatch.setattr(
            registry_parts.AdapterRegistry,
            "_engine_is_ready",
            lambda self: probed.__setitem__("n", probed["n"] + 1) or True,
        )
        registry.select(1, "/tmp", 12.0)
        assert probed["n"] == 0

    def test_unresolvable_engine_status_excludes_engine_adapters(
        self, registry_parts, monkeypatch
    ):
        """An engine we cannot ask about is one we must not route work to."""
        registry = registry_parts.AdapterRegistry()
        registry.register(self._engine_adapter(registry_parts))
        registry.register(registry_parts.StubAdapter())
        monkeypatch.setattr(
            registry_parts.AdapterRegistry,
            "_engine_is_ready",
            lambda self: False,
        )
        chosen = registry.select(1, "/tmp", 12.0)
        assert isinstance(chosen, registry_parts.StubAdapter)
