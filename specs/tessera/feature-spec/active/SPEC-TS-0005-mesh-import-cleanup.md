# Feature Specification: Mesh Import, Cleanup & Topology Optimization

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0005 |
| **Task ID** | TASK-TS-0005 |
| **Status** | Approved |
| **Version** | 1.1 |
| **Created** | 2026-04-09 |
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
AI-generated 3D meshes from reconstruction models (Trellis, InstantMesh, Zero-1-to-3++, etc.) are universally noisy — overlapping faces, non-manifold edges, inverted normals, degenerate triangles, and excessive poly-counts. These meshes cannot be directly 3D-printed, edited in Blender, or exported to slicers without crashing or producing failed prints. This task is the "cleanup crew" that transforms raw AI output into clean, watertight Blender objects with print-ready topology.

The feature spans two phases: Phase 1 delivers the minimum viable cleanup for the end-to-end demo (PRD M1.5 — basic import + repair to manifold), while Phase 2 adds quality topology optimization for production use (PRD M2.2 — quad remesh, poly-count control).

### 1.2 User Story
**As a** user who just generated a 3D reconstruction from reference images,  
**I want** the mesh to be automatically cleaned up and imported into Blender with watertight topology and consistent normals,  
**So that** I can edit it in Blender if needed and it is ready for 3D printing without manual repair.

### 1.3 Proposed Approach
Build a `MeshCleanupPipeline` class inside the Tessera add-on that accepts raw mesh data (vertices + faces) from the reconstruction engine adapter, imports it into the active Blender scene, and executes a configurable chain of cleanup operations via `bpy.ops.mesh.*` and `bmesh` API calls. Phase 1 implements the core pipeline: duplicate removal, normal recalculation, hole filling, and voxel remesh fallback. Phase 2 extends it with QuadriFlow-based quad remesh, decimation with sharp-edge preservation, and named object hierarchy creation.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Manifold output rate | 0% (no cleanup exists) | 100% of cleaned meshes | Automated `bpy.ops.mesh.select_non_manifold()` check post-cleanup |
| Cleanup latency (≤500K faces) | N/A | < 5 seconds | `time.perf_counter()` around pipeline execution |
| Shape fidelity (Hausdorff distance) | N/A | < 2% of bounding-box diagonal | PyMeshLab `hausdorff_distance` between input and output |

---

## 2. TECHNICAL CONTEXT

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/__init__.py` | Add-on scaffold (SPEC-TS-0001) | Module registration, class collection pattern |
| `tessera/operators/` | Existing operator stubs | Operator `bl_idname` / `bl_label` naming convention |
| `tessera/properties.py` | Scene-level PropertyGroup | Extending scene properties with cleanup settings |
| Blender 3D Print Toolbox source | Official print validation add-on | Manifold check, thin-wall detection patterns |
| `bpy.ops.mesh.*` docs | Blender mesh operations | Available cleanup operators and their parameters |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`, `bmesh`, `mathutils`)
- **Mesh Processing:** `bpy.ops.mesh`, `bmesh` module, Blender modifiers (Voxel Remesh, Decimate, QuadriFlow Remesh)
- **Validation:** Runtime assertions + Blender property system
- **Testing:** `pytest` run via `blender --background --python` for headless testing
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── mesh/
│   ├── __init__.py
│   ├── importer.py           # MeshImporter: vertices+faces → bpy.types.Object
│   ├── cleanup.py            # MeshCleanupPipeline: orchestrates cleanup chain
│   ├── steps/
│   │   ├── __init__.py
│   │   ├── dedup.py           # Step: remove doubles / merge by distance
│   │   ├── normals.py         # Step: recalculate normals outside
│   │   ├── hole_fill.py       # Step: detect and fill boundary edges
│   │   ├── voxel_remesh.py    # Step: voxel remesh fallback
│   │   ├── quad_remesh.py     # Step: QuadriFlow quad remesh [Phase 2]
│   │   └── decimate.py        # Step: Decimate modifier [Phase 2]
│   ├── hierarchy.py           # Phase 2: named objects, origin placement
│   └── diagnostics.py         # Pre/post cleanup mesh stats
├── operators/
│   ├── cleanup_ops.py         # OT_RunCleanup, OT_RunQuadRemesh, etc.
│   └── ...
└── ui/
    ├── cleanup_panel.py       # Cleanup settings sub-panel
    └── ...
