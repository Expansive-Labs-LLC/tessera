# Feature Specification: Real-World Scaling & Print Orientation

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0008 |
| **Task ID** | TASK-TS-0008 |
| **Status** | Draft |
| **Version** | 1.1 |
| **Created** | 2026-04-10 |
| **Last Updated** | 2026-04-14 |
| **Author** | Orchestrator (AI) |
| **Pod** | Tessera |
| **CSO Approver** | Derek |
| **Spec Type** | Feature |

### Status Transitions
| From | To | Trigger |
|------|----|---------|
| Draft | In Review | Author submits, AI-Readiness ≥80 |
| In Review | Approved | CSO approves |
| In Review | Draft | CSO requests changes |
| Approved | In Progress | Orchestrator begins implementation |
| In Progress | Complete | PR merged |

---

## 1. PROBLEM STATEMENT

### 1.1 Business Context
AI-generated 3D meshes exist in arbitrary "unit space" with no real-world dimensions — a mug might be 1 unit tall, which could mean 1 mm or 1 meter depending on interpretation. For 3D printing, exact millimeter dimensions are critical: a mug that prints at 5 mm tall or 500 mm tall is useless. Additionally, print orientation directly impacts print quality, support material usage, and success rate. An object placed with a large overhang surface on top will require excessive supports and likely fail on FDM printers.

This task bridges the gap between unitless AI output and physically correct, print-optimized geometry by providing: (1) user-specified or auto-inferred real-world dimensions, (2) printer build-volume awareness, and (3) automated orientation optimization to minimize overhangs and flatten the base to the build plate.

This feature corresponds to PRD milestones M2.3 (real-world scaling) and M2.4 (print orientation optimizer) and directly supports strategic goals G4 (configurable print constraints) and G6 (correct unit scaling).

### 1.2 User Story
**As a** user who specified my object should be 80 mm wide,  
**I want** the generated model to be exactly 80 mm wide in the exported STL with an orientation that minimizes print supports,  
**So that** it prints at the correct size on my 3D printer without wasting filament on unnecessary supports.

### 1.3 Proposed Approach
Build a `ScalingOrientationPipeline` within the Tessera add-on that accepts a cleaned mesh (from SPEC-TS-0005) and applies two sequential transformations: (1) a scaling transform that maps the mesh bounding box to user-specified or auto-inferred millimeter dimensions, with a sanity check against the selected printer's build volume; and (2) an orientation optimizer that evaluates candidate orientations (6 canonical + gradient-refined) to minimize overhang area beyond 45°, then aligns the flattest base region to Z=0. Both steps operate via `bpy` transforms and are fully undoable.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Dimensional accuracy | N/A (no scaling exists) | ±0.1 mm of user-specified dimension | Bounding-box measurement post-export vs. target |
| Build-volume violations caught | N/A | 100% of oversized models flagged before export | Automated test with meshes exceeding build volume |
| Support volume reduction vs. default orientation | N/A | ≥30% reduction on test set | Slicer analysis (PrusaSlicer CLI) on 20 test meshes comparing default vs. optimized orientation |

---

## 2. TECHNICAL CONTEXT

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/__init__.py` | Add-on scaffold (SPEC-TS-0001) | Module registration, class collection pattern |
| `tessera/mesh/cleanup.py` | Mesh cleanup pipeline (SPEC-TS-0005) | Pipeline pattern, diagnostics report structure |
| `tessera/properties.py` | Scene-level PropertyGroup | Extending scene properties with scaling/orientation settings |
| `tessera/operators/` | Existing operator stubs | Operator `bl_idname` / `bl_label` naming convention |
| Blender 3D Print Toolbox source | Official print validation add-on | Overhang detection, scale-check patterns |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`, `bmesh`, `mathutils`)
- **Math:** `mathutils.Vector`, `mathutils.Matrix`, `mathutils.Euler` for transform operations; NumPy for batch face-normal computations
- **Validation:** Runtime assertions + Blender property system
- **Testing:** `pytest` run via `blender --background --python` for headless testing
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── scaling/
│   ├── __init__.py
│   ├── pipeline.py             # ScalingOrientationPipeline: orchestrates scaling + orientation
│   ├── dimension_input.py      # DimensionSpec: user-specified or inferred dimensions
│   ├── auto_infer.py           # Object-class heuristic dimension inference
│   ├── scaler.py               # MeshScaler: bounding-box → mm transform
│   ├── printer_profiles.py     # PrinterProfile dataclass + built-in presets
│   ├── build_volume_check.py   # Build volume validation
│   ├── orientation.py          # OrientationOptimizer: minimize overhangs
│   └── base_flattener.py       # BaseFlatener: align flattest region to Z=0
├── operators/
│   ├── scaling_ops.py          # OT_ApplyScaling, OT_OptimizeOrientation, OT_AutoInferDimensions
│   └── ...
└── ui/
    ├── scaling_panel.py        # Scaling & Orientation settings sub-panel
    └── ...
