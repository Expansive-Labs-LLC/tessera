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

"""Print-readiness validation panel for Tessera.

Provides the ``TESSERA_PT_validation_panel`` UI panel with
validation settings and the **Validate** button.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-031, FR-033, FR-036, FR-037, FR-039.
"""

from __future__ import annotations

from bpy.types import Panel


class TESSERA_PT_validation_panel(Panel):
    """Panel for print-readiness validation settings and actions.

    Draws the Printer Type, Wall Thickness, Overhang Angle,
    Build Volume, Auto-Repair/Orient options, and the Validate button.

    Implements: FR-031, FR-033, FR-036, FR-037, FR-039.
    """

    bl_label = "Print Validation"
    bl_idname = "TESSERA_PT_validation_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_order = 40

    @classmethod
    def poll(cls, context):
        """Show panel only when a mesh object is active."""
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def draw(self, context):
        """Draw the validation panel layout.

        Args:
            context: Blender context.
        """
        layout = self.layout
        tessera = context.scene.tessera
        vs = tessera.validator

        # Printer Type (FR-033, FR-036).
        layout.prop(vs, "printer_type")

        # Validation Thresholds.
        box = layout.box()
        box.label(text="Thresholds", icon="PREFERENCES")
        box.prop(vs, "wall_thickness_mm")
        box.prop(vs, "overhang_angle_deg")

        # Build Volume.
        box = layout.box()
        box.label(text="Build Volume (mm)", icon="CUBE")
        row = box.row(align=True)
        row.prop(vs, "build_x_mm", text="X")
        row.prop(vs, "build_y_mm", text="Y")
        row.prop(vs, "build_z_mm", text="Z")

        # Options.
        box = layout.box()
        box.label(text="Options", icon="TOOL_SETTINGS")
        box.prop(vs, "auto_repair")
        box.prop(vs, "auto_orient")
        box.prop(vs, "auto_scale")
        box.prop(vs, "voxel_size_mm")

        # Validate button (FR-039).
        layout.separator()
        layout.operator(
            "tessera.validate_print",
            text="Validate for Printing",
            icon="CHECKMARK",
        )


# Classes to register
classes = [
    TESSERA_PT_validation_panel,
]
