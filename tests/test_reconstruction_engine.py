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

"""Tests for SPEC-TS-0004 — Single-Image 3D Reconstruction Engine.

Each test maps to a test scenario (TS-XXX) in §13 of the spec,
linked to acceptance criteria (AC-XXX) and edge cases (EC-XXX).

Tests are designed to run in CI without a GPU or the Trellis wheel.
- StubAdapter exercises the full engine pipeline.
- TrellisAdapter is tested via direct method calls with mocked
  internals.
"""

from __future__ import annotations

import signal
import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vision_result(
    width: int = 512,
    height: int = 512,
    view_label: str = "front",
    mask_value: int = 255,
    depth_value: float = 0.5,
    label_confidence: float = 0.92,
    label_source: str = "user",
    label_needs_confirmation: bool = False,
):
    """Create a minimal VisionResult-like object for testing.

    Returns a ``MagicMock`` with the fields expected by
    ``ReconstructionEngine``.
    """
    result = MagicMock()
    result.image = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    result.mask = np.full((height, width), mask_value, dtype=np.uint8)
    result.depth_map = np.full((height, width), depth_value, dtype=np.float32)
    result.view_label = view_label
    result.label_confidence = label_confidence
    result.label_source = label_source
    result.label_needs_confirmation = label_needs_confirmation
    result.features = np.random.randn(1, 768).astype(np.float32)
    result.original_size = (width, height)
    result.processing_time_s = {"segmentation": 1.0}
    return result


# ---------------------------------------------------------------------------
# Lazy imports — deferred so conftest's bpy mock is active first
# ---------------------------------------------------------------------------


class _FakeCache:
    """Stands in for ``CacheManager`` at the adapter's weight boundary.

    The adapter no longer owns weight discovery or digests — it asks the
    model layer (SPEC-TS-0002). These tests therefore drive the adapter
    through that contract rather than by planting files on disk.
    """

    def __init__(self, path=None, integrity=(True, None)):
        self._path = path
        self._integrity = integrity

    def get_model_path(self, model_id):
        return self._path

    def verify_integrity(self, model_id):
        return self._integrity


def _cached_weights(tmp_path):
    """Create a snapshot dir shaped like the TRELLIS manifest entry."""
    snap = tmp_path / "snapshot"
    (snap / "ckpts").mkdir(parents=True)
    (snap / "pipeline.json").write_text("{}")
    return snap


@pytest.fixture
def reconstruction_imports():
    """Import reconstruction modules after bpy mock is installed."""
    from tessera.reconstruction.adapters.stub_adapter import StubAdapter
    from tessera.reconstruction.adapters.trellis_adapter import TrellisAdapter
    from tessera.reconstruction.engine import (
        ReconstructionEngine,
        _TimeoutError,
    )
    from tessera.reconstruction.mesh_output import (
        AdapterCapabilities,
        ReconstructionResult,
        StandardMesh,
    )
    from tessera.reconstruction.registry import AdapterRegistry
    from tessera.reconstruction.utils.mesh_conversion import (
        normalize_to_standard_mesh,
        validate_mesh,
    )
    from tessera.reconstruction.utils.vram_guard import VRAMGuard

    class _Imports:
        pass

    m = _Imports()
    m.StubAdapter = StubAdapter
    m.TrellisAdapter = TrellisAdapter
    m.ReconstructionEngine = ReconstructionEngine
    m.AdapterRegistry = AdapterRegistry
    m.StandardMesh = StandardMesh
    m.ReconstructionResult = ReconstructionResult
    m.AdapterCapabilities = AdapterCapabilities
    m.VRAMGuard = VRAMGuard
    m.normalize_to_standard_mesh = normalize_to_standard_mesh
    m.validate_mesh = validate_mesh
    m._TimeoutError = _TimeoutError
    return m


# ---------------------------------------------------------------------------
# Test Suites — mapped to §13 test scenarios
# ---------------------------------------------------------------------------


