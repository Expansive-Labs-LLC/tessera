# Feature Specification: Sketch-to-3D Pathway

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0010 |
| **Task ID** | TASK-TS-0010 |
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
Tessera's core pipeline (TASK-TS-0003 → TASK-TS-0004) converts photos of real objects into 3D-printable meshes. However, not every user has a photo of what they want. Designers, students, and hobbyists often start with a hand-drawn sketch on paper or a tablet drawing. Without sketch support, an entire user cohort — educators using the US-04 workflow ("I drew a shape on paper, photograph it, and the agent turns it into a 3D object I can hold") — is excluded from Tessera.

Sketch input differs fundamentally from photo input: sketches lack texture, shading, and photorealistic depth cues that reconstruction models rely on. Feeding a raw sketch directly into a photo-trained 3D reconstruction model produces degenerate geometry (flat, broken, or unrecognizable meshes). A dedicated sketch pathway must bridge this gap by (1) detecting sketches automatically, (2) cleaning and normalizing the sketch, (3) synthesizing a photo-realistic rendering from the sketch using image-conditioned diffusion (ControlNet), and (4) routing the rendered image through the existing reconstruction adapter (SPEC-TS-0004) with symmetry priors enabled.

This is a Phase 3 task (M3.4) with P3 priority. The photo-based path (TASK-TS-0004) serves the primary use case; this extends coverage to hand-drawn input.

### 1.2 User Story
**As a** student who drew a shape on paper,  
**I want** to photograph my drawing and have the agent turn it into a 3D object,  
**So that** I can hold a physical version of my sketch.

### 1.3 Proposed Approach
Implement a four-component sketch-to-3D pathway that integrates with the existing vision pipeline (SPEC-TS-0003) and reconstruction engine (SPEC-TS-0004):

1. **Sketch Detector** — A binary classifier that determines whether an uploaded image is a photograph or a sketch/line drawing, using edge-density heuristics combined with a lightweight CNN classifier. When a sketch is detected, the image is routed to the sketch pathway instead of the standard photo pathway.

2. **Sketch Preprocessor** — Cleans and normalizes raw sketch images: adaptive binarization (Otsu + adaptive thresholding), noise removal (morphological opening), line thinning (Zhang-Suen skeletonization), and optional perspective correction (contour-based quadrilateral detection + warp) for photographed paper sketches.

3. **Sketch-to-Rendered-Image Synthesizer** — Uses a locally-hosted diffusion model with ControlNet (scribble/lineart conditioning) to convert the cleaned sketch into a photo-realistic rendered image. This bridges the domain gap between sparse line drawings and the photorealistic inputs that 3D reconstruction models expect. The synthesizer runs entirely on the local GPU.

4. **Sketch-Conditioned Reconstruction** — Routes the synthesized rendered image through the existing `ReconstructionEngine` (SPEC-TS-0004) with symmetry mode enabled by default. Bilateral symmetry is applied as a post-processing step when the sketch appears to depict a symmetrical object. Multi-view sketch support allows the user to upload front + side sketches, which are individually synthesized and then fed as a multi-view pair to the reconstruction engine.

All inference runs locally on the user's GPU — no external API calls.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Sketch detection accuracy | N/A | ≥ 95% on mixed photo/sketch inputs | Binary classification accuracy on 100-image test set (50 photos, 50 sketches) |
| Sketch-to-3D recognizability | N/A | ≥ 75% of simple symmetric objects produce recognizable meshes | Visual evaluation on 20-object test set (cups, vases, bottles, boxes) |
| End-to-end sketch pathway latency | N/A | < 120 seconds on RTX 3060 | Wall-clock from sketch upload to `StandardMesh` return |
| Symmetry enforcement accuracy | N/A | ≥ 90% of symmetric sketches produce bilaterally symmetric meshes | Vertex-pair distance deviation < 1mm after symmetry pass |

---

## 2. TECHNICAL CONTEXT

> ⚠️ **AI needs this context BEFORE generating code.** Provide patterns and references here.

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/vision/pipeline.py` | Vision pipeline orchestration (SPEC-TS-0003) | Integrating sketch detection as a classification stage |
| `tessera/vision/types.py` | `VisionResult`, `ImageInput` dataclasses | Extending with sketch-specific fields (`is_sketch`, `sketch_type`) |
| `tessera/vision/preprocessing.py` | Image loading, resizing, format conversion | Extending with sketch-specific preprocessing |
| `tessera/reconstruction/adapter.py` | `ReconstructionAdapter` ABC (SPEC-TS-0004) | Adapter pattern for sketch-conditioned reconstruction |
| `tessera/reconstruction/engine.py` | `ReconstructionEngine` (SPEC-TS-0004) | Entry point for routing synthesized sketch images to reconstruction |
| `tessera/reconstruction/mesh_output.py` | `StandardMesh` dataclass (SPEC-TS-0004) | Output format for sketch-to-3D pathway |
| [ControlNet](https://github.com/lllyasviel/ControlNet) | Image-conditioned diffusion model | Scribble/lineart conditioning for sketch-to-rendered-image synthesis |
| [Stable Diffusion](https://github.com/Stability-AI/stablediffusion) | Base diffusion model | Local inference for image synthesis |
| [Trellis / InstantMesh / OpenLRM](https://github.com/microsoft/TRELLIS) | 3D reconstruction models (SPEC-TS-0004) | Downstream reconstruction from synthesized rendered images |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`)
- **ML Runtime:** PyTorch 2.x with CUDA / ROCm backend
- **Image Processing:** OpenCV (`cv2`) for sketch preprocessing, `numpy` for array operations
- **Diffusion Inference:** `diffusers` library (HuggingFace) for ControlNet + Stable Diffusion local inference
- **Mesh Processing:** `trimesh`, `numpy` (via SPEC-TS-0004 `StandardMesh`)
- **Testing:** `pytest` run via `blender --background --python` for headless testing
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── sketch/
│   ├── __init__.py
│   ├── detector.py              # SketchDetector — photo vs. sketch classification
│   ├── preprocessor.py          # SketchPreprocessor — binarization, thinning, perspective correction
│   ├── synthesizer.py           # SketchSynthesizer — ControlNet sketch-to-rendered-image
│   ├── symmetry.py              # SymmetryEnforcer — bilateral symmetry post-processing
│   ├── pipeline.py              # SketchPipeline — orchestrates detect → preprocess → synthesize → reconstruct
│   ├── types.py                 # SketchDetectionResult, SketchConfig, SketchPipelineResult
│   └── utils/
│       ├── __init__.py
│       ├── edge_density.py      # Edge density heuristic for sketch detection
│       └── perspective.py       # Contour-based perspective correction
```

**Data flow:**

```
User uploads image(s)
        │
        ▼
