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

"""Edit executor — orchestrates the refinement pipeline.

Coordinates the operation dispatch, parameter validation,
pre-edit confirmation, and post-edit validation.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-018, FR-019, FR-035, FR-044, SEC-004, CON-008.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .intent_schema import (
    EditIntent,
    EditResult,
    OperationType,
    clamp_parameters,
)
from .operations import OPERATION_HANDLERS
from .undo_manager import UndoManager

logger = logging.getLogger("tessera.refinement")

#: FR-018: Vertex coverage threshold for confirmation prompt.
LARGE_EDIT_THRESHOLD = 0.80


class EditExecutor:
    """Executes edit operations on mesh objects.

    Orchestrates:
    1. Parameter validation and clamping (FR-044, SEC-004).
    2. Large-edit confirmation check (FR-018).
    3. Pre-edit undo snapshot (FR-032).
    4. Operation dispatch via the registry (FR-019).
    5. Post-edit print-readiness validation (FR-035).

    Implements: FR-018, FR-019, FR-035, FR-044, SEC-004, CON-008.
    """

    def __init__(self, undo_manager: UndoManager) -> None:
        """Initialize the executor.

        Args:
            undo_manager: The undo manager for snapshot tracking.
        """
        self._undo_manager = undo_manager

    def needs_confirmation(
        self,
        intent: EditIntent,
        obj: Any,
        vertex_group_name: str,
    ) -> Optional[str]:
        """Check if the operation needs user confirmation.

        FR-018: Operations affecting > 80% of vertices require
        confirmation before execution.

        Args:
            intent: The edit intent.
            obj: Target mesh object.
            vertex_group_name: Target vertex group.

        Returns:
            Confirmation message if needed, ``None`` otherwise.
        """
        # Skip confirmation for undo/redo.
        if intent.operation in (OperationType.UNDO, OperationType.REDO):
            return None

        try:
            total_verts = len(obj.data.vertices)
            if total_verts == 0:
                return None

            # Estimate affected vertices.
            if vertex_group_name in ("_bf_all", ""):
                affected = total_verts
            elif hasattr(obj, "vertex_groups") and vertex_group_name in obj.vertex_groups:
                vg_index = obj.vertex_groups[vertex_group_name].index
                affected = sum(
                    1 for v in obj.data.vertices
                    for g in v.groups
                    if g.group == vg_index
                )
            else:
                affected = total_verts

            ratio = affected / total_verts
            if ratio >= LARGE_EDIT_THRESHOLD:
                return (
                    f"This {intent.operation.value.lower()} will affect "
                    f"~{int(ratio * 100)}% of the mesh "
                    f"({affected:,} of {total_verts:,} vertices). "
                    f"Proceed?"
                )
        except (AttributeError, TypeError):
            pass

        return None

    def execute(
        self,
        context: Any,
        obj: Any,
        intent: EditIntent,
        vertex_group_name: str,
    ) -> EditResult:
        """Execute an edit operation.

        Args:
            context: Blender context.
            obj: Target mesh object.
            intent: The parsed edit intent.
            vertex_group_name: Resolved vertex group name.

        Returns:
            ``EditResult`` with operation outcome.

        Implements: FR-019, FR-035, FR-044, SEC-004.
        """
        operation = intent.operation

        logger.info(
            "Edit execution started: operation=%s, "
            "target_region=%s, vertex_group=%s",
            operation.value,
            intent.target_region,
            vertex_group_name,
        )

        # FR-044, SEC-004: Validate and clamp parameters.
        clamped_params, param_warnings = clamp_parameters(
            operation, intent.parameters
        )

        if param_warnings:
            for warning in param_warnings:
                logger.warning("Parameter clamped: %s", warning)

        # Get the handler.
        handler = OPERATION_HANDLERS.get(operation)
        if handler is None:
            return EditResult(
                success=False,
                description=f"No handler for operation: {operation.value}",
            )

        # FR-032: Push pre-edit snapshot (except for undo/redo).
        if operation not in (OperationType.UNDO, OperationType.REDO):
            description = (
                f"{operation.value}: {intent.target_region}"
            )
            self._undo_manager.push(obj, description)

        # Execute the operation.
        try:
            if operation in (OperationType.UNDO, OperationType.REDO):
                result = handler(
                    context, obj, clamped_params, vertex_group_name,
                    undo_manager=self._undo_manager,
                )
            else:
                result = handler(
                    context, obj, clamped_params, vertex_group_name,
                )
        except Exception as exc:
            logger.error(
                "Edit execution failed: operation=%s, "
                "error_type=%s, error_message=%s",
                operation.value,
                type(exc).__name__,
                str(exc),
            )
            return EditResult(
                success=False,
                description=f"Operation failed: {exc}",
            )

        # Attach parameter warnings.
        if param_warnings and result.success:
            result.warning = "; ".join(param_warnings)

        # FR-035: Post-edit validation (non-blocking).
        if result.success and operation not in (
            OperationType.UNDO, OperationType.REDO
        ):
            self._run_post_edit_validation(context, obj, result)

        logger.info(
            "Edit execution completed: operation=%s, success=%s, "
            "vertices_modified=%d, execution_time_seconds=%.3f",
            operation.value,
            result.success,
            result.vertices_modified,
            result.execution_time_seconds,
        )

        return result

    def _run_post_edit_validation(
        self,
        context: Any,
        obj: Any,
        result: EditResult,
    ) -> None:
        """Run print-readiness validation after a successful edit.

        FR-035: Integrates with SPEC-TS-0006 ``PrintValidator`` in
        validation-only mode (``auto_repair=False``).

        Validation is non-blocking — failures are appended as
        warnings, not errors.

        Args:
            context: Blender context.
            obj: Edited mesh object.
            result: The edit result to annotate with warnings.
        """
        try:
            from ..validator.print_validator import PrintValidator

            validator = PrintValidator()
            report = validator.validate(
                context, obj, auto_repair=False
            )

            if report.failures > 0:
                failure_names = [
                    c.check_name for c in report.checks
                    if c.status.value == "FAIL"
                ]
                warning_msg = (
                    f"Post-edit validation: {report.failures} issue(s) "
                    f"detected ({', '.join(failure_names[:3])}). "
                    f"Run Print Validator for details."
                )
                if result.warning:
                    result.warning += f"; {warning_msg}"
                else:
                    result.warning = warning_msg

                logger.debug(
                    "Post-edit validation warnings: failures=%d, "
                    "checks=%s",
                    report.failures,
                    failure_names,
                )
            else:
                logger.debug(
                    "Post-edit validation passed: warnings=%d",
                    report.warnings,
                )
        except Exception as exc:
            # Validation failure should not block the edit.
            logger.debug(
                "Post-edit validation skipped: %s",
                str(exc),
            )
