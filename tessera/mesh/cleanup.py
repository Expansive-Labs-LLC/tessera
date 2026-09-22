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

"""Mesh cleanup pipeline orchestrator.

Executes a configurable chain of cleanup steps on a Blender mesh
object, following a chain-of-responsibility pattern.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-003–FR-009, FR-010–FR-016, FR-017–FR-020,
    CON-004, CON-005, CON-008, EC-002, EC-006.

Public API:
    MeshCleanupPipeline.execute() — runs the full pipeline.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any

import bpy

from .diagnostics import (
    build_diagnostics,
    check_manifold,
    check_topology,
    collect_after_stats,
    collect_before_stats,
)
from .exceptions import MeshCleanupError
from .steps.decimate import DecimateStep
from .steps.dedup import DedupStep
from .steps.degenerate import DegenerateStep
from .steps.hole_fill import HoleFillStep
from .steps.normals import NormalsStep
from .steps.quad_remesh import QuadRemeshStep
from .steps.voxel_remesh import VoxelRemeshStep

logger = logging.getLogger("tessera.mesh")

# EC-002: Large mesh face count threshold.
_LARGE_MESH_THRESHOLD = 500_000
_LARGE_MESH_ABORT_THRESHOLD = 1_000_000

# Critical steps whose failure raises MeshCleanupError (FR-020).
_CRITICAL_STEPS = frozenset({"DedupStep", "NormalsStep"})


class MeshCleanupPipeline:
    """Orchestrates the mesh cleanup chain of responsibility.

    Executes cleanup steps in dependency order, handles critical
    vs. non-critical step failures, and assembles a diagnostics
    report.

    Implements: FR-003–FR-009, FR-017–FR-020, CON-004, EC-002,
        EC-006.
    """

    def execute(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        merge_distance: float = 0.0001,
        voxel_size: float = 0.01,
        auto_voxel_fallback: bool = True,
        enable_quad_remesh: bool = False,
        quad_target_faces: int = 10000,
        enable_decimate: bool = False,
        decimate_target_faces: int = 50000,
    ) -> dict[str, Any]:
        """Execute the full cleanup pipeline on a mesh object.

        Args:
            context: Blender context.
            obj: Target mesh object (must have mesh data).
            merge_distance: Merge distance for duplicate removal
                (default ``0.0001`` m).
            voxel_size: Voxel size for remesh fallback
                (default ``0.01`` m).
            auto_voxel_fallback: Enable automatic voxel remesh
                when mesh remains non-manifold (default ``True``).
            enable_quad_remesh: Enable QuadriFlow quad remesh
                (default ``False``, Phase 2, opt-in per FR-016).
            quad_target_faces: Target face count for quad remesh
                (default ``10000``).
            enable_decimate: Enable decimation step
                (default ``False``, Phase 2).
            decimate_target_faces: Target face count for decimation
                (default ``50000``).

        Returns:
            Diagnostics dict per FR-007 (15 keys + ``step_errors``).

        Raises:
            MeshCleanupError: If a critical step (DedupStep,
                NormalsStep) fails.

        Implements: FR-003–FR-009, FR-017–FR-020, CON-004.
        """
        pipeline_start = time.perf_counter()

        # FR-019 / CON-004: Register undo step before destructive ops.
        bpy.ops.ed.undo_push(message="Tessera Mesh Cleanup")

        # CON-005: Verify we are only operating on the target object.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        # Collect before stats (FR-007).
        before_stats = collect_before_stats(obj)

        # EC-002: Large mesh warning.
        face_count = before_stats["faces_before"]
        if face_count > _LARGE_MESH_ABORT_THRESHOLD:
            logger.warning(
                "Input mesh has %d faces (exceeds %dK threshold). "
                "Cleanup may take longer than 5 seconds.",
                face_count,
                _LARGE_MESH_ABORT_THRESHOLD // 1000,
            )
        elif face_count > _LARGE_MESH_THRESHOLD:
            logger.warning(
                "Input mesh has %d faces (exceeds %dK threshold). "
                "Cleanup may take longer than 5 seconds.",
                face_count,
                _LARGE_MESH_THRESHOLD // 1000,
            )

        # Build settings dict for steps.
        settings: dict[str, Any] = {
            "merge_distance": merge_distance,
            "voxel_size": voxel_size,
            "auto_voxel_fallback": auto_voxel_fallback,
            "enable_quad_remesh": enable_quad_remesh,
            "quad_target_faces": quad_target_faces,
            "enable_decimate": enable_decimate,
            "decimate_target_faces": decimate_target_faces,
        }

        # Build the step chain.
        # Phase 1 steps always run; Phase 2 steps check their
        # enable flag internally.
        phase1_steps = [
            DedupStep(),
            DegenerateStep(),
            NormalsStep(),
            HoleFillStep(),
        ]

        phase2_steps = [
            QuadRemeshStep(),
            DecimateStep(),
        ]

        # Execute Phase 1 steps.
        merged_reports: dict[str, Any] = {}
        step_errors: list[dict[str, str]] = []

        for step in phase1_steps:
            merged_reports, step_errors = self._run_step(
                step, context, obj, settings, merged_reports, step_errors
            )

        # Check manifold status after Phase 1 surgical repair.
        is_manifold_after_repair = check_manifold(obj)

        # FR-006: Voxel remesh fallback if still non-manifold.
        if not is_manifold_after_repair and auto_voxel_fallback:
            voxel_step = VoxelRemeshStep()
            merged_reports, step_errors = self._run_step(
                voxel_step,
                context,
                obj,
                settings,
                merged_reports,
                step_errors,
            )
        else:
            merged_reports["voxel_remesh_applied"] = False

        # Execute Phase 2 steps (each checks its own enable flag).
        for step in phase2_steps:
            merged_reports, step_errors = self._run_step(
                step, context, obj, settings, merged_reports, step_errors
            )

        # Collect after stats.
        after_stats = collect_after_stats(obj)

        # Final validation (single bmesh round-trip).
        is_manifold, is_watertight = check_topology(obj)

        # Build diagnostics dict (FR-007).
        pipeline_time = time.perf_counter() - pipeline_start
        diagnostics = build_diagnostics(
            before_stats=before_stats,
            step_reports=merged_reports,
            after_stats=after_stats,
            is_manifold=is_manifold,
            is_watertight=is_watertight,
            cleanup_time=pipeline_time,
            step_errors=step_errors,
        )

        # FR-009: Select the cleaned object and frame in viewport.
        context.view_layer.objects.active = obj
        obj.select_set(True)
        try:
            bpy.ops.view3d.view_selected()
        except (RuntimeError, AttributeError):
            # May fail if no 3D viewport is open (headless/background mode).
            pass

        # §11.1: Log pipeline completion with full diagnostics.
        logger.info("Cleanup pipeline completed: %s", diagnostics)

        return diagnostics

    def _run_step(
        self,
        step: Any,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        settings: dict[str, Any],
        merged_reports: dict[str, Any],
        step_errors: list[dict[str, str]],
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        """Run a single cleanup step with error handling.

        Critical steps (DedupStep, NormalsStep) raise
        ``MeshCleanupError`` on failure.  Non-critical steps
        catch exceptions and continue.

        Args:
            step: The cleanup step instance.
            context: Blender context.
            obj: Target mesh object.
            settings: Pipeline settings dict.
            merged_reports: Accumulated step reports.
            step_errors: Accumulated non-critical error list.

        Returns:
            Tuple of (updated merged_reports, updated step_errors).

        Implements: FR-020, EC-006.
        """
        is_critical = step.name in _CRITICAL_STEPS

        try:
            report = step.execute(context, obj, settings)
            merged_reports.update(report)
        except Exception as exc:
            if is_critical:
                # FR-020: Critical step failure — raise to caller.
                raise MeshCleanupError(step.name, exc) from exc

            # FR-020 / EC-006: Non-critical step failure.
            error_msg = str(exc)
            logger.error(
                "Non-critical cleanup step '%s' failed: %s\n%s",
                step.name,
                error_msg,
                traceback.format_exc(),
            )
            step_errors.append({"step": step.name, "error": error_msg})

        return merged_reports, step_errors
