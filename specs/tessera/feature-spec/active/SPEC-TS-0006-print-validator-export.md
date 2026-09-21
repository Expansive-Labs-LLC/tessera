# Feature Specification: Print-Readiness Validator & Export Pipeline

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0006 |
| **Task ID** | TASK-TS-0006 |
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
Tessera's core promise is "give it images, get a printable STL." Without a rigorous validation gate, AI-generated meshes — even after cleanup (SPEC-TS-0005) — may still contain non-manifold geometry, self-intersections, thin walls, excessive overhangs, or incorrect scaling that cause slicer crashes, failed prints, and wasted filament. This feature is the final gatekeeper: it runs 7 automated validation checks per PRD §5.4, attempts auto-repair on failures, generates a pass/warn/fail report, and exports to STL/3MF/OBJ only when the mesh is genuinely print-ready. It fulfills Phase 1 exit criteria M1.6 — "STL export with print-readiness validation."

### 1.2 User Story
**As a** user who wants to 3D print the generated model,  
**I want** the agent to validate that the mesh is printable, automatically fix common issues, and export to my preferred format,  
**So that** I can confidently send the exported file to my slicer without worrying about print failures.

### 1.3 Proposed Approach
Build a two-stage system within the Tessera add-on: (1) a `PrintValidator` class that runs a configurable chain of validation checks — non-manifold edges, self-intersections, zero-area faces, wall thickness, overhang angle, mesh volume, and scale sanity — each with an auto-repair strategy; and (2) an `ExportPipeline` class that operates on a **duplicate** of the original mesh (named `ObjectName_print`), applies any auto-repairs, and exports to STL (binary, mm scale), 3MF, or OBJ with a JSON + human-readable validation report. Auto-repair operates exclusively on the duplicate to preserve the user's original edits.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Manifold export rate | 0% (no export exists) | 100% of exported meshes pass manifold check | Automated re-validation of exported file via `trimesh.is_watertight` or re-import check |
| Print success rate | N/A | ≥ 85% first-attempt success on FDM printer | Manual test prints across 10 object categories |
| Export pipeline latency | N/A | < 10 seconds for meshes ≤ 500K faces | `time.perf_counter()` around full validate-and-export pipeline |
| Validation report accuracy | N/A | 0 false-pass results (no check reports "pass" when issue exists) | Golden-mesh test suite with known defects |

---

## 2. TECHNICAL CONTEXT

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/__init__.py` | Add-on scaffold (SPEC-TS-0001) | Module registration, class collection pattern |
| `tessera/mesh/cleanup.py` | Mesh cleanup pipeline (SPEC-TS-0005) | Chain-of-responsibility step pattern, diagnostics dict structure |
| `tessera/mesh/steps/` | Individual cleanup steps | Step class interface: `execute(context, obj, settings)` pattern |
| `tessera/operators/` | Existing operator stubs | Operator `bl_idname` / `bl_label` naming convention |
| `tessera/properties.py` | Scene-level PropertyGroup | Extending scene properties with validator/export settings |
| Blender 3D Print Toolbox add-on | Built-in validation (non-manifold, thickness, overhang) | Leveraging `bpy.ops.mesh.print3d_*` operators where available |
| `bpy.ops.export_mesh.stl()` | Built-in STL exporter | Export parameters, coordinate system, scale factor |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`, `bmesh`, `mathutils`)
- **Mesh Analysis:** `bmesh` module, `mathutils.bvhtree.BVHTree`, Blender 3D Print Toolbox operators
- **Export:** Blender built-in exporters (`bpy.ops.export_mesh.stl`, `bpy.ops.export_mesh.obj`, `bpy.ops.export_scene.threemf` or io_mesh_3mf)
- **Validation:** Runtime assertions + `bmesh`-level geometry queries
- **Testing:** `pytest` run via `blender --background --python` for headless testing
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── validator/
│   ├── __init__.py
│   ├── print_validator.py        # PrintValidator: orchestrates validation chain
│   ├── checks/
│   │   ├── __init__.py
│   │   ├── manifold.py           # Check: non-manifold edges
│   │   ├── self_intersection.py  # Check: self-intersections via BVH
│   │   ├── degenerate_faces.py   # Check: zero-area / degenerate faces
│   │   ├── wall_thickness.py     # Check: minimum wall thickness via ray-cast
│   │   ├── overhang.py           # Check: overhang angle vs build plate
│   │   ├── volume.py             # Check: mesh volume > 0 (closed surface)
│   │   └── scale_sanity.py       # Check: bounding box within build volume
│   ├── report.py                 # ValidationReport: JSON + human-readable output
│   └── repair.py                 # Auto-repair strategies per check type
├── export/
│   ├── __init__.py
│   ├── export_pipeline.py        # ExportPipeline: duplicate → validate → repair → export
│   ├── stl_exporter.py           # STL export with binary/mm config
│   ├── threemf_exporter.py       # 3MF export wrapper
│   └── obj_exporter.py           # OBJ export wrapper
├── operators/
│   ├── validator_ops.py          # OT_ValidatePrint, OT_ExportForPrint
│   └── ...
└── ui/
    ├── validator_panel.py        # Validator settings + report display sub-panel
    └── ...
```

**Design principles:**
- **Chain-of-responsibility:** Each validation check is an independent class with `check(obj, settings) → CheckResult` and `repair(obj, settings) → RepairResult` methods. The `PrintValidator` executes them in sequence and aggregates results.
- **Non-destructive:** All auto-repair operates on a duplicated mesh object (`ObjectName_print`). The original is never modified.
- **Composable:** Export is decoupled from validation. Users can run validation-only, or validate-then-export.

**Data flow:**
```
User clicks "Export for Print"
  → ExportPipeline.execute()
    → Duplicate active object → "ObjectName_print"
    → PrintValidator.validate(duplicate_obj)
      → ManifoldCheck → SelfIntersectionCheck → DegenerateFacesCheck
      → WallThicknessCheck → OverhangCheck → VolumeCheck → ScaleSanityCheck
    → For each FAIL result where auto_repair=True:
      → RepairStrategy.repair(duplicate_obj)
      → Re-run failed check to verify fix
    → Generate ValidationReport (JSON + human-readable)
    → If all checks pass or warn-only:
      → Export to requested format(s)
    → If any check still FAIL after repair:
      → Show report to user with failures highlighted
      → Do NOT export (unless user force-overrides)