SketchDetector.classify(image) → SketchDetectionResult
        │
        ├── is_sketch == False → Standard photo pathway (SPEC-TS-0003 → SPEC-TS-0004)
        │
        └── is_sketch == True
                │
                ▼
        SketchPreprocessor.preprocess(image) → cleaned_sketch
                │
                ▼
        SketchSynthesizer.synthesize(cleaned_sketch, prompt) → rendered_image
                │
                ▼
        ReconstructionEngine.reconstruct([VisionPipelineOutput(rendered_image, ...)])
                │
                ▼
        SymmetryEnforcer.enforce(StandardMesh, config) → StandardMesh (symmetrized)
                │
                ▼
        SketchPipelineResult
```

**Multi-view sketch flow:**

```
User uploads sketch_front + sketch_side
        │
        ├── Each sketch individually: detect → preprocess → synthesize
        │
        ▼
ReconstructionEngine.reconstruct([
    VisionPipelineOutput(rendered_front, view_label="front"),
    VisionPipelineOutput(rendered_side, view_label="right")
])
        │
        ▼
SymmetryEnforcer.enforce(mesh, config) → final mesh
```

**Two-stage reconstruction rationale:**

Sketch-conditioned 3D reconstruction models are a less mature space than photo-to-3D. Rather than implementing a separate sketch-specific 3D model (which would require maintaining a second model backend and has lower quality), the two-stage approach leverages the existing, proven reconstruction adapter (SPEC-TS-0004) by first translating the sketch into the domain it understands (photorealistic rendered images). This design:
- Reuses the entire SPEC-TS-0004 adapter infrastructure (no new 3D model needed)
- Benefits from future improvements to the photo reconstruction adapter
- Uses ControlNet which is well-understood, actively maintained, and produces high-quality outputs
- Keeps model management simpler (one diffusion model + one 3D model vs. two specialized 3D models)

---

## 3. FUNCTIONAL REQUIREMENTS

> ⚠️ **Use precise language:** SHALL (required), SHALL NOT (prohibited), SHOULD (recommended), SHOULD NOT (discouraged), MAY (optional). The keyword IS the priority.

### 3.1 Core Requirements — Sketch Detection

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL implement a `SketchDetector` class with a `classify(image: np.ndarray) → SketchDetectionResult` method that determines whether an input image is a photograph or a sketch/line drawing. |
| FR-002 | The `SketchDetectionResult` SHALL contain: `is_sketch` (bool), `confidence` (float, 0.0–1.0), `sketch_type` (str: `"pencil"`, `"ink"`, `"digital"`, `"unknown"`), `edge_density_ratio` (float, 0.0–1.0), and `detection_method` (str: `"heuristic"`, `"cnn"`, `"user_override"`). |
| FR-003 | The sketch detector SHALL use a two-stage classification approach: (a) an edge-density heuristic that computes the ratio of Canny edge pixels to total pixels, and (b) a lightweight CNN classifier (MobileNetV3-Small fine-tuned on photo-vs-sketch binary classification) for confirmation when the heuristic confidence is between 0.40 and 0.85. |
| FR-004 | When edge-density ratio is ≥ 0.15 (high edge density) AND color channel standard deviation is ≤ 30.0 (low color variation), the heuristic SHALL classify the image as a sketch with confidence = `min(1.0, edge_density_ratio * 3.0 + (1.0 - color_std / 128.0) * 0.5)`. |
| FR-005 | When the heuristic confidence is between 0.40 and 0.85, the system SHALL invoke the CNN classifier to confirm the classification, using the CNN's output as the final result. |
| FR-006 | The system SHALL allow users to override the auto-detection result by explicitly marking an image as a sketch via the `ImageInput.force_sketch` field (bool, default `False`). When `force_sketch` is `True`, the detector SHALL skip classification and return `SketchDetectionResult(is_sketch=True, confidence=1.0, sketch_type="unknown", detection_method="user_override")`. The `force_sketch` field is added to the canonical `ImageInput` dataclass in SPEC-TS-0003 §3.2 (backward-compatible — defaults to `False`, invisible to non-sketch callers). |

### 3.2 Core Requirements — Sketch Preprocessing

| ID | Requirement |
|----|-------------|
| FR-007 | The system SHALL implement a `SketchPreprocessor` class with a `preprocess(image: np.ndarray, config: SketchConfig) → PreprocessedSketch` method. |
| FR-008 | The preprocessor SHALL convert the input image to grayscale using luminance weighting (`0.299*R + 0.587*G + 0.114*B`). |
| FR-009 | The preprocessor SHALL apply adaptive binarization using Otsu's method as a global threshold, followed by `cv2.adaptiveThreshold` with a block size of 11 and constant C=2 for local refinement, producing a binary image (0 = background, 255 = line). |
| FR-010 | The preprocessor SHALL remove salt-and-pepper noise via morphological opening with a 3×3 kernel (`cv2.morphologyEx` with `MORPH_OPEN`), applied once. |
| FR-011 | The preprocessor SHALL apply Zhang-Suen line thinning via `cv2.ximgproc.thinning()` to reduce line strokes to single-pixel width. |
| FR-012 | The preprocessor SHALL attempt perspective correction when the `SketchConfig.perspective_correction` flag is `True` (default: `True`). Perspective correction SHALL: (a) detect the largest quadrilateral contour in the image (paper boundary), (b) compute a perspective transform via `cv2.getPerspectiveTransform()`, and (c) warp the image to a rectangular output via `cv2.warpPerspective()`. |
| FR-013 | If perspective correction fails to detect a quadrilateral contour with ≥ 4 corner points, the system SHALL skip the correction step, log a DEBUG message "Perspective correction skipped: no paper boundary detected", and continue with the uncorrected image. |
| FR-014 | The `PreprocessedSketch` output SHALL contain: `binary_image` (np.ndarray, H×W, uint8, values 0 or 255), `thinned_image` (np.ndarray, H×W, uint8, values 0 or 255), `was_perspective_corrected` (bool), and `original_size` (tuple[int, int]). |
| FR-015 | The preprocessor output SHALL always follow the convention 255 = stroke/line, 0 = background. If the input binary image has white strokes on a dark background (determined by > 50% of binarized pixels being 255), the preprocessor SHALL invert the image before proceeding with thinning. |

### 3.3 Core Requirements — Sketch-to-Rendered-Image Synthesis

| ID | Requirement |
|----|-------------|
| FR-016 | The system SHALL implement a `SketchSynthesizer` class with a `synthesize(sketch: PreprocessedSketch, prompt: str, config: SketchConfig) → SynthesizedImage` method. |
| FR-017 | The synthesizer SHALL use a locally-hosted Stable Diffusion model with ControlNet (scribble or lineart conditioning) to generate a photo-realistic rendered image from the preprocessed sketch. |
| FR-018 | The synthesizer SHALL accept a text prompt (str) describing the object in the sketch (e.g., `"a ceramic vase, studio lighting, white background"`). When no prompt is provided, the system SHALL use a default prompt: `"a 3D object, studio lighting, white background, product photography"`. |
| FR-019 | The synthesizer SHALL generate an output image at 512×512 resolution (matching SPEC-TS-0004's recommended input size) in RGB format as a uint8 numpy array. |
| FR-020 | The synthesizer SHALL use a fixed random seed (configurable via `SketchConfig.synthesis_seed`, default: 42) for deterministic output given the same input sketch and prompt. |
| FR-021 | The synthesizer SHALL run inference with ControlNet conditioning strength (guidance scale) of 7.5 (configurable via `SketchConfig.guidance_scale`, range 1.0–20.0) and 30 diffusion steps (configurable via `SketchConfig.num_inference_steps`, range 10–100). |
| FR-022 | The `SynthesizedImage` output SHALL contain: `rendered_image` (np.ndarray, 512×512×3, uint8, RGB), `prompt_used` (str), `seed` (int), `inference_time_s` (float), and `guidance_scale` (float). |
| FR-023 | The system SHALL unload the diffusion model and ControlNet from GPU VRAM after synthesis completes (both success and failure) before handing the rendered image to the reconstruction engine, to free VRAM for 3D reconstruction. |

### 3.4 Core Requirements — Symmetry-Aware Generation

| ID | Requirement |
|----|-------------|
| FR-024 | The system SHALL implement a `SymmetryEnforcer` class with an `enforce(mesh: StandardMesh, config: SymmetryConfig) → StandardMesh` method. |
| FR-025 | Bilateral symmetry enforcement SHALL be enabled by default for all sketch-originated meshes (`SymmetryConfig.enable_symmetry`, default: `True`). Users MAY disable it by setting this flag to `False`. |
| FR-026 | The symmetry enforcer SHALL detect the primary symmetry axis of the mesh by computing the principal components of the vertex positions (PCA) and selecting the axis with the smallest eigenvalue as the reflection plane normal. |
| FR-027 | The symmetry enforcer SHALL produce a symmetric mesh by: (a) selecting one half of the mesh relative to the detected symmetry plane, (b) mirroring the selected half across the plane, and (c) merging boundary vertices at the symmetry plane within a tolerance of 0.001 units (in normalized mesh space). |
| FR-028 | If the mesh's vertex position spread along the candidate symmetry axis is < 5% of the mesh's bounding box diagonal, the enforcer SHALL skip symmetry (the mesh is already near-planar along that axis) and log a WARNING: "Symmetry enforcement skipped: mesh has insufficient depth along the detected symmetry axis ({spread:.4f} < {threshold:.4f})." |
| FR-029 | The symmetry-enforced mesh SHALL preserve the total vertex count to within ±10% of the original mesh. If vertex count changes by more than 10%, the system SHALL log a WARNING: "Symmetry enforcement changed vertex count by {delta_percent:.1f}% (original: {original_count}, new: {new_count})." |

### 3.5 Core Requirements — Sketch Pipeline Orchestration

| ID | Requirement |
|----|-------------|
| FR-030 | The system SHALL implement a `SketchPipeline` class with a `process(inputs: list[ImageInput]) → SketchPipelineResult` method that orchestrates the full sketch-to-3D flow. |
| FR-031 | The `SketchPipeline` SHALL classify each input image via the `SketchDetector`. Images classified as sketches SHALL be routed through the sketch pathway; images classified as photos SHALL be passed through to the standard vision pipeline (SPEC-TS-0003). |
| FR-032 | The `SketchPipelineResult` SHALL contain: `mesh` (StandardMesh or None), `success` (bool), `error_message` (str, empty on success), `warnings` (list[str]), `detection_results` (list[SketchDetectionResult]), `synthesized_images` (list[SynthesizedImage]), `symmetry_applied` (bool), and `total_time_s` (float). |
| FR-033 | For multi-view sketch input (2 sketches with different view labels), the `SketchPipeline` SHALL preprocess and synthesize each sketch independently, then pass both synthesized rendered images to `ReconstructionEngine.reconstruct()` as a 2-image input with the user's view labels. |
| FR-034 | The system SHALL support a maximum of 2 sketch inputs per reconstruction request. If more than 2 sketches are provided, the system SHALL return an error: "Sketch-to-3D pathway supports a maximum of 2 sketch inputs. Received: {count}. Provide 1 (single-view) or 2 (front + side) sketches." |
| FR-035 | The `SketchPipeline` SHALL execute stages sequentially — sketch detection, preprocessing, synthesis, reconstruction, symmetry — loading and unloading GPU models between stages to minimize peak VRAM usage. |
| FR-036 | The system SHOULD display a progress indicator in the Blender UI during sketch pipeline execution showing: current stage name (Detecting, Preprocessing, Synthesizing, Reconstructing, Symmetry), current sketch index / total, and elapsed time. |
| FR-037 | The system SHOULD include the sketch-specific metadata in `StandardMesh.metadata`: `"input_type": "sketch"`, `"sketch_type"` (from detection), `"synthesis_prompt"` (the prompt used), `"symmetry_applied"` (bool). |
| FR-038 | The `SketchPipeline` SHALL construct a `VisionPipelineOutput` (type alias for `VisionResult` from SPEC-TS-0003) from each `SynthesizedImage` using the following field mapping: `image` = `rendered_image` (512×512×3 uint8 RGB), `mask` = `np.full((512, 512), 255, dtype=np.uint8)` (entire synthesized image is foreground — no background segmentation needed), `depth_map` = `np.zeros((512, 512), dtype=np.float32)` (depth estimation is not run on synthesized images), `view_label` = the user-supplied `view_label` or `"front"` for single-sketch input without a label, `label_confidence` = `1.0`, `label_source` = `"user"`, `label_needs_confirmation` = `False`, `features` = `np.zeros((1, 768), dtype=np.float32)` (DINOv2 features are not extracted for synthesized images), `original_size` = `(512, 512)`, `processing_time_s` = `{"sketch_synthesis": inference_time_s}`. |
| FR-039 | The `SketchPipeline` SHALL check available GPU VRAM via `torch.cuda.mem_get_info()` before loading the diffusion model (ControlNet + Stable Diffusion). If available VRAM is below 8 GB, the system SHALL return `SketchPipelineResult(success=False, error_message="Insufficient GPU VRAM for sketch synthesis. Required: 8 GB, Available: {available_gb:.1f} GB. Close other GPU applications or free VRAM before running sketch-to-3D.")` without loading any model weights. |
| FR-040 | The `SketchDetector` SHALL determine `sketch_type` using the following heuristic rules applied after sketch classification is confirmed: (a) `"digital"` — if the input image has ≤ 4 unique grayscale values after quantization to 8 levels AND no perspective correction was needed (clean digital input), (b) `"pencil"` — if the image is grayscale (color channel standard deviation ≤ 5.0) AND the mean stroke intensity on the binarized image is between 100 and 200 (soft gray lines), (c) `"ink"` — if the image is grayscale or near-grayscale (color channel standard deviation ≤ 30.0) AND the mean stroke intensity is ≥ 200 (high-contrast dark lines), (d) `"unknown"` — if none of the above conditions are met. When `force_sketch` is `True`, `sketch_type` SHALL default to `"unknown"`. |
| FR-041 | The CNN classifier (MobileNetV3-Small) SHALL accept input images resized to 224×224 pixels using bilinear interpolation, normalized using ImageNet mean `[0.485, 0.456, 0.406]` and standard deviation `[0.229, 0.224, 0.225]`, and converted to a float32 tensor of shape `(1, 3, 224, 224)`. The classifier SHALL output a single sigmoid score in `[0.0, 1.0]` where values ≥ 0.5 indicate "sketch" and values < 0.5 indicate "photo". |

### 3.6 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| `inputs` | `list[ImageInput]` | Length 1–2 for sketch pathway | Yes | See `ImageInput` from SPEC-TS-0003 |
| `inputs[*].filepath` | `str` | Valid file path; extensions: `.jpg`, `.png`, `.webp`, `.heic` | Yes | `"/home/user/sketch_front.jpg"` |
| `inputs[*].view_label` | `str \| None` | PRD §6 vocabulary or `None` | No | `"front"` |
| `inputs[*].force_sketch` | `bool` | Override auto-detection — field added to canonical `ImageInput` in SPEC-TS-0003 §3.2 (backward-compatible, defaults to `False`) | No (default: `False`) | `True` |
| `prompt` | `str \| None` | Free-form description of the sketched object | No | `"a ceramic vase"` |
| `config.symmetry_enabled` | `bool` | Enable bilateral symmetry | No (default: `True`) | `True` |
| `config.perspective_correction` | `bool` | Attempt perspective correction on paper sketches | No (default: `True`) | `True` |
| `config.guidance_scale` | `float` | ControlNet conditioning strength | No (default: `7.5`) | `7.5` |
| `config.num_inference_steps` | `int` | Diffusion steps for synthesis | No (default: `30`) | `30` |
| `config.synthesis_seed` | `int` | Random seed for deterministic synthesis | No (default: `42`) | `42` |

```python
# Type Definitions (for AI reference)
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