```

**Pipeline pattern:** The `ScalingOrientationPipeline` follows the same chain-of-responsibility pattern as the `MeshCleanupPipeline` (SPEC-TS-0005). Each stage is an independent class with an `execute(context, obj, settings)` method. The pipeline returns a diagnostics dict summarizing what was applied.

**Cross-spec delegation with SPEC-TS-0006:** SPEC-TS-0006 (Print Validator & Export Pipeline) defines fallback orientation (FR-025), mm scale conversion (FR-026), and Z=0 bottom flattening (FR-027) inside the export pipeline. When SPEC-TS-0008 scaling/orientation has been applied to an object, the export pipeline SHALL detect this by checking the `tessera.scaling.applied` BoolProperty on the object (set to `True` by `ScalingOrientationPipeline.execute()`) and SHALL skip its own FR-025/FR-026/FR-027 logic. This avoids redundant transforms and ensures a single source of truth for scaling, orientation, and Z-alignment.

**Data flow:**
```
Cleaned bpy.types.Object (from MeshCleanupPipeline)
  → ScalingOrientationPipeline.execute()
    → DimensionSpec.resolve()          # User input or auto-inference
    → MeshScaler.apply()               # Scale bounding box to target mm
    → BuildVolumeCheck.validate()      # Verify fits in printer bed
    → OrientationOptimizer.optimize()  # Find best orientation
    → BaseFlattener.flatten()          # Align base to Z=0
  → Scaled + oriented bpy.types.Object ready for export
