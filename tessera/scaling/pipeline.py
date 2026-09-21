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

"""Scaling and orientation pipeline orchestrator.

Chains the scaling, build-volume validation, orientation optimization,
and base flattening stages into a single pipeline that transforms a
cleaned mesh into print-ready geometry.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-031–FR-035, CON-004, CON-005.

Public API:
    ScalingOrientationPipeline.execute() — runs the full pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import bpy

from .base_flattener import BaseFlattener
from .build_volume_check import BuildVolumeCheck
from .dimension_input import DimensionSpec
from .exceptions import ScalingError
from .orientation import OrientationOptimizer
from .printer_profiles import PrinterProfile, get_profile_by_name
from .scaler import MeshScaler

logger = logging.getLogger("tessera.scaling")

# Default printer profile name.
_DEFAULT_PROFILE_NAME = "Generic FDM"


class ScalingOrientationPipeline:
    """Orchestrates scaling, validation, orientation, and flattening.

    Follows the same chain-of-responsibility pattern as the
    ``MeshCleanupPipeline`` (SPEC-TS-0005).  Each stage is an
    independent class with an ``execute()``/``apply()``/
    ``validate()``/``optimize()``/``flatten()`` method.

    The pipeline returns a diagnostics dict summarizing all
    applied transformations.

    Implements: FR-031–FR-035, CON-004, CON-005.
    """

    def execute(
        self,
        context: "bpy.types.Context",
        obj: "bpy.types.Object",
        dimension_spec: DimensionSpec,
        printer_profile: Optional[PrinterProfile] = None,
        enable_orientation: bool = True,
        overhang_threshold_deg: float = 45.0,
        enable_fine_tuning: bool = True,
        manual_euler_deg: Optional[Tuple[float, float, float]] = None,
    ) -> Dict[str, Any]:
        """Execute the full scaling and orientation pipeline.

        Args:
            context: Blender context.
            obj: Target mesh object (must have mesh data).
            dimension_spec: Target dimensions (user-specified or
                resolved from auto-inference).
            printer_profile: Printer profile for build volume
                validation.  Defaults to ``"Generic FDM"``.
            enable_orientation: Enable orientation optimization
                (default ``True``).
            overhang_threshold_deg: Overhang angle threshold in
                degrees (default 45.0, range 20–70).
            enable_fine_tuning: Enable gradient refinement around
                the best orientation candidate (default ``True``).
            manual_euler_deg: If provided, apply this rotation
                directly instead of optimizing (FR-026).

        Returns:
            Diagnostics dict per FR-033 with 17+ keys.

        Implements: FR-031–FR-035, CON-004, CON-005.
        """
        pipeline_start = time.perf_counter()

        # Resolve printer profile.
        if printer_profile is None:
            printer_profile = get_profile_by_name(_DEFAULT_PROFILE_NAME)
            if printer_profile is None:
                # Should never happen, but defensive fallback.
                from .printer_profiles import get_builtin_profiles
                printer_profile = get_builtin_profiles()[0]

        logger.info(
            "Scaling pipeline started: target=(%s, %s, %s) mm, "
            "printer=%s, object=%s",
            dimension_spec.width_mm or "auto",
            dimension_spec.height_mm or "auto",
            dimension_spec.depth_mm or "auto",
            printer_profile.name,
            obj.name,
        )

        # FR-034 / CON-004: Register undo step.
        bpy.ops.ed.undo_push(message="Tessera Scaling & Orientation")

        # CON-005: Only operate on the target object.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        # Determine dimension source.
        dimension_source = "auto_inferred" if dimension_spec.auto else "user"

        all_warnings: List[str] = []

        # Stage 1: Scaling.
        try:
            scaler = MeshScaler()
            scaling_result = scaler.apply(
                context,
                obj,
                dimension_spec,
                printer_technology=printer_profile.technology,
            )
            all_warnings.extend(scaling_result.get("warnings", []))

            logger.debug("Scaling stage complete: %s", scaling_result)

            # Stage 2: Build volume validation.
            bv_checker = BuildVolumeCheck()
            bv_result = bv_checker.validate(obj, printer_profile)
            all_warnings.extend(bv_result.get("build_volume_warnings", []))

            logger.debug("Build volume check complete: %s", bv_result)

            # Stage 3: Orientation optimization (if enabled).
            orientation_result: Dict[str, Any]
            if enable_orientation:
                optimizer = OrientationOptimizer()
                orientation_result = optimizer.optimize(
                    context,
                    obj,
                    overhang_threshold_deg=overhang_threshold_deg,
                    enable_fine_tuning=enable_fine_tuning,
                    manual_euler_deg=manual_euler_deg,
                )
            else:
                orientation_result = {
                    "orientation_applied": False,
                    "orientation_euler_deg": (0.0, 0.0, 0.0),
                    "overhang_area_before_mm2": 0.0,
                    "overhang_area_after_mm2": 0.0,
                    "overhang_reduction_pct": 0.0,
                    "candidate_count": 0,
                    "orientation_time_seconds": 0.0,
                }

            logger.debug("Orientation stage complete: %s", orientation_result)

            # Stage 4: Base flattening.
            flattener = BaseFlattener()
            flatten_result = flattener.flatten(context, obj)
            all_warnings.extend(flatten_result.get("warnings", []))

            logger.debug("Base flattening complete: %s", flatten_result)

        except (ScalingError, ValueError):
            # Expected pipeline errors — propagate without wrapping.
            raise
        except Exception as exc:
            logger.error(
                "Unexpected error during scaling pipeline: %s", exc,
                exc_info=True,
            )
            raise ScalingError(
                f"Scaling pipeline failed unexpectedly: {exc}"
            ) from exc

        # Mark the object as having been processed by this pipeline.
        # Cross-spec delegation: SPEC-TS-0006 checks this property
        # to skip its own FR-025/FR-026/FR-027 logic.
        try:
            obj["tessera.scaling.applied"] = True
        except Exception:
            # May fail in some test contexts.
            pass

        # FR-033: Assemble diagnostics dict.
        pipeline_time = time.perf_counter() - pipeline_start

        diagnostics: Dict[str, Any] = {
            # Scaling diagnostics.
            "original_dimensions_mm": scaling_result["original_dimensions_mm"],
            "target_dimensions_mm": scaling_result["target_dimensions_mm"],
            "scaled_dimensions_mm": scaling_result["scaled_dimensions_mm"],
            "scale_factors": scaling_result["scale_factors"],
            "dimension_source": dimension_source,
            # Printer / build volume diagnostics.
            "printer_profile": printer_profile.name,
            "build_volume_fit": bv_result["build_volume_fit"],
            "build_volume_violations": bv_result["build_volume_violations"],
            # Orientation diagnostics.
            "orientation_applied": orientation_result["orientation_applied"],
            "orientation_euler_deg": orientation_result[
                "orientation_euler_deg"
            ],
            "overhang_area_before_mm2": orientation_result[
                "overhang_area_before_mm2"
            ],
            "overhang_area_after_mm2": orientation_result[
                "overhang_area_after_mm2"
            ],
            "overhang_reduction_pct": orientation_result[
                "overhang_reduction_pct"
            ],
            # Base flattening diagnostics.
            "bottom_flatness_variance_mm2": flatten_result[
                "bottom_flatness_variance_mm2"
            ],
            "base_z_offset_mm": flatten_result["base_z_offset_mm"],
            # Pipeline-level diagnostics.
            "pipeline_time_seconds": pipeline_time,
            "warnings": all_warnings,
        }

        logger.info("Pipeline completed: %s", diagnostics)

        return diagnostics
