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

"""Tessera add-on preferences.

Provides user-configurable preferences accessible via
Edit → Preferences → Add-ons → Tessera.

Implements: FR-007, FR-008, FR-009, EC-003.
"""

import logging
import os
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import AddonPreferences

from .gpu_detection import get_gpu_info

logger = logging.getLogger("tessera")

# Module-level GPU info cache (populated on registration)
_gpu_info = None


def _get_default_cache_dir():
    """Get the default cache directory path.

    Uses ``bpy.utils.extension_path_user()`` for extension installs,
    with a fallback for manual ``.zip`` installs per §3.2.

    Returns:
        str: Default cache directory path.
    """
    try:
        # Extension install path (Blender 4.2+ extensions)
        cache_path = bpy.utils.extension_path_user(__package__, "cache")
        if cache_path:
            return cache_path
    except (TypeError, AttributeError):
        pass

    # Fallback for manual .zip installs
    return os.path.join(
        bpy.utils.user_resource("SCRIPTS"),
        "addons",
        "tessera",
        "cache",
    )


def _sync_license_optin(self, context):
    """Mirror the licence opt-in into the model-download gate.

    Called as an update callback on ``allow_restricted_license_models``.
    Downloads run on worker threads that must not touch ``bpy``
    (SPEC-TS-0002 CON-003), so the preference is mirrored into a
    module-level flag here, on the main thread.
    """
    from .models import licensing

    licensing.set_restricted_models_allowed(self.allow_restricted_license_models)


def _validate_cache_dir(self, context):
    """Validate that the cache directory is writable.

    Called as an update callback on the ``cache_dir`` property.
    If the directory is not writable, reverts to the default path
    and displays a warning per EC-003.
    """
    cache_path = Path(self.cache_dir).resolve()

    # If the directory doesn't exist, try to create it
    if not cache_path.exists():
        try:
            cache_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.warning("Cache directory is not writable: %s", cache_path)
            self["cache_dir"] = _get_default_cache_dir()
            return

    # Check write permissions
    if not os.access(str(cache_path), os.W_OK):
        logger.warning("Cache directory is not writable: %s", cache_path)
        self["cache_dir"] = _get_default_cache_dir()


def _get_gpu_device_items(self, context):
    """Dynamic enum callback for GPU device selector.

    Returns:
        list: List of (identifier, name, description) tuples for EnumProperty.
    """
    global _gpu_info

    if _gpu_info is None:
        _gpu_info = get_gpu_info()

    if _gpu_info["name"] is None:
        return [("NONE", "No compatible GPU found", "")]

    name = _gpu_info["name"]
    backend = _gpu_info["backend"] or "Unknown"
    return [(backend, f"{name} ({backend})", f"Use {name} via {backend}")]