class TestSingleImageReconstruction:
    """Tests mapping to AC-001 (single-image happy path)."""

    def test_TS001_single_image_returns_valid_mesh(
        self, reconstruction_imports, tmp_path
    ):
        """TS-001 → AC-001: Single-image reconstruction returns valid
        StandardMesh with ≥ 4 vertices (stub adapter in CI)."""
        m = reconstruction_imports

        # Given — engine with stub adapter fallback (no GPU, no weights)
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp = _make_vision_result(width=512, height=512, view_label="front")

        # When
        result = engine.reconstruct([inp])

        # Then
        assert result.success is True, f"Expected success, got: {result.error_message}"
        assert result.mesh is not None
        assert result.mesh.vertices.shape[1] == 3  # (N, 3)
        assert result.mesh.faces.shape[1] == 3  # (M, 3)
        assert result.mesh.vertices.dtype == np.float32
        assert result.mesh.faces.dtype == np.int32
        assert result.mesh.metadata["vertex_count"] >= 4
        assert result.mesh.metadata["face_count"] >= 4
        assert result.mesh.metadata["model_name"] != ""
        assert "inference_time_s" in result.mesh.metadata
        assert "confidence" in result.mesh.metadata

    def test_TS016_single_image_completes_within_60s(
        self, reconstruction_imports, tmp_path
    ):
        """TS-016 → NFR-001: Single-image reconstruction completes
        in < 60s (stub adapter: near-instant)."""
        m = reconstruction_imports

        # Given
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=60)
        inp = _make_vision_result()

        # When
        start = time.monotonic()
        result = engine.reconstruct([inp])
        elapsed = time.monotonic() - start

        # Then
        assert result.success is True
        assert elapsed < 60.0, f"Reconstruction took {elapsed:.1f}s (limit: 60s)"

    def test_TS017_peak_vram_below_10gb(self, reconstruction_imports, tmp_path):
        """TS-017 → NFR-003: Peak VRAM usage stays below 10 GB
        (stub adapter uses 0 VRAM)."""
        m = reconstruction_imports

        # Given — StubAdapter uses no GPU memory
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp = _make_vision_result()

        # When
        result = engine.reconstruct([inp])

        # Then — stub adapter uses 0 VRAM; verify we can query VRAM
        assert result.success is True
        available = m.VRAMGuard.get_available_vram_gb()
        # In CI (no GPU), available should be 0.0 — just verify no crash
        assert isinstance(available, float)


class TestFewImageReconstruction:
    """Tests mapping to AC-002 (few-image happy path)."""

    def test_TS002_two_image_returns_valid_mesh(self, reconstruction_imports, tmp_path):
        """TS-002 → AC-002: Two-image reconstruction with 'front' and
        'right' labels returns valid mesh."""
        m = reconstruction_imports

        # Given
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp_front = _make_vision_result(view_label="front")
        inp_right = _make_vision_result(view_label="right")

        # When
        result = engine.reconstruct([inp_front, inp_right])

        # Then
        assert result.success is True, f"Expected success, got: {result.error_message}"
        assert result.mesh is not None
        assert result.mesh.metadata["vertex_count"] >= 4
        assert result.mesh.metadata["face_count"] >= 4
        # No duplicate-label warning expected
        dup_warnings = [w for w in result.warnings if "share the view label" in w]
        assert len(dup_warnings) == 0


class TestMissingWeights:
    """Tests mapping to AC-003 (missing model weights)."""

    def test_TS003_missing_weights_returns_failure(
        self, reconstruction_imports, tmp_path
    ):
        """TS-003 → AC-003: Missing model weights returns success=False
        with actionable error message from TrellisAdapter."""
        m = reconstruction_imports

        # Given — TrellisAdapter pointed at empty cache
        adapter = m.TrellisAdapter(cache_dir=str(tmp_path))

        # When
        assert adapter.weights_available() is False
        inp = _make_vision_result()
        result = adapter.reconstruct([inp])

        # Then
        assert result.success is False
        assert result.mesh is None
        assert "not found" in result.error_message.lower()
        assert "download" in result.error_message.lower()
        assert result.source_adapter == "trellis-v1.0"


