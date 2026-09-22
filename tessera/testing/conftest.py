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

"""Pytest fixtures for golden-mesh regression testing.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-028.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def golden_mesh_dir(tmp_path: Path) -> Path:
    """Temporary directory for golden-mesh reference files.

    Returns:
        Path to the temporary golden-mesh directory.
    """
    d = tmp_path / "golden_meshes"
    d.mkdir()
    return d


@pytest.fixture
def sample_cube_vertices() -> np.ndarray:
    """Vertices of a unit cube centered at origin.

    Returns:
        Array of shape ``(8, 3)``.
    """
    return np.array(
        [
            [-0.5, -0.5, -0.5],
            [0.5, -0.5, -0.5],
            [0.5, 0.5, -0.5],
            [-0.5, 0.5, -0.5],
            [-0.5, -0.5, 0.5],
            [0.5, -0.5, 0.5],
            [0.5, 0.5, 0.5],
            [-0.5, 0.5, 0.5],
        ],
        dtype=np.float64,
    )


@pytest.fixture
def sample_cube_faces() -> np.ndarray:
    """Faces of a unit cube (6 quads as triangulated tris).

    Returns:
        Array of shape ``(12, 3)``.
    """
    return np.array(
        [
            [0, 1, 2],
            [0, 2, 3],  # bottom
            [4, 6, 5],
            [4, 7, 6],  # top
            [0, 4, 5],
            [0, 5, 1],  # front
            [2, 6, 7],
            [2, 7, 3],  # back
            [0, 3, 7],
            [0, 7, 4],  # left
            [1, 5, 6],
            [1, 6, 2],  # right
        ],
        dtype=np.int64,
    )


@pytest.fixture
def sample_sphere_vertices() -> np.ndarray:
    """Vertices of a simple UV sphere (low-poly, 42 verts).

    Returns:
        Array of shape ``(42, 3)``.
    """
    verts = []
    n_segments = 8
    n_rings = 4

    # Top pole.
    verts.append([0.0, 0.0, 1.0])

    # Rings.
    for i in range(1, n_rings + 1):
        phi = np.pi * i / (n_rings + 1)
        z = np.cos(phi)
        r = np.sin(phi)
        for j in range(n_segments):
            theta = 2.0 * np.pi * j / n_segments
            x = r * np.cos(theta)
            y = r * np.sin(theta)
            verts.append([x, y, z])

    # Bottom pole.
    verts.append([0.0, 0.0, -1.0])

    return np.array(verts, dtype=np.float64)


@pytest.fixture
def sample_sphere_faces() -> np.ndarray:
    """Faces of a simple UV sphere matching the sample vertices.

    Returns:
        Array of shape ``(M, 3)``.
    """
    faces = []
    n_segments = 8

    # Top cap.
    for j in range(n_segments):
        faces.append([0, 1 + j, 1 + (j + 1) % n_segments])

    # Middle quads (as tris).
    for i in range(3):  # n_rings - 1
        for j in range(n_segments):
            curr = 1 + i * n_segments + j
            next_j = 1 + i * n_segments + (j + 1) % n_segments
            below = curr + n_segments
            below_next = next_j + n_segments
            faces.append([curr, below, below_next])
            faces.append([curr, below_next, next_j])

    # Bottom cap.
    bottom = 1 + 4 * n_segments
    last_ring_start = 1 + 3 * n_segments
    for j in range(n_segments):
        faces.append(
            [bottom, last_ring_start + (j + 1) % n_segments, last_ring_start + j]
        )

    return np.array(faces, dtype=np.int64)
