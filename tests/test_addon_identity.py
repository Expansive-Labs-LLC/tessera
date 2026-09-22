# SPDX-License-Identifier: GPL-2.0-or-later
"""Regression tests for add-on identity resolution.

Blender keys ``context.preferences.addons`` by the add-on's package name,
which differs between a legacy add-on install (``tessera``) and an
extension install (``bl_ext.user_default.tessera``). Hard-coding either
one breaks the other, and the failure is close to invisible: Blender
registers the preferences class but never associates it, so the panel
renders empty with no error in the console.

These tests fail fast on a re-introduced literal. They do not replace
loading the add-on in Blender — see ``scripts/`` for that — but they
catch the specific mistake that produced an empty preferences panel.
"""

import pathlib
import re

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "tessera"

# addons["tessera"] / addons.get("tessera") / addons['tessera']
_LITERAL = re.compile(r"""addons\s*(?:\[|\.get\()\s*["']tessera["']""")
# bl_idname = "tessera"  (must be ADDON_ID, i.e. __package__)
_BL_IDNAME = re.compile(r"""bl_idname\s*=\s*["']tessera["']""")


def _sources():
    return [p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]


def test_no_hardcoded_preferences_key():
    """The add-on key must be resolved, never spelled as a literal."""
    hits = []
    for path in _sources():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _LITERAL.search(line):
                hits.append(f"{path.relative_to(SRC.parent)}:{n}: {line.strip()}")
    assert not hits, (
        "Preferences must be read via tessera.addon.get_addon_preferences(); "
        'a literal "tessera" key resolves only for legacy installs and '
        "silently yields no preferences under an extension install:\n"
        + "\n".join(hits)
    )


def test_preferences_bl_idname_is_not_a_literal():
    """AddonPreferences.bl_idname must equal __package__."""
    hits = []
    for path in _sources():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _BL_IDNAME.search(line):
                hits.append(f"{path.relative_to(SRC.parent)}:{n}")
    assert not hits, (
        "bl_idname must be ADDON_ID (__package__). A literal makes Blender "
        "register the class without associating it, so the preferences "
        "panel draws empty:\n" + "\n".join(hits)
    )


def test_extension_path_user_is_called_with_keyword_path():
    """``path`` is keyword-only; a positional call raises TypeError.

    The TypeError was caught and silently fell back to the legacy add-ons
    directory, putting multi-gigabyte model weights outside the
    extension's own cache.
    """
    src = (SRC / "preferences.py").read_text(encoding="utf-8")
    # Only real invocations — the identifier also appears inside a log
    # message, which is not a call.
    calls = re.findall(r"bpy\.utils\.extension_path_user\(([^)]*)\)", src, re.S)
    # Prose references like ``bpy.utils.extension_path_user()`` in the
    # docstring carry no arguments and are not calls.
    calls = [c for c in calls if c.strip()]
    assert calls, "expected preferences.py to call extension_path_user()"
    for args in calls:
        assert "path=" in args, (
            "extension_path_user() takes one positional argument; pass "
            f"path= as a keyword. Found: extension_path_user({args.strip()})"
        )


@pytest.mark.parametrize("module", ["addon"])
def test_addon_module_exposes_identity_api(module):
    """``tessera.addon`` is the single source of the add-on key."""
    src = (SRC / f"{module}.py").read_text(encoding="utf-8")
    assert "ADDON_ID" in src
    assert "def get_addon_preferences" in src
    assert "__package__" in src, "ADDON_ID must derive from __package__"
