# Feature Specification: Local Model Weight Management

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0002 |
| **Task ID** | TASK-TS-0002 |
| **Status** | Approved |
| **Version** | 1.3 |
| **Created** | 2026-04-09 |
| **Last Updated** | 2026-09-21 |
| **Author** | Derek |
| **Pod** | Tessera |
| **CSO Approver** | Derek |
| **Spec Type** | Feature |
| **Score** | 92 |

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
Tessera runs entirely locally with no cloud APIs (decision D3). The AI pipelines — vision analysis (TASK-TS-0003), reconstruction (TASK-TS-0004), and mesh processing (TASK-TS-0005) — all depend on multi-gigabyte neural network weight files (Depth Anything V2, SAM 2, DINOv2, TRELLIS). These weights must be downloaded from official sources, cached locally, and version-managed so that inference never requires a network call. Without this infrastructure, no AI pipeline task can function. This is a P1 foundation task that unblocks Phase 1 milestones M1.3 and M1.4.

### 1.2 User Story
**As a** Tessera user,  
**I want** model weights to download automatically on first use and be cached locally,  
**So that** I don't have to manually manage AI model files or worry about disk space.

### 1.3 Proposed Approach
Build a model weight management layer using the `huggingface_hub` Python library as the download and caching backend. The system consists of four components: (1) a **model registry** — a JSON manifest embedded in the add-on that declares every required model with its HuggingFace repo ID, revision, expected SHA256, file size, and minimum VRAM requirement; (2) a **download manager** — a background download engine with progress reporting integrated into Blender's UI, resume support for interrupted downloads, and SHA256 integrity verification; (3) a **cache manager** — disk usage tracking, per-model clear/re-download controls in the add-on preferences panel, and VRAM-aware model variant selection (fp16 vs fp32); and (4) a **licence gate** — a single enforcement point, consulted before any network access, that refuses to download weights whose terms do not unambiguously permit commercial use unless the user has explicitly opted in. The cache directory is user-configurable (defaulting to the path set in SPEC-TS-0001's preferences panel) and all downloads use HTTPS from official HuggingFace repositories.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| First-use download completes without manual intervention | N/A | 100% on systems with ≥ 25 Mbps connection | Manual test on Windows/Mac/Linux |
| Subsequent pipeline invocations load from cache with zero network calls | N/A | 100% | Network traffic monitoring during inference |
| Total core model disk footprint | N/A | < 10 GB | `scan_cache_dir()` output after all core models downloaded |

---

