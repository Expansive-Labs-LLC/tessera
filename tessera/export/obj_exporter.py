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

"""OBJ exporter for Tessera.

Wraps Blender's built-in OBJ exporter with print-ready parameters.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-020.
"""

from __future__ import annotations

import logging

import bpy

logger = logging.getLogger("tessera.export")


def export_obj(filepath: str) -> None:
    """Export the selected object to OBJ format.

    Args:
        filepath: Absolute path to the output ``.obj`` file.

    Implements: FR-020.
    """
    logger.info("Export started: format=OBJ, export_path=%s", filepath)

    bpy.ops.export_scene.obj(
        filepath=filepath,
        use_selection=True,
        use_mesh_modifiers=True,
        global_scale=1.0,
    )