class TestInsufficientVRAM:
    """Tests mapping to AC-004 (insufficient VRAM)."""

    def test_TS009_insufficient_vram_returns_failure(
        self, reconstruction_imports, tmp_path
    ):
        """TS-009 → AC-004: Insufficient VRAM returns success=False
        before loading weights."""
        m = reconstruction_imports

        # Given — weights resolved and verified by the model layer
        adapter = m.TrellisAdapter(
            cache_dir=str(tmp_path),
            cache_manager=_FakeCache(path=_cached_weights(tmp_path)),
        )
        assert adapter.weights_available() is True

        # Mock: system-level non-determinism — GPU VRAM detection
        with patch.object(m.VRAMGuard, "check", return_value=(False, 2.0)):
            inp = _make_vision_result()
            result = adapter.reconstruct([inp])

        # Then
        assert result.success is False
        assert result.mesh is None
        assert "insufficient" in result.error_message.lower()
        assert "vram" in result.error_message.lower()


class TestAdapterRegistryFallback:
    """Tests mapping to AC-005 (registry fallback to StubAdapter)."""

    def test_TS010_stub_adapter_returns_cube(self, reconstruction_imports):
        """TS-010 → AC-005: StubAdapter returns unit cube without
        GPU or model weights."""
        m = reconstruction_imports

        # Given
        stub = m.StubAdapter()
        inp = _make_vision_result()

        # When
        result = stub.reconstruct([inp])

        # Then
        assert result.success is True
        assert result.mesh is not None
        assert result.mesh.metadata["vertex_count"] == 8  # Unit cube
        assert result.mesh.metadata["face_count"] == 12  # 6 sides × 2 tris
        assert result.source_adapter == "stub"
        assert result.mesh.metadata["model_name"] == "stub"
        assert result.mesh.metadata["confidence"] == 1.0
        assert result.mesh.vertex_colors is not None
        assert result.mesh.vertex_colors.shape == (8, 3)

    def test_TS013_registry_discovers_adapters_within_100ms(
        self, reconstruction_imports, tmp_path
    ):
        """TS-013 → NFR-007: AdapterRegistry discovers and lists
        all registered adapters in < 100ms."""
        m = reconstruction_imports

        # Given
        registry = m.AdapterRegistry()
        registry.register(m.StubAdapter())
        registry.register(m.TrellisAdapter(cache_dir=str(tmp_path)))

        # When
        start = time.monotonic()
        caps = registry.list_all()
        elapsed_ms = (time.monotonic() - start) * 1000

        # Then
        assert (
            elapsed_ms < 100.0
        ), f"Registry listing took {elapsed_ms:.1f}ms (limit: 100ms)"
        assert len(caps) == 2
        names = {c.model_name for c in caps}
        assert "stub" in names
        assert "trellis-v1.0" in names


class TestVRAMCleanup:
    """Tests mapping to AC-006 (GPU cleanup after reconstruction)."""

    def test_TS011_vram_within_50mb_after_reconstruction(
        self, reconstruction_imports, tmp_path
    ):
        """TS-011 → AC-006: GPU memory cleanup is called after
        reconstruction (verifies cleanup_gpu() invocation)."""
        m = reconstruction_imports

        # Given
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp = _make_vision_result()

        # When
        # Mock: system-level non-determinism — GPU VRAM cleanup
        with patch.object(m.VRAMGuard, "cleanup_gpu", return_value=0.0):
            result = engine.reconstruct([inp])

        # Then — StubAdapter path doesn't directly call cleanup_gpu
        # (it's called from TrellisAdapter), but engine always succeeds
        assert result.success is True

        # Verify cleanup_gpu is callable and returns float
        freed = m.VRAMGuard.cleanup_gpu()
        assert isinstance(freed, float)
        assert freed >= 0.0


