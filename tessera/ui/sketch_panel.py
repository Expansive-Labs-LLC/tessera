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

"""Sketch-to-3D sub-panel for Tessera.

Displays the sketch generation button, sketch detection button,
synthesis configuration, and pipeline progress feedback.

Implements: SPEC-TS-0010 UI integration.
"""

from bpy.types import Panel


class TESSERA_PT_Sketch(Panel):
    """Sketch-to-3D sub-panel (position 4 in sidebar).

    Shows the sketch-to-3D button, detect sketches button,
    synthesis settings, and pipeline progress during processing.

    Implements: SPEC-TS-0010 FR-030, FR-036.
    """

    bl_label = "Sketch to 3D"
    bl_idname = "TESSERA_PT_Sketch"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_parent_id = "TESSERA_PT_Main"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        """Draw the sketch panel layout."""
        layout = self.layout
        props = context.scene.tessera
        image_count = len(props.images)

        # Info / guidance
        if image_count == 0:
            layout.label(text="Add sketch images to begin", icon="INFO")
        elif image_count <= 2:
            layout.label(
                text=f"{image_count} image{'s' if image_count != 1 else ''} "
                f"loaded (max 2 for sketch)",
                icon="GREASEPENCIL",
            )
        else:
            layout.label(
                text=f"{image_count} images loaded (using first 2)",
                icon="GREASEPENCIL",
            )

        # Sketch generate button
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator(
            "tessera.sketch_generate",
            text="Sketch to 3D",
            icon="GREASEPENCIL",
        )

        # Detect only button
        row = layout.row(align=True)
        row.operator(
            "tessera.sketch_detect",
            text="Detect Sketches",
            icon="VIEWZOOM",
        )

        # Pipeline progress (shown during sketch processing)
        status = props.pipeline_status
        if status and ("sketch" in status.lower() or "detect" in status.lower()):
            layout.separator()
            box = layout.box()
            box.label(text=status, icon="TIME")
            if 0.0 < props.pipeline_progress <= 1.0:
                box.prop(
                    props,
                    "pipeline_progress",
                    text="Progress",
                    slider=True,
                )


# Classes to register
classes = [
    TESSERA_PT_Sketch,
]
