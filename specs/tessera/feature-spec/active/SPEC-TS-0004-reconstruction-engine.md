# Feature Specification: Single-Image 3D Reconstruction Engine

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0004 |
| **Task ID** | TASK-TS-0004 |
| **Status** | Reopened |
| **Version** | 1.2 |
| **Created** | 2026-04-09 |
| **Last Updated** | 2026-09-22 |
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
Tessera's core value proposition is turning 2D images into 3D-printable models. The reconstruction engine is the centerpiece of this pipeline — it takes structured vision data (segmentation masks, depth maps, view labels) from the vision pipeline (TASK-TS-0003) and produces a 3D mesh. Without this component, Tessera is an empty shell with no AI capability. This task is on the critical path for Phase 1 (M1.4) and produces the raw mesh that all downstream tasks (mesh cleanup, print validation, export) consume.

The reconstruction engine must be **model-agnostic** per PRD §5.2, implementing a pluggable adapter pattern so that 3D reconstruction models — which evolve rapidly — can be swapped or upgraded without changing the rest of the system. The initial implementation integrates one primary backend (Trellis, InstantMesh, or OpenLRM) with the architecture designed for future expansion.

### 1.2 User Story
**As a** user who uploaded a photo of an object,  
**I want** the agent to generate a 3D mesh that looks like the object in my photo,  
**So that** I can get a starting point for a 3D-printable model without any modeling skills.

### 1.3 Proposed Approach
Implement a model-agnostic adapter layer with an abstract base class (`ReconstructionAdapter`) defining a `reconstruct()` method. Build one concrete adapter for the primary reconstruction model (selected from Trellis, InstantMesh, or OpenLRM based on spike results). The adapter normalizes all model-specific outputs (NeRF volumes, implicit surfaces, point clouds) to a standard mesh representation (vertices, faces, optional vertex colors). The engine exposes two entry paths: single-image (1 image + mask + depth) and few-image (2 images with view labels) reconstruction. All inference runs locally on the user's GPU using pre-cached model weights from TASK-TS-0002.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Single-image reconstruction success rate | N/A | ≥ 90% recognizable meshes on simple objects | Visual evaluation on 20-object test set (mugs, vases, figurines) |
| Reconstruction latency (single image) | N/A | < 60 seconds on RTX 3060 | Wall-clock time from `reconstruct()` call to mesh return |
| Adapter swap time | N/A | < 1 hour developer effort to add a new backend | Measured by implementing a second adapter |

---

## 2. TECHNICAL CONTEXT

> ⚠️ **AI needs this context BEFORE generating code.** Provide patterns and references here.

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/gpu_detection.py` | GPU detection and VRAM reporting (SPEC-TS-0001) | GPU capability checks before running inference |
| `tessera/preferences.py` | Add-on preferences with cache directory (SPEC-TS-0001) | Locating model weight files on disk |
| TASK-TS-0003 vision pipeline output | `{image, mask, depth_map, view_label, features}` per image | Input format this engine consumes |
| [Trellis](https://github.com/microsoft/TRELLIS) | Microsoft's image-to-3D model | Primary adapter candidate — mesh extraction from structured latent triplane |
| [InstantMesh](https://github.com/TencentARC/InstantMesh) | Tencent's single-image 3D reconstruction | Alternative adapter — multi-view generation + reconstruction |
| [OpenLRM](https://github.com/3DTopia/OpenLRM) | Open-source large reconstruction model | Alternative adapter — direct triplane prediction |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`) + PyTorch (for model inference)
- **Inference:** PyTorch with CUDA / ROCm backend
- **Mesh Processing:** `trimesh` for intermediate mesh handling, `numpy` for vertex/face arrays
- **Validation:** Runtime assertions + type checking via `dataclasses` / `typing`
- **Testing:** `pytest` run via `blender --background --python` for headless testing
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── reconstruction/
│   ├── __init__.py
│   ├── adapter.py              # ReconstructionAdapter ABC + ReconstructionResult dataclass
│   ├── registry.py             # AdapterRegistry — discovers, registers, selects adapters
│   ├── mesh_output.py          # StandardMesh dataclass + normalization utilities
│   ├── engine.py               # ReconstructionEngine — orchestrates adapter selection + execution
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── trellis_adapter.py  # Trellis backend (or primary model)
│   │   └── stub_adapter.py     # Test/development stub adapter
│   └── utils/
│       ├── __init__.py
│       ├── vram_guard.py       # VRAM availability check before inference
│       └── mesh_conversion.py  # NeRF→mesh, point cloud→mesh, implicit→mesh converters
```

**Data flow:**

```
VisionPipelineOutput (per image) — type alias for VisionResult from SPEC-TS-0003
  ├── image: np.ndarray (H×W×3, uint8)
  ├── mask: np.ndarray (H×W, uint8, values 0 or 255)
  ├── depth_map: np.ndarray (H×W, float32, range [0.0, 1.0])
  ├── view_label: str
  ├── label_confidence: float ([0.0, 1.0])
  ├── label_source: str ("user" | "auto")
  ├── label_needs_confirmation: bool
  ├── features: np.ndarray (1×D, float32, DINOv2 embeddings)
  ├── original_size: tuple[int, int]
  └── processing_time_s: dict[str, float]
        │
        ▼
