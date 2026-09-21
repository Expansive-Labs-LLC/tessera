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

"""Golden-mesh testing infrastructure for Tessera.

Provides ``compute_mesh_hash`` for deterministic mesh fingerprinting
and ``GoldenMeshRegistry`` for managing reference meshes.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)
"""

from .golden_mesh import GoldenMeshRegistry
from .mesh_hash import compute_mesh_hash

__all__ = [
    "GoldenMeshRegistry",
    "compute_mesh_hash",
]
