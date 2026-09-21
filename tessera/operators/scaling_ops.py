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

"""Scaling and orientation operators for Tessera.

Provides operators for applying real-world scaling, optimizing print
orientation, and auto-inferring dimensions.

Spec: SPEC-TS-0008 (Real-World Scaling & Print Orientation)

Implements: FR-032, FR-034, CON-004, CON-008.
"""

from __future__ import annotations

import logging

import bpy
from bpy.types import Operator

logger = logging.getLogger("tessera.scaling")


class TESSERA_OT_ApplyScaling(Operator):
    """Apply real-world scaling to the active mesh object.

    Reads dimension targets from scene properties and runs the
    full ``ScalingOrientationPipeline``, including build-volume
    validation, orientation optimization, and base flattening.

    Uses a modal operator pattern per CON-008 to avoid blocking
    Blender's UI thread.

    Implements: FR-032, FR-034, CON-004, CON-008.
    """

    bl_idname = "tessera.apply_scaling"
    bl_label = "Apply Scaling & Orientation"
    bl_description = (
        "Scale the active mesh to target mm dimensions and optimize "
        "print orientation to minimize overhangs"
    )
    bl_options = {"REGISTER", "UNDO"}

    _timer = None

    @classmethod
    def poll(cls, context):
        """Enable only when a mesh object is active."""
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def invoke(self, context, event):
        """Start the modal operator with a timer.

        Implements: CON-008.
        """
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set("Tessera: Applying scaling…")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        """Process scaling in the modal loop.

        Implements: CON-008.
        """
        if event.type != "TIMER":
            return {"RUNNING_MODAL"}

        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None

        result = self._run_pipeline(context)
        context.workspace.status_text_set(None)
        return result

    def execute(self, context):
        """Fallback for scripting: run scaling synchronously."""
        return self._run_pipeline(context)

    def _run_pipeline(self, context):
        """Run the scaling pipeline and report results."""
        from ..scaling.dimension_input import DimensionSpec
        from ..scaling.exceptions import ScalingError
        from ..scaling.pipeline import ScalingOrientationPipeline
        from ..scaling.printer_profiles import PrinterProfile, get_profile_by_name

        obj = context.active_object

        # Read settings from scene properties.
        try:
            settings = context.scene.tessera.scaling

            # Build DimensionSpec from properties.
            dimension_spec = DimensionSpec(
                width_mm=settings.target_width_mm,
                height_mm=settings.target_height_mm,
                depth_mm=settings.target_depth_mm,
                auto=settings.auto_infer,
                object_class_label=settings.object_class_label,
            )

            # Resolve printer profile.
            profile_id = settings.printer_profile
            # Map EnumProperty identifier back to profile name.
            profile_name_map = {
                "GENERIC_FDM": "Generic FDM",
                "ENDER_3": "Ender 3",
                "PRUSA_MK4": "Prusa MK4",
                "BAMBU_LAB_P1S": "Bambu Lab P1S",
                "ELEGOO_MARS_3": "Elegoo Mars 3",
                "ELEGOO_SATURN_3": "Elegoo Saturn 3",
                "CUSTOM": "Custom",
            }
            profile_name = profile_name_map.get(profile_id, "Generic FDM")
            printer_profile = get_profile_by_name(profile_name)

            # FR-016: Custom profile override.
            if profile_id == "CUSTOM" and printer_profile is not None:
                printer_profile = PrinterProfile(
                    name="Custom",
                    build_width_mm=settings.custom_build_width_mm,
                    build_depth_mm=settings.custom_build_depth_mm,
                    build_height_mm=settings.custom_build_height_mm,
                    technology=settings.custom_technology,
                    default_wall_thickness_mm=(
                        1.2 if settings.custom_technology == "FDM" else 0.5
                    ),
                )

        except (AttributeError, ValueError) as exc:
            self.report({"ERROR"}, f"Invalid scaling settings: {exc}")
            logger.error("Scaling settings error: %s", exc)
            return {"CANCELLED"}

        pipeline = ScalingOrientationPipeline()

        try:
            diagnostics = pipeline.execute(
                context=context,
                obj=obj,
                dimension_spec=dimension_spec,
                printer_profile=printer_profile,
                enable_orientation=settings.enable_orientation,
                overhang_threshold_deg=settings.overhang_threshold_deg,
                enable_fine_tuning=settings.enable_fine_tuning,
            )
        except ScalingError as exc:
            self.report({"ERROR"}, f"Scaling failed: {exc.message}")
            logger.error("Scaling pipeline failed: %s", exc)
            return {"CANCELLED"}

        # Report results.
        dims = diagnostics["scaled_dimensions_mm"]
        self.report(
            {"INFO"},
            f"Scaling complete: {dims[0]:.1f} × {dims[1]:.1f} × "
            f"{dims[2]:.1f} mm "
            f"({diagnostics['pipeline_time_seconds']:.2f}s)",
        )

        if not diagnostics["build_volume_fit"]:
            violations = diagnostics["build_volume_violations"]
            self.report(
                {"WARNING"},
                f"Object exceeds build volume on {len(violations)} "
                f"axis(es). Check the diagnostics panel.",
            )

        return {"FINISHED"}


