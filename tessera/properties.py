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

"""Scene-level PropertyGroup definitions for Tessera.

Defines the image list data model, cleanup settings, validator/export
settings, refinement settings, and scene-level properties consumed via
``bpy.context.scene.tessera``.

Spec: SPEC-TS-0001, SPEC-TS-0005, SPEC-TS-0006, SPEC-TS-0008, SPEC-TS-0009.
"""

import logging

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


# FR-006: View label canonical vocabulary.
# Identifiers are UPPER_SNAKE_CASE (stored values).
# Display names are lowercase equivalents shown in the UI.
VIEW_LABEL_ITEMS = [
    ("UNLABELED", "unlabeled", "No view label assigned (default)"),
    ("FRONT", "front", "Front view of the object"),
    ("BACK", "back", "Back/rear view of the object"),
    ("LEFT", "left", "Left side view of the object"),
    ("RIGHT", "right", "Right side view of the object"),
    ("TOP", "top", "Top/overhead view of the object"),
    ("BOTTOM", "bottom", "Bottom/underside view of the object"),
    ("FRONT_LEFT", "front-left", "Front-left angled view"),
    ("FRONT_RIGHT", "front-right", "Front-right angled view"),
    ("ISOMETRIC", "isometric", "Isometric/3-quarter view"),
    ("CUSTOM", "custom", "Custom view angle (classification tag)"),
]


class TesseraImageItem(PropertyGroup):
    """A single image entry in the Tessera image list.

    Attributes:
        filepath: Absolute path to the image file on disk.
        view_label: One of the VIEW_LABEL_ITEMS identifiers.
        name: Display name (typically the file basename).
    """

    filepath: StringProperty(
        name="File Path",
        description="Absolute path to the image file",
        subtype="FILE_PATH",
        default="",
    )  # type: ignore[assignment]

    view_label: EnumProperty(
        name="View Label",
        description="Camera view direction for this image",
        items=VIEW_LABEL_ITEMS,
        default="UNLABELED",
    )  # type: ignore[assignment]

    name: StringProperty(
        name="Name",
        description="Display name (file basename)",
        default="",
    )  # type: ignore[assignment]


class TesseraCleanupSettings(PropertyGroup):
    """Cleanup pipeline settings for Tessera.

    Accessed via ``bpy.context.scene.tessera.cleanup``.

    All default values and ranges match SPEC-TS-0005 §3.4.

    Implements: FR-017.
    """

    merge_distance: FloatProperty(
        name="Merge Distance",
        description="Maximum distance for merging duplicate vertices (meters)",
        default=0.0001,
        min=0.00001,
        max=0.01,
        precision=5,
        step=0.001,
        unit="LENGTH",
    )  # type: ignore[assignment]

    voxel_size: FloatProperty(
        name="Voxel Size",
        description="Voxel size for remesh fallback (meters)",
        default=0.01,
        min=0.001,
        max=0.1,
        precision=3,
        step=0.01,
        unit="LENGTH",
    )  # type: ignore[assignment]

    auto_voxel_fallback: BoolProperty(
        name="Auto Voxel Fallback",
        description=(
            "Automatically apply voxel remesh when mesh remains "
            "non-manifold after surgical repair"
        ),
        default=True,
    )  # type: ignore[assignment]

    enable_quad_remesh: BoolProperty(
        name="Enable Quad Remesh",
        description=(
            "Convert to quad-dominant topology using QuadriFlow "
            "(Phase 2, opt-in)"
        ),
        default=False,
    )  # type: ignore[assignment]

    quad_target_faces: IntProperty(
        name="Quad Target Faces",
        description="Target face count for QuadriFlow quad remesh",
        default=10000,
        min=1000,
        max=500000,
    )  # type: ignore[assignment]

    enable_decimate: BoolProperty(
        name="Enable Decimate",
        description=(
            "Reduce polygon count while preserving sharp edges "
            "(Phase 2, opt-in)"
        ),
        default=False,
    )  # type: ignore[assignment]

    decimate_target_faces: IntProperty(
        name="Decimate Target Faces",
        description="Target face count for decimation",
        default=50000,
        min=1000,
        max=1000000,
    )  # type: ignore[assignment]

logger = logging.getLogger("tessera")

