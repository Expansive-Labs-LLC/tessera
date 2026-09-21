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

"""Print orientation optimizer — minimizes overhang area.

Evaluates candidate orientations (6 canonical + 8 diagonal + optional
fine-tuning) to find the rotation that minimizes faces exceeding the
overhang threshold relative to the build plate.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-021–FR-026, EC-001.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

logger = logging.getLogger("tessera.scaling")

# EC-001: Symmetry detection — variance threshold as fraction of mean.
_SYMMETRY_VARIANCE_THRESHOLD = 0.01  # 1%

# FR-025: Fine-tuning angle steps in degrees.
_FINE_TUNE_ANGLES_DEG = [-10.0, -5.0, 5.0, 10.0]


@dataclass
class OrientationCandidate:
    """A candidate orientation with its overhang score.

    Attributes:
        euler_deg: Euler angles in degrees ``(rx, ry, rz)``.
        overhang_area_mm2: Total overhang area in mm² for faces
            exceeding the overhang threshold.
        index: Candidate index for debugging.
    """

    euler_deg: Tuple[float, float, float]
    overhang_area_mm2: float
    index: int


class OrientationOptimizer:
    """Optimizes mesh orientation to minimize print overhangs.

    Tests a minimum of 14 candidate orientations (6 canonical +
    8 diagonal), optionally refined with ±5°/±10° gradient search.

    Implements: FR-021–FR-026, EC-001.
    """

    def optimize(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        overhang_threshold_deg: float = 45.0,
        enable_fine_tuning: bool = True,
        manual_euler_deg: Optional[Tuple[float, float, float]] = None,
    ) -> Dict[str, Any]:
        """Find and apply the optimal orientation.

        Args:
            context: Blender context.
            obj: Target mesh object.
            overhang_threshold_deg: Overhang angle threshold in
                degrees (default 45°, range 20°–70°).
            enable_fine_tuning: Enable gradient refinement around
                the best candidate (FR-025, default ``True``).
            manual_euler_deg: If provided, skip optimization and
                apply this rotation directly (FR-026).

        Returns:
            Dict with orientation diagnostics.

        Implements: FR-021–FR-026, EC-001.
        """
        start_time = time.perf_counter()

        # Ensure object is active and selected.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        # FR-026: Manual mode — bypass optimizer.
        if manual_euler_deg is not None:
            return self._apply_manual_orientation(
                context, obj, manual_euler_deg, overhang_threshold_deg,
                start_time,
            )

        # Extract face data once for reuse across all candidates.
        normals, areas = self._extract_face_data(obj)

        # Compute initial overhang score (current orientation).
        initial_score = self._score_orientation(
            obj, (0.0, 0.0, 0.0), overhang_threshold_deg,
            normals=normals, areas=areas,
        )
        logger.info(
            "Initial overhang area: %.2f mm²", initial_score
        )

        # FR-022: Build candidate orientations.
        candidates = self._build_candidates(
            obj, overhang_threshold_deg,
            normals=normals, areas=areas,
        )

        logger.info(
            "Orientation optimization started: %d candidates, "
            "overhang threshold=%.1f°",
            len(candidates),
            overhang_threshold_deg,
        )

        # EC-001: Symmetry detection.
        scores = [c.overhang_area_mm2 for c in candidates]
        if len(scores) > 1:
            mean_score = np.mean(scores)
            variance = np.var(scores)
            if mean_score > 0.0:
                relative_variance = variance / (mean_score ** 2)
                if relative_variance < _SYMMETRY_VARIANCE_THRESHOLD:
                    elapsed = time.perf_counter() - start_time
                    logger.info(
                        "Mesh is approximately symmetrical — orientation "
                        "optimization has minimal effect. Using default "
                        "orientation (current)."
                    )
                    return {
                        "orientation_applied": False,
                        "orientation_euler_deg": (0.0, 0.0, 0.0),
                        "overhang_area_before_mm2": initial_score,
                        "overhang_area_after_mm2": initial_score,
                        "overhang_reduction_pct": 0.0,
                        "candidate_count": len(candidates),
                        "orientation_time_seconds": elapsed,
                    }

        # Find the best candidate.
        best = min(candidates, key=lambda c: c.overhang_area_mm2)

        logger.debug(
            "Best base candidate: index=%d, euler=%s, "
            "overhang=%.2f mm²",
            best.index,
            best.euler_deg,
            best.overhang_area_mm2,
        )

        # FR-025: Optional fine-tuning around the best candidate.
        if enable_fine_tuning:
            fine_candidates = self._build_fine_tune_candidates(
                obj, best.euler_deg, overhang_threshold_deg,
                start_index=len(candidates),
                normals=normals, areas=areas,
            )
            candidates.extend(fine_candidates)

            if fine_candidates:
                fine_best = min(
                    fine_candidates, key=lambda c: c.overhang_area_mm2
                )
                if fine_best.overhang_area_mm2 < best.overhang_area_mm2:
                    best = fine_best
                    logger.debug(
                        "Fine-tuning improved result: euler=%s, "
                        "overhang=%.2f mm²",
                        best.euler_deg,
                        best.overhang_area_mm2,
                    )

        # FR-024: Apply the winning orientation.
        self._apply_orientation(context, obj, best.euler_deg)

        # Compute reduction.
        after_score = best.overhang_area_mm2
        reduction_pct = 0.0
        if initial_score > 0.0:
            reduction_pct = (
                (initial_score - after_score) / initial_score * 100.0
            )

        elapsed = time.perf_counter() - start_time

        logger.info(
            "Best orientation selected: euler=(%.1f, %.1f, %.1f)°, "
            "overhang before=%.2f mm², after=%.2f mm², "
            "reduction=%.1f%%, time=%.3f s",
            *best.euler_deg,
            initial_score,
            after_score,
            reduction_pct,
            elapsed,
        )

        return {
            "orientation_applied": True,
            "orientation_euler_deg": best.euler_deg,
            "overhang_area_before_mm2": initial_score,
            "overhang_area_after_mm2": after_score,
            "overhang_reduction_pct": reduction_pct,
            "candidate_count": len(candidates),
            "orientation_time_seconds": elapsed,
        }

    def _extract_face_data(
        self,
        obj: "bpy.types.Object",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Extract face normals and areas from the mesh once.

        Uses ``foreach_get`` for bulk array extraction when
        available (real Blender), with a Python-loop fallback
        for mock/test environments.

        Args:
            obj: Target mesh object.

        Returns:
            Tuple of (normals, areas) as NumPy arrays.
            normals: shape ``(N, 3)``, dtype float64.
            areas: shape ``(N,)``, dtype float64.
        """
        mesh = obj.data
        mesh.calc_loop_triangles()
        polys = mesh.polygons
        num_faces = len(polys)

        if num_faces == 0:
            return (
                np.zeros((0, 3), dtype=np.float64),
                np.zeros(0, dtype=np.float64),
            )

        normals = np.zeros((num_faces, 3), dtype=np.float64)
        areas = np.zeros(num_faces, dtype=np.float64)

        # Prefer foreach_get for ~10× faster bulk extraction
        # on real Blender meshes.  Fall back to a Python loop
        # when the method is absent (mock environments).
        try:
            normals_flat = np.zeros(num_faces * 3, dtype=np.float64)
            polys.foreach_get("normal", normals_flat)
            normals = normals_flat.reshape((num_faces, 3))
            polys.foreach_get("area", areas)
        except (AttributeError, TypeError):
            for i, poly in enumerate(polys):
                normals[i] = (
                    poly.normal[0], poly.normal[1], poly.normal[2]
                )
                areas[i] = poly.area

        return normals, areas

    def _build_candidates(
        self,
        obj: "bpy.types.Object",
        overhang_threshold_deg: float,
        normals: Optional[np.ndarray] = None,
        areas: Optional[np.ndarray] = None,
    ) -> List[OrientationCandidate]:
        """Build the 14 base candidate orientations.

        6 canonical (each axis ±) + 8 diagonal (each octant).

        Args:
            obj: Target mesh object.
            overhang_threshold_deg: Overhang threshold in degrees.
            normals: Pre-extracted face normals (optional).
            areas: Pre-extracted face areas (optional).

        Returns:
            List of 14 ``OrientationCandidate`` instances.

        Implements: FR-022.
        """
        if normals is None or areas is None:
            normals, areas = self._extract_face_data(obj)

        candidates: List[OrientationCandidate] = []
        index = 0

        # 6 canonical rotations: align each axis to Z in both
        # directions.
        canonical_eulers_deg = [
            (0.0, 0.0, 0.0),      # +Z up (identity)
            (180.0, 0.0, 0.0),    # -Z up (flip around X)
            (90.0, 0.0, 0.0),     # +Y up
            (-90.0, 0.0, 0.0),    # -Y up
            (0.0, 90.0, 0.0),     # +X up
            (0.0, -90.0, 0.0),    # -X up
        ]

        for euler_deg in canonical_eulers_deg:
            score = self._score_orientation(
                obj, euler_deg, overhang_threshold_deg,
                normals=normals, areas=areas,
            )
            candidates.append(
                OrientationCandidate(
                    euler_deg=euler_deg,
                    overhang_area_mm2=score,
                    index=index,
                )
            )
            logger.debug(
                "Candidate %d: euler=%s, overhang=%.2f mm²",
                index,
                euler_deg,
                score,
            )
            index += 1

        # 8 diagonal orientations: each octant direction.
        diag_val = math.degrees(math.atan2(1.0, math.sqrt(2.0)))
        diagonal_eulers_deg = [
            (diag_val, diag_val, 0.0),
            (diag_val, -diag_val, 0.0),
            (-diag_val, diag_val, 0.0),
            (-diag_val, -diag_val, 0.0),
            (diag_val, 0.0, diag_val),
            (diag_val, 0.0, -diag_val),
            (-diag_val, 0.0, diag_val),
            (-diag_val, 0.0, -diag_val),
        ]

        for euler_deg in diagonal_eulers_deg:
            score = self._score_orientation(
                obj, euler_deg, overhang_threshold_deg,
                normals=normals, areas=areas,
            )
            candidates.append(
                OrientationCandidate(
                    euler_deg=euler_deg,
                    overhang_area_mm2=score,
                    index=index,
                )
            )
            logger.debug(
                "Candidate %d: euler=%s, overhang=%.2f mm²",
                index,
                euler_deg,
                score,
            )
            index += 1

        return candidates

    def _build_fine_tune_candidates(
        self,
        obj: "bpy.types.Object",
        base_euler_deg: Tuple[float, float, float],
        overhang_threshold_deg: float,
        start_index: int = 0,
        normals: Optional[np.ndarray] = None,
        areas: Optional[np.ndarray] = None,
    ) -> List[OrientationCandidate]:
        """Build 16 fine-tuning candidates around the best base.

        Tests ±5° and ±10° rotations around X and Y axes
        (4 × 4 = 16 combinations).

        Args:
            obj: Target mesh object.
            base_euler_deg: Base orientation Euler angles in degrees.
            overhang_threshold_deg: Overhang threshold in degrees.
            start_index: Starting candidate index.
            normals: Pre-extracted face normals (optional).
            areas: Pre-extracted face areas (optional).

        Returns:
            List of 16 ``OrientationCandidate`` instances.

        Implements: FR-025.
        """
        if normals is None or areas is None:
            normals, areas = self._extract_face_data(obj)

        candidates: List[OrientationCandidate] = []
        index = start_index

        rx_base, ry_base, rz_base = base_euler_deg

        for dx in _FINE_TUNE_ANGLES_DEG:
            for dy in _FINE_TUNE_ANGLES_DEG:
                euler_deg = (rx_base + dx, ry_base + dy, rz_base)
                score = self._score_orientation(
                    obj, euler_deg, overhang_threshold_deg,
                    normals=normals, areas=areas,
                )
                candidates.append(
                    OrientationCandidate(
                        euler_deg=euler_deg,
                        overhang_area_mm2=score,
                        index=index,
                    )
                )
                logger.debug(
                    "Fine-tune candidate %d: euler=%s, "
                    "overhang=%.2f mm²",
                    index,
                    euler_deg,
                    score,
                )
                index += 1

        return candidates

    def _score_orientation(
        self,
        obj: "bpy.types.Object",
        euler_deg: Tuple[float, float, float],
        overhang_threshold_deg: float,
        normals: Optional[np.ndarray] = None,
        areas: Optional[np.ndarray] = None,
    ) -> float:
        """Compute overhang score for a candidate orientation.

        Applies the rotation virtually (to face normals, not the
        object) and computes the total area of faces exceeding
        the overhang threshold.

        Uses vectorized NumPy operations for performance (FR-023).
        Accepts optional pre-extracted ``normals`` and ``areas``
        to avoid redundant mesh data extraction across multiple
        candidate evaluations.

        Args:
            obj: Target mesh object.
            euler_deg: Candidate Euler angles in degrees.
            overhang_threshold_deg: Overhang threshold in degrees.
            normals: Pre-extracted face normals, shape ``(N, 3)``.
                If ``None``, extracted from ``obj.data.polygons``.
            areas: Pre-extracted face areas, shape ``(N,)``.
                If ``None``, extracted from ``obj.data.polygons``.

        Returns:
            Total overhang area in mm².

        Implements: FR-023.
        """
        # Extract face data if not provided (standalone calls).
        if normals is None or areas is None:
            normals, areas = self._extract_face_data(obj)

        if len(normals) == 0:
            return 0.0

        # Build rotation matrix from candidate Euler angles.
        euler_rad = tuple(math.radians(a) for a in euler_deg)
        rot_matrix = Euler(euler_rad, "XYZ").to_matrix()

        # Apply rotation to normals.
        rot_np = np.array(rot_matrix, dtype=np.float64)
        rotated_normals = normals @ rot_np.T

        # Gravity direction: negative Z = (0, 0, -1).
        gravity = np.array([0.0, 0.0, -1.0], dtype=np.float64)

        # Compute angle between each rotated normal and gravity.
        dot_products = rotated_normals @ gravity
        dot_products = np.clip(dot_products, -1.0, 1.0)
        angles_rad = np.arccos(dot_products)
        angles_deg = np.degrees(angles_rad)

        # FR-021: Sum areas of faces exceeding the threshold.
        overhang_mask = angles_deg > overhang_threshold_deg
        overhang_area = float(np.sum(areas[overhang_mask]))

        return overhang_area

    def _compute_overhang_score(
        self,
        obj: "bpy.types.Object",
        overhang_threshold_deg: float,
    ) -> float:
        """Compute overhang score at current orientation.

        Args:
            obj: Target mesh object.
            overhang_threshold_deg: Overhang threshold in degrees.

        Returns:
            Total overhang area in mm².
        """
        return self._score_orientation(
            obj, (0.0, 0.0, 0.0), overhang_threshold_deg
        )

    def _apply_orientation(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        euler_deg: Tuple[float, float, float],
    ) -> None:
        """Apply the winning orientation to the object.

        Sets ``obj.rotation_euler`` and applies via
        ``bpy.ops.object.transform_apply(rotation=True)``.

        Args:
            context: Blender context.
            obj: Target mesh object.
            euler_deg: Euler angles in degrees.

        Implements: FR-024.
        """
        euler_rad = tuple(math.radians(a) for a in euler_deg)
        obj.rotation_euler = Euler(euler_rad, "XYZ")

        context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(
            location=False, rotation=True, scale=False
        )

        logger.debug(
            "Applied orientation: euler=(%.1f, %.1f, %.1f)°",
            *euler_deg,
        )

    def _apply_manual_orientation(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        euler_deg: Tuple[float, float, float],
        overhang_threshold_deg: float,
        start_time: float,
    ) -> Dict[str, Any]:
        """Apply a user-specified manual orientation.

        Args:
            context: Blender context.
            obj: Target mesh object.
            euler_deg: User-specified Euler angles in degrees.
            overhang_threshold_deg: Overhang threshold for scoring.
            start_time: Pipeline start timestamp.

        Returns:
            Dict with orientation diagnostics.

        Implements: FR-026.
        """
        before_score = self._compute_overhang_score(
            obj, overhang_threshold_deg
        )

        self._apply_orientation(context, obj, euler_deg)

        after_score = self._score_orientation(
            obj, (0.0, 0.0, 0.0), overhang_threshold_deg
        )

        reduction_pct = 0.0
        if before_score > 0.0:
            reduction_pct = (
                (before_score - after_score) / before_score * 100.0
            )

        elapsed = time.perf_counter() - start_time

        logger.info(
            "Manual orientation applied: euler=(%.1f, %.1f, %.1f)°, "
            "overhang before=%.2f mm², after=%.2f mm²",
            *euler_deg,
            before_score,
            after_score,
        )

        return {
            "orientation_applied": True,
            "orientation_euler_deg": euler_deg,
            "overhang_area_before_mm2": before_score,
            "overhang_area_after_mm2": after_score,
            "overhang_reduction_pct": reduction_pct,
            "candidate_count": 1,
            "orientation_time_seconds": elapsed,
        }