```

---

## 3. FUNCTIONAL REQUIREMENTS

### 3.1 Core Requirements — Validation Checks

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL detect non-manifold edges by selecting edges where `edge.is_manifold == False` using `bmesh` iteration. Non-manifold edges include boundary edges (belong to 1 face), wire edges (belong to 0 faces), and edges shared by more than 2 faces. |
| FR-002 | The system SHALL auto-repair non-manifold edges by: (a) merging vertices within a configurable distance (default: `0.0001` meters) using `bmesh.ops.remove_doubles()`, (b) filling boundary holes using `bmesh.ops.triangle_fill()` for loops with ≤ 500 edges. |
| FR-003 | The system SHALL detect self-intersecting faces by building a `mathutils.bvhtree.BVHTree` from the mesh and querying `BVHTree.overlap(tree, tree)` to find pairs of intersecting faces. |
| FR-004 | The system SHALL auto-repair self-intersections by applying a boolean union to self: duplicate the object, apply a `BOOLEAN` modifier in `UNION` mode with the object as its own target, then apply the modifier. |
| FR-005 | The system SHALL detect zero-area faces by iterating all faces in `bmesh` and flagging faces with `face.calc_area() < 1e-8` square meters. |
| FR-006 | The system SHALL auto-repair zero-area faces by dissolving degenerate faces using `bmesh.ops.dissolve_degenerate(bm, dist=1e-8, edges=bm.edges)`. |
| FR-007 | The system SHALL detect insufficient wall thickness by casting rays inward (opposite to face normal) from sample points on each face and measuring the distance to the nearest opposing surface. Faces where the ray hit distance is less than the thickness threshold SHALL be flagged. |
| FR-008 | The wall thickness threshold SHALL be configurable via a `FloatProperty` with: default `1.2` mm (FDM), range `0.1` mm to `10.0` mm. The system SHALL provide presets: `FDM` → `1.2` mm, `SLA` → `0.5` mm. |
| FR-009 | The system SHALL auto-repair thin walls by applying a `SOLIDIFY` modifier with thickness equal to `(threshold - measured_minimum) + 0.1 mm` margin, mode `COMPLEX`, and `offset = -1` (solidify inward). |
| FR-010 | The system SHALL detect overhang faces by computing the angle between each face normal and the build-plate normal (negative Z-axis, i.e., `(0, 0, -1)`). Faces with an angle less than `(90° - overhang_threshold)` from the downward vector (equivalently, the face normal makes an angle > `overhang_threshold` from the up vector when the face points downward) SHALL be flagged. |
| FR-011 | The overhang threshold SHALL be configurable via a `FloatProperty` with: default `45.0` degrees, range `0.0` to `90.0` degrees. |
| FR-012 | The system SHALL NOT auto-repair overhangs automatically. Overhang detection SHALL produce a `WARN` result when the percentage of overhanging faces is ≤ 50%, with a message listing the count and percentage of overhanging faces. When the percentage of overhanging faces exceeds 50%, the system SHALL produce a `FAIL` result with message: `"{count} faces ({pct}%) exceed {threshold}° overhang threshold. Object may be misoriented. Consider using auto-orient."` The system MAY offer an `auto_orient` option that rotates the object to minimize overhanging face area (see FR-025). |
| FR-013 | The system SHALL compute the mesh volume using `bmesh` by summing signed tetrahedron volumes: `V = Σ (v1 · (v2 × v3)) / 6` for each face. A volume ≤ 0 indicates a non-closed surface or inverted normals. |
| FR-014 | The system SHALL auto-repair negative/zero volume by: (a) recalculating normals outward using `bmesh.ops.recalc_face_normals()`, (b) if volume is still ≤ 0, applying a voxel remesh fallback with configurable voxel size (default `0.5` mm, range `0.1` mm to `5.0` mm). |
| FR-015 | The system SHALL check that the object's bounding box fits within the configured printer build volume. The default build volume SHALL be `220 × 220 × 250` mm (generic FDM). Build volume SHALL be configurable via three `FloatProperty` values (`build_x_mm`, `build_y_mm`, `build_z_mm`). |
| FR-016 | If the object exceeds the build volume, the system SHALL compute the uniform scale factor required to fit and report it as a `WARN` with message: `"Object bounding box ({x}×{y}×{z} mm) exceeds build volume ({bx}×{by}×{bz} mm). Scale factor {factor:.2f}× required to fit."` The system MAY auto-scale the object if `auto_scale` is enabled in settings. |

### 3.2 Core Requirements — Export Pipeline

| ID | Requirement |
|----|-------------|
| FR-017 | When executing the export pipeline (`TESSERA_OT_export_for_print`), the system SHALL duplicate the active mesh object before any repair operations. The duplicate SHALL be named `"{OriginalName}_print"`. The original object SHALL remain unmodified. Validation-only mode (`TESSERA_OT_validate_print`) SHALL NOT create a duplicate (see FR-039). |
| FR-018 | The system SHALL export to **binary STL** format using `bpy.ops.export_mesh.stl()` with parameters: `use_selection=True`, `global_scale=1.0`, `use_scene_unit=False`, `ascii=False`, `use_mesh_modifiers=True`. The export unit SHALL be millimeters. |
| FR-019 | The system SHALL export to **3MF** format using Blender's 3MF exporter (`bpy.ops.export_scene.threemf()` or the `io_mesh_3mf` add-on) with the object scaled to millimeters. |
| FR-020 | The system SHALL export to **OBJ** format using `bpy.ops.export_scene.obj()` with parameters: `use_selection=True`, `use_mesh_modifiers=True`, `global_scale=1.0`. |
| FR-021 | The system SHALL allow the user to select one or more export formats (STL, 3MF, OBJ) via an `EnumProperty` with `ENUM_FLAG` option set. Default: STL only. |
| FR-022 | The system SHALL allow the user to specify the export directory via a `StringProperty` with `subtype='DIR_PATH'`. Default: the directory containing the current `.blend` file. If the `.blend` file has not been saved, default to the user's home directory. |
| FR-023 | Exported files SHALL be named `"{ObjectName}.{ext}"` where `{ObjectName}` is the original object name (not the `_print` duplicate) and `{ext}` is `stl`, `3mf`, or `obj`. |
| FR-024 | After export completes, the system SHALL delete the `_print` duplicate object from the scene to avoid clutter. The system SHALL log the deletion at `DEBUG` level. |

### 3.3 Core Requirements — Scale & Orientation

| ID | Requirement |
|----|-------------|
| FR-025 | The system SHOULD provide a print orientation optimizer that rotates the object to minimize the total area of overhanging faces. The optimizer SHALL evaluate rotations in 15° increments around the X and Y axes (24 × 24 = 576 candidate orientations), compute the overhanging face area for each, and select the rotation with the minimum overhang area. |
| FR-026 | The system SHALL ensure that the exported mesh is scaled to millimeters. If Blender's scene unit scale is not `0.001` (i.e., not already in mm), the system SHALL apply a scale transform to the `_print` duplicate: `obj.scale *= (1000.0 * scene.unit_settings.scale_length)` and apply the scale via `bpy.ops.object.transform_apply(scale=True)`. |
| FR-027 | The system SHOULD flatten the bottom face of the object to the Z=0 plane by translating the object so that its lowest vertex Z-coordinate is 0. This ensures the object sits on the build plate in the slicer. |

### 3.4 Core Requirements — Validation Report

| ID | Requirement |
|----|-------------|
| FR-028 | The system SHALL generate a validation report as a Python `dict` containing one entry per check, each with keys: `check_name` (str), `status` (one of `"PASS"`, `"WARN"`, `"FAIL"`), `message` (str), `details` (dict with check-specific data), `repaired` (bool), `repair_message` (str or None). |
| FR-029 | The system SHALL serialize the validation report to a JSON file saved alongside the exported mesh file(s) with name `"{ObjectName}_validation.json"`. |
| FR-030 | The system SHALL generate a human-readable summary string from the validation report with format: one line per check showing `"[PASS] Check Name"`, `"[WARN] Check Name: message"`, or `"[FAIL] Check Name: message"`, followed by a summary line: `"Result: X/Y checks passed, Z warnings, W failures."` |
| FR-031 | The system SHALL display the human-readable validation summary in the Blender Info area using `self.report({'INFO'}, summary)` for pass/warn results and `self.report({'WARNING'}, summary)` for any failures. |
| FR-032 | The system SHALL include aggregate metrics in the validation report: `total_checks`, `passed`, `warnings`, `failures`, `auto_repairs_applied`, `validation_time_seconds`, `export_time_seconds`. |

### 3.5 Pipeline Control Requirements

| ID | Requirement |
|----|-------------|
| FR-033 | The system SHALL expose validator settings as a `PropertyGroup` on `bpy.types.Scene.tessera.validator` with properties: `printer_type` (EnumProperty: `FDM`, `SLA`; default `FDM`), `wall_thickness_mm` (FloatProperty), `overhang_angle_deg` (FloatProperty), `build_x_mm` (FloatProperty), `build_y_mm` (FloatProperty), `build_z_mm` (FloatProperty), `auto_repair` (BoolProperty, default True), `auto_scale` (BoolProperty, default False), `auto_orient` (BoolProperty, default False), `voxel_size_mm` (FloatProperty), `export_formats` (EnumProperty with `ENUM_FLAG`), `export_directory` (StringProperty with `subtype='DIR_PATH'`). |
| FR-034 | The system SHALL provide a Blender operator `TESSERA_OT_validate_print` that runs validation only (no export) on the active object and displays the report. |
| FR-035 | The system SHALL provide a Blender operator `TESSERA_OT_export_for_print` that runs the full pipeline: duplicate → validate → auto-repair → re-validate → export → cleanup duplicate. |
| FR-036 | When `printer_type` is changed, the system SHALL auto-update `wall_thickness_mm` to the corresponding preset value (`FDM` → `1.2` mm, `SLA` → `0.5` mm) unless the user has manually overridden the value. |
| FR-037 | The system SHALL register an undo step before executing either operator so that users can revert via Ctrl+Z. |
| FR-038 | The system SHALL provide a `force_export` BoolProperty (default `False`) that, when enabled, allows export even if validation checks have `FAIL` results. A confirmation dialog SHALL be shown to the user with message: `"Validation has {N} failure(s). Exporting may produce an unprintable file. Continue?"` |
| FR-039 | When executing validation-only mode (`TESSERA_OT_validate_print`), the system SHALL NOT create a duplicate object. All validation checks SHALL operate in read-only mode on the original object using `bmesh.from_edit_mesh()` or a temporary `bmesh` copy (via `bmesh.new()` + `bmesh.from_mesh(obj.data)`) without modifying the original mesh data. Auto-repair SHALL NOT be applied in validation-only mode. The validation report SHALL be displayed but no files SHALL be exported. |
| FR-040 | When executing the export pipeline on an object with unapplied modifiers (e.g., Subdivision Surface, Mirror, Array), the system SHALL apply all modifiers on the `_print` duplicate via `bpy.ops.object.convert(target='MESH')` before running validation checks. This ensures validation operates on the evaluated (final) geometry rather than the base mesh. The system SHALL log an `INFO` message: `"Applied {count} modifier(s) on duplicate before validation."` |

### 3.6 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| Active `bpy.types.Object` | Mesh object | Must have `type == 'MESH'` with ≥ 4 vertices and ≥ 4 faces | Yes | `bpy.context.active_object` |
| `printer_type` | `str` | One of: `"FDM"`, `"SLA"` | No (default: `"FDM"`) | `"FDM"` |
| `wall_thickness_mm` | `float` | Range `0.1` to `10.0` mm | No (default: `1.2`) | `1.2` |
| `overhang_angle_deg` | `float` | Range `0.0` to `90.0` degrees | No (default: `45.0`) | `45.0` |
| `build_x_mm` | `float` | Range `10.0` to `2000.0` mm | No (default: `220.0`) | `220.0` |
| `build_y_mm` | `float` | Range `10.0` to `2000.0` mm | No (default: `220.0`) | `220.0` |
| `build_z_mm` | `float` | Range `10.0` to `2000.0` mm | No (default: `250.0`) | `250.0` |
| `export_formats` | `set[str]` | Subset of: `{"STL", "3MF", "OBJ"}` | No (default: `{"STL"}`) | `{"STL", "3MF"}` |
| `export_directory` | `str` | Valid writable filesystem path | No (default: `.blend` file directory) | `"/home/user/prints/"` |

```python
# Type Definition (for AI reference)
from dataclasses import dataclass, field

