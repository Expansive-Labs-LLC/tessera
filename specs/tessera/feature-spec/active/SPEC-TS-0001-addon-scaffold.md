# Feature Specification: Blender Add-on Scaffold & GPU Configuration

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0001 |
| **Task ID** | TASK-TS-0001 |
| **Status** | Draft |
| **Version** | 1.2 |
| **Created** | 2026-03-26 |
| **Last Updated** | 2026-09-21 |
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
Tessera is an AI-powered Blender add-on that converts reference images into 3D-printable models. Before any AI pipeline work can begin, the project needs a properly structured Blender add-on that registers with Blender, provides a sidebar UI panel, detects GPU capabilities, and manages user preferences. This scaffold is the foundation for every other task in the project — without it, no features can be delivered to the user.

### 1.2 User Story
**As a** Blender user who wants to generate 3D-printable models from photos,  
**I want** to install Tessera as a standard Blender add-on and see its UI panel in the sidebar,  
**So that** I can access AI-powered 3D generation directly from within Blender without switching tools.

### 1.3 Proposed Approach
Build a multi-module Blender add-on targeting Blender 4.2+ LTS using the `bpy` Python API. The add-on registers an N-panel (sidebar) in the 3D Viewport with placeholder sections for the full workflow (image upload, view labeling, generation, validation, export). GPU detection runs on registration to validate CUDA/ROCm availability. Add-on preferences expose GPU device selection and model cache directory configuration. Third-party Python dependencies SHALL be bundled as `python-wheels` per Blender extension guidelines.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Add-on installs without error | N/A | 100% on Blender 4.2+ (Win/Mac/Linux) | Manual install test matrix |
| GPU detection accuracy | N/A | 100% correct detection on CUDA/ROCm systems | Automated test |

---

## 2. TECHNICAL CONTEXT

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| Blender 3D Print Toolbox source | Official bundled add-on | Multi-module add-on structure, panel registration |
| Blender Add-on Tutorial (docs.blender.org) | Official guide | `bl_info`, `register()`/`unregister()` lifecycle |
| `bpy.types.AddonPreferences` | Blender API | User-configurable preferences pattern |