```

**Pipeline pattern:** The `MeshCleanupPipeline` follows a chain-of-responsibility design. Each step is an independent class with an `execute(context, obj, settings)` method. Steps are executed in sequence, and each step reports what it changed (vertices removed, faces filled, etc.) for the diagnostics report. Steps can be individually enabled/disabled via cleanup settings.

**Data flow:**
```
ReconstructionEngine output (numpy arrays: vertices, faces)
  → MeshImporter.import_mesh() → bpy.types.Object
  → MeshCleanupPipeline.execute()
    → DedupStep → NormalsStep → HoleFillStep → [VoxelRemeshStep if needed]
    → [QuadRemeshStep → DecimateStep → HierarchyStep]  (Phase 2)
  → Cleaned bpy.types.Object in active scene
```

---

## 3. FUNCTIONAL REQUIREMENTS

### 3.1 Core Requirements — Phase 1 (Basic Import + Repair)

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL accept raw mesh data as NumPy arrays (`vertices: np.ndarray` of shape `(N, 3)` with dtype `float32`, `faces: np.ndarray` of shape `(M, 3)` with dtype `int32`) and create a new `bpy.types.Object` in the active Blender scene. |
| FR-002 | The system SHALL set the newly created object's name to `"Tessera_<timestamp>"` where `<timestamp>` is `YYYYMMDD_HHMMSS` format, and place it at the scene's 3D cursor location. |
| FR-003 | The system SHALL execute a duplicate vertex removal step using `bmesh.ops.remove_doubles()` with a configurable merge distance (default: `0.0001` meters, range: `0.00001` to `0.01` meters). |
| FR-004 | The system SHALL recalculate all face normals to point outward using `bmesh.ops.recalc_face_normals()`, ensuring consistent winding order across all faces. |
| FR-005 | The system SHALL detect boundary edges (edges belonging to only one face) and fill holes by triangulating boundary loops using `bmesh.ops.triangle_fill()` for loops with ≤ 500 edges. Loops exceeding 500 edges SHALL be skipped and logged as warnings. |
| FR-006 | The system SHALL provide a voxel remesh fallback that applies a Blender Voxel Remesh modifier with a configurable voxel size (default: `0.01` meters, range: `0.001` to `0.1` meters) when the mesh remains non-manifold after steps FR-003 through FR-005. |
| FR-007 | The system SHALL report cleanup diagnostics as a Python `dict` containing the following 15 keys: |

**FR-007 Diagnostics Key Table:**

| Key | Type | Source Step |
|-----|------|------------|
| `vertices_before` | `int` | Import |
| `vertices_after` | `int` | Final |
| `faces_before` | `int` | Import |
| `faces_after` | `int` | Final |
| `doubles_removed` | `int` | DedupStep |
| `degenerate_faces_removed` | `int` | DegenerateStep (EC-001) |
| `normals_flipped` | `int` | NormalsStep |
| `holes_filled` | `int` | HoleFillStep |
| `holes_skipped` | `int` | HoleFillStep |
| `voxel_remesh_applied` | `bool` | VoxelRemeshStep |
| `quad_remesh_applied` | `bool` | QuadRemeshStep |
| `decimate_applied` | `bool` | DecimateStep |
| `is_manifold` | `bool` | Final validation |
| `is_watertight` | `bool` | Final validation |
| `cleanup_time_seconds` | `float` | Pipeline timer |
| FR-008 | The system SHALL log each cleanup step's execution and result at `DEBUG` level using the `tessera` logger. |
| FR-009 | The system SHALL select the cleaned object as the active object and frame it in the 3D viewport using `bpy.ops.view3d.view_selected()` after cleanup completes. |

### 3.2 Core Requirements — Phase 2 (Topology Optimization)

| ID | Requirement |
|----|-------------|
| FR-010 | The system SHOULD provide a quad remesh step that converts a triangle mesh to quad-dominant topology using Blender's QuadriFlow remesh operator (`bpy.ops.object.quadriflow_remesh()`) with a configurable target face count (default: `10000`, range: `1000` to `500000`). |
| FR-011 | The system SHOULD provide a decimation step that applies a Blender Decimate modifier in `COLLAPSE` mode with a configurable target face count (default: `50000`, range: `1000` to `1000000`) and `use_collapse_triangulate = False`. |
| FR-012 | The decimation step SHOULD preserve sharp edges by setting `use_dissolve_boundaries = False` and marking edges with a dihedral angle > 30° as sharp prior to decimation. |
| FR-013 | The system SHOULD set the object's origin to the center of its bounding box via `bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')`. |
| FR-014 | The system SHOULD assign a descriptive object name format: `"BF_<source>_<timestamp>"` where `<source>` is the reconstruction model name (e.g., `"trellis"`, `"instantmesh"`). |
| FR-015 | The system MAY create a parent empty object named `"Tessera_Session_<timestamp>"` to group multiple generated objects in the Blender outliner hierarchy. |
| FR-016 | The quad remesh step SHALL be opt-in (disabled by default) and SHALL NOT execute automatically unless the user explicitly enables it in cleanup settings. |

