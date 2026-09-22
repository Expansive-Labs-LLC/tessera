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

"""Export operator for Tessera.

Provides the ``TESSERA_OT_export_for_print`` operator that runs the
full pipeline: duplicate → validate → repair → export → cleanup.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-035, FR-037, FR-038, EC-003, EC-004, SEC-001.
"""

from __future__ import annotations

import logging
import os

from bpy.types import Operator

from ..export.export_pipeline import ExportPipeline

logger = logging.getLogger("tessera.export")


class TESSERA_OT_export_for_print(Operator):
    """Export the active mesh for 3D printing.

    Runs the full pipeline: duplicate → validate → auto-repair →
    re-validate → export → cleanup duplicate.

    If ``force_export`` is enabled and validation has failures,
    shows a confirmation dialog before exporting.

    Implements: FR-035, FR-037, FR-038.
    """

    bl_idname = "tessera.export_for_print"
    bl_label = "Export for Printing"
    bl_description = (
        "Validate, repair, and export the active mesh to " "STL/3MF/OBJ for 3D printing"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Return ``True`` only when a mesh object is active.

        Implements: EC-003, SEC-001.
        """
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def invoke(self, context, event):
        """Handle pre-export checks and force-export confirmation.

        Args:
            context: Blender context.
            event: Blender event.

        Returns:
            Operator result set.

        Implements: FR-038, EC-004.
        """
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            self.report(
                {"ERROR"},
                "No mesh object selected. Select a mesh object to validate.",
            )
            return {"CANCELLED"}

        # EC-004: Validate export directory before proceeding.
        vs = context.scene.tessera.validator
        export_dir = vs.export_directory

        if export_dir:
            resolved = os.path.realpath(export_dir)
            if not os.path.isdir(resolved):
                self.report(
                    {"ERROR"},
                    f"Export directory '{export_dir}' does not exist "
                    f"or is not writable.",
                )
                return {"CANCELLED"}
            if not os.access(resolved, os.W_OK):
                self.report(
                    {"ERROR"},
                    f"Export directory '{export_dir}' does not exist "
                    f"or is not writable.",
                )
                return {"CANCELLED"}

        # FR-038: If force_export is enabled, run a quick validation
        # to check if we need a confirmation dialog.
        if vs.force_export:
            from ..validator.print_validator import PrintValidator

            validator = PrintValidator()
            quick_report = validator.validate(
                context=context,
                obj=obj,
                printer_type=vs.printer_type,
                wall_thickness_mm=vs.wall_thickness_mm,
                overhang_angle_deg=vs.overhang_angle_deg,
                build_volume_mm=(
                    vs.build_x_mm,
                    vs.build_y_mm,
                    vs.build_z_mm,
                ),
                auto_repair=False,
                auto_scale=False,
                voxel_size_mm=vs.voxel_size_mm,
            )

            if quick_report.has_failures:
                # Show confirmation dialog.
                return context.window_manager.invoke_confirm(self, event)

        return self.execute(context)

    def execute(self, context):
        """Run the full export pipeline.

        Args:
            context: Blender context.

        Returns:
            ``{'FINISHED'}`` on success, ``{'CANCELLED'}`` on error.

        Implements: FR-035.
        """
        obj = context.active_object

        # SEC-001: Final mesh type verification.
        if obj is None or obj.type != "MESH":
            self.report(
                {"ERROR"},
                "No mesh object selected. Select a mesh object to validate.",
            )
            return {"CANCELLED"}

        # Verify minimum geometry.
        if len(obj.data.vertices) < 4 or len(obj.data.polygons) < 4:
            self.report(
                {"ERROR"},
                "Mesh must have at least 4 vertices and 4 faces.",
            )
            return {"CANCELLED"}

        # Get settings from scene properties.
        vs = context.scene.tessera.validator

        # Build export format set from the EnumProperty flags.
        export_formats = set(vs.export_formats)
        if not export_formats:
            export_formats = {"STL"}

        # Run the full export pipeline.
        pipeline = ExportPipeline()
        result = pipeline.execute(
            context=context,
            obj=obj,
            export_formats=export_formats,
            export_directory=vs.export_directory,
            auto_repair=vs.auto_repair,
            auto_orient=vs.auto_orient,
            auto_scale=vs.auto_scale,
            force_export=vs.force_export,
            printer_type=vs.printer_type,
            wall_thickness_mm=vs.wall_thickness_mm,
            overhang_angle_deg=vs.overhang_angle_deg,
            build_volume_mm=(
                vs.build_x_mm,
                vs.build_y_mm,
                vs.build_z_mm,
            ),
            voxel_size_mm=vs.voxel_size_mm,
        )

        # FR-031: Display summary.
        summary = result.report.to_text()

        if result.success:
            files_str = ", ".join(os.path.basename(f) for f in result.exported_files)
            summary += f"\nExported: {files_str}"
            self.report({"INFO"}, summary)
            return {"FINISHED"}
        else:
            if result.report.has_failures:
                self.report(
                    {"WARNING"},
                    summary + "\nExport cancelled due to validation failures.",
                )
            else:
                self.report({"ERROR"}, "Export failed. Check system console.")
            return {"CANCELLED"}


# Classes to register
classes = [
    TESSERA_OT_export_for_print,
]
