# Feature Specification: Vision Analysis Pipeline — Segmentation, Depth & View Labels

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0003 |
| **Task ID** | TASK-TS-0003 |
| **Status** | Approved |
| **Version** | 1.3 |
| **Created** | 2026-04-09 |
| **Last Updated** | 2026-09-21 |
| **Author** | Derek |
| **Pod** | Tessera |
| **CSO Approver** | Derek |
| **Spec Type** | Feature |

### Status Transitions
| From | To | Trigger |
|------|----|---------|
| Draft | Submitted | Author submits for review |
| Submitted | Approved | CSO approves |
| Submitted | Draft | CSO requests changes |
| Approved | Reopened | Amendment raised against an approved spec |
| Reopened | Approved | CSO approves the amendment |
| Approved | In Progress | Implementation begins |
| In Progress | Complete | PR merged |

---

## 1. PROBLEM STATEMENT

### 1.1 Business Context
The vision pipeline is the "eyes" of Tessera — it processes user-uploaded reference images into structured data that the 3D reconstruction engine (TASK-TS-0004) consumes. Without it, the agent cannot understand what it's looking at. This task is on the critical path for Phase 1 milestone M1.3 and directly blocks the reconstruction engine. The pipeline must extract three essential signals from each image: (1) an object segmentation mask to isolate the subject from the background, (2) a monocular depth map to provide geometry hints, and (3) a view-direction label to establish 3D camera pose. It also extracts DINOv2 features to provide shape priors and symmetry cues to the reconstruction engine.

### 1.2 User Story
**As a** user uploading reference images of an object,  
**I want** the agent to automatically segment the object from the background, estimate depth, and understand which angle each image shows,  
**So that** the 3D reconstruction is accurate and doesn't include background clutter.

### 1.3 Proposed Approach
Build a sequential, GPU-accelerated vision pipeline that processes each uploaded image through four stages: (1) SAM 2 segmentation to produce a binary object mask, (2) Depth Anything V2 monocular depth estimation to produce a depth map, (3) a lightweight view-direction classifier to auto-detect or confirm user-supplied view labels, and (4) DINOv2 feature extraction for shape priors and symmetry cues. All inference runs locally on the user's GPU — no external API calls. The pipeline uses a model adapter pattern to allow swapping models (e.g., FastSAM for lower VRAM). Output is a standardized `VisionResult` data structure per image consumed by the reconstruction engine.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Segmentation accuracy (IoU) | N/A | ≥ 0.90 on foreground objects with clean backgrounds | Manual evaluation on 20 test images |
| View-label auto-detection accuracy | N/A | ≥ 80% on standard object orientations | Classification accuracy on labeled test set of 50 images |
| Pipeline throughput | N/A | ≤ 8 seconds per image for full pipeline | Wall-clock time on NVIDIA RTX 3060 (12 GB VRAM) |
| Peak VRAM usage | N/A | ≤ 6 GB running all stages sequentially | `torch.cuda.max_memory_allocated()` after processing 1 image |

---

## 2. TECHNICAL CONTEXT

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/__init__.py` | Add-on registration (SPEC-TS-0001) | Module registration, `register()`/`unregister()` pattern |
| `tessera/properties.py` | Scene-level `CollectionProperty` for images | Extending image data with pipeline outputs |
| `tessera/gpu_detection.py` | GPU info API (SPEC-TS-0001) | Querying available VRAM before loading models |
| Model weight manager (SPEC-TS-0002) | Download & cache management | Loading SAM 2, Depth Anything V2, DINOv2 weights |
| SAM 2 — [github.com/facebookresearch/sam2](https://github.com/facebookresearch/sam2) | Segmentation model | Automatic mask mode (no point prompts) |
| Depth Anything V2 — [github.com/DepthAnything/Depth-Anything-V2](https://github.com/DepthAnything/Depth-Anything-V2) | Monocular depth | Depth map inference |
| DINOv2 — [github.com/facebookresearch/dinov2](https://github.com/facebookresearch/dinov2) | Self-supervised features | Feature vector extraction |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`)
- **ML Runtime:** PyTorch 2.x with CUDA / ROCm backend
- **Validation:** Runtime assertions + type annotations (dataclasses / TypedDict)
- **Testing:** `pytest` run via `blender --background --python` for headless testing; model tests run standalone with pytest + torch
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── vision/
│   ├── __init__.py
│   ├── pipeline.py             # VisionPipeline — orchestrates all stages
│   ├── types.py                # VisionResult, ImageInput, DepthMap, etc.
│   ├── preprocessing.py        # Image loading, resizing, format conversion
│   ├── segmentation/
│   │   ├── __init__.py
│   │   ├── base.py             # SegmentationAdapter (abstract)
│   │   ├── sam2_adapter.py     # SAM 2 implementation
│   │   └── fastsam_adapter.py  # FastSAM fallback (future)
│   ├── depth/
│   │   ├── __init__.py
│   │   ├── base.py             # DepthAdapter (abstract)
│   │   ├── depth_anything_adapter.py  # Depth Anything V2 implementation
│   │   └── marigold_adapter.py        # Marigold fallback (future)
│   ├── view_classifier/
│   │   ├── __init__.py
│   │   ├── base.py             # ViewClassifierAdapter (abstract)
│   │   └── silhouette_classifier.py  # Silhouette + up-vector heuristic
│   └── features/
│       ├── __init__.py
│       ├── base.py             # FeatureAdapter (abstract)
│       └── dinov2_adapter.py   # DINOv2 feature extraction
```

The pipeline follows a **sequential execution model** — each stage runs to completion before the next begins, sharing the GPU. This prevents VRAM exhaustion by loading one model at a time. Each stage uses an abstract adapter pattern allowing model swaps.

```mermaid
flowchart LR
    A[User Images] --> B[Preprocessing]
    B --> C[Segmentation - SAM 2]
    C --> D[Depth Estimation - DA V2]
    D --> E[View Classification]
    E --> F[Feature Extraction - DINOv2]
    F --> G[VisionResult per image]
