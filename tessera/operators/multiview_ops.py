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

"""Multi-view alignment and reconstruction operators for Tessera.

Wires the StrategySelector (SPEC-TS-0007) to automatically route
reconstruction through single-image or multi-view paths based on
image count and view-label quality.  Also provides a 4-view preview
render operator for quick visual validation.

Pipeline flow:
    scene.tessera.images → ImageInput → VisionPipeline.process()
    → VisionResult list → StrategySelector.reconstruct()
    → ReconstructionResult → MeshImporter.import_mesh() → bpy.types.Object

    For preview:
    selected bpy.types.Object → PreviewRenderer.render_previews()
    → 4× preview PNGs displayed in Blender image viewer

Implements: SPEC-TS-0007 FR-001–FR-004, FR-025–FR-037.
"""

from __future__ import annotations

import logging
import os
import tempfile

import bpy
from bpy.types import Operator

logger = logging.getLogger("tessera")


class TESSERA_OT_MultiViewGenerate(Operator):
    """Generate a 3D model using multi-view aware reconstruction.

    Runs the full pipeline with StrategySelector routing:
    1. Collects images from the Tessera image list
    2. Runs vision analysis on all images
    3. Routes to single-image or multi-view reconstruction
       based on image count (1–2 → single, 3–12 → multi-view)
    4. Imports the resulting mesh into the active Blender scene

    Requires ≥3 images for multi-view path; falls back to
    single-image if pose estimation fails.
    """

    bl_idname = "tessera.multiview_generate"
    bl_label = "Multi-View Generate"
    bl_description = (
        "Generate a 3D model using multi-view alignment "
        "(requires 3+ images for best results)"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Enable when at least 3 images are loaded for multi-view."""
        if not hasattr(context.scene, "tessera"):
            return False
        props = context.scene.tessera
        return len(props.images) >= 3

    def execute(self, context):
        """Run the multi-view generation pipeline."""
        props = context.scene.tessera

        # ------------------------------------------------------------------
        # Step 1: Collect images from the UI list
        # ------------------------------------------------------------------
        image_count = len(props.images)
        if image_count < 3:
            self.report(
                {"WARNING"},
                "Multi-view generation requires at least 3 images. "
                f"Currently {image_count} loaded.",
            )
            return {"CANCELLED"}

        if image_count > 12:
            self.report(
                {"WARNING"},
                f"Too many images ({image_count}). Maximum supported: 12.",
            )
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            f"Starting multi-view generation with {image_count} image(s)...",
        )
        logger.info("Multi-view generation started: image_count=%d", image_count)

        props.pipeline_status = "Initializing multi-view pipeline..."
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

            view_label = None
            if item.view_label != "UNLABELED":
                view_label = item.view_label.lower().replace("_", "-")

            image_inputs.append(ImageInput(filepath=filepath, view_label=view_label))

        if len(image_inputs) < 3:
            self.report(
                {"WARNING"},
                "Fewer than 3 valid image files found. "
                "Multi-view requires at least 3.",
            )
            props.pipeline_status = ""
            props.pipeline_progress = 0.0
            return {"CANCELLED"}

        # ------------------------------------------------------------------
        # Step 2: Run vision pipeline on all images
        # ------------------------------------------------------------------
        try:
            props.pipeline_status = "Running vision analysis..."
            props.pipeline_progress = 0.1

            from ..vision import VisionPipeline

            pipeline = VisionPipeline()
            vision_results = pipeline.process(image_inputs)

            logger.info(
                "Vision pipeline complete: results=%d",
                len(vision_results),
            )
        except Exception as exc:
            error_msg = f"Vision pipeline failed: {exc}"
            self.report({"ERROR"}, error_msg)
            logger.error(error_msg, exc_info=True)
            props.pipeline_status = "Vision pipeline failed"
            props.pipeline_progress = 0.0
            return {"CANCELLED"}

        # ------------------------------------------------------------------
        # Step 3: Run StrategySelector (multi-view aware routing)
        # ------------------------------------------------------------------
        try:
            props.pipeline_status = "Running multi-view reconstruction..."
            props.pipeline_progress = 0.4

            from ..multiview import (
                HlocPoseEstimator,
                MultiViewAdapter,
                StrategySelector,
            )
            from ..reconstruction.engine import ReconstructionEngine

            # Access cache_dir from addon preferences
            addon_prefs = context.preferences.addons.get("tessera")
            if addon_prefs and hasattr(addon_prefs, "preferences"):
                cache_dir = addon_prefs.preferences.cache_dir
            else:
                cache_dir = os.path.join(
                    bpy.utils.user_resource("SCRIPTS"),
                    "addons",
                    "tessera",
                    "cache",
                )

            # Build the strategy selector with both adapters
            engine = ReconstructionEngine(cache_dir=cache_dir)
            single_adapter = engine.get_best_adapter()
            multi_adapter = MultiViewAdapter(cache_dir=cache_dir)
            pose_estimator = HlocPoseEstimator(cache_dir=cache_dir)

            selector = StrategySelector(
                single_adapter=single_adapter,
                multi_adapter=multi_adapter,
                pose_estimator=pose_estimator,
            )

            result = selector.reconstruct(vision_results)

            if not result.success:
                error_msg = (
                    f"Multi-view reconstruction failed: " f"{result.error_message}"
                )
                self.report({"ERROR"}, error_msg)
                logger.error(error_msg)
                props.pipeline_status = "Reconstruction failed"
                props.pipeline_progress = 0.0
                return {"CANCELLED"}

            # Report any warnings (including fallback notices)
            for warning in result.warnings:
                self.report({"WARNING"}, warning)
                logger.warning("Reconstruction warning: %s", warning)

            strategy = result.mesh.metadata.get("strategy", "unknown")
            logger.info(
                "Reconstruction complete: strategy=%s, " "vertices=%d, faces=%d",
                strategy,
                result.mesh.metadata.get("vertex_count", 0),
                result.mesh.metadata.get("face_count", 0),
            )
        except Exception as exc:
            error_msg = f"Multi-view reconstruction failed: {exc}"
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
            props.pipeline_progress = 0.85

            from ..mesh.importer import MeshImporter

            importer = MeshImporter()
            source = result.source_adapter or strategy
            obj = importer.import_mesh(
                vertices=result.mesh.vertices,
                faces=result.mesh.faces,
                source_model=source,
            )

            # Apply vertex colors if available
            if result.mesh.vertex_colors is not None:
                self._apply_vertex_colors(obj, result.mesh.vertex_colors)

            logger.info(
                "Mesh imported: object_name=%s, vertex_count=%d, " "face_count=%d",
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
        props.pipeline_status = f"Complete ({strategy})"
        props.pipeline_progress = 1.0

        self.report(
            {"INFO"},
            f"3D model generated via {strategy}: {obj.name} "
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


class TESSERA_OT_PreviewRender(Operator):
    """Render 4-view preview images of the selected mesh.

    Uses Blender's Workbench engine to quickly render front, right,
    top, and isometric views at 512×512 for visual validation before
    committing to cleanup and export.
    """

    bl_idname = "tessera.preview_render"
    bl_label = "Render Previews"
    bl_description = (
        "Render 4-view preview images (front, right, top, isometric) "
        "of the selected mesh for visual validation"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        """Enable when a mesh object is selected."""
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def execute(self, context):
        """Render 4-view previews of the active mesh object."""
        obj = context.active_object
        props = context.scene.tessera

        self.report({"INFO"}, f"Rendering previews for {obj.name}...")
        props.pipeline_status = "Rendering previews..."
        props.pipeline_progress = 0.1

        # Determine output directory
        if bpy.data.filepath:
            base_dir = os.path.dirname(bpy.data.filepath)
        else:
            base_dir = tempfile.gettempdir()
        output_dir = os.path.join(base_dir, "tessera_previews")

        try:
            from ..multiview.preview.renderer import PreviewRenderer

            renderer = PreviewRenderer()
            previews = renderer.render_previews(obj, output_dir)

            props.pipeline_status = "Previews complete"
            props.pipeline_progress = 1.0

            self.report(
                {"INFO"},
                f"Rendered {len(previews)} preview(s) to {output_dir}",
            )

            # Open the first preview in Blender's image viewer
            if previews:
                first_path = previews[0].filepath
                if os.path.isfile(first_path):
                    img = bpy.data.images.load(first_path)
                    # Try to show in an image editor if available
                    for area in context.screen.areas:
                        if area.type == "IMAGE_EDITOR":
                            area.spaces.active.image = img
                            break

            logger.info(
                "Preview render complete: count=%d, output_dir=%s",
                len(previews),
                output_dir,
            )
            return {"FINISHED"}

        except Exception as exc:
            error_msg = f"Preview render failed: {exc}"
            self.report({"ERROR"}, error_msg)
            logger.error(error_msg, exc_info=True)
            props.pipeline_status = "Preview render failed"
            props.pipeline_progress = 0.0
            return {"CANCELLED"}


# Classes to register
classes = [
    TESSERA_OT_MultiViewGenerate,
    TESSERA_OT_PreviewRender,
]
