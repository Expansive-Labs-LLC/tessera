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

Implements: FR-009, FR-010, FR-016, FR-017, FR-025 – FR-032.
"""

import logging

import bpy
from bpy.props import EnumProperty, StringProperty
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
        wm["tessera_dl_vram_warning"] = latest_progress.get("vram_warning", "") or ""

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
        # Main thread: refresh the licence gate before the worker thread
        # reads it (SPEC-TS-0002 CON-003).
        from ..models import licensing

        licensing.sync_from_preferences()

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
                "A download is already in progress. " "Please wait for it to complete.",
            )
            return {"CANCELLED"}

        # Surface licence gating here rather than as a background failure,
        # so the user gets an actionable message.
        try:
            entry = dm._registry.get_model(self.model_id)
        except Exception:
            entry = None
        if entry is not None:
            try:
                licensing.check_download_allowed(entry)
            except Exception as e:
                self.report({"ERROR"}, str(e))
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
        # Main thread: refresh the licence gate before worker threads read it.
        from ..models import licensing

        licensing.sync_from_preferences()

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
        freed_mb = freed / (1024**2)
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
def _family_items(self, context):
    """Enum items for the architecture family selector (FR-026)."""
    from ..models.families import family_choices

    return family_choices()


class TESSERA_OT_AddUserModel(Operator):
    """Add a model from Hugging Face to the local model list.

    Resolves the repository's declared licence and per-file checksums
    before anything is downloaded, so a user-added model is governed the
    same way a bundled one is: non-commercial, restricted and undeclared
    licences are refused unless the user has opted in.

    Implements: FR-025 – FR-031, SEC-007.
    """

    bl_idname = "tessera.add_user_model"
    bl_label = "Add Model from Hugging Face"
    bl_description = (
        "Look up a model on Hugging Face and add it to your model list. "
        "Its licence and checksums are verified before it is added"
    )
    bl_options = {"REGISTER", "UNDO"}

    repo_id: StringProperty(
        name="Repository",
        description="Hugging Face repository, in the form 'owner/name'",
        default="",
    )  # type: ignore[assignment]

    family: EnumProperty(
        name="Architecture",
        description="Which of Tessera's model families this checkpoint belongs to",
        items=_family_items,
    )  # type: ignore[assignment]

    variant: StringProperty(
        name="Variant",
        description=(
            "Variant within the family, where it applies — for Depth "
            "Anything V2 this is the encoder: vits, vitb, vitl or vitg"
        ),
        default="",
    )  # type: ignore[assignment]

    model_id: StringProperty(
        name="Name",
        description="Name to list it under. Derived from the repository if left blank",
        default="",
    )  # type: ignore[assignment]

    def invoke(self, context, event):
        """Open a properties dialog so the user can fill in the fields."""
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        """Draw the dialog, including the licence policy note."""
        layout = self.layout
        layout.prop(self, "repo_id")
        layout.prop(self, "family")
        layout.prop(self, "variant")
        layout.prop(self, "model_id")

        box = layout.box()
        box.label(text="Model weights are third-party.", icon="INFO")
        box.label(text="Tessera checks the licence Hugging Face declares and")
        box.label(text="refuses non-commercial or undeclared ones unless you")
        box.label(text="have enabled restricted models in preferences.")
        box.label(text="You are responsible for complying with each licence.")

    def execute(self, context):
        """Resolve, licence-check and register the model."""
        from ..models import licensing
        from ..models.hf_metadata import (
            MetadataError,
            build_user_entry,
            fetch_model_metadata,
        )

        licensing.sync_from_preferences()

        cm = _get_cache_manager()
        if cm is None:
            self.report({"ERROR"}, "Model management is not initialized.")
            return {"CANCELLED"}

        registry = cm._registry

        try:
            metadata = fetch_model_metadata(self.repo_id, self.family, revision=None)
        except MetadataError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        # FR-029: classify before download, and say what was found either way.
        if (
            licensing.classify_license(metadata.license_id)
            != (licensing.COMMERCIAL_USE_ALLOWED)
            and not licensing.restricted_models_allowed()
        ):
            self.report(
                {"ERROR"},
                (
                    f"{metadata.repo_id} declares its licence as "
                    f"'{metadata.license_display}', which Tessera treats as "
                    f"{licensing.classify_license(metadata.license_id)}. It "
                    f"was not added. Enable 'Allow Restricted-Licence "
                    f"Models' in preferences if your use complies with "
                    f"those terms — see MODEL-LICENSES.md."
                ),
            )
            return {"CANCELLED"}

        try:
            entry_data = build_user_entry(
                metadata,
                family_id=self.family,
                model_id=self.model_id.strip() or None,
                variant_id=self.variant.strip() or None,
            )
            entry = registry.add_user_model(entry_data)
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            (
                f"Added '{entry.model_id}' ({metadata.license_display}, "
                f"{entry.size_bytes / 1e9:.2f} GB). Download it from the "
                f"model list below."
            ),
        )
        return {"FINISHED"}


class TESSERA_OT_RemoveUserModel(Operator):
    """Remove a user-added model from the model list.

    Cached files are left on disk — use Delete to reclaim the space.

    Implements: FR-032.
    """

    bl_idname = "tessera.remove_user_model"
    bl_label = "Remove Model"
    bl_description = "Remove this user-added model from the list"
    bl_options = {"REGISTER", "UNDO"}

    model_id: StringProperty(
        name="Model ID",
        description="Unique model identifier",
        default="",
    )  # type: ignore[assignment]

    def execute(self, context):
        """Unregister the model."""
        cm = _get_cache_manager()
        if cm is None:
            self.report({"ERROR"}, "Model management is not initialized.")
            return {"CANCELLED"}

        try:
            removed = cm._registry.remove_user_model(self.model_id)
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        if not removed:
            self.report({"WARNING"}, f"'{self.model_id}' is not in the list.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Removed '{self.model_id}'.")
        return {"FINISHED"}


classes = [
    TESSERA_OT_AddUserModel,
    TESSERA_OT_RemoveUserModel,
    TESSERA_OT_DownloadModel,
    TESSERA_OT_DownloadAllModels,
    TESSERA_OT_ClearModelCache,
    TESSERA_OT_UpdateModel,
    TESSERA_OT_CancelDownload,
    TESSERA_OT_OpenPreferencesModels,
]