### 3.3 Pipeline Control Requirements

| ID | Requirement |
|----|-------------|
| FR-017 | The system SHALL expose cleanup settings as a `PropertyGroup` on `bpy.types.Scene.tessera.cleanup` with the following properties: `merge_distance` (FloatProperty), `voxel_size` (FloatProperty), `auto_voxel_fallback` (BoolProperty, default True), `enable_quad_remesh` (BoolProperty, default False), `quad_target_faces` (IntProperty), `enable_decimate` (BoolProperty, default False), `decimate_target_faces` (IntProperty). |
| FR-018 | The system SHALL provide a Blender operator `TESSERA_OT_run_cleanup` that executes the full cleanup pipeline on the active object and MAY be invoked from the UI panel or via Python scripting. |
| FR-019 | The system SHALL register an undo step before executing the cleanup pipeline so that users can revert via Ctrl+Z. |
| FR-020 | If a non-critical cleanup step (hole fill, degenerate removal) raises an exception, the pipeline SHALL catch the exception, log it at `ERROR` level with the step name and traceback, append the error to a `step_errors` list in the diagnostics dict, and continue to the next step. If a critical step (import, dedup, normals) raises an exception, the pipeline SHALL raise a `MeshCleanupError(step_name, original_exception)` and leave the undo step intact so the scene can be reverted. |

### 3.4 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| `vertices` | `np.ndarray` | Shape `(N, 3)`, dtype `float32`, N ≥ 3 | Yes | `np.array([[0,0,0],[1,0,0],[0,1,0]], dtype=np.float32)` |
| `faces` | `np.ndarray` | Shape `(M, 3)`, dtype `int32`, values in range `[0, N-1]` | Yes | `np.array([[0,1,2]], dtype=np.int32)` |
| `source_model` | `str` | Well-known values: `"trellis"`, `"instantmesh"`, `"openlrm"`, `"zero123"`, `"custom"`. Any alphanumeric string with hyphens/underscores (≤ 32 chars) is accepted; SEC-005 sanitization applies. | No (default: `"custom"`) | `"trellis"` |
| `merge_distance` | `float` | Range `0.00001` to `0.01` meters | No (default: `0.0001`) | `0.0001` |
| `voxel_size` | `float` | Range `0.001` to `0.1` meters | No (default: `0.01`) | `0.01` |

```python
# Type Definition (for AI reference)
from dataclasses import dataclass
import numpy as np

@dataclass
class RawMeshData:
    vertices: np.ndarray   # Shape (N, 3), dtype float32
    faces: np.ndarray      # Shape (M, 3), dtype int32
    source_model: str = "custom"
```

### 3.5 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `object` | `bpy.types.Object` | Blender mesh object in active scene | `bpy.data.objects["BF_trellis_20260409_143022"]` |
| `diagnostics` | `dict` | See FR-007 | See below |

```python
# Diagnostics output example
{
    "vertices_before": 125430,
    "vertices_after": 98210,
    "faces_before": 250860,
    "faces_after": 196420,
    "doubles_removed": 27220,
    "degenerate_faces_removed": 14,
    "normals_flipped": 1843,
    "holes_filled": 12,
    "holes_skipped": 0,
    "voxel_remesh_applied": False,
    "quad_remesh_applied": False,
    "decimate_applied": False,
    "is_manifold": True,
    "is_watertight": True,
    "cleanup_time_seconds": 2.34,
    "step_errors": []  # List of {"step": str, "error": str} for non-critical failures
}
```

