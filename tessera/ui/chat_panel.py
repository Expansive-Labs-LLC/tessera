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

"""Refinement chat panel in the 3D Viewport sidebar.

Provides the chat UI for the natural-language refinement loop,
including message history display, text input, undo/redo buttons,
and confirmation prompts.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006,
            AC-008.
"""

import bpy
from bpy.types import Panel


class TESSERA_PT_Refinement(Panel):
    """Refinement chat panel in the Tessera sidebar.

    Displays the chat message history, text input field, and
    contextual action buttons (send, undo, redo, confirm).

    Sub-panel of the main Tessera panel.

    Implements: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006.
    """

    bl_label = "Refinement Chat"
    bl_idname = "TESSERA_PT_Refinement"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_parent_id = "TESSERA_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        """Draw the refinement chat panel."""
        layout = self.layout
        scene = context.scene

        try:
            settings = scene.tessera.refinement
        except AttributeError:
            layout.label(text="Refinement not initialized", icon="ERROR")
            return

        obj = context.active_object

        # FR-006 / AC-008: Show warning when no mesh is selected.
        if obj is None or obj.type != "MESH":
            box = layout.box()
            col = box.column(align=True)
            col.alert = True
            col.label(text="Select a mesh object to use", icon="INFO")
            col.label(text="the refinement chat.")
            return

        # --- Message History (FR-002) ---
        self._draw_message_history(layout, context)

        # --- Status Indicator (FR-004) ---
        if settings.is_processing:
            row = layout.row()
            row.alignment = "CENTER"
            row.label(text="Thinking…", icon="SORTTIME")

        if settings.status_message:
            row = layout.row()
            row.alignment = "CENTER"
            row.label(text=settings.status_message, icon="INFO")

        # --- Confirmation Buttons (FR-017, FR-018) ---
        if settings.awaiting_confirmation:
            row = layout.row(align=True)
            row.operator(
                "tessera.confirm_edit",
                text="Confirm",
                icon="CHECKMARK",
            )
            return

        # --- Selection Confirmation (FR-016) ---
        if settings.awaiting_selection:
            row = layout.row(align=True)
            row.operator(
                "tessera.confirm_selection",
                text="Confirm Selection",
                icon="RESTRICT_SELECT_OFF",
            )
            return

        # --- Text Input + Send (FR-005) ---
        row = layout.row(align=True)
        row.prop(settings, "chat_input", text="")
        row.operator(
            "tessera.send_message",
            text="",
            icon="PLAY",
        )

        # --- Undo/Redo Buttons (FR-029) ---
        row = layout.row(align=True)
        row.operator(
            "tessera.undo_edit",
            text="Undo",
            icon="LOOP_BACK",
        )
        row.operator(
            "tessera.redo_edit",
            text="Redo",
            icon="LOOP_FORWARDS",
        )

    def _draw_message_history(self, layout, context):
        """Draw the scrollable message history.

        FR-002: Shows user and assistant messages with role indicators.
        FR-003: Displays inline preview thumbnails for assistant messages.

        Args:
            layout: Blender UI layout.
            context: Blender context.
        """
        from ..operators.refinement_ops import _chat_manager

        if _chat_manager is None or _chat_manager.message_count == 0:
            box = layout.box()
            col = box.column(align=True)
            col.scale_y = 0.8
            col.label(text="Type a command to edit your mesh.")
            col.label(text="Examples:")
            col.label(text="  • 'Make it 20% taller'")
            col.label(text="  • 'Smooth the top'")
            col.label(text="  • 'Add a handle on the right'")
            return

        # Draw messages in a scrollable box.
        box = layout.box()
        col = box.column(align=True)

        # Show last 10 messages to keep the panel manageable.
        messages = _chat_manager.get_messages()
        visible = messages[-10:]

        if len(messages) > 10:
            col.label(
                text=f"({len(messages) - 10} earlier messages)",
                icon="TRIA_UP",
            )

        for msg in visible:
            row = col.row()
            row.scale_y = 0.8

            if msg.role == "user":
                row.label(text=f"You: {msg.text}", icon="USER")
            elif msg.role == "assistant":
                # FR-003: Show preview thumbnail if available.
                if msg.image_name:
                    img = bpy.data.images.get(msg.image_name)
                    if img is not None:
                        row.template_icon(
                            icon_value=img.preview.icon_id
                            if img.preview
                            else 0,
                            scale=2.0,
                        )

                # Version badge (FR-030).
                version_str = f" [v{msg.version}]" if msg.version is not None else ""

                # Split long messages across lines.
                lines = msg.text.split("\n")
                for i, line in enumerate(lines):
                    if i == 0:
                        row.label(
                            text=f"AI: {line}{version_str}",
                            icon="OUTLINER_OB_FONT",
                        )
                    else:
                        sub = col.row()
                        sub.scale_y = 0.8
                        sub.label(text=f"    {line}")
            elif msg.role == "system":
                row.label(text=msg.text, icon="INFO")


# Classes to register
classes = [
    TESSERA_PT_Refinement,
]
