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

"""Operators for the natural-language refinement loop.

Handles the full edit cycle: send message → background LLM → parse →
resolve → confirm → execute → preview → respond.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-005, FR-006, FR-016, FR-017, FR-018, FR-029,
            CON-002, CON-006.
"""

from __future__ import annotations

import logging
import queue
import threading

import bpy
from bpy.types import Operator

from ..addon import get_addon_preferences

logger = logging.getLogger("tessera.refinement")

# ---------------------------------------------------------------------------
# Module-level state (per-session singletons)
# ---------------------------------------------------------------------------

_chat_manager = None
_undo_manager = None
_edit_executor = None
_preview_renderer = None
_result_queue: queue.Queue = queue.Queue()

# Pending state for confirmation / selection flows.
_pending_intents: list = []
_pending_vertex_group: str = ""
_pending_obj_name: str = ""


def _get_or_create_managers():
    """Lazily initialize module-level manager singletons."""
    global _chat_manager, _undo_manager, _edit_executor, _preview_renderer

    if _chat_manager is None:
        from ..refinement.chat_manager import ChatManager

        _chat_manager = ChatManager()

    if _undo_manager is None:
        from ..refinement.undo_manager import UndoManager

        _undo_manager = UndoManager()

    if _edit_executor is None:
        from ..refinement.edit_executor import EditExecutor

        _edit_executor = EditExecutor(_undo_manager)

    if _preview_renderer is None:
        from ..refinement.preview_renderer import PreviewRenderer

        _preview_renderer = PreviewRenderer()

    return _chat_manager, _undo_manager, _edit_executor, _preview_renderer


def _create_llm_backend():
    """Create an LLM backend based on user preferences.

    Returns:
        An ``LLMBackend`` instance (local or API).
    """
    try:
        prefs = get_addon_preferences()
        if prefs is None:
            return None
        backend_type = prefs.llm_backend
    except (KeyError, AttributeError):
        backend_type = "LOCAL"

    if backend_type == "API":
        from ..refinement.llm_backend import APILLMBackend

        try:
            prefs = get_addon_preferences()
            return APILLMBackend(
                endpoint=prefs.llm_api_endpoint,
                api_key=prefs.llm_api_key,
                model_name=prefs.llm_api_model,
            )
        except Exception as exc:
            logger.error("Failed to create API backend: %s", exc)
            # Fall through to local.

    from ..refinement.llm_backend import LocalLLMBackend

    return LocalLLMBackend()


def _get_mesh_context(obj):
    """Build mesh context dict for the intent parser.

    CON-001: Only includes bounding box, vertex group names,
    and face count — no raw geometry data.

    Args:
        obj: Blender mesh object.

    Returns:
        Dict with ``bounding_box_mm``, ``vertex_groups``, ``face_count``.
    """
    try:
        dims = obj.dimensions
        bb = {
            "x": dims.x * 1000,
            "y": dims.y * 1000,
            "z": dims.z * 1000,
        }
    except (AttributeError, TypeError):
        bb = {"x": 0, "y": 0, "z": 0}

    try:
        vgroups = [vg.name for vg in obj.vertex_groups]
    except (AttributeError, TypeError):
        vgroups = []

    try:
        face_count = len(obj.data.polygons)
    except (AttributeError, TypeError):
        face_count = 0

    return {
        "bounding_box_mm": bb,
        "vertex_groups": vgroups,
        "face_count": face_count,
    }


def _llm_thread_func(command, mesh_context, message_history, result_queue):
    """Background thread function for LLM inference.

    CON-002: No ``bpy`` access occurs in this thread.
    CON-006: Results are placed on a queue for the main thread timer.

    Args:
        command: User's text command.
        mesh_context: Mesh context dict.
        message_history: LLM-formatted message history.
        result_queue: Queue for returning results to main thread.
    """
    try:
        backend = _create_llm_backend()
        from ..refinement.intent_parser import IntentParser

        parser = IntentParser(backend)
        result = parser.parse(command, mesh_context, message_history)
        result_queue.put(("intents", result))
    except Exception as exc:
        logger.error("LLM thread error: %s", exc)
        result_queue.put(("error", str(exc)))