```

---

## 3. FUNCTIONAL REQUIREMENTS

> ⚠️ **Use precise language:** SHALL (required), SHALL NOT (prohibited), SHOULD (recommended), SHOULD NOT (discouraged), MAY (optional). The keyword IS the priority.

### 3.1 Core Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL accept 1–6 images per batch via the `VisionPipeline.process(images: list[ImageInput])` method. The 6-image ceiling bounds peak CPU RAM usage (6 × 1024² × 3 bytes × 5 output arrays ≈ 90 MB) and total pipeline wall-clock time (≤ 30 s per NFR-002). The limit is defined as `MAX_BATCH_SIZE = 6` in `vision/pipeline.py` and MAY be increased in future versions. The system SHALL raise `PipelineError` with message "No images provided." when given an empty list, and "Batch size {n} exceeds maximum of {MAX_BATCH_SIZE}." when given more than `MAX_BATCH_SIZE` images. |
| FR-002 | The system SHALL support input images in `.jpg`, `.png`, `.webp`, and `.heic` formats. |
| FR-003 | The system SHALL resize all input images to a maximum dimension of 1024 px (preserving aspect ratio) before inference to bound VRAM usage. |
| FR-004 | The system SHALL run SAM 2 in automatic mask generation mode (no user point prompts) to produce a binary segmentation mask per image, selecting the largest connected-component foreground region. If multiple connected components have equal area, the system SHALL select the one whose centroid is closest to the image center. |
| FR-005 | The segmentation adapter SHALL output a binary mask as a NumPy array of shape `(H, W)` with dtype `uint8`, where 255 = foreground and 0 = background. |
| FR-006 | The system SHALL run Depth Anything V2 to produce a monocular depth map per image, outputting a single-channel float32 NumPy array of shape `(H, W)` with values normalized to `[0.0, 1.0]` (0 = near, 1 = far). |
| FR-007 | The depth estimation adapter SHALL apply the segmentation mask to zero out background regions of the depth map, producing a masked depth map. |
| FR-008 | The system SHALL accept optional user-supplied view labels per image from the PRD §6 vocabulary: `front`, `back`, `left`, `right`, `top`, `bottom`, `front-left`, `front-right`, `isometric`, `custom:<az>,<el>`. |
| FR-009 | When a view label is not supplied by the user for a given image, the system SHALL run a view-direction auto-classifier to infer the label. |
| FR-010 | The view-direction auto-classifier SHALL output a predicted label and a confidence score in the range `[0.0, 1.0]`. |
| FR-011 | When the auto-classifier confidence is ≥ 0.80, the system SHALL use the predicted label and record `label_source: "auto"` in the output. |
| FR-012 | When the auto-classifier confidence is < 0.80, the system SHALL flag the image for user confirmation by setting `label_needs_confirmation: true` and assigning the top prediction as a suggestion. |
| FR-013 | The system SHALL extract DINOv2 feature vectors per image, outputting a float32 NumPy array of shape `(1, D)` where D is the model's embedding dimension (e.g., 768 for ViT-B/14). |
| FR-014 | The system SHALL produce a `VisionResult` data structure per image containing: `image` (preprocessed), `mask`, `depth_map`, `view_label`, `label_confidence`, `label_source`, `label_needs_confirmation`, and `features`. |
| FR-015 | The system SHALL process pipeline stages sequentially (segmentation → depth → view classification → feature extraction) to avoid concurrent GPU memory pressure. |
| FR-016 | Each model adapter SHALL load its model weights on first invocation and cache the loaded model in memory for subsequent images in the same batch. |
| FR-017 | Each model adapter SHALL unload its model weights from GPU memory after processing all images in a batch, releasing VRAM for the next stage. |
| FR-018 | The system SHALL provide an abstract base class for each pipeline stage (`SegmentationAdapter`, `DepthAdapter`, `ViewClassifierAdapter`, `FeatureAdapter`) to enable model swapping via the adapter pattern. |
| FR-019 | The system SHOULD report per-stage timing (wall-clock seconds) in the `VisionResult` metadata for profiling and user feedback. |
| FR-020 | The system SHOULD display a progress indicator in the Blender UI during pipeline execution showing: current stage name, current image index / total images, and elapsed time. |
| FR-021 | The system MAY support a "low-VRAM" mode that uses smaller model variants (e.g., SAM 2 Tiny instead of SAM 2 Large) when detected VRAM is < 8 GB. |
| FR-022 | *(v1.3)* The system SHALL validate that a GPU it can run inference on is available before starting the pipeline, and raise a `GPUNotAvailableError` if none is. v1 supports **CUDA only** — the supported set is `gpu_detection.SUPPORTED_INFERENCE_BACKENDS`. The error SHALL distinguish the two cases: no GPU detected ("Tessera requires an NVIDIA GPU with CUDA. No compatible GPU was detected.") versus a GPU detected on an unsupported backend, which SHALL name the device and its backend. *(Previously this check accepted ROCm, which then failed inside `torch` at `device="cuda"`. Reversal is tracked by TASK-TS-0022.)* |

### 3.2 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| `filepath` | `str` | Valid file path; extensions: `.jpg`, `.png`, `.webp`, `.heic`; max file size 50 MB | Yes | `"/home/user/photos/mug_front.jpg"` |
| `view_label` | `str \| None` | One of PRD §6 vocabulary or `None` for auto | No (default: `None`) | `"front"` |
| `custom_azimuth` | `float \| None` | Degrees, range 0–360 | No | `45.0` |
| `custom_elevation` | `float \| None` | Degrees, range -90–90 | No | `35.0` |
| `force_sketch` | `bool` | Override sketch auto-detection; when `True`, image is always routed through sketch pathway (SPEC-TS-0010) | No (default: `False`) | `False` |

```python
# Type Definition
from dataclasses import dataclass
from typing import Optional

