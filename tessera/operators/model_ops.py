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

"""Model management operators for Tessera.

Provides operators for downloading, deleting, and updating model weights.
All download operations run in background threads with progress
polling via ``bpy.app.timers`` (CON-003).

Implements: FR-009, FR-010, FR-016, FR-017.
"""

import logging

import bpy
from bpy.props import StringProperty
from bpy.types import Operator

logger = logging.getLogger("tessera.models")

# Timer interval for progress queue polling (FR-004: 100ms)
_TIMER_INTERVAL = 0.1


def _get_download_manager():
    """Get the global download manager, or None if not initialized."""
    from ..models.download_manager import get_global_download_manager

    return get_global_download_manager()


def _get_cache_manager():
    """Get the global cache manager, or None if not initialized."""
    from ..models.cache_manager import get_global_cache_manager

    return get_global_cache_manager()


def _poll_download_progress():
    """Timer callback to poll the download progress queue.

    Runs on the main thread at 100ms intervals (FR-004).
    Updates scene properties that the UI reads (CON-003).

    Returns:
        float or None: Timer interval to continue polling,
            or None to stop the timer.
    """
    dm = _get_download_manager()
    if dm is None:
        return None

    # Drain the queue
    latest_progress = None
    while not dm.progress_queue.empty():
        try:
            latest_progress = dm.progress_queue.get_nowait()
        except Exception:
            break

    if latest_progress is not None:
        # Store progress in window manager custom props for UI access
        # (CON-003: safe bpy access from main thread timer)
        wm = bpy.context.window_manager
        wm["tessera_dl_model_id"] = latest_progress.get("model_id", "")
        wm["tessera_dl_bytes"] = latest_progress.get("bytes_downloaded", 0)
        wm["tessera_dl_total"] = latest_progress.get("total_bytes", 0)
        wm["tessera_dl_speed"] = latest_progress.get("speed_bps", 0.0)
        wm["tessera_dl_eta"] = latest_progress.get("eta_seconds", 0.0)
        wm["tessera_dl_status"] = latest_progress.get("status", "")
        wm["tessera_dl_error"] = latest_progress.get("error", "")
        wm["tessera_dl_vram_warning"] = latest_progress.get(
            "vram_warning", ""
        ) or ""

        status = latest_progress.get("status", "")
        if status in ("completed", "error", "all_completed"):
            # Redraw UI one last time
            for area in bpy.context.screen.areas:
                if area.type in ("VIEW_3D", "PREFERENCES"):
                    area.tag_redraw()

            if status == "error":
                error_msg = latest_progress.get("error", "Unknown error")
                logger.error(
                    "Download failed: model=%s, error=%s",
                    latest_progress.get("model_id"),
                    error_msg,
                )

            # Stop polling if no more downloads
            if not dm.is_downloading:
                _cleanup_download_props()
                return None

        # Request UI redraw
        for area in bpy.context.screen.areas:
            if area.type in ("VIEW_3D", "PREFERENCES"):
                area.tag_redraw()

    # Continue polling if download is active
    if dm.is_downloading:
        return _TIMER_INTERVAL
    else:
        _cleanup_download_props()
        return None


def _cleanup_download_props():
    """Remove temporary download progress properties from window manager."""
    wm = bpy.context.window_manager
    for key in (
        "tessera_dl_model_id",
        "tessera_dl_bytes",
        "tessera_dl_total",
        "tessera_dl_speed",
        "tessera_dl_eta",
        "tessera_dl_status",
        "tessera_dl_error",
        "tessera_dl_vram_warning",
    ):
        if key in wm:
            del wm[key]


class TESSERA_OT_DownloadModel(Operator):
    """Download a single model's weights.

    Starts a background download thread and registers a timer
    for progress polling.

    Implements: FR-010.
    """

    bl_idname = "tessera.download_model"
    bl_label = "Download Model"
    bl_description = "Download model weights from HuggingFace"
    bl_options = {"REGISTER"}

    model_id: StringProperty(
        name="Model ID",
        description="Unique model identifier from manifest",
        default="",
    )  # type: ignore[assignment]

    def execute(self, context):
        """Start background download for a single model."""
        dm = _get_download_manager()
        if dm is None:
            self.report(
                {"ERROR"},
                "Model management not initialized. "
                "Please check the Tessera add-on installation.",
            )
            return {"CANCELLED"}

        if not self.model_id:
            self.report({"ERROR"}, "No model_id specified.")
            return {"CANCELLED"}

        if dm.is_downloading:
            self.report(
                {"WARNING"},
                "A download is already in progress. "
                "Please wait for it to complete.",
            )
            return {"CANCELLED"}

        # Start background download (FR-003, CON-003)
        dm.start_background_download(self.model_id)

        # Register timer for progress polling (FR-004)
        bpy.app.timers.register(
            _poll_download_progress,
            first_interval=_TIMER_INTERVAL,
        )

        self.report({"INFO"}, f"Downloading model: {self.model_id}")
        return {"FINISHED"}