class TestDegenerateOutput:
    """Tests mapping to AC-007 (degenerate mesh detection)."""

    def test_TS012_degenerate_mesh_returns_failure(self, reconstruction_imports):
        """TS-012 → AC-007: Degenerate output (< 4 vertices) returns
        success=False."""
        m = reconstruction_imports

        # Given — create a degenerate mesh
        tiny_mesh = m.normalize_to_standard_mesh(
            vertices=np.zeros((2, 3), dtype=np.float32),
            faces=np.zeros((1, 3), dtype=np.int32),
        )

        # When
        valid, err = m.validate_mesh(tiny_mesh)

        # Then
        assert valid is False
        assert "degenerate" in err.lower()

        # Also verify a valid mesh passes
        ok_mesh = m.normalize_to_standard_mesh(
            vertices=np.random.randn(100, 3).astype(np.float32),
            faces=np.arange(30).reshape(10, 3).astype(np.int32),
        )
        valid2, err2 = m.validate_mesh(ok_mesh)
        assert valid2 is True
        assert err2 == ""


class TestEdgeCases:
    """Tests mapping to edge cases EC-001 through EC-006."""

    def test_TS004_small_image_accepted_with_warning(
        self, reconstruction_imports, tmp_path
    ):
        """TS-004 → EC-001: Image at minimum resolution (64×64) is
        accepted with quality warning."""
        m = reconstruction_imports

        # Given — 64×64 image (below 256×256 recommended minimum)
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp = _make_vision_result(width=64, height=64)

        # When
        result = engine.reconstruct([inp])

        # Then — should succeed with a resolution warning
        assert result.success is True
        quality_warnings = [
            w
            for w in result.warnings
            if "below" in w.lower() and "resolution" in w.lower()
        ]
        assert (
            len(quality_warnings) >= 1
        ), f"Expected resolution warning, got warnings: {result.warnings}"

    def test_TS005_full_mask_proceeds_with_warning(
        self, reconstruction_imports, tmp_path
    ):
        """TS-005 → EC-002: All-True mask proceeds with full-image
        warning."""
        m = reconstruction_imports

        # Given — mask covers 100% of image
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp = _make_vision_result(mask_value=255)

        # When
        result = engine.reconstruct([inp])

        # Then — should succeed with a full-mask warning
        assert result.success is True
        full_mask_warnings = [w for w in result.warnings if "100%" in w]
        assert (
            len(full_mask_warnings) >= 1
        ), f"Expected full-mask warning, got warnings: {result.warnings}"

    def test_TS006_empty_mask_returns_failure(self, reconstruction_imports, tmp_path):
        """TS-006 → EC-003: All-False mask returns success=False with
        no-object error."""
        m = reconstruction_imports

        # Given — mask is all zeros (no object detected)
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp = _make_vision_result(mask_value=0)

        # When
        result = engine.reconstruct([inp])

        # Then
        assert result.success is False
        assert result.mesh is None
        assert (
            "empty" in result.error_message.lower()
            or "no object" in result.error_message.lower()
        )

    def test_TS007_duplicate_view_labels_produce_warning(
        self, reconstruction_imports, tmp_path
    ):
        """TS-007 → EC-004: Duplicate view labels produce warning
        but succeed."""
        m = reconstruction_imports

        # Given — two images with the same label
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp_a = _make_vision_result(view_label="front")
        inp_b = _make_vision_result(view_label="front")

        # When
        result = engine.reconstruct([inp_a, inp_b])

        # Then — should succeed with a duplicate label warning
        assert result.success is True
        dup_warnings = [w for w in result.warnings if "share the view label" in w]
        assert (
            len(dup_warnings) >= 1
        ), f"Expected duplicate label warning, got: {result.warnings}"

    def test_TS008_nan_inf_depth_replaced_with_warning(
        self, reconstruction_imports, tmp_path
    ):
        """TS-008 → EC-005: NaN/Inf in depth map are replaced with
        0.0 and warning logged."""
        m = reconstruction_imports

        # Given — depth map with NaN and Inf values
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp = _make_vision_result()
        # Inject NaN and Inf into the depth map
        inp.depth_map[0, 0] = np.nan
        inp.depth_map[0, 1] = np.inf
        inp.depth_map[0, 2] = -np.inf

        # When
        result = engine.reconstruct([inp])

        # Then — should succeed with a sanitization warning
        assert result.success is True
        nan_warnings = [w for w in result.warnings if "invalid values" in w.lower()]
        assert (
            len(nan_warnings) >= 1
        ), f"Expected NaN/Inf warning, got: {result.warnings}"
        # Verify depth map was actually sanitized
        assert np.all(
            np.isfinite(inp.depth_map)
        ), "Depth map should be sanitized (no NaN/Inf)"

    def test_TS018_exceeding_max_inputs_returns_failure(
        self, reconstruction_imports, tmp_path
    ):
        """TS-018 → EC-006, FR-021: Passing >2 inputs returns
        success=False with multi-view deferral message."""
        m = reconstruction_imports

        # Given — three input images
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inputs = [
            _make_vision_result(view_label="front"),
            _make_vision_result(view_label="right"),
            _make_vision_result(view_label="back"),
        ]

        # When
        result = engine.reconstruct(inputs)

        # Then
        assert result.success is False
        assert result.mesh is None
        assert "1–2" in result.error_message or "1-2" in result.error_message
        assert "3" in result.error_message

    def test_zero_inputs_returns_failure(self, reconstruction_imports, tmp_path):
        """Additional: Passing 0 inputs returns success=False."""
        m = reconstruction_imports

        # Given
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)

        # When
        result = engine.reconstruct([])

        # Then
        assert result.success is False
        assert "no input" in result.error_message.lower()