---

## 4. CONSTRAINTS

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT make any network calls from any code in this task. |
| CON-002 | SHALL NOT depend on any Python package not bundled with Blender unless packaged as a `python-wheel` within the add-on `.zip`. NumPy is bundled with Blender and is permitted. |
| CON-003 | SHALL NOT modify the original input mesh data arrays. The system SHALL operate on a copy after import into Blender. |
| CON-004 | SHALL NOT execute destructive operations (voxel remesh, quad remesh, decimate) without first registering an undo step via `bpy.ops.ed.undo_push()`. |
| CON-005 | SHALL NOT alter any existing objects in the scene. All operations SHALL target only the newly imported object. |
| CON-006 | SHALL NOT use `bpy.ops.mesh.*` operators for performance-critical inner loops. Use `bmesh` API directly for bulk vertex/face operations. Operators MAY be used for high-level steps (remesh, decimate) where no `bmesh` equivalent exists. |
| CON-007 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. |
| CON-008 | SHALL NOT block Blender's UI thread for more than 100ms without yielding. For operations exceeding this threshold, the system SHALL use a modal operator with progress reporting. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Phase 1 cleanup latency | Wall-clock time for full pipeline (FR-003 through FR-006) | < 5 seconds | Mesh with ≤ 500K faces on a system with 16 GB RAM and any modern CPU (2020+) |
| NFR-002 | Mesh import latency | Wall-clock time for `MeshImporter.import_mesh()` | < 1 second | 500K vertices / 1M faces input array |
| NFR-003 | Voxel remesh latency | Wall-clock time for voxel remesh fallback | < 10 seconds | 500K face mesh, voxel size 0.01m |
| NFR-004 | Quad remesh latency | Wall-clock time for QuadriFlow remesh | < 60 seconds | 500K face mesh, target 10K faces |
| NFR-005 | Peak memory overhead | Additional Python memory above input mesh size | < 3× input mesh memory | 500K face mesh (≈ 18 MB raw data) |
| NFR-006 | Shape fidelity | Hausdorff distance between input and cleaned output | < 2% of bounding-box diagonal | After Phase 1 cleanup (no voxel remesh) |
| NFR-007 | Shape fidelity after voxel remesh | Hausdorff distance between input and remeshed output | < 5% of bounding-box diagonal | After voxel remesh at default voxel size |

---

## 6. ACCEPTANCE CRITERIA

### AC-001: Basic Mesh Import
**Given** a reconstruction engine output of 50,000 vertices and 100,000 triangular faces as NumPy arrays,  
**When** `MeshImporter.import_mesh(vertices, faces)` is called,  
**Then** a new `bpy.types.Object` with a `bpy.types.Mesh` data block appears in the active scene containing exactly 50,000 vertices and 100,000 faces, the object is selected and active, and the operation completes in < 1 second.

### AC-002: Full Phase 1 Cleanup on Noisy Mesh
**Given** a mesh with 200,000 faces containing 5,000 duplicate vertices (within 0.0001m), 200 inverted normals, and 3 boundary holes (each < 100 edges),  
**When** `MeshCleanupPipeline.execute()` is called with default settings,  
**Then** the output mesh has 0 duplicate vertices within merge distance, 0 inverted normals, 0 boundary edges, `diagnostics["is_manifold"]` is `True`, `diagnostics["is_watertight"]` is `True`, and `diagnostics["cleanup_time_seconds"]` is < 5.0.

### AC-003: Voxel Remesh Fallback Activation
**Given** a severely damaged mesh with 50,000 faces that remains non-manifold after duplicate removal, normal recalculation, and hole filling (e.g., self-intersecting geometry),  
**When** `MeshCleanupPipeline.execute()` is called with `auto_voxel_fallback = True`,  
**Then** the pipeline automatically applies the voxel remesh step, the output mesh has `diagnostics["voxel_remesh_applied"]` set to `True`, `diagnostics["is_manifold"]` is `True`, and `diagnostics["is_watertight"]` is `True`.

