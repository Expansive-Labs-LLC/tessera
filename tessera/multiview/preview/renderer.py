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

"""Preview render pipeline using Blender's Workbench engine.

Renders 4 canonical preview images of a reconstructed mesh for
quick visual validation before the user commits to cleanup and
export.

Note: ``bpy`` is imported lazily inside method bodies so this
module can be imported in test environments without Blender.

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    PreviewRenderer — 4-view Workbench preview renders (FR-028)
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from ...multiview.preview.camera_setup import (
    PREVIEW_RESOLUTION,
    PREVIEW_VIEWS,
    PreviewImage,
    compute_camera_position,
    compute_framing_distance,
)

if TYPE_CHECKING:
    import bpy

logger = logging.getLogger("tessera.multiview")

# SEC-006: Allowed view label pattern for sanitised filenames.
_VIEW_LABEL_PATTERN = re.compile(r"^[a-z_]+$")


class PreviewRenderer:
    """Renders 4 canonical preview images of a reconstructed mesh.

    Uses Blender's Workbench engine for fast solid-shading renders
    at 512×512 resolution.  Creates temporary cameras and lights
    for each view, renders to PNG, and cleans up all temporary
    objects afterwards.

    Blender interaction is isolated to this class per CON-007 —
    no other multi-view module touches ``bpy``.

    Implements: FR-028 through FR-035, FR-037, CON-007, CON-010,
        SEC-004, SEC-006.
    """

    def render_previews(
        self,
        obj: bpy.types.Object,
        output_dir: str,
    ) -> list[PreviewImage]:
        """Render 4 preview images of the given object.

        Args:
            obj: A Blender mesh object in the active scene.
            output_dir: Directory to write preview PNGs.  Created
                if it doesn't exist.

        Returns:
            List of 4 ``PreviewImage`` dataclasses — one per canonical
            view (front, right, top, isometric).

        Raises:
            ValueError: If the object is invalid or not in the active
                scene (FR-037).

        Implements: FR-028 through FR-035, FR-037.
        """
        import bpy  # Lazy import — Blender-only module

        # FR-037: Validate object
        self._validate_object(obj)

        # SEC-004: Validate and resolve output directory
        output_path = self._validate_output_dir(output_dir)

        # Save and configure render settings
        original_settings = self._save_render_settings()

        # Track temporary objects for cleanup (CON-010)
        temp_objects: list = []

        try:
            self._configure_workbench()

            # Get object bounding box for camera framing (FR-031)
            bbox_dims = self._get_bbox_dimensions(obj)

            previews: list[PreviewImage] = []

            for view in PREVIEW_VIEWS:
                label = view["label"]
                azimuth = view["azimuth"]
                elevation = view["elevation"]

                # SEC-006: Sanitise view label for filename
                if not _VIEW_LABEL_PATTERN.match(label):
                    logger.warning("Skipping view with invalid label: %s", label)
                    continue

                logger.info(
                    "Preview render started: view_label=%s, resolution=%s",
                    label,
                    PREVIEW_RESOLUTION,
                )

                start = time.monotonic()

                # Create temporary camera
                camera_obj = self._create_camera(
                    label, azimuth, elevation, bbox_dims, obj
                )
                temp_objects.append(camera_obj)

                # Create temporary light
                light_obj = self._create_light(label, azimuth, elevation, bbox_dims)
                temp_objects.append(light_obj)

                # Set active camera
                bpy.context.scene.camera = camera_obj

                # Render
                filename = f"preview_{label}.png"
                filepath = str(output_path / filename)
                bpy.context.scene.render.filepath = filepath
                bpy.ops.render.render(write_still=True)

                duration = time.monotonic() - start

                preview = PreviewImage(
                    view_label=label,
                    filepath=filepath,
                    resolution=PREVIEW_RESOLUTION,
                    camera_pose={
                        "azimuth": azimuth,
                        "elevation": elevation,
                    },
                )
                previews.append(preview)

                logger.info(
                    "Preview render completed: view_label=%s, "
                    "filepath=%s, duration_s=%.2f",
                    label,
                    filename,
                    duration,
                )

            return previews

        finally:
            # FR-034, CON-010: Clean up temporary objects
            self._cleanup_temp_objects(temp_objects)
            # Restore original render settings
            self._restore_render_settings(original_settings)

    def _validate_object(self, obj: bpy.types.Object) -> None:
        """Validate the object exists in the active Blender scene.

        Args:
            obj: The Blender object to validate.

        Raises:
            ValueError: If the object is invalid or not in the scene.

        Implements: FR-037, EC-007.
        """
        import bpy  # Lazy import

        obj_name = getattr(obj, "name", "<unknown>")

        # Check if the object reference is valid
        try:
            _ = obj.name
        except (ReferenceError, AttributeError):
            raise ValueError(
                f"Object '{obj_name}' not found in the active " "Blender scene."
            )

        # Check if the object is in the active scene
        scene_objects = bpy.context.scene.objects
        if obj.name not in scene_objects:
            raise ValueError(
                f"Object '{obj.name}' not found in the active " "Blender scene."
            )

    def _validate_output_dir(self, output_dir: str) -> Path:
        """Validate and resolve the output directory path.

        Resolves the path to prevent traversal attacks and creates
        the directory if it doesn't exist.

        Args:
            output_dir: Path to the output directory.

        Returns:
            Resolved ``Path`` object.

        Implements: SEC-004.
        """
        resolved = Path(output_dir).resolve()

        # SEC-004: Check for path traversal
        try:
            resolved.relative_to(resolved.parent)
        except ValueError:
            raise ValueError(f"Invalid output directory path: {output_dir}")

        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    def _save_render_settings(self) -> dict:
        """Save current render settings for restoration.

        Returns:
            Dict of saved settings.
        """
        import bpy  # Lazy import

        scene = bpy.context.scene
        render = scene.render
        return {
            "engine": render.engine,
            "resolution_x": render.resolution_x,
            "resolution_y": render.resolution_y,
            "resolution_percentage": render.resolution_percentage,
            "film_transparent": render.film_transparent,
            "filepath": render.filepath,
            "image_settings_format": render.image_settings.file_format,
            "camera": scene.camera,
        }

    def _restore_render_settings(self, settings: dict) -> None:
        """Restore previously saved render settings.

        Args:
            settings: Dict from ``_save_render_settings()``.
        """
        import bpy  # Lazy import

        scene = bpy.context.scene
        render = scene.render
        render.engine = settings["engine"]
        render.resolution_x = settings["resolution_x"]
        render.resolution_y = settings["resolution_y"]
        render.resolution_percentage = settings["resolution_percentage"]
        render.film_transparent = settings["film_transparent"]
        render.filepath = settings["filepath"]
        render.image_settings.file_format = settings["image_settings_format"]
        scene.camera = settings["camera"]

    def _configure_workbench(self) -> None:
        """Configure Blender for Workbench rendering.

        Sets the render engine to Workbench with solid shading and
        a neutral gray material.

        Implements: FR-030.
        """
        import bpy  # Lazy import

        render = bpy.context.scene.render
        render.engine = "BLENDER_WORKBENCH"
        render.resolution_x = PREVIEW_RESOLUTION[0]
        render.resolution_y = PREVIEW_RESOLUTION[1]
        render.resolution_percentage = 100
        render.film_transparent = True
        render.image_settings.file_format = "PNG"

        # Configure Workbench shading
        shading = bpy.context.scene.display.shading
        shading.light = "STUDIO"
        shading.color_type = "SINGLE"
        shading.single_color = (0.6, 0.6, 0.6)  # Neutral gray

    def _get_bbox_dimensions(self, obj: bpy.types.Object) -> tuple[float, float, float]:
        """Get the bounding box dimensions of an object.

        Args:
            obj: The Blender object.

        Returns:
            ``(width, depth, height)`` of the bounding box.
        """
        import bpy  # Lazy import

        bbox = [
            obj.matrix_world @ bpy.mathutils.Vector(corner) for corner in obj.bound_box
        ]

        xs = [v.x for v in bbox]
        ys = [v.y for v in bbox]
        zs = [v.z for v in bbox]

        return (
            max(xs) - min(xs),
            max(ys) - min(ys),
            max(zs) - min(zs),
        )

    def _create_camera(
        self,
        label: str,
        azimuth: float,
        elevation: float,
        bbox_dims: tuple[float, float, float],
        target_obj: bpy.types.Object,
    ) -> bpy.types.Object:
        """Create a temporary camera for a preview view.

        Args:
            label: View label for naming.
            azimuth: Camera azimuth in degrees.
            elevation: Camera elevation in degrees.
            bbox_dims: Object bounding box dimensions.
            target_obj: The object to frame.

        Returns:
            The created camera object.

        Implements: FR-029, FR-031.
        """
        import bpy  # Lazy import

        cam_name = f"_bf_preview_cam_{label}"
        cam_data = bpy.data.cameras.new(cam_name)
        cam_data.lens = 50  # 50mm lens
        cam_data.clip_start = 0.01
        cam_data.clip_end = 100.0

        cam_obj = bpy.data.objects.new(cam_name, cam_data)
        bpy.context.scene.collection.objects.link(cam_obj)

        # Compute camera distance for framing (FR-031)
        distance = compute_framing_distance(bbox_dims)
        pos = compute_camera_position(azimuth, elevation, distance)

        cam_obj.location = pos

        # Point camera at the object center
        target_loc = target_obj.location
        direction = bpy.mathutils.Vector(target_loc) - bpy.mathutils.Vector(pos)
        rot_quat = direction.to_track_quat("-Z", "Y")
        cam_obj.rotation_euler = rot_quat.to_euler()

        return cam_obj

    def _create_light(
        self,
        label: str,
        azimuth: float,
        elevation: float,
        bbox_dims: tuple[float, float, float],
    ) -> bpy.types.Object:
        """Create a temporary light for a preview view.

        Positions a sun light slightly offset from the camera position
        for clean preview illumination.

        Args:
            label: View label for naming.
            azimuth: Camera azimuth in degrees.
            elevation: Camera elevation in degrees.
            bbox_dims: Object bounding box dimensions.

        Returns:
            The created light object.
        """
        import bpy  # Lazy import

        light_name = f"_bf_preview_light_{label}"
        light_data = bpy.data.lights.new(light_name, type="SUN")
        light_data.energy = 2.0

        light_obj = bpy.data.objects.new(light_name, light_data)
        bpy.context.scene.collection.objects.link(light_obj)

        # Position light slightly above and to the side of the camera
        distance = compute_framing_distance(bbox_dims) * 1.5
        pos = compute_camera_position(azimuth + 30.0, elevation + 20.0, distance)
        light_obj.location = pos

        return light_obj

    def _cleanup_temp_objects(
        self,
        temp_objects: list,
    ) -> None:
        """Remove temporary cameras and lights from the scene.

        Args:
            temp_objects: List of objects to remove.

        Implements: FR-034, CON-010.
        """
        import bpy  # Lazy import

        for obj in temp_objects:
            try:
                # Remove the object's data block (camera or light)
                data = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                # Clean up orphan data
                if data is not None:
                    if isinstance(data, bpy.types.Camera):
                        bpy.data.cameras.remove(data)
                    elif isinstance(data, bpy.types.Light):
                        bpy.data.lights.remove(data)
            except (ReferenceError, RuntimeError) as exc:
                logger.debug("Failed to clean up temp object: %s", exc)

        logger.debug(
            "Preview cleanup: removed %d temporary objects",
            len(temp_objects),
        )