@dataclass
class ImageInput:
    filepath: str              # Absolute path to image file
    view_label: Optional[str] = None  # PRD §6 label or None for auto-detect
    custom_azimuth: Optional[float] = None   # Only when view_label == "custom"
    custom_elevation: Optional[float] = None  # Only when view_label == "custom"
    force_sketch: bool = False  # Override sketch detection (SPEC-TS-0010)
```

### 3.3 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `image` | `np.ndarray` | `(H, W, 3)` uint8 RGB, max dim 1024 | Preprocessed image array |
| `mask` | `np.ndarray` | `(H, W)` uint8, values 0 or 255 | Binary segmentation mask |
| `depth_map` | `np.ndarray` | `(H, W)` float32, range [0.0, 1.0] | Masked monocular depth |
| `view_label` | `str` | PRD §6 vocabulary | `"front"` |
| `label_confidence` | `float` | Range [0.0, 1.0] | `0.92` |
| `label_source` | `str` | `"user"` or `"auto"` | `"auto"` |
| `label_needs_confirmation` | `bool` | — | `False` |
| `features` | `np.ndarray` | `(1, D)` float32 | DINOv2 CLS token embedding |
| `original_size` | `tuple[int, int]` | `(width, height)` in pixels | `(3024, 4032)` |
| `processing_time_s` | `dict[str, float]` | Stage name → seconds | `{"segmentation": 1.2, "depth": 0.8, ...}` |

```python
# Type Definition
from dataclasses import dataclass, field
import numpy as np

@dataclass
class VisionResult:
    image: np.ndarray                    # (H, W, 3) uint8 RGB
    mask: np.ndarray                     # (H, W) uint8, 0/255
    depth_map: np.ndarray                # (H, W) float32, [0.0, 1.0]
    view_label: str                      # PRD §6 vocabulary
    label_confidence: float              # [0.0, 1.0]
    label_source: str                    # "user" | "auto"
    label_needs_confirmation: bool       # True if auto + conf < 0.80
    features: np.ndarray                 # (1, D) float32
    original_size: tuple[int, int]       # (width, height)
    processing_time_s: dict[str, float] = field(default_factory=dict)
