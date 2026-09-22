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

"""Mesh importer — converts raw NumPy arrays into Blender objects.

Accepts vertex/face arrays from the reconstruction engine and creates
a new ``bpy.types.Object`` in the active Blender scene.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-001, FR-002, SEC-001, SEC-002, SEC-005, CON-003,
    CON-006, EC-003, EC-005.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

import bpy
import numpy as np

from .data_types import SOURCE_MODEL_RE

logger = logging.getLogger("tessera.mesh")

# EC-003: Minimum mesh requirements for a closed volume.
_MIN_VERTICES = 4
_MIN_FACES = 4

# SEC-005: Maximum source_model string length.
_MAX_SOURCE_MODEL_LEN = 32


class MeshImporter:
    """Imports raw mesh data into the active Blender scene.

    Validates input arrays, creates a ``bpy.types.Mesh`` data block
    populated via the ``bmesh`` API (CON-006), and returns the
    resulting ``bpy.types.Object`` placed at the scene's 3D cursor.

    Implements: FR-001, FR-002, SEC-001, SEC-002, SEC-005, CON-003,
        CON-006, EC-003, EC-005.
    """

    def import_mesh(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        source_model: str = "custom",
        name_override: str | None = None,
    ) -> "bpy.types.Object":
        """Import raw mesh data into the active Blender scene.

        Args:
            vertices: Vertex positions, shape ``(N, 3)`` float32.
            faces: Triangle face indices, shape ``(M, 3)`` int32.
            source_model: Reconstruction model identifier (default
                ``"custom"``).  Sanitized per SEC-005.
            name_override: If provided, overrides the auto-generated
                object name.

        Returns:
            The newly created ``bpy.types.Object`` in the active scene.

        Raises:
            ValueError: If input validation fails (shape, dtype,
                NaN/Inf, face bounds, minimum mesh size).

        Implements: FR-001, FR-002.
        """
        start_time = time.perf_counter()

        # --- Input validation ---
        self._validate_vertices(vertices)
        self._validate_faces(faces, len(vertices))
        sanitized_source = self._sanitize_source_model(source_model)

        # CON-003: Operate on copies — never mutate the original arrays.
        verts = vertices.copy()
        face_indices = faces.copy()

        # --- Determine object name (FR-002) ---
        if name_override:
            obj_name = name_override
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            obj_name = f"Tessera_{timestamp}"

        # §11.1: Log import started before mesh operations.
        logger.info(
            "Mesh import started: vertex_count=%d, face_count=%d, " "source_model=%s",
            len(verts),
            len(face_indices),
            sanitized_source,
        )

        # --- Create mesh data block via foreach_set (CON-006) ---
        # foreach_set accepts flat C-contiguous arrays directly from
        # NumPy, avoiding the O(N) Python list/tuple construction
        # overhead that from_pydata(tolist()) incurs for large meshes.
        mesh_data = bpy.data.meshes.new(name=obj_name)
        try:
            n_verts = len(verts)
            n_faces = len(face_indices)

            mesh_data.vertices.add(n_verts)
            mesh_data.vertices.foreach_set("co", verts.ravel().astype(float))

            mesh_data.loops.add(n_faces * 3)
            mesh_data.loops.foreach_set(
                "vertex_index",
                face_indices.ravel().astype(int),
            )

            mesh_data.polygons.add(n_faces)
            mesh_data.polygons.foreach_set(
                "loop_start",
                [i * 3 for i in range(n_faces)],
            )
            mesh_data.polygons.foreach_set("loop_total", [3] * n_faces)

            mesh_data.update()
            mesh_data.validate()
        except (AttributeError, TypeError):
            # Fallback to from_pydata for compatibility with mock
            # environments or older Blender builds where foreach_set
            # is unavailable on mesh elements.
            mesh_data = bpy.data.meshes.new(name=obj_name)
            mesh_data.from_pydata(verts.tolist(), [], face_indices.tolist())
            mesh_data.update()

        # --- Create object and link to scene ---
        obj = bpy.data.objects.new(name=obj_name, object_data=mesh_data)
        collection = bpy.context.collection
        collection.objects.link(obj)

        # FR-002: Place at the scene's 3D cursor location.
        obj.location = bpy.context.scene.cursor.location.copy()

        # Select and make active
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        elapsed = time.perf_counter() - start_time

        # §11.1: Log import completed.
        logger.info(
            "Mesh import completed: object_name=%s, import_time_seconds=%.3f",
            obj_name,
            elapsed,
        )

        return obj

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_vertices(vertices: np.ndarray) -> None:
        """Validate the vertices array.

        Checks shape, dtype, NaN/Inf values, and minimum vertex count.

        Args:
            vertices: Array to validate.

        Raises:
            ValueError: On any validation failure.

        Implements: SEC-001, EC-003.
        """
        if not isinstance(vertices, np.ndarray):
            raise ValueError(
                f"vertices must be a numpy array, got {type(vertices).__name__}"
            )

        if vertices.ndim != 2 or vertices.shape[1] != 3:
            raise ValueError(f"vertices must have shape (N, 3), got {vertices.shape}")

        if vertices.dtype != np.float32:
            raise ValueError(f"vertices dtype must be float32, got {vertices.dtype}")

        # SEC-001: Reject NaN / Inf values.
        if np.any(np.isnan(vertices)):
            raise ValueError("vertices array contains NaN values")
        if np.any(np.isinf(vertices)):
            raise ValueError("vertices array contains Inf values")

        # EC-003: Minimum mesh requirements.
        if len(vertices) < _MIN_VERTICES:
            raise ValueError(
                f"Input mesh must contain at least {_MIN_VERTICES} vertices "
                f"and {_MIN_FACES} faces to form a closed volume. "
                f"Received {len(vertices)} vertices and unknown faces."
            )

    @staticmethod
    def _validate_faces(faces: np.ndarray, vertex_count: int) -> None:
        """Validate the faces array.

        Checks shape, dtype, column count, minimum face count, and
        index bounds.

        Args:
            faces: Array to validate.
            vertex_count: Number of vertices (for bounds checking).

        Raises:
            ValueError: On any validation failure.

        Implements: SEC-001, SEC-002, EC-003, EC-005.
        """
        if not isinstance(faces, np.ndarray):
            raise ValueError(f"faces must be a numpy array, got {type(faces).__name__}")

        # EC-005: Must be triangular.
        if faces.ndim != 2 or faces.shape[1] != 3:
            raise ValueError(
                f"Input faces must be triangular (shape (M, 3)). "
                f"Received shape {faces.shape}."
            )

        if faces.dtype != np.int32:
            raise ValueError(f"faces dtype must be int32, got {faces.dtype}")

        # EC-003: Minimum mesh requirements.
        if len(faces) < _MIN_FACES:
            raise ValueError(
                f"Input mesh must contain at least {_MIN_VERTICES} vertices "
                f"and {_MIN_FACES} faces to form a closed volume. "
                f"Received {vertex_count} vertices and {len(faces)} faces."
            )

        # SEC-002: Face index bounds check.
        if np.any(faces < 0) or np.any(faces >= vertex_count):
            raise ValueError(
                f"Face indices must be in range [0, {vertex_count - 1}]. "
                f"Found values outside this range."
            )

    @staticmethod
    def _sanitize_source_model(source_model: str) -> str:
        """Sanitize the source_model string per SEC-005.

        Replaces characters not matching ``[a-zA-Z0-9_-]`` with ``_``
        and truncates to 32 characters.

        Args:
            source_model: Raw source model identifier.

        Returns:
            Sanitized string safe for use in Blender object names.

        Implements: SEC-005.
        """
        sanitized = SOURCE_MODEL_RE.sub("_", source_model)
        return sanitized[:_MAX_SOURCE_MODEL_LEN]