```

---

## 3. FUNCTIONAL REQUIREMENTS

### 3.1 Dimension Input & Scaling

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL accept user-specified target dimensions as a `DimensionSpec` containing optional `width_mm`, `height_mm`, and `depth_mm` float values, where at least one dimension is provided and the remaining dimensions are computed proportionally from the mesh's aspect ratio. |
| FR-002 | The system SHALL apply a uniform `bpy.ops.transform.resize()` when only one target dimension is specified, scaling all axes by the ratio `target_dimension / current_bounding_box_dimension` for the specified axis. Note: a single `bpy.ops.transform.resize()` call (not in a loop) is acceptable per project convention; performance-critical inner loops use `bmesh` API directly. |
| FR-003 | The system SHALL apply per-axis `bpy.ops.transform.resize()` when two or three target dimensions are specified, scaling each axis independently by `target_dimension / current_bounding_box_dimension`. Note: a single `bpy.ops.transform.resize()` call (not in a loop) is acceptable per project convention. |
| FR-004 | The system SHALL apply the scale transform to the mesh data using `bpy.ops.object.transform_apply(scale=True)` after resizing so that the object's scale property returns to `(1.0, 1.0, 1.0)` and the mesh vertices contain the final mm coordinates. |
| FR-005 | The system SHALL set the Blender scene unit system to metric with a scale of `0.001` (so 1 Blender unit = 1 mm) and set `bpy.context.scene.unit_settings.length_unit` to `'MILLIMETERS'` before applying any scaling transform. |
| FR-006 | The system SHALL verify post-scaling dimensional accuracy by measuring the object's bounding-box dimensions via `obj.dimensions` and asserting each specified target axis matches within ±0.01 mm tolerance. If the assertion fails, the system SHALL raise a `ScalingError` with message `"Post-scaling dimension mismatch: axis={axis}, expected={expected}mm, actual={actual}mm"`. |

### 3.2 Auto-Dimension Inference

| ID | Requirement |
|----|-------------|
| FR-007 | The system SHALL provide an auto-dimension inference mode activated when the user specifies `auto=True` or provides no target dimensions. |
| FR-008 | The auto-inference system SHALL use a lookup table mapping object class labels (strings) to typical real-world dimension ranges. The table SHALL include at minimum the following entries: `"mug"` → height 80–100 mm, `"vase"` → height 150–250 mm, `"figurine"` → height 50–150 mm, `"phone_case"` → height 140–160 mm, `"bottle"` → height 200–300 mm, `"bowl"` → diameter 150–200 mm, `"box"` → width 100–200 mm. |
| FR-009 | When auto-inference is used, the system SHALL return a `DimensionSuggestion` containing the inferred dimensions and a confidence level (`"high"` if object class is recognized and unambiguous, `"low"` otherwise). The system SHALL NOT apply auto-inferred dimensions without user confirmation. |
| FR-010 | The system SHALL provide a callback mechanism (`on_confirm: Callable[[DimensionSpec], None]`) that the UI layer invokes after the user confirms or modifies the suggested dimensions. |
| FR-011 | If the object class label is not present in the lookup table, the system SHALL return a `DimensionSuggestion` with `confidence="low"`, `suggested_height_mm=100.0` (generic fallback), and `message="Object class '{label}' not recognized. Please specify target dimensions manually or confirm the 100 mm height default."`. |
| FR-012 | The auto-inference lookup table SHALL be defined as a JSON file at `tessera/scaling/dimension_defaults.json` so that users can extend it without modifying Python source code. |

### 3.3 Printer Profile Presets

| ID | Requirement |
|----|-------------|
| FR-013 | The system SHALL define a `PrinterProfile` dataclass with fields: `name` (str), `build_width_mm` (float), `build_depth_mm` (float), `build_height_mm` (float), `technology` (enum: `FDM`, `SLA`), `default_wall_thickness_mm` (float). |
| FR-014 | The system SHALL ship with the following built-in printer profiles: (1) `"Generic FDM"` — 220×220×250 mm, FDM, wall 1.2 mm; (2) `"Ender 3"` — 220×220×250 mm, FDM, wall 1.2 mm; (3) `"Prusa MK4"` — 250×210×220 mm, FDM, wall 1.2 mm; (4) `"Bambu Lab P1S"` — 256×256×256 mm, FDM, wall 1.2 mm; (5) `"Elegoo Mars 3"` — 143×89×175 mm, SLA, wall 0.5 mm; (6) `"Elegoo Saturn 3"` — 218×123×250 mm, SLA, wall 0.5 mm; (7) `"Custom"` — user-defined dimensions. |
| FR-015 | The system SHALL expose the printer profile selection as an `EnumProperty` on `bpy.types.Scene.tessera.scaling.printer_profile` with `items` populated from the built-in profiles plus any user-defined custom profiles. |
| FR-016 | The system SHALL allow users to define custom printer profiles via `bpy.types.Scene.tessera.scaling.custom_build_width_mm`, `custom_build_depth_mm`, `custom_build_height_mm`, and `custom_technology` properties, which are used when `printer_profile == "Custom"`. |

### 3.4 Build Volume Validation

| ID | Requirement |
|----|-------------|
| FR-017 | The system SHALL validate that the scaled mesh's bounding box fits within the selected printer profile's build volume on all three axes. |
| FR-018 | If the mesh exceeds the build volume on any axis, the system SHALL return a `BuildVolumeViolation` containing: `axis` (str), `mesh_dimension_mm` (float), `build_limit_mm` (float), `overflow_mm` (float), and `suggested_scale_factor` (float — the uniform scale factor that would make the mesh fit). |
| FR-019 | The system SHALL NOT automatically scale down a mesh that exceeds the build volume. The system SHALL report the violation and the suggested scale factor, then wait for user confirmation before applying any corrective scaling. |
| FR-020 | If the mesh's smallest bounding-box dimension is less than 5.0 mm after scaling, the system SHALL issue a warning: `"Smallest dimension is {dim}mm — object may be too small to print reliably on {technology} printers."`. |

### 3.5 Print Orientation Optimization

| ID | Requirement |
|----|-------------|
| FR-021 | The system SHALL evaluate candidate orientations to find the orientation that minimizes the total area of faces with overhang angles exceeding a configurable threshold (default: 45°, range: 20° to 70°) relative to the build plate (negative Z direction). |
| FR-022 | The system SHALL test a minimum of 14 candidate orientations: 6 canonical rotations (each axis aligned to Z in both directions: +X, −X, +Y, −Y, +Z, −Z up) plus 8 diagonal orientations (each octant direction — combinations of ±X, ±Y, ±Z normalized). |
| FR-023 | For each candidate orientation, the system SHALL compute the overhang score as the sum of face areas (in mm²) for all faces whose angle between the face normal and the negative Z-axis (gravity direction) exceeds the overhang threshold. The computation SHALL use vectorized NumPy operations on the mesh's face normals and areas for performance. |
| FR-024 | The system SHALL apply the winning orientation by rotating the object using `obj.rotation_euler` and then applying the rotation via `bpy.ops.object.transform_apply(rotation=True)`. |
| FR-025 | The system MAY perform a gradient-descent refinement around the best candidate orientation, testing ±5° and ±10° rotations around X and Y axes (16 additional candidates: for each of {−10°, −5°, +5°, +10°} around X crossed with {−10°, −5°, +5°, +10°} around Y, producing 4 × 4 = 16 combined rotation candidates) to find a local minimum. This refinement SHALL be opt-in via `enable_fine_tuning: bool` (default: `True`). |
| FR-026 | The system SHOULD provide a `manual` orientation mode where the user specifies an explicit rotation as Euler angles `(rx, ry, rz)` in degrees, bypassing the optimizer. |

### 3.6 Bottom Flattening

| ID | Requirement |
|----|-------------|
| FR-027 | After orientation optimization, the system SHALL identify the flattest face region on the bottom of the mesh. The "bottom" is defined as faces whose center Z-coordinate is within 10% of the bounding-box height from the minimum Z value. |
| FR-028 | The system SHALL compute a "flatness score" for the bottom region as the variance of the Z-coordinates of all vertices belonging to bottom faces. A variance below `0.01 mm²` is considered "flat". |
| FR-029 | The system SHALL translate the object along the Z-axis so that the minimum Z vertex is at `Z=0.0` (the build plate), using `obj.location.z -= min_z`. |
| FR-030 | If the bottom region flatness variance exceeds `1.0 mm²`, the system SHALL log a warning: `"Bottom region is not flat (variance={var}mm²). The object may not sit stably on the build plate. Consider manual orientation."` |

### 3.7 Pipeline Control & Diagnostics

| ID | Requirement |
|----|-------------|
| FR-031 | The system SHALL expose scaling and orientation settings as a `PropertyGroup` on `bpy.types.Scene.tessera.scaling` with properties: `target_width_mm` (FloatProperty, default 0.0 = unset), `target_height_mm` (FloatProperty, default 0.0 = unset), `target_depth_mm` (FloatProperty, default 0.0 = unset), `auto_infer` (BoolProperty, default False), `object_class_label` (StringProperty), `printer_profile` (EnumProperty), `overhang_threshold_deg` (FloatProperty, default 45.0), `enable_orientation` (BoolProperty, default True), `enable_fine_tuning` (BoolProperty, default True). |
| FR-032 | The system SHALL provide Blender operators: `TESSERA_OT_apply_scaling` (applies dimension scaling), `TESSERA_OT_optimize_orientation` (runs orientation optimizer), `TESSERA_OT_infer_dimensions` (runs auto-inference and shows confirmation dialog). |
| FR-033 | The system SHALL return a diagnostics dict from the pipeline containing: `original_dimensions_mm` (tuple of 3 floats), `target_dimensions_mm` (tuple of 3 floats), `scaled_dimensions_mm` (tuple of 3 floats), `scale_factors` (tuple of 3 floats), `dimension_source` ("user" or "auto_inferred"), `printer_profile` (str), `build_volume_fit` (bool), `build_volume_violations` (list of dicts), `orientation_applied` (bool), `orientation_euler_deg` (tuple of 3 floats), `overhang_area_before_mm2` (float), `overhang_area_after_mm2` (float), `overhang_reduction_pct` (float), `bottom_flatness_variance_mm2` (float), `base_z_offset_mm` (float), `pipeline_time_seconds` (float). |
| FR-034 | The system SHALL register an undo step before executing the pipeline so that users can revert via Ctrl+Z. |
| FR-035 | The system SHALL log each pipeline stage's execution and result at `DEBUG` level using the `tessera.scaling` logger. |

---

## 4. CONSTRAINTS

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT make any network calls from any code in this task. |
| CON-002 | SHALL NOT depend on any Python package not bundled with Blender unless packaged as a `python-wheel` within the add-on `.zip`. NumPy is bundled with Blender and is permitted. |
| CON-003 | SHALL NOT modify the mesh's topology (no adding/removing vertices or faces). All operations are transform-only (position, rotation, scale) and translation. |
| CON-004 | SHALL NOT apply scaling or orientation transforms without first registering an undo step via `bpy.ops.ed.undo_push()`. |
| CON-005 | SHALL NOT alter any existing objects in the scene other than the target object. |
| CON-006 | SHALL NOT automatically apply auto-inferred dimensions or build-volume corrective scaling without explicit user confirmation. |
| CON-007 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. |
| CON-008 | SHALL NOT block Blender's UI thread for more than 100ms without yielding. Orientation optimization with 30+ candidates SHALL use a modal operator with progress reporting if total computation exceeds 100ms. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Scaling transform latency | Wall-clock time for `MeshScaler.apply()` including `transform_apply` | < 500 ms | Mesh with ≤ 500K faces on a system with 16 GB RAM and a 4-core x86_64 CPU with ≥ 3.0 GHz base clock |
| NFR-002 | Orientation optimization latency (14 candidates) | Wall-clock time for `OrientationOptimizer.optimize()` with 14 candidates | < 2 seconds | Mesh with ≤ 500K faces on a system with 16 GB RAM and a 4-core x86_64 CPU with ≥ 3.0 GHz base clock, no fine-tuning |
| NFR-003 | Orientation optimization latency (30 candidates, with fine-tuning) | Wall-clock time for optimize with fine-tuning enabled | < 5 seconds | Mesh with ≤ 500K faces on a system with 16 GB RAM and a 4-core x86_64 CPU with ≥ 3.0 GHz base clock |
| NFR-004 | Dimensional accuracy | Absolute deviation between target dimension and post-scaling bounding box | ≤ 0.01 mm per axis | Any mesh, any single target dimension |
| NFR-005 | Build volume check latency | Wall-clock time for `BuildVolumeCheck.validate()` | < 10 ms | Any mesh (bounding-box comparison only) |
| NFR-006 | Peak memory overhead | Additional Python memory above mesh data for orientation scoring | < 50 MB | 500K face mesh (storing 30 face-normal dot-product arrays) |
| NFR-007 | Auto-inference lookup latency | Wall-clock time for JSON file parse + label lookup | < 50 ms | Default `dimension_defaults.json` with ≤ 100 entries |

---

## 6. ACCEPTANCE CRITERIA

### AC-001: Single-Axis Uniform Scaling
**Given** a cleaned mesh with bounding-box dimensions (1.0, 1.5, 0.8) in Blender units and the Blender scene set to metric/mm,  
**When** `ScalingOrientationPipeline.execute()` is called with `target_width_mm=80.0` and no other target dimensions,  
**Then** the object's `obj.dimensions` returns `(80.0, 120.0, 64.0)` ±0.01 mm (preserving the original 1.0:1.5:0.8 aspect ratio), the object's scale is `(1.0, 1.0, 1.0)`, and `diagnostics["dimension_source"]` is `"user"`.

### AC-002: Multi-Axis Non-Uniform Scaling
**Given** a cleaned mesh with bounding-box dimensions (1.0, 1.0, 1.0) in Blender units,  
**When** `ScalingOrientationPipeline.execute()` is called with `target_width_mm=80.0`, `target_height_mm=120.0`, and `target_depth_mm=60.0`,  
**Then** the object's `obj.dimensions` returns `(80.0, 120.0, 60.0)` ±0.01 mm and `diagnostics["scale_factors"]` is `(80.0, 120.0, 60.0)`.

### AC-003: Build Volume Violation Detection
**Given** a mesh scaled to dimensions (300.0, 200.0, 150.0) mm and a printer profile `"Ender 3"` with build volume 220×220×250 mm,  
**When** `BuildVolumeCheck.validate()` is called,  
**Then** the result contains a `BuildVolumeViolation` for the X-axis with `mesh_dimension_mm=300.0`, `build_limit_mm=220.0`, `overflow_mm=80.0`, and `suggested_scale_factor` ≈ 0.733 (220/300), and `diagnostics["build_volume_fit"]` is `False`.

### AC-004: Orientation Optimizer Reduces Overhangs
**Given** a canonical test mesh: an inverted cone with 30° half-angle, base diameter 100 mm, 10,000 faces, oriented base-up (maximum overhang — 60% of face area exceeding 45° overhang in its initial orientation),  
**When** `OrientationOptimizer.optimize()` is called with `overhang_threshold_deg=45.0`,  
**Then** the returned orientation reduces the overhang area by ≥30% compared to the initial orientation, and `diagnostics["overhang_reduction_pct"]` is ≥ 30.0.

### AC-005: Base Flattening to Build Plate
**Given** a mesh that has been orientation-optimized and its lowest vertex is at Z = −15.3 mm,  
**When** `BaseFlattener.flatten()` is called,  
**Then** the object's minimum vertex Z-coordinate is 0.0 mm (±0.001 mm), and `diagnostics["base_z_offset_mm"]` is `15.3`.

### AC-006: Auto-Dimension Inference with Confirmation
**Given** an object class label of `"mug"` and no user-specified target dimensions,  
**When** `AutoDimensionInfer.infer(object_class="mug")` is called,  
**Then** the system returns a `DimensionSuggestion` with `suggested_height_mm` between 80 and 100 (inclusive), `confidence="high"`, and `requires_confirmation=True`. The system SHALL NOT apply any scaling until the user confirms.

### AC-007: Undo Support
**Given** a mesh object that has been scaled and orientation-optimized by the pipeline,  
**When** the user presses Ctrl+Z,  
**Then** the mesh reverts to its pre-pipeline state including position, rotation, scale, and vertex positions.

---

## 7. EDGE CASES

### EC-001: Symmetrical Object with No Preferred Orientation (Sphere)
| Aspect | Detail |
|--------|--------|
| **Scenario** | The mesh is a near-perfect sphere with no flat faces and uniform overhang in all orientations. There is no "front", "bottom", or preferred base. |
| **Input Example** | A UV sphere with 10,000 faces, all face normals pointing radially outward from the center. |
| **Expected Behavior** | The system SHALL detect that the overhang score variance across all 14 candidate orientations is < 1% of the mean score and log a message: `"Mesh is approximately symmetrical — orientation optimization has minimal effect. Using default orientation (current)."` The system SHALL keep the current orientation and set `diagnostics["orientation_applied"]` to `False`. |
| **Test ID** | TS-004 |

### EC-002: Mesh Exceeds Build Volume on All Three Axes
| Aspect | Detail |
|--------|--------|
| **Scenario** | The user specifies target dimensions of 400×400×400 mm but selects a printer profile with a build volume of 220×220×250 mm. The mesh overflows on all axes. |
| **Input Example** | `target_width_mm=400, target_height_mm=400, target_depth_mm=400`, printer profile `"Ender 3"`. |
| **Expected Behavior** | The system SHALL return `BuildVolumeViolation` entries for all three axes with individual overflow values. The `suggested_scale_factor` SHALL be the minimum of all single-axis scale factors (i.e., `min(220/400, 220/400, 250/400)` = 0.55) so that all axes fit if applied uniformly. The system SHALL NOT auto-apply the scale factor. |
| **Test ID** | TS-005 |

### EC-003: Zero-Volume Flat Mesh (Plane)
| Aspect | Detail |
|--------|--------|
| **Scenario** | The mesh is a planar object with zero height along one axis (e.g., a flat disc or a decal). |
| **Input Example** | Mesh with bounding box `(100mm, 100mm, 0.0mm)` — all vertices coplanar on the XY plane. |
| **Expected Behavior** | The system SHALL detect that one bounding-box dimension is 0.0 and raise a `ScalingError` with message `"Mesh has zero extent along the {axis} axis. Cannot compute scale factor for a zero-dimension axis. The mesh may be a flat plane, which is not printable."` The system SHALL NOT attempt to divide by zero. |
| **Test ID** | TS-006 |

### EC-004: User Specifies Contradictory Dimensions (Aspect Ratio Violation)
| Aspect | Detail |
|--------|--------|
| **Scenario** | The user specifies all three dimensions but the requested aspect ratio differs significantly from the mesh's natural aspect ratio, resulting in extreme stretching (e.g., a mug stretched to be 10× wider than tall). |
| **Input Example** | A mug mesh with natural aspect ratio 1:1.2:1 and user requests `width=200mm, height=20mm, depth=200mm`. |
| **Expected Behavior** | The system SHALL compute the per-axis scale factors and, if the ratio between the largest and smallest scale factor exceeds 5.0, log a warning: `"Non-uniform scaling is extreme (max/min scale ratio = {ratio:.1f}). The object will be significantly distorted from its original proportions."` The system SHALL proceed with the scaling (user intent is explicit) but SHALL include the warning in the diagnostics under `diagnostics["warnings"]`. |
| **Test ID** | TS-007 |

### EC-005: Very Small Object at Printer Resolution Limit
| Aspect | Detail |
|--------|--------|
| **Scenario** | The user specifies a target height of 2 mm for an object — below the practical print resolution of most FDM printers (layer height 0.1–0.3 mm means only ~7–20 layers). |
| **Input Example** | `target_height_mm=2.0`, printer profile `"Ender 3"` (FDM). |
| **Expected Behavior** | The system SHALL issue a warning: `"Target height (2.0mm) is very small for FDM printing. At a typical 0.2mm layer height, the object would be only 10 layers tall. Consider SLA printing for small objects."` The system SHALL proceed with scaling (user intent is explicit). |
| **Test ID** | TS-008 |

### EC-006: User Specifies Negative Target Dimension
| Aspect | Detail |
|--------|--------|
| **Scenario** | The user specifies a negative value for one or more target dimensions (e.g., `target_width_mm=-50.0`). |
| **Input Example** | `target_width_mm=-50.0`, `target_height_mm=100.0`. |
| **Expected Behavior** | The system SHALL reject the input and raise a `ValueError` with message `"Target dimension must be positive: width=-50.0mm"`. No scaling transform SHALL be applied. This is enforced by SEC-001 validation, which rejects NaN, Inf, negative values, and values exceeding 1e6 mm. |
| **Test ID** | TS-024 |

### EC-007: No Target Dimensions Specified with Auto-Inference Disabled
| Aspect | Detail |
|--------|--------|
| **Scenario** | The user runs the scaling pipeline with all three target dimensions at their default (0.0 = unset) and `auto_infer=False`. No dimensions are specified and the system cannot auto-infer. |
| **Input Example** | `target_width_mm=0.0`, `target_height_mm=0.0`, `target_depth_mm=0.0`, `auto_infer=False`. |
| **Expected Behavior** | The system SHALL raise a `ValueError` with message `"At least one target dimension must be specified when auto_infer is disabled. Set target_width_mm, target_height_mm, or target_depth_mm to a positive value, or enable auto_infer."` No scaling transform SHALL be applied. |
| **Test ID** | TS-025 |

---

## 8. OUT OF SCOPE

The following are explicitly **excluded** from this feature:

- ❌ Mesh topology modification (adding/removing vertices, faces, or edges — SPEC-TS-0005)
- ❌ Print-readiness validation (manifold checks, wall thickness, self-intersections — TASK-TS-0006)
- ❌ STL/3MF/OBJ file export (TASK-TS-0006)
- ❌ AI-based object class detection from the mesh or image (requires vision pipeline — TASK-TS-0003). Object class labels are provided by the user or upstream pipeline.
- ❌ Support structure generation (slicer responsibility)
- ❌ Slicer integration (PrusaSlicer, Cura) — deferred per PRD NG2
- ❌ Multi-part object scaling (each object scaled independently — v1 is single-object only per PRD D4)
- ❌ Texture or UV coordinate transformation during scaling
- ❌ Finite element analysis or structural strength simulation
- ❌ Automatic mesh splitting for objects that exceed build volume
- ⚠️ **Cross-spec note:** SPEC-TS-0006 §3.3 (FR-025/FR-026/FR-027) provides fallback orientation/scale/Z-flatten logic inside the export pipeline. When SPEC-TS-0008 has been applied upstream, the export pipeline SHALL skip those steps by checking the `tessera.scaling.applied` BoolProperty on the object. This spec is the authoritative source for scaling, orientation, and Z-alignment.

---

## 9. SECURITY CONSIDERATIONS

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — local Blender add-on, no network interaction |
| **Auth Method** | None |
| **Required Permissions** | File system read for `dimension_defaults.json` (bundled with add-on) |
| **Rate Limiting** | N/A |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| Target dimensions (mm values) | Internal | In-memory only; stored in Blender scene properties |
| Printer profile data | Internal | Bundled JSON; user customizations in `.blend` file |
| Auto-inference lookup table | Internal | Read-only JSON bundled with add-on |
| Diagnostics output | Internal | Displayed in UI; not transmitted anywhere |
| Object class labels | Internal | User-supplied string; stored in scene properties |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL validate all numerical inputs (dimensions, angles, scale factors) to reject NaN, Inf, negative values, and values exceeding `1e6` mm. Invalid values SHALL raise a `ValueError` with a descriptive message. |
| SEC-002 | SHALL sanitize the `object_class_label` string to contain only alphanumeric characters, hyphens, underscores, and spaces. Characters not matching `[a-zA-Z0-9_\- ]` SHALL be stripped before lookup. |
| SEC-003 | SHALL validate the `dimension_defaults.json` file structure on load. If the JSON is malformed or contains unexpected types, the system SHALL log an `ERROR` and fall back to hardcoded defaults without crashing. |
| SEC-004 | SHALL NOT make any network connections, DNS lookups, or socket operations. |
| SEC-005 | SHALL NOT execute any code from user-specified paths or dynamically load modules based on input data. |

---

## 10. API CONTRACT [CONDITIONAL]

> **No REST/HTTP APIs.** This section documents the internal Python API contract for downstream tasks.

### 10.1 DimensionSpec API
```python
from tessera.scaling.dimension_input import DimensionSpec

