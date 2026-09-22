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

"""Shared pytest fixtures and configuration for tessera test suite.

This conftest installs a bpy mock before any tessera modules are
imported, allowing the pure-Python submodules (data_types, report,
export helpers) to be tested outside Blender.

The ``test_checks_integration.py`` module uses
``pytest.importorskip("bpy")`` to skip when running outside Blender.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ── Mock Blender modules for non-Blender tests ──────────────────────
#
# When running under standard CPython (not Blender's embedded Python),
# we install lightweight mocks for bpy, bpy.types, bpy.props, bmesh,
# mathutils, etc. so that tessera's import chain doesn't break.
#
# These mocks are installed ONCE at conftest load time, which is
# before any test module collection.

if "bpy" not in sys.modules:
    # Create a mock bpy module that behaves like a proper package.
    _bpy = MagicMock(spec=[])
    _bpy.__name__ = "bpy"
    _bpy.__path__ = []
    _bpy.__package__ = "bpy"
    _bpy.data = MagicMock()
    _bpy.data.filepath = ""
    _bpy.ops = MagicMock()
    _bpy.context = MagicMock()

    # bpy.types — operators, panels, property groups.
    _bpy_types = ModuleType("bpy.types")
    _bpy_types.Operator = type("Operator", (), {})
    _bpy_types.Panel = type("Panel", (), {})
    _bpy_types.PropertyGroup = type("PropertyGroup", (), {})
    _bpy_types.AddonPreferences = type("AddonPreferences", (), {})
    _bpy_types.UIList = type("UIList", (), {})
    _bpy_types.Menu = type("Menu", (), {})
    _bpy_types.Header = type("Header", (), {})
    _bpy_types.Scene = MagicMock()
    _bpy_types.Object = MagicMock()
    _bpy_types.Mesh = MagicMock()
    _bpy_types.Context = MagicMock()

    # bpy.props — property descriptors.
    _bpy_props = ModuleType("bpy.props")
    for prop_name in (
        "BoolProperty",
        "IntProperty",
        "FloatProperty",
        "StringProperty",
        "EnumProperty",
        "PointerProperty",
        "CollectionProperty",
        "FloatVectorProperty",
        "IntVectorProperty",
        "BoolVectorProperty",
    ):
        setattr(_bpy_props, prop_name, lambda *args, **kwargs: None)

    # bpy.utils
    _bpy_utils = ModuleType("bpy.utils")
    _bpy_utils.register_class = MagicMock()
    _bpy_utils.unregister_class = MagicMock()

    # bmesh and mathutils also need mocks if they're imported at
    # module level. Individual test files that need real bmesh
    # should use pytest.importorskip().
    _bmesh = MagicMock()
    _bmesh.__name__ = "bmesh"

    _mathutils = ModuleType("mathutils")
    _mathutils.__path__ = []
    _mathutils.__package__ = "mathutils"
    _mathutils.Vector = MagicMock()
    _mathutils.Euler = MagicMock()
    _mathutils.Matrix = MagicMock()

    _mathutils_bvhtree = ModuleType("mathutils.bvhtree")
    _mathutils_bvhtree.BVHTree = MagicMock()

    # gpu / gpu_extras — imported by some UI modules.
    _gpu = MagicMock()
    _gpu.__name__ = "gpu"
    _gpu.__path__ = []
    _gpu.__package__ = "gpu"

    _gpu_extras = MagicMock()
    _gpu_extras.__name__ = "gpu_extras"
    _gpu_extras.__path__ = []
    _gpu_extras.__package__ = "gpu_extras"

    # bl_math
    _bl_math = MagicMock()
    _bl_math.__name__ = "bl_math"

    # Install all mocks.
    sys.modules["bpy"] = _bpy
    sys.modules["bpy.types"] = _bpy_types
    sys.modules["bpy.props"] = _bpy_props
    sys.modules["bpy.utils"] = _bpy_utils
    sys.modules["bmesh"] = _bmesh
    sys.modules["mathutils"] = _mathutils
    sys.modules["mathutils.bvhtree"] = _mathutils_bvhtree
    sys.modules["gpu"] = _gpu
    sys.modules["gpu_extras"] = _gpu_extras
    sys.modules["bl_math"] = _bl_math


# ── Markers ──────────────────────────────────────────────────────────


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "blender: marks tests requiring Blender runtime "
        "(deselect with '-m \"not blender\"')",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests in test_checks_integration.py as 'blender'."""
    for item in items:
        if "test_checks_integration" in str(item.fspath):
            item.add_marker(pytest.mark.blender)