## 2. TECHNICAL CONTEXT

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
│   ├── licensing.py         # Licence gate: classification, opt-in mirror, refusal
│   └── variant_selector.py  # VRAM-aware model variant selection (fp16/fp32)
├── ui/
│   └── download_panel.py    # Download progress UI sub-panel
├── operators/
│   └── model_ops.py         # OT_DownloadModel, OT_ClearModelCache, OT_CheckUpdates
└── ... (existing from SPEC-TS-0001)
```

**Threading model:** Downloads run in a `threading.Thread`. The thread writes progress to a thread-safe `queue.Queue`. A Blender `bpy.app.timers` callback polls the queue at 100ms intervals and updates scene properties that the UI reads. This avoids any direct `bpy` access from the background thread.

**`ensure_model()` threading contract:** The `ensure_model()` function (FR-014) is a blocking call designed for use **within pipeline background threads** (e.g., the reconstruction or vision pipeline threads from TASK-TS-0003+). It SHALL NOT be called from the Blender main thread, as it would block the event loop and violate NFR-004. UI-triggered downloads use the non-blocking `DownloadManager` with progress queue polling instead.

**Licence gate placement:** The gate lives in `tessera/models/licensing.py` and is invoked from `DownloadManager._download_model()` — the single point every download path funnels through — before any network access occurs. It exposes `is_gated()`, `check_download_allowed()` (which raises `ModelLicenseError`), `license_summary()` for UI display, and the opt-in mirror pair `restricted_models_allowed()` / `set_restricted_models_allowed()` plus `sync_from_preferences()`. Only `sync_from_preferences()` touches `bpy` and it is main-thread only; worker threads read `restricted_models_allowed()`.

**Exception hierarchy:** All model-management exceptions are defined in `tessera/models/__init__.py`: `ManifestLoadError`, `ModelNotFoundError`, `ModelLicenseError`, `ModelDownloadError`, `IntegrityError`.

**Integration with SPEC-TS-0001:** The cache directory path is read via `tessera.addon.get_addon_preferences().cache_dir`. The add-on key SHALL NOT be spelled as a literal: Blender keys `context.preferences.addons` by the package name, which is `tessera` for a legacy add-on install and `bl_ext.user_default.tessera` for an extension install, so `tessera.addon.ADDON_ID` resolves it from `__package__`. The same value SHALL be used as `AddonPreferences.bl_idname` — a mismatch registers the class without associating it, and the preferences panel renders empty with no error. The default cache directory comes from `bpy.utils.extension_path_user(ADDON_ID, path="cache", create=False)`, whose `path` argument is keyword-only. The GPU VRAM is read via `tessera.gpu_detection.get_gpu_info()`.

---

## 3. FUNCTIONAL REQUIREMENTS

### 3.1 Core Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL provide a model registry loaded from an embedded `manifest.json` file that declares each required model with fields: `model_id` (unique string), `repo_id` (HuggingFace repository ID), `revision` (Git commit hash or tag), `files` (list of relative file paths within the repo), `sha256` (dict of filename → expected SHA256 hex digest), `size_bytes` (total download size in bytes), `min_vram_gb` (minimum GPU VRAM required in GB), `variants` (list of variant objects, see FR-012), `description` (human-readable purpose), `license` (the weights' licence — an SPDX identifier where one is published, or the literal `"undeclared"` where the publisher states no terms), `license_url` (where those terms are published, or the repository URL when undeclared), and `commercial_use` (one of `"allowed"`, `"restricted"`, `"prohibited"`, `"unknown"` — see FR-020). |
| FR-002 | The system SHALL download model weights from HuggingFace repositories using `huggingface_hub.hf_hub_download()` (per-file download) with the `cache_dir` set to the user's configured cache directory and the `revision` pinned to the manifest-specified commit hash. Per-file download is required because the manifest declares individual files with per-file SHA256 hashes for integrity verification. |
| FR-003 | The system SHALL run all downloads in a background thread that does not block Blender's main UI thread. |
| FR-004 | The system SHALL report download progress to the Blender UI by writing progress data (bytes downloaded, total bytes, download speed in bytes/sec, model name) to a thread-safe queue, polled by a `bpy.app.timers` callback at 100ms intervals. |
| FR-005 | The system SHALL display a download progress bar in the Tessera sidebar panel showing: model name, percentage complete, downloaded/total size in MB, and estimated time remaining. |
| FR-006 | The system SHALL support resuming interrupted downloads by relying on `huggingface_hub`'s built-in resume mechanism (HTTP Range headers). If a download is interrupted (network failure, Blender closed), the next download attempt for the same model SHALL resume from the last downloaded byte. |
| FR-007 | The system SHALL verify the SHA256 hash of each downloaded file against the expected hash in `manifest.json`. If the hash does not match, the system SHALL delete the corrupted file and report an error: `"Integrity check failed for {filename}. Expected SHA256: {expected}. File has been deleted. Please retry the download."` |
| FR-007a | Verification SHALL fail closed. A file whose manifest digest is absent, empty, the literal `"TODO"`, or malformed (not 64 hexadecimal characters) SHALL be reported as a verification **failure**, not skipped. Unlike the digest-mismatch case in FR-007, an unverifiable file SHALL NOT be deleted — the fault is in the manifest, not the file — and the reported error SHALL name the file and direct the reader to add the digest to `manifest.json`. The system SHALL NOT make an unverifiable file available to pipeline tasks. |
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
| FR-020 | *(v1.2)* Each manifest entry SHALL declare the licence of its **weights** via `license`, `license_url` and `commercial_use`. Model weights are third-party, are not redistributed by Tessera, and are not covered by Tessera's GPL-2.0-or-later licence. A `commercial_use` value that is absent or unrecognised SHALL be treated as `"unknown"`. |
| FR-021 | *(v1.2)* The system SHALL refuse to download any model whose `commercial_use` is not `"allowed"` unless the user has explicitly opted in. This gate SHALL fail closed: `"restricted"`, `"prohibited"` and `"unknown"` are all refused by default. The refusal SHALL raise `ModelLicenseError` naming the model, its licence, the reason, and how to opt in. |
| FR-022 | *(v1.2)* The opt-in SHALL be an add-on preference, `allow_restricted_license_models`, defaulting to **disabled**, displayed with a warning when enabled. Because downloads run on worker threads that SHALL NOT touch `bpy` (CON-003), the preference SHALL be mirrored into a module-level flag set from the main thread on registration, on preference change, and at each download operator's entry point. |
| FR-023 | *(v1.2)* The licence gate SHALL be enforced at the single download choke point so that every path is covered: explicit download, background download, download-all, and first-use auto-download (FR-018). `start_download_all_missing()` SHALL skip gated models rather than fail the batch. |
| FR-024 | *(v1.2)* The Models table (FR-008) SHALL display each model's licence, SHALL visually flag entries that are gated, and SHALL disable the Download action for a gated model until the user opts in. |

| FR-026 | *(v1.3)* The model list SHALL be user-extensible. User-added models SHALL be persisted to `<cache_dir>/user_models.json` — outside the add-on directory, so additions survive an add-on update — and merged over the bundled manifest at registry load. A malformed user file SHALL be logged and skipped, never fatal: bundled models SHALL still load. |
| FR-027 | *(v1.3)* A user-added model SHALL declare the architecture **family** it belongs to, chosen from the families an adapter can instantiate (`tessera.models.families`). The system SHALL NOT offer a family it has no adapter for. A family whose adapter cannot yet load an arbitrary variant SHALL be marked as such and SHALL name the task that will change it, so the Models table can say so on the row. |
| FR-028 | *(v1.3)* The system SHALL resolve a user-chosen model before registering it: `GET /api/models/{repo_id}` supplies the declared licence, the current commit, and the file list, filtered to the family's permitted extensions and to `ALLOWED_EXTENSIONS` (SEC-004). The resolved commit SHA SHALL be pinned into the entry — a moving ref SHALL NOT be stored. |
| FR-029 | *(v1.3)* The system SHALL record a SHA256 digest for every file of a user-added model before registering it, via `POST /api/models/{repo_id}/paths-info/{revision}` (a file's LFS `oid` is its SHA256). A non-LFS file below 1 MB MAY be downloaded and hashed locally. A file whose digest cannot be established SHALL cause the addition to be refused — the system SHALL NOT register a model it cannot verify (SEC-001, FR-007a). |
| FR-030 | *(v1.3)* The licence of a user-added model SHALL be classified from the publisher's declared identifier, before any weights are downloaded, into the same vocabulary as FR-020. Non-commercial identifiers SHALL classify as `prohibited`; OpenRAIL/RAIL-family and community licences (Llama, Gemma) as `restricted`; `other`, empty or absent as `unknown`; only recognised permissive identifiers as `allowed`. The gate of FR-021 SHALL apply unchanged, and the refusal SHALL name the declared licence so the user learns the terms without downloading anything. |
| FR-031 | *(v1.3)* The add flow SHALL state, before the model is added, that weights are third-party, that Tessera checks only what the publisher declares, and that compliance with each licence is the user's responsibility. The Models table SHALL identify user-added entries and show their source repository. |
| FR-032 | *(v1.3)* A user-added model SHALL NOT shadow a bundled model id; such an addition SHALL be refused with a message naming the collision. Registration SHALL be atomic — if persistence fails, the in-memory registry SHALL be rolled back. |
| FR-033 | *(v1.3)* The system SHALL allow removing a user-added model, persisting the change. Removal SHALL NOT delete cached weight files — that remains the Delete action of FR-010. Removing a **bundled** model SHALL be refused. |
| FR-025 | The licence gate SHALL be enforced at download time only. Once weights have been downloaded under an active opt-in, they SHALL remain usable if the opt-in is later withdrawn: `get_model_path()` SHALL NOT perform a licence check, and `ensure_model()` SHALL return a cached path without re-consulting the gate. Withdrawing the opt-in SHALL prevent further downloads of gated models, and the Models table SHALL continue to display the licence of any cached gated model so the user can identify and delete it. |

### 3.2 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| `model_id` | `str` | Matches a key in `manifest.json`, alphanumeric + hyphens, max 64 chars | Yes | `"depth-anything-v2-small"` |
| `cache_dir` | `str` | Valid writable directory path (inherited from SPEC-TS-0001 preferences) | Yes | `"/home/user/.tessera/cache"` |
| `variant_id` | `str` | One of variant IDs in the model's `variants` list, or `"auto"` for VRAM-based selection | No (default: `"auto"`) | `"fp16"` |

```python
# Manifest entry type definition
@dataclass
class ModelVariant:
    variant_id: str       # e.g. "fp16", "fp32"
    min_vram_gb: float    # minimum VRAM required
    size_bytes: int       # download size for this variant
    files: list[str]      # relative file paths within repo for this variant

