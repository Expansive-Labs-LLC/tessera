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

"""Shared pytest fixtures for Tessera add-on tests.

Provides ``bpy`` mock scaffolding so modules can be imported and tested
outside of a running Blender process.
"""

import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# bpy mock infrastructure
# ---------------------------------------------------------------------------

def _build_bpy_mock():
    """Build a comprehensive mock for the ``bpy`` module.

    Creates a fake ``bpy`` with enough structure for Tessera's
    registration, PropertyGroup, Operator, and preferences APIs.

    Returns:
        MagicMock: A mock ``bpy`` module.
    """
    bpy = MagicMock()

    # bpy.app.version
    bpy.app.version = (4, 2, 0)
    bpy.app.timers.is_registered.return_value = False

    # bpy.types — provide base classes that can be subclassed
    bpy.types.PropertyGroup = type("PropertyGroup", (), {})
    bpy.types.Operator = type(
        "Operator",
        (),
        {
            "bl_idname": "",
            "bl_label": "",
            "bl_description": "",
            "bl_options": set(),
            "report": lambda self, level, msg: None,
        },
    )
    bpy.types.Panel = type(
        "Panel",
        (),
        {
            "bl_label": "",
            "bl_idname": "",
            "bl_space_type": "",
            "bl_region_type": "",
            "bl_category": "",
        },
    )
    bpy.types.UIList = type(
        "UIList",
        (),
        {"bl_idname": ""},
    )
    bpy.types.AddonPreferences = type(
        "AddonPreferences",
        (),
        {"bl_idname": ""},
    )
    bpy.types.Scene = MagicMock()

    # bpy.props — return MagicMock callables that accept keyword args
    bpy.props.StringProperty = MagicMock(return_value="")
    bpy.props.IntProperty = MagicMock(return_value=0)
    bpy.props.BoolProperty = MagicMock(return_value=False)
    bpy.props.FloatProperty = MagicMock(return_value=0.0)
    bpy.props.EnumProperty = MagicMock(return_value="")
    bpy.props.CollectionProperty = MagicMock(return_value=MagicMock())
    bpy.props.PointerProperty = MagicMock(return_value=MagicMock())

    # bpy.utils
    bpy.utils.register_class = MagicMock()
    bpy.utils.unregister_class = MagicMock()
    bpy.utils.user_resource = MagicMock(return_value="/tmp/blender_user")
    bpy.utils.extension_path_user = MagicMock(return_value="/tmp/tessera_cache")

    # bpy.context
    bpy.context.preferences.addons = {}
    bpy.context.preferences.active_section = ""

    return bpy


@pytest.fixture(autouse=True)
def mock_bpy(monkeypatch):
    """Inject a mock ``bpy`` into ``sys.modules`` for every test.

    This allows importing Tessera modules without a running Blender.
    The mock is removed after each test.

    Yields:
        MagicMock: The mock bpy module.
    """
    bpy_mock = _build_bpy_mock()

    # Build bmesh mock
    bmesh_mock = MagicMock()
    bmesh_mock.ops = MagicMock()

    # Build mathutils mock (Blender-only module used by overhang checks)
    mathutils_mock = types.ModuleType("mathutils")
    mathutils_mock.Vector = MagicMock()
    mathutils_mock.Matrix = MagicMock()

    # Euler mock: returns a real rotation matrix via to_matrix() so that
    # the orientation optimizer's NumPy-based scoring works correctly.
    import math as _math

    class _MockEuler:
        """Minimal Euler mock that computes real 3×3 rotation matrices."""
        def __init__(self, angles, order="XYZ"):
            self._angles = angles  # (rx, ry, rz) in radians
            self._order = order
        def to_matrix(self):
            rx, ry, rz = self._angles
            cx, sx = _math.cos(rx), _math.sin(rx)
            cy, sy = _math.cos(ry), _math.sin(ry)
            cz, sz = _math.cos(rz), _math.sin(rz)
            # XYZ Euler → rotation matrix.
            return [
                [cy*cz,            -cy*sz,           sy],
                [sx*sy*cz + cx*sz, -sx*sy*sz + cx*cz, -sx*cy],
                [-cx*sy*cz + sx*sz, cx*sy*sz + sx*cz,  cx*cy],
            ]
        def __iter__(self):
            return iter(self._angles)

    mathutils_mock.Euler = _MockEuler

    mathutils_bvhtree_mock = types.ModuleType("mathutils.bvhtree")
    mathutils_bvhtree_mock.BVHTree = MagicMock()
    mathutils_mock.bvhtree = mathutils_bvhtree_mock

    # Insert bpy, bmesh, mathutils and their sub-modules into sys.modules
    modules_to_inject = {
        "bpy": bpy_mock,
        "bpy.app": bpy_mock.app,
        "bpy.types": bpy_mock.types,
        "bpy.props": bpy_mock.props,
        "bpy.utils": bpy_mock.utils,
        "bpy.ops": bpy_mock.ops,
        "bpy.mathutils": mathutils_mock,
        "bmesh": bmesh_mock,
        "bmesh.ops": bmesh_mock.ops,
        "bmesh.types": bmesh_mock.types,
        "mathutils": mathutils_mock,
        "mathutils.bvhtree": mathutils_bvhtree_mock,
    }

    saved = {}
    for name, mod in modules_to_inject.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    # Also clear any previously cached tessera imports so they reload
    # with the mocked bpy.
    tessera_keys = [k for k in sys.modules if k.startswith("tessera")]
    saved_tessera = {k: sys.modules.pop(k) for k in tessera_keys}

    yield bpy_mock

    # Restore original sys.modules state
    for name, original in saved.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

    # Clean up tessera modules
    for k in list(sys.modules):
        if k.startswith("tessera"):
            sys.modules.pop(k, None)

    # Restore any previously cached tessera modules
    sys.modules.update(saved_tessera)


@pytest.fixture
def tmp_image_files(tmp_path):
    """Create temporary image files for testing.

    Creates 3 small files with valid image extensions.

    Args:
        tmp_path: pytest built-in temporary directory.

    Returns:
        list[Path]: List of 3 temporary image file paths.
    """
    files = []
    for name in ["photo_front.jpg", "photo_back.png", "photo_side.webp"]:
        p = tmp_path / name
        p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # Minimal header bytes
        files.append(p)
    return files


@pytest.fixture
def tmp_bmp_file(tmp_path):
    """Create a temporary .bmp file (unsupported format).

    Returns:
        Path: Path to the .bmp file.
    """
    p = tmp_path / "invalid.bmp"
    p.write_bytes(b"BM" + b"\x00" * 100)
    return p


@pytest.fixture
def tmp_heic_file(tmp_path):
    """Create a temporary .heic file.

    Returns:
        Path: Path to the .heic file.
    """
    p = tmp_path / "photo.heic"
    p.write_bytes(b"\x00" * 100)
    return p


@pytest.fixture
def non_writable_dir(tmp_path):
    """Create a non-writable directory.

    Returns:
        Path: Path to the non-writable directory.
    """
    d = tmp_path / "readonly_cache"
    d.mkdir()
    d.chmod(0o444)
    yield d
    # Restore permissions for cleanup
    d.chmod(0o755)