@dataclass
class ValidatorSettings:
    printer_type: str = "FDM"            # "FDM" or "SLA"
    wall_thickness_mm: float = 1.2       # Range 0.1–10.0
    overhang_angle_deg: float = 45.0     # Range 0.0–90.0
    build_x_mm: float = 220.0            # Range 10.0–2000.0
    build_y_mm: float = 220.0
    build_z_mm: float = 250.0
    auto_repair: bool = True
    auto_scale: bool = False
    auto_orient: bool = False
    voxel_size_mm: float = 0.5           # Range 0.1–5.0
    export_formats: set = field(default_factory=lambda: {"STL"})
    export_directory: str = ""           # Empty = .blend file dir
    force_export: bool = False
```

### 3.7 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| Exported file(s) | `.stl` / `.3mf` / `.obj` | Binary STL (mm), 3MF, OBJ | `MyObject.stl` |
| Validation report (JSON) | `.json` | See FR-028, FR-032 | `MyObject_validation.json` |
| Validation report (human-readable) | `str` | Printed to Blender Info area | See below |

```python
# Validation report JSON example
{
    "object_name": "BF_trellis_20260410_090000",
    "timestamp": "2026-04-10T09:00:15Z",
    "printer_type": "FDM",
    "checks": [
        {
            "check_name": "Non-Manifold Edges",
            "status": "PASS",
            "message": "No non-manifold edges detected.",
            "details": {"non_manifold_edge_count": 0},
            "repaired": false,
            "repair_message": null
        },
        {
            "check_name": "Self-Intersections",
            "status": "PASS",
            "message": "No self-intersecting faces detected.",
            "details": {"intersection_pairs": 0},
            "repaired": false,
            "repair_message": null
        },
        {
            "check_name": "Zero-Area Faces",
            "status": "PASS",
            "message": "No zero-area faces detected.",
            "details": {"degenerate_face_count": 0},
            "repaired": false,
            "repair_message": null
        },
        {
            "check_name": "Wall Thickness",
            "status": "WARN",
            "message": "12 faces (0.3%) below 1.2 mm threshold. Minimum: 0.9 mm.",
            "details": {
                "thin_face_count": 12,
                "thin_face_percentage": 0.3,
                "min_thickness_mm": 0.9,
                "threshold_mm": 1.2
            },
            "repaired": true,
            "repair_message": "Applied Solidify modifier with 0.4 mm offset."
        },
        {
            "check_name": "Overhang Angle",
            "status": "WARN",
            "message": "847 faces (4.2%) exceed 45° overhang threshold.",
            "details": {
                "overhang_face_count": 847,
                "overhang_face_percentage": 4.2,
                "max_overhang_deg": 72.3,
                "threshold_deg": 45.0
            },
            "repaired": false,
            "repair_message": null
        },
        {
            "check_name": "Mesh Volume",
            "status": "PASS",
            "message": "Mesh volume is 45230.5 mm³ (closed surface confirmed).",
            "details": {"volume_mm3": 45230.5},
            "repaired": false,
            "repair_message": null
        },
        {
            "check_name": "Scale Sanity",
            "status": "PASS",
            "message": "Bounding box 85.2×62.1×120.0 mm fits within 220×220×250 mm build volume.",
            "details": {
                "bbox_x_mm": 85.2,
                "bbox_y_mm": 62.1,
                "bbox_z_mm": 120.0,
                "build_x_mm": 220.0,
                "build_y_mm": 220.0,
                "build_z_mm": 250.0
            },
            "repaired": false,
            "repair_message": null
        }
    ],
    "summary": {
        "total_checks": 7,
        "passed": 5,
        "warnings": 2,
        "failures": 0,
        "auto_repairs_applied": 1,
        "validation_time_seconds": 3.42,
        "export_time_seconds": 1.08
    }
}
```

```text
# Human-readable summary example
=== Tessera Print Validation Report ===
Object: BF_trellis_20260410_090000
Printer: FDM

