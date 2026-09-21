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

"""Mesh import, cleanup & topology optimization for Tessera.

Provides the ``MeshImporter`` for converting raw NumPy arrays into
Blender mesh objects and the ``MeshCleanupPipeline`` for repairing
noisy AI-generated meshes into watertight, print-ready topology.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Public API:
    MeshImporter — vertices + faces → bpy.types.Object
    MeshCleanupPipeline — orchestrates configurable cleanup chain
    MeshCleanupError — raised on critical pipeline step failure
    RawMeshData — input data container
"""

from .cleanup import MeshCleanupPipeline
from .data_types import RawMeshData
from .exceptions import MeshCleanupError
from .importer import MeshImporter

__all__ = [
    "MeshCleanupPipeline",
    "MeshCleanupError",
    "MeshImporter",
    "RawMeshData",
]