@dataclass
class ModelEntry:
    model_id: str         # unique identifier, e.g. "depth-anything-v2-small"
    repo_id: str          # HuggingFace repo, e.g. "depth-anything/Depth-Anything-V2-Small"
    revision: str         # pinned commit hash, e.g. "a5b2b12b..."
    description: str      # human-readable, e.g. "Monocular depth estimation"
    files: list[str]      # default file list (no variants)
    sha256: dict[str, str]  # filename → expected SHA256 hex digest
    size_bytes: int       # total download size in bytes
    min_vram_gb: float    # minimum VRAM for default variant
    license: str          # weights licence, e.g. "Apache-2.0"  (v1.2)
    license_url: str      # where those terms are published      (v1.2)
    commercial_use: str   # allowed | restricted | prohibited | unknown (v1.2)
    variants: list[ModelVariant]  # optional VRAM-tiered variants
```

### 3.3 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `model_path` | `pathlib.Path` | Absolute path to cached model directory | `Path("/home/user/.tessera/cache/models--depth-anything--Depth-Anything-V2-Small/snapshots/a5b2b12b/")` |
| `download_progress` | `dict` | `{"model_id": str, "bytes_downloaded": int, "total_bytes": int, "speed_bps": float, "eta_seconds": float}` | `{"model_id": "depth-anything-v2-small", "bytes_downloaded": 524288000, "total_bytes": 1340000000, "speed_bps": 5242880.0, "eta_seconds": 156.0}` |
| `cache_report` | `dict` | `{"total_bytes": int, "models": [{"model_id": str, "status": str, "size_bytes": int}]}` | See cache manager API |

```python
# Public API return types
from pathlib import Path
from typing import Optional, Callable

