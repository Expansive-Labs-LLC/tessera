# Feature Specification: Production Hardening, Testing & Documentation

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0011 |
| **Task ID** | TASK-TS-0011 |
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
Phases 1–3 of Tessera deliver features: vision analysis, reconstruction, mesh cleanup, print validation, multi-view alignment, NL refinement, sketch-to-3D, scaling, and orientation. Without Phase 4, these features remain prototype-quality — cryptic error messages when VRAM runs out, no performance profiling, no automated regression detection, and no onboarding documentation. TASK-TS-0011 transforms Tessera from a working prototype into a product users can trust. It covers six deliverables from PRD §9 Phase 4 (M4.1–M4.5) and §10 Success Metrics: (1) error handling with actionable UI messages, (2) performance optimization targeting <5 min end-to-end for simple objects, (3) enhanced 3MF export with embedded print metadata, (4) an automated golden-mesh regression test suite, (5) cross-platform documentation (Windows, macOS Apple Silicon, Linux), and (6) a curated example gallery of 10+ objects.

### 1.2 User Story
**As a** user trying Tessera for the first time,  
**I want** clear error messages when something goes wrong, fast performance, and documentation to help me get started,  
**So that** I can confidently use the tool without frustration.

### 1.3 Proposed Approach
Build six interconnected subsystems within the existing Tessera add-on: (1) a centralized `ErrorHandler` that catches exceptions from all pipeline stages (vision, reconstruction, cleanup, validation, export), classifies them by severity and category, and surfaces actionable messages in Blender's UI via `self.report()` and a dedicated error panel; (2) a `PerformanceProfiler` that instruments each pipeline stage with `time.perf_counter()` timing, identifies bottlenecks, and applies optimizations (lazy model loading, GPU memory pooling, batch operations); (3) a `ThreeMFMetadataExporter` that extends the existing 3MF export (SPEC-TS-0006) to embed print settings, infill suggestions, and model metadata in the 3MF XML structure; (4) a `GoldenMeshTestSuite` using `pytest` with deterministic mesh hash comparisons that runs in CI without GPU; (5) a documentation site using MkDocs with user guide, API reference, and tutorial content; (6) a gallery of 10+ example objects with input images, generated meshes, and print photos.

### 1.4 Success Metrics

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Print success rate on test suite | N/A | ≥ 90% of test-suite objects produce print-successful STLs (note: exceeds PRD §10 global target of ≥85%; aligns with Phase 4 exit criteria in PRD §9 which specifies 90%) | Automated validation + manual test prints on FDM + SLA printers |
| First-use time-to-export | N/A | < 10 minutes from install to first STL export following tutorial | Timed user test with 5 participants following documentation |
| Error message actionability | N/A | 100% of caught errors display a message with ≥ 1 suggested resolution | Automated audit of error catalog entries |
| End-to-end latency (simple objects) | N/A | < 5 minutes wall-clock | `time.perf_counter()` from image upload to STL export on RTX 3060 (12 GB VRAM) |
| CI test suite pass rate | N/A | 100% of golden-mesh tests pass on every commit | GitHub Actions CI pipeline |

---

## 2. TECHNICAL CONTEXT

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/__init__.py` | Add-on scaffold (SPEC-TS-0001) | Module registration, class collection pattern |
| `tessera/validator/print_validator.py` | Print validation chain (SPEC-TS-0006) | Chain-of-responsibility pattern, diagnostics dict |
| `tessera/export/export_pipeline.py` | Export pipeline (SPEC-TS-0006) | Export flow, duplicate-then-export pattern |
| `tessera/export/threemf_exporter.py` | Basic 3MF export (SPEC-TS-0006) | Extending with metadata |
| `tessera/mesh/cleanup.py` | Cleanup pipeline (SPEC-TS-0005) | Step execution, diagnostics reporting |
| `tessera/vision/pipeline.py` | Vision pipeline (SPEC-TS-0003) | GPU model loading, VRAM management |
| `tessera/reconstruction/adapters/` | Reconstruction adapters (SPEC-TS-0004) | Adapter pattern, model inference |
| `tessera/properties.py` | Scene-level PropertyGroup | Extending scene properties |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`, `bmesh`, `mathutils`)
- **Testing:** `pytest` run via `blender --background --python` for headless testing; `pytest` standalone for non-Blender tests
- **Documentation:** MkDocs with Material theme; bundled `README.md` + in-add-on help panel
- **3MF Metadata:** XML manipulation via Python `xml.etree.ElementTree` (stdlib)
- **Performance:** `time.perf_counter()`, `tracemalloc`, `cProfile`
- **CI:** GitHub Actions (Ubuntu runner, no GPU — mesh comparison only)
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── errors/
│   ├── __init__.py
│   ├── handler.py              # ErrorHandler: centralized exception catching + classification
│   ├── catalog.py              # ERROR_CATALOG: {code → message, severity, resolution}
│   ├── categories.py           # ErrorCategory enum: VRAM, INPUT, MODEL, EXPORT, BLENDER
│   └── ui_reporter.py          # UIReporter: surfaces errors in Blender panels + info area
├── perf/
│   ├── __init__.py
│   ├── profiler.py             # PerformanceProfiler: per-stage timing + memory tracking
│   ├── optimizer.py            # Optimization strategies (lazy loading, batching)
│   └── report.py               # PerfReport: JSON timing breakdown
├── export/
│   ├── threemf_metadata.py     # ThreeMFMetadataExporter: print settings in 3MF XML
│   └── ... (existing from SPEC-TS-0006)
├── testing/
│   ├── __init__.py
│   ├── golden_mesh.py          # GoldenMeshRegistry: stores/loads reference mesh hashes
│   ├── mesh_hash.py            # Deterministic mesh hashing (vertex/face canonical form)
│   └── conftest.py             # pytest fixtures for Blender headless
├── operators/
│   ├── error_ops.py            # OT_ShowErrorDetails
│   └── ... (existing)
├── ui/
│   ├── error_panel.py          # Error log panel in sidebar
│   ├── perf_panel.py           # Performance timing display
│   └── ... (existing)
docs/
├── mkdocs.yml                  # MkDocs configuration
├── docs/
│   ├── index.md                # Landing page
│   ├── installation.md         # Windows / macOS (Apple Silicon) / Linux
│   ├── quickstart.md           # First-use tutorial (< 10 min)
│   ├── user-guide/
│   │   ├── image-input.md
│   │   ├── reconstruction.md
│   │   ├── refinement.md
│   │   └── export.md
│   ├── api/
│   │   ├── adapters.md         # Extending reconstruction adapters
│   │   └── pipeline.md         # Pipeline API reference
│   ├── gallery/
│   │   └── index.md            # 10+ example objects
│   └── troubleshooting.md      # Common errors + resolutions
tests/
├── golden_meshes/              # Reference .npz files (vertices + faces hashes)
│   ├── mug_simple.npz
│   ├── vase_organic.npz
│   └── ... (10+ objects)
├── test_golden_mesh.py         # Golden-mesh comparison tests (no GPU)
├── test_error_handler.py       # Error handling unit tests
├── test_perf_profiler.py       # Profiler unit tests
├── test_threemf_metadata.py    # 3MF metadata unit tests
└── conftest.py                 # Shared fixtures
```

**Data flow — Error Handling:**
```
Any pipeline stage raises exception
  → ErrorHandler.catch(exception, stage_name)
    → Classify: ErrorCategory + severity (CRITICAL / ERROR / WARNING / INFO)
    → Look up ERROR_CATALOG[error_code] → {message, resolution_steps}
    → UIReporter.show(error_code, message, resolution_steps)
      → self.report({'ERROR'}, user_message) in Blender Info area
      → Append to error log panel (scrollable history)
    → Log full traceback at DEBUG level for developer debugging
