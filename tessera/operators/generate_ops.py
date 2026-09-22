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

"""Generation operators for Tessera.

Wires the vision pipeline (SPEC-TS-0003) to the reconstruction engine
(SPEC-TS-0004) and imports the resulting mesh into the Blender scene
via the mesh importer (SPEC-TS-0005).

Pipeline flow:
    scene.tessera.images → ImageInput → VisionPipeline.process()
    → VisionResult → ReconstructionEngine.reconstruct()
    → StandardMesh → MeshImporter.import_mesh() → bpy.types.Object

Implements: FR-011, FR-020.
"""

from __future__ import annotations

import logging
import os

import bpy
from bpy.types import Operator

from ..addon import get_addon_preferences

logger = logging.getLogger("tessera")


class TESSERA_OT_Generate(Operator):
    """Generate a 3D model from loaded reference images.

    Runs the full pipeline:
    1. Collects images from the Tessera image list
    2. Runs vision analysis (segmentation, depth, view classification, features)
    3. Runs 3D reconstruction via the best available adapter
    4. Imports the resulting mesh into the active Blender scene
    """

    bl_idname = "tessera.generate"
    bl_label = "Generate 3D Model"
    bl_description = "Generate a 3D model from reference images using AI reconstruction"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Enable when at least one image is loaded."""
        if context is None or not hasattr(context.scene, "tessera"):
            return False
        props = context.scene.tessera
        return len(props.images) > 0

    def execute(self, context):
        """Run the full generation pipeline."""
        props = context.scene.tessera

        # ------------------------------------------------------------------
        # Step 1: Collect images from the UI list
        # ------------------------------------------------------------------
        image_count = len(props.images)
        if image_count == 0:
            self.report({"WARNING"}, "No images loaded. Add reference images first.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Starting generation with {image_count} image(s)...")
        logger.info("Generation started: image_count=%d", image_count)

        # Update UI status
        props.pipeline_status = "Initializing pipeline..."
        props.pipeline_progress = 0.0

        # Build ImageInput list from scene properties
        from ..vision.types import ImageInput

        image_inputs = []
        for item in props.images:
            filepath = bpy.path.abspath(item.filepath)
            if not os.path.isfile(filepath):
                self.report({"WARNING"}, f"Image not found: {item.name}")
                logger.warning("Image file not found: %s", item.name)
                continue

            # Map Blender enum to vision pipeline view label
            view_label = None
            if item.view_label != "UNLABELED":
                view_label = item.view_label.lower().replace("_", "-")

            image_inputs.append(ImageInput(filepath=filepath, view_label=view_label))

        if not image_inputs:
            self.report({"WARNING"}, "No valid image files found.")
            props.pipeline_status = ""
            props.pipeline_progress = 0.0
            return {"CANCELLED"}

        # ------------------------------------------------------------------
        # Step 2: Run vision pipeline
        # ------------------------------------------------------------------
        try:
            props.pipeline_status = "Running vision analysis..."
            props.pipeline_progress = 0.1

            from ..vision import VisionPipeline

            pipeline = VisionPipeline()
            vision_results = pipeline.process(image_inputs)

            logger.info("Vision pipeline complete: results=%d", len(vision_results))
        except Exception as exc:
            error_msg = f"Vision pipeline failed: {exc}"
            self.report({"ERROR"}, error_msg)
            logger.error(error_msg, exc_info=True)
            props.pipeline_status = "Vision pipeline failed"
            props.pipeline_progress = 0.0
            return {"CANCELLED"}

        # ------------------------------------------------------------------
        # Step 3: Run reconstruction engine
        # ------------------------------------------------------------------
        try:
            props.pipeline_status = "Reconstructing 3D mesh..."
            props.pipeline_progress = 0.6

            from ..reconstruction.engine import ReconstructionEngine

            # Access cache_dir from addon preferences
            addon_prefs = get_addon_preferences(context)
            if addon_prefs is not None:
                cache_dir = addon_prefs.cache_dir
            else:
                # Fallback to default cache location
                import os

                cache_dir = os.path.join(
                    bpy.utils.user_resource("SCRIPTS"),
                    "addons",
                    "tessera",
                    "cache",
                )
            engine = ReconstructionEngine(cache_dir=cache_dir)
            result = engine.reconstruct(vision_results)

            if not result.success:
                error_msg = f"Reconstruction failed: {result.error_message}"
                self.report({"ERROR"}, error_msg)
                logger.error(error_msg)
                props.pipeline_status = "Reconstruction failed"
                props.pipeline_progress = 0.0
                return {"CANCELLED"}

            # Report any warnings
            for warning in result.warnings:
                self.report({"WARNING"}, warning)
                logger.warning("Reconstruction warning: %s", warning)

            logger.info(
                "Reconstruction complete: adapter=%s, vertices=%d, faces=%d",
                result.source_adapter,
                result.mesh.metadata.get("vertex_count", 0),
                result.mesh.metadata.get("face_count", 0),
            )
        except Exception as exc:
            error_msg = f"Reconstruction failed: {exc}"
            self.report({"ERROR"}, error_msg)
            logger.error(error_msg, exc_info=True)
            props.pipeline_status = "Reconstruction failed"
            props.pipeline_progress = 0.0
            return {"CANCELLED"}

        # ------------------------------------------------------------------
        # Step 4: Import mesh into Blender scene
        # ------------------------------------------------------------------
        try:
            props.pipeline_status = "Importing mesh..."
            props.pipeline_progress = 0.9

            from ..mesh.importer import MeshImporter

            importer = MeshImporter()
            source_model = result.source_adapter or "tessera"
            obj = importer.import_mesh(
                vertices=result.mesh.vertices,
                faces=result.mesh.faces,
                source_model=source_model,
            )

            # Apply vertex colors if available
            if result.mesh.vertex_colors is not None:
                self._apply_vertex_colors(obj, result.mesh.vertex_colors)

            logger.info(
                "Mesh imported: object_name=%s, vertex_count=%d, face_count=%d",
                obj.name,
                len(result.mesh.vertices),
                len(result.mesh.faces),
            )
        except Exception as exc:
            error_msg = f"Mesh import failed: {exc}"
            self.report({"ERROR"}, error_msg)
            logger.error(error_msg, exc_info=True)
            props.pipeline_status = "Import failed"
            props.pipeline_progress = 0.0
            return {"CANCELLED"}

        # ------------------------------------------------------------------
        # Done
        # ------------------------------------------------------------------
        props.pipeline_status = "Generation complete"
        props.pipeline_progress = 1.0

        self.report(
            {"INFO"},
            f"3D model generated: {obj.name} "
            f"({len(result.mesh.vertices)} vertices, "
            f"{len(result.mesh.faces)} faces)",
        )
        return {"FINISHED"}

    @staticmethod
    def _apply_vertex_colors(obj, vertex_colors):
        """Apply per-vertex RGB colors to the mesh object.

        Creates a vertex color layer and sets values from the
        (N, 3) float32 array.

        Args:
            obj: The Blender mesh object.
            vertex_colors: (N, 3) float32 array, values in [0.0, 1.0].
        """

        mesh = obj.data
        if not mesh.vertex_colors:
            mesh.vertex_colors.new(name="TesseraColor")
        color_layer = mesh.vertex_colors.active

        # Set per-loop vertex colors
        for poly in mesh.polygons:
            for loop_idx in poly.loop_indices:
                vert_idx = mesh.loops[loop_idx].vertex_index
                if vert_idx < len(vertex_colors):
                    r, g, b = vertex_colors[vert_idx]
                    color_layer.data[loop_idx].color = (r, g, b, 1.0)

        logger.info(
            "Vertex colors applied: layer=%s, vertex_count=%d",
            color_layer.name,
            len(vertex_colors),
        )


# Classes to register
classes = [
    TESSERA_OT_Generate,
]