def get_model_path(model_id: str) -> Optional[Path]:
    """Returns the local path to a cached model, or None if not downloaded.

    Performs no licence check (FR-025). Raises ModelNotFoundError if the
    model_id is not in the manifest.
    """
    ...

def ensure_model(model_id: str, callback: Optional[Callable] = None) -> Path:
    """Downloads model if not cached, returns local path.

    Raises:
        ModelLicenseError: the model is licence-gated and the user has not
            opted in (FR-021). Raised before any network access.
        IntegrityError: a downloaded file failed SHA256 verification, or its
            manifest digest is absent, empty, "TODO" or malformed (FR-007a).
        ModelDownloadError: the download failed after all retries (EC-004).
        ModelNotFoundError: model_id is not declared in the manifest.
    """
    ...

def get_cache_report() -> dict:
    """Returns disk usage summary for all registered models."""
    ...
```

---

## 4. CONSTRAINTS

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

### AC-001: First-Use Model Download with Progress
**Given** Tessera is installed with no models cached and the user has a working internet connection,  
**When** the user opens add-on preferences and clicks "Download All Required",  
**Then** each model downloads sequentially, the UI shows a progress bar per model with model name, percentage (0–100%), downloaded/total MB, estimated time remaining, and upon completion the status column shows "Downloaded" for all models.

### AC-002: Pipeline Loads Model from Cache Without Network
**Given** the model `depth-anything-v2-small` has been previously downloaded and cached,  
**When** a downstream pipeline task calls `get_model_path("depth-anything-v2-small")`,  
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

### AC-008: Licence-Gated Model Is Refused by Default *(v1.2)*
**Given** the manifest declares `depth-anything-v2-large` with `commercial_use: "prohibited"` and the user has not enabled `allow_restricted_license_models`,
**When** any download path is invoked for that model — explicit download, background download, download-all, or first-use auto-download —
**Then** no network request is made for it, a `ModelLicenseError` is raised naming the model, its licence (`CC-BY-NC-4.0`), the reason, and the preference that enables it; the Models table shows the licence and a disabled Download action; and `start_download_all_missing()` skips the model and continues with the rest.

### AC-009: Unverifiable File Is Rejected *(v1.2)*
**Given** a cached model file whose manifest digest is absent, empty, or `"TODO"`,
**When** the system performs integrity verification,
**Then** verification returns a failure naming the file, the download raises `IntegrityError`, and the file is not made available to pipeline tasks.

### AC-010: User Adds a Model From Hugging Face *(v1.3)*
**Given** a user supplies the repository id `depth-anything/Depth-Anything-V2-Base`, the family *Depth Anything V2* and the variant `vitb`, with `allow_restricted_license_models` disabled,
**When** they confirm the add dialog,
**Then** the system resolves the repository, reads the declared licence `cc-by-nc-4.0`, classifies it as `prohibited`, refuses the addition with a message naming that licence and the preference that would permit it, and downloads nothing.
**And Given** the same flow against an `apache-2.0` repository,
**Then** the model is registered with its commit SHA pinned and a SHA256 recorded for every file, is written to `<cache_dir>/user_models.json`, appears in the Models table marked as user-added with its source repository, and is still listed after the add-on is re-registered.

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
| **Input Example** | Two concurrent `ensure_model("depth-anything-v2-small")` calls |
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

The following are explicitly **excluded** from this feature (with rationale where the scope differs from the originating task):

- ❌ Loading or initializing models for inference (handled by pipeline tasks TASK-TS-0003 through TASK-TS-0005)
- ❌ Model fine-tuning, training, or weight modification
- ❌ Uploading models or any data to external servers
- ❌ Supporting non-HuggingFace download sources (GitHub Releases, direct URLs) — *Rationale: Every model in the shipped manifest (Depth Anything V2, SAM 2, DINOv2, TRELLIS) is available on HuggingFace. Using a single download backend (`huggingface_hub`) reduces implementation complexity and testing surface. GitHub Releases support can be added later if a required model is not available on HuggingFace.*
- ❌ Multi-model ensemble download coordination (each model is independent)
- ❌ Automatic manifest updates from a remote server — manifest is updated only by releasing a new add-on version
- ❌ User authentication with HuggingFace (all repos must be public)
- ❌ Torrent-based or peer-to-peer download mechanisms
- ❌ Model quantization or conversion (GGUF, GPTQ, etc.) — variants are pre-built

---

## 9. SECURITY CONSIDERATIONS

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
| Downloaded model weights (`commercial_use: allowed`) | Public | Openly licensed weights; stored locally only |
| Downloaded model weights (gated: `restricted` / `prohibited` / `unknown`) | Restricted | Downloadable only under explicit user opt-in (FR-021). Never redistributed. Licence displayed wherever the model is listed (FR-024) so the user can identify and delete them. Output produced through `prohibited` weights may not be used commercially. |
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
| SEC-007 | *(v1.2)* SHALL NOT download model weights whose licence terms forbid, restrict, or fail to declare commercial use, unless the user has explicitly opted in (FR-021). The default posture is refusal. |
| SEC-008 | *(v1.3)* Metadata lookups for user-added models SHALL contact `huggingface.co` over HTTPS and no other host (consistent with SEC-002). A user-supplied repository id SHALL be validated against the `owner/name` form before it is used in a URL, and the Hub response SHALL NOT be trusted to name files outside `ALLOWED_EXTENSIONS` (SEC-004). |

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
entry = registry.get_model("depth-anything-v2-small")
# Returns: ModelEntry or raises ModelNotFoundError
```