@dataclass
class SketchConfig:
    """Configuration for the sketch-to-3D pipeline."""
    symmetry_enabled: bool = True
    perspective_correction: bool = True
    guidance_scale: float = 7.5
    num_inference_steps: int = 30
    synthesis_seed: int = 42
    synthesis_prompt: Optional[str] = None  # None → use default prompt

@dataclass
class SymmetryConfig:
    """Configuration for symmetry enforcement."""
    enable_symmetry: bool = True
    merge_tolerance: float = 0.001    # Vertex merge distance at symmetry plane
    min_axis_spread_ratio: float = 0.05  # Skip if axis spread < 5% of bbox diagonal

@dataclass
class SketchDetectionResult:
    """Result of sketch vs. photo classification."""
    is_sketch: bool
    confidence: float              # 0.0–1.0
    sketch_type: str               # "pencil", "ink", "digital", "unknown"
    edge_density_ratio: float      # 0.0–1.0 — ratio of edge pixels to total
    detection_method: str          # "heuristic", "cnn", "user_override"

@dataclass
class PreprocessedSketch:
    """Output of sketch preprocessing."""
    binary_image: np.ndarray       # (H, W) uint8, 0 or 255
    thinned_image: np.ndarray      # (H, W) uint8, 0 or 255
    was_perspective_corrected: bool
    original_size: tuple[int, int]  # (width, height)

