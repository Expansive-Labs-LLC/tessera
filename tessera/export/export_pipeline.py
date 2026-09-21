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

"""Export pipeline: duplicate → validate → repair → export.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

Implements: FR-017, FR-021–FR-027, FR-035, FR-040,
    CON-003, CON-004, CON-005, SEC-002, SEC-003, SEC-006.
"""

from __future__ import annotations

import logging
import math
import os
import re
import time
from typing import Any

import bpy

from ..validator.data_types import ExportResult
from ..validator.print_validator import PrintValidator
from .obj_exporter import export_obj
from .stl_exporter import export_stl
from .threemf_exporter import export_threemf

logger = logging.getLogger("tessera.export")

# SEC-003: Regex for allowed filename characters.
_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_\-.]")

# Format exporter dispatch table.
_EXPORTERS = {
    "STL": export_stl,
    "3MF": export_threemf,
    "OBJ": export_obj,
}

# Format file extensions.
_EXTENSIONS = {
    "STL": "stl",
    "3MF": "3mf",
    "OBJ": "obj",
}


class ExportPipeline:
    """Full export pipeline: duplicate → validate → repair → export.

    Operates on a duplicate of the original mesh to preserve the
    user's edits (CON-003).

    Implements: FR-017, FR-021–FR-027, FR-035, FR-040,
        CON-003, CON-004, CON-005, SEC-002, SEC-003, SEC-006.
    """

    def execute(
        self,
        context: Any,
        obj: Any,
        export_formats: set[str] | None = None,
        export_directory: str = "",
        auto_repair: bool = True,
        auto_orient: bool = False,
        auto_scale: bool = False,
        force_export: bool = False,
        printer_type: str = "FDM",
        wall_thickness_mm: float = 1.2,
        overhang_angle_deg: float = 45.0,
        build_volume_mm: tuple[float, float, float] = (
            220.0,
            220.0,
            250.0,
        ),
        voxel_size_mm: float = 0.5,
    ) -> ExportResult:
        """Execute the full export pipeline.

        Args:
            context: Blender context.
            obj: Original ``bpy.types.Object`` with mesh data.
            export_formats: Set of format strings (``"STL"``, ``"3MF"``,
                ``"OBJ"``). Default: ``{"STL"}``.
            export_directory: Target directory for exported files.
            auto_repair: Attempt auto-repair on check failures.
            auto_orient: Rotate to minimize overhangs (FR-025).
            auto_scale: Auto-scale to fit build volume (FR-016).
            force_export: Export even if checks have ``FAIL`` results.
            printer_type: ``"FDM"`` or ``"SLA"``.
            wall_thickness_mm: Minimum wall thickness threshold.
            overhang_angle_deg: Overhang angle threshold.
            build_volume_mm: Build volume ``(x, y, z)`` in mm.
            voxel_size_mm: Voxel size for remesh fallback.

        Returns:
            ``ExportResult`` with report, exported file paths, and
            success status.

        Implements: FR-017, FR-021–FR-027, FR-035, FR-040.
        """
        if export_formats is None:
            export_formats = {"STL"}

        # Resolve export directory.
        export_dir = self._resolve_export_directory(export_directory)

        # Original object name (for file naming per FR-023).
        original_name = obj.name

        # FR-017: Duplicate the active mesh object.
        duplicate = self._duplicate_object(context, obj)

        try:
            # FR-040: Apply modifiers on duplicate.
            modifier_count = self._apply_modifiers(context, duplicate)
            if modifier_count > 0:
                logger.info(
                    "Applied %d modifier(s) on duplicate before validation.",
                    modifier_count,
                )

            # FR-026: Ensure mm scale.
            self._apply_mm_scale(context, duplicate)

            # FR-027: Flatten bottom to Z=0.
            self._align_bottom_z0(duplicate)

            # FR-025: Auto-orient if enabled.
            if auto_orient:
                self._auto_orient(duplicate, overhang_angle_deg)

            # Run validation with auto-repair on the duplicate.
            validator = PrintValidator()
            report = validator.validate(
                context=context,
                obj=duplicate,
                printer_type=printer_type,
                wall_thickness_mm=wall_thickness_mm,
                overhang_angle_deg=overhang_angle_deg,
                build_volume_mm=build_volume_mm,
                auto_repair=auto_repair,
                auto_scale=auto_scale,
                voxel_size_mm=voxel_size_mm,
            )

            # CON-004: Don't export without validation unless force.
            if report.has_failures and not force_export:
                return ExportResult(
                    report=report,
                    exported_files=[],
                    success=False,
                )

            # Export to each requested format.
            export_start = time.perf_counter()
            exported_files: list[str] = []

            # Sanitize the name for filenames.
            safe_name = _sanitize_filename(original_name)

            for fmt in export_formats:
                ext = _EXTENSIONS.get(fmt)
                exporter = _EXPORTERS.get(fmt)
                if ext is None or exporter is None:
                    logger.warning("Unknown export format: %s", fmt)
                    continue

                # CON-005: Handle file collisions.
                file_path = _resolve_file_path(
                    export_dir, safe_name, ext
                )

                # SEC-006: Validate path doesn't escape export dir.
                if not _validate_path_within_dir(export_dir, file_path):
                    logger.error(
                        "Export path %s escapes export directory %s",
                        file_path,
                        export_dir,
                    )
                    continue

                try:
                    # Select only the duplicate for export.
                    bpy.ops.object.select_all(action="DESELECT")
                    duplicate.select_set(True)
                    context.view_layer.objects.active = duplicate

                    exporter(file_path)

                    file_size = os.path.getsize(file_path)
                    logger.info(
                        "Export completed: format=%s, "
                        "file_size_bytes=%d, export_path=%s",
                        fmt,
                        file_size,
                        file_path,
                    )
                    exported_files.append(file_path)

                except Exception as exc:
                    logger.error(
                        "Export failed: format=%s, error_message=%s",
                        fmt,
                        str(exc),
                    )

            export_elapsed = time.perf_counter() - export_start
            report.export_time_seconds = export_elapsed

            # FR-029: Save validation report JSON.
            report_path = os.path.join(
                export_dir, f"{safe_name}_validation.json"
            )
            report.save_json(report_path)

            return ExportResult(
                report=report,
                exported_files=exported_files,
                success=len(exported_files) > 0,
            )

        finally:
            # FR-024: Delete the _print duplicate.
            self._delete_duplicate(context, duplicate)

    def _duplicate_object(
        self, context: Any, obj: Any
    ) -> Any:
        """Duplicate the mesh object for export processing.

        Args:
            context: Blender context.
            obj: Original object to duplicate.

        Returns:
            The duplicated ``bpy.types.Object``.

        Implements: FR-017.
        """
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        context.view_layer.objects.active = obj

        bpy.ops.object.duplicate()
        duplicate = context.active_object
        duplicate.name = f"{obj.name}_print"

        logger.debug("Duplicate object created: duplicate_name=%s", duplicate.name)
        return duplicate

    def _delete_duplicate(self, context: Any, duplicate: Any) -> None:
        """Delete the _print duplicate from the scene.

        Args:
            context: Blender context.
            duplicate: The duplicate object to delete.

        Implements: FR-024.
        """
        try:
            dup_name = duplicate.name
            bpy.ops.object.select_all(action="DESELECT")
            duplicate.select_set(True)
            context.view_layer.objects.active = duplicate
            bpy.ops.object.delete()
            logger.debug("Duplicate object deleted: duplicate_name=%s", dup_name)
        except Exception as exc:
            logger.warning("Failed to delete duplicate: %s", exc)

    def _apply_modifiers(self, context: Any, obj: Any) -> int:
        """Apply all modifiers on the duplicate.

        Args:
            context: Blender context.
            obj: The duplicate object.

        Returns:
            Number of modifiers applied.

        Implements: FR-040.
        """
        modifier_count = len(obj.modifiers)
        if modifier_count == 0:
            return 0

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")

        return modifier_count

    def _apply_mm_scale(self, context: Any, obj: Any) -> None:
        """Ensure the duplicate is scaled to millimeters.

        If the scene unit scale is not 0.001 (mm), applies a
        corrective scale transform.

        Args:
            context: Blender context.
            obj: The duplicate object.

        Implements: FR-026.
        """
        scene = context.scene
        unit_scale = scene.unit_settings.scale_length

        # Blender default is 1.0 (meters). For mm, scale_length = 0.001.
        if abs(unit_scale - 0.001) > 1e-6:
            scale_factor = 1000.0 * unit_scale
            obj.scale *= scale_factor

            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(scale=True)

            logger.debug(
                "Applied mm scale conversion: factor=%.3f", scale_factor
            )

    def _align_bottom_z0(self, obj: Any) -> None:
        """Translate object so its lowest vertex Z = 0.

        Args:
            obj: The duplicate object.

        Implements: FR-027.
        """
        from mathutils import Vector

        bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        min_z = min(v.z for v in bbox)

        if abs(min_z) > 1e-6:
            obj.location.z -= min_z
            logger.debug("Aligned bottom to Z=0: offset=%.4f", -min_z)

    def _auto_orient(
        self, obj: Any, overhang_angle_deg: float
    ) -> None:
        """Rotate object to minimize overhanging face area.

        Evaluates 576 candidate rotations (15° increments around
        X and Y axes) and selects the one with minimum overhang area.

        Args:
            obj: The duplicate object.
            overhang_angle_deg: Overhang angle threshold in degrees.

        Implements: FR-025.
        """
        import bmesh
        from mathutils import Euler, Vector

        threshold_rad = math.radians(overhang_angle_deg)
        up = Vector((0.0, 0.0, 1.0))

        best_rotation = Euler((0.0, 0.0, 0.0))
        min_overhang_area = float("inf")

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.faces.ensure_lookup_table()

            # Evaluate 576 candidate orientations.
            step = math.radians(15.0)
            for xi in range(24):
                for yi in range(24):
                    rx = xi * step
                    ry = yi * step
                    euler = Euler((rx, ry, 0.0))
                    rot_matrix = euler.to_matrix()

                    overhang_area = 0.0
                    for face in bm.faces:
                        rotated_normal = rot_matrix @ face.normal
                        angle_from_up = rotated_normal.angle(up)
                        if angle_from_up > (math.pi - threshold_rad):
                            overhang_area += face.calc_area()

                    if overhang_area < min_overhang_area:
                        min_overhang_area = overhang_area
                        best_rotation = Euler((rx, ry, 0.0))

        finally:
            bm.free()

        # Apply the best rotation.
        if best_rotation.x != 0.0 or best_rotation.y != 0.0:
            obj.rotation_euler = best_rotation
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.ops.object.transform_apply(rotation=True)

            logger.info(
                "Auto-orient applied: rotation=(%.1f°, %.1f°, 0°), "
                "overhang_area=%.2f",
                math.degrees(best_rotation.x),
                math.degrees(best_rotation.y),
                min_overhang_area,
            )

    def _resolve_export_directory(self, export_directory: str) -> str:
        """Resolve and validate the export directory.

        Falls back to ``.blend`` file directory, then home directory.

        Args:
            export_directory: User-specified directory path.

        Returns:
            Validated absolute directory path.

        Implements: FR-022, EC-006, SEC-002.
        """
        if export_directory:
            # SEC-002: Resolve symlinks.
            resolved = os.path.realpath(export_directory)
            return resolved

        # Try .blend file directory.
        blend_path = bpy.data.filepath
        if blend_path:
            return os.path.dirname(os.path.realpath(blend_path))

        # EC-006: Fall back to home directory.
        home = os.path.expanduser("~")
        logger.info(
            "Blend file not saved. Defaulting export directory to "
            "home directory: %s.",
            home,
        )
        return home


