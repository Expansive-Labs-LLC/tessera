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

"""Help panel for the Tessera sidebar.

Provides quick links to documentation, issue tracker, and
inline tooltip references.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-039.
"""

from __future__ import annotations

import bpy

# Documentation URLs.
_DOCS_URL = "https://expansive-labs-llc.github.io/tessera/"
_ISSUES_URL = "https://github.com/Expansive-Labs-LLC/tessera/issues"
_QUICKSTART_URL = "https://expansive-labs-llc.github.io/tessera/quickstart/"


class TESSERA_PT_help(bpy.types.Panel):
    """Tessera Help & Documentation panel."""

    bl_label = "Help & Documentation"
    bl_idname = "TESSERA_PT_help"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tessera"
    bl_order = 99
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        """Draw the help panel.

        Shows links to documentation, issue tracker, and tips.

        Implements: FR-039.
        """
        layout = self.layout

        # Documentation links.
        box = layout.box()
        box.label(text="Documentation", icon="INFO")
        box.operator(
            "wm.url_open",
            text="📖 User Guide",
            icon="URL",
        ).url = _DOCS_URL
        box.operator(
            "wm.url_open",
            text="🚀 Quick Start Guide",
            icon="URL",
        ).url = _QUICKSTART_URL

        layout.separator()

        # Support links.
        box = layout.box()
        box.label(text="Support", icon="URL")
        box.operator(
            "wm.url_open",
            text="🐛 Report an Issue",
            icon="URL",
        ).url = _ISSUES_URL

        layout.separator()

        # Quick tips.
        box = layout.box()
        box.label(text="Quick Tips", icon="LIGHT_SUN")
        tips = [
            "Use high-contrast reference images",
            "Center the object in each photo",
            "3–6 views give best results",
            "Use well-lit, non-blurry images",
            "FDM: Target ≥1.2mm wall thickness",
        ]
        for tip in tips:
            box.label(text=f"  • {tip}")


classes = [TESSERA_PT_help]
