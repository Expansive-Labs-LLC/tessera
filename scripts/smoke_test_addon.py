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

"""Load the built add-on in Blender and assert that it actually works.

Run inside Blender, not pytest::

    blender --background --factory-startup --python scripts/smoke_test_addon.py

The unit suite mocks ``bpy``, which means a whole class of defect passes it
untouched. Each check below corresponds to one that did:

* a nested archive root, so Blender found no ``__init__.py``
* ``AddonPreferences.bl_idname`` not matching the package name, so Blender
  registered the class, never associated it, and drew an empty panel
* preferences read via a hard-coded ``"tessera"`` key, which resolves only
  for a legacy install and left the model cache uninitialised
* ``extension_path_user()`` called positionally, silently relocating the
  weight cache to the legacy add-ons directory

Exits non-zero on the first failed check, printing what was expected.
"""

import sys
import traceback

import bpy

ADDON_ID = "bl_ext.user_default.tessera"

_failures: list[str] = []


def check(label, condition, detail=""):
    """Record one assertion and print its outcome."""
    if condition:
        print(f"  PASS  {label}" + (f" — {detail}" if detail else ""))
    else:
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))
        _failures.append(label)
    return bool(condition)


def main():
    print(f"Blender {bpy.app.version_string}")
    print(f"Add-on  {ADDON_ID}\n")

    # --- registration -----------------------------------------------------
    try:
        bpy.ops.preferences.addon_enable(module=ADDON_ID)
    except Exception as exc:
        print(f"  FAIL  add-on enables — {exc}")
        traceback.print_exc()
        return 1
    check("add-on enables", True)

    entry = bpy.context.preferences.addons.get(ADDON_ID)
    if not check(
        "preferences entry present",
        entry is not None,
        "a missing entry means the package name does not match",
    ):
        return 1

    prefs = getattr(entry, "preferences", None)
    if not check(
        "preferences instance present",
        prefs is not None,
        "bl_idname must equal __package__, else the panel draws empty",
    ):
        return 1

    check(
        "bl_idname matches the package",
        type(prefs).bl_idname == ADDON_ID,
        f"bl_idname={type(prefs).bl_idname!r}",
    )

    import importlib

    addon = importlib.import_module(ADDON_ID)
    check(
        "ADDON_ID resolves from __package__",
        addon.addon.ADDON_ID == ADDON_ID,
        f"got {addon.addon.ADDON_ID!r}",
    )

    # --- preference-backed initialisation ---------------------------------
    cache_mod = importlib.import_module(f"{ADDON_ID}.models.cache_manager")
    cm = cache_mod.get_global_cache_manager()
    check(
        "model cache manager initialised",
        cm is not None,
        "None means the preferences lookup failed during registration",
    )

    dl_mod = importlib.import_module(f"{ADDON_ID}.models.download_manager")
    check("download manager initialised", dl_mod.get_global_download_manager())

    if cm is not None:
        cache_dir = str(cm.cache_dir)
        check(
            "weight cache is inside the extension directory",
            "extensions" in cache_dir,
            cache_dir,
        )
        try:
            n_models = len(cm._registry.list_models())
        except Exception as exc:
            n_models = -1
            print(f"        (registry unreadable: {exc})")
        check("manifest loads at least one model", n_models > 0, f"{n_models} models")

    # --- licence gate -----------------------------------------------------
    lic = importlib.import_module(f"{ADDON_ID}.models.licensing")
    try:
        lic.sync_from_preferences()
        synced = True
    except Exception as exc:
        synced = False
        print(f"        ({exc})")
    check(
        "licence opt-in mirrors from preferences",
        synced,
        "silent failure leaves the opt-in inert",
    )
    check(
        "licence gate defaults to closed",
        lic.restricted_models_allowed() is False,
    )

    # --- operators and panels --------------------------------------------
    for op in (
        "add_user_model",
        "remove_user_model",
        "download_model",
        "download_all_models",
        "clear_model_cache",
    ):
        check(f"operator tessera.{op} registered", hasattr(bpy.ops.tessera, op))

    # --- the preferences panel actually draws -----------------------------
    class _Layout:
        """Minimal stand-in that accepts Blender's layout call shapes."""

        enabled = True

        def __getattr__(self, name):
            def call(*args, **kwargs):
                if name in ("box", "row", "column", "split", "operator", "grid_flow"):
                    return self
                return None

            return call

    # ``prefs.draw()`` cannot be called directly: it reads ``self.layout``,
    # which Blender only populates during a real UI pass. What matters and
    # *is* checkable headless is that the class is bound to the add-on with a
    # usable draw method — the binding is what was broken.
    check(
        "preferences class exposes draw()",
        callable(getattr(type(prefs), "draw", None)),
    )

    panel = importlib.import_module(f"{ADDON_ID}.ui.download_panel")
    try:
        panel.draw_models_preferences(_Layout(), bpy.context)
        models_drew = True
    except Exception as exc:
        models_drew = False
        print(f"        ({type(exc).__name__}: {exc})")
    check(
        "Models section draws",
        models_drew,
        "this is the section that was silently swallowed",
    )

    # --- version ----------------------------------------------------------
    check(
        "bl_info carries an injected version",
        addon.bl_info["version"] != (0, 0, 0),
        f"version={addon.bl_info['version']} "
        "(0, 0, 0) means the build did not inject one",
    )

    print()
    if _failures:
        print(f"SMOKE TEST FAILED — {len(_failures)} check(s):")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