def _poll_llm_result():
    """Timer callback to poll for LLM results on the main thread.

    CON-002, CON-006: All ``bpy`` operations execute here on the
    main thread. Called by ``bpy.app.timers``.

    Returns:
        ``None`` to unregister, or interval in seconds to continue polling.
    """
    global _pending_intents, _pending_vertex_group, _pending_obj_name

    try:
        msg_type, data = _result_queue.get_nowait()
    except queue.Empty:
        return 0.1  # Keep polling.

    chat, undo, executor, renderer = _get_or_create_managers()
    scene = bpy.context.scene
    settings = scene.tessera.refinement
    settings.is_processing = False

    if msg_type == "error":
        chat.add_message("assistant", f"Sorry, I encountered an error: {data}")
        settings.status_message = ""
        return None

    # msg_type == "intents"
    from ..refinement.intent_schema import AmbiguityResponse

    if isinstance(data, AmbiguityResponse):
        # FR-017: Ambiguity response.
        if data.candidates:
            lines = ["I'm not sure what you mean. Did you want to:"]
            for i, (desc, conf) in enumerate(data.candidates, 1):
                lines.append(f"  {i}. {desc} (confidence: {conf:.0%})")
            lines.append("Please clarify your command.")
            chat.add_message("assistant", "\n".join(lines))
        else:
            # EC-005: Completely unrecognized command.
            chat.add_message(
                "assistant",
                "I didn't understand that command. Try something like "
                "'make it 20% taller' or 'smooth the top'.",
            )
        settings.status_message = ""
        return None

    # We have a list of EditIntent objects.
    intents = data
    obj = bpy.context.active_object

    if obj is None or obj.type != "MESH":
        chat.add_message("assistant", "No mesh object selected.")
        settings.status_message = ""
        return None

    # Process intents sequentially.
    from ..refinement.region_resolver import RegionResolver

    resolver = RegionResolver()

    for intent in intents:
        # Resolve target region.
        region_result = resolver.resolve(intent.target_region, obj)

        if region_result.method == "user_selection":
            # FR-016: Prompt for user vertex selection.
            _pending_intents = intents
            _pending_obj_name = obj.name
            settings.awaiting_selection = True
            chat.add_message(
                "assistant",
                f"I couldn't identify '{intent.target_region}' on the mesh. "
                f"Please select the target vertices and click 'Confirm Selection'.",
            )
            settings.status_message = "Select vertices…"
            return None

        vg_name = region_result.vertex_group_name

        # Create spatial vertex group on mesh if needed.
        if region_result.method == "spatial_heuristic":
            created = resolver.create_selection_from_spatial(obj, intent.target_region)
            if created:
                vg_name = created

        # FR-018: Check for large edit confirmation.
        confirm_msg = executor.needs_confirmation(intent, obj, vg_name)
        if confirm_msg:
            _pending_intents = [intent]
            _pending_vertex_group = vg_name
            _pending_obj_name = obj.name
            settings.awaiting_confirmation = True
            chat.add_message("assistant", confirm_msg)
            settings.status_message = "Awaiting confirmation…"
            return None

        # Execute the edit.
        result = executor.execute(bpy.context, obj, intent, vg_name)

        if result.success:
            msg = result.description
            if result.warning:
                msg += f"\n⚠️ {result.warning}"
            version = undo.current_version
            # Render preview.
            image_name = renderer.render(obj)
            renderer.cleanup_old_previews()
            chat.add_message("assistant", msg, image_name=image_name, version=version)
        else:
            chat.add_message("assistant", f"❌ {result.description}")

    settings.status_message = ""
    return None


class TESSERA_OT_send_message(Operator):
    """Send a natural-language edit command.

    Spawns a background thread for LLM inference and registers
    a timer callback for main-thread execution.

    Implements: FR-005, CON-002, CON-006.
    """

    bl_idname = "tessera.send_message"
    bl_label = "Send Message"
    bl_description = "Send a natural-language edit command"

    @classmethod
    def poll(cls, context):
        """FR-006: Disabled when no mesh is selected or processing."""
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            return False
        try:
            settings = context.scene.tessera.refinement
            if settings.is_processing:
                return False
            if not settings.chat_input.strip():
                return False
        except (AttributeError, TypeError):
            return False
        return True

    def execute(self, context):
        """Launch the refinement pipeline."""
        settings = context.scene.tessera.refinement
        command = settings.chat_input.strip()

        if not command:
            self.report({"WARNING"}, "No command entered")
            return {"CANCELLED"}

        chat, undo, executor, renderer = _get_or_create_managers()

        # Start session if not active.
        if not chat.is_active:
            chat.start_session()
            settings.session_active = True
            # Push initial undo snapshot.
            obj = context.active_object
            undo.push(obj, "Initial state")

        # Add user message.
        chat.add_message("user", command)
        settings.chat_input = ""
        settings.is_processing = True
        settings.status_message = "Thinking…"

        # Build context (main thread — safe).
        obj = context.active_object
        mesh_context = _get_mesh_context(obj)
        message_history = chat.get_llm_history()

        # Launch background thread (CON-002).
        thread = threading.Thread(
            target=_llm_thread_func,
            args=(command, mesh_context, message_history, _result_queue),
            daemon=True,
        )
        thread.start()

        # Register timer to poll results (CON-006).
        if not bpy.app.timers.is_registered(_poll_llm_result):
            bpy.app.timers.register(_poll_llm_result, first_interval=0.1)

        return {"FINISHED"}


