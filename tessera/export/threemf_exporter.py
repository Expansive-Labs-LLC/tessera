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

"""3MF exporter for Tessera.

Wraps Blender's 3MF exporter (``io_mesh_3mf`` add-on or built-in).

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-019.
"""

from __future__ import annotations

import logging

import bpy

logger = logging.getLogger("tessera.export")


def export_threemf(filepath: str) -> None:
    """Export the selected object to 3MF format.

    Uses Blender's ``export_scene.threemf`` operator if available,
    falling back to the ``io_mesh_3mf`` add-on.

    Args:
        filepath: Absolute path to the output ``.3mf`` file.

    Raises:
        RuntimeError: If no 3MF exporter is available in Blender.

    Implements: FR-019.
    """
    logger.info("Export started: format=3MF, export_path=%s", filepath)

    # Try the built-in 3MF exporter first.
    if hasattr(bpy.ops.export_scene, "threemf"):
        bpy.ops.export_scene.threemf(filepath=filepath)
        return

    # Fallback: try enabling the io_mesh_3mf add-on.
    try:
        bpy.ops.preferences.addon_enable(module="io_mesh_3mf")
        if hasattr(bpy.ops.export_scene, "threemf"):
            bpy.ops.export_scene.threemf(filepath=filepath)
            return
    except Exception:
        pass

    raise RuntimeError(
        "No 3MF exporter available. Ensure Blender 4.2+ is used "
        "or install the io_mesh_3mf add-on."
    )
