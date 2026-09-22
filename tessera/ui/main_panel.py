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

"""Main Tessera panel in the 3D Viewport sidebar.

Provides the top-level N-panel (sidebar) under the 'Tessera' tab.
Displays a GPU warning banner when no compatible GPU is detected.

Implements: FR-003, FR-010, FR-016.
"""

from bpy.types import Panel

from ..gpu_detection import is_inference_supported
from ..preferences import get_cached_gpu_info


class TESSERA_PT_Main(Panel):
    """Tessera main panel in the 3D Viewport sidebar.

    Top-level panel under the 'Tessera' tab (N-panel).

    Implements: FR-003, FR-010, FR-016.
    """

    bl_label = "Tessera"
    bl_idname = "TESSERA_PT_Main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"

    def draw(self, context):
        """Draw the main panel layout."""
        layout = self.layout

        # FR-010: GPU warning banner. Covers both "no GPU" and the case that
        # actually surprises people — a GPU that is detected and displayed
        # correctly but that no inference adapter can use (AMD, Apple
        # Silicon). NVIDIA CUDA only in v1; see TASK-TS-0022.
        gpu_info = get_cached_gpu_info()
        if gpu_info is None or gpu_info.get("name") is None:
            box = layout.box()
            col = box.column(align=True)
            col.alert = True
            col.label(text="Tessera requires an NVIDIA GPU with", icon="ERROR")
            col.label(text="CUDA. No compatible GPU was detected.")
            layout.separator()
        elif not is_inference_supported(gpu_info):
            backend = gpu_info.get("backend") or "unknown"
            label = {"ROCM": "AMD (ROCm)", "METAL": "Apple Silicon"}.get(
                backend, backend
            )
            box = layout.box()
            col = box.column(align=True)
            col.alert = True
            col.label(text=f"{label} GPU detected.", icon="ERROR")
            col.label(text="Tessera runs on NVIDIA CUDA only in v1 —")
            col.label(text="generation will not work on this GPU.")
            layout.separator()

        # FR-017: Missing models notification banner
        try:
            from ..models.cache_manager import get_global_cache_manager

            cm = get_global_cache_manager()
            if cm is not None:
                missing_count, missing_gb = cm.get_missing_models_summary()
                if missing_count > 0:
                    box = layout.box()
                    col = box.column(align=True)
                    col.alert = True
                    col.label(
                        text=(
                            f"Required models not downloaded. Open "
                            f"Preferences to download ({missing_count} "
                            f"models, ~{missing_gb:.1f} GB total)."
                        ),
                        icon="INFO",
                    )
                    col.operator(
                        "tessera.open_preferences_models",
                        text="Open Preferences",
                        icon="PREFERENCES",
                    )
                    layout.separator()
        except Exception:
            pass  # Models module may not be initialized yet

        # FR-016 (MAY): Open Preferences button
        layout.operator(
            "tessera.open_preferences",
            text="Open Preferences",
            icon="PREFERENCES",
        )


# Classes to register
classes = [
    TESSERA_PT_Main,
]