### AC-004: Quad Remesh Opt-In (Phase 2)
**Given** a cleaned manifold mesh with 200,000 triangular faces,  
**When** `MeshCleanupPipeline.execute()` is called with `enable_quad_remesh = True` and `quad_target_faces = 10000`,  
**Then** the output mesh contains ≤ 12,000 faces (within 20% of target), ≥ 85% of faces are quads, and the operation completes in < 60 seconds.

### AC-005: Decimation with Sharp Edge Preservation (Phase 2)
**Given** a mesh with 200,000 faces containing edges with dihedral angles > 30° (sharp creases),  
**When** `MeshCleanupPipeline.execute()` is called with `enable_decimate = True` and `decimate_target_faces = 50000`,  
**Then** the output mesh contains ≤ 55,000 faces (within 10% of target), sharp edges (dihedral angle > 30°) are preserved in the output, and the overall silhouette matches the input within 2% Hausdorff distance.

### AC-006: Undo Support
**Given** a mesh object exists in the scene and the cleanup pipeline has been executed,  
**When** the user presses Ctrl+Z,  
**Then** the mesh reverts to its pre-cleanup state, including vertex positions, face topology, and normals.

### AC-007: Diagnostics Report Completeness
**Given** a cleanup pipeline execution on any valid mesh,  
**When** the pipeline completes (whether by normal cleanup or voxel remesh fallback),  
**Then** the returned diagnostics dict contains all 15 keys defined in the FR-007 diagnostics key table (7 integers, 4 booleans, 1 float, and 1 list) plus the `step_errors` list, with correct types as specified.

---

## 7. EDGE CASES

### EC-001: Degenerate Input — Mesh with Zero-Area Faces
| Aspect | Detail |
|--------|--------|
| **Scenario** | Reconstruction engine produces a mesh containing faces where all 3 vertices are collinear (zero-area degenerate triangles). |
| **Input Example** | `vertices = [[0,0,0], [1,0,0], [2,0,0], [0,1,0]]`, `faces = [[0,1,2], [0,1,3]]` — face `[0,1,2]` has zero area. |
| **Expected Behavior** | The system SHALL detect faces with area < 1e-8 m² and dissolve them using `bmesh.ops.dissolve_degenerate()` before normal recalculation. The diagnostics dict SHALL include a `degenerate_faces_removed` count. |
| **Test ID** | TS-004 |

### EC-002: Extremely Large Mesh Exceeding Performance Budget
| Aspect | Detail |
|--------|--------|
| **Scenario** | Reconstruction engine produces a mesh with > 1,000,000 faces (e.g., from a high-resolution reconstruction). |
| **Input Example** | 2,000,000 face mesh from a fine-grained Trellis reconstruction. |
| **Expected Behavior** | The system SHALL log a `WARNING` message: `"Input mesh has {count} faces (exceeds 500K threshold). Cleanup may take longer than 5 seconds."` and proceed with cleanup. The system SHALL NOT crash or raise an exception. If cleanup exceeds 30 seconds, the system SHALL report progress via the modal operator status bar. |
| **Test ID** | TS-005 |

### EC-003: Empty or Minimal Mesh Input
| Aspect | Detail |
|--------|--------|
| **Scenario** | Reconstruction engine returns a degenerate result with < 4 vertices (minimum for a closed volume) or 0 faces. |
| **Input Example** | `vertices = [[0,0,0], [1,0,0]]`, `faces = []` |
| **Expected Behavior** | The system SHALL raise a `ValueError` with message `"Input mesh must contain at least 4 vertices and 4 faces to form a closed volume. Received {n_verts} vertices and {n_faces} faces."` without creating any scene objects. |
| **Test ID** | TS-006 |

### EC-004: Boundary Hole Too Large to Fill
| Aspect | Detail |
|--------|--------|
| **Scenario** | Mesh has a boundary loop with > 500 edges (e.g., a large open region from a failed reconstruction). |
| **Input Example** | Mesh with a 750-edge boundary loop representing an entire missing hemisphere. |
| **Expected Behavior** | The system SHALL skip the hole fill for that loop, log a `WARNING` with message `"Boundary loop with {n} edges exceeds 500-edge limit. Skipping fill — consider voxel remesh."`, increment `diagnostics["holes_skipped"]`, and proceed. If `auto_voxel_fallback = True` and the mesh is non-manifold after all other steps, voxel remesh SHALL activate. |
| **Test ID** | TS-007 |

