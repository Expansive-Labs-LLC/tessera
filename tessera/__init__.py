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

"""Tessera — AI-powered Blender add-on for 3D-printable model generation.

This is the main entry point for the Tessera Blender add-on.
It handles add-on registration, class collection, and lifecycle management.

Spec: SPEC-TS-0001 (Blender Add-on Scaffold & GPU Configuration)
Spec: SPEC-TS-0002 (Local Model Weight Management)
"""

import logging

import bpy

from . import operators, ui
from .addon import ADDON_ID, get_addon_preferences
from .preferences import TesseraPreferences, init_gpu_info
from .properties import (
    TesseraCleanupSettings,
    TesseraImageItem,
    TesseraProperties,
    TesseraRefinementSettings,
    TesseraScalingSettings,
    TesseraValidatorSettings,
)

logger = logging.getLogger("tessera")

# FR-001: bl_info with minimum Blender version (4, 2, 0)
bl_info = {
    "name": "Tessera",
    "author": "Tessera Team",
    # Placeholder; scripts/build_addon.sh injects the release version.
    "version": (0, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Tessera",
    "description": "AI-powered 3D-printable model generation from reference images",
    "warning": "",
    "doc_url": "https://expansivelabs.io/tessera/",
    "category": "3D View",
}

# FR-002: Collect all classes for registration.
# Order matters: PropertyGroups first, then operators, then panels,
# then preferences (which may reference operators).
# Note: TesseraCleanupSettings must come before TesseraProperties
# because TesseraProperties references it via PointerProperty.
_classes = (
    [
        TesseraImageItem,
        TesseraCleanupSettings,
        TesseraValidatorSettings,
        TesseraScalingSettings,
        TesseraRefinementSettings,
        TesseraProperties,
    ]
    + operators.classes
    + ui.classes
    + [TesseraPreferences]
)


def register():
    """Register the Tessera add-on with Blender.

    Registers all classes in dependency order, attaches scene-level
    properties, and initializes GPU detection.

    Implements: FR-002, FR-008, CON-005.

    Note:
        CON-005: This function uses only ``bpy.utils.register_class()``
        — no ``bpy.ops`` calls.
    """
    # Register all classes
    for cls in _classes:
        bpy.utils.register_class(cls)

    # FR-012: Attach scene-level properties
    bpy.types.Scene.tessera = bpy.props.PointerProperty(type=TesseraProperties)

    # FR-008: Initialize GPU detection on registration
    init_gpu_info()

    # Mirror the saved model-licence opt-in into the download gate. The
    # preference persists across sessions; the module-level flag does not.
    from .models import licensing

    licensing.sync_from_preferences()

    # §11.1: Log registration with GPU info
    from .preferences import get_cached_gpu_info

    gpu = get_cached_gpu_info()
    logger.info(
        "Tessera add-on registered (Blender %s, GPU: %s, VRAM: %.1f GB, Backend: %s)",
        ".".join(str(v) for v in bpy.app.version),
        gpu.get("name", "None") if gpu else "None",
        gpu.get("vram_gb", 0) if gpu else 0,
        gpu.get("backend", "None") if gpu else "None",
    )

    # SPEC-TS-0002: Initialize model weight management
    _init_model_management(gpu)


def unregister():
    """Unregister the Tessera add-on from Blender.

    Removes scene-level properties and unregisters all classes in
    reverse order to respect dependency chains.

    Implements: FR-002, AC-005, CON-005.

    Note:
        CON-005: This function uses only ``bpy.utils.unregister_class()``
        — no ``bpy.ops`` calls.
    """
    # Remove scene-level properties (AC-005: clean uninstall)
    if hasattr(bpy.types.Scene, "tessera"):
        del bpy.types.Scene.tessera

    # FR-002: Unregister all classes in reverse order
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            # Class may have already been unregistered
            pass

    # SPEC-TS-0002: Clean up model management
    _cleanup_model_management()

    logger.info("Tessera add-on unregistered")


def _init_model_management(gpu_info):
    """Initialize model weight management subsystem.

    Creates the ModelRegistry, CacheManager, and DownloadManager
    global instances used by the rest of the add-on.

    Implements: SPEC-TS-0002 integration.

    Args:
        gpu_info: GPU info dict from gpu_detection (may be None).
    """
    try:
        from .models.cache_manager import CacheManager, set_global_cache_manager
        from .models.download_manager import (
            DownloadManager,
            set_global_download_manager,
        )
        from .models.registry import ModelRegistry

        # Get cache directory from preferences
        try:
            addon_prefs = get_addon_preferences()
            if addon_prefs is None:
                logger.warning(
                    "Add-on preferences unavailable for %r; falling back to "
                    "the default cache directory.",
                    ADDON_ID,
                )
            cache_dir = getattr(addon_prefs, "cache_dir", "")
            if not cache_dir:
                # Use default if not set
                from .preferences import _get_default_cache_dir

                cache_dir = _get_default_cache_dir()
        except (KeyError, AttributeError):
            from .preferences import _get_default_cache_dir

            cache_dir = _get_default_cache_dir()

        # Load the model registry: the bundled manifest plus any models the
        # user added from Hugging Face. The user list lives beside the cache
        # rather than inside the add-on, so it survives add-on updates
        # (SPEC-TS-0002 FR-025).
        from pathlib import Path

        registry = ModelRegistry(
            user_manifest_path=Path(cache_dir) / "user_models.json"
        )

        # Initialize cache manager
        cache_manager = CacheManager(cache_dir=cache_dir, registry=registry)
        set_global_cache_manager(cache_manager)

        # Get available VRAM for variant selection
        available_vram = gpu_info.get("vram_gb", 0.0) if gpu_info else 0.0

        # Initialize download manager
        download_manager = DownloadManager(
            cache_dir=cache_dir,
            registry=registry,
            cache_manager=cache_manager,
            available_vram_gb=available_vram,
        )
        set_global_download_manager(download_manager)

        logger.info(
            "Model management initialized: %d models registered, " "cache_dir=%s",
            len(registry),
            cache_dir,
        )

    except Exception as e:
        # ManifestLoadError or other init failures —
        # log but don't block add-on registration
        logger.error(
            "Model management initialization failed: %s. "
            "Model download features will be unavailable.",
            e,
        )


def _cleanup_model_management():
    """Clean up model management subsystem on unregister.

    Cancels active downloads, removes timers, and clears global instances.
    """
    try:
        from .models.cache_manager import set_global_cache_manager
        from .models.download_manager import (
            get_global_download_manager,
            set_global_download_manager,
        )

        # Cancel any active downloads
        dm = get_global_download_manager()
        if dm is not None:
            dm.cancel_download()

        # Clear global instances
        set_global_download_manager(None)
        set_global_cache_manager(None)

        # Remove any lingering download progress timer
        from .operators.model_ops import _poll_download_progress

        if bpy.app.timers.is_registered(_poll_download_progress):
            bpy.app.timers.unregister(_poll_download_progress)

    except Exception as e:
        logger.debug("Model management cleanup: %s", e)