class TESSERA_OT_undo_edit(Operator):
    """Undo the last refinement edit.

    Implements: FR-029.
    """

    bl_idname = "tessera.undo_edit"
    bl_label = "Undo Edit"
    bl_description = "Undo the last refinement edit"

    @classmethod
    def poll(cls, context):
        if _undo_manager is None:
            return False
        return _undo_manager.can_undo

    def execute(self, context):
        chat, undo, executor, renderer = _get_or_create_managers()
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "No mesh selected")
            return {"CANCELLED"}

        try:
            from_v = undo.current_version
            undo.undo(obj)
            to_v = undo.current_version
            image_name = renderer.render(obj)
            renderer.cleanup_old_previews()
            chat.add_message(
                "assistant",
                f"⟲ Undone (v{from_v} → v{to_v})",
                image_name=image_name,
                version=to_v,
            )
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        return {"FINISHED"}


class TESSERA_OT_redo_edit(Operator):
    """Redo the last undone refinement edit.

    Implements: FR-029.
    """

    bl_idname = "tessera.redo_edit"
    bl_label = "Redo Edit"
    bl_description = "Redo the last undone refinement edit"

    @classmethod
    def poll(cls, context):
        if _undo_manager is None:
            return False
        return _undo_manager.can_redo

    def execute(self, context):
        chat, undo, executor, renderer = _get_or_create_managers()
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "No mesh selected")
            return {"CANCELLED"}

        try:
            from_v = undo.current_version
            undo.redo(obj)
            to_v = undo.current_version
            image_name = renderer.render(obj)
            renderer.cleanup_old_previews()
            chat.add_message(
                "assistant",
                f"⟳ Redone (v{from_v} → v{to_v})",
                image_name=image_name,
                version=to_v,
            )
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        return {"FINISHED"}


class TESSERA_OT_confirm_edit(Operator):
    """Confirm a pending edit operation.

    FR-018: Confirms large-edit or ambiguity prompt.

    Implements: FR-017, FR-018.
    """

    bl_idname = "tessera.confirm_edit"
    bl_label = "Confirm"
    bl_description = "Confirm the pending edit operation"

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.tessera.refinement.awaiting_confirmation
        except (AttributeError, TypeError):
            return False

    def execute(self, context):
        global _pending_intents, _pending_vertex_group, _pending_obj_name

        chat, undo, executor, renderer = _get_or_create_managers()
        settings = context.scene.tessera.refinement
        settings.awaiting_confirmation = False

        obj = bpy.data.objects.get(_pending_obj_name)
        if obj is None:
            chat.add_message("assistant", "Object no longer exists.")
            return {"CANCELLED"}

        for intent in _pending_intents:
            result = executor.execute(context, obj, intent, _pending_vertex_group)
            if result.success:
                msg = result.description
                if result.warning:
                    msg += f"\n⚠️ {result.warning}"
                image_name = renderer.render(obj)
                renderer.cleanup_old_previews()
                chat.add_message(
                    "assistant",
                    msg,
                    image_name=image_name,
                    version=undo.current_version,
                )
            else:
                chat.add_message("assistant", f"❌ {result.description}")

        _pending_intents = []
        _pending_vertex_group = ""
        _pending_obj_name = ""
        settings.status_message = ""

        return {"FINISHED"}


class TESSERA_OT_confirm_selection(Operator):
    """Confirm user vertex selection for region resolution.

    FR-016, EC-003: Uses the current vertex selection as the
    target region.

    Implements: FR-016, EC-003.
    """

    bl_idname = "tessera.confirm_selection"
    bl_label = "Confirm Selection"
    bl_description = "Use current vertex selection as target region"

    @classmethod
    def poll(cls, context):
        try:
            return context.scene.tessera.refinement.awaiting_selection
        except (AttributeError, TypeError):
            return False

    def execute(self, context):
        global _pending_intents, _pending_obj_name

        chat, undo, executor, renderer = _get_or_create_managers()
        settings = context.scene.tessera.refinement
        settings.awaiting_selection = False

        obj = bpy.data.objects.get(_pending_obj_name)
        if obj is None:
            chat.add_message("assistant", "Object no longer exists.")
            return {"CANCELLED"}

        from ..refinement.region_resolver import RegionResolver

        resolver = RegionResolver()
        vg_name = resolver.create_user_selection_group(obj)

        for intent in _pending_intents:
            result = executor.execute(context, obj, intent, vg_name)
            if result.success:
                msg = result.description
                if result.warning:
                    msg += f"\n⚠️ {result.warning}"
                image_name = renderer.render(obj)
                renderer.cleanup_old_previews()
                chat.add_message(
                    "assistant",
                    msg,
                    image_name=image_name,
                    version=undo.current_version,
                )
            else:
                chat.add_message("assistant", f"❌ {result.description}")

        _pending_intents = []
        _pending_obj_name = ""
        settings.status_message = ""

        return {"FINISHED"}


# Classes to register
classes = [
    TESSERA_OT_send_message,
    TESSERA_OT_undo_edit,
    TESSERA_OT_redo_edit,
    TESSERA_OT_confirm_edit,
    TESSERA_OT_confirm_selection,
]