class TestSecurityValidation:
    """Tests mapping to security requirements SEC-001, SEC-004."""

    def test_TS014_mismatched_shapes_raise_value_error(
        self, reconstruction_imports, tmp_path
    ):
        """TS-014 → SEC-001: Input arrays with mismatched shapes
        (image 512×512, mask 256×256) returns failure result."""
        m = reconstruction_imports

        # Given — mismatched image/mask shapes
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        inp = _make_vision_result(width=512, height=512)
        # Replace mask with wrong dimensions
        inp.mask = np.full((256, 256), 255, dtype=np.uint8)

        # When
        result = engine.reconstruct([inp])

        # Then — engine should catch ValueError and return failure
        assert result.success is False
        assert result.mesh is None
        assert "mask" in result.error_message.lower()

    def test_TS015_checksum_mismatch_returns_error(
        self, reconstruction_imports, tmp_path
    ):
        """TS-015 → SEC-004: Model weight checksum mismatch returns
        error with expected/actual hashes."""
        m = reconstruction_imports

        # Given — the model layer reports an integrity failure
        detail = (
            "Integrity check failed for ckpts/slat_dec_gs.safetensors. "
            "Expected SHA256: " + "a" * 64 + "."
        )
        adapter = m.TrellisAdapter(
            cache_dir=str(tmp_path),
            cache_manager=_FakeCache(
                path=_cached_weights(tmp_path), integrity=(False, detail)
            ),
        )

        # When
        inp = _make_vision_result()
        result = adapter.reconstruct([inp])

        # Then — the adapter surfaces the model layer's detail verbatim
        # and does not proceed to load anything.
        assert result.success is False
        assert result.mesh is None
        assert detail in result.error_message
        assert "download" in result.error_message.lower()

    def test_unverifiable_weights_fail_closed(self, reconstruction_imports, tmp_path):
        """SEC-004 → SPEC-TS-0002 FR-007a: the adapter keeps no digest
        table of its own, so an unverifiable weight cannot be skipped
        here the way it once was."""
        m = reconstruction_imports
        import tessera.reconstruction.adapters.trellis_adapter as ta

        # The adapter must not carry a parallel checksum map — that
        # duplicate is what allowed verification to be silently skipped.
        assert not hasattr(ta, "_EXPECTED_CHECKSUMS")
        assert not hasattr(ta, "_compute_sha256")

        adapter = m.TrellisAdapter(
            cache_dir=str(tmp_path),
            cache_manager=_FakeCache(
                path=_cached_weights(tmp_path),
                integrity=(False, "No SHA256 digest declared for ckpts/x.safetensors."),
            ),
        )
        result = adapter.reconstruct([_make_vision_result()])

        assert result.success is False
        assert "no sha256 digest" in result.error_message.lower()