### 10.2 Cache Manager API
```python
from tessera.models.cache_manager import CacheManager

cache = CacheManager(cache_dir="/path/to/cache")

# Get local path to a downloaded model (returns None if not cached)
path = cache.get_model_path("depth-anything-v2-small")
# Returns: Optional[Path]

# Get cache usage report
report = cache.get_cache_report()
# Returns: {"total_bytes": 7200000000, "models": [{"model_id": "...", "status": "Downloaded", "size_bytes": 1340000000}, ...]}

# Delete a specific model's cache
cache.delete_model("depth-anything-v2-small")

# Delete all cached models
cache.clear_all()
```

### 10.3 Download Manager API
```python
from tessera.models.download_manager import DownloadManager

dm = DownloadManager(cache_dir="/path/to/cache", registry=registry)

# Download a specific model (blocking, with optional progress callback)
path = dm.ensure_model("depth-anything-v2-small", callback=on_progress)
# callback receives: {"model_id": str, "bytes_downloaded": int, "total_bytes": int, "speed_bps": float, "eta_seconds": float}
# Returns: Path to cached model directory
# Raises: ModelLicenseError  — gated model, no opt-in (FR-021); raised before any network access
#         IntegrityError     — SHA256 mismatch, or absent/placeholder/malformed digest (FR-007, FR-007a)
#         ModelDownloadError — download failed after all retries (EC-004)
#         ModelNotFoundError — model_id not in the manifest

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

### 10.5 Licence Gate API
```python
from tessera.models import licensing