ReconstructionEngine.reconstruct(inputs: list[VisionPipelineOutput])
        │
        ├── validate input count (1–2 for this version)
        ├── select adapter (from registry, based on input count + available VRAM)
        ├── validate inputs (masks present, depth maps present)
        ├── check VRAM headroom (VRAMGuard)
        ├── invoke adapter.reconstruct() with timeout
        └── normalize output → StandardMesh
                │
                ▼
StandardMesh
  ├── vertices: np.ndarray (N×3, float32)
  ├── faces: np.ndarray (M×3, int32)
  ├── vertex_colors: np.ndarray | None (N×3, float32, range 0–1)
  └── metadata: dict (model_name, inference_time_s, confidence)
```

The adapter pattern follows the Strategy design pattern:
- `ReconstructionAdapter` is an abstract base class with `reconstruct()` and `capabilities()` methods
- Each model backend implements the adapter interface
- `AdapterRegistry` discovers available adapters and selects the best one based on input type and GPU resources
- `ReconstructionEngine` is the public API — callers never interact with individual adapters directly

**Adapter selection algorithm** (executed by `AdapterRegistry.select()`):

1. **Filter by input compatibility:** Keep adapters where `capabilities.min_images ≤ len(inputs) ≤ capabilities.max_images`
2. **Filter by weight availability:** Keep adapters whose model weight files exist in the cache directory
3. **Filter by VRAM:** Keep adapters where `capabilities.min_vram_gb ≤ available_vram_gb`
4. **Exclude StubAdapter:** Remove `StubAdapter` from candidates unless no other adapter survives filtering
5. **Rank by capability:** Among remaining adapters, select the one with the highest `min_vram_gb` (prefer more capable models that fit in available VRAM)
6. **Fallback:** If no adapter survives steps 1–3, fall back to `StubAdapter` if available; otherwise return `None` (engine returns `ReconstructionResult(success=False)`)

---

## 3. FUNCTIONAL REQUIREMENTS

> ⚠️ **Use precise language:** SHALL (required), SHALL NOT (prohibited), SHOULD (recommended), SHOULD NOT (discouraged), MAY (optional). The keyword IS the priority.

### 3.1 Core Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL define an abstract base class `ReconstructionAdapter` with the following abstract methods: `reconstruct(inputs: list[VisionPipelineOutput]) → ReconstructionResult` and `capabilities() → AdapterCapabilities`. |
| FR-002 | The system SHALL define a `StandardMesh` dataclass containing: `vertices` (N×3 float32 ndarray), `faces` (M×3 int32 ndarray), `vertex_colors` (optional N×3 float32 ndarray, range 0.0–1.0), and `metadata` (dict with keys: `model_name`, `inference_time_s`, `confidence`). |
| FR-003 | The system SHALL define a `ReconstructionResult` dataclass containing: `mesh` (StandardMesh), `success` (bool), `error_message` (str, empty on success), and `warnings` (list[str]). |
| FR-004 | The system SHALL implement one concrete adapter for the primary reconstruction model (Trellis, InstantMesh, or OpenLRM — selected after spike evaluation). |
| FR-005 | The system SHALL implement a `StubAdapter` that returns a unit cube mesh for testing and development purposes, without requiring GPU or model weights. |
| FR-006 | The system SHALL implement an `AdapterRegistry` that discovers available adapters, checks their `capabilities()`, and selects the best adapter for a given set of inputs. |
| FR-007 | The system SHALL support a **single-image reconstruction path**: given 1 image + 1 segmentation mask + 1 depth map, the adapter SHALL produce a 3D mesh that passes the degenerate-mesh check (≥ 4 vertices, ≥ 4 faces per FR-011) and achieves a confidence score ≥ 0.3. |
| FR-008 | The system SHALL support a **few-image reconstruction path**: given 2 images with view labels + corresponding masks and depth maps, the adapter SHALL produce a reconstruction that incorporates information from both views. |
| FR-009 | The system SHALL apply the segmentation mask to zero out background pixels before passing the image to the reconstruction model. |
| FR-010 | The system SHALL normalize all adapter outputs to the `StandardMesh` format, converting model-specific representations (NeRF volumes, implicit surfaces, point clouds, raw triangles) to vertices + faces. |
| FR-011 | The system SHALL validate the output mesh contains ≥ 4 vertices and ≥ 4 faces. If the output is degenerate, the system SHALL return `ReconstructionResult(success=False, error_message="Reconstruction produced degenerate mesh with fewer than 4 vertices or 4 faces.")`. |
| FR-012 | The system SHALL check available GPU VRAM before invoking reconstruction. If available VRAM is below the adapter's declared minimum requirement, the system SHALL return `ReconstructionResult(success=False, error_message="Insufficient GPU VRAM. Required: {required_gb} GB, Available: {available_gb} GB. Close other GPU applications or select a lighter model.")`. |
| FR-013 | The system SHALL load model weights from the local cache directory configured in add-on preferences (SPEC-TS-0001, FR-007). The system SHALL NOT download model weights at runtime. |
| FR-014 | The system SHALL verify model weight files exist and match expected checksums before loading. If weights are missing, the system SHALL return `ReconstructionResult(success=False, error_message="Model weights not found for {model_name}. Run weight download from Add-on Preferences → Tessera → Download Models.")`. |
| FR-015 | The system SHALL release all GPU tensors and clear the CUDA/ROCm cache after reconstruction completes (both success and failure) to prevent VRAM leaks. |
| FR-016 | The system SHOULD provide a `confidence` field (float, 0.0–1.0) in the mesh metadata estimating reconstruction quality based on adapter-specific heuristics. |
| FR-017 | The system SHOULD log a warning when `confidence` < 0.5, including the message: "Low reconstruction confidence ({confidence:.2f}). Consider adding more reference images or trying a different angle." |
| FR-018 | The system SHALL include the adapter name and inference time in the `StandardMesh.metadata` dictionary. |
| FR-019 | The system MAY support batch reconstruction of multiple objects in a future version, but this spec covers single-object reconstruction only. |
| FR-020 | The system SHALL expose a public `ReconstructionEngine` class that accepts `list[VisionPipelineOutput]` and returns `ReconstructionResult`, encapsulating all adapter selection and execution logic. |
| FR-021 | The system SHALL validate that `len(inputs)` is between 1 and 2 (inclusive). If `len(inputs) == 0`, the system SHALL return `ReconstructionResult(success=False, error_message="No input images provided. At least 1 VisionPipelineOutput is required.")`. If `len(inputs) > 2`, the system SHALL return `ReconstructionResult(success=False, error_message="This version supports 1–2 input images. Received {n}. Multi-view reconstruction (≥3 images) is planned for TASK-TS-0007.")`. |
| FR-022 | The system SHOULD enforce a configurable timeout (default: 120 seconds) on adapter `reconstruct()` invocations. If the timeout is exceeded, the system SHALL terminate inference, clean up GPU resources per FR-015, and return `ReconstructionResult(success=False, error_message="Reconstruction timed out after {timeout_s} seconds. Consider using a lighter model or reducing input resolution.")`. |

### 3.2 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| `inputs` | `list[VisionPipelineOutput]` | Length 1–2 (this spec); each element valid | Yes | See dataclass below |
| `inputs[*].image` | `np.ndarray` | Shape (H, W, 3), dtype uint8, RGB, H ≥ 64, W ≥ 64 | Yes | 512×512×3 photo crop |
| `inputs[*].mask` | `np.ndarray` | Shape (H, W), dtype uint8, values 0 or 255, same H×W as image | Yes | Binary foreground mask (0=background, 255=foreground) |
| `inputs[*].depth_map` | `np.ndarray` | Shape (H, W), dtype float32, values in [0.0, 1.0], same H×W as image | Yes | Monocular depth estimation output |
| `inputs[*].view_label` | `str` | One of: `front`, `back`, `left`, `right`, `top`, `bottom`, `front-left`, `front-right`, `isometric`, `custom:<az>,<el>`, `unlabeled` | Yes (default: `unlabeled`) | `"front"` |
| `inputs[*].label_confidence` | `float` | Range [0.0, 1.0] | Yes | `0.92` |
| `inputs[*].label_source` | `str` | `"user"` or `"auto"` | Yes | `"user"` |
| `inputs[*].label_needs_confirmation` | `bool` | — | Yes | `False` |
| `inputs[*].features` | `np.ndarray` | Shape (1, D), dtype float32, D = feature dimension (e.g., 768 for DINOv2-base) | Yes | DINOv2 embedding vector |
| `inputs[*].original_size` | `tuple[int, int]` | (width, height) in pixels | Yes | `(3024, 4032)` |
| `inputs[*].processing_time_s` | `dict[str, float]` | Stage name → seconds | Yes | `{"segmentation": 1.2}` |

> **Note:** `VisionPipelineOutput` is a **type alias** for `VisionResult` defined in SPEC-TS-0003 (`tessera.vision.types`). This spec re-exports it for clarity but the canonical definition lives in the vision pipeline module.

```python
# Type Definitions (for AI reference)
from dataclasses import dataclass, field
import numpy as np