# User-specified dimensions
spec = DimensionSpec(
    width_mm=80.0,       # Optional — 0.0 means "unset, compute proportionally"
    height_mm=0.0,       # Optional
    depth_mm=0.0,        # Optional
    auto=False           # If True, triggers auto-inference
)

# Auto-inference mode
spec = DimensionSpec(auto=True, object_class_label="mug")
```

### 10.2 PrinterProfile API
```python
from tessera.scaling.printer_profiles import PrinterProfile, get_builtin_profiles

# List built-in profiles
profiles = get_builtin_profiles()  # Returns: list[PrinterProfile]

# Access specific profile
profile = PrinterProfile(
    name="Ender 3",
    build_width_mm=220.0,
    build_depth_mm=220.0,
    build_height_mm=250.0,
    technology="FDM",
    default_wall_thickness_mm=1.2
)
```

### 10.3 ScalingOrientationPipeline API
```python
from tessera.scaling.pipeline import ScalingOrientationPipeline
from tessera.scaling.dimension_input import DimensionSpec
from tessera.scaling.printer_profiles import get_profile_by_name

pipeline = ScalingOrientationPipeline()
diagnostics = pipeline.execute(
    context=bpy.context,
    obj=obj,                                     # bpy.types.Object with mesh data
    dimension_spec=DimensionSpec(width_mm=80.0),  # Required
    printer_profile=get_profile_by_name("Ender 3"),  # Optional, default "Generic FDM"
    enable_orientation=True,                      # Optional
    overhang_threshold_deg=45.0,                  # Optional
    enable_fine_tuning=True,                      # Optional
)
# Returns: dict — pipeline diagnostics (see FR-033)
```

### 10.4 Integration with Mesh Cleanup (SPEC-TS-0005) and Print Validator (TASK-TS-0006)
```python
# Expected end-to-end calling pattern

