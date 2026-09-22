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

"""Download progress and model management UI panels for Tessera.

Provides:
- Download progress sub-panel in the 3D Viewport sidebar
- Models section in the add-on preferences panel

Implements: FR-005, FR-008, FR-009, FR-010, FR-011, FR-016, FR-018.
"""

import logging

from bpy.types import Panel

logger = logging.getLogger("tessera.models")


def _format_bytes(size_bytes: int) -> str:
    """Format bytes as a human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        str: Formatted size (e.g., "1.3 GB", "512 MB").
    """
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024 ** 3):.1f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024 ** 2):.0f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f} KB"
    else:
        return f"{size_bytes} B"


def _format_eta(seconds: float) -> str:
    """Format seconds as a human-readable ETA string.

    Args:
        seconds: Estimated time remaining in seconds.

    Returns:
        str: Formatted ETA (e.g., "2m 36s", "< 1s").
    """
    if seconds <= 0:
        return "< 1s"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


class TESSERA_PT_DownloadProgress(Panel):
    """Download progress sub-panel in the 3D Viewport sidebar.

    Shows active download progress with model name, percentage,
    downloaded/total size, and estimated time remaining.

    Only visible when a download is active.

    Implements: FR-005.
    """

    bl_label = "Model Download"
    bl_idname = "TESSERA_PT_DownloadProgress"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_parent_id = "TESSERA_PT_Main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        """Only show when a download is active."""
        wm = context.window_manager
        status = wm.get("tessera_dl_status", "")
        return status in ("downloading", "completed", "error")

    def draw(self, context):
        """Draw the download progress panel."""
        layout = self.layout
        wm = context.window_manager

        model_id = wm.get("tessera_dl_model_id", "")
        bytes_dl = wm.get("tessera_dl_bytes", 0)
        total = wm.get("tessera_dl_total", 0)
        speed = wm.get("tessera_dl_speed", 0.0)
        eta = wm.get("tessera_dl_eta", 0.0)
        status = wm.get("tessera_dl_status", "")
        error = wm.get("tessera_dl_error", "")
        vram_warning = wm.get("tessera_dl_vram_warning", "")

        box = layout.box()

        if status == "error":
            box.alert = True
            box.label(text=f"Download failed: {model_id}", icon="ERROR")
            if error:
                col = box.column(align=True)
                # Wrap long error messages
                words = error.split()
                line = ""
                for word in words:
                    if len(line) + len(word) + 1 > 50:
                        col.label(text=line)
                        line = word
                    else:
                        line = f"{line} {word}" if line else word
                if line:
                    col.label(text=line)
            return

        if status == "completed":
            box.label(text=f"✓ {model_id} downloaded", icon="CHECKMARK")
            return

        # Active download
        col = box.column(align=True)
        col.label(text=f"Downloading: {model_id}", icon="IMPORT")

        # Progress percentage
        if total > 0:
            pct = min(100.0, (bytes_dl / total) * 100)
            col.progress(
                factor=pct / 100.0,
                type="BAR",
                text=f"{pct:.0f}%",
            )

            # Size and speed info
            row = col.row(align=True)
            row.label(text=f"{_format_bytes(bytes_dl)} / {_format_bytes(total)}")
            if speed > 0:
                row.label(text=f"{_format_bytes(int(speed))}/s")

            # ETA
            if eta > 0:
                col.label(text=f"ETA: {_format_eta(eta)}")
        else:
            col.label(text="Starting download...")

        # VRAM warning (EC-005)
        if vram_warning:
            warn_box = box.box()
            warn_box.alert = True
            warn_box.label(text="VRAM Warning", icon="ERROR")
            col = warn_box.column(align=True)
            words = vram_warning.split()
            line = ""
            for word in words:
                if len(line) + len(word) + 1 > 45:
                    col.label(text=line)
                    line = word
                else:
                    line = f"{line} {word}" if line else word
            if line:
                col.label(text=line)

        # Cancel button
        box.operator("tessera.cancel_download", icon="CANCEL")


def draw_models_preferences(layout, context):
    """Draw the Models section in the add-on preferences panel.

    Called from TesseraPreferences.draw() to add model management UI.

    Implements: FR-008, FR-009, FR-010, FR-011, FR-016, FR-018.

    Args:
        layout: The Blender layout to draw into.
        context: Blender context.
    """
    from ..models.cache_manager import get_global_cache_manager
    from ..models.download_manager import get_global_download_manager

    cm = get_global_cache_manager()
    dm = get_global_download_manager()

    box = layout.box()
    box.label(text="Models", icon="PACKAGE")

    if cm is None:
        box.label(text="Model management not initialized.", icon="ERROR")
        return

    # FR-018 (MAY): Download on first use toggle
    addon_prefs = context.preferences.addons.get("tessera")
    if addon_prefs and hasattr(addon_prefs.preferences, "download_on_first_use"):
        box.prop(
            addon_prefs.preferences,
            "download_on_first_use",
            text="Download on first use",
        )

    # FR-011: Total disk usage summary
    report = cm.get_cache_report()
    total_size = _format_bytes(report["total_bytes"])
    cache_path = str(cm.cache_dir)
    box.label(text=f"Model cache: {total_size} used in {cache_path}")

    box.separator()

    # FR-009: Download All Required button
    row = box.row()
    if dm and dm.is_downloading:
        row.enabled = False
    row.operator("tessera.download_all_models", icon="IMPORT")

    box.separator()

    # FR-008: Model table
    for model_report in report["models"]:
        model_id = model_report["model_id"]
        status = model_report["status"]
        size = model_report["size_bytes"]

        try:
            entry = cm._registry.get_model(model_id)
        except Exception:
            continue

        model_box = box.box()
        row = model_box.row()

        # Status icon
        if status == "Downloaded":
            icon = "CHECKMARK"
        elif status == "Update Available":
            icon = "FILE_REFRESH"
        elif dm and dm.active_download_id == model_id:
            icon = "IMPORT"
            status = "Downloading..."
        else:
            icon = "IMPORT"

        # Name and status
        col = row.column()
        col.label(text=entry.description, icon=icon)

        sub = col.row(align=True)
        sub.label(text=f"Status: {status}")
        if size > 0:
            sub.label(text=f"Size: {_format_bytes(size)}")
        else:
            sub.label(text=f"Size: ~{_format_bytes(entry.size_bytes)}")
        sub.label(text=f"VRAM: {entry.min_vram_gb:.0f} GB")

        # Action buttons (FR-010, FR-016)
        action_row = model_box.row(align=True)
        if status == "Not Downloaded":
            op = action_row.operator(
                "tessera.download_model",
                text="Download",
                icon="IMPORT",
            )
            op.model_id = model_id
        elif status == "Downloaded":
            op = action_row.operator(
                "tessera.clear_model_cache",
                text="Delete",
                icon="TRASH",
            )
            op.model_id = model_id
        elif status == "Update Available":
            op = action_row.operator(
                "tessera.update_model",
                text="Update",
                icon="FILE_REFRESH",
            )
            op.model_id = model_id
            op2 = action_row.operator(
                "tessera.clear_model_cache",
                text="Delete",
                icon="TRASH",
            )
            op2.model_id = model_id
        elif status == "Downloading...":
            action_row.operator(
                "tessera.cancel_download",
                text="Cancel",
                icon="CANCEL",
            )

    # VRAM warnings for models (EC-005)
    from ..models.variant_selector import select_variant
    from ..preferences import get_cached_gpu_info

    gpu_info = get_cached_gpu_info()
    if gpu_info and gpu_info.get("vram_gb", 0) > 0:
        vram = gpu_info["vram_gb"]
        for entry in cm._registry.list_models():
            _, warning = select_variant(entry, vram)
            if warning:
                warn_box = box.box()
                warn_box.alert = True
                warn_box.label(text=warning, icon="ERROR")


# Classes to register
classes = [
    TESSERA_PT_DownloadProgress,
]
