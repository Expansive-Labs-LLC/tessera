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

"""Cleanup settings sub-panel for Tessera.

Displays mesh cleanup configuration in the 3D Viewport sidebar
under the Tessera tab, with Phase 1 settings always visible and
Phase 2 settings in a collapsible section.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-017 (UI exposure of cleanup settings).
"""

import bpy
from bpy.types import Panel


class TESSERA_PT_Cleanup(Panel):
    """Mesh cleanup settings sub-panel.

    Appears under the main Tessera panel in the 3D Viewport sidebar.
    Provides controls for the cleanup pipeline settings and a button
    to run the pipeline operator.

    Implements: FR-017.
    """

    bl_label = "Mesh Cleanup"
    bl_idname = "TESSERA_PT_Cleanup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_parent_id = "TESSERA_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        """Draw the cleanup settings panel layout."""
        layout = self.layout

        try:
            cleanup = context.scene.tessera.cleanup
        except AttributeError:
            layout.label(text="Cleanup settings not available")
            return

        # --- Phase 1 Settings ---
        box = layout.box()
        box.label(text="Phase 1 — Repair", icon="MOD_MESHDEFORM")

        col = box.column(align=True)
        col.prop(cleanup, "merge_distance", text="Merge Distance")
        col.prop(cleanup, "voxel_size", text="Voxel Size")
        col.prop(
            cleanup, "auto_voxel_fallback", text="Auto Voxel Fallback"
        )

        layout.separator()

        # --- Phase 2 Settings ---
        box = layout.box()
        box.label(text="Phase 2 — Topology", icon="MOD_REMESH")

        col = box.column(align=True)
        row = col.row()
        row.prop(cleanup, "enable_quad_remesh", text="Quad Remesh")
        sub = col.column(align=True)
        sub.enabled = cleanup.enable_quad_remesh
        sub.prop(cleanup, "quad_target_faces", text="Target Faces")

        col.separator()

        row = col.row()
        row.prop(cleanup, "enable_decimate", text="Decimate")
        sub = col.column(align=True)
        sub.enabled = cleanup.enable_decimate
        sub.prop(
            cleanup, "decimate_target_faces", text="Target Faces"
        )

        layout.separator()

        # --- Run Button ---
        layout.operator(
            "tessera.run_cleanup",
            text="Run Cleanup",
            icon="MESH_DATA",
        )


# Classes to register
classes = [
    TESSERA_PT_Cleanup,
]
