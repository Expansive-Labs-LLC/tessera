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

"""Golden-mesh registry for reference mesh storage and comparison.

Stores reference mesh data as ``.npz`` files with vertex/face hashes,
topology metadata, and bounding box dimensions. Used by the
regression test suite to detect unintended geometry changes.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-025, FR-026, FR-027, FR-028, SEC-005, EC-002, EC-005.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np

from .mesh_hash import compute_mesh_hash

logger = logging.getLogger("tessera.testing")


@dataclass
class GoldenMeshReference:
    """A golden-mesh reference entry.

    Attributes:
        name: Descriptive name of the reference mesh.
        mesh_hash: Deterministic hash from ``compute_mesh_hash()``.
        vertex_count: Number of vertices.
        face_count: Number of faces.
        bounding_box: (min_corner, max_corner) as 3D vectors.
        source_description: Description of how this reference was
            generated (e.g., ``"cube via bpy.ops.mesh.primitive_cube_add"``).
    """

    name: str
    mesh_hash: str
    vertex_count: int
    face_count: int
    bounding_box: tuple[tuple[float, float, float], tuple[float, float, float]]
    source_description: str = ""


class GoldenMeshRegistry:
    """Manages golden-mesh reference files for regression testing.

    Reference meshes are stored as ``.npz`` files in a specified
    directory. The registry supports creating new references from
    mesh data and loading existing references for comparison.

    File format (per mesh):
        - ``vertex_hash``: SHA-256 of canonical vertex data
        - ``face_hash``: SHA-256 of canonical face data
        - ``vertex_count``: int
        - ``face_count``: int
        - ``bbox_min``: float64[3]
        - ``bbox_max``: float64[3]
        - ``source_description``: str

    Implements: FR-025, FR-026, FR-027, SEC-005, EC-002, EC-005.
    """

    def __init__(self, registry_dir: Union[str, Path]) -> None:
        """Initialize the registry.

        Args:
            registry_dir: Directory where ``.npz`` reference files
                are stored.
        """
        self._dir = Path(registry_dir)

    @property
    def registry_dir(self) -> Path:
        """Path to the registry directory."""
        return self._dir

    def create_reference(
        self,
        name: str,
        vertices: np.ndarray,
        faces: np.ndarray,
        source_description: str = "",
    ) -> GoldenMeshReference:
        """Create a new golden-mesh reference file.

        Computes the deterministic mesh hash, extracts topology
        metadata, and saves all data to ``{name}.npz``.

        Args:
            name: Descriptive name (used as filename stem).
            vertices: Array of shape ``(N, 3)`` — vertex positions.
            faces: Array of shape ``(M, K)`` — face vertex indices.
            source_description: How this reference was generated.

        Returns:
            ``GoldenMeshReference`` with the computed metadata.

        Implements: FR-025.
        """
        self._dir.mkdir(parents=True, exist_ok=True)

        mesh_hash = compute_mesh_hash(vertices, faces)
        vertex_hash, face_hash = mesh_hash.split(":")

        bbox_min = vertices.min(axis=0).tolist()
        bbox_max = vertices.max(axis=0).tolist()

        filepath = self._dir / f"{name}.npz"
        np.savez(
            filepath,
            vertex_hash=np.array([vertex_hash]),
            face_hash=np.array([face_hash]),
            vertex_count=np.array([len(vertices)]),
            face_count=np.array([len(faces)]),
            bbox_min=np.array(bbox_min, dtype=np.float64),
            bbox_max=np.array(bbox_max, dtype=np.float64),
            source_description=np.array([source_description]),
        )

        logger.info(
            "Golden-mesh reference created: name=%s, vertices=%d, "
            "faces=%d, file=%s",
            name,
            len(vertices),
            len(faces),
            filepath.name,
        )

        ref = GoldenMeshReference(
            name=name,
            mesh_hash=mesh_hash,
            vertex_count=len(vertices),
            face_count=len(faces),
            bounding_box=(tuple(bbox_min), tuple(bbox_max)),
            source_description=source_description,
        )
        return ref

    def load_reference(self, name: str) -> Optional[GoldenMeshReference]:
        """Load a golden-mesh reference from disk.

        SEC-005: Uses ``np.load(allow_pickle=False)`` to prevent
        arbitrary code execution from malicious ``.npz`` files.

        Args:
            name: Reference name (filename stem without .npz).

        Returns:
            ``GoldenMeshReference`` if found and valid,
            ``None`` if missing or corrupted.

        Implements: FR-026, SEC-005, EC-002.
        """
        filepath = self._dir / f"{name}.npz"

        if not filepath.exists():
            logger.error(
                "Golden-mesh reference not found: name=%s, path=%s",
                name,
                filepath.name,
            )
            return None

        try:
            # SEC-005: Prevent pickle-based attacks.
            data = np.load(filepath, allow_pickle=False)

            vertex_hash = str(data["vertex_hash"][0])
            face_hash = str(data["face_hash"][0])
            vertex_count = int(data["vertex_count"][0])
            face_count = int(data["face_count"][0])
            bbox_min = tuple(data["bbox_min"].tolist())
            bbox_max = tuple(data["bbox_max"].tolist())
            source_description = str(data["source_description"][0])

            return GoldenMeshReference(
                name=name,
                mesh_hash=f"{vertex_hash}:{face_hash}",
                vertex_count=vertex_count,
                face_count=face_count,
                bounding_box=(bbox_min, bbox_max),
                source_description=source_description,
            )

        except Exception as exc:
            logger.error(
                "Golden-mesh reference corrupted: name=%s, error=%s",
                name,
                str(exc),
            )
            return None

    def compare(
        self,
        name: str,
        vertices: np.ndarray,
        faces: np.ndarray,
    ) -> tuple[bool, str]:
        """Compare a mesh against its golden reference.

        First checks the deterministic hash. If the hash matches,
        the mesh is identical. If the hash differs, performs a
        secondary vertex/face count comparison (EC-005) to provide
        more diagnostic information.

        Args:
            name: Golden-mesh reference name.
            vertices: Array of shape ``(N, 3)`` — vertex positions.
            faces: Array of shape ``(M, K)`` — face vertex indices.

        Returns:
            Tuple of (match: bool, detail: str). ``match`` is
            ``True`` if the mesh matches the reference. ``detail``
            explains the comparison result.

        Implements: FR-027, EC-005.
        """
        ref = self.load_reference(name)
        if ref is None:
            return False, f"Reference '{name}' not found or corrupted."

        current_hash = compute_mesh_hash(vertices, faces)

        if current_hash == ref.mesh_hash:
            return True, "Mesh matches golden reference exactly."

        # EC-005: Secondary vertex/face count comparison.
        vc = len(vertices)
        fc = len(faces)

        detail_parts = [f"Hash mismatch for '{name}'."]
        if vc != ref.vertex_count:
            detail_parts.append(
                f"Vertex count: expected {ref.vertex_count}, got {vc}."
            )
        if fc != ref.face_count:
            detail_parts.append(
                f"Face count: expected {ref.face_count}, got {fc}."
            )
        if vc == ref.vertex_count and fc == ref.face_count:
            detail_parts.append(
                "Counts match but vertex positions or face winding differ."
            )

        return False, " ".join(detail_parts)

    def list_references(self) -> list[str]:
        """List all available golden-mesh reference names.

        Returns:
            List of reference name strings (without ``.npz``).
        """
        if not self._dir.exists():
            return []
        return sorted(
            p.stem for p in self._dir.glob("*.npz")
        )