class TESSERA_OT_OptimizeOrientation(Operator):
    """Optimize print orientation for the active mesh object.

    Runs orientation optimization without scaling. Useful when
    the user wants to adjust orientation independently.

    Implements: FR-032, CON-008.
    """

    bl_idname = "tessera.optimize_orientation"
    bl_label = "Optimize Orientation"
    bl_description = (
        "Rotate the active mesh to minimize print overhang area"
    )
    bl_options = {"REGISTER", "UNDO"}

    _timer = None

    @classmethod
    def poll(cls, context):
        """Enable only when a mesh object is active."""
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def invoke(self, context, event):
        """Start the modal operator with a timer."""
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        context.workspace.status_text_set(
            "Tessera: Optimizing orientation…"
        )
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        """Process orientation in the modal loop."""
        if event.type != "TIMER":
            return {"RUNNING_MODAL"}

        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None

        result = self._run_optimizer(context)
        context.workspace.status_text_set(None)
        return result

    def execute(self, context):
        """Fallback for scripting."""
        return self._run_optimizer(context)

    def _run_optimizer(self, context):
        """Run orientation optimizer and report results."""
        from ..scaling.base_flattener import BaseFlattener
        from ..scaling.orientation import OrientationOptimizer

        obj = context.active_object

        # FR-034 / CON-004: Register undo step.
        bpy.ops.ed.undo_push(message="Tessera Orientation Optimization")

        try:
            settings = context.scene.tessera.scaling
            threshold = settings.overhang_threshold_deg
            fine_tuning = settings.enable_fine_tuning
        except AttributeError:
            threshold = 45.0
            fine_tuning = True

        optimizer = OrientationOptimizer()
        result = optimizer.optimize(
            context, obj,
            overhang_threshold_deg=threshold,
            enable_fine_tuning=fine_tuning,
        )

        # Also flatten the base.
        flattener = BaseFlattener()
        flattener.flatten(context, obj)

        if result["orientation_applied"]:
            self.report(
                {"INFO"},
                f"Orientation optimized: overhang reduced by "
                f"{result['overhang_reduction_pct']:.1f}%",
            )
        else:
            self.report(
                {"INFO"},
                "Mesh is approximately symmetrical — orientation "
                "unchanged.",
            )

        return {"FINISHED"}


class TESSERA_OT_InferDimensions(Operator):
    """Auto-infer dimensions from object class label.

    Runs the auto-inference engine and displays a confirmation
    dialog with the suggested dimensions.

    Implements: FR-032, FR-009, CON-006.
    """

    bl_idname = "tessera.infer_dimensions"
    bl_label = "Auto-Infer Dimensions"
    bl_description = (
        "Suggest target dimensions based on the object class label"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        """Enable only when a mesh object is active."""
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def execute(self, context):
        """Run auto-inference and populate dimension fields."""
        from ..scaling.auto_infer import AutoDimensionInfer

        try:
            settings = context.scene.tessera.scaling
            label = settings.object_class_label
        except AttributeError:
            self.report({"ERROR"}, "Scaling settings not available.")
            return {"CANCELLED"}

        if not label.strip():
            self.report(
                {"WARNING"},
                "Please enter an object class label first "
                "(e.g. mug, vase, figurine).",
            )
            return {"CANCELLED"}

        infer = AutoDimensionInfer()
        suggestion = infer.infer(label)

        # Populate the dimension fields with the suggestion.
        if suggestion.suggested_width_mm > 0.0:
            settings.target_width_mm = suggestion.suggested_width_mm
        if suggestion.suggested_height_mm > 0.0:
            settings.target_height_mm = suggestion.suggested_height_mm
        if suggestion.suggested_depth_mm > 0.0:
            settings.target_depth_mm = suggestion.suggested_depth_mm

        # Report the suggestion.
        conf_label = (
            "high confidence" if suggestion.confidence == "high"
            else "low confidence"
        )
        self.report(
            {"INFO"},
            f"Dimension suggestion ({conf_label}): "
            f"{suggestion.message}",
        )

        return {"FINISHED"}


# Classes to register.
classes = [
    TESSERA_OT_ApplyScaling,
    TESSERA_OT_OptimizeOrientation,
    TESSERA_OT_InferDimensions,
]