```

**Data flow — Golden-Mesh Testing:**
```
CI pipeline (no GPU):
  tests/golden_meshes/mug_simple.npz  (pre-computed reference)
    → Load reference vertex_hash + face_hash
    → Load test output mesh .npz (generated during development, committed to repo)
    → Compare hashes: vertex_hash_test == vertex_hash_ref AND face_hash_test == face_hash_ref
    → PASS if match, FAIL if differs (regression detected)
```

---

## 3. FUNCTIONAL REQUIREMENTS

### 3.1 Error Handling (M4.1)

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL implement a centralized `ErrorHandler` class that wraps all pipeline stages (vision analysis, reconstruction, mesh cleanup, print validation, export) in try/except blocks and catches all exceptions. |
| FR-002 | The system SHALL maintain an `ERROR_CATALOG` dictionary mapping error codes (string keys in format `\"BF-EXXX\"`) to structured entries containing: `message` (str, user-facing), `severity` (one of `\"CRITICAL\"`, `\"ERROR\"`, `\"WARNING\"`, `\"INFO\"`), `category` (one of `\"VRAM\"`, `\"INPUT\"`, `\"MODEL\"`, `\"EXPORT\"`, `\"BLENDER\"`, `\"SYSTEM\"`), and `resolution_steps` (list of strings, each a concrete action the user can take). |
| FR-003 | The error catalog SHALL contain entries for at minimum the following 16 error scenarios: (1) `BF-E001` VRAM exhaustion during model loading, (2) `BF-E002` VRAM exhaustion during inference, (3) `BF-E003` unsupported image format, (4) `BF-E004` image resolution too low (< 256×256 px), (5) `BF-E005` image is blurry (Laplacian variance < 100), (6) `BF-E006` model weight file not found, (7) `BF-E007` model weight file corrupted (hash mismatch), (8) `BF-E008` reconstruction produced empty mesh, (9) `BF-E009` reconstruction timeout (> 120 seconds), (10) `BF-E010` mesh cleanup failed to produce manifold output, (11) `BF-E011` export directory not writable, (12) `BF-E012` Blender version incompatible, (13) `BF-E013` no CUDA/ROCm GPU detected, (14) `BF-E014` Python dependency missing, (15) `BF-E015` disk space insufficient for model weights (< 2 GB free), (16) `BF-E016` 3MF exporter add-on not available in Blender. |
| FR-004 | Each error message displayed to the user SHALL follow the format: `\"[BF-EXXX] {message}. Try: {resolution_steps[0]}.\"` The full resolution steps list SHALL be viewable via the error details panel. |
| FR-005 | The system SHALL display error messages in the Blender Info area using `self.report({'ERROR'}, formatted_message)` for severity `CRITICAL` and `ERROR`, and `self.report({'WARNING'}, formatted_message)` for severity `WARNING`. |
| FR-006 | The system SHALL maintain a scrollable error log in a dedicated sidebar panel (`TESSERA_PT_error_log`) showing the last 50 errors with timestamp, code, severity icon, and truncated message. Clicking an entry SHALL expand to show full details and resolution steps. |
| FR-007 | The system SHALL implement graceful degradation for VRAM exhaustion: when a `torch.cuda.OutOfMemoryError` (or equivalent) is caught during model loading, the system SHALL (a) free all GPU tensors via `torch.cuda.empty_cache()`, (b) log the available/required VRAM, and (c) suggest switching to a smaller model variant in the error message. |
| FR-008 | The system SHALL validate input images before pipeline execution by checking: file exists, format is in `{jpg, jpeg, png, webp, heic}`, file size > 0 bytes, image dimensions ≥ 256×256 px. Failures SHALL raise a specific `BF-E003` or `BF-E004` error before GPU resources are allocated. |
| FR-009 | The system SHALL detect blurry input images by computing the Laplacian variance of the grayscale image. If the variance is < 100, the system SHALL report `BF-E005` as a `WARNING` (not blocking) with message: `\"Image appears blurry (sharpness score: {score}). Results may be lower quality. Try: Use a sharper reference image.\"` |

### 3.2 Performance Optimization (M4.2)

| ID | Requirement |
|----|-------------|
| FR-010 | The system SHALL instrument each pipeline stage with `time.perf_counter()` timing via a `PerformanceProfiler` class, recording: `stage_name`, `start_time`, `end_time`, `duration_seconds`, `peak_memory_mb` (via `tracemalloc`). |
| FR-011 | The system SHALL generate a `PerfReport` as a Python `dict` containing per-stage timings, total pipeline duration, peak GPU memory usage (via `torch.cuda.max_memory_allocated()`), and peak CPU memory usage. The report SHALL be serializable to JSON. |
| FR-012 | The system SHALL implement lazy model loading: AI models (SAM 2, Depth Anything V2, reconstruction models) SHALL NOT be loaded into GPU memory until the first inference call that requires them. Once loaded, models SHALL remain cached in memory until explicitly freed or until VRAM pressure triggers eviction (see FR-007). |
| FR-013 | The system SHALL implement a model cache with LRU eviction: when loading a new model would exceed available VRAM (checked via `torch.cuda.mem_get_info()`), the least-recently-used cached model SHALL be evicted first. The cache SHALL hold a maximum of 3 models simultaneously. The cache SHALL NOT evict a model that has an active inference call in progress. If all 3 cached models are in active use and a new model is required, the system SHALL report `BF-E002` (VRAM exhaustion during inference) rather than evicting an in-use model. |
| FR-014 | The system SHALL batch GPU operations where possible: (a) vision pipeline stages (segmentation + depth estimation) SHALL share a single GPU context without redundant model loads, (b) multiple export format writes SHALL share a single validation pass. |
| FR-015 | The system SHALL display a performance summary in a sidebar panel (`TESSERA_PT_performance`) showing per-stage timing bars and total duration after each pipeline execution. |
| FR-016 | The system SHOULD profile the top 3 bottleneck stages on first run and log recommendations at `INFO` level, e.g., `\"Reconstruction took 180s (72% of total). Consider using InstantMesh adapter for faster results.\"` |