# Step 1: Import and clean (SPEC-TS-0005)
from tessera.mesh.importer import MeshImporter
from tessera.mesh.cleanup import MeshCleanupPipeline

importer = MeshImporter()
obj = importer.import_mesh(vertices=raw.vertices, faces=raw.faces, source_model="trellis")
cleanup_diag = MeshCleanupPipeline().execute(bpy.context, obj)

# Step 2: Scale and orient (this spec — SPEC-TS-0008)
from tessera.scaling.pipeline import ScalingOrientationPipeline
from tessera.scaling.dimension_input import DimensionSpec

scaling_diag = ScalingOrientationPipeline().execute(
    context=bpy.context,
    obj=obj,
    dimension_spec=DimensionSpec(width_mm=80.0),
)

# Step 3: Validate and export (TASK-TS-0006)
# validator = PrintValidator().validate(bpy.context, obj)
# exporter = MeshExporter().export(obj, format="stl")
```

---

## 11. OBSERVABILITY

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------|
| Input validation: negative dimension rejected | ERROR | `axis`, `value`, `error_message` | ⚠️ No PII |
| Input validation: no dimensions specified | ERROR | `auto_infer`, `error_message` | ⚠️ No PII |
| Scaling pipeline started | INFO | `target_dimensions`, `printer_profile`, `object_name` | ⚠️ No PII |
| Scene units configured | DEBUG | `unit_system`, `unit_scale`, `length_unit` | ⚠️ No PII |
| Scaling transform applied | INFO | `original_dimensions`, `target_dimensions`, `scale_factors`, `time_seconds` | ⚠️ No PII |
| Dimension accuracy verified | DEBUG | `axis`, `expected_mm`, `actual_mm`, `deviation_mm` | ⚠️ No PII |
| Auto-inference executed | INFO | `object_class`, `suggested_dimensions`, `confidence` | ⚠️ No PII |
| Build volume check passed | INFO | `mesh_dimensions`, `build_volume`, `printer_name` | ⚠️ No PII |
| Build volume violation | WARN | `axis`, `mesh_dim_mm`, `build_limit_mm`, `overflow_mm` | ⚠️ No PII |
| Small object warning | WARN | `smallest_dimension_mm`, `technology` | ⚠️ No PII |
| Orientation optimization started | INFO | `candidate_count`, `overhang_threshold_deg` | ⚠️ No PII |
| Candidate orientation scored | DEBUG | `candidate_index`, `euler_deg`, `overhang_area_mm2` | ⚠️ No PII |
| Best orientation selected | INFO | `euler_deg`, `overhang_area_before`, `overhang_area_after`, `reduction_pct` | ⚠️ No PII |
| Symmetrical mesh detected | INFO | `score_variance_pct`, `message` | ⚠️ No PII |
| Base flattened to build plate | INFO | `z_offset_mm`, `flatness_variance_mm2` | ⚠️ No PII |
| Non-flat bottom warning | WARN | `flatness_variance_mm2` | ⚠️ No PII |
| Pipeline completed | INFO | Full diagnostics dict | ⚠️ No PII |
| Input validation failed | ERROR | `error_message`, `invalid_values` | ⚠️ No PII |

> All logging uses Python's `logging` module with logger name `"tessera.scaling"`. Blender routes this to the system console.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only).

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — functionality available when add-on is installed |
| **Default State** | Scaling enabled by default; orientation optimization enabled by default; auto-inference disabled by default |
| **Rollout Plan** | Bundled with add-on `.zip`; all settings exposed in UI panel |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| SPEC-TS-0001 (Add-on Scaffold) | Yes | Provides module registration, UI panel framework, scene properties |
| SPEC-TS-0005 (Mesh Import & Cleanup) | Yes | Produces the cleaned mesh object that this task consumes |
| Blender 4.2+ | Yes | Requires stable `bpy` API for transform operations |
| NumPy (bundled with Blender) | Yes | Used for vectorized face-normal computation in orientation optimizer |

### 12.3 Rollback Plan
1. User disables the add-on or reverts to a previous add-on version
2. Existing `.blend` files are unaffected — scaled/oriented mesh objects remain in the scene after add-on removal
3. Users can Ctrl+Z to undo scaling/orientation if the pipeline was just executed
4. Verify no orphan data via Blender's Outliner → Orphan Data view

---

## 13. TEST SCENARIOS

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Single-axis uniform scaling, verify proportional dimensions | Unit | AC-001 | Must Pass |
| TS-002 | Multi-axis non-uniform scaling, verify exact dimensions | Unit | AC-002 | Must Pass |
| TS-003 | Build volume violation detection on oversized mesh | Unit | AC-003 | Must Pass |
| TS-004 | Symmetrical sphere has no preferred orientation | Unit | EC-001 | Must Pass |
| TS-005 | Mesh exceeding build volume on all 3 axes | Unit | EC-002 | Must Pass |
| TS-006 | Zero-extent flat mesh raises ScalingError | Unit | EC-003 | Must Pass |
| TS-007 | Extreme aspect ratio distortion warning | Unit | EC-004 | Must Pass |
| TS-008 | Very small object at resolution limit warning | Unit | EC-005 | Must Pass |
| TS-009 | Orientation optimizer reduces overhangs on inverted cone | Integration | AC-004 | Must Pass |
| TS-010 | Base flattening places lowest vertex at Z=0 | Unit | AC-005 | Must Pass |
| TS-011 | Auto-inference returns "mug" dimensions with confirmation required | Unit | AC-006 | Must Pass |
| TS-012 | Ctrl+Z after pipeline reverts all transforms | Integration | AC-007 | Must Pass |
| TS-013 | Diagnostics dict contains all required keys with correct types | Unit | FR-033 | Must Pass |
| TS-014 | Scaling latency < 500ms on 500K face mesh | Performance | NFR-001 | Must Pass |
| TS-015 | Orientation latency < 2s with 14 candidates on 500K face mesh | Performance | NFR-002 | Must Pass |
| TS-016 | Orientation latency < 5s with fine-tuning on 500K face mesh | Performance | NFR-003 | Must Pass |
| TS-017 | Post-scaling dimension accuracy ≤ 0.01mm | Unit | NFR-004 | Must Pass |
| TS-018 | Input validation rejects NaN/Inf/negative dimensions | Unit | SEC-001 | Must Pass |
| TS-019 | Malformed JSON defaults file falls back to hardcoded | Unit | SEC-003 | Must Pass |
| TS-020 | PropertyGroup registration and defaults | Unit | FR-031 | Must Pass |
| TS-021 | Scene unit system set to metric/mm before scaling | Unit | FR-005 | Must Pass |
| TS-022 | Printer profile EnumProperty populated with all built-in profiles | Unit | FR-015 | Must Pass |
| TS-023 | Unknown object class label returns low-confidence fallback | Unit | FR-011 | Must Pass |
| TS-024 | Negative target dimension raises ValueError | Unit | EC-006 | Must Pass |
| TS-025 | All dimensions 0.0 with auto_infer=False raises ValueError | Unit | EC-007 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0001 (Add-on Scaffold) | Required | Draft | Tessera | Yes — need module registration framework |
| SPEC-TS-0005 (Mesh Import & Cleanup) | Required | Draft | Tessera | Yes — need cleaned mesh output |
| TASK-TS-0006 (Print Validator) | Co-dependent | Pending | Tessera | No — build volume check in this spec replaces scale-sanity check in TASK-TS-0006 |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| Blender 4.2+ LTS | Required | [docs.blender.org](https://docs.blender.org/api/current/) | No fallback — hard requirement |
| Blender `mathutils` module | Required | [mathutils API](https://docs.blender.org/api/current/mathutils.html) | N/A — bundled with Blender |
| NumPy (Blender-bundled) | Required | [numpy.org](https://numpy.org/doc/) | N/A — bundled with Blender 4.x |

---

## 15. APPROVAL

| Role | Name | Date | Status |
|------|------|------|--------|
| Author (Orchestrator) | AI | 2026-04-10 | ☐ Submitted |
| CSO Approval | Derek | | ☐ Approved / ☐ Changes Requested |
| Deputy Review | | | ☐ N/A |

**Approval Notes:**
[Space for CSO/Deputy feedback]

---

## AI-READINESS SELF-SCORE

| Criterion | Max | Score | Guidance |
|-----------|-----|-------|----------|
| SHALL/SHOULD/MAY requirements | 20 | 20 | 35 requirements with precise SHALL/SHOULD/MAY language across 7 functional sections |
| Quantified NFRs | 15 | 15 | 7 NFRs, all quantified with specific targets, units, measurement conditions, and CPU floor |
| Given-When-Then criteria (3+) | 20 | 20 | 7 acceptance criteria in Given-When-Then format with specific numerical values and canonical test mesh |
| Edge cases (2+) | 15 | 15 | 7 edge cases with concrete input examples and expected behaviors (including negative dims, no-dims) |
| Out of scope defined | 10 | 10 | 10 explicit exclusions + cross-spec delegation note for SPEC-TS-0006 |
| Security constraints | 10 | 10 | 5 security requirements + data classification table |
| No ambiguous language | 10 | 10 | All ambiguous terms replaced with specifics. FR-025 candidate count arithmetic clarified. |
| **TOTAL** | **100** | **100** | **Target: ≥80 ✅** |

### Score Decision
| Score | Action |
|-------|--------|
| ≥80 | Submit for CSO review ✅ |

### Ambiguous Language Checklist
> Verify **NONE** of these words appear without specific definitions:

- [x] "appropriate" → not used
- [x] "properly" → not used
- [x] "correctly" → not used
- [x] "as expected" → not used
- [x] "handle gracefully" → replaced with specific error responses
- [x] "fast" / "efficient" / "performant" → replaced with ms/second targets
- [x] "secure" → replaced with SEC-001 through SEC-005
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → replaced with specific performance targets

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-10 | Orchestrator (AI) | Initial draft |
| 1.1 | 2026-04-14 | Spec Review | Added cross-spec delegation contract with SPEC-TS-0006 (FR-025/026/027 handoff via `tessera.scaling.applied` BoolProperty). Added EC-006 (negative dimensions) and EC-007 (no dimensions with auto=False). Clarified FR-025 fine-tuning candidate count arithmetic (4×4=16). Added CPU floor to NFR-001/002/003 measurement conditions. Specified canonical test cone in AC-004. Fixed logging table markdown formatting. Added bpy.ops single-call note to FR-002/003. Added TS-024/TS-025. Recalibrated self-score to 100. |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0008-scaling-orientation.md`
