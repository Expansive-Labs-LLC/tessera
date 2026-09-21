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

"""Tests for the golden-mesh registry and deterministic hashing.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Covers: TS-005, TS-006, TS-011, TS-014, TS-018, TS-021, TS-029.

All ``bpy`` dependencies are mocked via conftest.py fixtures.
Imports from ``tessera.*`` are deferred to test body.
"""

from __future__ import annotations

import numpy as np
import pytest


# -------------------------------------------------------------------
# Sample mesh fixtures
# -------------------------------------------------------------------
@pytest.fixture
def cube_vertices() -> np.ndarray:
    """Unit cube vertices (8, 3)."""
    return np.array(
        [
            [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5],
            [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5],
            [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5],
            [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5],
        ],
        dtype=np.float64,
    )


@pytest.fixture
def cube_faces() -> np.ndarray:
    """Unit cube faces (12, 3)."""
    return np.array(
        [
            [0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
            [0, 4, 5], [0, 5, 1], [2, 6, 7], [2, 7, 3],
            [0, 3, 7], [0, 7, 4], [1, 5, 6], [1, 6, 2],
        ],
        dtype=np.int64,
    )


# -------------------------------------------------------------------
# TS-005: Deterministic mesh hashing
# -------------------------------------------------------------------
class TestMeshHash:
    """Test deterministic mesh hashing."""

    def test_identical_mesh_produces_same_hash(
        self, cube_vertices, cube_faces
    ) -> None:
        """Same vertices and faces → identical hash."""
        from tessera.testing.mesh_hash import compute_mesh_hash

        h1 = compute_mesh_hash(cube_vertices, cube_faces)
        h2 = compute_mesh_hash(cube_vertices.copy(), cube_faces.copy())
        assert h1 == h2

    def test_shuffled_vertices_produce_same_hash(
        self, cube_vertices, cube_faces
    ) -> None:
        """Shuffled vertex order → same hash (canonical sorting)."""
        from tessera.testing.mesh_hash import compute_mesh_hash

        shuffled = cube_vertices[::-1].copy()
        h_original = compute_mesh_hash(cube_vertices, cube_faces)
        h_shuffled = compute_mesh_hash(shuffled, cube_faces)
        assert h_original == h_shuffled

    def test_shuffled_faces_produce_same_hash(
        self, cube_vertices, cube_faces
    ) -> None:
        """Shuffled face order → same hash (canonical sorting)."""
        from tessera.testing.mesh_hash import compute_mesh_hash

        shuffled = cube_faces[::-1].copy()
        h_original = compute_mesh_hash(cube_vertices, cube_faces)
        h_shuffled = compute_mesh_hash(cube_vertices, shuffled)
        assert h_original == h_shuffled

    def test_different_mesh_produces_different_hash(
        self, cube_vertices, cube_faces
    ) -> None:
        """Modified vertices → different hash."""
        from tessera.testing.mesh_hash import compute_mesh_hash

        modified = cube_vertices.copy()
        modified[0, 0] += 1.0
        h_original = compute_mesh_hash(cube_vertices, cube_faces)
        h_modified = compute_mesh_hash(modified, cube_faces)
        assert h_original != h_modified

    def test_hash_format_is_vertex_colon_face(
        self, cube_vertices, cube_faces
    ) -> None:
        """Hash format: 'vertex_hash:face_hash'."""
        from tessera.testing.mesh_hash import compute_mesh_hash

        h = compute_mesh_hash(cube_vertices, cube_faces)
        parts = h.split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 64  # SHA-256 hex
        assert len(parts[1]) == 64

    def test_precision_rounding(self) -> None:
        """Tiny floating-point differences below precision are ignored."""
        from tessera.testing.mesh_hash import compute_mesh_hash

        v1 = np.array([[1.00001, 0.0, 0.0]], dtype=np.float64)
        v2 = np.array([[1.00002, 0.0, 0.0]], dtype=np.float64)
        f = np.array([[0]], dtype=np.int64)
        # Both round to [1.0000, 0.0, 0.0] at precision=4.
        h1 = compute_mesh_hash(v1, f, precision=4)
        h2 = compute_mesh_hash(v2, f, precision=4)
        assert h1 == h2


# -------------------------------------------------------------------
# TS-006: GoldenMeshRegistry create + load round trip
# -------------------------------------------------------------------
class TestGoldenMeshRegistry:
    """Test golden-mesh registry CRUD operations."""

    def test_create_and_load_reference(
        self, tmp_path, cube_vertices, cube_faces
    ) -> None:
        """create_reference → load_reference round trip."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        ref = registry.create_reference(
            "cube", cube_vertices, cube_faces, "unit cube"
        )
        loaded = registry.load_reference("cube")
        assert loaded is not None
        assert loaded.mesh_hash == ref.mesh_hash
        assert loaded.vertex_count == 8
        assert loaded.face_count == 12

    def test_list_references(
        self, tmp_path, cube_vertices, cube_faces
    ) -> None:
        """list_references() returns all saved reference names."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        registry.create_reference("cube", cube_vertices, cube_faces)
        registry.create_reference("cube2", cube_vertices, cube_faces)
        names = registry.list_references()
        assert "cube" in names
        assert "cube2" in names


# -------------------------------------------------------------------
# TS-011: Mesh comparison
# -------------------------------------------------------------------
class TestGoldenMeshComparison:
    """Test golden-mesh comparison logic."""

    def test_matching_mesh_returns_true(
        self, tmp_path, cube_vertices, cube_faces
    ) -> None:
        """Identical mesh matches the reference."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        registry.create_reference("cube", cube_vertices, cube_faces)
        match, detail = registry.compare("cube", cube_vertices, cube_faces)
        assert match is True
        assert "matches" in detail.lower()

    def test_different_mesh_returns_false(
        self, tmp_path, cube_vertices, cube_faces
    ) -> None:
        """Modified mesh does not match reference."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        registry.create_reference("cube", cube_vertices, cube_faces)
        modified = cube_vertices.copy()
        modified[0, 0] += 10.0
        match, detail = registry.compare("cube", modified, cube_faces)
        assert match is False


# -------------------------------------------------------------------
# TS-014: Missing reference handling (EC-002)
# -------------------------------------------------------------------
class TestMissingReference:
    """Test behavior with missing or corrupted references."""

    def test_load_missing_returns_none(self, tmp_path) -> None:
        """load_reference() returns None for missing file (EC-002)."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        result = registry.load_reference("nonexistent")
        assert result is None

    def test_compare_missing_returns_false(
        self, tmp_path, cube_vertices, cube_faces
    ) -> None:
        """compare() returns False for missing reference."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        match, detail = registry.compare("nonexistent", cube_vertices, cube_faces)
        assert match is False
        assert "not found" in detail.lower()


# -------------------------------------------------------------------
# TS-018: SEC-005 — np.load safety
# -------------------------------------------------------------------
class TestNpzSecurity:
    """Test secure .npz loading."""

    def test_corrupted_npz_returns_none(self, tmp_path) -> None:
        """Corrupted .npz file returns None gracefully."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        (tmp_path / "golden").mkdir(parents=True, exist_ok=True)
        corrupt_file = tmp_path / "golden" / "bad.npz"
        corrupt_file.write_bytes(b"not a valid npz file")
        result = registry.load_reference("bad")
        assert result is None


# -------------------------------------------------------------------
# TS-021: Secondary count comparison (EC-005)
# -------------------------------------------------------------------
class TestSecondaryComparison:
    """Test secondary vertex/face count comparison."""

    def test_count_mismatch_reported_in_detail(
        self, tmp_path, cube_vertices, cube_faces
    ) -> None:
        """Detail message reports count differences (EC-005)."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        registry.create_reference("cube", cube_vertices, cube_faces)

        extra_v = np.vstack([cube_vertices, [[0.0, 0.0, 0.0]]])
        extra_f = np.vstack([cube_faces, [[0, 1, 8]]])
        match, detail = registry.compare("cube", extra_v, extra_f)
        assert match is False
        assert "Vertex count" in detail or "Face count" in detail

    def test_same_counts_but_different_positions(
        self, tmp_path, cube_vertices, cube_faces
    ) -> None:
        """Same counts but different values → reports positions differ."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        registry.create_reference("cube", cube_vertices, cube_faces)

        modified = cube_vertices.copy()
        modified[0] = [99.0, 99.0, 99.0]
        match, detail = registry.compare("cube", modified, cube_faces)
        assert match is False
        assert "positions" in detail.lower() or "winding" in detail.lower()


# -------------------------------------------------------------------
# TS-029: Bounding box in reference
# -------------------------------------------------------------------
class TestBoundingBox:
    """Test bounding box metadata in references."""

    def test_bounding_box_stored(
        self, tmp_path, cube_vertices, cube_faces
    ) -> None:
        """Reference stores correct bounding box."""
        from tessera.testing.golden_mesh import GoldenMeshRegistry

        registry = GoldenMeshRegistry(tmp_path / "golden")
        ref = registry.create_reference("cube", cube_vertices, cube_faces)
        assert ref.bounding_box[0] == pytest.approx((-0.5, -0.5, -0.5))
        assert ref.bounding_box[1] == pytest.approx((0.5, 0.5, 0.5))
