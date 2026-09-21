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

"""Preferences operators for Tessera.

Provides operators for cache management and quick preferences access.

Implements: FR-007 (Clear Cache button), FR-016 (Open Preferences).
"""

import logging
import shutil
from pathlib import Path

import bpy
from bpy.types import Operator

logger = logging.getLogger("tessera")


class TESSERA_OT_ClearCache(Operator):
    """Clear the Tessera model cache directory.

    Removes all files in the configured cache directory.

    Implements: FR-007.
    """

    bl_idname = "tessera.clear_cache"
    bl_label = "Clear Cache"
    bl_description = "Remove all cached model files"
    bl_options = {"REGISTER"}

    def execute(self, context):
        """Clear the cache directory contents."""
        addon_prefs = context.preferences.addons[__package__.split(".")[0]].preferences
        cache_dir = Path(addon_prefs.cache_dir).resolve()

        if not cache_dir.exists():
            self.report({"INFO"}, "Cache directory does not exist.")
            return {"FINISHED"}

        if not cache_dir.is_dir():
            self.report({"WARNING"}, "Cache path is not a directory.")
            return {"CANCELLED"}

        try:
            # Remove contents but keep the directory itself
            for item in cache_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

            logger.info("Cache cleared: %s", cache_dir)
            self.report({"INFO"}, "Cache cleared successfully.")
        except OSError as e:
            logger.warning("Failed to clear cache: %s", e)
            self.report({"WARNING"}, f"Failed to clear cache: {e}")
            return {"CANCELLED"}

        return {"FINISHED"}

    def invoke(self, context, event):
        """Show confirmation dialog before clearing."""
        return context.window_manager.invoke_confirm(self, event)


class TESSERA_OT_OpenPreferences(Operator):
    """Open the Tessera preferences panel.

    Navigates to Edit → Preferences → Add-ons → Tessera.

    Implements: FR-016 (MAY).
    """

    bl_idname = "tessera.open_preferences"
    bl_label = "Open Preferences"
    bl_description = "Open Tessera add-on preferences"
    bl_options = {"REGISTER"}

    def execute(self, context):
        """Open the preferences window and navigate to the add-on."""
        bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
        # Set the preferences to show the add-on tab
        context.preferences.active_section = "ADDONS"
        return {"FINISHED"}


# Classes to register
classes = [
    TESSERA_OT_ClearCache,
    TESSERA_OT_OpenPreferences,
]