# FR-033: Printer type presets for wall thickness.
_PRINTER_THICKNESS_PRESETS = {
    "FDM": 1.2,
    "SLA": 0.5,
}


def _on_printer_type_update(self, context):
    """Callback when printer_type changes.

    Auto-updates wall_thickness_mm to the corresponding preset
    value unless the user has manually overridden it.

    Implements: FR-036.
    """
    preset = _PRINTER_THICKNESS_PRESETS.get(self.printer_type)
    if preset is not None:
        # Only update if the current value matches a known preset
        # (i.e., user hasn't manually changed it).
        current_is_preset = any(
            abs(self.wall_thickness_mm - v) < 0.001
            for v in _PRINTER_THICKNESS_PRESETS.values()
        )
        if current_is_preset or self.wall_thickness_mm == 1.2:
            self.wall_thickness_mm = preset
            logger.debug(
                "Printer type changed to %s, wall thickness set to %.1f mm",
                self.printer_type,
                preset,
            )


# FR-021: Export format items for EnumProperty with ENUM_FLAG.
_EXPORT_FORMAT_ITEMS = [
    ("STL", "STL", "Binary STL format (recommended for FDM)", 1),
    ("3MF", "3MF", "3MF format (recommended for multi-material)", 2),
    ("OBJ", "OBJ", "OBJ format (universal compatibility)", 4),
]


class TesseraValidatorSettings(PropertyGroup):
    """Validator and export pipeline settings for Tessera.

    Accessed via ``bpy.context.scene.tessera.validator``.

    Implements: FR-033.
    """

    printer_type: EnumProperty(
        name="Printer Type",
        description="Printer profile for validation thresholds",
        items=[
            ("FDM", "FDM", "Fused Deposition Modeling"),
            ("SLA", "SLA", "Stereolithography"),
        ],
        default="FDM",
        update=_on_printer_type_update,
    )  # type: ignore[assignment]

    wall_thickness_mm: FloatProperty(
        name="Wall Thickness (mm)",
        description="Minimum wall thickness threshold in millimeters",
        default=1.2,
        min=0.1,
        max=10.0,
        precision=1,
        step=10,
    )  # type: ignore[assignment]

    overhang_angle_deg: FloatProperty(
        name="Overhang Angle (°)",
        description="Maximum overhang angle from vertical in degrees",
        default=45.0,
        min=0.0,
        max=90.0,
        precision=1,
        step=100,
    )  # type: ignore[assignment]

    build_x_mm: FloatProperty(
        name="Build X (mm)",
        description="Printer build volume X dimension in millimeters",
        default=220.0,
        min=10.0,
        max=2000.0,
    )  # type: ignore[assignment]

    build_y_mm: FloatProperty(
        name="Build Y (mm)",
        description="Printer build volume Y dimension in millimeters",
        default=220.0,
        min=10.0,
        max=2000.0,
    )  # type: ignore[assignment]

    build_z_mm: FloatProperty(
        name="Build Z (mm)",
        description="Printer build volume Z dimension in millimeters",
        default=250.0,
        min=10.0,
        max=2000.0,
    )  # type: ignore[assignment]

    auto_repair: BoolProperty(
        name="Auto Repair",
        description="Automatically attempt to fix validation failures",
        default=True,
    )  # type: ignore[assignment]

    auto_scale: BoolProperty(
        name="Auto Scale",
        description="Automatically scale object to fit build volume",
        default=False,
    )  # type: ignore[assignment]

    auto_orient: BoolProperty(
        name="Auto Orient",
        description=(
            "Automatically rotate object to minimize overhangs "
            "(evaluates 576 candidate orientations)"
        ),
        default=False,
    )  # type: ignore[assignment]

    voxel_size_mm: FloatProperty(
        name="Voxel Size (mm)",
        description="Voxel size for remesh fallback in millimeters",
        default=0.5,
        min=0.1,
        max=5.0,
        precision=1,
        step=1,
    )  # type: ignore[assignment]

    export_formats: EnumProperty(
        name="Export Formats",
        description="File formats to export",
        items=_EXPORT_FORMAT_ITEMS,
        default={"STL"},
        options={"ENUM_FLAG"},
    )  # type: ignore[assignment]

    export_directory: StringProperty(
        name="Export Directory",
        description=(
            "Directory for exported files. "
            "Default: directory of the current .blend file"
        ),
        subtype="DIR_PATH",
        default="",
    )  # type: ignore[assignment]

    force_export: BoolProperty(
        name="Force Export",
        description=(
            "Export even when validation checks have failures. "
            "A confirmation dialog will be shown."
        ),
        default=False,
    )  # type: ignore[assignment]

    embed_3mf_metadata: BoolProperty(
        name="Embed 3MF Metadata",
        description=(
            "Embed Tessera print settings and validation metadata "
            "into exported 3MF files. Includes printer type, wall "
            "thickness, infill suggestion, and validation results"
        ),
        default=True,
    )  # type: ignore[assignment]


