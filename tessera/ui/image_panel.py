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

"""Image Input sub-panel for Tessera.

Provides the UIList for uploaded images with view label assignment,
add/remove/reorder controls.

Implements: FR-004 (position 1), FR-005, FR-006, FR-013, FR-014, EC-004.
"""

import bpy
from bpy.types import Panel, UIList


class TESSERA_UL_ImageList(UIList):
    """Custom UIList for displaying Tessera reference images.

    Shows the image filename alongside its assigned view label.

    Implements: FR-006.
    """

    bl_idname = "TESSERA_UL_ImageList"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_property, index
    ):
        """Draw a single image list item.

        Args:
            item: A TesseraImageItem PropertyGroup instance.
        """
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            # Image name
            row.label(text=item.name, icon="IMAGE_DATA")
            # View label dropdown (FR-006)
            row.prop(item, "view_label", text="")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=item.name, icon="IMAGE_DATA")


class TESSERA_PT_ImageInput(Panel):
    """Image Input sub-panel (position 1 in sidebar).

    Displays the image list and add/remove/reorder controls.

    Implements: FR-004, FR-005, FR-006, FR-013, FR-014, EC-004.
    """

    bl_label = "Image Input"
    bl_idname = "TESSERA_PT_ImageInput"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_parent_id = "TESSERA_PT_Main"
    bl_order = 1

    def draw(self, context):
        """Draw the image input panel layout."""
        layout = self.layout
        props = context.scene.tessera

        # EC-004: Empty image list placeholder
        if len(props.images) == 0:
            col = layout.column()
            col.alignment = "CENTER"
            col.label(text="No images added. Click 'Add Image' to begin.")
            col.separator()
            col.operator("tessera.add_image", text="Add Image", icon="ADD")
            return

        # FR-006: UIList with image entries
        row = layout.row()
        row.template_list(
            "TESSERA_UL_ImageList",
            "",
            props,
            "images",
            props,
            "active_image_index",
            rows=3,
            maxrows=8,
        )

        # Side buttons column (add, remove, move up/down)
        col = row.column(align=True)
        col.operator("tessera.add_image", text="", icon="ADD")
        col.operator("tessera.remove_image", text="", icon="REMOVE")
        col.separator()
        col.operator("tessera.move_image_up", text="", icon="TRIA_UP")
        col.operator("tessera.move_image_down", text="", icon="TRIA_DOWN")

        # Show selected image details
        if props.active_image_index < len(props.images):
            item = props.images[props.active_image_index]
            box = layout.box()
            box.label(text=f"File: {item.name}", icon="FILE_IMAGE")
            box.prop(item, "view_label", text="View")


# Classes to register
classes = [
    TESSERA_UL_ImageList,
    TESSERA_PT_ImageInput,
]