### 3.3 3MF Metadata Export (M4.3)

| ID | Requirement |
|----|-------------|
| FR-017 | The system SHALL extend the existing 3MF export (SPEC-TS-0006) to embed metadata in the 3MF XML structure under the `<metadata>` element of the 3MF `3dmodel.model` root. |
| FR-018 | The embedded metadata SHALL include: `Title` (object name), `Designer` (`\"Tessera {version}\"`), `CreationDate` (ISO 8601), `ModificationDate` (ISO 8601), `Description` (user-provided or `\"Generated from reference images by Tessera\"`). |
| FR-019 | The system SHALL embed print settings as custom metadata entries with namespace `http://tessera.org/spec/2026/04`: `bf:PrinterType` (`FDM` or `SLA`), `bf:WallThicknessMM` (float), `bf:InfillSuggestion` (one of `\"10%\"`, `\"15%\"`, `\"20%\"`, `\"30%\"`, `\"50%\"`, `\"100%\"` — selected based on object volume in mm³, converted from `bf:VolumeMMCubed`: < 10,000 mm³ → `\"100%\"`, < 50,000 mm³ → `\"30%\"`, < 200,000 mm³ → `\"20%\"`, else → `\"15%\"`), `bf:SupportSuggestion` (`\"required\"` if overhang check reported > 5% overhang faces, else `\"optional\"` — note: the 5% threshold is a print-quality heuristic for metadata advisory purposes, distinct from the validation pipeline's WARN/FAIL threshold in SPEC-TS-0006 FR-012 which uses 50%; objects with > 5% overhang faces typically benefit from support structures when printed via FDM), `bf:SourceImages` (integer count of input reference images). |
| FR-020 | The system SHALL embed the validation report summary as metadata: `bf:ManifoldStatus` (`\"PASS\"` / `\"FAIL\"`), `bf:WallThicknessStatus` (`\"PASS\"` / `\"WARN\"` / `\"FAIL\"`), `bf:OverhangStatus` (`\"PASS\"` / `\"WARN\"`), `bf:VolumeMMCubed` (float). |
| FR-021 | The 3MF metadata embedding SHALL NOT alter the mesh geometry data within the 3MF file. Metadata SHALL be appended to the XML after the geometry is written by the base exporter. |
| FR-022 | The system SHALL provide a `BoolProperty` `embed_3mf_metadata` (default `True`) that allows users to disable metadata embedding if desired. |

### 3.4 Automated Test Suite (M4.4)

| ID | Requirement |
|----|-------------|
| FR-023 | The system SHALL implement a deterministic mesh hashing function that canonicalizes vertex positions (sorted by x, y, z with 4 decimal places of precision) and face indices (sorted, with per-face vertex indices normalized to smallest-first rotation) before computing a SHA-256 hash. |
| FR-024 | The system SHALL store golden-mesh references as `.npz` files in `tests/golden_meshes/` containing: `vertex_hash` (SHA-256 hex string), `face_hash` (SHA-256 hex string), `vertex_count` (int), `face_count` (int), `bounding_box` (6 floats: min_x, min_y, min_z, max_x, max_y, max_z), `source_description` (string). |
| FR-025 | The test suite SHALL contain golden-mesh references for at minimum 10 objects across 5 categories: (1) simple geometric (mug, vase), (2) organic (figurine, animal), (3) hard-surface (box, gear), (4) thin-walled (bowl, plate), (5) complex (chess piece, architectural element). |
| FR-026 | The test suite SHALL run in CI (GitHub Actions) without a GPU by comparing pre-computed mesh hashes against reference hashes. The CI pipeline SHALL NOT perform 3D reconstruction or GPU inference. |
| FR-027 | The test suite SHALL include a `pytest` test that loads each golden-mesh `.npz`, feeds the stored mesh through the cleanup pipeline (SPEC-TS-0005) and validation pipeline (SPEC-TS-0006) in Blender headless mode (`blender --background --python`), and verifies: (a) output mesh is manifold, (b) output mesh is watertight, (c) all 7 validation checks pass or warn (no failures). |
| FR-028 | The test suite SHALL include a `pytest` test for each error catalog entry (FR-003) verifying that the correct error code, message, and resolution steps are returned when the error condition is simulated. |
| FR-029 | The test suite SHALL include a `pytest` test for 3MF metadata export verifying that the output `.3mf` file contains all required metadata fields (FR-018, FR-019, FR-020) by parsing the 3MF ZIP and inspecting the XML. |
| FR-030 | The test suite SHALL generate a test report in JUnit XML format (`--junitxml=test-results.xml`) for CI integration. |
| FR-031 | The system SHALL provide a convenience script `scripts/generate_golden_mesh.py` that takes an input mesh file (`.stl`, `.obj`, `.ply`), runs it through the cleanup and validation pipelines, and outputs a `.npz` golden-mesh reference file. |

### 3.5 Documentation (M4.5)

| ID | Requirement |
|----|-------------|
| FR-032 | The system SHALL include a `docs/` directory with a MkDocs project (`mkdocs.yml` + `docs/` source directory) that generates a static documentation site. |
| FR-033 | The documentation SHALL include an installation guide covering: (a) Windows 10/11 with NVIDIA GPU (CUDA), (b) macOS with Apple Silicon (MPS backend), (c) Ubuntu 22.04+ with NVIDIA GPU (CUDA). Each platform section SHALL include: prerequisites, step-by-step install, GPU driver verification, Blender version verification, and a platform-specific troubleshooting subsection. |
| FR-034 | The documentation SHALL include a quickstart tutorial that guides a new user from installation to first exported STL in ≤ 8 numbered steps, with screenshots at each step. The tutorial SHALL use a provided example image (bundled with the add-on). |
| FR-035 | The documentation SHALL include a user guide with chapters for: image input & view labels, reconstruction modes, mesh cleanup options, print validation settings, export formats, NL refinement, and sketch-to-3D. |
| FR-036 | The documentation SHALL include an API reference section documenting the adapter interface (`BaseReconstructionAdapter`) with: method signatures, parameter types, return types, and a complete example of implementing a custom adapter. |
| FR-037 | The documentation SHALL include a troubleshooting page listing all 15 error codes from FR-003 with: error message, cause description, and step-by-step resolution. |
| FR-038 | The system SHALL include a `README.md` in the repository root with: project description, feature list, installation quickstart (link to full docs), system requirements, license, and contributing guidelines. |
| FR-039 | The system SHALL include an in-add-on help panel (`TESSERA_PT_help`) with: link to documentation site, link to GitHub issues, and inline tooltips on every user-facing property (via `description` parameter of Blender properties). |

### 3.6 Example Gallery (M4.5)

| ID | Requirement |
|----|-------------|
| FR-040 | The documentation SHALL include a gallery page showcasing ≥ 10 example objects. Each gallery entry SHALL contain: (a) input reference image(s), (b) screenshot of the generated mesh in Blender viewport, (c) validation report summary (pass/warn/fail per check), (d) photo of the 3D-printed result (if available, placeholder text `\"Print photo pending\"` otherwise), (e) object category label, (f) pipeline timing. |
| FR-041 | The gallery data SHALL be stored as a YAML file (`docs/gallery/gallery.yaml`) with one entry per object, enabling automated gallery page generation via MkDocs macro or Jinja template. |
| FR-042 | The gallery SHALL cover at minimum 5 object categories: simple geometric, organic, hard-surface, thin-walled, and complex (matching the test suite categories in FR-025). |

### 3.7 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| Error scenario trigger | Exception instance | Any Python exception | Yes (for error handler) | `torch.cuda.OutOfMemoryError("CUDA out of memory")` |
| Pipeline stage name | `str` | One of: `"vision"`, `"reconstruction"`, `"cleanup"`, `"validation"`, `"export"` | Yes (for error handler) | `"reconstruction"` |
| Input image for blur detection | `np.ndarray` | Shape `(H, W, 3)`, dtype `uint8`, H ≥ 256, W ≥ 256 | Yes (for blur check) | 1024×768×3 uint8 array |
| Golden-mesh reference path | `str` | Valid path to `.npz` file | Yes (for test suite) | `"tests/golden_meshes/mug_simple.npz"` |
| 3MF metadata fields | `dict` | See FR-018 through FR-020 | No (auto-populated) | `{"Title": "MyObject", "PrinterType": "FDM"}` |

```python
# Type Definitions (for AI reference)
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class ErrorCategory(Enum):
    VRAM = "VRAM"
    INPUT = "INPUT"
    MODEL = "MODEL"
    EXPORT = "EXPORT"
    BLENDER = "BLENDER"
    SYSTEM = "SYSTEM"

class ErrorSeverity(Enum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"

@dataclass
class ErrorCatalogEntry:
    code: str                          # "BF-E001"
    message: str                       # User-facing message
    severity: ErrorSeverity
    category: ErrorCategory
    resolution_steps: list[str]        # ["Free GPU memory by closing other apps", ...]

@dataclass
class PerfStageResult:
    stage_name: str
    duration_seconds: float
    peak_memory_mb: float

@dataclass
class PerfReport:
    stages: list[PerfStageResult]
    total_duration_seconds: float
    peak_gpu_memory_mb: float
    peak_cpu_memory_mb: float

@dataclass
class GoldenMeshReference:
    vertex_hash: str                   # SHA-256 hex
    face_hash: str                     # SHA-256 hex
    vertex_count: int
    face_count: int
    bounding_box: tuple[float, ...]    # (min_x, min_y, min_z, max_x, max_y, max_z)
    source_description: str
```

### 3.8 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| Error message | `str` | `"[BF-EXXX] message. Try: step."` | `"[BF-E001] GPU memory exhausted while loading SAM 2. Try: Close other GPU applications."` |
| Performance report | `dict` → JSON | See `PerfReport` dataclass | `{"total_duration_seconds": 245.3, "stages": [...]}` |
| 3MF with metadata | `.3mf` (ZIP) | Standard 3MF + custom metadata namespace | `MyObject.3mf` |
| Test results | JUnit XML | Standard JUnit format | `test-results.xml` |
| Documentation site | Static HTML | MkDocs Material output | `docs/site/` |
| Golden-mesh reference | `.npz` | NumPy compressed archive | `tests/golden_meshes/mug_simple.npz` |

---

## 4. CONSTRAINTS

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT make any network calls from any production code. Documentation site build (MkDocs) MAY use network for theme/font downloads during build only, not at runtime. |
| CON-002 | SHALL NOT depend on any Python package not bundled with Blender unless packaged as a `python-wheel` within the add-on `.zip`. `xml.etree.ElementTree`, `hashlib`, `tracemalloc`, `cProfile`, and `zipfile` are Python stdlib and are permitted. |
| CON-003 | SHALL NOT collect telemetry, usage analytics, or crash reports. All performance data stays local. |
| CON-004 | SHALL NOT modify any existing pipeline behavior. Error handling and profiling SHALL wrap existing code, not alter it. |
| CON-005 | Test suite CI pipeline SHALL NOT require a GPU. All CI tests SHALL operate on pre-computed mesh data or Blender headless (CPU) operations. |
| CON-006 | Documentation SHALL NOT reference any external commercial API or cloud service as a requirement. |
| CON-007 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. Documentation content SHALL be licensed under CC-BY-4.0. |
| CON-008 | 3MF metadata SHALL conform to the OPC (Open Packaging Conventions) and 3MF Core Specification v1.3. Custom metadata SHALL use a dedicated namespace to avoid conflicts. |
| CON-009 | Golden-mesh `.npz` reference files SHALL be ≤ 1 MB each to keep the repository size manageable. Store hashes, not full vertex data. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | End-to-end pipeline latency (simple object) | Wall-clock time from image upload to STL export | < 5 minutes (300 seconds) | Single input image, simple object (mug/vase), RTX 3060 12 GB VRAM, 16 GB RAM |
| NFR-002 | End-to-end pipeline latency (complex object) | Wall-clock time from 3+ images to STL export | < 15 minutes (900 seconds) | 3 input images, complex object, RTX 3060 12 GB VRAM, 16 GB RAM |
| NFR-003 | Error handler overhead | Additional latency from error handling wrappers | < 1 ms per pipeline stage | Measured by profiler on no-error path |
| NFR-004 | Performance profiler overhead | Additional latency from timing instrumentation | < 5 ms total across all stages | Full pipeline execution |
| NFR-005 | 3MF metadata embedding latency | Additional time beyond base 3MF export | < 200 ms | Any mesh size |
| NFR-006 | Golden-mesh hash computation | Time to compute vertex_hash + face_hash | < 500 ms | Mesh with ≤ 500K faces |
| NFR-007 | CI test suite execution time | Wall-clock time for full test suite | < 5 minutes | GitHub Actions Ubuntu runner, no GPU |
| NFR-008 | Documentation site build time | MkDocs build to static HTML | < 30 seconds | Full documentation set |
| NFR-009 | Print success rate | Percentage of test-suite objects that produce print-successful STLs | ≥ 90% | Across 10+ golden-mesh test objects, validated by manifold + watertight + wall thickness checks |
| NFR-010 | Model loading latency (lazy, cached) | Time to serve a cached model | < 50 ms | Model already in GPU memory |
| NFR-011 | Model loading latency (lazy, cold) | Time to load model from disk to GPU | < 30 seconds | First load of SAM 2 / Depth Anything V2 on RTX 3060 |

---

## 6. ACCEPTANCE CRITERIA

### AC-001: VRAM Exhaustion Error Handling
**Given** a system with 4 GB of available GPU VRAM and a reconstruction model that requires 8 GB,  
**When** the pipeline attempts to load the reconstruction model,  
**Then** the system catches the `OutOfMemoryError`, displays `"[BF-E001] GPU memory exhausted while loading reconstruction model (requires ~8 GB, available: ~4 GB). Try: Close other GPU applications or switch to a smaller model variant in add-on preferences."` in the Blender Info area, appends the error to the error log panel, and does NOT crash Blender.

### AC-002: Blurry Image Warning
**Given** an input image with Laplacian variance of 45 (below the 100 threshold),  
**When** the vision pipeline processes the image,  
**Then** the system displays `"[BF-E005] Image appears blurry (sharpness score: 45). Results may be lower quality. Try: Use a sharper reference image."` as a WARNING, and the pipeline continues processing (non-blocking).

### AC-003: Performance Report After Pipeline Execution
**Given** a complete pipeline execution (image → reconstruction → cleanup → validation → export) on a simple object,  
**When** the export completes,  
**Then** the performance panel displays timing for each stage (vision, reconstruction, cleanup, validation, export) with duration in seconds, the total duration is ≤ 300 seconds, and a JSON performance report is available via `PerfReport.to_json()`.

### AC-004: 3MF Metadata Embedding
**Given** a validated mesh object with: printer type FDM, wall thickness 1.2 mm, bounding box volume 45 cm³, 3% overhang faces, and 2 input images,  
**When** `TESSERA_OT_export_for_print` is executed with `export_formats = {"3MF"}` and `embed_3mf_metadata = True`,  
**Then** the output `.3mf` file contains metadata entries: `Title`, `Designer` = `"Tessera 1.0"`, `CreationDate` in ISO 8601, `bf:PrinterType = "FDM"`, `bf:WallThicknessMM = "1.2"`, `bf:InfillSuggestion = "20%"` (volume 45 cm³ → 20%), `bf:SupportSuggestion = "optional"` (3% < 5%), `bf:SourceImages = "2"`, `bf:ManifoldStatus = "PASS"`.

### AC-005: Golden-Mesh Regression Test Pass
**Given** a golden-mesh reference file `tests/golden_meshes/mug_simple.npz` with known vertex and face hashes,  
**When** `pytest tests/test_golden_mesh.py::test_mug_simple` runs in CI (no GPU),  
**Then** the test loads the reference hashes, feeds the stored mesh through the cleanup pipeline in Blender headless mode, computes output hashes, and the test passes if both `vertex_hash` and `face_hash` match the reference.

### AC-006: Golden-Mesh Regression Test Failure Detection
**Given** a code change that alters the mesh cleanup pipeline (e.g., changing the default merge distance),  
**When** `pytest tests/test_golden_mesh.py` runs,  
**Then** at least one golden-mesh test fails with a clear message: `"Regression detected in 'mug_simple': vertex_hash mismatch. Expected: {expected}, Got: {actual}."`.

### AC-007: Cross-Platform Installation Documentation
**Given** a user on macOS with Apple Silicon (M2 chip) and Blender 4.2 installed,  
**When** the user follows the installation guide at `docs/installation.md`,  
**Then** the guide includes: (a) MPS backend verification command, (b) Python dependency installation steps, (c) add-on ZIP installation in Blender, (d) GPU verification within the add-on preferences panel, and (e) a troubleshooting section for common macOS issues (Gatekeeper, MPS compatibility).

### AC-008: First-Use Quickstart Tutorial
**Given** a user with Tessera successfully installed,  
**When** the user follows the quickstart tutorial (`docs/quickstart.md`),  
**Then** the tutorial completes in ≤ 8 numbered steps, uses a bundled example image, and the user has an exported STL file at the end.

### AC-009: Error Catalog Completeness
**Given** the `ERROR_CATALOG` dictionary in `tessera/errors/catalog.py`,  
**When** an automated test iterates all entries,  
**Then** each of the 16 error codes (BF-E001 through BF-E016) has: a non-empty `message` (≥ 20 characters), a valid `severity`, a valid `category`, and ≥ 1 `resolution_steps` entry that is a concrete action (not vague).

### AC-010: Unsupported Image Format Error
**Given** a user uploads a `.bmp` image (not in the supported formats list),  
**When** the vision pipeline attempts to process the image,  
**Then** the system immediately displays `"[BF-E003] Unsupported image format '.bmp'. Supported formats: .jpg, .jpeg, .png, .webp, .heic. Try: Convert the image to PNG or JPEG."` and does not proceed with pipeline execution.

---

## 7. EDGE CASES

### EC-001: All Pipeline Stages Fail Sequentially
| Aspect | Detail |
|--------|--------|
| **Scenario** | An extremely corrupted input image causes failures in vision (segmentation fails), reconstruction (empty mesh), and cleanup (ValueError from empty input). The error handler must manage a cascade of errors without duplicate reporting. |
| **Input Example** | A 256×256 solid black PNG image with no discernible object. |
| **Expected Behavior** | The system SHALL report only the first blocking error (`BF-E008`: reconstruction produced empty mesh) and SHALL NOT stack multiple error dialogs. Subsequent stage errors (cleanup failing on empty input) SHALL be logged at `DEBUG` level with note `"Suppressed cascading error from previous stage failure."` The error log panel SHALL show the root cause error prominently. |
| **Test ID** | TS-010 |

### EC-002: Golden-Mesh Reference File Missing or Corrupted
| Aspect | Detail |
|--------|--------|
| **Scenario** | A developer accidentally deletes or corrupts a `.npz` reference file in `tests/golden_meshes/`. |
| **Input Example** | `tests/golden_meshes/mug_simple.npz` is deleted or contains invalid data. |
| **Expected Behavior** | The system SHALL raise a `FileNotFoundError` or `ValueError` with message `"Golden-mesh reference 'mug_simple.npz' not found or corrupted. Run 'python scripts/generate_golden_mesh.py' to regenerate."` The test SHALL be marked as `ERROR` (not `FAIL`) in pytest output to distinguish infrastructure issues from regressions. |
| **Test ID** | TS-011 |

### EC-003: 3MF Exporter Plugin Not Available in Blender
| Aspect | Detail |
|--------|--------|
| **Scenario** | User's Blender installation does not have the `io_mesh_3mf` add-on enabled, and the built-in 3MF exporter is unavailable. |
| **Input Example** | `bpy.ops.export_scene.threemf.poll()` returns `False`. |
| **Expected Behavior** | The system SHALL detect the missing exporter during add-on initialization, display a one-time `WARNING`: `"[BF-E016] 3MF exporter not available. Enable 'Import/Export: 3MF' in Blender Preferences → Add-ons to use 3MF export with metadata."` If the user attempts 3MF export, the system SHALL skip 3MF and report which formats were exported. |
| **Test ID** | TS-012 |

### EC-004: Performance Profiler on System Without tracemalloc Support
| Aspect | Detail |
|--------|--------|
| **Scenario** | Blender's bundled Python is compiled without `tracemalloc` support (unlikely but possible on custom builds). |
| **Input Example** | `import tracemalloc` raises `ImportError`. |
| **Expected Behavior** | The system SHALL catch the `ImportError`, set `peak_cpu_memory_mb = -1.0` in the `PerfReport`, and log an `INFO` message: `"tracemalloc not available. CPU memory tracking disabled."` All other profiler functionality SHALL continue to work. |
| **Test ID** | TS-013 |

### EC-005: Hash Collision in Golden-Mesh Comparison (False Positive)
| Aspect | Detail |
|--------|--------|
| **Scenario** | Two different meshes produce the same SHA-256 hash after canonicalization (astronomically unlikely but the test framework should handle it). |
| **Input Example** | N/A — theoretical edge case. |
| **Expected Behavior** | The golden-mesh test framework SHALL also compare `vertex_count` and `face_count` as secondary checks. If hashes match but counts differ, the test SHALL report `FAIL` with message `"Hash collision detected: hashes match but vertex_count differs ({expected} vs {actual}). Regenerate reference."` |
| **Test ID** | TS-014 |

---

## 8. OUT OF SCOPE

The following are explicitly **excluded** from this feature:

- ❌ Any changes to the vision pipeline logic (SPEC-TS-0003) — error handling wraps it, does not alter it
- ❌ Any changes to the reconstruction engine logic (SPEC-TS-0004) — error handling wraps it, does not alter it
- ❌ Any changes to mesh cleanup logic (SPEC-TS-0005) — error handling wraps it, does not alter it
- ❌ Any changes to print validation logic (SPEC-TS-0006) — error handling wraps it, does not alter it
- ❌ Automated 3D printing from the add-on (direct slicer integration — PRD NG2)
- ❌ Cloud-based CI runners with GPUs — CI runs CPU-only mesh comparisons
- ❌ Video tutorials — documentation is text + screenshots only for v1
- ❌ Internationalization (i18n) of documentation or error messages — English only for v1
- ❌ Telemetry, analytics, or crash reporting (PRD D3 — local only)
- ❌ Performance optimization of third-party model inference code — only Tessera orchestration is optimized
- ❌ Actual 3D print verification — digital validation only in CI; manual print-test log maintained separately (per CSO suggestion)

---

## 9. SECURITY CONSIDERATIONS

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — local Blender add-on, no network interaction |
| **Auth Method** | None |
| **Required Permissions** | File system read/write for exports, docs, and test fixtures (handled by OS) |
| **Rate Limiting** | N/A |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| Error messages / tracebacks | Internal | Displayed in UI only; tracebacks logged locally at DEBUG level, never transmitted |
| Performance reports | Internal | Stored in memory and optionally saved to local JSON file |
| 3MF metadata | Internal | Embedded in locally exported file only |
| Golden-mesh hashes | Public | Committed to repository; contain no user data |
| Documentation content | Public | Published as static site |
| User input images | Internal | Processed in memory only; never persisted beyond the Blender session unless user saves the `.blend` file |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL NOT include stack traces or internal file paths in user-facing error messages. Stack traces SHALL only appear in DEBUG-level log output. |
| SEC-002 | SHALL sanitize any user-provided strings (object names, descriptions) used in 3MF XML metadata using `xml.sax.saxutils.escape()` to prevent XML injection. |
| SEC-003 | SHALL NOT make any network connections, DNS lookups, or socket operations from production code. |
| SEC-004 | SHALL NOT execute dynamically loaded code from user-specified paths in error handling, profiling, or test infrastructure. |
| SEC-005 | SHALL validate that golden-mesh `.npz` files loaded during testing contain only expected keys (`vertex_hash`, `face_hash`, `vertex_count`, `face_count`, `bounding_box`, `source_description`) and SHALL NOT use `pickle` for deserialization (use `np.load(allow_pickle=False)`). |
| SEC-006 | SHALL NOT log or display full file system paths of user images in error messages. Use basename only: `"image.jpg"` not `"/home/user/photos/image.jpg"`. |

---

## 10. API CONTRACT [CONDITIONAL]

> **No REST/HTTP APIs.** This section documents the internal Python API contracts.

### 10.1 ErrorHandler API
```python
from tessera.errors.handler import ErrorHandler
from tessera.errors.catalog import ERROR_CATALOG

handler = ErrorHandler(catalog=ERROR_CATALOG)

# Wrap a pipeline stage
try:
    result = vision_pipeline.execute(image)
except Exception as e:
    error_result = handler.catch(
        exception=e,
        stage_name="vision",
        context={"image_path": "image.jpg", "gpu_memory_available_mb": 4096}
    )
    # error_result.code: str           — "BF-E001"
    # error_result.user_message: str   — Formatted user-facing message
    # error_result.severity: ErrorSeverity
    # error_result.resolution_steps: list[str]
    # error_result.logged: bool        — True if logged successfully
```

**Exception-to-Error-Code Classification Table:**

The `ErrorHandler.catch()` method SHALL classify exceptions using the following `(exception_type, stage_name/context)` → `error_code` mapping:

| Exception Type | Stage / Context | Error Code |
|----------------|-----------------|------------|
| `torch.cuda.OutOfMemoryError` | Any stage, during model loading | `BF-E001` |
| `torch.cuda.OutOfMemoryError` | Any stage, during inference | `BF-E002` |
| `ValueError` with "unsupported format" | `vision` (input validation) | `BF-E003` |
| `ValueError` with "resolution too low" | `vision` (input validation) | `BF-E004` |
| N/A (proactive check) | `vision` (blur detection, Laplacian < 100) | `BF-E005` |
| `FileNotFoundError` | Model weight loading | `BF-E006` |
| `ValueError` with "hash mismatch" | Model weight verification | `BF-E007` |
| `ValueError` with "empty mesh" | `reconstruction` | `BF-E008` |
| `TimeoutError` | `reconstruction` (> 120 seconds) | `BF-E009` |
| `RuntimeError` with "non-manifold" | `cleanup` | `BF-E010` |
| `PermissionError` / `OSError` | `export` (directory write) | `BF-E011` |
| `RuntimeError` with version check | Add-on initialization | `BF-E012` |
| `RuntimeError` with GPU detection | Add-on initialization | `BF-E013` |
| `ImportError` | Add-on initialization | `BF-E014` |
| `OSError` with disk space check | Model weight download | `BF-E015` |
| `RuntimeError` with exporter poll | Add-on initialization / `export` | `BF-E016` |

If an exception does not match any known classification, the handler SHALL assign a generic code `BF-E999` with severity `ERROR`, category `SYSTEM`, and message `"An unexpected error occurred in the {stage_name} stage. Try: Restart Blender and try again."`

### 10.2 PerformanceProfiler API
```python
from tessera.perf.profiler import PerformanceProfiler

profiler = PerformanceProfiler()

with profiler.stage("vision"):
    vision_result = vision_pipeline.execute(image)

with profiler.stage("reconstruction"):
    mesh = reconstruction_adapter.generate(vision_result)

report = profiler.report()
# report.total_duration_seconds: float
# report.stages: list[PerfStageResult]
# report.to_json(): str
```

### 10.3 ThreeMFMetadataExporter API
```python
from tessera.export.threemf_metadata import ThreeMFMetadataExporter

metadata_exporter = ThreeMFMetadataExporter()
metadata_exporter.embed(
    threemf_path="/path/to/MyObject.3mf",
    object_name="MyObject",
    printer_type="FDM",
    wall_thickness_mm=1.2,
    volume_mm3=45230.5,
    overhang_face_percentage=3.2,
    source_image_count=2,
    validation_report=report,  # ValidationReport from SPEC-TS-0006
    tessera_version="1.0.0",
    description="Generated from reference images"
)
# Modifies the .3mf ZIP in-place, adding metadata to the XML
```

### 10.4 GoldenMeshRegistry API
```python
from tessera.testing.golden_mesh import GoldenMeshRegistry
from tessera.testing.mesh_hash import compute_mesh_hash

registry = GoldenMeshRegistry(base_path="tests/golden_meshes/")

# Generate a reference
ref = registry.create_reference(
    name="mug_simple",
    vertices=vertices_array,
    faces=faces_array,
    source_description="Simple mug, single image, Trellis adapter"
)
# Saves tests/golden_meshes/mug_simple.npz

# Compare against reference
ref = registry.load_reference("mug_simple")
test_hash = compute_mesh_hash(test_vertices, test_faces)
assert test_hash.vertex_hash == ref.vertex_hash
assert test_hash.face_hash == ref.face_hash
```

---

## 11. OBSERVABILITY

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------|
| Error caught by handler | ERROR | `error_code`, `stage_name`, `severity`, `user_message` | ⚠️ No PII — file basenames only |
| Error traceback (developer) | DEBUG | `error_code`, `full_traceback` | ⚠️ No PII — verify no paths |
| Error cascading suppressed | DEBUG | `suppressed_error_code`, `root_cause_code` | ⚠️ No PII |
| Pipeline stage started | DEBUG | `stage_name` | ⚠️ No PII |
| Pipeline stage completed | INFO | `stage_name`, `duration_seconds`, `peak_memory_mb` | ⚠️ No PII |
| Performance report generated | INFO | `total_duration_seconds`, `stage_count` | ⚠️ No PII |
| Bottleneck recommendation | INFO | `stage_name`, `percentage_of_total`, `recommendation` | ⚠️ No PII |
| 3MF metadata embedded | DEBUG | `threemf_path_basename`, `metadata_field_count` | ⚠️ No PII |
| Model loaded (lazy) | INFO | `model_name`, `load_time_seconds`, `gpu_memory_used_mb` | ⚠️ No PII |
| Model evicted (LRU) | INFO | `model_name`, `reason` | ⚠️ No PII |
| Golden-mesh test passed | DEBUG | `test_name`, `hash_match` | ⚠️ No PII |
| Golden-mesh test failed | ERROR | `test_name`, `expected_hash`, `actual_hash` | ⚠️ No PII |
| Image blur check | DEBUG | `image_basename`, `laplacian_variance`, `threshold` | ⚠️ No PII |
| Input validation failed | WARN | `error_code`, `validation_detail` | ⚠️ No PII |

> All logging uses Python's `logging` module with loggers: `"tessera.errors"`, `"tessera.perf"`, `"tessera.export.metadata"`, `"tessera.testing"`.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only).

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — all features available when add-on is installed |
| **Default State** | Error handling always active; performance profiler always active (minimal overhead); 3MF metadata embedding enabled by default (opt-out via `embed_3mf_metadata` property) |
| **Rollout Plan** | Bundled with add-on `.zip`; documentation deployed to GitHub Pages |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| All Phase 1–3 specs (SPEC-TS-0001 through SPEC-TS-0010) | Yes | Error handling wraps all existing pipeline stages; test suite validates all pipelines |
| Blender 4.2+ | Yes | Required for API compatibility |
| Python stdlib (`xml.etree`, `hashlib`, `tracemalloc`, `zipfile`, `cProfile`) | Yes | Bundled with Blender's Python |
| MkDocs + Material theme | Yes (dev dependency only) | For doc site generation; not bundled with add-on |
| pytest | Yes (dev dependency only) | For test execution; not bundled with add-on |
| GitHub Actions | Yes (CI only) | For automated test execution on push |

### 12.3 Rollback Plan
1. Error handling and profiling are additive wrappers — removing them restores previous behavior
2. 3MF metadata is opt-out via `embed_3mf_metadata = False`
3. Test suite and documentation are development-only artifacts — no impact on user-facing add-on
4. In-add-on help panel can be hidden via Blender's panel visibility controls

---

## 13. TEST SCENARIOS

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | VRAM exhaustion error caught, formatted message displayed, Blender does not crash | Unit | AC-001 | Must Pass |
| TS-002 | Blurry image detected at variance < 100, WARNING displayed, pipeline continues | Unit | AC-002 | Must Pass |
| TS-003 | Performance profiler records per-stage timing, report JSON is valid | Unit | AC-003 | Must Pass |
| TS-004 | 3MF export contains all required metadata fields in XML | Integration | AC-004 | Must Pass |
| TS-005 | Golden-mesh test passes when hashes match reference | Unit | AC-005 | Must Pass |
| TS-006 | Golden-mesh test fails with clear message when hashes differ | Unit | AC-006 | Must Pass |
| TS-007 | All 16 error catalog entries have valid code, message, severity, category, and ≥1 resolution step | Unit | AC-009 | Must Pass |
| TS-008 | Unsupported image format triggers BF-E003 error before GPU allocation | Unit | AC-010 | Must Pass |
| TS-009 | Image < 256×256 px triggers BF-E004 error | Unit | FR-008 | Must Pass |
| TS-010 | Cascading errors suppressed: only root cause displayed | Integration | EC-001 | Must Pass |
| TS-011 | Missing golden-mesh .npz reports ERROR (not FAIL) | Unit | EC-002 | Must Pass |
| TS-012 | Missing 3MF exporter: WARNING displayed, graceful skip | Unit | EC-003 | Must Pass |
| TS-013 | Profiler works without tracemalloc: memory = -1.0 | Unit | EC-004 | Must Pass |
| TS-014 | Hash match + count mismatch: FAIL with collision message | Unit | EC-005 | Must Pass |
| TS-015 | Error handler overhead < 1 ms per stage on no-error path | Performance | NFR-003 | Must Pass |
| TS-016 | Profiler overhead < 5 ms total pipeline | Performance | NFR-004 | Must Pass |
| TS-017 | 3MF metadata embedding < 200 ms | Performance | NFR-005 | Must Pass |
| TS-018 | Mesh hash computation < 500 ms for 500K face mesh | Performance | NFR-006 | Must Pass |
| TS-019 | Full CI test suite < 5 minutes | Performance | NFR-007 | Should Pass |
| TS-020 | 3MF XML metadata escaped against injection | Unit | SEC-002 | Must Pass |
| TS-021 | Golden-mesh .npz loaded with allow_pickle=False | Unit | SEC-005 | Must Pass |
| TS-022 | Error messages use basename only, no full paths | Unit | SEC-006 | Must Pass |
| TS-023 | Error log panel shows last 50 entries in scrollable list | Integration | FR-006 | Must Pass |
| TS-024 | Lazy model loading: model not in GPU until first inference | Integration | FR-012 | Must Pass |
| TS-025 | LRU cache evicts least-recent model when VRAM full | Integration | FR-013 | Should Pass |
| TS-026 | Installation guide covers Windows, macOS Apple Silicon, Linux | Manual | AC-007 | Must Pass |
| TS-027 | Quickstart tutorial completes in ≤ 8 steps | Manual | AC-008 | Must Pass |
| TS-028 | Gallery page shows ≥ 10 objects across 5 categories | Manual | FR-040 | Must Pass |
| TS-029 | generate_golden_mesh.py produces valid .npz | Unit | FR-031 | Must Pass |
| TS-030 | Infill suggestion logic: volume thresholds produce correct suggestions | Unit | FR-019 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0001 (Add-on Scaffold) | Required | Draft | Tessera | Yes — provides module registration framework |
| SPEC-TS-0002 (Model Weight Management) | Required | Draft | Tessera | Yes — error handling wraps model download/cache |
| SPEC-TS-0003 (Vision Pipeline) | Required | Draft | Tessera | Yes — error handling wraps vision stages |
| SPEC-TS-0004 (Reconstruction Engine) | Required | Draft | Tessera | Yes — error handling wraps reconstruction |
| SPEC-TS-0005 (Mesh Cleanup) | Required | Draft | Tessera | Yes — test suite validates cleanup output |
| SPEC-TS-0006 (Print Validator & Export) | Required | Draft | Tessera | Yes — 3MF metadata extends export; test suite validates exports |
| SPEC-TS-0007 (Multi-View Reconstruction) | Required | Draft | Tessera | Yes — error handling wraps multi-view |
| SPEC-TS-0008 (Scaling & Orientation) | Required | Draft | Tessera | Yes — test suite validates scaling |
| SPEC-TS-0009 (NL Refinement Loop) | Required | Draft | Tessera | Yes — error handling wraps refinement |
| SPEC-TS-0010 (Sketch-to-3D) | Required | Draft | Tessera | Yes — error handling wraps sketch pipeline |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| Blender 4.2+ LTS | Required | [docs.blender.org](https://docs.blender.org/api/current/) | No fallback — hard requirement |
| Python stdlib (`xml.etree`, `hashlib`, `tracemalloc`, `zipfile`) | Required | [docs.python.org](https://docs.python.org/3/) | N/A — bundled with Python |
| NumPy (Blender-bundled) | Required | [numpy.org](https://numpy.org/doc/) | N/A — bundled with Blender |
| MkDocs + Material theme | Dev only | [mkdocs.org](https://www.mkdocs.org/) | Documentation can be read as raw Markdown |
| pytest + pytest-junitxml | Dev only | [pytest.org](https://docs.pytest.org/) | Tests can run with unittest stdlib |
| GitHub Actions | CI only | [docs.github.com](https://docs.github.com/en/actions) | Tests can run locally via `pytest` |

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
| SHALL/SHOULD/MAY requirements | 20 | 20 | 42 requirements with precise SHALL/SHOULD/MAY language across FR-001 to FR-042 |
| Quantified NFRs | 15 | 15 | 11 NFRs, all quantified with specific latency/memory/rate targets and measurement conditions |
| Given-When-Then criteria (3+) | 20 | 20 | 10 acceptance criteria in Given-When-Then format with specific values |
| Edge cases (2+) | 15 | 15 | 5 edge cases with concrete input examples and expected behaviors |
| Out of scope defined | 10 | 10 | 11 explicit exclusions listed with cross-references to other specs and PRD decisions |
| Security constraints | 10 | 10 | 6 security requirements + data classification table addressing XML injection, pickle safety, path exposure |
| No ambiguous language | 10 | 10 | All ambiguous terms replaced with specifics. Volume units normalized to mm³. Support threshold rationale documented. PRD metric ratcheting annotated. |
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
- [x] "handle gracefully" → replaced with specific error responses (FR-007, EC-001)
- [x] "fast" / "efficient" / "performant" → replaced with ms/second targets (NFR-001 through NFR-011)
- [x] "secure" → replaced with SEC-001 through SEC-006
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → replaced with specific latency and throughput targets

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-10 | Orchestrator (AI) | Initial draft |
| 1.1 | 2026-04-14 | Antigravity (AI) | Spec review fixes: normalized volume units to mm³ in FR-019, documented 5% support threshold rationale, expanded error catalog to 16 entries (added BF-E016), added LRU eviction guard for active inference in FR-013, added exception-to-error-code classification table in §10.1, annotated PRD print success rate ratcheting in §1.4, updated AC-009 and TS-007 to reflect 16 error codes |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0011-production-hardening.md`