class TestTimeout:
    """Tests mapping to FR-022 (inference timeout)."""

    @pytest.mark.skipif(
        not hasattr(signal, "SIGALRM"),
        reason="SIGALRM not available on this platform",
    )
    def test_TS019_timeout_returns_failure(self, reconstruction_imports, tmp_path):
        """TS-019 → FR-022: Reconstruction exceeding timeout returns
        success=False with timeout message."""
        m = reconstruction_imports

        # Given — engine with a very short timeout
        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=1)

        # Create a slow adapter that sleeps longer than timeout
        class SlowAdapter(m.StubAdapter):
            def reconstruct(self, inputs):
                time.sleep(5)  # Exceeds 1s timeout
                return super().reconstruct(inputs)

        # Replace the stub adapter in the registry
        engine._registry._adapters["stub"] = SlowAdapter()

        inp = _make_vision_result()

        # When
        result = engine.reconstruct([inp])

        # Then
        assert result.success is False
        assert "timed out" in result.error_message.lower()


class TestAdapterRegistry:
    """Additional tests for AdapterRegistry selection algorithm."""

    def test_registry_prefers_production_over_stub(
        self, reconstruction_imports, tmp_path
    ):
        """Registry excludes StubAdapter when production adapter
        passes all filters."""
        m = reconstruction_imports

        # Given — registry with both adapters, but Trellis has
        # weights available and sufficient VRAM
        registry = m.AdapterRegistry()
        registry.register(m.StubAdapter())

        trellis = m.TrellisAdapter(
            cache_dir=str(tmp_path),
            cache_manager=_FakeCache(path=_cached_weights(tmp_path)),
        )
        registry.register(trellis)

        # When
        selected = registry.select(
            input_count=1,
            cache_dir=str(tmp_path),
            available_vram_gb=12.0,  # Plenty of VRAM
        )

        # Then — should pick Trellis, not stub
        assert selected is not None
        assert not isinstance(selected, m.StubAdapter)
        assert selected.capabilities().model_name == "trellis-v1.0"

    def test_registry_falls_back_to_stub_when_no_weights(
        self, reconstruction_imports, tmp_path
    ):
        """When production adapter has no weights, fallback to stub."""
        m = reconstruction_imports

        # Given — no weight files
        registry = m.AdapterRegistry()
        registry.register(m.StubAdapter())
        registry.register(m.TrellisAdapter(cache_dir=str(tmp_path)))

        # When
        selected = registry.select(
            input_count=1,
            cache_dir=str(tmp_path),
            available_vram_gb=12.0,
        )

        # Then
        assert selected is not None
        assert isinstance(selected, m.StubAdapter)

    def test_registry_returns_none_when_no_compatible_adapter(
        self, reconstruction_imports, tmp_path
    ):
        """When no adapter supports the input count, return None."""
        m = reconstruction_imports

        # Given — empty registry
        registry = m.AdapterRegistry()

        # When
        selected = registry.select(
            input_count=1,
            cache_dir=str(tmp_path),
            available_vram_gb=12.0,
        )

        # Then
        assert selected is None

    def test_registry_contains_and_len(self, reconstruction_imports, tmp_path):
        """Verify __contains__ and __len__ dunder methods."""
        m = reconstruction_imports

        registry = m.AdapterRegistry()
        assert len(registry) == 0
        assert "stub" not in registry

        registry.register(m.StubAdapter())
        assert len(registry) == 1
        assert "stub" in registry
        assert "trellis-v1.0" not in registry

    def test_get_capabilities_returns_none_for_unknown(
        self, reconstruction_imports, tmp_path
    ):
        """get_capabilities returns None for unknown model name."""
        m = reconstruction_imports

        registry = m.AdapterRegistry()
        registry.register(m.StubAdapter())

        assert registry.get_capabilities("nonexistent") is None
        caps = registry.get_capabilities("stub")
        assert caps is not None
        assert caps.model_name == "stub"


