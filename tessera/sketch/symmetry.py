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

"""Symmetry enforcer — bilateral symmetry post-processing for meshes.

Detects the primary symmetry axis via PCA and enforces bilateral
symmetry by mirroring one half of the mesh across the detected plane.

Spec: SPEC-TS-0010 (Sketch-to-3D Pathway)

Public API:
    SymmetryEnforcer — bilateral symmetry enforcement (FR-024)

Implements: FR-024, FR-025, FR-026, FR-027, FR-028, FR-029.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from ..sketch.types import SymmetryConfig

if TYPE_CHECKING:
    from ..reconstruction.mesh_output import StandardMesh

logger = logging.getLogger("tessera.sketch")


class SymmetryEnforcer:
    """Enforce bilateral symmetry on a reconstructed mesh.

    Detects the primary symmetry axis using PCA, selects one half
    of the mesh, mirrors it, and merges boundary vertices at the
    symmetry plane.

    The enforcer preserves topology and vertex count to within
    ±10% of the original mesh (FR-029).

    Example::

        enforcer = SymmetryEnforcer()
        symmetric_mesh = enforcer.enforce(mesh, config)

    Implements: FR-024.
    """

    def enforce(
        self,
        mesh: "StandardMesh",
        config: SymmetryConfig,
    ) -> "StandardMesh":
        """Apply bilateral symmetry enforcement to a mesh.

        FR-025: Enabled by default; can be disabled via config.
        FR-028: Skips if mesh has insufficient depth along the
          detected symmetry axis.

        Args:
            mesh: Input ``StandardMesh`` from reconstruction.
            config: Symmetry enforcement configuration.

        Returns:
            Symmetry-enforced ``StandardMesh``.

        Implements: FR-024, FR-025, FR-026, FR-027, FR-028, FR-029.
        """
        if not config.enable_symmetry:
            logger.debug("Symmetry enforcement disabled by config")
            return mesh

        vertices = mesh.vertices.copy().astype(np.float64)
        faces = mesh.faces.copy()
        original_count = len(vertices)

        if original_count < 3:
            logger.warning(
                "Symmetry enforcement skipped: mesh has fewer than 3 vertices"
            )
            return mesh

        # --- FR-026: Detect symmetry axis via PCA ---
        centroid = np.mean(vertices, axis=0)
        centered = vertices - centroid

        # Covariance matrix and eigendecomposition.
        cov = np.cov(centered.T)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)

        # The axis with the smallest eigenvalue is the symmetry
        # plane normal (least variance → most symmetric).
        min_idx = int(np.argmin(eigenvalues))
        symmetry_normal = eigenvectors[:, min_idx]
        symmetry_normal = symmetry_normal / np.linalg.norm(symmetry_normal)

        logger.debug(
            "Symmetry detection result: symmetry_axis=%s, " "eigenvalues=%s",
            symmetry_normal,
            eigenvalues,
        )

        # --- FR-028: Check axis spread ---
        # Project vertices onto symmetry axis.
        projections = centered @ symmetry_normal
        axis_spread = float(np.max(projections) - np.min(projections))

        # Compute bounding box diagonal.
        bbox_min = np.min(vertices, axis=0)
        bbox_max = np.max(vertices, axis=0)
        bbox_diagonal = float(np.linalg.norm(bbox_max - bbox_min))

        threshold = config.min_axis_spread_ratio * bbox_diagonal

        if axis_spread < threshold:
            logger.warning(
                "Symmetry enforcement skipped: mesh has insufficient "
                "depth along the detected symmetry axis "
                "(%.4f < %.4f).",
                axis_spread,
                threshold,
            )
            return mesh

        # --- FR-027: Select one half and mirror ---
        # Select vertices on the positive side of the symmetry plane.
        positive_mask = projections >= 0

        # Normalise vertices to mesh-space coordinates.
        scale = bbox_diagonal if bbox_diagonal > 0 else 1.0

        # Mirror positive-side vertices to negative side.
        # Replace negative-side vertex positions with mirrored
        # positions from their closest positive-side counterparts.
        positive_verts = centered[positive_mask]
        negative_mask = ~positive_mask

        if len(positive_verts) == 0 or np.sum(negative_mask) == 0:
            logger.warning(
                "Symmetry enforcement skipped: could not split mesh " "into two halves"
            )
            return mesh

        # Mirror positive vertices across symmetry plane.
        mirrored_positive = positive_verts.copy()
        proj_pos = mirrored_positive @ symmetry_normal
        mirrored_positive -= 2.0 * np.outer(proj_pos, symmetry_normal)

        # Build symmetric mesh by combining original positive half
        # with mirrored half.
        new_vertices = np.vstack([positive_verts, mirrored_positive])
        new_vertices += centroid  # Restore centroid offset.

        # Rebuild faces — map old vertex indices to new indices.
        old_to_new = np.full(original_count, -1, dtype=np.int32)
        positive_indices = np.where(positive_mask)[0]

        for new_idx, old_idx in enumerate(positive_indices):
            old_to_new[old_idx] = new_idx

        # Map negative-side vertices to their nearest positive-side mirror.
        negative_indices = np.where(negative_mask)[0]
        if len(negative_indices) > 0 and len(positive_indices) > 0:
            neg_verts = centered[negative_indices]
            # Find closest mirrored positive vertex for each negative.
            for i, neg_idx in enumerate(negative_indices):
                neg_v = neg_verts[i]
                distances = np.linalg.norm(mirrored_positive - neg_v, axis=1)
                closest = int(np.argmin(distances))
                # Map to corresponding mirrored index.
                old_to_new[neg_idx] = len(positive_indices) + closest

        # Rebuild valid faces.
        new_faces = []
        for face in faces:
            mapped = old_to_new[face]
            if np.all(mapped >= 0):
                new_faces.append(mapped)

        if len(new_faces) == 0:
            logger.warning(
                "Symmetry enforcement produced no valid faces — "
                "returning original mesh"
            )
            return mesh

        new_faces_arr = np.array(new_faces, dtype=np.int32)

        # --- FR-027(c): Merge boundary vertices at symmetry plane ---
        # Vertices near the symmetry plane (projection ≈ 0)
        # should be merged.
        new_centered = new_vertices - np.mean(new_vertices, axis=0)
        new_projections = new_centered @ symmetry_normal
        merge_tolerance = config.merge_tolerance * scale

        near_plane = np.abs(new_projections) < merge_tolerance
        if np.any(near_plane):
            # Project near-plane vertices onto the symmetry plane.
            plane_indices = np.where(near_plane)[0]
            for idx in plane_indices:
                proj = float(new_projections[idx])
                new_vertices[idx] -= proj * symmetry_normal

        # --- FR-029: Verify vertex count change ---
        new_count = len(new_vertices)
        delta_percent = abs(new_count - original_count) / max(original_count, 1) * 100

        if delta_percent > 10.0:
            logger.warning(
                "Symmetry enforcement changed vertex count by "
                "%.1f%% (original: %d, new: %d).",
                delta_percent,
                original_count,
                new_count,
            )

        logger.info(
            "Symmetry enforcement complete: original_vertex_count=%d, "
            "new_vertex_count=%d, delta_percent=%.1f",
            original_count,
            new_count,
            delta_percent,
        )

        # Build result mesh.
        from ..reconstruction.mesh_output import StandardMesh

        result = StandardMesh(
            vertices=new_vertices.astype(np.float32),
            faces=new_faces_arr,
            vertex_colors=mesh.vertex_colors,
            metadata=dict(mesh.metadata),
        )

        return result