# FR-015: Printer profile EnumProperty items for SPEC-TS-0008.
_PRINTER_PROFILE_ITEMS = [
    ("GENERIC_FDM", "Generic FDM", "FDM — 220×220×250 mm"),
    ("ENDER_3", "Ender 3", "FDM — 220×220×250 mm"),
    ("PRUSA_MK4", "Prusa MK4", "FDM — 250×210×220 mm"),
    ("BAMBU_LAB_P1S", "Bambu Lab P1S", "FDM — 256×256×256 mm"),
    ("ELEGOO_MARS_3", "Elegoo Mars 3", "SLA — 143×89×175 mm"),
    ("ELEGOO_SATURN_3", "Elegoo Saturn 3", "SLA — 218×123×250 mm"),
    ("CUSTOM", "Custom", "User-defined build volume"),
]


class TesseraScalingSettings(PropertyGroup):
    """Scaling and orientation pipeline settings for Tessera.

    Accessed via ``bpy.context.scene.tessera.scaling``.

    Implements: FR-031, FR-015, FR-016.
    """

    target_width_mm: FloatProperty(
        name="Target Width (mm)",
        description="Target width in millimeters (0.0 = unset, compute proportionally)",
        default=0.0,
        min=0.0,
        max=1000000.0,
        precision=2,
    )  # type: ignore[assignment]

    target_height_mm: FloatProperty(
        name="Target Height (mm)",
        description="Target height in millimeters (0.0 = unset, compute proportionally)",
        default=0.0,
        min=0.0,
        max=1000000.0,
        precision=2,
    )  # type: ignore[assignment]

    target_depth_mm: FloatProperty(
        name="Target Depth (mm)",
        description="Target depth in millimeters (0.0 = unset, compute proportionally)",
        default=0.0,
        min=0.0,
        max=1000000.0,
        precision=2,
    )  # type: ignore[assignment]

    auto_infer: BoolProperty(
        name="Auto Infer Dimensions",
        description="Automatically infer dimensions from object class label",
        default=False,
    )  # type: ignore[assignment]

    object_class_label: StringProperty(
        name="Object Class",
        description="Object class label for auto-inference (e.g. mug, vase, figurine)",
        default="",
    )  # type: ignore[assignment]

    printer_profile: EnumProperty(
        name="Printer Profile",
        description="Printer profile for build volume validation",
        items=_PRINTER_PROFILE_ITEMS,
        default="GENERIC_FDM",
    )  # type: ignore[assignment]

    # FR-016: Custom printer profile fields.
    custom_build_width_mm: FloatProperty(
        name="Custom Build Width (mm)",
        description="Custom printer build volume width in millimeters",
        default=220.0,
        min=10.0,
        max=2000.0,
    )  # type: ignore[assignment]

    custom_build_depth_mm: FloatProperty(
        name="Custom Build Depth (mm)",
        description="Custom printer build volume depth in millimeters",
        default=220.0,
        min=10.0,
        max=2000.0,
    )  # type: ignore[assignment]

    custom_build_height_mm: FloatProperty(
        name="Custom Build Height (mm)",
        description="Custom printer build volume height in millimeters",
        default=250.0,
        min=10.0,
        max=2000.0,
    )  # type: ignore[assignment]

    custom_technology: EnumProperty(
        name="Custom Technology",
        description="Custom printer technology type",
        items=[
            ("FDM", "FDM", "Fused Deposition Modeling"),
            ("SLA", "SLA", "Stereolithography"),
        ],
        default="FDM",
    )  # type: ignore[assignment]

    overhang_threshold_deg: FloatProperty(
        name="Overhang Threshold (°)",
        description="Maximum overhang angle from vertical in degrees",
        default=45.0,
        min=20.0,
        max=70.0,
        precision=1,
    )  # type: ignore[assignment]

    enable_orientation: BoolProperty(
        name="Enable Orientation",
        description="Optimize orientation to minimize print overhangs",
        default=True,
    )  # type: ignore[assignment]

    enable_fine_tuning: BoolProperty(
        name="Enable Fine Tuning",
        description="Refine orientation with ±5°/±10° gradient search",
        default=True,
    )  # type: ignore[assignment]


