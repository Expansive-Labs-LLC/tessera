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

"""Cleanup operators for Tessera.

Provides the ``TESSERA_OT_RunCleanup`` operator that executes
the full mesh cleanup pipeline on the active Blender object.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-008, FR-009, FR-018.
"""

from __future__ import annotations

import logging

import bpy
from bpy.types import Operator

logger = logging.getLogger("tessera.mesh")


class TESSERA_OT_RunCleanup(Operator):
    """Execute the full mesh cleanup pipeline on the active object.

    Uses a modal operator pattern per CON-008 to avoid blocking
    Blender's UI thread for more than 100ms.  The ``invoke()``
    method starts a timer-based modal loop, and ``modal()``
    processes the cleanup result.

    Implements: FR-008, FR-009, FR-018, CON-008.
    """

    bl_idname = "tessera.run_cleanup"
    bl_label = "Run Mesh Cleanup"
    bl_description = (
        "Clean up the active mesh: remove duplicates, fix normals, "
        "fill holes, and optionally remesh/decimate"
    )
    bl_options = {"REGISTER", "UNDO"}

    # Internal state for modal processing.
    _diagnostics = None
    _error_message = None
    _timer = None

    @classmethod
    def poll(cls, context):
        """Enable only when a mesh object is active."""
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def invoke(self, context, event):
        """Start the modal operator with a timer.

        Adds a modal handler and schedules a timer tick so the
        cleanup runs inside the modal loop, yielding control
        back to Blender's event system between iterations.

        Implements: CON-008.
        """
        self._diagnostics = None
        self._error_message = None

        # Add a timer (0.01s tick) to trigger modal processing.
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)

        context.workspace.status_text_set("Tessera: Starting cleanup…")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        """Process cleanup in the modal loop.

        On the first ``TIMER`` event, runs the full pipeline.
        Subsequent events report the result and finish.

        Implements: CON-008.
        """
        if event.type != "TIMER":
            return {"RUNNING_MODAL"}

        # Cancel the timer — we only need one tick.
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None

        # Run the cleanup pipeline.
        result = self._run_pipeline(context)

        context.workspace.status_text_set(None)
        return result

    def execute(self, context):
        """Fallback for scripting: run cleanup synchronously.

        When invoked via Python scripting (``bpy.ops.tessera.run_cleanup()``),
        the ``execute()`` path is used directly without modal handling.

        Implements: FR-008, FR-009, FR-018.
        """
        return self._run_pipeline(context)

    def _run_pipeline(self, context):
        """Run the cleanup pipeline and report results.

        Shared logic between ``modal()`` and ``execute()``.

        Returns:
            Blender operator result set (``FINISHED`` or ``CANCELLED``).
        """
        from ..mesh.cleanup import MeshCleanupPipeline
        from ..mesh.exceptions import MeshCleanupError

        obj = context.active_object

        # Read settings from scene properties (FR-017).
        try:
            cleanup_settings = context.scene.tessera.cleanup
            settings_kwargs = {
                "merge_distance": cleanup_settings.merge_distance,
                "voxel_size": cleanup_settings.voxel_size,
                "auto_voxel_fallback": cleanup_settings.auto_voxel_fallback,
                "enable_quad_remesh": cleanup_settings.enable_quad_remesh,
                "quad_target_faces": cleanup_settings.quad_target_faces,
                "enable_decimate": cleanup_settings.enable_decimate,
                "decimate_target_faces": cleanup_settings.decimate_target_faces,
            }
        except AttributeError:
            # Fallback to defaults if properties are not registered yet.
            settings_kwargs = {}

        pipeline = MeshCleanupPipeline()

        try:
            diagnostics = pipeline.execute(context, obj, **settings_kwargs)
        except MeshCleanupError as exc:
            self.report(
                {"ERROR"},
                f"Cleanup failed at step '{exc.step_name}': "
                f"{exc.original_exception}",
            )
            logger.error("Cleanup pipeline failed: %s", exc)
            return {"CANCELLED"}

        # FR-009: Select the cleaned object and frame in viewport.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        try:
            bpy.ops.view3d.view_selected()
        except RuntimeError:
            # May fail if no 3D viewport is open (headless mode).
            pass

        # Report results.
        if diagnostics.get("is_manifold"):
            self.report(
                {"INFO"},
                f"Cleanup complete — manifold: "
                f"{diagnostics['vertices_after']} verts, "
                f"{diagnostics['faces_after']} faces "
                f"({diagnostics['cleanup_time_seconds']:.2f}s)",
            )
        else:
            self.report(
                {"WARNING"},
                f"Cleanup finished but mesh is NOT manifold. "
                f"Consider enabling voxel remesh fallback.",
            )

        return {"FINISHED"}


# Classes to register
classes = [
    TESSERA_OT_RunCleanup,
]