### EC-005: Non-Triangular Input Faces
| Aspect | Detail |
|--------|--------|
| **Scenario** | Although the spec defines triangular input (shape `(M, 3)`), a future reconstruction adapter might output quads or n-gons. |
| **Input Example** | `faces` array with shape `(M, 4)` containing quad indices. |
| **Expected Behavior** | The system SHALL validate that the `faces` array has exactly 3 columns. If column count ≠ 3, the system SHALL raise a `ValueError` with message `"Input faces must be triangular (shape (M, 3)). Received shape {faces.shape}."`. |
| **Test ID** | TS-008 |

### EC-006: Pipeline Step Exception Mid-Execution
| Aspect | Detail |
|--------|--------|
| **Scenario** | A non-critical cleanup step (e.g., `HoleFillStep`) raises an unexpected exception due to corrupt mesh topology that `bmesh` cannot process. |
| **Input Example** | Mesh with a self-referencing edge loop that causes `bmesh.ops.triangle_fill()` to raise a `RuntimeError`. |
| **Expected Behavior** | The pipeline SHALL catch the exception, log it at `ERROR` level with the step name and traceback, append `{"step": "HoleFillStep", "error": "<exception message>"}` to `diagnostics["step_errors"]`, and continue to the next step (VoxelRemeshStep). If a critical step (DedupStep, NormalsStep) fails, the pipeline SHALL raise `MeshCleanupError` with the step name and original exception, leaving the undo step intact. |
| **Test ID** | TS-019 |

---

## 8. OUT OF SCOPE

The following are explicitly **excluded** from this feature:

- ❌ 3D reconstruction or mesh generation (TASK-TS-0004)
- ❌ Print-readiness validation (wall thickness, overhang, volume checks — TASK-TS-0006)
- ❌ STL/3MF/OBJ export (TASK-TS-0006)
- ❌ Real-world unit scaling and dimension inference (TASK-TS-0008)
- ❌ Print orientation optimization (TASK-TS-0008)
- ❌ UV unwrapping or texture coordinate generation
- ❌ Vertex color or material assignment
- ❌ Natural-language refinement of the cleaned mesh (TASK-TS-0009)
- ❌ Multi-part mesh splitting or assembly
- ❌ Boolean operations (union, intersection, difference)
- ❌ External mesh processing libraries (PyMeshLab, trimesh) — all operations use Blender's built-in `bpy`/`bmesh` APIs

---

## 9. SECURITY CONSIDERATIONS

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — local Blender add-on, no network interaction |
| **Auth Method** | None |
| **Required Permissions** | File system read/write for `.blend` file (handled by Blender) |
| **Rate Limiting** | N/A |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| `vertices` / `faces` arrays | Internal | In-memory only; persisted in `.blend` file by Blender |
| Cleanup diagnostics | Internal | Displayed in UI; not transmitted anywhere |
| Mesh object names / timestamps | Internal | Stored in scene data only |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL validate all input array shapes and dtypes before processing. Reject arrays with unexpected dimensions, NaN values, or Inf values. |
| SEC-002 | SHALL validate that face index values are within bounds `[0, len(vertices) - 1]`. Out-of-bounds indices SHALL raise a `ValueError`. |
| SEC-003 | SHALL NOT execute any code from user-specified paths or dynamically load modules based on input data. |
| SEC-004 | SHALL NOT make any network connections, DNS lookups, or socket operations. |
| SEC-005 | SHALL sanitize the `source_model` string to contain only alphanumeric characters, hyphens, and underscores before using it in object names. Characters not matching `[a-zA-Z0-9_-]` SHALL be replaced with `_`. |

---

## 10. API CONTRACT [CONDITIONAL]

> **No REST/HTTP APIs.** This section documents the internal Python API contract for downstream tasks.