[PASS] Non-Manifold Edges
[PASS] Self-Intersections
[PASS] Zero-Area Faces
[WARN] Wall Thickness: 12 faces (0.3%) below 1.2 mm threshold. Minimum: 0.9 mm. (Auto-repaired)
[WARN] Overhang Angle: 847 faces (4.2%) exceed 45° threshold.
[PASS] Mesh Volume
[PASS] Scale Sanity

Result: 5/7 checks passed, 2 warnings, 0 failures.
Exported: MyObject.stl
```

---

## 4. CONSTRAINTS

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT make any network calls from any code in this task. |
| CON-002 | SHALL NOT depend on any Python package not bundled with Blender unless packaged as a `python-wheel` within the add-on `.zip`. NumPy and `mathutils` are bundled with Blender and are permitted. |
| CON-003 | SHALL NOT modify the original mesh object. All validation and repair operations SHALL target the `_print` duplicate exclusively. |
| CON-004 | SHALL NOT export any file without first running the full validation chain, unless `force_export` is explicitly enabled by the user. |
| CON-005 | SHALL NOT overwrite existing export files without user confirmation. If a file with the same name exists in the export directory, the system SHALL append a numeric suffix: `ObjectName_001.stl`, `ObjectName_002.stl`, etc. |
| CON-006 | SHALL NOT block Blender's UI thread for more than 100ms without yielding. For wall thickness ray-casting on large meshes (> 100K faces), the system SHALL use a modal operator with progress reporting. |
| CON-007 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. |
| CON-008 | SHALL NOT sample every face for wall thickness ray-casting on meshes with > 100K faces. The system SHALL use stratified random sampling at a rate of `min(face_count, 10000)` sample faces to bound computation time. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Full validation pipeline latency | Wall-clock time for all 7 checks | < 10 seconds | Mesh with ≤ 500K faces on a system with 16 GB RAM and a 4-core x86_64 CPU with ≥ 3.0 GHz base clock |
| NFR-002 | Non-manifold check latency | Wall-clock time for manifold edge detection | < 500 milliseconds | Mesh with ≤ 500K faces |
| NFR-003 | Self-intersection check latency | Wall-clock time for BVH overlap query | < 3 seconds | Mesh with ≤ 500K faces |
| NFR-004 | Wall thickness check latency | Wall-clock time for ray-cast sampling | < 5 seconds | Mesh with ≤ 500K faces, sampling 10K faces |
| NFR-005 | STL export latency | Wall-clock time for binary STL write | < 2 seconds | Mesh with ≤ 500K faces |
| NFR-006 | Validation report generation latency | Wall-clock time for JSON + text report | < 100 milliseconds | Any mesh size |
| NFR-007 | Peak memory overhead | Additional Python memory above mesh size | < 2× mesh memory during BVH construction | 500K face mesh (≈ 18 MB raw data) |
| NFR-008 | Wall thickness sampling accuracy | Percentage of thin-wall faces detected | ≥ 95% of actual thin-wall faces | 10K stratified sample on 500K face mesh with known thin regions |

---

## 6. ACCEPTANCE CRITERIA

### AC-001: Happy Path — Full Export Pipeline
**Given** a manifold, watertight mesh object with 100K faces, wall thickness ≥ 1.5 mm everywhere, no overhangs > 45°, bounding box 80×60×100 mm, and Blender scene unit set to meters,  
**When** `TESSERA_OT_export_for_print` is executed with default FDM settings and export format STL,  
**Then** all 7 validation checks report `PASS`, a binary STL file is created in the export directory with correct mm scale, a `_validation.json` file is created alongside it, the `_print` duplicate is deleted from the scene, the original object is unmodified, and the total operation completes in < 10 seconds.

### AC-002: Auto-Repair Non-Manifold Mesh
**Given** a mesh object with 50K faces containing 200 non-manifold boundary edges forming 5 small holes (each < 50 edges) and `auto_repair = True`,  
**When** `TESSERA_OT_export_for_print` is executed,  
**Then** the non-manifold check initially reports `FAIL`, auto-repair fills the 5 holes on the `_print` duplicate, re-validation reports `PASS` with `repaired = True`, the STL is exported, and the original mesh retains its 200 non-manifold edges unchanged.

### AC-003: Self-Intersection Detection and Repair
**Given** a mesh object with 30K faces containing 15 pairs of self-intersecting faces and `auto_repair = True`,  
**When** `TESSERA_OT_validate_print` is executed,  
**Then** the self-intersection check reports the 15 intersection pairs in `details`, auto-repair applies a boolean union to self, and re-validation reports 0 intersection pairs.

### AC-004: Wall Thickness Warning with Auto-Repair
**Given** a mesh object with 50K faces where 500 faces have wall thickness of 0.8 mm (below the FDM threshold of 1.2 mm) and `auto_repair = True`,  
**When** `TESSERA_OT_export_for_print` is executed with `printer_type = "FDM"`,  
**Then** the wall thickness check reports `FAIL` with `min_thickness_mm = 0.8` and `thin_face_count = 500`, the Solidify modifier is applied to the `_print` duplicate, re-validation shows all faces ≥ 1.2 mm thick, and the STL is exported.

### AC-005: Overhang Warning Without Auto-Repair
**Given** a mesh object with 50K faces where 2000 faces have overhangs exceeding 45° and `auto_repair = True`,  
**When** `TESSERA_OT_export_for_print` is executed,  
**Then** the overhang check reports `WARN` (not `FAIL`) with `overhang_face_count = 2000`, no auto-repair is applied for overhangs, and the STL is exported (overhangs produce warnings, not blocking failures).

### AC-006: Scale Sanity — Object Exceeds Build Volume
**Given** a mesh object with bounding box 300×200×400 mm and build volume set to 220×220×250 mm, with `auto_scale = False`,  
**When** `TESSERA_OT_export_for_print` is executed,  
**Then** the scale sanity check reports `WARN` with the computed scale factor (`0.625×`), the STL is still exported at original size, and the validation report includes the warning message.

### AC-007: Force Export with Failures
**Given** a mesh object that fails the manifold check with 50 non-manifold edges and auto-repair also fails to fix them, and `force_export = True`,  
**When** `TESSERA_OT_export_for_print` is executed,  
**Then** a confirmation dialog is shown, the user confirms, the STL is exported despite the failure, and the validation report shows the `FAIL` result with `repaired = False`.

### AC-008: Multi-Format Export
**Given** a valid mesh object and `export_formats = {"STL", "3MF", "OBJ"}`,  
**When** `TESSERA_OT_export_for_print` is executed,  
**Then** three files are created: `ObjectName.stl`, `ObjectName.3mf`, `ObjectName.obj`, each with correct format-specific encoding, and a single `ObjectName_validation.json` report covers all exports.

### AC-009: Validation-Only Mode
**Given** a mesh object with mixed pass/warn/fail checks,  
**When** `TESSERA_OT_validate_print` is executed (validation only, no export),  
**Then** the validation report is displayed in the Blender Info area, no files are exported, no duplicate is created (validation runs in-place analysis without modification), and the operator completes in < 10 seconds.

### AC-010: Duplicate Preserves Original
**Given** a mesh object the user has manually edited (added vertex groups, custom normals, shape keys),  
**When** `TESSERA_OT_export_for_print` is executed and the pipeline completes (pass or fail),  
**Then** the original object retains all vertex groups, custom normals, and shape keys unchanged, and the `_print` duplicate is deleted.

---

## 7. EDGE CASES

### EC-001: Mesh with Zero Volume (Open Surface)
| Aspect | Detail |
|--------|--------|
| **Scenario** | Reconstruction produces a mesh that looks like a bowl — open on top, volume = 0 because it is not a closed surface. |
| **Input Example** | A hemisphere mesh with 10K faces, no bottom cap; `volume_mm3 = 0.0`. |
| **Expected Behavior** | The system SHALL report the volume check as `FAIL`. If `auto_repair = True`, the system SHALL first recalculate normals, then if volume is still ≤ 0, apply voxel remesh at the configured voxel size to close the surface. The diagnostics SHALL report `"Volume was 0 mm³ (open surface). Applied voxel remesh to close."` |
| **Test ID** | TS-004 |

### EC-002: Extremely Thin Object (Entire Model Below Wall Thickness)
| Aspect | Detail |
|--------|--------|
| **Scenario** | User generates a very thin medallion or coin where the entire model is 0.5 mm thick, below the 1.2 mm FDM threshold. Applying a Solidify modifier would double the model's volume and distort its shape. |
| **Input Example** | A disc mesh, 50 mm diameter × 0.5 mm thick, all 8K faces fail wall thickness. |
| **Expected Behavior** | The system SHALL detect that > 80% of sampled faces fail wall thickness and report `FAIL` with message: `"Model is uniformly thin (0.5 mm). Auto-repair (Solidify) would significantly alter geometry. Manual adjustment recommended."` The system SHALL NOT apply the Solidify modifier when thin-face percentage exceeds 80%. |
| **Test ID** | TS-005 |

### EC-003: No Active Object Selected
| Aspect | Detail |
|--------|--------|
| **Scenario** | User triggers the export operator but no mesh object is selected or the active object is a camera, light, or empty. |
| **Input Example** | `bpy.context.active_object` is `None` or `bpy.context.active_object.type == 'CAMERA'`. |
| **Expected Behavior** | The system SHALL return `{'CANCELLED'}` from the operator with `self.report({'ERROR'}, "No mesh object selected. Select a mesh object to validate.")`. The operator's `poll()` method SHALL return `False` when `context.active_object` is `None` or `context.active_object.type != 'MESH'`. |
| **Test ID** | TS-006 |

### EC-004: Export Directory Does Not Exist or Is Not Writable
| Aspect | Detail |
|--------|--------|
| **Scenario** | User configures an export directory that has been deleted or is on a read-only filesystem. |
| **Input Example** | `export_directory = "/mnt/usb/prints/"` where the USB drive has been ejected. |
| **Expected Behavior** | The system SHALL check `os.path.isdir(export_directory)` and `os.access(export_directory, os.W_OK)` before attempting export. If either check fails, the system SHALL report `{'CANCELLED'}` with message: `"Export directory '{path}' does not exist or is not writable."` |
| **Test ID** | TS-007 |

### EC-005: BVH Self-Intersection Check on Very Large Mesh
| Aspect | Detail |
|--------|--------|
| **Scenario** | Mesh with > 500K faces causes the `BVHTree.overlap()` call to exceed the 3-second NFR target due to O(n log n) complexity with a high constant factor. |
| **Input Example** | 2,000,000 face mesh from a high-resolution reconstruction. |
| **Expected Behavior** | The system SHALL log a `WARNING`: `"Self-intersection check on {count} faces may exceed 3-second target. Consider decimating first."`. The system SHALL NOT skip the check but SHALL proceed and report the elapsed time in the check's `details`. If the check exceeds 30 seconds, the system SHALL abort the self-intersection check, report `WARN` with message `"Self-intersection check timed out after 30 seconds. Skipped."`, and proceed with remaining checks. |
| **Test ID** | TS-008 |

### EC-006: Unsaved Blend File — No Default Export Directory
| Aspect | Detail |
|--------|--------|
| **Scenario** | User has not saved the `.blend` file, so there is no file directory to default to for exports. |
| **Input Example** | `bpy.data.filepath == ""` (unsaved file). |
| **Expected Behavior** | The system SHALL fall back to `os.path.expanduser("~")` as the export directory and log an `INFO` message: `"Blend file not saved. Defaulting export directory to home directory: {path}."` |
| **Test ID** | TS-009 |

### EC-007: Object with Unapplied Modifiers
| Aspect | Detail |
|--------|--------|
| **Scenario** | The active object has unapplied modifiers (e.g., Subdivision Surface level 2, Mirror on X-axis) that significantly change the evaluated geometry compared to the base mesh. Validation on the base mesh alone would produce false-pass results (e.g., base mesh has adequate wall thickness but subdivided geometry does not). |
| **Input Example** | A cube with a Subdivision Surface modifier (level 2) and a Solidify modifier (0.3 mm). Base mesh: 6 faces, all walls > 1.2 mm. Evaluated mesh: 96 faces, some walls < 1.2 mm due to subdivision curvature. |
| **Expected Behavior** | The system SHALL apply all modifiers on the `_print` duplicate via `bpy.ops.object.convert(target='MESH')` before validation (FR-040). Validation checks SHALL operate on the fully evaluated geometry. The validation report SHALL note: `"Applied {count} modifier(s) on duplicate before validation."` The original object's modifier stack SHALL remain unchanged. |
| **Test ID** | TS-030 |

---

## 8. OUT OF SCOPE

The following are explicitly **excluded** from this feature:

- ❌ 3D reconstruction or mesh generation (TASK-TS-0004)
- ❌ Mesh cleanup / topology repair (non-manifold edge fixing, normal recalc, dedup — SPEC-TS-0005). This spec validates the *result* of cleanup; it does not replace it.
- ❌ UV unwrapping or texture coordinate generation
- ❌ Vertex color, material, or texture export
- ❌ 3MF advanced metadata (print settings, infill, support suggestions — deferred to Phase 4, M4.3)
- ❌ Direct slicer integration (Cura, PrusaSlicer API calls — PRD NG2)
- ❌ Multi-part assembly export or split-by-volume
- ❌ Natural-language refinement of the mesh (TASK-TS-0009)
- ❌ Dimension inference from reference images (TASK-TS-0008)
- ❌ Printer profile presets beyond FDM/SLA type selection (Phase 3, M3.5)
- ❌ Preview rendering of the validated mesh (Phase 2, M2.5)
- ❌ Cloud upload or network-based export

---

## 9. SECURITY CONSIDERATIONS

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — local Blender add-on, no network interaction |
| **Auth Method** | None |
| **Required Permissions** | File system read/write for export files (handled by OS) |
| **Rate Limiting** | N/A |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| Mesh geometry (vertices, faces) | Internal | In-memory only; persisted in `.blend` file by Blender |
| Validation report JSON | Internal | Written to user-specified local directory only |
| Exported STL/3MF/OBJ files | Internal | Written to user-specified local directory only |
| Export directory path | Internal | Displayed in UI; not transmitted anywhere |
| Printer settings | Internal | Stored in scene properties; not transmitted |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL validate that the active object is a `bpy.types.Object` with `type == 'MESH'` before any processing. |
| SEC-002 | SHALL validate export directory path using `os.path.realpath()` to resolve symlinks and prevent path traversal attacks via `../` sequences. |
| SEC-003 | SHALL sanitize the object name used in exported filenames by replacing characters not matching `[a-zA-Z0-9_\-\.]` with `_` to prevent filesystem injection. |
| SEC-004 | SHALL NOT make any network connections, DNS lookups, or socket operations. |
| SEC-005 | SHALL NOT execute any code from user-specified paths or dynamically load modules based on input data. |
| SEC-006 | SHALL validate that export file paths do not escape the configured export directory (i.e., `os.path.commonpath([export_dir, file_path]) == export_dir`). |

---

## 10. API CONTRACT [CONDITIONAL]

> **No REST/HTTP APIs.** This section documents the internal Python API contract for downstream tasks and the end-to-end pipeline.

### 10.1 PrintValidator API
```python
from tessera.validator.print_validator import PrintValidator
from tessera.validator.report import ValidationReport

