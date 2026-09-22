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

"""Data types for the Tessera mesh cleanup pipeline.

Defines the raw mesh input container and cleanup diagnostics
structure used throughout the pipeline.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: §3.4 Input Specifications, FR-007.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np

# SEC-005: Shared regex for allowed source_model characters.
# Characters not matching [a-zA-Z0-9_-] are replaced with '_'.
# Used by both MeshImporter and hierarchy helpers.
SOURCE_MODEL_RE = re.compile(r"[^a-zA-Z0-9_-]")


@dataclass
class RawMeshData:
    """Raw mesh data from a reconstruction engine.

    Container for the NumPy arrays produced by reconstruction
    adapters.  Passed to ``MeshImporter.import_mesh()`` for
    conversion into a Blender mesh object.

    Attributes:
        vertices: Vertex positions, shape ``(N, 3)`` float32.
        faces: Triangle face indices, shape ``(M, 3)`` int32.
        source_model: Reconstruction model identifier.  Well-known
            values: ``"trellis"``, ``"instantmesh"``, ``"openlrm"``,
            ``"zero123"``, ``"custom"``.  Any alphanumeric string
            with hyphens/underscores (≤ 32 chars) is accepted;
            SEC-005 sanitization is applied by the importer.

    Implements: §3.4.
    """

    vertices: np.ndarray  # Shape (N, 3), dtype float32
    faces: np.ndarray  # Shape (M, 3), dtype int32
    source_model: str = "custom"


# Diagnostics key names defined by FR-007.
DIAGNOSTICS_KEYS: list[str] = [
    "vertices_before",
    "vertices_after",
    "faces_before",
    "faces_after",
    "doubles_removed",
    "degenerate_faces_removed",
    "normals_flipped",
    "holes_filled",
    "holes_skipped",
    "voxel_remesh_applied",
    "quad_remesh_applied",
    "decimate_applied",
    "is_manifold",
    "is_watertight",
    "cleanup_time_seconds",
]


def empty_diagnostics() -> dict[str, Any]:
    """Return a diagnostics dict pre-filled with default values.

    Contains all 15 keys from FR-007 plus the ``step_errors`` list.

    Returns:
        A dict with integer keys defaulting to ``0``, boolean keys
        to ``False``, float keys to ``0.0``, and ``step_errors``
        as an empty list.

    Implements: FR-007.
    """
    return {
        "vertices_before": 0,
        "vertices_after": 0,
        "faces_before": 0,
        "faces_after": 0,
        "doubles_removed": 0,
        "degenerate_faces_removed": 0,
        "normals_flipped": 0,
        "holes_filled": 0,
        "holes_skipped": 0,
        "voxel_remesh_applied": False,
        "quad_remesh_applied": False,
        "decimate_applied": False,
        "is_manifold": False,
        "is_watertight": False,
        "cleanup_time_seconds": 0.0,
        "step_errors": [],
    }