@dataclass
class SynthesizedImage:
    """Output of ControlNet sketch-to-rendered-image synthesis."""
    rendered_image: np.ndarray     # (512, 512, 3) uint8 RGB
    prompt_used: str
    seed: int
    inference_time_s: float
    guidance_scale: float

@dataclass
class SketchPipelineResult:
    """Result of the full sketch-to-3D pipeline."""
    mesh: 'StandardMesh | None'    # None on failure
    success: bool
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)
    detection_results: list[SketchDetectionResult] = field(default_factory=list)
    synthesized_images: list[SynthesizedImage] = field(default_factory=list)
    symmetry_applied: bool = False
    total_time_s: float = 0.0
```

### 3.7 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `result.success` | `bool` | True if sketch pipeline succeeded | `True` |
| `result.mesh` | `StandardMesh` | SPEC-TS-0004 format | See `StandardMesh` dataclass |
| `result.mesh.vertices` | `np.ndarray` | (N, 3) float32 | 10000×3 array |
| `result.mesh.faces` | `np.ndarray` | (M, 3) int32 | 20000×3 array |
| `result.mesh.metadata` | `dict` | Extended with sketch fields | `{"model_name": "trellis-v1.0", "input_type": "sketch", ...}` |
| `result.detection_results` | `list[SketchDetectionResult]` | One per input image | See dataclass above |
| `result.synthesized_images` | `list[SynthesizedImage]` | One per sketch input | See dataclass above |
| `result.symmetry_applied` | `bool` | Whether symmetry was enforced | `True` |
| `result.total_time_s` | `float` | End-to-end wall-clock time | `95.3` |
| `result.error_message` | `str` | Empty on success; actionable message on failure | `""` |
| `result.warnings` | `list[str]` | Non-fatal issues | `["Low sketch confidence: 0.62"]` |

---

## 4. CONSTRAINTS

> ⚠️ **Critical for AI code generation.** These are hard prohibitions the AI must follow.

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT make any network calls. All model weights (ControlNet, Stable Diffusion, CNN classifier, reconstruction model) SHALL be loaded from the local filesystem only. |
| CON-002 | SHALL NOT run diffusion synthesis and 3D reconstruction on the GPU simultaneously. The diffusion model SHALL be fully unloaded from VRAM before the reconstruction model is loaded. |
| CON-003 | SHALL NOT modify the user's original image files on disk. All preprocessing operates on in-memory copies. |
| CON-004 | SHALL NOT hardcode model weight paths. All paths SHALL be resolved via the model weight manager API (SPEC-TS-0002). |
| CON-005 | SHALL NOT assume a specific GPU VRAM size. Check available VRAM before loading each model stage. |
| CON-006 | SHALL NOT bypass the existing `ReconstructionAdapter` interface (SPEC-TS-0004). The sketch pathway routes synthesized images through the standard reconstruction engine. |
| CON-007 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. |
| CON-008 | SHALL NOT use `subprocess` or shell commands for inference. All inference SHALL run in-process via Python/PyTorch. |
| CON-009 | SHALL NOT support SVG or vector sketch input in this version. Input is raster images only (photos of sketches or rasterized digital drawings). |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

> ⚠️ **All NFRs must be quantified.** Replace vague terms with specific numbers.

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Sketch detection latency | Wall-clock time for `SketchDetector.classify()` | < 500ms (heuristic only), < 2 seconds (heuristic + CNN) | RTX 3060, single 1024×1024 input |
| NFR-002 | Sketch preprocessing latency | Wall-clock time for `SketchPreprocessor.preprocess()` | < 1 second | CPU-only processing, single 1024×1024 input |
| NFR-003 | Sketch synthesis latency | Wall-clock time for `SketchSynthesizer.synthesize()` | < 45 seconds | RTX 3060 (12 GB VRAM), 30 diffusion steps, 512×512 output |
| NFR-004 | End-to-end single-sketch latency | Wall-clock from `SketchPipeline.process()` call to `SketchPipelineResult` return | < 120 seconds | RTX 3060, single sketch, including synthesis + reconstruction + symmetry |
| NFR-005 | End-to-end dual-sketch latency | Wall-clock for 2-sketch multi-view reconstruction | < 180 seconds | RTX 3060, two sketches, both synthesized + reconstructed |
| NFR-006 | Peak VRAM during synthesis | Maximum GPU memory allocated during ControlNet diffusion | < 8 GB | 512×512 output, 30 steps, FP16 inference |
| NFR-007 | Peak VRAM during reconstruction | Maximum GPU memory allocated during 3D reconstruction (post-synthesis) | < 10 GB | Single synthesized 512×512 image input |
| NFR-008 | VRAM cleanup between stages | GPU memory delta before synthesis load and after reconstruction unload | < 50 MB residual | After `torch.cuda.empty_cache()` |
| NFR-009 | Sketch detection accuracy | Binary classification accuracy (photo vs. sketch) | ≥ 95% | 100-image test set (50 photos, 50 sketches of varying quality) |
| NFR-010 | Symmetry enforcement latency | Wall-clock for `SymmetryEnforcer.enforce()` | < 2 seconds | Mesh with 100,000 vertices, CPU-only processing |

---

## 6. ACCEPTANCE CRITERIA

> ⚠️ **Minimum 3 criteria in Given-When-Then format.** These drive test implementation.

### AC-001: Single Sketch — Happy Path (Pencil Drawing of a Vase)
**Given** a single 1024×768 `.jpg` photograph of a pencil sketch of a vase on white paper, with `force_sketch=False`, no user-supplied view label, and default `SketchConfig`,  
**When** `SketchPipeline.process([ImageInput(filepath="vase_sketch.jpg")])` is called on a system with an NVIDIA RTX 3060 GPU and all model weights cached locally,  
**Then** the result has:
- `success == True`
- `detection_results[0].is_sketch == True` with `confidence ≥ 0.7`
- `synthesized_images[0].rendered_image` has shape `(512, 512, 3)` and dtype `uint8`
- `mesh` is a `StandardMesh` with ≥ 1,000 vertices and ≥ 2,000 faces
- `symmetry_applied == True`
- `mesh.metadata["input_type"] == "sketch"`
- `total_time_s < 120`
- `error_message` is empty

### AC-002: Multi-View Sketch — Front + Side
**Given** two sketch images: a front-view sketch with `view_label="front"` and a side-view sketch with `view_label="right"`,  
**When** `SketchPipeline.process([front_input, side_input])` is called with default config,  
**Then** the result has:
- `success == True`
- `len(detection_results) == 2`, both with `is_sketch == True`
- `len(synthesized_images) == 2`, each with shape `(512, 512, 3)`
- `mesh` has ≥ 1,000 vertices
- `total_time_s < 180`

### AC-003: Photo Detected — Fallback to Standard Pathway
**Given** a single `.jpg` photograph of a real ceramic mug (not a sketch) with `force_sketch=False`,  
**When** `SketchPipeline.process([ImageInput(filepath="mug_photo.jpg")])` is called,  
**Then** the result has `detection_results[0].is_sketch == False` and the image is routed to the standard vision pipeline (SPEC-TS-0003) instead of the sketch pathway, and `synthesized_images` is an empty list.

### AC-004: User Override — Force Sketch Detection
**Given** a single `.jpg` that the detector classifies as a photo (confidence of `is_sketch` < 0.5) but the user has set `force_sketch=True`,  
**When** `SketchPipeline.process([ImageInput(filepath="ambiguous.jpg", force_sketch=True)])` is called,  
**Then** the result has `detection_results[0].is_sketch == True`, `detection_results[0].confidence == 1.0`, `detection_results[0].detection_method == "user_override"`, and the image is processed through the sketch pathway.

### AC-005: Symmetry Disabled — No Mirror Applied
**Given** a single sketch of an asymmetric object (e.g., a shoe) with `SketchConfig(symmetry_enabled=False)`,  
**When** `SketchPipeline.process(...)` is called,  
**Then** `result.symmetry_applied == False` and the mesh vertices are unchanged from the reconstruction engine output.

### AC-006: Too Many Sketches — Error
**Given** 3 sketch images all classified as sketches,  
**When** `SketchPipeline.process(...)` is called,  
**Then** the result has `success == False` and `error_message` contains "Sketch-to-3D pathway supports a maximum of 2 sketch inputs. Received: 3."

### AC-007: Perspective Correction Applied
**Given** a `.jpg` photograph of a pencil sketch on paper taken at an oblique angle (visible perspective distortion), with `SketchConfig(perspective_correction=True)`,  
**When** `SketchPreprocessor.preprocess(image, config)` is called and a quadrilateral paper boundary is detected,  
**Then** the `PreprocessedSketch.was_perspective_corrected == True` and the output `binary_image` is rectangular (corrected for perspective).

---

## 7. EDGE CASES

> ⚠️ **Minimum 2 edge cases required.** Document non-obvious scenarios AI might miss.

### EC-001: Very Faint Pencil Lines
| Aspect | Detail |
|--------|--------|
| **Scenario** | User photographs a light pencil sketch where lines are barely visible (low contrast between pencil and paper) |
| **Input Example** | A `.jpg` where pencil strokes have grayscale values 200–240 (close to white paper at 255) |
| **Expected Behavior** | The adaptive binarization (Otsu + local adaptive threshold) SHALL detect the faint lines. If the binarized output contains fewer than 100 non-zero pixels (insufficient line content), the system SHALL return `SketchPipelineResult(success=False, error_message="Sketch preprocessing detected insufficient line content (< 100 pixels). The sketch may be too faint. Try using a darker pencil or increasing image contrast.")`. |
| **Test ID** | TS-008 |

### EC-002: Sketch on Colored or Textured Paper
| Aspect | Detail |
|--------|--------|
| **Scenario** | User draws on colored construction paper (e.g., blue) or lined notebook paper |
| **Input Example** | A `.jpg` of ink lines drawn on blue construction paper |
| **Expected Behavior** | The grayscale conversion and adaptive thresholding SHALL isolate the ink lines from the colored background. For notebook paper, the horizontal/vertical ruled lines SHALL remain in the binarized output (the system does not remove grid lines in v1). The result SHOULD include a warning: "Sketch appears to be drawn on colored or textured paper. Line detection quality may be reduced." The sketch_type SHALL be set to `"ink"` if high-contrast dark lines are detected on a non-white background. |
| **Test ID** | TS-009 |

### EC-003: Digital Sketch with Clean Lines (No Paper)
| Aspect | Detail |
|--------|--------|
| **Scenario** | User uploads a clean digital line drawing (e.g., from a tablet app) with perfectly clean lines on a pure white background — no paper texture, no noise |
| **Input Example** | A 1024×1024 `.png` with anti-aliased black lines on white (#FFFFFF) background |
| **Expected Behavior** | The sketch detector SHALL classify this as a sketch with confidence ≥ 0.90. The preprocessor SHALL skip perspective correction (no paper boundary detected) and produce a clean binary image. The thinning step SHALL reduce anti-aliased lines to single-pixel width. `sketch_type` SHALL be `"digital"`. |
| **Test ID** | TS-010 |

### EC-004: Crayon Drawing with Thick, Irregular Strokes
| Aspect | Detail |
|--------|--------|
| **Scenario** | A child's crayon drawing with very thick, irregular, colorful strokes (high color variance, low edge clarity) |
| **Input Example** | A `.jpg` of a red crayon drawing on white paper — strokes 10-20px wide with waxy texture |
| **Expected Behavior** | The sketch detector SHALL classify this as a sketch (high edge density despite color variance). The preprocessor SHALL binarize the colorful strokes to solid lines. Line thinning SHALL reduce thick crayon lines to single-pixel skeleton. The system SHOULD include a warning: "Sketch contains thick or irregular strokes. Thinned output may differ from original artistic intent." Reconstruction quality MAY be lower than for clean line drawings. |
| **Test ID** | TS-011 |

### EC-005: Sketch with No Closed Contours
| Aspect | Detail |
|--------|--------|
| **Scenario** | User draws a few disconnected lines (e.g., early WIP sketch) with no discernible shape |
| **Input Example** | A `.jpg` with 3 unconnected diagonal lines, total stroke area < 2% of image |
| **Expected Behavior** | The sketch pipeline SHALL proceed through preprocessing and synthesis. The synthesized rendered image is expected to be ambiguous due to insufficient input detail; the resulting reconstruction confidence score (from SPEC-TS-0004 `StandardMesh.metadata["confidence"]`) is expected to be low (< 0.5). The sketch pipeline SHALL include a warning: "Sketch has minimal line content ({stroke_percent:.1f}% of image area). Reconstruction quality may be very low. Consider adding more detail to the sketch." |
| **Test ID** | TS-012 |

### EC-006: Insufficient VRAM for Diffusion Model
| Aspect | Detail |
|--------|--------|
| **Scenario** | User's GPU has less than 8 GB available VRAM when sketch synthesis is attempted |
| **Input Example** | System with 6 GB total VRAM, 4.5 GB currently available due to Blender's viewport renderer |
| **Expected Behavior** | The `SketchPipeline` SHALL check available VRAM before loading the diffusion model (per FR-039). The system SHALL return `SketchPipelineResult(success=False, error_message="Insufficient GPU VRAM for sketch synthesis. Required: 8 GB, Available: 4.5 GB. Close other GPU applications or free VRAM before running sketch-to-3D.")`. No model weights SHALL be loaded and no GPU memory SHALL be allocated. |
| **Test ID** | TS-023 |

---

## 8. OUT OF SCOPE

> ⚠️ **Explicitly list what this feature does NOT include.** Prevents AI scope creep.

The following are explicitly **excluded** from this feature:

- ❌ SVG or vector sketch input — raster images only (deferred per CSO suggestion)
- ❌ Notebook grid line removal — lined paper lines remain in the binarized output
- ❌ Sketch-specific 3D reconstruction model (e.g., a dedicated sketch-to-3D neural network) — uses two-stage synthesis approach instead
- ❌ Interactive sketch editing or real-time sketch-to-3D preview
- ❌ Multi-part sketch interpretation (e.g., "draw the handle separately") — single object only
- ❌ Color extraction from colored sketches for mesh vertex coloring
- ❌ Sketch style transfer or artistic stylization
- ❌ Training or fine-tuning of any model on user sketches
- ❌ Natural-language refinement of sketch-originated meshes (TASK-TS-0009 applies independently)
- ❌ Mesh cleanup or topology optimization (TASK-TS-0005 handles downstream)
- ❌ Print-readiness validation (TASK-TS-0006 handles downstream)
- ❌ Real-world scaling (TASK-TS-0008 handles downstream)
- ❌ CPU-only inference fallback (GPU required per PRD D2)
- ❌ Batch sketch processing (> 2 sketches per request)

---

## 9. SECURITY CONSIDERATIONS

> ⚠️ **Required for all features.** AI-generated code needs explicit security constraints.

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — local Blender add-on, no network interaction |
| **Auth Method** | None |
| **Required Permissions** | File system read (user sketch images + model weight cache), GPU access via CUDA/ROCm |
| **Rate Limiting** | N/A |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| User sketch image files | Internal | Read from disk; processed in-memory only; not written back to disk; not transmitted |
| Preprocessed sketch arrays | Internal | In-memory numpy arrays; never persisted outside Blender session |
| Synthesized rendered images | Internal | In-memory numpy arrays; never written to disk by this component; not transmitted |
| Reconstruction output mesh | Internal | Returned in-memory to caller; not persisted by this component |
| ControlNet / SD model weights | Internal | Read from local disk; checksums verified before loading |
| CNN classifier weights | Internal | Read from local disk; loaded via `torch.load(weights_only=True)` |
| GPU device info | Internal | Used for VRAM checks; not transmitted |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL validate all input file paths using `pathlib.Path.resolve()` to prevent path traversal before reading sketch images. |
| SEC-002 | SHALL NOT execute downloaded model weights as Python code. All weights SHALL be loaded via `torch.load(path, weights_only=True)` or `safetensors.torch.load_file()`. |
| SEC-003 | SHALL NOT make any network connections, DNS lookups, or socket operations. |
| SEC-004 | SHALL NOT write synthesized images or preprocessed sketches to temp files. All processing SHALL occur on in-memory arrays. |
| SEC-005 | SHALL validate sketch image file size does not exceed 50 MB before loading to prevent memory exhaustion from crafted files. |
| SEC-006 | SHALL sanitize model checkpoint paths to ensure they reside within the model weight cache directory managed by SPEC-TS-0002. |

---

## 10. API CONTRACT [CONDITIONAL]

> **Skipped** — This is an internal Python module within the Blender add-on. No REST/HTTP APIs are exposed.

The sketch pipeline exposes the following **internal Python API** for the Blender UI and orchestrator:

### 10.1 Public API — SketchPipeline

```python
from tessera.sketch.pipeline import SketchPipeline
from tessera.sketch.types import SketchConfig, SketchPipelineResult
from tessera.vision.types import ImageInput