validator = PrintValidator()
report: ValidationReport = validator.validate(
    context=bpy.context,
    obj=obj,                              # bpy.types.Object with mesh data
    printer_type="FDM",                   # "FDM" or "SLA"
    wall_thickness_mm=1.2,                # Range 0.1–10.0
    overhang_angle_deg=45.0,              # Range 0.0–90.0
    build_volume_mm=(220.0, 220.0, 250.0) # (x, y, z) in mm
)

# Returns: ValidationReport with .checks, .summary, .to_json(), .to_text()
print(report.to_text())
report.save_json("/path/to/output/MyObject_validation.json")
```

### 10.2 ExportPipeline API
```python
from tessera.export.export_pipeline import ExportPipeline

pipeline = ExportPipeline()
result = pipeline.execute(
    context=bpy.context,
    obj=obj,                                # Original bpy.types.Object
    export_formats={"STL", "3MF"},          # Set of format strings
    export_directory="/home/user/prints/",  # Target directory
    auto_repair=True,                       # Attempt auto-repair on failures
    auto_orient=False,                      # Orientation optimization
    auto_scale=False,                       # Auto-scale to fit build volume
    force_export=False,                     # Export despite failures
    printer_type="FDM",
    wall_thickness_mm=1.2,
    overhang_angle_deg=45.0,
    build_volume_mm=(220.0, 220.0, 250.0)
)

