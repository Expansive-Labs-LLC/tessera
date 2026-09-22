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

"""Performance summary panel for the Tessera sidebar.

Displays per-stage timing data and total pipeline duration
from the most recent profiler run.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-015.
"""

from __future__ import annotations

import bpy

# Module-level variable to store the latest performance report.
_latest_report = None


def set_latest_report(report) -> None:
    """Store the latest performance report for panel display.

    Args:
        report: A ``PerfReport`` instance or ``None``.
    """
    global _latest_report
    _latest_report = report


def get_latest_report():
    """Get the latest performance report.

    Returns:
        The latest ``PerfReport`` instance or ``None``.
    """
    return _latest_report


class TESSERA_PT_performance(bpy.types.Panel):
    """Tessera Performance panel."""

    bl_label = "Performance"
    bl_idname = "TESSERA_PT_performance"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_order = 91
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        """Draw the performance summary panel.

        Shows per-stage timing data with duration bars and the
        total pipeline duration.

        Implements: FR-015.
        """
        layout = self.layout
        report = get_latest_report()

        if report is None:
            layout.label(
                text="No performance data. Run the pipeline first.",
                icon="TIME",
            )
            return

        # Total duration header.
        header = layout.row()
        header.label(
            text=f"Total: {report.total_duration_seconds:.2f}s",
            icon="TIME",
        )

        if report.peak_gpu_memory_mb > 0:
            header.label(text=f"GPU Peak: {report.peak_gpu_memory_mb:.0f} MB")

        layout.separator()

        # Per-stage timing.
        total = report.total_duration_seconds or 1.0
        for stage in report.stages:
            pct = stage.duration_seconds / total * 100

            box = layout.box()
            row = box.row()
            row.label(
                text=f"{stage.stage_name}",
                icon="RIGHTARROW_THIN",
            )
            row.label(text=f"{stage.duration_seconds:.2f}s ({pct:.0f}%)")

            # Memory info if available.
            if stage.peak_memory_mb >= 0:
                box.label(text=f"  CPU Peak: {stage.peak_memory_mb:.1f} MB")

        # Bottleneck recommendations.
        bottlenecks = report.get_bottleneck_stages(top_n=1)
        if bottlenecks:
            top = bottlenecks[0]
            pct = top.duration_seconds / total * 100
            if pct > 50:
                layout.separator()
                box = layout.box()
                box.label(
                    text=f"⚡ Bottleneck: {top.stage_name} " f"({pct:.0f}% of total)",
                    icon="ERROR",
                )


classes = [TESSERA_PT_performance]
