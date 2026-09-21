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

"""Multi-view generation sub-panel for Tessera.

Displays the multi-view generate button, preview render button,
and pipeline progress feedback.

Implements: SPEC-TS-0007 UI integration.
"""

from bpy.types import Panel


class TESSERA_PT_MultiView(Panel):
    """Multi-view generation sub-panel (position 3 in sidebar).

    Shows the multi-view generate button (enabled when ≥3 images are
    loaded), preview render button (enabled when a mesh is selected),
    and pipeline progress during processing.

    Implements: SPEC-TS-0007 FR-001, FR-028.
    """

    bl_label = "Multi-View"
    bl_idname = "TESSERA_PT_MultiView"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_parent_id = "TESSERA_PT_Main"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        """Draw the multi-view panel layout."""
        layout = self.layout
        props = context.scene.tessera
        image_count = len(props.images)

        # Info / guidance
        if image_count < 3:
            col = layout.column(align=True)
            col.label(text="Requires 3–12 images", icon="INFO")
            col.label(
                text=f"Currently: {image_count} loaded",
                icon="BLANK1",
            )
        else:
            layout.label(
                text=f"{image_count} images — multi-view ready",
                icon="OUTLINER_OB_CAMERA",
            )

        # Multi-view generate button
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator(
            "tessera.multiview_generate",
            text="Multi-View Generate",
            icon="MOD_ARRAY",
        )

        layout.separator()

        # Preview render button
        row = layout.row(align=True)
        row.operator(
            "tessera.preview_render",
            text="Render Previews",
            icon="RENDER_RESULT",
        )

        # Pipeline progress (shared with generation panel via props)
        if props.pipeline_status and "multi" in props.pipeline_status.lower():
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
    TESSERA_PT_MultiView,
]
