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

"""Validation operator for Tessera.

Provides the ``TESSERA_OT_validate_print`` operator that runs
print-readiness validation in read-only mode on the active mesh.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-034, FR-037, FR-039, EC-003, SEC-001.
"""

from __future__ import annotations

import logging

import bpy
from bpy.types import Operator

from ..validator.print_validator import PrintValidator

logger = logging.getLogger("tessera.validator")


class TESSERA_OT_validate_print(Operator):
    """Validate the active mesh for 3D printing (read-only).

    Runs all 7 validation checks without creating a duplicate and
    without applying any auto-repairs. Displays the validation
    report in the Blender Info area.

    Implements: FR-034, FR-037, FR-039.
    """

    bl_idname = "tessera.validate_print"
    bl_label = "Validate for Printing"
    bl_description = (
        "Run 7 print-readiness checks on the active mesh "
        "without modifying it"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Return ``True`` only when a mesh object is active.

        Implements: EC-003, SEC-001.
        """
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def execute(self, context):
        """Run validation-only pipeline.

        Args:
            context: Blender context.

        Returns:
            ``{'FINISHED'}`` on success, ``{'CANCELLED'}`` on error.

        Implements: FR-034, FR-039.
        """
        obj = context.active_object

        # SEC-001: Verify mesh type.
        if obj is None or obj.type != "MESH":
            self.report(
                {"ERROR"},
                "No mesh object selected. Select a mesh object to validate.",
            )
            return {"CANCELLED"}

        # Verify minimum geometry.
        if (
            len(obj.data.vertices) < 4
            or len(obj.data.polygons) < 4
        ):
            self.report(
                {"ERROR"},
                "Mesh must have at least 4 vertices and 4 faces.",
            )
            return {"CANCELLED"}

        # Get validator settings from scene properties.
        tessera = context.scene.tessera
        vs = tessera.validator

        # FR-039: Run validation in read-only mode (no auto_repair).
        validator = PrintValidator()
        report = validator.validate(
            context=context,
            obj=obj,
            printer_type=vs.printer_type,
            wall_thickness_mm=vs.wall_thickness_mm,
            overhang_angle_deg=vs.overhang_angle_deg,
            build_volume_mm=(vs.build_x_mm, vs.build_y_mm, vs.build_z_mm),
            auto_repair=False,  # FR-039: No repair in validation-only.
            auto_scale=False,
            voxel_size_mm=vs.voxel_size_mm,
        )

        # FR-031: Display summary in Blender Info area.
        summary = report.to_text()
        if report.has_failures:
            self.report({"WARNING"}, summary)
        else:
            self.report({"INFO"}, summary)

        return {"FINISHED"}


# Classes to register
classes = [
    TESSERA_OT_validate_print,
]