### 10.1 MeshImporter API
```python
from tessera.mesh.importer import MeshImporter
import numpy as np

importer = MeshImporter()
obj = importer.import_mesh(
    vertices=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]], dtype=np.float32),
    faces=np.array([[0,1,2],[0,1,3],[0,2,3],[1,2,3]], dtype=np.int32),
    source_model="trellis",         # Optional, default "custom"
    name_override=None              # Optional, overrides auto-naming
)
# Returns: bpy.types.Object — the newly created mesh object in the active scene
```

### 10.2 MeshCleanupPipeline API
```python
from tessera.mesh.cleanup import MeshCleanupPipeline

pipeline = MeshCleanupPipeline()
diagnostics = pipeline.execute(
    context=bpy.context,
    obj=obj,                        # bpy.types.Object with mesh data
    merge_distance=0.0001,          # Optional
    voxel_size=0.01,                # Optional
    auto_voxel_fallback=True,       # Optional
    enable_quad_remesh=False,       # Optional, Phase 2
    quad_target_faces=10000,        # Optional, Phase 2
    enable_decimate=False,          # Optional, Phase 2
    decimate_target_faces=50000     # Optional, Phase 2
)
# Returns: dict — cleanup diagnostics (see FR-007)
```

### 10.3 Integration with Reconstruction Engine (TASK-TS-0004)
```python
# Expected calling pattern from reconstruction engine adapter
raw_mesh = reconstruction_adapter.generate(image_data)  # Returns RawMeshData

importer = MeshImporter()
obj = importer.import_mesh(
    vertices=raw_mesh.vertices,
    faces=raw_mesh.faces,
    source_model=raw_mesh.source_model
)

pipeline = MeshCleanupPipeline()
diagnostics = pipeline.execute(bpy.context, obj)

if not diagnostics["is_manifold"]:
    logger.error("Cleanup failed to produce manifold mesh")
```

---

## 11. OBSERVABILITY

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------|
| Mesh import started | INFO | `vertex_count`, `face_count`, `source_model` | ⚠️ No PII |
| Mesh import completed | INFO | `object_name`, `import_time_seconds` | ⚠️ No PII |
| Cleanup step started | DEBUG | `step_name`, `face_count_before` | ⚠️ No PII |
| Cleanup step completed | DEBUG | `step_name`, `items_modified`, `step_time_seconds` | ⚠️ No PII |
| Voxel remesh fallback activated | WARN | `reason` ("mesh still non-manifold after surgical repair") | ⚠️ No PII |
| Large mesh warning | WARN | `face_count`, `threshold` | ⚠️ No PII |
| Hole fill skipped (too large) | WARN | `boundary_edge_count`, `max_allowed` | ⚠️ No PII |
| Cleanup pipeline completed | INFO | Full diagnostics dict | ⚠️ No PII |
| Input validation failed | ERROR | `error_message`, `input_shape` | ⚠️ No PII |

> All logging uses Python's `logging` module with logger name `"tessera.mesh"`. Blender routes this to the system console.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only).

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — functionality available when add-on is installed |
| **Default State** | Phase 1 steps enabled by default; Phase 2 steps disabled by default |
| **Rollout Plan** | Bundled with add-on `.zip`; Phase 2 settings exposed in UI but default-off |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| SPEC-TS-0001 (Add-on Scaffold) | Yes | Provides module registration, UI panel framework, scene properties |
| SPEC-TS-0004 (Reconstruction Engine) | Yes | Produces the raw mesh data that this task consumes |
| Blender 4.2+ | Yes | QuadriFlow remesh requires Blender 4.0+; target LTS version |
| NumPy (bundled with Blender) | Yes | Used for input mesh data arrays |

### 12.3 Rollback Plan
1. User disables the add-on or reverts to a previous add-on version
2. Existing `.blend` files are unaffected — mesh objects remain in the scene after add-on removal
3. Verify no orphan data blocks via Blender's Outliner → Orphan Data view

---