class TESSERA_OT_DownloadAllModels(Operator):
    """Download all required model weights.

    Initiates sequential download of all models marked as
    "Not Downloaded".

    Implements: FR-009.
    """

    bl_idname = "tessera.download_all_models"
    bl_label = "Download All Required"
    bl_description = "Download all missing model weights"
    bl_options = {"REGISTER"}

    def execute(self, context):
        """Start sequential background download of all missing models."""
        dm = _get_download_manager()
        if dm is None:
            self.report(
                {"ERROR"},
                "Model management not initialized.",
            )
            return {"CANCELLED"}

        if dm.is_downloading:
            self.report(
                {"WARNING"},
                "A download is already in progress.",
            )
            return {"CANCELLED"}

        # Start background download-all (FR-009)
        dm.start_download_all_missing()

        # Register timer for progress polling (FR-004)
        bpy.app.timers.register(
            _poll_download_progress,
            first_interval=_TIMER_INTERVAL,
        )

        self.report({"INFO"}, "Downloading all required models...")
        return {"FINISHED"}


class TESSERA_OT_ClearModelCache(Operator):
    """Delete a specific model's cached files.

    Implements: FR-010.
    """

    bl_idname = "tessera.clear_model_cache"
    bl_label = "Delete Model"
    bl_description = "Delete cached model files to free disk space"
    bl_options = {"REGISTER"}

    model_id: StringProperty(
        name="Model ID",
        description="Model to delete",
        default="",
    )  # type: ignore[assignment]

    def execute(self, context):
        """Delete the specified model's cache."""
        cm = _get_cache_manager()
        if cm is None:
            self.report({"ERROR"}, "Cache manager not initialized.")
            return {"CANCELLED"}

        if not self.model_id:
            self.report({"ERROR"}, "No model_id specified.")
            return {"CANCELLED"}

        freed = cm.delete_model(self.model_id)
        freed_mb = freed / (1024 ** 2)
        self.report({"INFO"}, f"Deleted {self.model_id} ({freed_mb:.1f} MB freed)")

        # Redraw preferences
        for area in context.screen.areas:
            if area.type == "PREFERENCES":
                area.tag_redraw()

        return {"FINISHED"}

    def invoke(self, context, event):
        """Show confirmation dialog before deleting."""
        return context.window_manager.invoke_confirm(self, event)


class TESSERA_OT_UpdateModel(Operator):
    """Update a model to the latest manifest revision.

    Downloads the new version and removes old cached files.

    Implements: FR-016 (SHOULD).
    """

    bl_idname = "tessera.update_model"
    bl_label = "Update Model"
    bl_description = "Download the latest version of this model"
    bl_options = {"REGISTER"}

    model_id: StringProperty(
        name="Model ID",
        description="Model to update",
        default="",
    )  # type: ignore[assignment]

    def execute(self, context):
        """Delete old version and re-download."""
        dm = _get_download_manager()
        cm = _get_cache_manager()

        if dm is None or cm is None:
            self.report({"ERROR"}, "Model management not initialized.")
            return {"CANCELLED"}

        if not self.model_id:
            self.report({"ERROR"}, "No model_id specified.")
            return {"CANCELLED"}

        if dm.is_downloading:
            self.report({"WARNING"}, "A download is already in progress.")
            return {"CANCELLED"}

        # Delete existing cache
        cm.delete_model(self.model_id)

        # Start fresh download
        dm.start_background_download(self.model_id)
        bpy.app.timers.register(
            _poll_download_progress,
            first_interval=_TIMER_INTERVAL,
        )

        self.report({"INFO"}, f"Updating model: {self.model_id}")
        return {"FINISHED"}


class TESSERA_OT_CancelDownload(Operator):
    """Cancel the active model download."""

    bl_idname = "tessera.cancel_download"
    bl_label = "Cancel Download"
    bl_description = "Cancel the currently active download"
    bl_options = {"REGISTER"}

    def execute(self, context):
        """Signal the download to cancel."""
        dm = _get_download_manager()
        if dm is None:
            return {"CANCELLED"}

        dm.cancel_download()
        self.report({"INFO"}, "Download cancellation requested.")
        return {"FINISHED"}


class TESSERA_OT_OpenPreferencesModels(Operator):
    """Open the Tessera preferences panel to the Models section.

    Implements: FR-017 (notification banner button).
    """

    bl_idname = "tessera.open_preferences_models"
    bl_label = "Open Preferences"
    bl_description = "Open Tessera preferences to manage models"
    bl_options = {"REGISTER"}

    def execute(self, context):
        """Open preferences and navigate to add-on tab."""
        bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
        context.preferences.active_section = "ADDONS"
        return {"FINISHED"}


# Classes to register
classes = [
    TESSERA_OT_DownloadModel,
    TESSERA_OT_DownloadAllModels,
    TESSERA_OT_ClearModelCache,
    TESSERA_OT_UpdateModel,
    TESSERA_OT_CancelDownload,
    TESSERA_OT_OpenPreferencesModels,
]
