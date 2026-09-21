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

"""Generation settings sub-panel for Tessera.

Displays the generate button and pipeline progress feedback.

Implements: FR-004 (position 2), FR-011, FR-020.
"""

from bpy.types import Panel


class TESSERA_PT_Generation(Panel):
    """Generation sub-panel (position 2 in sidebar).

    Shows the generate button (enabled when images are loaded),
    pipeline progress bar during processing, and status messages.

    Implements: FR-004, FR-011, FR-020.
    """

    bl_label = "Generation"
    bl_idname = "TESSERA_PT_Generation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_parent_id = "TESSERA_PT_Main"
    bl_order = 2
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        """Draw the generation panel layout."""
        layout = self.layout
        props = context.scene.tessera
        image_count = len(props.images)

        # Image count indicator
        if image_count == 0:
            layout.label(text="Add reference images to begin", icon="INFO")
        else:
            layout.label(
                text=f"{image_count} image{'s' if image_count != 1 else ''} loaded",
                icon="IMAGE_DATA",
            )

        # Generate button — enabled/disabled via operator poll
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator(
            "tessera.generate",
            text="Generate 3D Model",
            icon="MESH_ICOSPHERE",
        )

        # Pipeline progress (shown during/after generation)
        if props.pipeline_status:
            layout.separator()
            box = layout.box()
            box.label(text=props.pipeline_status, icon="TIME")

            if 0.0 < props.pipeline_progress <= 1.0:
                box.prop(
                    props,
                    "pipeline_progress",
                    text="Progress",
                    slider=True,
                )


# Classes to register
classes = [
    TESSERA_PT_Generation,
]
