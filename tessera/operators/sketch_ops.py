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

"""Sketch-to-3D operators for Tessera.

Wires the SketchPipeline (SPEC-TS-0010) into Blender operators so
users can generate 3D meshes from hand-drawn sketch images.  Provides
both a full sketch-to-3D operator and a sketch detection-only operator
for pre-classification feedback.

Pipeline flow:
    scene.tessera.images → ImageInput → SketchPipeline.process()
    → SketchPipelineResult → MeshImporter.import_mesh() → bpy.types.Object

Implements: SPEC-TS-0010 FR-030–FR-039.
"""

from __future__ import annotations

import logging
import os

import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator

logger = logging.getLogger("tessera")


class TESSERA_OT_SketchGenerate(Operator):
    """Generate a 3D model from sketch images.

    Runs the sketch-to-3D pipeline:
    1. Classifies images as sketch vs. photo
    2. Preprocesses sketches (binarisation, thinning, perspective)
    3. Synthesises photo-realistic views via ControlNet
    4. Reconstructs a 3D mesh
    5. Applies bilateral symmetry enforcement

    Supports 1–2 sketch images (front and/or side views).
    Photos are automatically routed to the standard pipeline.
    """

    bl_idname = "tessera.sketch_generate"
    bl_label = "Sketch to 3D"
    bl_description = (
        "Generate a 3D model from hand-drawn sketch images "
        "using ControlNet synthesis and reconstruction"
    )
    bl_options = {"REGISTER", "UNDO"}

    # Operator properties exposed in the redo panel
    synthesis_prompt: StringProperty(
        name="Prompt",
        description=(
            "Text prompt describing the sketched object "
            "(e.g., 'a ceramic vase'). Leave blank for default."
        ),
        default="",
    )  # type: ignore[assignment]

    guidance_scale: FloatProperty(
        name="Guidance Scale",
        description="ControlNet conditioning strength (higher = more faithful to sketch)",
        default=7.5,
        min=1.0,
        max=20.0,
        step=50,
        precision=1,
    )  # type: ignore[assignment]

    num_inference_steps: IntProperty(
        name="Inference Steps",
        description="Diffusion sampling steps (higher = better quality, slower)",
        default=30,
        min=10,
        max=100,
    )  # type: ignore[assignment]

    synthesis_seed: IntProperty(
        name="Seed",
        description="Random seed for reproducible synthesis (0 = random)",
        default=42,
        min=0,
    )  # type: ignore[assignment]

    enable_symmetry: BoolProperty(
        name="Symmetry",
        description="Apply bilateral symmetry enforcement to the output mesh",
        default=True,
    )  # type: ignore[assignment]

    @classmethod
    def poll(cls, context):
        """Enable when at least one image is loaded."""
        if not hasattr(context.scene, "tessera"):
            return False
        props = context.scene.tessera
        return len(props.images) > 0

    def execute(self, context):
        """Run the sketch-to-3D pipeline."""
        props = context.scene.tessera

        # ------------------------------------------------------------------
        # Step 1: Collect images (max 2 for sketch pathway)
        # ------------------------------------------------------------------
        image_count = len(props.images)
        if image_count == 0:
            self.report({"WARNING"}, "No images loaded. Add sketch images first.")
            return {"CANCELLED"}

        if image_count > 2:
            self.report(
                {"WARNING"},
                f"Sketch-to-3D supports max 2 images (front + side). "
                f"Currently {image_count} loaded. Using first 2.",
            )

        self.report(
            {"INFO"},
            f"Starting sketch-to-3D with {min(image_count, 2)} image(s)...",
        )
        logger.info(
            "Sketch generation started: image_count=%d", image_count
        )

        props.pipeline_status = "Initializing sketch pipeline..."
        props.pipeline_progress = 0.0

        # Build ImageInput list (max 2)
        from tessera.vision.types import ImageInput

        image_inputs = []
        for item in list(props.images)[:2]:
            filepath = bpy.path.abspath(item.filepath)
            if not os.path.isfile(filepath):
                self.report({"WARNING"}, f"Image not found: {item.name}")
                logger.warning("Image file not found: %s", item.name)
                continue

            view_label = None
            if item.view_label != "UNLABELED":
                view_label = item.view_label.lower().replace("_", "-")

            image_inputs.append(
                ImageInput(filepath=filepath, view_label=view_label)
            )

        if not image_inputs:
            self.report({"WARNING"}, "No valid image files found.")
            props.pipeline_status = ""
            props.pipeline_progress = 0.0
            return {"CANCELLED"}

        # ------------------------------------------------------------------
        # Step 2: Build config and run sketch pipeline
        # ------------------------------------------------------------------
        try:
            props.pipeline_status = "Running sketch pipeline..."
            props.pipeline_progress = 0.1

            from tessera.sketch import SketchPipeline
            from tessera.sketch.types import SketchConfig

            # Access cache_dir from addon preferences
            addon_prefs = context.preferences.addons.get("tessera")
            if addon_prefs and hasattr(addon_prefs, "preferences"):
                cache_dir = addon_prefs.preferences.cache_dir
            else:
                cache_dir = os.path.join(
                    bpy.utils.user_resource("SCRIPTS"),
                    "addons", "tessera", "cache",
                )

            config = SketchConfig(
                symmetry_enabled=self.enable_symmetry,
                guidance_scale=self.guidance_scale,
                num_inference_steps=self.num_inference_steps,
                synthesis_seed=self.synthesis_seed,
                synthesis_prompt=(
                    self.synthesis_prompt if self.synthesis_prompt else None
                ),
            )

            pipeline = SketchPipeline(cache_dir=cache_dir)
            result = pipeline.process(inputs=image_inputs, config=config)

            if not result.success:
                error_msg = (
                    f"Sketch pipeline failed: {result.error_message}"
                )
                self.report({"ERROR"}, error_msg)
                logger.error(error_msg)
                props.pipeline_status = "Sketch pipeline failed"
                props.pipeline_progress = 0.0
                return {"CANCELLED"}

            # Report warnings
            for warning in result.warnings:
                self.report({"WARNING"}, warning)
                logger.warning("Sketch pipeline warning: %s", warning)

            # Handle photo-only result (no mesh produced)
            if result.mesh is None and result.success:
                self.report(
                    {"INFO"},
                    "All images classified as photos. "
                    "Use 'Generate 3D Model' instead.",
                )
                props.pipeline_status = "No sketches detected"
                props.pipeline_progress = 0.0
                return {"CANCELLED"}

            logger.info(
                "Sketch pipeline complete: symmetry_applied=%s, "
                "total_time_s=%.2f",
                result.symmetry_applied,
                result.total_time_s,
            )
        except Exception as exc:
            error_msg = f"Sketch pipeline failed: {exc}"
            self.report({"ERROR"}, error_msg)
            logger.error(error_msg, exc_info=True)
            props.pipeline_status = "Sketch pipeline failed"
            props.pipeline_progress = 0.0
            return {"CANCELLED"}

        # ------------------------------------------------------------------
        # Step 3: Import mesh into Blender scene
        # ------------------------------------------------------------------
        try:
            props.pipeline_status = "Importing sketch mesh..."
            props.pipeline_progress = 0.9

            from tessera.mesh.importer import MeshImporter

            importer = MeshImporter()
            obj = importer.import_mesh(
                vertices=result.mesh.vertices,
                faces=result.mesh.faces,
                source_model="sketch_pipeline",
            )

            # Apply vertex colors if available
            if result.mesh.vertex_colors is not None:
                self._apply_vertex_colors(obj, result.mesh.vertex_colors)

            logger.info(
                "Sketch mesh imported: object_name=%s, "
                "vertex_count=%d, face_count=%d",
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
        props.pipeline_status = "Sketch generation complete"
        props.pipeline_progress = 1.0

        sym_tag = " (symmetry applied)" if result.symmetry_applied else ""
        self.report(
            {"INFO"},
            f"Sketch → 3D complete: {obj.name} "
            f"({len(result.mesh.vertices)} vertices, "
            f"{len(result.mesh.faces)} faces){sym_tag}",
        )
        return {"FINISHED"}

    @staticmethod
    def _apply_vertex_colors(obj, vertex_colors):
        """Apply per-vertex RGB colors to the mesh object.

        Args:
            obj: The Blender mesh object.
            vertex_colors: (N, 3) float32 array, values in [0.0, 1.0].
        """
        mesh = obj.data
        if not mesh.vertex_colors:
            mesh.vertex_colors.new(name="TesseraColor")
        color_layer = mesh.vertex_colors.active

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


class TESSERA_OT_SketchDetect(Operator):
    """Classify loaded images as sketch or photo.

    Runs only the sketch detection stage for quick feedback
    without triggering full reconstruction. Results are reported
    as INFO messages per image.
    """

    bl_idname = "tessera.sketch_detect"
    bl_label = "Detect Sketches"
    bl_description = (
        "Classify loaded images as sketch or photo "
        "without running full reconstruction"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        """Enable when at least one image is loaded."""
        if not hasattr(context.scene, "tessera"):
            return False
        props = context.scene.tessera
        return len(props.images) > 0

    def execute(self, context):
        """Run sketch detection on all loaded images."""
        props = context.scene.tessera

        props.pipeline_status = "Detecting sketches..."
        props.pipeline_progress = 0.0

        try:
            import numpy as np
            from PIL import Image as PILImage

            from tessera.sketch import SketchDetector

            # Access cache_dir from addon preferences
            addon_prefs = context.preferences.addons.get("tessera")
            if addon_prefs and hasattr(addon_prefs, "preferences"):
                cache_dir = addon_prefs.preferences.cache_dir
            else:
                cache_dir = os.path.join(
                    bpy.utils.user_resource("SCRIPTS"),
                    "addons", "tessera", "cache",
                )

            detector = SketchDetector(cache_dir=cache_dir)
            total = len(props.images)
            sketch_count = 0

            for i, item in enumerate(props.images):
                filepath = bpy.path.abspath(item.filepath)
                if not os.path.isfile(filepath):
                    self.report(
                        {"WARNING"}, f"Image not found: {item.name}"
                    )
                    continue

                props.pipeline_progress = (i + 1) / total

                # Load and classify
                img = PILImage.open(filepath).convert("RGB")
                image_array = np.array(img, dtype=np.uint8)
                result = detector.classify(image_array)

                classification = "SKETCH" if result.is_sketch else "PHOTO"
                if result.is_sketch:
                    sketch_count += 1

                self.report(
                    {"INFO"},
                    f"{item.name}: {classification} "
                    f"(confidence: {result.confidence:.0%}, "
                    f"type: {result.sketch_type}, "
                    f"method: {result.detection_method})",
                )

            props.pipeline_status = (
                f"Detection complete: {sketch_count} sketch(es), "
                f"{total - sketch_count} photo(s)"
            )
            props.pipeline_progress = 1.0

            self.report(
                {"INFO"},
                f"Detection complete: {sketch_count} sketch(es), "
                f"{total - sketch_count} photo(s) out of {total}",
            )
            return {"FINISHED"}

        except Exception as exc:
            error_msg = f"Sketch detection failed: {exc}"
            self.report({"ERROR"}, error_msg)
            logger.error(error_msg, exc_info=True)
            props.pipeline_status = "Detection failed"
            props.pipeline_progress = 0.0
            return {"CANCELLED"}


# Classes to register
classes = [
    TESSERA_OT_SketchGenerate,
    TESSERA_OT_SketchDetect,
]