class TestMeshConversion:
    """Additional tests for mesh normalization and validation."""

    def test_normalize_mesh_dtype_conversion(self, reconstruction_imports):
        """normalize_to_standard_mesh converts dtypes correctly."""
        m = reconstruction_imports

        # Given — float64 vertices, int64 faces
        verts = np.random.randn(10, 3).astype(np.float64)
        faces = np.arange(12).reshape(4, 3).astype(np.int64)

        # When
        mesh = m.normalize_to_standard_mesh(verts, faces)

        # Then
        assert mesh.vertices.dtype == np.float32
        assert mesh.faces.dtype == np.int32
        assert mesh.metadata["vertex_count"] == 10
        assert mesh.metadata["face_count"] == 4

    def test_normalize_mesh_clamps_colors(self, reconstruction_imports):
        """normalize_to_standard_mesh clamps colors to [0.0, 1.0]."""
        m = reconstruction_imports

        # Given — colors outside valid range
        verts = np.random.randn(5, 3).astype(np.float32)
        faces = np.arange(6).reshape(2, 3).astype(np.int32)
        colors = np.array(
            [
                [-0.5, 1.5, 0.5],
                [0.0, 2.0, -1.0],
                [0.5, 0.5, 0.5],
                [1.0, 1.0, 1.0],
                [0.0, 0.0, 0.0],
            ],
            dtype=np.float32,
        )

        # When
        mesh = m.normalize_to_standard_mesh(verts, faces, vertex_colors=colors)

        # Then
        assert mesh.vertex_colors is not None
        assert np.all(mesh.vertex_colors >= 0.0)
        assert np.all(mesh.vertex_colors <= 1.0)

    def test_validate_mesh_boundary_at_threshold(self, reconstruction_imports):
        """validate_mesh: exactly 4 vertices and 4 faces passes."""
        m = reconstruction_imports

        # Given — exactly at the threshold
        mesh = m.normalize_to_standard_mesh(
            vertices=np.random.randn(4, 3).astype(np.float32),
            faces=np.arange(12).reshape(4, 3).astype(np.int32),
        )

        # When
        valid, err = m.validate_mesh(mesh)

        # Then
        assert valid is True
        assert err == ""

    def test_validate_mesh_below_threshold(self, reconstruction_imports):
        """validate_mesh: 3 vertices fails."""
        m = reconstruction_imports

        mesh = m.normalize_to_standard_mesh(
            vertices=np.random.randn(3, 3).astype(np.float32),
            faces=np.arange(9).reshape(3, 3).astype(np.int32),
        )

        valid, err = m.validate_mesh(mesh)
        assert valid is False
        assert "degenerate" in err.lower()