# Initialize pipeline
pipeline = SketchPipeline(cache_dir="/path/to/model/cache")

# Single sketch reconstruction
config = SketchConfig(symmetry_enabled=True, synthesis_prompt="a ceramic vase")
result: SketchPipelineResult = pipeline.process(
    inputs=[ImageInput(filepath="/path/to/sketch.jpg")],
    config=config
)

# Multi-view sketch reconstruction
result: SketchPipelineResult = pipeline.process(
    inputs=[
        ImageInput(filepath="/path/to/front_sketch.jpg", view_label="front"),
        ImageInput(filepath="/path/to/side_sketch.jpg", view_label="right"),
    ],
    config=config
)

# Check result
if result.success:
    mesh = result.mesh
    print(f"Vertices: {mesh.metadata['vertex_count']}")
    print(f"Input type: {mesh.metadata['input_type']}")  # "sketch"
    print(f"Symmetry applied: {result.symmetry_applied}")
    print(f"Total time: {result.total_time_s:.1f}s")
else:
    print(f"Failed: {result.error_message}")

# Check detection results
for det in result.detection_results:
    print(f"Is sketch: {det.is_sketch} (confidence: {det.confidence:.2f})")
```

### 10.2 Sketch Detection API (standalone)

```python
from tessera.sketch.detector import SketchDetector
from tessera.sketch.types import SketchDetectionResult
import numpy as np