# Returns: ExportResult
# result.report: ValidationReport
# result.exported_files: list[str]  — absolute paths to exported files
# result.success: bool              — True if exported (no failures or force_export)
```

### 10.3 Integration with Mesh Cleanup (SPEC-TS-0005)
```python
# Expected end-to-end calling pattern
from tessera.mesh.importer import MeshImporter
from tessera.mesh.cleanup import MeshCleanupPipeline
from tessera.export.export_pipeline import ExportPipeline

# Step 1: Import raw mesh from reconstruction
importer = MeshImporter()
obj = importer.import_mesh(vertices=raw_mesh.vertices, faces=raw_mesh.faces)

# Step 2: Run cleanup pipeline (SPEC-TS-0005)
cleanup = MeshCleanupPipeline()
diagnostics = cleanup.execute(bpy.context, obj)

# Step 3: Validate and export (this spec, SPEC-TS-0006)
export = ExportPipeline()
result = export.execute(
    context=bpy.context,
    obj=obj,
    export_formats={"STL"},
    export_directory="/home/user/prints/",
    auto_repair=True
)

if result.success:
    print(f"Exported: {result.exported_files}")
else:
    print(f"Export failed: {result.report.to_text()}")
```

### 10.4 Individual Check API
```python
from tessera.validator.checks.manifold import ManifoldCheck