# VisionPipelineOutput is a type alias for VisionResult from SPEC-TS-0003.
# Import from the canonical location:
from tessera.vision.types import VisionResult as VisionPipelineOutput

# Canonical definition (owned by SPEC-TS-0003, reproduced here for reference):
# @dataclass
# class VisionResult:
#     image: np.ndarray                    # (H, W, 3) uint8 RGB
#     mask: np.ndarray                     # (H, W) uint8, 0/255
#     depth_map: np.ndarray                # (H, W) float32, [0.0, 1.0]
#     view_label: str                      # View direction label
#     label_confidence: float              # [0.0, 1.0]
#     label_source: str                    # "user" | "auto"
#     label_needs_confirmation: bool       # True if auto + conf < 0.80
#     features: np.ndarray                 # (1, D) float32
#     original_size: tuple[int, int]       # (width, height)
#     processing_time_s: dict[str, float]  # Stage name → seconds

@dataclass
class AdapterCapabilities:
    """Declares what an adapter supports."""
    model_name: str                      # e.g. "trellis-v1.0"
    min_images: int                      # Minimum input images (1)
    max_images: int                      # Maximum input images
    requires_depth: bool                 # Whether depth maps are used
    requires_mask: bool                  # Whether masks are required
    min_vram_gb: float                   # Minimum GPU VRAM in GB
    supported_view_labels: list[str]     # View labels this adapter uses
    output_types: list[str]             # e.g. ["mesh", "point_cloud", "nerf"]