class TesseraPreferences(AddonPreferences):
    """Tessera add-on preferences panel.

    Accessible via Edit → Preferences → Add-ons → Tessera.
    Contains GPU device selector, VRAM display, model cache directory,
    and a 'Clear Cache' button.

    Implements: FR-007, FR-008, FR-009, EC-003.
    """

    bl_idname = "tessera"

    gpu_device: EnumProperty(
        name="GPU Device",
        description="Select the GPU to use for inference",
        items=_get_gpu_device_items,
    )  # type: ignore[assignment]

    cache_dir: StringProperty(
        name="Model Cache Directory",
        description="Directory for caching downloaded model weights",
        subtype="DIR_PATH",
        default="",
        update=_validate_cache_dir,
    )  # type: ignore[assignment]

    # FR-018 (MAY): Download on first use toggle
    download_on_first_use: BoolProperty(
        name="Download on First Use",
        description=(
            "When enabled, pipeline tasks automatically download "
            "missing models before inference. When disabled, models "
            "must be downloaded manually from this preferences panel"
        ),
        default=True,
    )  # type: ignore[assignment]

    # Model weight licences are third-party and are not covered by
    # Tessera's GPL licence. Weights that restrict or prohibit commercial
    # use — or declare no terms — are gated behind this opt-in.
    # See MODEL-LICENSES.md and tessera.models.licensing.
    allow_restricted_license_models: BoolProperty(
        name="Allow Restricted-Licence Models",
        description=(
            "Permit downloading model weights whose licences restrict or "
            "prohibit commercial use, such as Depth Anything V2 Large "
            "(CC-BY-NC-4.0). Off by default. Only enable this if your use "
            "complies with each model's terms — see MODEL-LICENSES.md"
        ),
        default=False,
        update=_sync_license_optin,
    )  # type: ignore[assignment]

    # SPEC-TS-0009 (FR-039): LLM backend preferences.
    llm_backend: EnumProperty(
        name="LLM Backend",
        description="Backend used for natural-language intent parsing",
        items=[
            ("LOCAL", "Local (GGUF)", "Use local GGUF model via llama-cpp-python"),
            ("API", "API (OpenAI-compatible)", "Use a remote OpenAI-compatible API"),
        ],
        default="LOCAL",
    )  # type: ignore[assignment]

    llm_api_endpoint: StringProperty(
        name="API Endpoint",
        description="OpenAI-compatible API endpoint URL (HTTPS only)",
        default="https://api.openai.com/v1",
    )  # type: ignore[assignment]

    llm_api_key: StringProperty(
        name="API Key",
        description="API key for the LLM endpoint",
        subtype="PASSWORD",
        default="",
    )  # type: ignore[assignment]

    llm_api_model: StringProperty(
        name="Model Name",
        description="Model identifier for API requests",
        default="gpt-4",
    )  # type: ignore[assignment]

    def draw(self, context):
        """Draw the preferences panel layout."""
        layout = self.layout

        # GPU section
        box = layout.box()
        box.label(text="GPU Configuration")

        # GPU device selector (FR-008)
        box.prop(self, "gpu_device", text="Device")

        # GPU info display (FR-009)
        global _gpu_info
        if _gpu_info is None:
            _gpu_info = get_gpu_info()

        if _gpu_info["name"]:
            row = box.row()
            row.label(text=f"GPU: {_gpu_info['name']}")

            vram_text = f"{_gpu_info['vram_gb']:.0f} GB"
            if _gpu_info.get("shared_memory"):
                vram_text += " (shared)"
            row = box.row()
            row.label(text=f"VRAM: {vram_text}")

            row = box.row()
            row.label(text=f"Backend: {_gpu_info['backend']}")
        else:
            box.label(
                text="No compatible GPU found",
                icon="ERROR",
            )

        layout.separator()

        # Cache directory section
        box = layout.box()
        box.label(text="Model Cache", icon="FILE_FOLDER")
        box.prop(self, "cache_dir", text="Cache Directory")

        # Validate and show warning if needed (EC-003)
        if self.cache_dir:
            cache_path = Path(self.cache_dir).resolve()
            if cache_path.exists() and not os.access(str(cache_path), os.W_OK):
                box.label(
                    text="Cache directory is not writable. "
                    "Please choose a different location.",
                    icon="ERROR",
                )

        # Clear cache button (FR-007)
        box.operator("tessera.clear_cache", icon="TRASH")

        layout.separator()

        # SPEC-TS-0009 (FR-039): LLM Backend section.
        box = layout.box()
        box.label(text="LLM Backend (Refinement)", icon="OUTLINER_OB_FONT")
        box.prop(self, "llm_backend", text="Backend")

        if self.llm_backend == "API":
            box.prop(self, "llm_api_endpoint", text="Endpoint")
            box.prop(self, "llm_api_key", text="API Key")
            box.prop(self, "llm_api_model", text="Model")

            # FR-040: API key empty warning.
            if not self.llm_api_key:
                row = box.row()
                row.alert = True
                row.label(
                    text="API key required for API backend",
                    icon="ERROR",
                )

        layout.separator()

        # Model weight licensing section.
        box = layout.box()
        box.label(text="Model Weight Licences", icon="TEXT")
        box.label(
            text="Weights are third-party and are not covered by Tessera's "
            "GPL licence."
        )
        box.prop(self, "allow_restricted_license_models")
        if self.allow_restricted_license_models:
            row = box.row()
            row.alert = True
            row.label(
                text="Restricted weights enabled — some forbid commercial use",
                icon="ERROR",
            )
        box.label(text="Details: MODEL-LICENSES.md in the Tessera repository")

        layout.separator()

        # SPEC-TS-0002: Models management section (FR-008 through FR-011)
        try:
            from .ui.download_panel import draw_models_preferences

            draw_models_preferences(layout, context)
        except Exception:
            pass  # Models module may not be initialized yet


def init_gpu_info():
    """Initialize the GPU info cache.

    Called during add-on registration to populate GPU data.
    """
    global _gpu_info
    _gpu_info = get_gpu_info()


def get_cached_gpu_info():
    """Get the cached GPU info dict.

    Returns:
        dict: GPU info dict, or None if not yet initialized.
    """
    return _gpu_info


# Classes to register
classes = [
    TesseraPreferences,
]
