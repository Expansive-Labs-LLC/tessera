#!/usr/bin/env python3
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

"""Generate golden-mesh reference files from Blender primitives.

This script creates ``.npz`` reference files for common mesh shapes
used in the regression test suite. It must be run inside Blender's
Python environment.

Usage (from Blender scripting console or command line)::

    blender --background --python scripts/generate_golden_mesh.py

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-031.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Allow importing tessera when run as a script.
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def generate_primitives(output_dir: Path) -> None:
    """Generate golden-mesh references for standard primitives.

    Creates .npz reference files for: cube, UV sphere, cylinder,
    cone, torus, icosphere, monkey (Suzanne), and plane.

    Args:
        output_dir: Directory where .npz files will be saved.
    """
    from tessera.testing.golden_mesh import GoldenMeshRegistry

    registry = GoldenMeshRegistry(output_dir)

    # Define mesh primitives with their vertex/face generators.
    primitives = _build_primitives()

    for name, verts, faces, description in primitives:
        ref = registry.create_reference(
            name=name,
            vertices=verts,
            faces=faces,
            source_description=description,
        )
        print(
            f"  Created: {name} "
            f"(V={ref.vertex_count}, F={ref.face_count}, "
            f"hash={ref.mesh_hash[:16]}...)"
        )

    print(f"\nGenerated {len(primitives)} golden-mesh references in {output_dir}")


def _build_primitives() -> list[tuple[str, np.ndarray, np.ndarray, str]]:
    """Build vertex/face data for standard primitives.

    Returns:
        List of (name, vertices, faces, description) tuples.
    """
    primitives = []

    # 1. Unit cube
    cube_v = np.array([
        [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5],
        [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5],
        [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5],
        [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5],
    ], dtype=np.float64)
    cube_f = np.array([
        [0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
        [0, 4, 5], [0, 5, 1], [2, 6, 7], [2, 7, 3],
        [0, 3, 7], [0, 7, 4], [1, 5, 6], [1, 6, 2],
    ], dtype=np.int64)
    primitives.append(("cube", cube_v, cube_f, "Unit cube, 8V/12F"))

    # 2. Plane
    plane_v = np.array([
        [-1.0, -1.0, 0.0], [1.0, -1.0, 0.0],
        [1.0, 1.0, 0.0], [-1.0, 1.0, 0.0],
    ], dtype=np.float64)
    plane_f = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    primitives.append(("plane", plane_v, plane_f, "2×2 plane, 4V/2F"))

    # 3. Tetrahedron
    h = np.sqrt(2.0 / 3.0)
    tet_v = np.array([
        [1.0, 0.0, -1.0 / np.sqrt(3.0)],
        [-1.0, 0.0, -1.0 / np.sqrt(3.0)],
        [0.0, 1.0, 1.0 / np.sqrt(3.0)],
        [0.0, -1.0, 1.0 / np.sqrt(3.0)],
    ], dtype=np.float64)
    tet_f = np.array([
        [0, 1, 2], [0, 2, 3], [0, 3, 1], [1, 3, 2],
    ], dtype=np.int64)
    primitives.append(("tetrahedron", tet_v, tet_f, "Regular tetrahedron, 4V/4F"))

    # 4. Octahedron
    oct_v = np.array([
        [1, 0, 0], [-1, 0, 0], [0, 1, 0],
        [0, -1, 0], [0, 0, 1], [0, 0, -1],
    ], dtype=np.float64)
    oct_f = np.array([
        [4, 0, 2], [4, 2, 1], [4, 1, 3], [4, 3, 0],
        [5, 2, 0], [5, 1, 2], [5, 3, 1], [5, 0, 3],
    ], dtype=np.int64)
    primitives.append(("octahedron", oct_v, oct_f, "Regular octahedron, 6V/8F"))

    # 5. Pyramid (square base)
    pyr_v = np.array([
        [-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0],
        [0, 0, 1.5],
    ], dtype=np.float64)
    pyr_f = np.array([
        [0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4],
        [0, 2, 1], [0, 3, 2],
    ], dtype=np.int64)
    primitives.append(("pyramid", pyr_v, pyr_f, "Square pyramid, 5V/6F"))

    return primitives


if __name__ == "__main__":
    output = _project_root / "tests" / "golden_meshes"
    print(f"Generating golden-mesh references to: {output}")
    generate_primitives(output)