# Whether an entry requires explicit opt-in (restricted / prohibited / unknown)
licensing.is_gated(model_entry)                    # -> bool

# Raise ModelLicenseError if this model may not be downloaded right now
licensing.check_download_allowed(model_entry)      # -> None | raises ModelLicenseError

# One-line licence text for the Models table (FR-024)
licensing.license_summary(model_entry)             # -> "CC-BY-NC-4.0 — non-commercial only"

# Opt-in mirror. sync_from_preferences() is MAIN THREAD ONLY (CON-003);
# worker threads read restricted_models_allowed().
licensing.restricted_models_allowed()              # -> bool   (thread-safe read)
licensing.set_restricted_models_allowed(value)     # main thread
licensing.sync_from_preferences()                  # main thread; no-op when bpy is unavailable
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
| TS-018 | Every entry in the shipped manifest declares `license`, `license_url` and a recognised `commercial_use` | Unit | FR-020 | Must Pass |
| TS-019 | A model with `commercial_use` of `prohibited`, `restricted`, `unknown`, or absent is refused without opt-in and permitted with it | Unit | FR-021, FR-022, SEC-007, AC-008 | Must Pass |
| TS-020 | A file with an absent, empty, `"TODO"` or malformed digest fails verification and is not deleted; the shipped manifest contains no such digests | Unit | FR-007a, AC-009, SEC-001 | Must Pass |
| TS-021 | Every download entry point — `ensure_model()`, the download operator, `start_download_all_missing()`, and first-use auto-download — reaches `check_download_allowed()` before any network call; `start_download_all_missing()` skips a gated model and completes the rest | Unit | FR-023 | Must Pass |
| TS-022 | The Models table renders each entry's licence, flags gated entries, and disables their Download action until the opt-in is enabled | Unit | FR-024 | Must Pass |
| TS-023 | A gated model downloaded under an active opt-in remains resolvable by `get_model_path()` and `ensure_model()` after the opt-in is withdrawn, while a fresh download of a gated model is refused | Unit | FR-025 | Must Pass |
| TS-024 | Licence identifiers classify correctly: permissive → allowed, `-nc` → prohibited, OpenRAIL/Llama/Gemma → restricted, `other`/absent/unrecognised → unknown | Unit | FR-030 | Must Pass |
| TS-025 | Repository lookup pins the commit, filters non-model files, and rejects malformed ids, unsupported families, repositories with no usable files, and non-Hugging-Face URLs | Unit | FR-027, FR-028, SEC-008 | Must Pass |
| TS-026 | A built entry carries a digest for every file — LFS `oid` passed through, small files hashed locally — and refuses unverifiable or oversized models | Unit | FR-029, SEC-001 | Must Pass |
| TS-027 | User models persist across a registry reload, cannot shadow or remove bundled models, roll back on persistence failure, are licence-gated like bundled ones, and a corrupt user file leaves bundled models working | Unit | FR-026, FR-032, FR-033, AC-010 | Must Pass |

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
| Author | Derek | 2026-09-21 | ☑ Submitted |
| CSO Approval | Derek | 2026-09-21 | ☑ Approved |
| Deputy Review | — | — | ☑ N/A |