def _sanitize_filename(name: str) -> str:
    """Sanitize object name for use in filenames.

    Replaces characters not matching ``[a-zA-Z0-9_\\-\\.]`` with ``_``.

    Args:
        name: Raw object name.

    Returns:
        Sanitized filename-safe string.

    Implements: SEC-003.
    """
    sanitized = _SAFE_NAME_RE.sub("_", name)
    if not sanitized:
        sanitized = "export"
    return sanitized


def _resolve_file_path(
    directory: str, name: str, ext: str
) -> str:
    """Resolve file path with collision avoidance.

    Appends numeric suffixes (``_001``, ``_002``, etc.) if the file
    already exists.

    Args:
        directory: Export directory path.
        name: Sanitized object name.
        ext: File extension (without dot).

    Returns:
        Absolute path to the export file.

    Implements: CON-005.
    """
    base_path = os.path.join(directory, f"{name}.{ext}")
    if not os.path.exists(base_path):
        return base_path

    counter = 1
    while counter <= 999:
        suffixed = os.path.join(
            directory, f"{name}_{counter:03d}.{ext}"
        )
        if not os.path.exists(suffixed):
            return suffixed
        counter += 1

    raise RuntimeError(
        f"Too many file collisions for '{name}.{ext}' in '{directory}'. "
        f"Clean up existing files before exporting."
    )


def _validate_path_within_dir(
    directory: str, file_path: str
) -> bool:
    """Validate that file_path does not escape the export directory.

    Args:
        directory: Base export directory.
        file_path: Full file path to validate.

    Returns:
        ``True`` if the path is within the directory.

    Implements: SEC-006.
    """
    real_dir = os.path.realpath(directory)
    real_file = os.path.realpath(file_path)
    return os.path.commonpath([real_dir, real_file]) == real_dir