```

### 3.3 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `result.success` | `bool` | True if reconstruction succeeded | `True` |
| `result.mesh` | `StandardMesh` | Normalized mesh data | See dataclass below |
| `result.mesh.vertices` | `np.ndarray` | (N, 3) float32 | 10000×3 array |
| `result.mesh.faces` | `np.ndarray` | (M, 3) int32, zero-indexed | 20000×3 array |
| `result.mesh.vertex_colors` | `np.ndarray \| None` | (N, 3) float32, range 0.0–1.0 | RGB per vertex |
| `result.mesh.metadata` | `dict` | See keys below | `{"model_name": "trellis-v1.0", ...}` |
| `result.error_message` | `str` | Empty on success; actionable message on failure | `""` |
| `result.warnings` | `list[str]` | Non-fatal issues encountered | `["Low confidence: 0.42"]` |

```python
# Type Definitions (for AI reference)
@dataclass
class StandardMesh:
    """Normalized mesh output from any reconstruction adapter."""
    vertices: np.ndarray          # (N, 3) float32
    faces: np.ndarray             # (M, 3) int32, zero-indexed
    vertex_colors: np.ndarray | None = None  # (N, 3) float32, 0.0–1.0
    metadata: dict = field(default_factory=lambda: {
        "model_name": "",
        "inference_time_s": 0.0,
        "confidence": 0.0,
        "vertex_count": 0,
        "face_count": 0,
    })

@dataclass
class ReconstructionResult:
    """Result returned by the reconstruction engine."""
    mesh: StandardMesh | None     # None on failure
    success: bool
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)
    source_adapter: str = ""
