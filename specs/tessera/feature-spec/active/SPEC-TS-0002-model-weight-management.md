# Feature Specification: Local Model Weight Management

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0002 |
| **Task ID** | TASK-TS-0002 |
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
Tessera runs entirely locally with no cloud APIs (decision D3). The AI pipelines — vision analysis (TASK-TS-0003), reconstruction (TASK-TS-0004), and mesh processing (TASK-TS-0005) — all depend on multi-gigabyte neural network weight files (Depth Anything V2, SAM 2, DINOv2, Zero-1-to-3++, OpenLRM, Trellis, InstantMesh). These weights must be downloaded from official sources, cached locally, and version-managed so that inference never requires a network call. Without this infrastructure, no AI pipeline task can function. This is a P1 foundation task that unblocks Phase 1 milestones M1.3 and M1.4.

### 1.2 User Story
**As a** Tessera user,  
**I want** model weights to download automatically on first use and be cached locally,  
**So that** I don't have to manually manage AI model files or worry about disk space.

### 1.3 Proposed Approach
Build a model weight management layer using the `huggingface_hub` Python library as the download and caching backend. The system consists of three components: (1) a **model registry** — a JSON manifest embedded in the add-on that declares every required model with its HuggingFace repo ID, revision, expected SHA256, file size, and minimum VRAM requirement; (2) a **download manager** — a background download engine with progress reporting integrated into Blender's UI, resume support for interrupted downloads, and SHA256 integrity verification; (3) a **cache manager** — disk usage tracking, per-model clear/re-download controls in the add-on preferences panel, and VRAM-aware model variant selection (fp16 vs fp32). The cache directory is user-configurable (defaulting to the path set in SPEC-TS-0001's preferences panel) and all downloads use HTTPS from official HuggingFace repositories.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| First-use download completes without manual intervention | N/A | 100% on systems with ≥ 25 Mbps connection | Manual test on Windows/Mac/Linux |
| Subsequent pipeline invocations load from cache with zero network calls | N/A | 100% | Network traffic monitoring during inference |
| Total core model disk footprint | N/A | < 10 GB | `scan_cache_dir()` output after all core models downloaded |

---

## 2. TECHNICAL CONTEXT

