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

"""Scaling & Orientation settings panel for Tessera.

Sub-panel of the main Tessera sidebar panel that exposes dimension
input, printer profile selection, and orientation optimization controls.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-031, FR-032.
"""

from __future__ import annotations

import bpy
from bpy.types import Panel


class TESSERA_PT_Scaling(Panel):
    """Scaling & Orientation sub-panel in the Tessera sidebar.

    Provides controls for:
    - Target dimension input (width, height, depth in mm)
    - Auto-inference toggle and object class label
    - Printer profile selection
    - Custom printer dimensions (when profile is "Custom")
    - Orientation optimizer settings
    - Action buttons for scaling, orientation, and inference

    Implements: FR-031, FR-032.
    """

    bl_label = "Scaling & Orientation"
    bl_idname = "TESSERA_PT_Scaling"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_parent_id = "TESSERA_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        """Show only when a mesh object is active."""
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def draw(self, context):
        """Draw the scaling and orientation panel."""
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        try:
            settings = context.scene.tessera.scaling
        except AttributeError:
            layout.label(text="Scaling settings not available.")
            return

        # --- Target Dimensions ---
        box = layout.box()
        box.label(text="Target Dimensions", icon="ARROW_LEFTRIGHT")

        col = box.column(align=True)
        col.prop(settings, "target_width_mm")
        col.prop(settings, "target_height_mm")
        col.prop(settings, "target_depth_mm")

        # Auto-inference section.
        row = box.row()
        row.prop(settings, "auto_infer")

        if settings.auto_infer:
            col = box.column(align=True)
            col.prop(settings, "object_class_label")
            col.operator(
                "tessera.infer_dimensions",
                text="Suggest Dimensions",
                icon="QUESTION",
            )

        # --- Printer Profile ---
        box = layout.box()
        box.label(text="Printer Profile", icon="MODIFIER")

        box.prop(settings, "printer_profile")

        # Show custom fields when "Custom" is selected.
        if settings.printer_profile == "CUSTOM":
            col = box.column(align=True)
            col.prop(settings, "custom_build_width_mm")
            col.prop(settings, "custom_build_depth_mm")
            col.prop(settings, "custom_build_height_mm")
            col.prop(settings, "custom_technology")

        # --- Orientation Settings ---
        box = layout.box()
        box.label(text="Orientation", icon="ORIENTATION_NORMAL")

        box.prop(settings, "enable_orientation")

        if settings.enable_orientation:
            col = box.column(align=True)
            col.prop(settings, "overhang_threshold_deg")
            col.prop(settings, "enable_fine_tuning")

        # --- Action Buttons ---
        layout.separator()

        col = layout.column(align=True)
        col.scale_y = 1.4
        col.operator(
            "tessera.apply_scaling",
            text="Apply Scaling & Orientation",
            icon="MOD_MESHDEFORM",
        )

        row = layout.row(align=True)
        row.operator(
            "tessera.optimize_orientation",
            text="Orientation Only",
            icon="ORIENTATION_NORMAL",
        )


# Classes to register.
classes = [
    TESSERA_PT_Scaling,
]
