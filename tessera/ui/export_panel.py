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

"""Export panel for Tessera.

Provides the ``TESSERA_PT_export_panel`` UI panel with export
format selection, directory, and the **Export** button.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-021, FR-022, FR-031, FR-035, FR-037, FR-038.
"""

from __future__ import annotations

from bpy.types import Panel


class TESSERA_PT_export_panel(Panel):
    """Panel for print-ready export settings and actions.

    Draws the Export Formats, Export Directory, Force Export toggle,
    and the Export button.

    Implements: FR-021, FR-022, FR-031, FR-035, FR-037, FR-038.
    """

    bl_label = "Print Export"
    bl_idname = "TESSERA_PT_export_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_order = 41

    @classmethod
    def poll(cls, context):
        """Show panel only when a mesh object is active."""
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def draw(self, context):
        """Draw the export panel layout.

        Args:
            context: Blender context.
        """
        layout = self.layout
        tessera = context.scene.tessera
        vs = tessera.validator

        # Export Formats (FR-021).
        box = layout.box()
        box.label(text="Export Formats", icon="EXPORT")
        box.prop(vs, "export_formats")

        # Export Directory (FR-022).
        box = layout.box()
        box.label(text="Export Directory", icon="FILE_FOLDER")
        box.prop(vs, "export_directory", text="")

        # Force Export (FR-038).
        layout.prop(vs, "force_export")

        # Export button (FR-035).
        layout.separator()
        layout.operator(
            "tessera.export_for_print",
            text="Export for Printing",
            icon="FILE_TICK",
        )


# Classes to register
classes = [
    TESSERA_PT_export_panel,
]