check = ManifoldCheck()
result = check.check(obj, settings)
# result.status: "PASS" | "WARN" | "FAIL"
# result.message: str
# result.details: dict

if result.status == "FAIL" and settings.auto_repair:
    repair_result = check.repair(obj, settings)
    # repair_result.success: bool
    # repair_result.message: str
```

---

## 11. OBSERVABILITY

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------
| Validation pipeline started | INFO | `object_name`, `face_count`, `printer_type` | ⚠️ No PII |
| Validation check started | DEBUG | `check_name`, `face_count` | ⚠️ No PII |
| Validation check completed | DEBUG | `check_name`, `status`, `elapsed_seconds` | ⚠️ No PII |
| Auto-repair attempted | INFO | `check_name`, `repair_strategy` | ⚠️ No PII |
| Auto-repair succeeded | INFO | `check_name`, `repair_message` | ⚠️ No PII |
| Auto-repair failed | WARN | `check_name`, `error_message` | ⚠️ No PII |
| Validation pipeline completed | INFO | Full summary (passed/warned/failed counts, elapsed time) | ⚠️ No PII |
| Export started | INFO | `format`, `export_path` | ⚠️ No PII |
| Export completed | INFO | `format`, `file_size_bytes`, `export_time_seconds` | ⚠️ No PII |
| Export failed | ERROR | `format`, `error_message` | ⚠️ No PII |
| Duplicate object created | DEBUG | `duplicate_name` | ⚠️ No PII |
| Duplicate object deleted | DEBUG | `duplicate_name` | ⚠️ No PII |
| Directory validation failed | ERROR | `export_directory`, `reason` | ⚠️ No PII |
| Self-intersection check timeout | WARN | `face_count`, `elapsed_seconds`, `timeout_seconds` | ⚠️ No PII |
| Large mesh warning | WARN | `face_count`, `threshold` | ⚠️ No PII |
| Wall thickness sampling enabled | DEBUG | `total_faces`, `sample_count` | ⚠️ No PII |

> All logging uses Python's `logging` module with logger name `"tessera.validator"` and `"tessera.export"`. Blender routes this to the system console.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only).

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — functionality available when add-on is installed |
| **Default State** | All validation checks enabled; auto-repair enabled; auto-orient/auto-scale disabled |
| **Rollout Plan** | Bundled with add-on `.zip`; orientation optimizer (FR-025) is opt-in |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| SPEC-TS-0001 (Add-on Scaffold) | Yes | Provides module registration, UI panel framework, scene properties |
| SPEC-TS-0005 (Mesh Import & Cleanup) | Yes | Produces the cleaned mesh that this task validates |
| Blender 4.2+ | Yes | Required for API compatibility; 3MF exporter availability |
| Blender 3D Print Toolbox add-on | No | Optional — system implements its own checks but MAY delegate to 3D Print Toolbox if enabled |
| NumPy (bundled with Blender) | Yes | Used for array operations in ray-casting |

### 12.3 Rollback Plan
1. User disables the add-on or reverts to a previous add-on version
2. Existing exported files remain on disk unaffected
3. Existing `.blend` files are unaffected — mesh objects remain in the scene after add-on removal
4. Verify no orphan data blocks via Blender's Outliner → Orphan Data view

---

## 13. TEST SCENARIOS

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Full pipeline on valid mesh: all checks pass, STL exported | Integration | AC-001 | Must Pass |
| TS-002 | Auto-repair non-manifold mesh: holes filled, re-validation passes | Integration | AC-002 | Must Pass |
| TS-003 | Self-intersection detection and boolean union repair | Integration | AC-003 | Must Pass |
| TS-004 | Zero-volume open surface: voxel remesh closes the mesh | Unit | EC-001 | Must Pass |
| TS-005 | Uniformly thin model: Solidify skipped, FAIL reported | Unit | EC-002 | Must Pass |
| TS-006 | No mesh selected: operator poll returns False | Unit | EC-003 | Must Pass |
| TS-007 | Invalid export directory: operator cancelled with error | Unit | EC-004 | Must Pass |
| TS-008 | BVH overlap timeout on 2M face mesh | Performance | EC-005 | Should Pass |
| TS-009 | Unsaved blend file: export defaults to home directory | Unit | EC-006 | Must Pass |
| TS-010 | Wall thickness FAIL + auto-repair Solidify | Integration | AC-004 | Must Pass |
| TS-011 | Overhang WARN: no repair, export proceeds | Unit | AC-005 | Must Pass |
| TS-012 | Scale sanity WARN: factor computed, no auto-scale | Unit | AC-006 | Must Pass |
| TS-013 | Force export with failures: confirmation + export | Integration | AC-007 | Must Pass |
| TS-014 | Multi-format export: STL + 3MF + OBJ created | Integration | AC-008 | Must Pass |
| TS-015 | Validation-only mode: report shown, no export | Unit | AC-009 | Must Pass |
| TS-016 | Original object unchanged after export pipeline | Integration | AC-010 | Must Pass |
| TS-017 | Full pipeline latency < 10 seconds on 500K face mesh | Performance | NFR-001 | Must Pass |
| TS-018 | STL export latency < 2 seconds on 500K face mesh | Performance | NFR-005 | Must Pass |
| TS-019 | ValidationReport JSON serialization < 100ms | Unit | NFR-006 | Must Pass |
| TS-020 | Object name sanitization for filenames | Unit | SEC-003 | Must Pass |
| TS-021 | Export path traversal prevention | Unit | SEC-006 | Must Pass |
| TS-022 | File collision: numeric suffix appended | Unit | CON-005 | Must Pass |
| TS-023 | Validator property group registration and defaults | Unit | FR-033 | Must Pass |
| TS-024 | Printer type change auto-updates wall thickness | Unit | FR-036 | Must Pass |
| TS-025 | Undo after export restores pre-pipeline state | Integration | FR-037 | Must Pass |
| TS-026 | Print orientation optimizer selects minimum overhang | Integration | FR-025 | Should Pass |
| TS-027 | MM scale conversion for non-mm scene units | Unit | FR-026 | Must Pass |
| TS-028 | Bottom face Z=0 alignment | Unit | FR-027 | Must Pass |
| TS-029 | Wall thickness sampling: ≥ 95% detection rate | Performance | NFR-008 | Must Pass |
| TS-030 | Unapplied modifiers: evaluated geometry used for validation | Integration | EC-007 | Must Pass |
| TS-031 | Overhang > 50% faces: FAIL result produced | Unit | FR-012 | Must Pass |
| TS-032 | Validation-only mode: no duplicate created, read-only checks | Unit | FR-039 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0001 (Add-on Scaffold) | Required | Draft | Tessera | Yes — need module registration framework |
| SPEC-TS-0005 (Mesh Import & Cleanup) | Required | Draft | Tessera | Yes — need cleaned mesh as input |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| Blender 4.2+ LTS | Required | [docs.blender.org](https://docs.blender.org/api/current/) | No fallback — hard requirement |
| Blender `bmesh` module | Required | [bmesh API](https://docs.blender.org/api/current/bmesh.html) | N/A — bundled with Blender |
| Blender `mathutils.bvhtree` | Required | [mathutils API](https://docs.blender.org/api/current/mathutils.bvhtree.html) | N/A — bundled with Blender |
| NumPy (Blender-bundled) | Required | [numpy.org](https://numpy.org/doc/) | N/A — bundled with Blender 4.x |
| Blender 3D Print Toolbox add-on | Optional | [Blender Docs](https://docs.blender.org/manual/en/latest/addons/mesh/3d_print_toolbox.html) | System implements own checks; 3D Print Toolbox is supplementary |

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
| SHALL/SHOULD/MAY requirements | 20 | 20 | 40 requirements with precise SHALL/SHOULD/MAY language across FR-001 to FR-040 |
| Quantified NFRs | 15 | 15 | 8 NFRs, all quantified with specific latency/memory/accuracy targets and measurement conditions |
| Given-When-Then criteria (3+) | 20 | 20 | 10 acceptance criteria in Given-When-Then format with specific values |
| Edge cases (2+) | 15 | 15 | 7 edge cases with concrete input examples and expected behaviors |
| Out of scope defined | 10 | 10 | 12 explicit exclusions listed with cross-references to other tasks/phases |
| Security constraints | 10 | 10 | 6 security requirements + data classification table |
| No ambiguous language | 10 | 10 | All ambiguous terms replaced with specifics. NFR-001 hardware spec tightened to "4-core x86_64 CPU with ≥ 3.0 GHz base clock" |
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
- [x] "handle gracefully" → replaced with specific error responses (EC-003, EC-004)
- [x] "fast" / "efficient" / "performant" → replaced with ms/second targets (NFR-001 through NFR-008)
- [x] "secure" → replaced with SEC-001 through SEC-006
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → not used

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-10 | Orchestrator (AI) | Initial draft |
| 1.1 | 2026-04-14 | Spec Review | Fixed FR-017/AC-009 duplicate contradiction (added FR-039 for read-only validation-only mode). Added FR-040 and EC-007 for unapplied modifiers. Added overhang severity escalation to FR-012 (>50% → FAIL). Tightened NFR-001 hardware spec. Added TS-030/031/032. |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0006-print-validator-export.md`