```

**Metadata keys:**

| Key | Type | Description |
|-----|------|-------------|
| `model_name` | `str` | Name and version of the reconstruction model (e.g., `"trellis-v1.0"`) |
| `inference_time_s` | `float` | Wall-clock inference time in seconds |
| `confidence` | `float` | Quality score 0.0–1.0 (adapter-specific heuristic) |
| `vertex_count` | `int` | Number of vertices in the output mesh |
| `face_count` | `int` | Number of triangular faces in the output mesh |

---

## 4. CONSTRAINTS

> ⚠️ **Critical for AI code generation.** These are hard prohibitions the AI must follow.

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT make any network calls. All model weights SHALL be loaded from the local filesystem only. |
| CON-002 | SHALL NOT hard-couple to any specific reconstruction model. All model interaction SHALL go through the `ReconstructionAdapter` interface. |
| CON-003 | SHALL NOT allocate GPU memory that persists after `reconstruct()` returns. All CUDA/ROCm tensors SHALL be explicitly freed and cache cleared via `torch.cuda.empty_cache()`. |
| CON-004 | SHALL NOT execute reconstruction if the VRAM check fails. The system SHALL fail fast with a clear error message before loading model weights. |
| CON-005 | SHALL NOT hardcode file paths or model weight locations. All paths SHALL be resolved relative to the add-on preferences cache directory. |
| CON-006 | SHALL NOT modify or depend on Blender scene state (`bpy.context`, `bpy.data`). The reconstruction engine operates on raw numpy arrays and returns a `StandardMesh`. Blender integration is the responsibility of downstream tasks (TASK-TS-0005). |
| CON-007 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. |
| CON-008 | SHALL NOT invoke inference by shelling out to an arbitrary binary or constructing a command line. Inference SHALL run either in-process, or in the sanctioned local engine process over its defined local API (ADR-0001, SPEC-TS-0023). No other out-of-process mechanism is permitted. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

> ⚠️ **All NFRs must be quantified.** Replace vague terms with specific numbers.

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Single-image reconstruction latency | Wall-clock time from `reconstruct()` call to `ReconstructionResult` return | < 60 seconds | RTX 3060 (12 GB VRAM), single 512×512 input image, model weights pre-loaded in first call |
| NFR-002 | Few-image reconstruction latency | Wall-clock time for 2-image reconstruction | < 90 seconds | RTX 3060 (12 GB VRAM), two 512×512 input images with view labels |
| NFR-003 | Peak VRAM usage during inference | Maximum GPU memory allocated at any point during reconstruction | < 10 GB | Single-image path on RTX 3060 |
| NFR-004 | VRAM cleanup after inference | GPU memory delta before and after `reconstruct()` | < 50 MB residual | After `torch.cuda.empty_cache()` |
| NFR-005 | Model weight loading time | Time to load model weights from disk to GPU on first inference call | < 15 seconds | Model weights on SSD, cold start |
| NFR-006 | Output mesh quality — vertex count | Number of vertices in output mesh for standard objects | 5,000–200,000 vertices | Single mug/vase/figurine input |
| NFR-007 | Adapter registration time | Time for `AdapterRegistry` to discover and register all available adapters | < 100ms | On module import |
| NFR-008 | Input validation time | Time to validate input array shapes, dtypes, and constraints | < 10ms | For 2-image input set |

---

## 6. ACCEPTANCE CRITERIA

> ⚠️ **Minimum 3 criteria in Given-When-Then format.** These drive test implementation.

### AC-001: Single-Image Reconstruction — Happy Path
**Given** a single `VisionPipelineOutput` containing a 512×512 RGB image of a ceramic mug, a binary foreground mask with the mug segmented, a float32 depth map, and view label `"front"`,  
**When** `ReconstructionEngine.reconstruct([input])` is called with the primary adapter available and model weights cached locally,  
**Then** the result has `success=True`, `mesh` is a `StandardMesh` with ≥ 1,000 vertices and ≥ 2,000 faces, `metadata["model_name"]` is non-empty, `metadata["inference_time_s"]` is > 0 and < 60, and `error_message` is empty.

### AC-002: Few-Image Reconstruction — Two Views
**Given** two `VisionPipelineOutput` entries: one with view label `"front"` and one with view label `"right"`, each containing a 512×512 RGB image of the same vase, corresponding masks, and depth maps,  
**When** `ReconstructionEngine.reconstruct([input_front, input_right])` is called,  
**Then** the result has `success=True`, the output mesh has ≥ 1,000 vertices, and `metadata["inference_time_s"]` < 90.

### AC-003: Missing Model Weights
**Given** the model cache directory does not contain the weight files for the primary reconstruction model,  
**When** `ReconstructionEngine.reconstruct([valid_input])` is called,  
**Then** the result has `success=False`, `mesh` is `None`, and `error_message` contains "Model weights not found for" and "Run weight download from Add-on Preferences".

### AC-004: Insufficient VRAM
**Given** the system has a GPU with 2 GB available VRAM and the primary adapter requires 6 GB minimum,  
**When** `ReconstructionEngine.reconstruct([valid_input])` is called,  
**Then** the result has `success=False`, `mesh` is `None`, and `error_message` contains "Insufficient GPU VRAM" with the required and available amounts.

### AC-005: Adapter Registry Fallback
**Given** the `AdapterRegistry` has two registered adapters — the primary adapter and the `StubAdapter`,  
**When** model weights for the primary adapter are missing but the `StubAdapter` is available,  
**Then** the registry selects the `StubAdapter`, reconstruction succeeds, and `result.source_adapter` equals `"stub"`.

### AC-006: VRAM Cleanup After Reconstruction
**Given** a successful single-image reconstruction completes,  
**When** the result is returned and `reconstruct()` has exited,  
**Then** GPU memory usage is within 50 MB of the pre-reconstruction baseline (measured via `torch.cuda.memory_allocated()`).

### AC-007: Degenerate Output Handling
**Given** the reconstruction model produces an output with fewer than 4 vertices (e.g., due to a very dark or featureless input image),  
**When** the output normalization step processes the result,  
**Then** the result has `success=False` and `error_message` contains "Reconstruction produced degenerate mesh".

---

## 7. EDGE CASES

> ⚠️ **Minimum 2 edge cases required.** Document non-obvious scenarios AI might miss.

### EC-001: Very Small Input Image
| Aspect | Detail |
|--------|--------|
| **Scenario** | User provides an image that is exactly at the minimum resolution boundary (64×64 pixels) |
| **Input Example** | `VisionPipelineOutput(image=np.zeros((64, 64, 3), dtype=np.uint8), mask=np.full((64, 64), 255, dtype=np.uint8), depth_map=np.ones((64, 64), dtype=np.float32), view_label="front", ...)` |
| **Expected Behavior** | The system SHALL accept the input and attempt reconstruction. The result SHOULD include a warning: "Input image resolution (64×64) is below recommended minimum (256×256). Reconstruction quality may be reduced." |
| **Test ID** | TS-004 |

### EC-002: Mask Covers Entire Image (No Background)
| Aspect | Detail |
|--------|--------|
| **Scenario** | The segmentation mask is all-255 — the entire image is considered foreground (no background removal) |
| **Input Example** | `mask = np.full((512, 512), 255, dtype=np.uint8)` — every pixel is foreground |
| **Expected Behavior** | The system SHALL proceed with reconstruction using the full image. The result SHOULD include a warning: "Segmentation mask covers 100% of the image. Background may be included in reconstruction." |
| **Test ID** | TS-005 |

### EC-003: Mask Covers No Pixels (Empty Foreground)
| Aspect | Detail |
|--------|--------|
| **Scenario** | The segmentation mask is all-0 — no object was detected in the image |
| **Input Example** | `mask = np.zeros((512, 512), dtype=np.uint8)` — every pixel is background |
| **Expected Behavior** | The system SHALL return `ReconstructionResult(success=False, error_message="Segmentation mask is empty — no object detected in image. Verify the reference image contains a visible object.")`. |
| **Test ID** | TS-006 |

### EC-004: Conflicting View Labels in Few-Image Path
| Aspect | Detail |
|--------|--------|
| **Scenario** | User provides two images with the same view label (e.g., both labeled `"front"`) |
| **Input Example** | `[VisionPipelineOutput(view_label="front"), VisionPipelineOutput(view_label="front")]` |
| **Expected Behavior** | The system SHALL proceed with reconstruction but include a warning: "Multiple images share the view label 'front'. Reconstruction quality improves with diverse viewpoints." |
| **Test ID** | TS-007 |

### EC-005: Depth Map Contains NaN or Infinity Values
| Aspect | Detail |
|--------|--------|
| **Scenario** | The monocular depth estimator produces NaN or ±inf values in the depth map |
| **Input Example** | `depth_map` with `depth_map[100, 100] = float('nan')` and `depth_map[200, 200] = float('inf')` |
| **Expected Behavior** | The system SHALL replace NaN and ±inf values with 0.0 before passing the depth map to the adapter. The result SHALL include a warning: "Depth map contained {count} invalid values (NaN/Inf) which were replaced with 0.0." |
| **Test ID** | TS-008 |

### EC-006: Input Count Exceeds Maximum (>2 Images)
| Aspect | Detail |
|--------|--------|
| **Scenario** | Caller passes 3 or more `VisionPipelineOutput` entries to `reconstruct()` |
| **Input Example** | `engine.reconstruct([input_front, input_right, input_back])` — 3 images |
| **Expected Behavior** | The system SHALL return `ReconstructionResult(success=False, error_message="This version supports 1–2 input images. Received 3. Multi-view reconstruction (≥3 images) is planned for TASK-TS-0007.")`. No adapter loading or inference SHALL be attempted. |
| **Test ID** | TS-018 |

---

## 8. OUT OF SCOPE

> ⚠️ **Explicitly list what this feature does NOT include.** Prevents AI scope creep.

The following are explicitly **excluded** from this feature:

- ❌ Multi-view reconstruction with ≥ 3 images (deferred to TASK-TS-0007)
- ❌ Sketch-to-3D pathway (deferred to TASK-TS-0010)
- ❌ Mesh cleanup, topology optimization, or remeshing (TASK-TS-0005)
- ❌ Importing the mesh into Blender scene / `bpy` operations (TASK-TS-0005)
- ❌ Print-readiness validation (TASK-TS-0006)
- ❌ Model weight downloading or caching logic (TASK-TS-0002)
- ❌ Vision pipeline processing (segmentation, depth estimation, view classification) (TASK-TS-0003)
- ❌ Texture mapping, UV unwrapping, or material assignment
- ❌ Real-world scaling or unit conversion (TASK-TS-0008)
- ❌ Natural-language refinement of the generated mesh (TASK-TS-0009)
- ❌ Batch reconstruction of multiple objects from a single scene
- ❌ CPU-only inference fallback (GPU required per PRD decision D2)

---

## 9. SECURITY CONSIDERATIONS

> ⚠️ **Required for all features.** AI-generated code needs explicit security constraints.

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — local Blender add-on, no network interaction |
| **Auth Method** | None |
| **Required Permissions** | File system read (model weights from cache directory) |
| **Rate Limiting** | N/A |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| User's reference images (pixel data) | Internal | Processed in-memory only; not written to disk by this component; not transmitted |
| Model weight files | Internal | Read from local disk only; checksums verified before loading |
| Reconstruction output (mesh data) | Internal | Returned in-memory to caller; not written to disk by this component |
| GPU device info | Internal | Used for VRAM checks; not transmitted |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL validate all input array shapes and dtypes before processing. Invalid shapes SHALL raise `ValueError` with a descriptive message. |
| SEC-002 | SHALL NOT execute any code or load modules from user-specified paths. Model weights SHALL be loaded via PyTorch's `torch.load()` with `weights_only=True` to prevent pickle deserialization attacks. |
| SEC-003 | SHALL NOT make any network connections, DNS lookups, or socket operations. |
| SEC-004 | SHALL verify model weight file checksums (SHA-256) against known-good values before loading. Known-good checksums SHALL be sourced from the model weight manifest maintained by SPEC-TS-0002. Mismatched checksums SHALL abort loading with error: "Model weight checksum mismatch for {filename}. Expected: {expected}, Got: {actual}. Re-download weights from Add-on Preferences." |
| SEC-005 | SHALL NOT log or store raw pixel data from user images. Logging SHALL reference images by index only (e.g., "input[0]"). |

---

## 10. API CONTRACT [CONDITIONAL]

> **Skipped** — This is an internal Python module within the Blender add-on. No REST/HTTP APIs are exposed.

The reconstruction engine exposes the following **internal Python API** for downstream tasks:

### 10.1 Public API — ReconstructionEngine

```python
from tessera.reconstruction.engine import ReconstructionEngine
from tessera.vision.types import VisionResult as VisionPipelineOutput
from tessera.reconstruction.mesh_output import ReconstructionResult