> ⚠️ **AI needs this context BEFORE generating code.** Provide patterns and references here.

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/preferences.py` (SPEC-TS-0001) | Add-on preferences with cache directory path | Where to read/write the `cache_dir` setting |
| `tessera/gpu_detection.py` (SPEC-TS-0001) | GPU detection + VRAM reporting | VRAM value used for model variant selection |
| `huggingface_hub.hf_hub_download()` | HF Hub single-file download API | Download pattern with `cache_dir`, `revision`, resume (used instead of `snapshot_download()` because the manifest declares specific files with per-file SHA256 verification) |
| `huggingface_hub.scan_cache_dir()` | HF Hub cache inspection API | Disk usage calculation and per-repo cache management |
| `tessera/ui/main_panel.py` (SPEC-TS-0001) | Sidebar panel structure | Pattern for adding download progress sub-panel |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`)
- **Download backend:** `huggingface_hub` >= 0.23.0 (bundled as `python-wheel` in add-on `.zip`)
- **Hashing:** `hashlib` (stdlib) for SHA256 integrity verification
- **Concurrency:** `threading.Thread` for background downloads (Blender's main thread must not block)
- **Validation:** `bpy.props` property system + runtime assertions
- **Testing:** `pytest` run via `blender --background --python` for headless testing
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── models/
│   ├── __init__.py
│   ├── registry.py          # ModelRegistry: loads + queries the manifest
│   ├── manifest.json        # Embedded model manifest (all model metadata)
│   ├── download_manager.py  # DownloadManager: background download with progress
│   ├── cache_manager.py     # CacheManager: disk usage, clear, version check
│   └── variant_selector.py  # VRAM-aware model variant selection (fp16/fp32)
├── ui/
│   └── download_panel.py    # Download progress UI sub-panel
├── operators/
│   └── model_ops.py         # OT_DownloadModel, OT_ClearModelCache, OT_CheckUpdates
└── ... (existing from SPEC-TS-0001)
```

**Threading model:** Downloads run in a `threading.Thread`. The thread writes progress to a thread-safe `queue.Queue`. A Blender `bpy.app.timers` callback polls the queue at 100ms intervals and updates scene properties that the UI reads. This avoids any direct `bpy` access from the background thread.

**`ensure_model()` threading contract:** The `ensure_model()` function (FR-014) is a blocking call designed for use **within pipeline background threads** (e.g., the reconstruction or vision pipeline threads from TASK-TS-0003+). It SHALL NOT be called from the Blender main thread, as it would block the event loop and violate NFR-004. UI-triggered downloads use the non-blocking `DownloadManager` with progress queue polling instead.

**Integration with SPEC-TS-0001:** The cache directory path is read from `bpy.context.preferences.addons['tessera'].preferences.cache_dir`. The GPU VRAM is read via `tessera.gpu_detection.get_gpu_info()`.

---

## 3. FUNCTIONAL REQUIREMENTS

> ⚠️ **Use precise language:** SHALL (required), SHALL NOT (prohibited), SHOULD (recommended), SHOULD NOT (discouraged), MAY (optional). The keyword IS the priority.

### 3.1 Core Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL provide a model registry loaded from an embedded `manifest.json` file that declares each required model with fields: `model_id` (unique string), `repo_id` (HuggingFace repository ID), `revision` (Git commit hash or tag), `files` (list of relative file paths within the repo), `sha256` (dict of filename → expected SHA256 hex digest), `size_bytes` (total download size in bytes), `min_vram_gb` (minimum GPU VRAM required in GB), `variants` (list of variant objects, see FR-012), and `description` (human-readable purpose). |
| FR-002 | The system SHALL download model weights from HuggingFace repositories using `huggingface_hub.hf_hub_download()` (per-file download) with the `cache_dir` set to the user's configured cache directory and the `revision` pinned to the manifest-specified commit hash. Per-file download is required because the manifest declares individual files with per-file SHA256 hashes for integrity verification. |
| FR-003 | The system SHALL run all downloads in a background thread that does not block Blender's main UI thread. |
| FR-004 | The system SHALL report download progress to the Blender UI by writing progress data (bytes downloaded, total bytes, download speed in bytes/sec, model name) to a thread-safe queue, polled by a `bpy.app.timers` callback at 100ms intervals. |
| FR-005 | The system SHALL display a download progress bar in the Tessera sidebar panel showing: model name, percentage complete, downloaded/total size in MB, and estimated time remaining. |
| FR-006 | The system SHALL support resuming interrupted downloads by relying on `huggingface_hub`'s built-in resume mechanism (HTTP Range headers). If a download is interrupted (network failure, Blender closed), the next download attempt for the same model SHALL resume from the last downloaded byte. |
| FR-007 | The system SHALL verify the SHA256 hash of each downloaded file against the expected hash in `manifest.json`. If the hash does not match, the system SHALL delete the corrupted file and report an error: `"Integrity check failed for {filename}. Expected SHA256: {expected}. File has been deleted. Please retry the download."` |
| FR-008 | The system SHALL provide a "Models" section in the add-on preferences panel that displays a table of all registered models with columns: Name, Status (Downloaded / Not Downloaded / Update Available / Downloading), Size on Disk, and Required VRAM. |
| FR-009 | The system SHALL provide a "Download All Required" operator button in the preferences panel that initiates sequential download of all models marked as "Not Downloaded". |
| FR-010 | The system SHALL provide per-model "Download" and "Delete" buttons in the preferences panel for individual model management. |
| FR-011 | The system SHALL display total disk usage of all cached models as a summary line in the preferences panel, formatted as `"Model cache: X.X GB used in {path}"`. |
| FR-012 | The system SHALL support model variants for different VRAM tiers. Each model entry in the manifest MAY contain a `variants` array (e.g., `[{"variant_id": "fp32", "min_vram_gb": 8, "size_bytes": 2000000000}, {"variant_id": "fp16", "min_vram_gb": 4, "size_bytes": 1000000000}]`). The system SHALL select the highest-quality variant whose `min_vram_gb` ≤ the detected GPU VRAM. If a model entry has no `variants` array (or the array is empty), `select_variant()` SHALL return a default variant constructed from the model's top-level `min_vram_gb`, `size_bytes`, and `files` fields with `variant_id = "default"`. |
| FR-013 | The system SHALL provide a `get_model_path(model_id: str) -> Optional[Path]` API that downstream pipeline tasks call to get the local file path for a cached model. If the model is not downloaded, the function SHALL return `None`. |
| FR-014 | The system SHALL provide an `ensure_model(model_id: str, callback: Optional[Callable]) -> Path` API that checks if a model is cached and, if not, initiates a download (with optional progress callback), blocking until the download completes, and returns the local path. This function is designed for use in pipeline background threads only — it SHALL NOT be called from the Blender main thread. |
| FR-015 | The system SHOULD detect when a newer revision of a model is available by comparing the manifest's `revision` against the cached revision. If a newer version exists, the model status SHALL display "Update Available". |
| FR-016 | The system SHOULD allow the user to update a specific model to the latest manifest revision via an "Update" button that downloads the new version and removes the old cached files. |
| FR-017 | The system SHALL display a notification banner in the main Tessera panel when one or more required models are not yet downloaded, with the text: `"Required models not downloaded. Open Preferences to download ({N} models, ~{X.X} GB total)."` and a button to open the preferences panel. |
| FR-018 | The system MAY provide a "Download on first use" toggle in preferences. When enabled (default: enabled), pipeline tasks call `ensure_model()` which auto-downloads missing models before inference. When disabled, the user must manually download models from preferences. |
| FR-019 | The system SHALL NOT make any network calls during model inference. All network activity is limited to the download manager. |

### 3.2 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| `model_id` | `str` | Matches a key in `manifest.json`, alphanumeric + hyphens, max 64 chars | Yes | `"depth-anything-v2-large"` |
| `cache_dir` | `str` | Valid writable directory path (inherited from SPEC-TS-0001 preferences) | Yes | `"/home/user/.tessera/cache"` |
| `variant_id` | `str` | One of variant IDs in the model's `variants` list, or `"auto"` for VRAM-based selection | No (default: `"auto"`) | `"fp16"` |

```python
# Manifest entry type definition (for AI reference)
@dataclass
class ModelVariant:
    variant_id: str       # e.g. "fp16", "fp32"
    min_vram_gb: float    # minimum VRAM required
    size_bytes: int       # download size for this variant
    files: list[str]      # relative file paths within repo for this variant

@dataclass
class ModelEntry:
    model_id: str         # unique identifier, e.g. "depth-anything-v2-large"
    repo_id: str          # HuggingFace repo, e.g. "depth-anything/Depth-Anything-V2-Large"
    revision: str         # pinned commit hash, e.g. "a5b2b12b..."
    description: str      # human-readable, e.g. "Monocular depth estimation"
    files: list[str]      # default file list (no variants)
    sha256: dict[str, str]  # filename → expected SHA256 hex digest
    size_bytes: int       # total download size in bytes
    min_vram_gb: float    # minimum VRAM for default variant
    variants: list[ModelVariant]  # optional VRAM-tiered variants
```

### 3.3 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `model_path` | `pathlib.Path` | Absolute path to cached model directory | `Path("/home/user/.tessera/cache/models--depth-anything--Depth-Anything-V2-Large/snapshots/a5b2b12b/")` |
| `download_progress` | `dict` | `{"model_id": str, "bytes_downloaded": int, "total_bytes": int, "speed_bps": float, "eta_seconds": float}` | `{"model_id": "depth-anything-v2-large", "bytes_downloaded": 524288000, "total_bytes": 1340000000, "speed_bps": 5242880.0, "eta_seconds": 156.0}` |
| `cache_report` | `dict` | `{"total_bytes": int, "models": [{"model_id": str, "status": str, "size_bytes": int}]}` | See cache manager API |

```python
# Public API return types (for AI reference)
from pathlib import Path
from typing import Optional, Callable

def get_model_path(model_id: str) -> Optional[Path]:
    """Returns the local path to a cached model, or None if not downloaded."""
    ...

def ensure_model(model_id: str, callback: Optional[Callable] = None) -> Path:
    """Downloads model if not cached, returns local path. Raises ModelDownloadError on failure."""
    ...

def get_cache_report() -> dict:
    """Returns disk usage summary for all registered models."""
    ...
```

---

## 4. CONSTRAINTS

> ⚠️ **Critical for AI code generation.** These are hard prohibitions the AI must follow.

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT make any network calls outside of the download manager module. No network calls during model inference. |
| CON-002 | SHALL NOT download models from any source other than official HuggingFace repositories as specified in `manifest.json`. |
| CON-003 | SHALL NOT access `bpy` APIs from background download threads. All `bpy` interaction SHALL occur on the main thread via `bpy.app.timers`. |
| CON-004 | SHALL NOT store API tokens, credentials, or secrets anywhere in the add-on. All HuggingFace downloads use public repository access only. |
| CON-005 | SHALL NOT hardcode file paths or platform-specific path separators. Use `pathlib.Path` for all path operations. |
| CON-006 | SHALL NOT load or execute arbitrary code from downloaded model files. Only load `.safetensors`, `.bin`, `.pt`, `.pth`, `.onnx`, and `.json` model weight files. |
| CON-007 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. |
| CON-008 | SHALL NOT use `pickle.load()` or `torch.load()` with `weights_only=False` on downloaded files. Use `safetensors.torch.load_file()` or `torch.load(..., weights_only=True)` exclusively. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

> ⚠️ **All NFRs must be quantified.** Replace vague terms with specific numbers.

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Download throughput | Sustained download speed | ≥ 80% of available bandwidth | On a 100 Mbps connection, sequential single-file download |
| NFR-002 | Download resume overhead | Time to resume after interruption | < 5 seconds to resume from last byte | After simulated network interruption mid-download |
| NFR-003 | Cache scan time | Time to compute disk usage for all cached models | < 2 seconds | With 10 models cached (≤ 10 GB total) |
| NFR-004 | UI responsiveness during download | Main thread frame rate | ≥ 15 fps (Blender viewport redraw) | During active model download |
| NFR-005 | SHA256 verification speed | Time to verify integrity of a 2 GB file | < 30 seconds | On system with NVMe SSD |
| NFR-006 | `get_model_path()` latency | Function return time | < 10ms | File existence check on local filesystem |
| NFR-007 | Memory overhead of download manager | Additional Python memory during download | < 50 MB | Including download buffer and progress tracking |
| NFR-008 | Cross-platform compatibility | Download + cache on all supported OS | 100% | Windows 10+, macOS 12+ (Intel & Apple Silicon), Ubuntu 22.04+ |

---

## 6. ACCEPTANCE CRITERIA

> ⚠️ **Minimum 3 criteria in Given-When-Then format.** These drive test implementation.

### AC-001: First-Use Model Download with Progress
**Given** Tessera is installed with no models cached and the user has a working internet connection,  
**When** the user opens add-on preferences and clicks "Download All Required",  
**Then** each model downloads sequentially, the UI shows a progress bar per model with model name, percentage (0–100%), downloaded/total MB, estimated time remaining, and upon completion the status column shows "Downloaded" for all models.

### AC-002: Pipeline Loads Model from Cache Without Network
**Given** the model `depth-anything-v2-large` has been previously downloaded and cached,  
**When** a downstream pipeline task calls `get_model_path("depth-anything-v2-large")`,  
**Then** the function returns a valid `Path` pointing to the cached model directory within 10ms, and no network connections are opened (verified by monitoring socket activity).

### AC-003: Interrupted Download Resumes
**Given** a model download is in progress and has completed 500 MB of a 1.3 GB file,  
**When** the network connection is interrupted and the user clicks "Download" again after reconnecting,  
**Then** the download resumes from within 1 MB (±1,048,576 bytes) of byte 500,000,000 (not from zero), accounting for HTTP Range header chunk alignment, and completes successfully with SHA256 verification passing.

### AC-004: VRAM-Aware Variant Selection
**Given** the manifest declares model `depth-anything-v2` with variants `fp32` (min 8 GB VRAM, 2 GB download) and `fp16` (min 4 GB VRAM, 1 GB download), and the user's GPU has 6 GB VRAM,  
**When** the download manager resolves the variant for this model,  
**Then** the system selects `fp16` (the highest-quality variant that fits in 6 GB) and downloads only the `fp16` files.

### AC-005: Integrity Check Failure
**Given** a model file has been downloaded but the stored file's SHA256 does not match the expected hash in `manifest.json` (simulated by modifying 1 byte of the cached file),  
**When** the system performs integrity verification,  
**Then** the system deletes the corrupted file, sets the model status to "Not Downloaded", and displays the error message: `"Integrity check failed for {filename}. Expected SHA256: {expected}. File has been deleted. Please retry the download."`.

### AC-006: Disk Usage Display and Cache Clearing
**Given** 3 models are cached totaling 7.2 GB of disk usage,  
**When** the user opens add-on preferences and views the Models section,  
**Then** the summary line reads `"Model cache: 7.2 GB used in /path/to/cache"`, each model row shows its individual size, and clicking the "Delete" button on one model removes its files and updates the total.

### AC-007: Missing Models Notification
**Given** 2 of 5 registered models are not yet downloaded,  
**When** the user opens the Tessera sidebar panel,  
**Then** a notification banner displays: `"Required models not downloaded. Open Preferences to download (2 models, ~3.4 GB total)."` with a clickable "Open Preferences" button.

---

## 7. EDGE CASES

> ⚠️ **Minimum 2 edge cases required.** Document non-obvious scenarios AI might miss.

### EC-001: Disk Space Exhausted During Download
| Aspect | Detail |
|--------|--------|
| **Scenario** | User's disk fills up while downloading a large model file |
| **Input Example** | Disk has 500 MB free; model download requires 1.3 GB |
| **Expected Behavior** | The system SHALL catch the `OSError` / `IOError`, set the model status to "Not Downloaded", and display the error: `"Download failed: insufficient disk space. {X.X} GB required, {Y.Y} GB available. Free up disk space and retry."` The partial download file SHALL be preserved for future resume. |
| **Test ID** | TS-004 |

### EC-002: Cache Directory Deleted While Add-on Is Running
| Aspect | Detail |
|--------|--------|
| **Scenario** | User manually deletes the cache directory from outside Blender while the add-on is active |
| **Input Example** | `rm -rf /home/user/.tessera/cache` while Blender is open |
| **Expected Behavior** | The system SHALL detect the missing directory on the next `get_model_path()` call, recreate the cache directory, set all model statuses to "Not Downloaded", and log a WARN: `"Cache directory was removed. All models marked as not downloaded."` |
| **Test ID** | TS-005 |

### EC-003: Concurrent Download Requests for Same Model
| Aspect | Detail |
|--------|--------|
| **Scenario** | User clicks "Download" on a model that is already downloading (e.g., triggered by both the preferences UI and an `ensure_model()` call from a pipeline) |
| **Input Example** | Two concurrent `ensure_model("depth-anything-v2-large")` calls |
| **Expected Behavior** | The system SHALL use a per-model `threading.Lock` to serialize access. The second caller SHALL wait for the first download to complete and then return the cached path. No duplicate downloads SHALL occur. |
| **Test ID** | TS-006 |

### EC-004: HuggingFace Repository Unavailable
| Aspect | Detail |
|--------|--------|
| **Scenario** | HuggingFace servers are unreachable or return HTTP 5xx errors |
| **Input Example** | `requests.exceptions.ConnectionError` during `hf_hub_download()` |
| **Constants** | `MAX_RETRIES = 3`, `INITIAL_BACKOFF_SECONDS = 2`, `BACKOFF_MULTIPLIER = 2` (defined in `download_manager.py`) |
| **Expected Behavior** | The system SHALL retry the download up to 3 times with exponential backoff (2s, 4s, 8s). After all retries fail, the system SHALL set model status to "Not Downloaded" and display: `"Download failed for {model_name}: unable to reach HuggingFace servers. Check your internet connection and retry."` |
| **Test ID** | TS-007 |

### EC-005: GPU VRAM Below All Model Variants
| Aspect | Detail |
|--------|--------|
| **Scenario** | User's GPU has only 2 GB VRAM, but the smallest model variant requires 4 GB |
| **Input Example** | `get_gpu_info()` returns `{"vram_gb": 2.0}`, model variants minimum is `fp16` at 4 GB |
| **Expected Behavior** | The system SHALL select the smallest variant (fp16) anyway but display a warning in the preferences panel: `"Your GPU has 2.0 GB VRAM. Model {model_name} requires at least 4 GB. Inference may fail or fall back to CPU."` The download SHALL proceed — the user can still attempt to use the model. |
| **Test ID** | TS-008 |

### EC-006: Manifest File Missing or Malformed
| Aspect | Detail |
|--------|--------|
| **Scenario** | The embedded `manifest.json` is missing, contains invalid JSON, or is missing required fields |
| **Input Example** | `manifest.json` contains `{"models": [{"model_id": "test"}]}` (missing `repo_id`, `revision`, `sha256`, etc.) |
| **Expected Behavior** | The system SHALL validate the manifest schema on load using the `ModelEntry` dataclass fields. If the file is missing or unparseable, the system SHALL raise `ManifestLoadError` with message: `"Failed to load model manifest: {error_detail}. Tessera model management is disabled until the manifest is restored."` All model-dependent UI elements SHALL display the error state. If individual entries are missing required fields, the system SHALL skip the invalid entry, log ERROR with the entry's `model_id` (if available) and the missing fields, and continue loading valid entries. |
| **Test ID** | TS-016 |

---

## 8. OUT OF SCOPE

> ⚠️ **Explicitly list what this feature does NOT include.** Prevents AI scope creep.

The following are explicitly **excluded** from this feature (with rationale where the scope differs from the originating task):

- ❌ Loading or initializing models for inference (handled by pipeline tasks TASK-TS-0003 through TASK-TS-0005)
- ❌ Model fine-tuning, training, or weight modification
- ❌ Uploading models or any data to external servers
- ❌ Supporting non-HuggingFace download sources (GitHub Releases, direct URLs) — *Rationale: All required models (Depth Anything V2, SAM 2, DINOv2, Zero-1-to-3++, OpenLRM, Trellis, InstantMesh) are available on HuggingFace. Using a single download backend (`huggingface_hub`) reduces implementation complexity and testing surface. GitHub Releases support can be added later if a required model is not available on HuggingFace.*
- ❌ Multi-model ensemble download coordination (each model is independent)
- ❌ Automatic manifest updates from a remote server — manifest is updated only by releasing a new add-on version
- ❌ User authentication with HuggingFace (all repos must be public)
- ❌ Torrent-based or peer-to-peer download mechanisms
- ❌ Model quantization or conversion (GGUF, GPTQ, etc.) — variants are pre-built

---

## 9. SECURITY CONSIDERATIONS

> ⚠️ **Required for all features.** AI-generated code needs explicit security constraints.

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — all model repositories are public on HuggingFace |
| **Auth Method** | None |
| **Required Permissions** | File system read/write (cache directory), network access (HTTPS to huggingface.co only) |
| **Rate Limiting** | N/A — subject to HuggingFace's rate limits on public downloads |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| `model_id`, `repo_id` | Public | Embedded in manifest, no restriction |
| `cache_dir` path | Internal | May contain username in path; log basename only |
| Downloaded model weights | Public | Public model weights; stored locally only |
| SHA256 hashes | Public | Used for integrity verification only |
| GPU device name / VRAM | Internal | Displayed in UI only; not transmitted |
| Download progress data | Internal | In-memory only; not persisted beyond session |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL verify SHA256 hash of every downloaded file against the manifest before making the file available to pipeline tasks. |
| SEC-002 | SHALL only connect to `huggingface.co` and `*.huggingface.co` domains over HTTPS. SHALL NOT connect to any other host. |
| SEC-003 | SHALL NOT use `pickle.load()` or `torch.load(weights_only=False)` on any downloaded file. SHALL only load weights via `safetensors.torch.load_file()` or `torch.load(..., weights_only=True)`. |
| SEC-004 | SHALL NOT execute or import any Python code from downloaded model files. Only data files (`.safetensors`, `.bin`, `.json`, `.pt`, `.pth`, `.onnx`) are permitted. |
| SEC-005 | SHALL use `pathlib.Path.resolve()` to canonicalize all file paths before file system operations to prevent path traversal. |
| SEC-006 | SHALL NOT store or transmit any user-identifying information (file paths, machine names) over the network. Only standard HuggingFace Hub HTTP headers are sent. |

---

## 10. API CONTRACT [CONDITIONAL]

> **Skipped** — This feature does not expose or consume REST/HTTP APIs.

The feature exposes the following **internal Python API** for downstream pipeline tasks:

### 10.1 Model Registry API
```python
from tessera.models.registry import ModelRegistry

registry = ModelRegistry()

# List all registered models
models = registry.list_models()
# Returns: list[ModelEntry]

# Get a specific model entry
entry = registry.get_model("depth-anything-v2-large")
# Returns: ModelEntry or raises ModelNotFoundError
```

### 10.2 Cache Manager API
```python
from tessera.models.cache_manager import CacheManager

cache = CacheManager(cache_dir="/path/to/cache")

# Get local path to a downloaded model (returns None if not cached)
path = cache.get_model_path("depth-anything-v2-large")
# Returns: Optional[Path]

# Get cache usage report
report = cache.get_cache_report()
# Returns: {"total_bytes": 7200000000, "models": [{"model_id": "...", "status": "Downloaded", "size_bytes": 1340000000}, ...]}

# Delete a specific model's cache
cache.delete_model("depth-anything-v2-large")

# Delete all cached models
cache.clear_all()
```

### 10.3 Download Manager API
```python
from tessera.models.download_manager import DownloadManager

dm = DownloadManager(cache_dir="/path/to/cache", registry=registry)

# Download a specific model (blocking, with optional progress callback)
path = dm.ensure_model("depth-anything-v2-large", callback=on_progress)
# callback receives: {"model_id": str, "bytes_downloaded": int, "total_bytes": int, "speed_bps": float, "eta_seconds": float}
# Returns: Path to cached model directory
# Raises: ModelDownloadError on failure

# Download all missing models (blocking, with optional progress callback)
dm.download_all_missing(callback=on_progress)
```

### 10.4 Variant Selector API
```python
from tessera.models.variant_selector import select_variant

variant = select_variant(model_entry, available_vram_gb=6.0)
# Returns: ModelVariant (the fp16 variant for 6 GB VRAM)
# Returns: smallest variant with a warning if VRAM is below all variants' minimums
# Returns: ModelVariant(variant_id="default", ...) constructed from top-level model fields if variants list is empty
```

---

## 11. OBSERVABILITY

> Define logging and metrics for production monitoring.

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------|
| Download started | INFO | `model_id`, `repo_id`, `variant_id`, `size_bytes` | ⚠️ No PII |
| Download progress (every 10%) | DEBUG | `model_id`, `percent_complete`, `speed_bps` | ⚠️ No PII |
| Download completed | INFO | `model_id`, `duration_seconds`, `size_bytes` | ⚠️ No PII |
| Download failed | ERROR | `model_id`, `error_type`, `error_message`, `retry_count` | ⚠️ No PII |
| Download resumed | INFO | `model_id`, `resume_byte_offset`, `total_bytes` | ⚠️ No PII |
| SHA256 verification passed | DEBUG | `model_id`, `filename` | ⚠️ No PII |
| SHA256 verification failed | ERROR | `model_id`, `filename`, `expected_hash`, `actual_hash` | ⚠️ No PII |
| Model cache cleared | INFO | `model_id`, `freed_bytes` | ⚠️ No PII |
| VRAM variant selected | INFO | `model_id`, `variant_id`, `available_vram_gb`, `required_vram_gb` | ⚠️ No PII |
| Cache directory missing | WARN | `cache_dir` (basename only) | ⚠️ No full path |

> All logging uses Python's `logging` module with logger name `"tessera.models"`. Blender routes this to the system console.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only).

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — feature is integral to add-on functionality |
| **Default State** | N/A |
| **Rollout Plan** | Ships with add-on `.zip`; models downloaded on first use |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| SPEC-TS-0001 (Add-on Scaffold) | Yes | Provides preferences panel, cache directory path, GPU detection |
| `huggingface_hub` Python wheel | Yes | Must be bundled in add-on `.zip` as `python-wheel` dependency |
| `safetensors` Python wheel | Yes | Required for secure model loading (SEC-003) |
| Blender 4.2+ | Yes | User must have compatible Blender version |

### 12.3 Rollback Plan
1. User disables the add-on — no downloads will run
2. User can delete the cache directory manually to reclaim disk space
3. Previous add-on version (without model management) can be reinstalled
4. Verify no orphaned `bpy.app.timers` callbacks remain after disable

---

## 13. TEST SCENARIOS

> Map tests to acceptance criteria and edge cases for traceability.

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Download single model, verify file exists and SHA256 matches | Unit | AC-001 | Must Pass |
| TS-002 | Call `get_model_path()` for cached model, verify < 10ms and no network | Unit | AC-002 | Must Pass |
| TS-003 | Interrupt download at 50%, resume, verify completion and SHA256 | Integration | AC-003 | Must Pass |
| TS-004 | Download with insufficient disk space, verify error message | Unit | EC-001 | Must Pass |
| TS-005 | Delete cache directory externally, verify re-detection and status reset | Unit | EC-002 | Must Pass |
| TS-006 | Concurrent `ensure_model()` calls for same model, verify no duplicate downloads | Unit | EC-003 | Must Pass |
| TS-007 | Simulate HuggingFace 500, verify 3 retries with backoff, then error | Unit | EC-004 | Must Pass |
| TS-008 | GPU VRAM below all variants minimum, verify warning + smallest variant selected | Unit | EC-005 | Must Pass |
| TS-009 | Select variant with 6 GB VRAM, model has fp32 (8 GB) and fp16 (4 GB), verify fp16 chosen | Unit | AC-004 | Must Pass |
| TS-010 | Corrupt cached file (flip 1 byte), verify SHA256 failure and deletion | Unit | AC-005 | Must Pass |
| TS-011 | Cache 3 models, verify disk usage display and per-model delete | Integration | AC-006 | Must Pass |
| TS-012 | Open panel with models missing, verify notification banner text and button | Unit | AC-007 | Must Pass |
| TS-013 | Download model on Windows/macOS/Linux, verify cross-platform path handling | Integration | NFR-008 | Should Pass |
| TS-014 | Measure UI fps during active download, verify ≥ 15 fps | Performance | NFR-004 | Should Pass |
| TS-015 | Verify `manifest.json` schema validation on load (missing fields, invalid types) | Unit | FR-001 | Must Pass |
| TS-016 | Delete or corrupt `manifest.json`, verify `ManifestLoadError` and disabled UI | Unit | EC-006 | Must Pass |
| TS-017 | Call `select_variant()` on model with empty `variants` list, verify default variant returned | Unit | FR-012 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0001 (Add-on Scaffold) | Required | Draft | Tessera | Yes — need preferences panel and GPU detection |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| `huggingface_hub` >= 0.23.0 | Required | [huggingface.co/docs/huggingface_hub](https://huggingface.co/docs/huggingface_hub) | No fallback — core download mechanism |
| `safetensors` >= 0.4.0 | Required | [github.com/huggingface/safetensors](https://github.com/huggingface/safetensors) | No fallback — required for secure weight loading |
| HuggingFace public model repositories | Required | Model-specific READMEs | If HuggingFace is down, show error and retry (EC-004) |
| Blender 4.2+ LTS | Required | [docs.blender.org](https://docs.blender.org/api/current/) | No fallback — hard requirement |

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
| SHALL/SHOULD/MAY requirements | 20 | 19 | 19 requirements with precise SHALL/SHOULD/MAY language, each specifically measurable |
| Quantified NFRs | 15 | 14 | 8 NFRs, all quantified with specific targets, units, and measurement conditions |
| Given-When-Then criteria (3+) | 20 | 19 | 7 acceptance criteria in Given-When-Then format with concrete values and verifiable outcomes |
| Edge cases (2+) | 15 | 15 | 6 edge cases with concrete input examples and exact expected behaviors |
| Out of scope defined | 10 | 10 | 9 explicit exclusions with rationale where scope differs from task |
| Security constraints | 10 | 10 | 6 security requirements + data classification table + serialization safety (SEC-003) |
| No ambiguous language | 10 | 10 | Reviewed against ambiguous language checklist; all vague terms replaced with specifics |
| **TOTAL** | **100** | **97** | **Target: ≥80 ✅** |

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
- [x] "handle gracefully" → replaced with specific error messages and behaviors
- [x] "fast" / "efficient" / "performant" → replaced with ms/fps/seconds targets
- [x] "secure" → replaced with SEC-001 through SEC-006
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → not used

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-09 | Orchestrator (AI) | Initial draft |
| 1.1 | 2026-04-14 | AI (Spec Review) | Addressed spec review findings: clarified hf_hub_download vs snapshot_download, documented GitHub Releases scope rationale, specified ensure_model threading contract, added manifest corruption edge case (EC-006), defined empty-variants fallback behavior, added tolerance to AC-003, added TS-016/TS-017, corrected self-score |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0002-model-weight-management.md`
