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

"""Mesh conversion and validation utilities.

Provides helpers to normalise model-specific mesh representations
into the ``StandardMesh`` format and to validate output meshes
against the degenerate-mesh threshold.

Spec: SPEC-TS-0004 (Single-Image 3D Reconstruction Engine)

Public API:
    normalize_to_standard_mesh — wrap arrays into StandardMesh (FR-010)
    validate_mesh — check degenerate mesh threshold (FR-011)
"""

from __future__ import annotations

import logging

import numpy as np

from ...reconstruction.mesh_output import StandardMesh

logger = logging.getLogger("tessera.reconstruction")

# FR-011: Minimum vertex and face counts.
MIN_VERTICES = 4
MIN_FACES = 4


def normalize_to_standard_mesh(
    vertices: np.ndarray,
    faces: np.ndarray,
    vertex_colors: np.ndarray | None = None,
    metadata: dict | None = None,
) -> StandardMesh:
    """Normalise raw mesh data into a ``StandardMesh``.

    Ensures correct dtypes and populates vertex/face counts in
    metadata.

    Args:
        vertices: Vertex positions, shape ``(N, 3)``.
        faces: Triangle face indices, shape ``(M, 3)``.
        vertex_colors: Per-vertex RGB colours, shape ``(N, 3)``,
            range ``[0.0, 1.0]``.  ``None`` if unavailable.
        metadata: Optional metadata dict.  Missing keys are filled
            with defaults.

    Returns:
        StandardMesh with normalised arrays and complete metadata.

    Implements: FR-010.
    """
    # Ensure correct dtypes
    verts = np.asarray(vertices, dtype=np.float32)
    fcs = np.asarray(faces, dtype=np.int32)

    colors = None
    if vertex_colors is not None:
        colors = np.asarray(vertex_colors, dtype=np.float32)
        # Clamp colour values to [0.0, 1.0]
        colors = np.clip(colors, 0.0, 1.0)

    # Build metadata with defaults
    meta = {
        "model_name": "",
        "inference_time_s": 0.0,
        "confidence": 0.0,
        "vertex_count": 0,
        "face_count": 0,
    }
    if metadata:
        meta.update(metadata)

    # Always set vertex/face counts from the actual arrays
    meta["vertex_count"] = int(verts.shape[0])
    meta["face_count"] = int(fcs.shape[0])

    return StandardMesh(
        vertices=verts,
        faces=fcs,
        vertex_colors=colors,
        metadata=meta,
    )


def validate_mesh(mesh: StandardMesh) -> tuple[bool, str]:
    """Validate that a mesh is not degenerate.

    A mesh is degenerate if it has fewer than 4 vertices or fewer
    than 4 faces.

    Args:
        mesh: The mesh to validate.

    Returns:
        Tuple of ``(valid, error_message)``.  ``error_message`` is
        empty when valid.

    Implements: FR-011.
    """
    vertex_count = mesh.vertices.shape[0] if mesh.vertices.ndim >= 1 else 0
    face_count = mesh.faces.shape[0] if mesh.faces.ndim >= 1 else 0

    if vertex_count < MIN_VERTICES or face_count < MIN_FACES:
        msg = (
            "Reconstruction produced degenerate mesh with fewer than "
            f"{MIN_VERTICES} vertices or {MIN_FACES} faces."
        )
        logger.error(
            "Degenerate mesh: %d vertices, %d faces",
            vertex_count,
            face_count,
        )
        return False, msg

    return True, ""