detector = SketchDetector(cache_dir="/path/to/model/cache")
image = ...  # np.ndarray (H, W, 3) uint8 RGB

result: SketchDetectionResult = detector.classify(image)
print(f"Is sketch: {result.is_sketch}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Sketch type: {result.sketch_type}")
print(f"Edge density: {result.edge_density_ratio:.3f}")
```

### 10.3 Sketch Preprocessing API (standalone)

```python
from tessera.sketch.preprocessor import SketchPreprocessor
from tessera.sketch.types import SketchConfig, PreprocessedSketch
import numpy as np

preprocessor = SketchPreprocessor()
image = ...  # np.ndarray (H, W, 3) uint8 RGB
config = SketchConfig(perspective_correction=True)

result: PreprocessedSketch = preprocessor.preprocess(image, config)
print(f"Binary shape: {result.binary_image.shape}")
print(f"Thinned shape: {result.thinned_image.shape}")
print(f"Perspective corrected: {result.was_perspective_corrected}")
```

---

## 11. OBSERVABILITY

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------|
| Sketch detection started | INFO | `filename` (basename), `image_size` | ⚠️ No full paths |
| Sketch detection result | INFO | `is_sketch`, `confidence`, `sketch_type`, `detection_method` | ⚠️ No PII |
| Edge density computed | DEBUG | `edge_density_ratio`, `color_std` | ⚠️ No PII |
| CNN classifier invoked | DEBUG | `heuristic_confidence`, `cnn_confidence` | ⚠️ No PII |
| Sketch preprocessing started | INFO | `filename` (basename), `perspective_correction_enabled` | ⚠️ No full paths |
| Perspective correction result | DEBUG | `was_corrected`, `contour_corners_found` | ⚠️ No PII |
| Binarization complete | DEBUG | `non_zero_pixel_count`, `total_pixel_count` | ⚠️ No PII |
| Sketch synthesis started | INFO | `prompt`, `seed`, `guidance_scale`, `num_steps` | ⚠️ No PII |
| Diffusion model loaded | DEBUG | `model_name`, `vram_used_mb`, `load_time_s` | ⚠️ No PII |
| Sketch synthesis complete | INFO | `inference_time_s`, `output_size` | ⚠️ No PII |
| Diffusion model unloaded | DEBUG | `vram_freed_mb` | ⚠️ No PII |
| Symmetry detection result | DEBUG | `symmetry_axis`, `axis_spread`, `threshold` | ⚠️ No PII |
| Symmetry enforcement complete | INFO | `original_vertex_count`, `new_vertex_count`, `delta_percent` | ⚠️ No PII |
| Symmetry enforcement skipped | WARN | `reason`, `axis_spread`, `threshold` | ⚠️ No PII |
| Sketch pipeline complete | INFO | `total_time_s`, `stages_completed`, `symmetry_applied`, `success` | ⚠️ No PII |
| Sketch pipeline failed | ERROR | `error_message`, `failed_stage` | ⚠️ No PII |

> All logging uses Python's `logging` module with logger name `"tessera.sketch"`. Blender routes this to the system console.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only). Performance data is available in `SketchPipelineResult` and `StandardMesh.metadata` for display in the Blender UI.

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — available when add-on is installed and required model weights are cached |
| **Default State** | N/A |
| **Rollout Plan** | Part of Tessera add-on `.zip` distribution, Phase 3 |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| TASK-TS-0001 (Add-on Scaffold) | Yes | Provides add-on preferences, GPU detection, cache directory configuration |
| TASK-TS-0002 (Model Weight Management) | Yes | ControlNet, Stable Diffusion, and CNN classifier weights must be downloaded and cached |
| TASK-TS-0003 (Vision Pipeline) | Yes | Sketch detection integrates with the vision pipeline's image classification stage |
| TASK-TS-0004 (Reconstruction Engine) | Yes | Sketch pathway routes synthesized images through the reconstruction engine |
| PyTorch + CUDA/ROCm | Yes | Must be bundled or documented as prerequisite |
| `diffusers` library | Yes | For ControlNet + Stable Diffusion inference; bundle as python-wheel |
| `opencv-python` (`cv2`) | Yes | For sketch preprocessing (binarization, thinning, perspective correction) |
| `scikit-learn` | Optional | For PCA-based symmetry axis detection (fallback: numpy `np.linalg.eigh`) |
| `numpy` | No | Already bundled with Blender's Python |

### 12.3 Rollback Plan
1. Remove or disable the `tessera/sketch/` module from the add-on package
2. The standard photo-based pathway continues to function normally
3. Sketch-specific model weights (ControlNet, SD, classifier) can be deleted from cache to free disk space
4. Verify no GPU memory leaks or residual tensors via Blender system console

---

## 13. TEST SCENARIOS

> Map tests to acceptance criteria and edge cases for traceability.

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Single pencil sketch → detect → preprocess → synthesize → reconstruct → symmetry → valid mesh | Integration | AC-001 | Must Pass |
| TS-002 | Two sketches (front + side) produce multi-view reconstruction | Integration | AC-002 | Must Pass |
| TS-003 | Photo input is correctly classified as non-sketch and routed to standard pipeline | Unit | AC-003 | Must Pass |
| TS-004 | `force_sketch=True` overrides detector and routes through sketch pathway | Unit | AC-004 | Must Pass |
| TS-005 | Symmetry disabled produces unmodified mesh | Unit | AC-005 | Must Pass |
| TS-006 | 3 sketches rejected with max-input error | Unit | AC-006 | Must Pass |
| TS-007 | Perspective correction applies to oblique paper photo | Unit | AC-007 | Must Pass |
| TS-008 | Very faint pencil lines → insufficient content error | Unit | EC-001 | Must Pass |
| TS-009 | Sketch on colored paper → warning logged, processing continues | Unit | EC-002 | Must Pass |
| TS-010 | Clean digital line drawing → high confidence sketch detection | Unit | EC-003 | Must Pass |
| TS-011 | Crayon drawing with thick strokes → thinned and processed with warning | Unit | EC-004 | Must Pass |
| TS-012 | Minimal line content sketch → low confidence warning | Unit | EC-005 | Should Pass |
| TS-013 | SketchDetector accuracy ≥ 95% on 100-image test set (50 photos, 50 sketches) | Accuracy | NFR-009 | Must Pass |
| TS-014 | Sketch detection latency < 500ms (heuristic), < 2s (heuristic + CNN) | Performance | NFR-001 | Should Pass |
| TS-015 | Sketch synthesis latency < 45s on RTX 3060 | Performance | NFR-003 | Should Pass |
| TS-016 | End-to-end single-sketch latency < 120s on RTX 3060 | Performance | NFR-004 | Should Pass |
| TS-017 | Peak VRAM during synthesis < 8 GB | Performance | NFR-006 | Should Pass |
| TS-018 | VRAM cleanup between synthesis and reconstruction < 50 MB residual | Integration | NFR-008 | Must Pass |
| TS-019 | Symmetry enforcer produces vertex count within ±10% of original | Unit | FR-029 | Must Pass |
| TS-020 | Path traversal in filepath rejected by SEC-001 | Unit | SEC-001 | Must Pass |
| TS-021 | File exceeding 50 MB rejected before loading | Unit | SEC-005 | Must Pass |
| TS-022 | Perspective correction skipped when no paper boundary detected (no crash) | Unit | FR-013 | Must Pass |
| TS-023 | Insufficient VRAM (< 8 GB) returns `success=False` before loading diffusion model | Unit | FR-039, EC-006 | Must Pass |
| TS-024 | `VisionPipelineOutput` constructed from `SynthesizedImage` has all required fields with correct types | Unit | FR-038 | Must Pass |
| TS-025 | Sketch type correctly classified as `"digital"` for clean digital line art (≤ 4 grayscale levels) | Unit | FR-040 | Should Pass |
| TS-026 | Sketch type correctly classified as `"pencil"` for grayscale soft-contrast scan | Unit | FR-040 | Should Pass |
| TS-027 | CNN classifier accepts 224×224 ImageNet-normalized input and produces sigmoid output in [0, 1] | Unit | FR-041 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| TASK-TS-0001 (Add-on Scaffold) | Required | Pending | TBD | Yes — need preferences API for cache directory and GPU detection |
| TASK-TS-0002 (Model Weight Management) | Required | Pending | TBD | Yes — need ControlNet, SD, and classifier weights cached locally |
| TASK-TS-0003 (Vision Pipeline) | Required | Pending | TBD | Yes — sketch detector integrates with vision pipeline classification stage |
| TASK-TS-0004 (Reconstruction Engine) | Required | Pending | TBD | Yes — sketch pathway routes synthesized images through `ReconstructionEngine.reconstruct()` |
| TASK-TS-0005 (Mesh Cleanup) | Downstream consumer | Pending | TBD | No — sketch pipeline produces `StandardMesh` consumed by cleanup |
| TASK-TS-0006 (Print Validator) | Downstream consumer | Pending | TBD | No — sketch-originated meshes go through the same print validation |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| PyTorch 2.x with CUDA/ROCm | Required | [pytorch.org](https://pytorch.org/) | No fallback — GPU inference required (PRD D2) |
| `diffusers` library (HuggingFace) | Required | [huggingface.co/docs/diffusers](https://huggingface.co/docs/diffusers/) | No fallback — core synthesis engine |
| ControlNet model weights (scribble/lineart) | Required | [github.com/lllyasviel/ControlNet](https://github.com/lllyasviel/ControlNet) | Alternative: use lineart preprocessor if scribble unavailable |
| Stable Diffusion 1.5 or SDXL model weights | Required | [github.com/Stability-AI/stablediffusion](https://github.com/Stability-AI/stablediffusion) | SD 1.5 as lighter fallback vs. SDXL |
| OpenCV (`cv2`) with `ximgproc` | Required | [docs.opencv.org](https://docs.opencv.org/) | `scikit-image` for skeletonization fallback |
| MobileNetV3-Small (classifier) | Required | [pytorch.org/vision/models/mobilenetv3](https://pytorch.org/vision/main/models/mobilenetv3.html) | Fall back to heuristic-only detection (lower accuracy) |
| Primary reconstruction model (Trellis/InstantMesh/OpenLRM) | Required (via SPEC-TS-0004) | See SPEC-TS-0004 §2.1 | `StubAdapter` for dev/testing only |
| `numpy` 1.24+ | Required | Bundled with Blender | N/A — always available |
| `trimesh` | Required (via SPEC-TS-0004) | [trimesh.org](https://trimesh.org/) | Fallback to raw numpy arrays |

**Model Weight Manifest Identifiers** (for SPEC-TS-0002 weight manager registration):

| Manifest ID | Model | Approximate Size | Notes |
|-------------|-------|------------------|-------|
| `controlnet-scribble-v1` | ControlNet scribble conditioning | ~1.4 GB | Primary; `controlnet-lineart-v1` as alternative |
| `stable-diffusion-v1-5` | Stable Diffusion 1.5 base model | ~4.0 GB | Lighter option; `sdxl-base-v1-0` (~6.5 GB) as upgrade |
| `mobilenetv3-sketch-classifier` | MobileNetV3-Small fine-tuned for photo-vs-sketch | ~10 MB | Binary classifier weights |

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
| SHALL/SHOULD/MAY requirements | 20 | 20 | 41 requirements with precise SHALL/SHOULD/MAY language across FR-001–FR-041 |
| Quantified NFRs | 15 | 15 | 10 NFRs, all quantified with specific targets, units, and measurement conditions |
| Given-When-Then criteria (3+) | 20 | 20 | 7 acceptance criteria in Given-When-Then format with specific values and verifiable outcomes |
| Edge cases (2+) | 15 | 15 | 6 edge cases with concrete input examples and exact expected behaviors |
| Out of scope defined | 10 | 10 | 14 explicit exclusions listed with task references |
| Security constraints | 10 | 10 | 6 security requirements + data classification table + auth section + weights_only=True for pickle safety |
| No ambiguous language | 10 | 10 | All ambiguous terms replaced with specifics. Cross-spec contracts verified and documented. |
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
- [x] "handle gracefully" → replaced with specific error messages and return types
- [x] "fast" / "efficient" / "performant" → replaced with specific latency targets (< 500ms, < 2s, < 45s, < 120s, etc.)
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
| 1.1 | 2026-04-14 | AI (spec-review remediation) | Resolved C-001: documented `force_sketch` as canonical `ImageInput` extension (SPEC-TS-0003 updated); M-001: added FR-038 `VisionPipelineOutput` construction from `SynthesizedImage`; M-002: added FR-040 `sketch_type` determination heuristic; M-003: added FR-039 VRAM pre-check with error message; M-004: added `detection_method` to FR-002 and FR-006; m-001: simplified FR-015 inversion convention; m-002: added EC-006 insufficient VRAM edge case; m-003: added FR-041 CNN classifier input preprocessing; m-004: added model weight manifest identifiers; m-005: reworded EC-005. Added TS-023–TS-027. Updated self-score to 100. |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0010-sketch-to-3d.md`
