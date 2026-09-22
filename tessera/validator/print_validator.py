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

"""Print-readiness validator orchestrator.

Runs all 7 validation checks in sequence, handles auto-repair,
and produces a ``ValidationReport``.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-028–FR-032, FR-034, FR-039.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .checks import ALL_CHECKS
from .data_types import CheckResult, CheckStatus
from .report import ValidationReport

logger = logging.getLogger("tessera.validator")


class PrintValidator:
    """Orchestrates the 7 print-readiness validation checks.

    Executes each check in sequence, optionally auto-repairs failures,
    re-validates after repair, and produces a ``ValidationReport``.

    Design note (CON-006): This orchestrator runs synchronously rather
    than via a modal operator. The spec requires no UI blocking >100ms,
    which is addressed by stratified sampling (CON-008, max 10K faces)
    that bounds wall-thickness ray-casting time. The full pipeline
    meets NFR-001 (<10s for ≤500K faces) without requiring modal
    execution. A modal operator may be introduced in a future iteration
    if real-world meshes exceed these targets.

    Implements: FR-028–FR-032, FR-034, FR-039.
    """

    def validate(
        self,
        context: Any,
        obj: Any,
        printer_type: str = "FDM",
        wall_thickness_mm: float = 1.2,
        overhang_angle_deg: float = 45.0,
        build_volume_mm: tuple[float, float, float] = (220.0, 220.0, 250.0),
        auto_repair: bool = False,
        auto_scale: bool = False,
        voxel_size_mm: float = 0.5,
    ) -> ValidationReport:
        """Run all validation checks on *obj*.

        When ``auto_repair`` is ``True``, failed checks are repaired
        on *obj* (which should be the ``_print`` duplicate) and
        re-validated.

        When called in validation-only mode (FR-039), ``auto_repair``
        should be ``False`` and *obj* is the original (not duplicated).

        Args:
            context: Blender context.
            obj: ``bpy.types.Object`` with mesh data.
            printer_type: ``"FDM"`` or ``"SLA"``.
            wall_thickness_mm: Minimum wall thickness in mm.
            overhang_angle_deg: Overhang angle threshold in degrees.
            build_volume_mm: Build volume ``(x, y, z)`` in mm.
            auto_repair: Whether to attempt auto-repair on failures.
            auto_scale: Whether to auto-scale to fit build volume.
            voxel_size_mm: Voxel size for remesh fallback.

        Returns:
            ``ValidationReport`` with results for all 7 checks.

        Implements: FR-028–FR-032.
        """
        report = ValidationReport(
            object_name=obj.name,
            printer_type=printer_type,
        )

        settings: dict[str, Any] = {
            "printer_type": printer_type,
            "wall_thickness_mm": wall_thickness_mm,
            "overhang_angle_deg": overhang_angle_deg,
            "build_x_mm": build_volume_mm[0],
            "build_y_mm": build_volume_mm[1],
            "build_z_mm": build_volume_mm[2],
            "auto_repair": auto_repair,
            "auto_scale": auto_scale,
            "voxel_size_mm": voxel_size_mm,
            "merge_distance": 0.0001,
        }

        face_count = len(obj.data.polygons)
        logger.info(
            "Validation pipeline started: object_name=%s, "
            "face_count=%d, printer_type=%s",
            obj.name,
            face_count,
            printer_type,
        )

        pipeline_start = time.perf_counter()

        for check_cls in ALL_CHECKS:
            check = check_cls()
            check_name = check.name

            logger.debug(
                "Validation check started: check_name=%s, face_count=%d",
                check_name,
                face_count,
            )

            check_start = time.perf_counter()
            result = check.check(obj, settings)
            check_elapsed = time.perf_counter() - check_start

            logger.debug(
                "Validation check completed: check_name=%s, status=%s, "
                "elapsed_seconds=%.3f",
                check_name,
                result.status.value,
                check_elapsed,
            )

            # Auto-repair if the check failed and repair is enabled.
            if result.status == CheckStatus.FAIL and auto_repair:
                result = self._attempt_repair(check, obj, settings, result)

            report.add_check(result)

        pipeline_elapsed = time.perf_counter() - pipeline_start
        report.validation_time_seconds = pipeline_elapsed

        logger.info(
            "Validation pipeline completed: passed=%d, warnings=%d, "
            "failures=%d, auto_repairs=%d, elapsed=%.2fs",
            report.passed,
            report.warnings,
            report.failures,
            report.auto_repairs_applied,
            pipeline_elapsed,
        )

        return report

    def _attempt_repair(
        self,
        check: Any,
        obj: Any,
        settings: dict[str, Any],
        original_result: CheckResult,
    ) -> CheckResult:
        """Attempt auto-repair and re-validate.

        Args:
            check: The check instance.
            obj: ``bpy.types.Object`` (the ``_print`` duplicate).
            settings: Validator settings dict.
            original_result: The initial ``FAIL`` result.

        Returns:
            Updated ``CheckResult`` after repair attempt.
        """
        check_name = check.name

        logger.info(
            "Auto-repair attempted: check_name=%s, " "repair_strategy=%s",
            check_name,
            type(check).__name__,
        )

        try:
            repair_result = check.repair(obj, settings)
        except Exception as exc:
            logger.warning(
                "Auto-repair failed: check_name=%s, error_message=%s",
                check_name,
                str(exc),
            )
            return original_result

        if repair_result.success:
            logger.info(
                "Auto-repair succeeded: check_name=%s, " "repair_message=%s",
                check_name,
                repair_result.message,
            )

            # Re-validate after repair.
            recheck_result = check.check(obj, settings)
            recheck_result.repaired = True
            recheck_result.repair_message = repair_result.message
            return recheck_result
        else:
            logger.warning(
                "Auto-repair failed: check_name=%s, " "error_message=%s",
                check_name,
                repair_result.message,
            )
            # Return original failure with repair attempt noted.
            original_result.repaired = False
            original_result.repair_message = repair_result.message
            return original_result
