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

"""Lightweight fake data objects replacing MagicMock for Blender types.

These fakes implement the *minimum* interface that Tessera application
code accesses on Blender objects, without relying on MagicMock's
auto-attribute generation.  This ensures tests validate real
application logic rather than mock behaviour.

Mock Discipline: These fakes exist because ``bpy.types.Object``,
``bpy.types.Mesh``, etc. are C-extension types that cannot be
instantiated outside of Blender.  They are *justified* fakes
(category: infrastructure you don't own — Blender runtime).

Usage::

    from tests.fakes import FakeBlenderObject, FakeContext

    obj = FakeBlenderObject(
        vertices=[(0, 0, 0), (1, 0, 0), (0.5, 1, 0)],
        polygons=[(0, 1, 2)],
    )
    ctx = FakeContext()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import numpy as np


# ---------------------------------------------------------------------------
# Vector / Vertex fakes
# ---------------------------------------------------------------------------


class FakeVector:
    """Minimal Blender ``mathutils.Vector`` stand-in.

    Supports ``.x``, ``.y``, ``.z`` attribute access and
    ``__getitem__`` / ``__setitem__`` indexing.
    """

    __slots__ = ("_data",)

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        self._data = [float(x), float(y), float(z)]

    @property
    def x(self) -> float:
        return self._data[0]

    @x.setter
    def x(self, val: float) -> None:
        self._data[0] = float(val)

    @property
    def y(self) -> float:
        return self._data[1]

    @y.setter
    def y(self, val: float) -> None:
        self._data[1] = float(val)

    @property
    def z(self) -> float:
        return self._data[2]

    @z.setter
    def z(self, val: float) -> None:
        self._data[2] = float(val)

    def __getitem__(self, i: int) -> float:
        return self._data[i]

    def __setitem__(self, i: int, val: float) -> None:
        self._data[i] = float(val)

    def __len__(self) -> int:
        return 3

    def __iter__(self):
        return iter(self._data)

    def __repr__(self) -> str:
        return f"FakeVector({self.x}, {self.y}, {self.z})"


class FakeVertex:
    """Minimal ``bpy.types.MeshVertex`` stand-in.

    Attributes:
        co: Vertex position as a ``FakeVector``.
        index: Vertex index.
        groups: Vertex group memberships.
        select: Whether the vertex is selected.
    """

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        index: int = 0,
    ):
        self.co = FakeVector(x, y, z)
        self.index = index
        self.groups: list = []
        self.select = False


class FakeVertexGroup:
    """Minimal ``bpy.types.VertexGroup`` stand-in."""

    def __init__(self, name: str, index: int):
        self.name = name
        self.index = index


# ---------------------------------------------------------------------------
# Polygon fake
# ---------------------------------------------------------------------------


class FakePolygon:
    """Minimal ``bpy.types.MeshPolygon`` stand-in.

    Attributes:
        vertices: Tuple of vertex indices forming the polygon.
        normal: Face normal as a tuple (nx, ny, nz).
        area: Face area.
        center: Face center as a tuple (x, y, z).
    """

    def __init__(
        self,
        vertices: tuple[int, ...],
        normal: tuple[float, float, float] = (0.0, 0.0, 1.0),
        area: float = 1.0,
        center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ):
        self.vertices = vertices
        self.normal = normal
        self.area = area
        self.center = center


# ---------------------------------------------------------------------------
# Mesh fake
# ---------------------------------------------------------------------------


class FakeMesh:
    """Minimal ``bpy.types.Mesh`` stand-in.

    Provides ``.vertices``, ``.polygons``, ``.name``, and
    ``.update()`` / ``.calc_loop_triangles()`` methods.
    """

    def __init__(
        self,
        name: str = "Mesh",
        vertices: list[FakeVertex] | None = None,
        polygons: list[FakePolygon] | None = None,
    ):
        self.name = name
        self.vertices = vertices or []
        self.polygons = polygons or []

    def update(self) -> None:
        """No-op — parallel to ``bpy.types.Mesh.update()``."""

    def calc_loop_triangles(self) -> None:
        """No-op — parallel to ``bpy.types.Mesh.calc_loop_triangles()``."""

    def __len__(self) -> int:
        return len(self.vertices)


# ---------------------------------------------------------------------------
# Object fake
# ---------------------------------------------------------------------------


class FakeBlenderObject:
    """Minimal ``bpy.types.Object`` stand-in.

    Provides the interface used by the mesh cleanup pipeline,
    scaling/orientation logic, hierarchy helpers, and diagnostics.

    Args:
        name: Object name.
        vertices: List of ``(x, y, z)`` tuples or ``FakeVertex`` objects.
        polygons: List of ``(i, j, k)`` index tuples or ``FakePolygon``
            objects.  Polygons from tuples get default normals.
        dimensions: Object bounding-box dimensions ``(w, h, d)``.
    """

    def __init__(
        self,
        name: str = "FakeObj",
        vertices: list | None = None,
        polygons: list | None = None,
        dimensions: tuple[float, float, float] = (1.0, 1.0, 1.0),
    ):
        self.name = name

        # Build vertex list.
        raw_verts = vertices or [(0.0, 0.0, 0.0)]
        self._vertices: list[FakeVertex] = []
        for i, v in enumerate(raw_verts):
            if isinstance(v, FakeVertex):
                v.index = i
                self._vertices.append(v)
            else:
                self._vertices.append(FakeVertex(v[0], v[1], v[2], index=i))

        # Build polygon list.
        raw_polys = polygons or []
        self._polygons: list[FakePolygon] = []
        for p in raw_polys:
            if isinstance(p, FakePolygon):
                self._polygons.append(p)
            else:
                self._polygons.append(FakePolygon(vertices=tuple(p)))

        # Mesh data.
        self.data = FakeMesh(
            name=name,
            vertices=self._vertices,
            polygons=self._polygons,
        )

        # Spatial properties.
        self.dimensions = list(dimensions)
        self.location = FakeVector(0.0, 0.0, 0.0)
        self.rotation_euler = (0.0, 0.0, 0.0)
        self.scale = [1.0, 1.0, 1.0]

        # Selection state.
        self._selected = False
        self._active = False

        # Modifiers (for cleanup pipeline).
        self.modifiers = FakeModifierCollection()

    def select_set(self, value: bool) -> None:
        """Set selection state."""
        self._selected = value

    @property
    def select_get(self) -> bool:
        return self._selected

    def __repr__(self) -> str:
        return (
            f"FakeBlenderObject(name={self.name!r}, "
            f"verts={len(self._vertices)}, "
            f"polys={len(self._polygons)})"
        )


class FakeModifierCollection:
    """Minimal modifier collection supporting ``new()`` and ``remove()``."""

    def __init__(self):
        self._modifiers: list[MagicMock] = []

    def new(self, name: str, type: str) -> MagicMock:
        # Mock: infrastructure — Blender modifier API creates C-level data
        mod = MagicMock()
        mod.name = name
        mod.type = type
        self._modifiers.append(mod)
        return mod

    def remove(self, mod: Any) -> None:
        self._modifiers = [m for m in self._modifiers if m is not mod]

    def __iter__(self):
        return iter(self._modifiers)

    def __len__(self):
        return len(self._modifiers)


# ---------------------------------------------------------------------------
# Context / ViewLayer fakes
# ---------------------------------------------------------------------------


class FakeViewLayer:
    """Minimal ``bpy.types.ViewLayer`` stand-in."""

    def __init__(self):
        self.objects = FakeViewLayerObjects()


class FakeViewLayerObjects:
    """Minimal ``bpy.types.ViewLayer.objects`` stand-in."""

    def __init__(self):
        self.active: Any = None


class FakeUnitSettings:
    """Minimal ``bpy.types.UnitSettings`` stand-in."""

    def __init__(self):
        self.system = "NONE"
        self.scale_length = 1.0
        self.length_unit = "NONE"


class FakeScene:
    """Minimal ``bpy.types.Scene`` stand-in."""

    def __init__(self):
        self.unit_settings = FakeUnitSettings()


class FakeCollection:
    """Minimal ``bpy.types.Collection`` stand-in."""

    def __init__(self):
        self._objects: list = []
        self.objects = self

    def link(self, obj: Any) -> None:
        self._objects.append(obj)


class FakeContext:
    """Minimal ``bpy.types.Context`` stand-in.

    Provides ``.view_layer``, ``.scene``, and ``.collection``.
    """

    def __init__(self):
        self.view_layer = FakeViewLayer()
        self.scene = FakeScene()
        self.collection = FakeCollection()


# ---------------------------------------------------------------------------
# Vision pipeline fakes
# ---------------------------------------------------------------------------


def make_vision_result(**overrides):
    """Create a real ``VisionResult``-like object with test data.

    Uses a simple ``SimpleNamespace`` to avoid depending on the real
    ``VisionResult`` import (which pulls in heavy deps).  Provides
    the exact attribute interface consumed by ``StrategySelector``.

    Returns:
        A namespace with all ``VisionResult`` attributes populated.
    """
    from types import SimpleNamespace

    defaults = {
        "image": np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8),
        "mask": np.ones((256, 256), dtype=np.uint8) * 255,
        "depth_map": np.random.rand(256, 256).astype(np.float32),
        "view_label": "front",
        "label_source": "user",
        "label_confidence": 1.0,
        "label_needs_confirmation": False,
        "features": np.random.randn(1, 768).astype(np.float32),
        "original_size": (256, 256),
        "processing_time_s": {"segmentation": 1.0},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Vertex list helpers (for NL refinement loop)
# ---------------------------------------------------------------------------


class FakeVertexList:
    """List-like vertex container supporting ``len`` / ``iter`` / ``getitem``."""

    def __init__(self, verts: list[FakeVertex]):
        self._verts = list(verts)

    def __len__(self) -> int:
        return len(self._verts)

    def __iter__(self):
        return iter(self._verts)

    def __getitem__(self, idx):
        return self._verts[idx]

    def __contains__(self, item):
        return item in self._verts