```

---

## 4. CONSTRAINTS

> ⚠️ **Critical for AI code generation.** These are hard prohibitions the AI must follow.

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT make any network calls, DNS lookups, or socket operations during pipeline execution. All model weights must be pre-downloaded via TASK-TS-0002. |
| CON-002 | SHALL NOT run multiple ML models on the GPU simultaneously. Stages execute sequentially; each model is loaded, used, and unloaded before the next stage begins. |
| CON-003 | SHALL NOT store or transmit user images outside the local machine. Images remain on disk at their original paths; pipeline operates on in-memory copies only. |
| CON-004 | SHALL NOT modify the original image files on disk. |
| CON-005 | SHALL NOT hardcode model checkpoint paths. Use the model weight manager API (SPEC-TS-0002) to resolve weight file locations. |
| CON-006 | SHALL NOT assume a specific GPU VRAM size. Check available VRAM via `gpu_detection.get_gpu_info()` before selecting model variants. |
| CON-007 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. |
| CON-008 | SHALL NOT use `bpy.ops` calls from within pipeline processing threads. All Blender UI updates SHALL go through thread-safe property updates on `bpy.types.Scene`. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

> ⚠️ **All NFRs must be quantified.** Replace vague terms with specific numbers.

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Single-image pipeline latency | Wall-clock time from `process()` call to `VisionResult` return | ≤ 8 seconds | NVIDIA RTX 3060 (12 GB), 1024×1024 input, all 4 stages |
| NFR-002 | Batch pipeline latency (6 images) | Wall-clock time for full batch | ≤ 30 seconds | Same GPU, 6 images at 1024 px max |
| NFR-003 | Peak GPU VRAM usage | `torch.cuda.max_memory_allocated()` | ≤ 6 GB | Processing any single stage with largest model variant |
| NFR-004 | CPU RAM usage | Additional Python heap for pipeline data structures | ≤ 500 MB | 6 images loaded with all outputs in memory |
| NFR-005 | Model load time per stage | Wall-clock time from disk load to GPU ready | ≤ 5 seconds per model | First invocation, weights on local NVMe SSD |
| NFR-006 | Segmentation quality | IoU of foreground mask vs. ground-truth | ≥ 0.90 | Object on clean background (single solid-color or gradient) |
| NFR-007 | Depth map quality | Ordinal ranking accuracy (Spearman ρ) | ≥ 0.85 | Standard monocular depth benchmarks |
| NFR-008 | View-label auto-detection accuracy | Classification accuracy across 10 canonical labels | ≥ 80% | On 50 test images with known ground-truth labels |
| NFR-009 | Minimum GPU VRAM | Minimum GPU VRAM required to run any single pipeline stage with the default model variants | ≥ 6 GB | Systems with < 6 GB SHALL receive `InsufficientVRAMError` during model loading |

---

## 6. ACCEPTANCE CRITERIA

> ⚠️ **Minimum 3 criteria in Given-When-Then format.** These drive test implementation.

### AC-001: Single Image Full Pipeline — Happy Path
**Given** a single 2048×1536 `.jpg` image of a ceramic mug on a white background, with user-supplied view label `"front"`,  
**When** `VisionPipeline.process([ImageInput(filepath="mug_front.jpg", view_label="front")])` is called on a system with an NVIDIA RTX 3060 GPU,  
**Then** the method returns a list containing exactly 1 `VisionResult` where:
- `image` has shape `(768, 1024, 3)` (resized to max dim 1024, preserving aspect ratio)
- `mask` has the same `(H, W)` as `image`, with at least 5% and at most 95% of pixels set to 255
- `depth_map` has the same `(H, W)`, values in `[0.0, 1.0]`, and background regions (where mask == 0) are 0.0
- `view_label` == `"front"` and `label_source` == `"user"` and `label_confidence` == 1.0
- `features` has shape `(1, D)` and dtype float32, where `D` matches the configured feature model's embedding dimension (768 for the default DINOv2 ViT-B/14)
- `processing_time_s` contains keys `"preprocessing"`, `"segmentation"`, `"depth"`, `"view_classification"`, `"feature_extraction"` with positive float values
- Total wall-clock time is ≤ 8 seconds

### AC-002: Batch Processing — Multiple Images
**Given** 4 images (`.jpg` and `.png` mix) of a vase from front, back, left, and right angles, with view labels `"front"`, `None`, `None`, `"right"`,  
**When** `VisionPipeline.process(...)` is called with these 4 `ImageInput` objects,  
**Then** the method returns a list of 4 `VisionResult` objects, where:
- Results at index 0 and 3 have `label_source == "user"`
- Results at index 1 and 2 have `label_source == "auto"`
- All 4 have non-zero masks, valid depth maps, and feature vectors
- Total wall-clock time is ≤ 20 seconds

### AC-003: View Label Auto-Detection with Low Confidence
**Given** an ambiguous image of a cylindrical object (e.g., a plain cylinder) with no user-supplied view label,  
**When** the view-direction auto-classifier produces a confidence of 0.55 for `"front"`,  
**Then** the `VisionResult` has `view_label == "front"`, `label_confidence == 0.55`, `label_source == "auto"`, and `label_needs_confirmation == True`.

### AC-004: No GPU Available — Error Handling
**Given** a system with no CUDA or ROCm compatible GPU detected by `gpu_detection.get_gpu_info()`,  
**When** `VisionPipeline.process(...)` is called,  
**Then** the method raises `GPUNotAvailableError` naming the NVIDIA CUDA requirement, and no model loading or inference is attempted. *(v1.3: a detected-but-unsupported GPU — AMD or Apple Silicon — raises the same error with the device and backend named, instead of passing validation and failing later inside `torch`.)*

### AC-005: HEIC Image Format Support
**Given** a single `.heic` image captured from an iPhone,  
**When** `VisionPipeline.process([ImageInput(filepath="object.heic")])` is called,  
**Then** the pipeline converts the HEIC to RGB, processes it through all 4 stages, and returns a valid `VisionResult` with no errors.

### AC-006: Pipeline Progress Reporting
**Given** a batch of 3 images being processed,  
**When** the pipeline is running,  
**Then** the Blender UI property `bpy.context.scene.tessera.pipeline_status` is updated at least once per stage per image with format `"Segmentation — Image 2/3"`, and a numeric progress value `pipeline_progress` is set in the range `[0.0, 1.0]`.

---

## 7. EDGE CASES

> ⚠️ **Minimum 2 edge cases required.** Document non-obvious scenarios AI might miss.

### EC-001: Very Small Input Image
| Aspect | Detail |
|--------|--------|
| **Scenario** | User provides an image smaller than the model's minimum input size (e.g., 64×64 px thumbnail) |
| **Input Example** | A 48×48 pixel `.png` file |
| **Expected Behavior** | The system SHALL upscale the image to the minimum input dimension of 256 px (preserving aspect ratio) using Lanczos interpolation before pipeline processing. The `VisionResult.original_size` SHALL reflect the original 48×48 dimensions. |
| **Test ID** | TS-004 |

### EC-002: Image with No Clear Foreground Object
| Aspect | Detail |
|--------|--------|
| **Scenario** | User uploads a photo of a plain wall or abstract texture with no distinct object to segment |
| **Input Example** | A 1024×768 `.jpg` of a solid blue wall |
| **Expected Behavior** | The segmentation adapter SHALL return a mask covering the entire image (all pixels 255) and log a WARNING: "No distinct foreground object detected. Using full image as foreground." The pipeline SHALL continue with depth and feature extraction on the full image. |
| **Test ID** | TS-005 |

### EC-003: Corrupt or Unreadable Image File
| Aspect | Detail |
|--------|--------|
| **Scenario** | File has a supported extension (`.jpg`) but the data is truncated or corrupt |
| **Input Example** | A 500-byte `.jpg` file that cannot be decoded |
| **Expected Behavior** | The preprocessing stage SHALL raise `ImageLoadError` with message "Failed to load image: {filename}. The file may be corrupt or truncated." and the pipeline SHALL skip this image, returning results for remaining valid images. If all images fail, raise `PipelineError` with message "No valid images could be processed." |
| **Test ID** | TS-006 |

### EC-004: Single Image with `custom:<az>,<el>` View Label
| Aspect | Detail |
|--------|--------|
| **Scenario** | User provides a custom view label with arbitrary azimuth/elevation angles |
| **Input Example** | `ImageInput(filepath="obj.jpg", view_label="custom", custom_azimuth=127.5, custom_elevation=-15.0)` |
| **Expected Behavior** | The system SHALL accept the custom angles, skip the auto-classifier for this image, set `label_source == "user"` and `label_confidence == 1.0`, and store the canonical label as `"custom:127.5,-15.0"`. Azimuth SHALL be normalized to `[0, 360)` and elevation to `[-90, 90]`. |
| **Test ID** | TS-007 |

### EC-005: VRAM Exhaustion During Model Loading
| Aspect | Detail |
|--------|--------|
| **Scenario** | GPU has only 4 GB VRAM, insufficient for the default SAM 2 Large model |
| **Input Example** | System with NVIDIA GTX 1650 (4 GB VRAM) |
| **Expected Behavior** | The system SHALL catch `torch.cuda.OutOfMemoryError` (or equivalent), log an ERROR with available vs. required VRAM, and raise `InsufficientVRAMError` with message "Insufficient GPU VRAM: {available_gb:.1f} GB available, {required_gb:.1f} GB required for {model_name}. Consider enabling low-VRAM mode in add-on preferences." |
| **Test ID** | TS-008 |

---

## 8. OUT OF SCOPE

> ⚠️ **Explicitly list what this feature does NOT include.** Prevents AI scope creep.

The following are explicitly **excluded** from this feature:

- ❌ 3D reconstruction from pipeline outputs (TASK-TS-0004)
- ❌ Mesh generation, import, or manipulation
- ❌ Interactive segmentation with user-provided point/box prompts (future enhancement)
- ❌ Multi-view stereo alignment or structure-from-motion (TASK-TS-0007)
- ❌ Video frame extraction or video input support
- ❌ Model weight downloading or caching logic (SPEC-TS-0002)
- ❌ Training, fine-tuning, or transfer learning of any model
- ❌ Texture or color extraction for mesh painting (deferred per PRD D5)
- ❌ Real-time / streaming inference (batch-only)
- ❌ CPU-only inference fallback (GPU required per PRD D2)
- ❌ View-label UI for per-image dropdown/label assignment (part of SPEC-TS-0001 add-on scaffold UI panels)

---

## 9. SECURITY CONSIDERATIONS

> ⚠️ **Required for all features.** AI-generated code needs explicit security constraints.

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — local Blender add-on, no network interaction |
| **Auth Method** | None |
| **Required Permissions** | File system read (user images), file system read (model weight cache), GPU access via CUDA/ROCm |
| **Rate Limiting** | N/A |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| User image file paths | Internal | Stored in Blender scene data only; logged as basename only (no full paths) |
| User image pixel data | Internal | Loaded into memory for processing; never written to disk in modified form; never transmitted |
| Segmentation masks | Internal | In-memory arrays; never persisted outside Blender session unless user saves `.blend` |
| Depth maps | Internal | In-memory arrays; same handling as masks |
| DINOv2 features | Internal | In-memory arrays; same handling |
| GPU device info | Internal | Displayed in UI only; not transmitted |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL validate all input file paths using `pathlib.Path.resolve()` to prevent path traversal attacks before reading images. |
| SEC-002 | SHALL NOT execute downloaded model weights as Python code. Weights SHALL be loaded only via `torch.load(path, weights_only=True)` or `safetensors.torch.load_file()`. |
| SEC-003 | SHALL NOT make any network connections, DNS lookups, or socket operations during pipeline execution. |
| SEC-004 | SHALL NOT write user image data to temporary files. All processing SHALL occur on in-memory copies. |
| SEC-005 | SHALL validate image file size does not exceed 50 MB before loading to prevent memory exhaustion attacks from crafted files. |
| SEC-006 | SHALL sanitize model checkpoint paths to ensure they reside within the model weight cache directory managed by SPEC-TS-0002. |

---

## 10. API CONTRACT [CONDITIONAL]

> **Skipped** — This is a local Python pipeline within the Blender add-on. No REST/HTTP APIs are exposed or consumed.

The pipeline exposes the following **internal Python API** for downstream tasks (TASK-TS-0004):

### 10.1 Pipeline API
```python
from tessera.vision.pipeline import VisionPipeline
from tessera.vision.types import ImageInput, VisionResult

