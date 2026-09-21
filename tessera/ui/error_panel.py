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

"""Error log panel for the Tessera sidebar.

Displays a scrollable list of recent errors with severity icons,
error codes, and truncated messages. Each entry is expandable
to show full resolution steps.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-006.
"""

from __future__ import annotations

import bpy

from ..errors.ui_reporter import get_global_reporter


class TESSERA_PT_error_log(bpy.types.Panel):
    """Tessera Error Log panel."""

    bl_label = "Error Log"
    bl_idname = "TESSERA_PT_error_log"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_order = 90
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        """Draw the error log panel.

        Shows a list of recent errors with severity-appropriate
        icons, error codes, and truncated messages.

        Implements: FR-006.
        """
        layout = self.layout
        reporter = get_global_reporter()

        if reporter is None or reporter.error_count == 0:
            layout.label(text="No errors recorded.", icon="CHECKMARK")
            return

        # Header row with count and clear button.
        header = layout.row()
        header.label(
            text=f"{reporter.error_count} error(s)",
            icon="ERROR",
        )
        header.operator(
            "tessera.clear_error_log",
            text="Clear",
            icon="X",
        )

        layout.separator()

        # Error list (most recent first, max 50 per FR-006).
        for entry in reporter.error_log:
            icon = reporter.get_icon(entry.severity)

            box = layout.box()
            row = box.row()
            row.label(
                text=f"[{entry.code}] {entry.truncated_message}",
                icon=icon,
            )
            row.label(text=entry.timestamp_str)

            # Resolution steps (collapsed by default).
            if entry.resolution_steps:
                sub = box.column(align=True)
                for step in entry.resolution_steps:
                    sub.label(text=f"  → {step}", icon="RIGHTARROW_THIN")


class TESSERA_OT_clear_error_log(bpy.types.Operator):
    """Clear the Tessera error log."""

    bl_idname = "tessera.clear_error_log"
    bl_label = "Clear Error Log"
    bl_description = "Clear all entries from the Tessera error log"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        """Clear the error log."""
        reporter = get_global_reporter()
        if reporter is not None:
            reporter.clear()
        return {"FINISHED"}


classes = [TESSERA_PT_error_log, TESSERA_OT_clear_error_log]