# Initialize engine with cache directory from add-on preferences
engine = ReconstructionEngine(cache_dir="/path/to/model/cache")

# Single-image reconstruction
result: ReconstructionResult = engine.reconstruct([single_input])

# Few-image reconstruction (2 views)
result: ReconstructionResult = engine.reconstruct([front_input, right_input])

# Check result
if result.success:
    mesh = result.mesh
    print(f"Vertices: {mesh.metadata['vertex_count']}")
    print(f"Faces: {mesh.metadata['face_count']}")
    print(f"Time: {mesh.metadata['inference_time_s']:.1f}s")
    print(f"Confidence: {mesh.metadata['confidence']:.2f}")
else:
    print(f"Failed: {result.error_message}")

# List available adapters
adapters = engine.list_adapters()  # Returns list[AdapterCapabilities]
```

### 10.2 Adapter Registration API

```python
from tessera.reconstruction.registry import AdapterRegistry
from tessera.reconstruction.adapter import ReconstructionAdapter

# Register a custom adapter
registry = AdapterRegistry()
registry.register(MyCustomAdapter)

# Query adapters
caps = registry.get_capabilities("my-custom-model")
available = registry.list_available(cache_dir="/path/to/cache")
```

---

## 11. OBSERVABILITY

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------|
| Reconstruction started | INFO | `adapter_name`, `input_count`, `image_resolutions` | ⚠️ No PII — resolutions only, no filenames |
| VRAM check passed | DEBUG | `required_gb`, `available_gb` | ⚠️ No PII |
| VRAM check failed | ERROR | `required_gb`, `available_gb`, `adapter_name` | ⚠️ No PII |
| Model weights loading | INFO | `model_name`, `cache_dir` (basename only) | ⚠️ No full paths |
| Model weights checksum verified | DEBUG | `model_name`, `checksum_status` | ⚠️ No PII |
| Model weights checksum failed | ERROR | `model_name`, `expected_hash`, `actual_hash` | ⚠️ No PII |
| Input validation passed | DEBUG | `input_count`, `shapes` | ⚠️ No PII |
| Input validation failed | ERROR | `reason`, `input_index` | ⚠️ No PII |
| Depth map sanitized (NaN/Inf) | WARN | `input_index`, `invalid_count` | ⚠️ No PII |
| Reconstruction completed | INFO | `adapter_name`, `inference_time_s`, `vertex_count`, `face_count`, `confidence` | ⚠️ No PII |
| Reconstruction failed | ERROR | `adapter_name`, `error_message` | ⚠️ No PII |
| VRAM cleanup completed | DEBUG | `memory_freed_mb` | ⚠️ No PII |
| Low confidence warning | WARN | `confidence`, `adapter_name` | ⚠️ No PII |

> All logging uses Python's `logging` module with logger name `"tessera.reconstruction"`. Blender routes this to the system console.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only). Performance data is captured in `StandardMesh.metadata` for display in the Blender UI.

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — available when add-on is installed and model weights are cached |
| **Default State** | N/A |
| **Rollout Plan** | Part of Tessera add-on `.zip` distribution |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| TASK-TS-0001 (Add-on Scaffold) | Yes | Provides add-on preferences, GPU detection, cache directory configuration |
| TASK-TS-0002 (Model Weight Management) | Yes | Reconstruction model weights must be downloaded and cached before this component functions |
| TASK-TS-0003 (Vision Pipeline) | Yes | Produces the `VisionPipelineOutput` input this engine consumes |
| PyTorch + CUDA/ROCm | Yes | Must be bundled as `python-wheels` within the add-on or documented as prerequisite |
| `trimesh` library | Yes | For intermediate mesh processing; bundle as `python-wheel` |
| `numpy` library | No | Already bundled with Blender's Python |

### 12.3 Rollback Plan
1. Remove or disable the reconstruction adapter module from the add-on package
2. Upstream UI (TASK-TS-0001 Generation panel) remains in stub state showing "Coming soon"
3. Verify no GPU memory leaks or residual tensors via Blender system console

---

## 13. TEST SCENARIOS

> Map tests to acceptance criteria and edge cases for traceability.

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Single-image reconstruction returns valid `StandardMesh` with ≥ 1,000 vertices | Integration | AC-001 | Must Pass |
| TS-002 | Two-image reconstruction with `"front"` and `"right"` labels returns valid mesh | Integration | AC-002 | Must Pass |
| TS-003 | Missing model weights returns `success=False` with actionable error | Unit | AC-003 | Must Pass |
| TS-004 | Image at minimum resolution (64×64) is accepted with quality warning | Unit | EC-001 | Must Pass |
| TS-005 | All-True mask proceeds with full-image warning | Unit | EC-002 | Must Pass |
| TS-006 | All-False mask returns `success=False` with no-object error | Unit | EC-003 | Must Pass |
| TS-007 | Duplicate view labels produce warning but succeed | Unit | EC-004 | Must Pass |
| TS-008 | NaN/Inf in depth map are replaced with 0.0 and warning logged | Unit | EC-005 | Must Pass |
| TS-009 | Insufficient VRAM returns `success=False` before loading weights | Unit | AC-004 | Must Pass |
| TS-010 | `StubAdapter` returns unit cube without GPU or model weights | Unit | AC-005 | Must Pass |
| TS-011 | GPU memory is within 50 MB of baseline after reconstruction | Integration | AC-006 | Must Pass |
| TS-012 | Degenerate output (< 4 vertices) returns `success=False` | Unit | AC-007 | Must Pass |
| TS-013 | `AdapterRegistry` discovers and lists all registered adapters in < 100ms | Unit | NFR-007 | Must Pass |
| TS-014 | Input arrays with mismatched shapes (image 512×512, mask 256×256) raise `ValueError` | Unit | SEC-001 | Must Pass |
| TS-015 | Model weight checksum mismatch returns error with expected/actual hashes | Unit | SEC-004 | Must Pass |
| TS-016 | Single-image reconstruction completes in < 60s on RTX 3060 tier GPU | Performance | NFR-001 | Must Pass |
| TS-017 | Peak VRAM usage stays below 10 GB during inference | Performance | NFR-003 | Must Pass |
| TS-018 | Passing >2 inputs returns `success=False` with multi-view deferral message | Unit | EC-006, FR-021 | Must Pass |
| TS-019 | Reconstruction exceeding timeout returns `success=False` with timeout message | Unit | FR-022 | Should Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| TASK-TS-0001 (Add-on Scaffold) | Required | Pending | TBD | Yes — need preferences API for cache directory |
| TASK-TS-0002 (Model Weight Management) | Required | Pending | TBD | Yes — need model weights cached locally |
| TASK-TS-0003 (Vision Pipeline) | Required | Pending | TBD | Yes — need `VisionPipelineOutput` data structure and processed images |
| TASK-TS-0005 (Mesh Import & Cleanup) | Downstream consumer | Pending | TBD | No — this task produces what TASK-TS-0005 consumes |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| PyTorch 2.x with CUDA/ROCm | Required | [pytorch.org](https://pytorch.org/) | No fallback — GPU inference is required (PRD D2) |
| Primary reconstruction model (Trellis/InstantMesh/OpenLRM) | Required | See §2.1 links | `StubAdapter` for development/testing only |
| `trimesh` library | Required | [trimesh.org](https://trimesh.org/) | Fallback to raw numpy vertex/face arrays |
| `numpy` 1.24+ | Required | Bundled with Blender | N/A — always available |

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
| SHALL/SHOULD/MAY requirements | 20 | 20 | 22 requirements with precise SHALL/SHOULD/MAY language (FR-001–FR-022) |
| Quantified NFRs | 15 | 15 | 8 NFRs, all quantified with specific targets, units, and measurement conditions |
| Given-When-Then criteria (3+) | 20 | 20 | 7 acceptance criteria in Given-When-Then format with specific values |
| Edge cases (2+) | 15 | 15 | 6 edge cases with concrete input examples and exact expected behaviors |
| Out of scope defined | 10 | 10 | 12 explicit exclusions listed with task references |
| Security constraints | 10 | 10 | 5 security requirements + data classification table + `weights_only=True` for pickle safety + checksum manifest cross-reference |
| No ambiguous language | 10 | 10 | All ambiguous terms replaced with specifics. "Plausible" (formerly FR-007) replaced with measurable criteria (≥4 vertices/faces + confidence ≥0.3) |
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
- [x] "handle gracefully" → replaced with specific error messages in FR-011, FR-012, FR-014, FR-021, FR-022
- [x] "fast" / "efficient" / "performant" → replaced with < 60s, < 90s, < 15s, < 100ms, < 120s timeout targets
- [x] "secure" → replaced with SEC-001 through SEC-005
- [x] "plausible" → replaced with measurable criteria in FR-007 (≥4 verts/faces + confidence ≥0.3)
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → not used

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-09 | Orchestrator (AI) | Initial draft |
| 1.1 | 2026-04-14 | AI (spec-review remediation) | Aligned `VisionPipelineOutput` with upstream `VisionResult` (C-001); replaced "plausible" in FR-007 with measurable criteria (M-001); added adapter selection algorithm (M-002); added FR-021 input count validation and EC-006 (M-003); added FR-022 timeout mechanism (M-004); fixed `source_adapter` location (m-002); added checksum manifest cross-ref to SEC-004 (m-004); aligned test priorities (m-005); updated self-score |
| 1.2 | 2026-09-22 | Derek | Amended CON-008 for ADR-0001. The constraint required all inference to run in-process, which the accepted thin-add-on / local-engine decision contradicts — an implementer following it would build the rejected option. The intent (no shelling out to arbitrary binaries) is preserved; the sanctioned engine boundary defined by SPEC-TS-0023 is now permitted, and nothing else is. |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0004-reconstruction-engine.md`
