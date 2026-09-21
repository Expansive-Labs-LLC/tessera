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

"""Deterministic mesh hashing for golden-mesh comparison.

Produces a canonical SHA-256 hash from mesh vertex and face data.
Vertices are sorted by (x, y, z) at 4 decimal precision. Faces
are normalized by rotating per-face indices to smallest-first, then
sorted lexicographically.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-024.
"""

from __future__ import annotations

import hashlib
from typing import Union

import numpy as np


def compute_mesh_hash(
    vertices: Union[np.ndarray, list[list[float]]],
    faces: Union[np.ndarray, list[list[int]]],
    precision: int = 4,
) -> str:
    """Compute a deterministic hash for a mesh.

    Uses canonical ordering and fixed decimal precision to ensure
    identical meshes always produce the same hash, regardless of
    vertex/face storage order.

    Algorithm:
        1. Round vertices to ``precision`` decimal places.
        2. Sort vertices by (x, y, z) lexicographically.
        3. For each face, rotate vertex indices so the smallest
           index is first (canonical rotation).
        4. Sort faces lexicographically.
        5. Concatenate vertex hash + face hash (SHA-256).

    Args:
        vertices: Array of shape ``(N, 3)`` — vertex positions.
        faces: Array of shape ``(M, K)`` — face vertex indices.
        precision: Number of decimal places for vertex rounding.

    Returns:
        Hex string of the form ``"vertex_hash:face_hash"`` where
        each hash is a SHA-256 hex digest.

    Implements: FR-024.
    """
    verts = np.asarray(vertices, dtype=np.float64)
    face_arr = np.asarray(faces, dtype=np.int64)

    # Step 1: Round vertices to fixed precision.
    verts = np.round(verts, decimals=precision)

    # Step 2: Sort vertices by (x, y, z).
    sort_order = np.lexsort((verts[:, 2], verts[:, 1], verts[:, 0]))
    sorted_verts = verts[sort_order]

    # Step 3: Canonical face rotation — rotate each face so that
    # the smallest index comes first.
    canonical_faces = []
    for face in face_arr:
        face_list = face.tolist()
        min_idx = face_list.index(min(face_list))
        rotated = face_list[min_idx:] + face_list[:min_idx]
        canonical_faces.append(tuple(rotated))

    # Step 4: Sort faces lexicographically.
    canonical_faces.sort()

    # Step 5: Hash.
    vertex_hash = hashlib.sha256(sorted_verts.tobytes()).hexdigest()
    face_bytes = str(canonical_faces).encode("utf-8")
    face_hash = hashlib.sha256(face_bytes).hexdigest()

    return f"{vertex_hash}:{face_hash}"