**Approval Notes:**
v1.3 approved 2026-09-22. v1.2 approved 2026-09-21. The licence gate, the fail-closed integrity change and the manifest reduction to four shipping models are implemented and covered by TS-018 through TS-023. Weight licences are recorded in `MODEL-LICENSES.md` and must be re-verified before any commercial release, as upstream terms can change under a bumped revision.

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-09 | Derek | Initial draft |
| 1.1 | 2026-04-14 | Derek | Documented why per-file `hf_hub_download()` is used instead of `snapshot_download()`; recorded the rationale for excluding non-HuggingFace download sources; specified the `ensure_model()` threading contract; added the manifest-corruption edge case (EC-006); defined the empty-`variants` fallback in FR-012; added resume tolerance to AC-003; added TS-016 and TS-017 |
| 1.3 | 2026-09-21 | Derek | Made the model list user-extensible (FR-026 – FR-033, SEC-008, AC-010, TS-024 – TS-027): a user can add any compatible Hugging Face model, resolved and commit-pinned at add time, licence-classified before download by the same fail-closed gate as bundled models, with a SHA256 recorded for every file or the addition refused. User entries persist outside the add-on so they survive updates, cannot shadow or remove bundled ids, and cannot be added for an architecture no adapter can load. Documented in `docs/docs/user-guide/custom-models.md` and `MODEL-LICENSES.md`. |
| 1.2 | 2026-09-21 | Derek | Added weight-licence metadata and a fail-closed licence gate (FR-020–FR-025, SEC-007, AC-008, TS-018/019/021/022/023) after `depth-anything-v2-large` (CC-BY-NC-4.0) was found serving as the default depth model. Made SHA256 verification fail closed on absent, empty, placeholder and malformed digests without deleting the file (FR-007a, AC-009, TS-020). Documented the gate module and exception hierarchy in §2.3, the `ModelLicenseError` / `IntegrityError` contracts in §3.3 and §10, the licence gate API in §10.5, and restricted-weight handling in §9.2. Removed Zero123++ and InstantMesh from the manifest, and from the model lists in §1.1 and §8, as no adapter referenced them. Switched worked examples to the Apache-2.0 Small checkpoint. See `MODEL-LICENSES.md`. |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0002-model-weight-management.md`