# Initialize pipeline (loads adapters, does NOT load model weights yet)
pipeline = VisionPipeline()

# Process a batch of images
inputs = [
    ImageInput(filepath="/path/to/mug_front.jpg", view_label="front"),
    ImageInput(filepath="/path/to/mug_side.jpg"),  # auto-detect label
]
results: list[VisionResult] = pipeline.process(inputs)

# Access individual results
for result in results:
    print(result.view_label)        # "front"
    print(result.mask.shape)        # (768, 1024)
    print(result.depth_map.shape)   # (768, 1024)
    print(result.features.shape)    # (1, 768)
    print(result.label_source)      # "user" or "auto"
```

### 10.2 Adapter Registration API
```python
from tessera.vision.segmentation.base import SegmentationAdapter
from tessera.vision.pipeline import VisionPipeline

# Register a custom segmentation adapter
class FastSAMAdapter(SegmentationAdapter):
    def load(self) -> None: ...
    def predict(self, image: np.ndarray) -> np.ndarray: ...
    def unload(self) -> None: ...

pipeline = VisionPipeline(segmentation_adapter=FastSAMAdapter())
```

### 10.3 Error Types
```python
from tessera.vision.types import (
    GPUNotAvailableError,    # No CUDA/ROCm GPU
    ImageLoadError,          # Cannot decode image file
    InsufficientVRAMError,   # Not enough GPU memory
    PipelineError,           # General pipeline failure
)
```

### 10.4 View-Label Camera-Pose Mapping

The reconstruction engine (TASK-TS-0004) uses view labels to initialize canonical camera poses. The `VisionResult.view_label` maps to azimuth/elevation pairs per PRD §6:

```python
# Canonical camera poses per view label (azimuth°, elevation°)
VIEW_LABEL_POSES: dict[str, tuple[float, float]] = {
    "front":       (0.0,    0.0),
    "back":        (180.0,  0.0),
    "left":        (270.0,  0.0),
    "right":       (90.0,   0.0),
    "top":         (0.0,    90.0),
    "bottom":      (0.0,   -90.0),
    "front-left":  (315.0,  0.0),
    "front-right": (45.0,   0.0),
    "isometric":   (45.0,   35.0),
    # "custom:<az>,<el>" — parsed from label string at runtime
}
```

This mapping is defined in `tessera/vision/types.py` and exported for downstream consumers. For `custom:<az>,<el>` labels, the azimuth and elevation are parsed from the label string and stored in `VisionResult.view_label` as `"custom:<az>,<el>"`.

---

## 11. OBSERVABILITY

> Define logging and metrics for production monitoring.

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------|
| Pipeline started | INFO | `num_images`, `gpu_name`, `vram_gb` | ⚠️ No PII |
| Preprocessing complete | DEBUG | `filename` (basename), `original_size`, `resized_size` | ⚠️ No full paths |
| Stage started | INFO | `stage_name`, `image_index`, `total_images`, `model_name` | ⚠️ No PII |
| Stage complete | INFO | `stage_name`, `image_index`, `duration_s` | ⚠️ No PII |
| Model loaded to GPU | DEBUG | `model_name`, `vram_used_mb`, `load_time_s` | ⚠️ No PII |
| Model unloaded from GPU | DEBUG | `model_name`, `vram_freed_mb` | ⚠️ No PII |
| View-label auto-detected | INFO | `filename` (basename), `predicted_label`, `confidence`, `needs_confirmation` | ⚠️ No full paths |
| No foreground object detected | WARN | `filename` (basename) | ⚠️ No full paths |
| Image load failed | ERROR | `filename` (basename), `error_message` | ⚠️ No full paths |
| VRAM exhaustion | ERROR | `model_name`, `available_vram_mb`, `required_vram_mb` | ⚠️ No PII |
| Pipeline complete | INFO | `num_images`, `total_time_s`, `images_needing_confirmation` | ⚠️ No PII |

> All logging uses Python's `logging` module with logger name `"tessera.vision"`. Blender routes this to the system console.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only). All timing data is available via `VisionResult.processing_time_s` for local profiling.

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — pipeline is invoked by the generation workflow |
| **Default State** | N/A |
| **Rollout Plan** | Included in add-on `.zip`; activated when user clicks "Generate" |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| SPEC-TS-0001 (Add-on Scaffold) | Yes | UI panels, image list, GPU detection must exist |
| SPEC-TS-0002 (Model Weights) | Yes | SAM 2, Depth Anything V2, DINOv2 weights must be downloaded + cached |
| PyTorch 2.x + torchvision | Yes | Bundled as python-wheels in the add-on `.zip` or resolved via Blender extension deps |
| `pillow-heif` | Yes | Required for `.heic` support; bundled as python-wheel |
| `safetensors` | Yes | For secure model weight loading; bundled as python-wheel |

### 12.3 Rollback Plan
1. If vision pipeline fails, the add-on remains functional — only the "Generate" workflow is affected
2. Users can disable individual pipeline stages via add-on preferences (future enhancement)
3. Model weight cache remains intact for re-use after bug fix

---

## 13. TEST SCENARIOS

> Map tests to acceptance criteria and edge cases for traceability.

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Process single JPG with user-supplied "front" label — verify all output fields | Integration | AC-001 | Must Pass |
| TS-002 | Process batch of 4 images with mixed user/auto labels — verify label sources | Integration | AC-002 | Must Pass |
| TS-003 | Auto-detect view label with low confidence — verify confirmation flag | Unit | AC-003 | Must Pass |
| TS-004 | Process 48×48 image — verify upscale to 256 px min and correct `original_size` | Unit | EC-001 | Must Pass |
| TS-005 | Process image of plain wall — verify full-image mask and warning log | Integration | EC-002 | Must Pass |
| TS-006 | Process corrupt `.jpg` file — verify `ImageLoadError` raised, other images succeed | Unit | EC-003 | Must Pass |
| TS-007 | Process image with `custom:127.5,-15.0` label — verify angle normalization | Unit | EC-004 | Must Pass |
| TS-008 | Call pipeline with no GPU — verify `GPUNotAvailableError` raised | Unit | AC-004 | Must Pass |
| TS-009 | Process `.heic` image — verify successful conversion and full pipeline | Integration | AC-005 | Must Pass |
| TS-010 | Verify progress updates during batch processing | Integration | AC-006 | Must Pass |
| TS-011 | Segmentation mask output: verify shape matches input, dtype uint8, values 0 or 255 | Unit | FR-005 | Must Pass |
| TS-012 | Depth map output: verify shape, dtype float32, range [0.0, 1.0], background zeroed | Unit | FR-006, FR-007 | Must Pass |
| TS-013 | Feature vector output: verify shape `(1, D)`, dtype float32, non-zero values | Unit | FR-013 | Must Pass |
| TS-014 | Process 6 images on RTX 3060 — verify ≤ 30s total and ≤ 6 GB peak VRAM | Performance | NFR-001–003 | Should Pass |
| TS-015 | Verify model unload after batch completion — VRAM returns to pre-pipeline level | Integration | FR-017 | Must Pass |
| TS-016 | Register custom segmentation adapter — verify it's used instead of SAM 2 | Unit | FR-018 | Should Pass |
| TS-017 | Process image exceeding 50 MB file size — verify rejection before loading | Unit | SEC-005 | Must Pass |
| TS-018 | Attempt path traversal in filepath — verify `SEC-001` catches it | Unit | SEC-001 | Must Pass |
| TS-019 | Call `pipeline.process([])` with empty list — verify `PipelineError("No images provided.")` raised | Unit | FR-001 | Must Pass |
| TS-020 | Call `pipeline.process(...)` with 7 images — verify `PipelineError("Batch size 7 exceeds maximum of 6.")` raised | Unit | FR-001 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0001 (Add-on Scaffold) | Required | Pending | TBD | Yes — need UI panels and `scene.tessera.images` |
| SPEC-TS-0002 (Model Weights) | Required | Pending | TBD | Yes — need weight download + cache API |
| `gpu_detection.get_gpu_info()` | Required | Pending (SPEC-TS-0001) | TBD | Yes — need VRAM query |
| `properties.py` scene data | Required | Pending (SPEC-TS-0001) | TBD | Yes — need image list property |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| SAM 2 model weights | Required | [github.com/facebookresearch/sam2](https://github.com/facebookresearch/sam2) | FastSAM as lighter alternative (future) |
| Depth Anything V2 model weights | Required | [github.com/DepthAnything/Depth-Anything-V2](https://github.com/DepthAnything/Depth-Anything-V2) | Marigold as alternative (future) |
| DINOv2 model weights | Required | [github.com/facebookresearch/dinov2](https://github.com/facebookresearch/dinov2) | No fallback needed — small model |
| PyTorch 2.x | Required | [pytorch.org](https://pytorch.org) | No fallback — hard requirement |
| `pillow-heif` | Required | [pypi.org/project/pillow-heif](https://pypi.org/project/pillow-heif/) | Skip HEIC; warn user to convert to JPG/PNG |
| `safetensors` | Recommended | [pypi.org/project/safetensors](https://pypi.org/project/safetensors/) | Fall back to `torch.load(weights_only=True)` |

---

## 15. APPROVAL

| Role | Name | Date | Status |
|------|------|------|--------|
| Author | Derek | 2026-09-21 | ☑ Submitted |
| CSO Approval | Derek | 2026-09-22 | ☑ Approved |
| Deputy Review | — | — | ☑ N/A |

**Approval Notes:**
v1.3 approved 2026-09-22. FR-022 now matches what the adapters implement: CUDA only, per PRD-001 D7. A detected-but-unsupported GPU is refused up front with the device named, rather than passing validation and failing inside `torch`. Reversal is gated on TASK-TS-0022.

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-09 | Derek | Initial draft |
| 1.1 | 2026-04-14 | Derek | Address review findings: added view-label UI to out-of-scope (M1), added VIEW_LABEL_POSES camera-pose mapping to API contract (M2), documented 6-image batch limit rationale with boundary error handling (M3), added segmentation tie-breaking rule (m1), parameterized feature dimension in AC-001 (m2), added NFR-009 minimum VRAM requirement (m3), added boundary tests TS-019/TS-020 (m4) |
| 1.2 | 2026-04-14 | Derek | Added `force_sketch: bool = False` field to canonical `ImageInput` dataclass and input specification table to support sketch detection override (SPEC-TS-0010 FR-006). Backward-compatible — defaults to `False`. |
| 1.3 | 2026-09-21 | Derek | Narrowed FR-022 to the backends the adapters actually implement (CUDA only, per PRD-001 D7 / NG8). The previous wording accepted ROCm, which passed validation and then failed inside `torch` at `device="cuda"`; a detected-but-unsupported GPU is now rejected up front with the device named. Reversal is tracked by TASK-TS-0022. |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0003-vision-pipeline.md`