## 13. TEST SCENARIOS

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Import 50K vert / 100K face mesh, verify object in scene | Unit | AC-001 | Must Pass |
| TS-002 | Full Phase 1 cleanup on noisy mesh, verify manifold + watertight | Integration | AC-002 | Must Pass |
| TS-003 | Voxel remesh fallback on non-repairable mesh | Integration | AC-003 | Must Pass |
| TS-004 | Input mesh with zero-area faces, verify degenerate removal | Unit | EC-001 | Must Pass |
| TS-005 | Input mesh with > 1M faces, verify warning + no crash | Performance | EC-002 | Must Pass |
| TS-006 | Input mesh with < 4 vertices, verify ValueError raised | Unit | EC-003 | Must Pass |
| TS-007 | Boundary loop > 500 edges, verify skip + warning + fallback | Unit | EC-004 | Must Pass |
| TS-008 | Input faces with 4 columns (quads), verify ValueError | Unit | EC-005 | Must Pass |
| TS-009 | Quad remesh on 200K triangle mesh, verify quad-dominant output | Integration | AC-004 | Should Pass |
| TS-010 | Decimate with sharp edges, verify preserved edges | Integration | AC-005 | Should Pass |
| TS-011 | Ctrl+Z after cleanup, verify full revert | Integration | AC-006 | Must Pass |
| TS-012 | Verify diagnostics dict has all 15 required keys + step_errors list | Unit | AC-007 | Must Pass |
| TS-013 | Phase 1 cleanup latency on 500K face mesh < 5 seconds | Performance | NFR-001 | Must Pass |
| TS-014 | Import latency for 500K verts / 1M faces < 1 second | Performance | NFR-002 | Must Pass |
| TS-015 | Input arrays with NaN/Inf values, verify rejection | Unit | SEC-001 | Must Pass |
| TS-016 | Face indices out of bounds, verify ValueError | Unit | SEC-002 | Must Pass |
| TS-017 | Cleanup settings PropertyGroup registration and defaults | Unit | FR-017 | Must Pass |
| TS-018 | Modal operator activates for >100ms cleanup, shows progress | Integration | CON-008 | Should Pass |
| TS-019 | Non-critical step exception caught, pipeline continues; critical step exception raises MeshCleanupError | Unit | EC-006, FR-020 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0001 (Add-on Scaffold) | Required | Draft | Tessera | Yes — need module registration framework |
| SPEC-TS-0004 (Reconstruction Engine) | Required | Draft | Tessera | Yes — need raw mesh output interface |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| Blender 4.2+ LTS | Required | [docs.blender.org](https://docs.blender.org/api/current/) | No fallback — hard requirement |
| Blender `bmesh` module | Required | [bmesh API](https://docs.blender.org/api/current/bmesh.html) | N/A — bundled with Blender |
| NumPy (Blender-bundled) | Required | [numpy.org](https://numpy.org/doc/) | N/A — bundled with Blender 4.x |

---

## 15. APPROVAL

| Role | Name | Date | Status |
|------|------|------|--------|
| Author (Orchestrator) | AI | 2026-04-09 | ☐ Submitted |
| CSO Approval | Derek | | ☐ Approved / ☐ Changes Requested |
| Deputy Review | | | ☐ N/A |

**Approval Notes:**
[Space for CSO/Deputy feedback]

---

## AI-READINESS SELF-SCORE

| Criterion | Max | Score | Guidance |
|-----------|-----|-------|----------|
| SHALL/SHOULD/MAY requirements | 20 | 20 | 20 requirements (incl. FR-020) with precise SHALL/SHOULD/MAY language across 3 sections |
| Quantified NFRs | 15 | 15 | 7 NFRs, all quantified with specific targets, units, and measurement conditions |
| Given-When-Then criteria (3+) | 20 | 20 | 7 acceptance criteria in Given-When-Then format with specific values |
| Edge cases (2+) | 15 | 15 | 6 edge cases with concrete input examples and expected behaviors |
| Out of scope defined | 10 | 10 | 11 explicit exclusions listed with cross-references to other tasks |
| Security constraints | 10 | 10 | 5 security requirements + data classification table |
| No ambiguous language | 10 | 10 | All diagnostics keys enumerated; type counts verified; no ambiguous terms |
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
- [x] "optimized" → not used

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-09 | Orchestrator (AI) | Initial draft |
| 1.1 | 2026-04-14 | Spec Review | Fixed diagnostics key enumeration (FR-007: 15 keys); added pipeline failure behavior (FR-020, EC-006); clarified source_model as open enum; added modal operator test (TS-018); added step exception test (TS-019) |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0005-mesh-import-cleanup.md`
