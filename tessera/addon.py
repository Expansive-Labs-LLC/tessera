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

"""Add-on identity and preference access.

Blender keys ``context.preferences.addons`` by the add-on's Python package
name. That name depends on how the add-on was installed:

* legacy add-on (``scripts/addons/tessera``) → ``"tessera"``
* extension (``extensions/user_default/tessera``) → ``"bl_ext.user_default.tessera"``

Hard-coding either one breaks the other. This module resolves it once from
``__package__`` — it lives at the package root, so ``__package__`` is the
root package under both layouts — and every other module imports it from
here rather than spelling a literal.

The same value is what ``AddonPreferences.bl_idname`` must equal. When it
does not match, Blender registers the class but never associates it with
the add-on, and the preferences panel renders **empty** with no error.

Spec: SPEC-TS-0001 (Add-on Scaffold)

Public API:
    ADDON_ID — the package name Blender knows this add-on by
    get_addon_preferences — the preferences instance, or None
"""

from typing import Any, Optional

#: The package name Blender keys this add-on by. Do not hard-code a literal.
ADDON_ID: str = __package__ or "tessera"


def get_addon_preferences(context: Any = None) -> Optional[Any]:
    """Return this add-on's preferences instance.

    Args:
        context: A Blender context. Defaults to ``bpy.context``.

    Returns:
        The ``TesseraPreferences`` instance, or ``None`` when the add-on is
        not registered or ``bpy`` is unavailable (tests, headless tooling).
    """
    try:
        import bpy

        ctx = context if context is not None else bpy.context
        entry = ctx.preferences.addons.get(ADDON_ID)
    except Exception:
        return None
    return getattr(entry, "preferences", None) if entry is not None else None