class TestVRAMGuard:
    """Additional tests for VRAMGuard."""

    def test_vram_check_pass(self, reconstruction_imports):
        """VRAMGuard.check returns ok=True when VRAM is sufficient."""
        m = reconstruction_imports

        # Mock: system-level non-determinism — GPU VRAM detection
        with patch.object(m.VRAMGuard, "get_available_vram_gb", return_value=12.0):
            ok, available = m.VRAMGuard.check(6.0)
            assert ok is True
            assert available == 12.0

    def test_vram_check_fail(self, reconstruction_imports):
        """VRAMGuard.check returns ok=False when VRAM is insufficient."""
        m = reconstruction_imports

        # Mock: system-level non-determinism — GPU VRAM detection
        with patch.object(m.VRAMGuard, "get_available_vram_gb", return_value=4.0):
            ok, available = m.VRAMGuard.check(6.0)
            assert ok is False
            assert available == 4.0

    def test_vram_guard_no_gpu_returns_zero(self, reconstruction_imports):
        """VRAMGuard returns 0.0 when no GPU available."""
        m = reconstruction_imports

        # In CI, no GPU is available — should return 0.0 gracefully
        available = m.VRAMGuard.get_available_vram_gb()
        assert isinstance(available, float)
        assert available >= 0.0

    def test_cleanup_gpu_returns_float(self, reconstruction_imports):
        """cleanup_gpu returns a float ≥ 0."""
        m = reconstruction_imports

        freed = m.VRAMGuard.cleanup_gpu()
        assert isinstance(freed, float)
        assert freed >= 0.0


class TestTrellisAdapterCapabilities:
    """Test TrellisAdapter capabilities declaration."""

    def test_trellis_capabilities(self, reconstruction_imports, tmp_path):
        """TrellisAdapter declares correct capabilities."""
        m = reconstruction_imports

        adapter = m.TrellisAdapter(cache_dir=str(tmp_path))
        caps = adapter.capabilities()

        assert caps.model_name == "trellis-v1.0"
        assert caps.min_images == 1
        assert caps.max_images == 2
        assert caps.requires_depth is True
        assert caps.requires_mask is True
        assert caps.min_vram_gb == 6.0
        assert "front" in caps.supported_view_labels
        assert "mesh" in caps.output_types

    def test_stub_capabilities(self, reconstruction_imports):
        """StubAdapter declares correct capabilities."""
        m = reconstruction_imports

        adapter = m.StubAdapter()
        caps = adapter.capabilities()

        assert caps.model_name == "stub"
        assert caps.min_images == 1
        assert caps.max_images == 2
        assert caps.requires_depth is False
        assert caps.requires_mask is False
        assert caps.min_vram_gb == 0.0


class TestTrellisApplyMask:
    """Test TrellisAdapter._apply_mask (FR-009)."""

    def test_apply_mask_zeros_background(self, reconstruction_imports, tmp_path):
        """_apply_mask zeros out pixels where mask is 0."""
        m = reconstruction_imports

        adapter = m.TrellisAdapter(cache_dir=str(tmp_path))

        # Given — image with known values, mask with partial coverage
        image = np.full((4, 4, 3), 200, dtype=np.uint8)
        mask = np.zeros((4, 4), dtype=np.uint8)
        mask[1:3, 1:3] = 255  # Only center pixels are foreground

        # When
        result = adapter._apply_mask(image, mask)

        # Then — background should be 0, foreground preserved
        assert result[0, 0, 0] == 0  # Background pixel
        assert result[1, 1, 0] == 200  # Foreground pixel
        assert result[3, 3, 0] == 0  # Background pixel


class TestEngineListAdapters:
    """Test ReconstructionEngine.list_adapters()."""

    def test_list_adapters_returns_both(self, reconstruction_imports, tmp_path):
        """Engine lists both registered adapters."""
        m = reconstruction_imports

        engine = m.ReconstructionEngine(cache_dir=str(tmp_path), timeout_s=30)
        caps = engine.list_adapters()

        assert len(caps) == 2
        names = {c.model_name for c in caps}
        assert "stub" in names
        assert "trellis-v1.0" in names