class TesseraRefinementSettings(PropertyGroup):
    """Settings for the natural-language refinement loop.

    Stores transient UI state for the refinement chat panel.

    Spec: SPEC-TS-0009

    Implements: FR-001, FR-004, FR-005.
    """

    chat_input: StringProperty(
        name="Chat Input",
        description="Current text input for the refinement chat",
        default="",
    )  # type: ignore[assignment]

    is_processing: BoolProperty(
        name="Processing",
        description="Whether the LLM is currently processing a command",
        default=False,
    )  # type: ignore[assignment]

    session_active: BoolProperty(
        name="Session Active",
        description="Whether a refinement session is currently active",
        default=False,
    )  # type: ignore[assignment]

    awaiting_confirmation: BoolProperty(
        name="Awaiting Confirmation",
        description="Whether the system is waiting for user confirmation",
        default=False,
    )  # type: ignore[assignment]

    awaiting_selection: BoolProperty(
        name="Awaiting Selection",
        description="Whether the system is waiting for user vertex selection",
        default=False,
    )  # type: ignore[assignment]

    status_message: StringProperty(
        name="Status",
        description="Current status message displayed in the chat panel",
        default="",
    )  # type: ignore[assignment]


class TesseraProperties(PropertyGroup):
    """Scene-level property group for Tessera.

    Accessed via ``bpy.context.scene.tessera``.

    Attributes:
        images: Collection of TesseraImageItem entries.
        active_image_index: Index of the currently selected image in the UI list.
        cleanup: Cleanup pipeline settings (SPEC-TS-0005).
        scaling: Scaling and orientation settings (SPEC-TS-0008).
    """

    images: CollectionProperty(
        type=TesseraImageItem,
        name="Images",
        description="List of uploaded reference images",
    )  # type: ignore[assignment]

    active_image_index: IntProperty(
        name="Active Image Index",
        description="Index of the selected image in the list",
        default=0,
        min=0,
    )  # type: ignore[assignment]

    # SPEC-TS-0003, AC-006: Pipeline progress reporting.
    pipeline_status: StringProperty(
        name="Pipeline Status",
        description="Current pipeline stage and image progress",
        default="",
    )  # type: ignore[assignment]

    pipeline_progress: FloatProperty(
        name="Pipeline Progress",
        description="Overall pipeline progress (0.0 to 1.0)",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
    )  # type: ignore[assignment]

    # SPEC-TS-0005: Cleanup pipeline settings.
    cleanup: PointerProperty(
        type=TesseraCleanupSettings,
        name="Cleanup Settings",
        description="Mesh cleanup pipeline configuration",
    )  # type: ignore[assignment]

    # SPEC-TS-0006: Validator and export pipeline settings.
    validator: PointerProperty(
        type=TesseraValidatorSettings,
        name="Validator Settings",
        description="Print-readiness validator and export configuration",
    )  # type: ignore[assignment]

    # SPEC-TS-0008: Scaling and orientation pipeline settings.
    scaling: PointerProperty(
        type=TesseraScalingSettings,
        name="Scaling Settings",
        description="Real-world scaling and print orientation configuration",
    )  # type: ignore[assignment]

    # SPEC-TS-0009: Refinement loop settings.
    refinement: PointerProperty(
        type=TesseraRefinementSettings,
        name="Refinement Settings",
        description="Natural-language refinement loop configuration",
    )  # type: ignore[assignment]


# Classes to register (collected by __init__.py)
# Note: TesseraCleanupSettings, TesseraValidatorSettings, and
# TesseraScalingSettings must be registered BEFORE TesseraProperties
# because TesseraProperties references them via PointerProperty.
classes = [
    TesseraImageItem,
    TesseraCleanupSettings,
    TesseraValidatorSettings,
    TesseraScalingSettings,
    TesseraRefinementSettings,
    TesseraProperties,
]