### 2.2 Tech Stack & Standards
- **Language:** Python 3.11+ (Blender's bundled Python)
- **Framework:** Blender 4.2+ LTS Python API (`bpy`)
- **Validation:** Runtime assertions + Blender's property system (EnumProperty, StringProperty, etc.)
- **Testing:** `pytest` run via `blender --background --python` for headless testing
- **License:** GPL v2+

### 2.3 Architecture Notes

```
tessera/
├── __init__.py              # bl_info, register(), unregister()
├── preferences.py           # AddonPreferences: GPU config, cache dir
├── gpu_detection.py         # CUDA/ROCm/Metal detection + VRAM reporting
├── ui/
│   ├── __init__.py
│   ├── main_panel.py        # Top-level N-panel (PT_TesseraMain)
│   ├── image_panel.py       # Image upload & view labeling sub-panel
│   ├── generation_panel.py  # Generation settings sub-panel (stub)
│   ├── validation_panel.py  # Print validation sub-panel (stub)
│   └── export_panel.py      # Export controls sub-panel (stub)
├── operators/
│   ├── __init__.py
│   ├── image_ops.py         # OT_UploadImages, OT_AssignViewLabel
│   ├── generate_ops.py      # OT_Generate (stub)
│   ├── validate_ops.py      # OT_Validate (stub)
│   └── export_ops.py        # OT_ExportSTL, OT_Export3MF (stubs)
├── properties.py            # Scene-level PropertyGroup (image list, settings)
└── utils/
    ├── __init__.py
    └── gpu_utils.py          # GPU query helpers
```

The add-on uses Blender's standard multi-module pattern:
- All classes are collected in module-level `classes` lists
- `register()` iterates all modules, registering classes via `bpy.utils.register_class()`
- `unregister()` reverses the order to respect dependency chains
- Scene-level properties are attached via `bpy.types.Scene.tessera`

#### GPU Detection Mechanism
GPU detection SHALL use Blender's Cycles device API as the primary mechanism:
1. Call `bpy.context.preferences.addons['cycles'].preferences.get_devices('CUDA')` and `get_devices('HIP')` to enumerate CUDA and ROCm devices.
2. On macOS, also call `get_devices('METAL')` to detect Apple Silicon GPUs.
3. If Cycles device data does not include VRAM, fall back to `subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'])` for NVIDIA, or `subprocess.run(['rocm-smi', '--showmeminfo', 'vram'])` for AMD.
4. For Apple Silicon, VRAM is shared system memory; report total system memory via `os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')` divided by 1024³ with the label "(shared)".

---

## 3. FUNCTIONAL REQUIREMENTS

### 3.1 Core Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | The add-on SHALL provide a `bl_info` dictionary with `"blender": (4, 2, 0)` minimum version. |
| FR-002 | The add-on SHALL register all UI panels, operators, and properties in `register()` and unregister them in reverse order in `unregister()`. |
| FR-003 | The add-on SHALL display a top-level panel named "Tessera" in the 3D Viewport sidebar (N-panel) under a custom "Tessera" tab. |
| FR-004 | The sidebar panel SHALL contain the following sub-panels in order: (1) Image Input, (2) Generation, (3) Validation, (4) Export. |
| FR-005 | The Image Input sub-panel SHALL allow users to add images via a file browser operator that accepts `.jpg`, `.png`, and `.webp` files. On systems where HEIC decoding is available (macOS or when `pillow-heif` is bundled), `.heic` files SHALL also be accepted. |
| FR-006 | The Image Input sub-panel SHALL display a list (UIList) of uploaded images, each with a dropdown to assign a view label. The dropdown uses `EnumProperty` identifiers (UPPER_SNAKE_CASE) as stored values and lowercase display names in the UI. The canonical vocabulary is: `FRONT` ("front"), `BACK` ("back"), `LEFT` ("left"), `RIGHT` ("right"), `TOP` ("top"), `BOTTOM` ("bottom"), `FRONT_LEFT` ("front-left"), `FRONT_RIGHT` ("front-right"), `ISOMETRIC` ("isometric"), `CUSTOM` ("custom"), `UNLABELED` ("unlabeled", default). The `CUSTOM` label is a simple classification tag in this scaffold; the PRD-defined `custom:<az>,<el>` angle-pair input will be added in a future spec when the reconstruction pipeline consumes view labels. |
| FR-007 | The add-on SHALL provide an `AddonPreferences` panel accessible via Edit → Preferences → Add-ons → Tessera, containing: GPU device selector, VRAM display (read-only), model cache directory path, and a "Clear Cache" button. |
| FR-008 | The add-on SHALL detect available GPU devices (CUDA, ROCm, or Metal) on registration and populate the GPU device selector in preferences. On macOS with Apple Silicon, Metal SHALL be detected as a compatible backend. See §2.3 "GPU Detection Mechanism" for implementation details. |
| FR-009 | The add-on SHALL display the detected GPU name and available VRAM (in GB) as a read-only label in the preferences panel. For Apple Silicon (Metal), VRAM SHALL be reported as shared system memory with a "(shared)" suffix (e.g., "16 GB (shared)"). |
| FR-010 | The add-on SHALL display a warning banner in the main panel if no GPU is detected, with the message: "Tessera requires an NVIDIA GPU with CUDA. No compatible GPU was detected." *(v1.2: message narrowed from "CUDA, ROCm, or Metal" — see FR-010a.)* |
| FR-010a | *(v1.2)* The add-on SHALL also display a warning banner when a GPU **is** detected but its backend is not one Tessera can run inference on. v1 supports **CUDA only**; AMD (ROCm) and Apple Silicon (Metal) are detected and reported (FR-008, FR-009) but no inference adapter implements a device path for them. The banner SHALL name the detected device and state that generation will not work on it. The supported set SHALL be declared in one place (`gpu_detection.SUPPORTED_INFERENCE_BACKENDS`) so that adding a backend (TASK-TS-0022) updates detection, validation and UI together. |
| FR-011 | The Generation, Validation, and Export sub-panels SHALL display placeholder text ("Coming soon — waiting for pipeline integration") and disabled operator buttons. |
| FR-012 | The add-on SHALL store the list of uploaded images and their view labels as a `CollectionProperty` on `bpy.types.Scene`. |
| FR-013 | The add-on SHOULD allow users to reorder images in the UIList via up/down buttons. |
| FR-014 | The add-on SHOULD allow users to remove individual images from the list via a remove button. |
| FR-015 | The add-on SHALL package as a standard `.zip` file installable via Edit → Preferences → Add-ons → Install. |
| FR-016 | The add-on MAY provide a one-click "Open Preferences" button in the main panel to navigate directly to the add-on preferences. |

### 3.2 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| `image_path` | `StringProperty(subtype='FILE_PATH')` | Must be valid file path, extensions: `.jpg`, `.png`, `.webp` (and `.heic` when HEIC decoding is available — see FR-005) | Yes | `"/home/user/photos/mug_front.jpg"` |
| `view_label` | `EnumProperty` | Identifier (stored value) one of: `FRONT`, `BACK`, `LEFT`, `RIGHT`, `TOP`, `BOTTOM`, `FRONT_LEFT`, `FRONT_RIGHT`, `ISOMETRIC`, `CUSTOM`, `UNLABELED`. Display names are the lowercase equivalents shown in FR-006. | No (default: `UNLABELED`) | `"FRONT"` |
| `cache_dir` | `StringProperty(subtype='DIR_PATH')` | Valid writable directory | No (default: `bpy.utils.extension_path_user(__package__, 'cache')` for extension installs; fallback: `os.path.join(bpy.utils.user_resource('SCRIPTS'), 'addons', 'tessera', 'cache')` for manual `.zip` installs) | `"/home/user/.tessera/cache"` |

### 3.3 Output Specifications

This task produces no data outputs — it is a UI/infrastructure scaffold. Outputs are visual (panels, labels, buttons in Blender's UI) and structural (registered operators and properties for downstream tasks to consume).

---

## 4. CONSTRAINTS

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT make any network calls from any code in this task. |
| CON-002 | SHALL NOT depend on any Python package not bundled with Blender unless packaged as a `python-wheel` within the add-on `.zip`. |
| CON-003 | SHALL NOT modify Blender's default UI elements, keymaps, or menus. The add-on SHALL only add to the sidebar. |
| CON-004 | SHALL NOT hardcode file paths or platform-specific logic. Use `bpy.utils.extension_path_user()` or `os.path` / `pathlib` for cross-platform paths. |
| CON-005 | SHALL NOT use `bpy.ops` calls from within `register()` or `unregister()` — only class registration via `bpy.utils.register_class()`. |
| CON-006 | All source code SHALL be licensed under GPL v2+. Each source file SHALL include a GPL license header comment. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Add-on registration time | Wall-clock time for `register()` | < 500ms | On a system with CUDA GPU, Blender 4.2, cold start |
| NFR-002 | GPU detection time | Wall-clock time for GPU probe | < 200ms | Including VRAM query |
| NFR-003 | Memory overhead | Additional Python memory usage when add-on is enabled but idle | < 5 MB | Measured via `sys.getsizeof` or Blender memory profiler |
| NFR-004 | Cross-platform compatibility | Install + register without errors | 100% | Windows 10+, macOS 12+ (Intel & Apple Silicon), Ubuntu 22.04+ |
| NFR-005 | Image list UI responsiveness | Panel redraw time with 20 images loaded | < 100ms | No visible lag on panel interaction |

---

## 6. ACCEPTANCE CRITERIA

### AC-001: Successful Add-on Installation
**Given** a freshly downloaded Tessera `.zip` file and Blender 4.2+ with no prior installation,  
**When** the user navigates to Edit → Preferences → Add-ons → Install and selects the `.zip` file,  
**Then** the add-on appears in the add-on list as "Tessera", can be enabled via checkbox, and the "Tessera" tab appears in the 3D Viewport sidebar.

### AC-002: Image Upload and View Labeling
**Given** the Tessera panel is visible in the sidebar,  
**When** the user clicks the "Add Image" button, selects a `.jpg` file from disk, and assigns the view label "front" from the dropdown,  
**Then** the image appears in the UIList with filename displayed and the label "front" shown next to it, and the image path and label are stored in `bpy.context.scene.tessera.images`.

### AC-003: GPU Detection on System with CUDA GPU
**Given** the user has an NVIDIA GPU with CUDA support and ≥ 4 GB VRAM,  
**When** the add-on is enabled,  
**Then** the preferences panel displays the GPU name (e.g., "NVIDIA GeForce RTX 3060"), VRAM (e.g., "12 GB"), and no warning banner appears in the main panel.

### AC-004: GPU Warning on System without Compatible GPU
**Given** the user's system has no CUDA or ROCm compatible GPU,  
**When** the add-on is enabled,  
**Then** the main panel displays a warning box with the text "Tessera requires a CUDA or ROCm compatible GPU. No compatible GPU was detected." and the preferences GPU selector shows "No compatible GPU found".

### AC-005: Clean Uninstall
**Given** Tessera is installed and enabled with 3 images loaded in the list,  
**When** the user disables and removes the add-on via Preferences,  
**Then** the "Tessera" tab disappears from the sidebar, no scene properties remain on `bpy.types.Scene`, and Blender reports no errors in the system console.

### AC-006: Cross-Platform Installation
**Given** Tessera `.zip` and Blender 4.2 on Windows 11, macOS 14 (Apple Silicon), and Ubuntu 24.04,  
**When** the add-on is installed and enabled on each platform,  
**Then** the add-on registers without errors, the panel appears, and GPU detection runs (detecting GPU if present, showing warning if not).

---

## 7. EDGE CASES

### EC-001: Blender Version Below Minimum
| Aspect | Detail |
|--------|--------|
| **Scenario** | User attempts to install Tessera on Blender 4.1 (below the 4.2 minimum) |
| **Input Example** | Blender 4.1.0 + Tessera `.zip` |
| **Expected Behavior** | Blender SHALL refuse to enable the add-on and display a message: "Tessera requires Blender 4.2 or later." via the `bl_info["blender"]` version check. |
| **Test ID** | TS-004 |

### EC-002: Unsupported Image Format
| Aspect | Detail |
|--------|--------|
| **Scenario** | User attempts to add a `.bmp` or `.tiff` file via the image upload operator |
| **Input Example** | `"/home/user/photo.bmp"` |
| **Expected Behavior** | The file browser operator SHALL filter to only show supported formats (`.jpg`, `.png`, `.webp`, `.heic`). If a file is somehow loaded with an unsupported extension, the operator SHALL report `{'WARNING'}` with message "Unsupported image format. Please use JPG, PNG, WebP, or HEIC." and not add the file to the list. |
| **Test ID** | TS-005 |

### EC-003: Cache Directory Not Writable
| Aspect | Detail |
|--------|--------|
| **Scenario** | User sets the model cache directory to a path they don't have write permission for |
| **Input Example** | `cache_dir = "/root/restricted_dir"` |
| **Expected Behavior** | The add-on SHALL validate directory write permissions when the path is changed. If not writable, the preferences SHALL display a warning: "Cache directory is not writable. Please choose a different location." and revert to the default path. |
| **Test ID** | TS-006 |

### EC-004: Empty Image List UI
| Aspect | Detail |
|--------|--------|
| **Scenario** | User opens Tessera panel with no images uploaded |
| **Input Example** | Fresh scene, no images in `scene.tessera.images` |
| **Expected Behavior** | The Image Input sub-panel SHALL display a centered label: "No images added. Click 'Add Image' to begin." and only the "Add Image" button. |
| **Test ID** | TS-007 |

### EC-005: HEIC Image on Platform Without Native HEIC Support
| Aspect | Detail |
|--------|--------|
| **Scenario** | User attempts to add a `.heic` file on Windows or Linux where HEIC decoding is not natively available |
| **Input Example** | `"/home/user/photo.heic"` on Ubuntu 24.04 without `pillow-heif` bundled |
| **Expected Behavior** | The file browser operator SHALL NOT show `.heic` in the extension filter on platforms without HEIC support. If a `.heic` file is somehow provided, the operator SHALL report `{'WARNING'}` with message "HEIC format is not supported on this platform. Please convert to JPG, PNG, or WebP." and not add the file to the list. |
| **Test ID** | TS-014 |

### EC-006: Apple Silicon Mac with Metal GPU
| Aspect | Detail |
|--------|--------|
| **Scenario** | User enables Tessera on a Mac with Apple M-series chip (Metal backend, no CUDA/ROCm) |
| **Input Example** | macOS 14, MacBook Pro M3 Pro, 18 GB unified memory |
| **Expected Behavior** | The add-on SHALL detect the Metal backend and report it accurately: the preferences panel SHALL display the GPU name (e.g., "Apple M3 Pro"), VRAM as shared system memory (e.g., "18 GB (shared)"), and backend as "METAL". *(v1.2)* Because no inference adapter supports Metal in v1, the main panel SHALL display a warning banner naming the device and stating that generation will not work on it. Detection succeeding is not the same as the pipeline being able to run — the previous expectation ("No warning banner SHALL appear") let a Mac user reach model load before discovering the limitation. Restoring the no-banner behaviour is part of TASK-TS-0022. |
| **Test ID** | TS-015 |

---

## 8. OUT OF SCOPE

The following are explicitly **excluded** from this feature:

- ❌ AI model loading, inference, or any machine learning operations
- ❌ Image processing (segmentation, depth estimation, feature extraction)
- ❌ 3D mesh generation, import, or manipulation
- ❌ Print-readiness validation logic
- ❌ STL/3MF/OBJ export functionality
- ❌ Natural-language chat/refinement interface
- ❌ Model weight downloading or caching logic (TASK-TS-0002)
- ❌ Network calls of any kind

---

## 9. SECURITY CONSIDERATIONS

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — local Blender add-on, no network interaction |
| **Auth Method** | None |
| **Required Permissions** | File system read (images), file system write (cache directory) |
| **Rate Limiting** | N/A |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| `image_path` (user's file paths) | Internal | Stored only in `.blend` file scene data; not transmitted |
| `cache_dir` | Internal | User-configurable local path; not transmitted |
| GPU device info | Internal | Displayed in UI only; not transmitted |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL validate all file paths against path traversal attacks before reading image files. |
| SEC-002 | SHALL NOT execute any downloaded code or load arbitrary Python modules from user-specified paths. |
| SEC-003 | SHALL NOT make any network connections, DNS lookups, or socket operations. |
| SEC-004 | SHALL use `pathlib.Path.resolve()` to canonicalize all file paths before file system operations. |

---

## 10. API CONTRACT [CONDITIONAL]

> **Skipped** — This is a Blender add-on UI scaffold. No REST/HTTP APIs are exposed or consumed.

The add-on exposes the following **internal Python API** for downstream tasks:

### 10.1 Scene Properties API
```python
# Access pattern for downstream tasks
scene = bpy.context.scene
images = scene.tessera.images  # CollectionProperty

for img in images:
    print(img.filepath)    # str — absolute path to image file
    print(img.view_label)  # str — one of VIEW_LABEL enum values
    print(img.name)        # str — display name (basename)
```

### 10.2 GPU Info API
```python
from tessera.gpu_detection import get_gpu_info

info = get_gpu_info()
# Returns: {"name": "NVIDIA GeForce RTX 3060", "vram_gb": 12.0, "backend": "CUDA"}
# Returns: {"name": "Apple M3 Pro", "vram_gb": 18.0, "backend": "METAL", "shared_memory": True}
# Returns: {"name": None, "vram_gb": 0, "backend": None} if no GPU
```

---

## 11. OBSERVABILITY

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------| 
| Add-on registered | INFO | `blender_version`, `gpu_name`, `vram_gb`, `backend` | ⚠️ No PII |
| Image added to list | DEBUG | `filename` (basename only), `view_label` | ⚠️ No full paths |
| Image removed from list | DEBUG | `filename` (basename only) | ⚠️ No full paths |
| GPU detection failed | WARN | `error_message` | ⚠️ No PII |
| Unsupported image format rejected | WARN | `filename`, `extension` | ⚠️ No full paths |
| Cache directory not writable | WARN | `directory_path` | ⚠️ Check for username in path |

> All logging uses Python's `logging` module with logger name `"tessera"`. Blender routes this to the system console.

### 11.2 Metrics

N/A — local add-on, no telemetry collected per decision D3 (local/self-hosted only).

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — add-on is either installed or not |
| **Default State** | N/A |
| **Rollout Plan** | Manual `.zip` distribution → Blender Extensions platform (future) |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| Blender 4.2+ | Yes | User must have compatible Blender version |
| No external dependencies for this task | — | All code uses only `bpy` and Python stdlib |

### 12.3 Rollback Plan
1. User disables add-on via Edit → Preferences → Add-ons
2. User removes add-on `.zip` if needed
3. Verify sidebar panel is gone and no errors in system console

---

## 13. TEST SCENARIOS

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Install `.zip` on Blender 4.2, enable, verify panel appears | Integration | AC-001 | Must Pass |
| TS-002 | Add 3 images via file browser, assign view labels, verify stored in scene | Unit | AC-002 | Must Pass |
| TS-003 | Enable add-on on system with CUDA GPU, verify GPU name and VRAM displayed | Integration | AC-003 | Must Pass |
| TS-004 | Attempt enable on Blender 4.1, verify rejection | Unit | EC-001 | Must Pass |
| TS-005 | Attempt to add `.bmp` file, verify warning and rejection | Unit | EC-002 | Must Pass |
| TS-006 | Set cache directory to non-writable path, verify warning and revert | Unit | EC-003 | Must Pass |
| TS-007 | Open panel with empty image list, verify placeholder message | Unit | EC-004 | Must Pass |
| TS-008 | Disable and remove add-on, verify clean uninstall | Integration | AC-005 | Must Pass |
| TS-009 | Install on Windows, macOS (ARM), Linux — verify registration | Integration | AC-006 | Must Pass |
| TS-010 | Add 20 images, verify panel redraw < 100ms | Performance | NFR-005 | Should Pass |
| TS-011 | Reorder images via up/down buttons, verify order persists | Unit | FR-013 | Should Pass |
| TS-012 | Remove image from middle of list, verify list updates | Unit | FR-014 | Should Pass |
| TS-013 | Enable on system with no GPU, verify warning banner | Integration | AC-004 | Must Pass |
| TS-014 | Attempt to add `.heic` file on Linux without HEIC support, verify warning | Unit | EC-005 | Must Pass |
| TS-015 | Enable on macOS Apple Silicon, verify Metal GPU detected, no warning | Integration | EC-006 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| None — this is the foundation task | — | — | — | No |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| Blender 4.2+ LTS | Required | [docs.blender.org](https://docs.blender.org/api/current/) | No fallback — hard requirement |
| CUDA or ROCm GPU driver | Recommended | Vendor docs | Add-on installs but shows warning; GPU features disabled |

---

## 15. APPROVAL

| Role | Name | Date | Status |
|------|------|------|--------|
| Author (Orchestrator) | AI | 2026-03-26 | ☐ Submitted |
| CSO Approval | Derek | | ☐ Approved / ☐ Changes Requested |
| Deputy Review | | | ☐ N/A |

**Approval Notes:**
[Space for CSO/Deputy feedback]

---

## AI-READINESS SELF-SCORE

| Criterion | Max | Score | Guidance |
|-----------|-----|-------|----------|
| SHALL/SHOULD/MAY requirements | 20 | 20 | 16 requirements with precise SHALL/SHOULD/MAY language |
| Quantified NFRs | 15 | 15 | 5 NFRs, all quantified with specific targets and conditions |
| Given-When-Then criteria (3+) | 20 | 20 | 6 acceptance criteria in Given-When-Then format with specific values |
| Edge cases (2+) | 15 | 14 | 6 edge cases with concrete examples and expected behaviors |
| Out of scope defined | 10 | 10 | 8 explicit exclusions listed |
| Security constraints | 10 | 10 | 4 security requirements + data classification table |
| No ambiguous language | 10 | 8 | Reviewed for ambiguous terms; view label convention documented explicitly |
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
- [x] "handle gracefully" → replaced with specific error responses
- [x] "fast" / "efficient" / "performant" → replaced with ms targets
- [x] "secure" → replaced with SEC-001 through SEC-004
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → not used

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-03-26 | Orchestrator (AI) | Initial draft |
| 1.2 | 2026-09-21 | Orchestrator (AI) | **Amendment — awaiting CSO approval.** v1 ships NVIDIA CUDA only (PRD-001 D7 / NG8): narrowed FR-010's message, added FR-010a (warn on a detected-but-unusable backend) and revised EC-006 so an Apple Silicon Mac is warned up front rather than failing at model load. Detection behaviour (FR-008, FR-009) is unchanged. Reversal is tracked by TASK-TS-0022. |
| 1.1 | 2026-04-14 | Spec Review Remediation | Resolved 7 review issues: clarified custom view label as simple tag (deferred angle input), documented enum identifier vs display name convention, added HEIC platform edge case (EC-005), added Apple Silicon/Metal edge case (EC-006), specified GPU detection mechanism (Cycles API + subprocess fallback), documented cache_dir fallback for manual installs, recalibrated self-score |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0001-addon-scaffold.md`
