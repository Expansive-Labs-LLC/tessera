# Feature Specification: Local Inference Engine

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0023 |
| **Task ID** | TASK-TS-0023 |
| **Status** | Draft |
| **Version** | 1.0 |
| **Created** | 2026-09-22 |
| **Last Updated** | 2026-09-22 |
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

Tessera's weight management is complete: models download on first use, are commit-pinned, digest-verified and licence-gated (SPEC-TS-0002). What is missing is the runtime that consumes them. Every inference adapter requires PyTorch — SAM 2 (10 references), DINOv2 (12), Depth Anything V2 and TRELLIS — and TRELLIS additionally requires compiled CUDA extensions. None of that can ship inside a Blender add-on archive, which is currently under 400 KB against a CUDA PyTorch distribution measured in gigabytes.

The consequence is that `AdapterRegistry` falls back to `StubAdapter` and the Generate button returns a placeholder cube. `tessera/models/families.py` records `adapter_ready=False` for `sam2`, `dinov2` and `trellis`. **No configuration of Tessera currently produces a real mesh.**

ADR-0001 decided the delivery mechanism: a thin add-on plus a separately installed local engine process. This spec defines that engine and the boundary between the two.

### 1.2 User Story
**As a** Tessera user who has installed the add-on and downloaded the models,
**I want** the Generate button to produce an actual 3D mesh from my photo,
**So that** the product does the thing it is for.

### 1.3 Proposed Approach

Split the product across a process boundary along the line that already exists in the code — the adapter interface.

The **add-on** remains a small GPL-2.0-or-later Blender extension. It keeps the UI, operators, weight registry, download manager, cache manager and licence gate. It gains an engine client: discovery, health check, version negotiation, and a request/response path for inference.

The **engine** is a separately installed local process with its own virtual environment carrying PyTorch, the CUDA runtime and TRELLIS's compiled extensions. It hosts the adapter implementations, which move out of the add-on largely unchanged. It exposes a small local HTTP API and never reaches the network for anything else.

Weight governance does not move. The add-on resolves and verifies weights and passes **absolute paths** to the engine; the engine never resolves, downloads or verifies weights itself. This keeps the licence gate a single choke point (SPEC-TS-0002 FR-023) rather than creating a second one to keep in sync.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Generate produces a real mesh | 0% — stub cube | 100% with engine installed | Manual generate on the test image set |
| Engine install completed unaided | N/A | ≥ 90% of first-time users | Install funnel telemetry is out of scope; measured by supervised testing |
| Add-on archive size | < 400 KB | < 1 MB | `build_addon.sh` output |
| Inference failures surfaced as actionable UI state | 0% | 100% | Fault injection: engine absent, stopped, version-skewed |

---

## 2. TECHNICAL CONTEXT

### 2.1 Related Code Patterns

| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/reconstruction/adapter.py` | `ReconstructionAdapter` interface | The boundary the split follows; the engine hosts implementations of it |
| `tessera/reconstruction/adapters/trellis_adapter.py` | TRELLIS adapter | Moves engine-side; its weight resolution stays add-on side |
| `tessera/reconstruction/registry.py` | Adapter selection and `StubAdapter` fallback | Where engine availability becomes an adapter-selection input |
| `tessera/models/cache_manager.py` | `get_model_path()`, `verify_integrity()` | Stays add-on side; supplies the paths sent to the engine |
| `tessera/models/licensing.py` | `check_download_allowed()` | Stays add-on side; the engine is never a download path |
| `tessera/addon.py` | `ADDON_ID`, `get_addon_preferences()` | Preference access for engine settings |

### 2.2 Tech Stack & Standards

- **Add-on language:** Python 3.11+ (Blender's bundled Python), `bpy`, GPL-2.0-or-later
- **Add-on HTTP client:** `urllib.request` (stdlib) — no new add-on dependency
- **Engine language:** Python 3.11+ in its own virtual environment
- **Engine HTTP server:** stdlib `http.server` or a single small dependency; the engine's dependency set is not constrained by Blender
- **Engine ML stack:** PyTorch with CUDA, `safetensors`, TRELLIS and its compiled extensions
- **Transport:** HTTP over `127.0.0.1` only
- **Testing:** `pytest` for both sides; engine-side adapter tests run without Blender

### 2.3 Architecture Notes

```
Blender process                          Engine process
┌──────────────────────────────┐        ┌────────────────────────────┐
│ tessera/  (GPL add-on)       │        │ tessera_engine/            │
│  models/    registry, cache, │        │   server.py   HTTP API     │
│             licensing  ◄─────┼─ owns  │   adapters/   torch impls  │
│  engine/                     │  weights│   runtime.py  CUDA, VRAM  │
│    client.py   HTTP client   │──────► │                            │
│    discovery.py  find/health │  paths │  own venv: torch + CUDA +  │
│    lifecycle.py  spawn/stop  │        │  compiled extensions       │
│  reconstruction/             │        └────────────────────────────┘
│    registry.py  selection    │
└──────────────────────────────┘
```

**Boundary rule:** the add-on owns *what* to run and *on which verified files*; the engine owns *how* to run it. Weight resolution, digest verification and licence gating never cross to the engine side.

**Threading:** engine calls are blocking HTTP and SHALL run on the same background threads pipeline work already uses. `bpy` is never touched from those threads (SPEC-TS-0002 CON-003); results reach the UI through the existing `bpy.app.timers` queue.

**Version negotiation:** the add-on and engine exchange a protocol version on connect. A mismatch is reported as an actionable state, never worked around.

---

## 3. FUNCTIONAL REQUIREMENTS

### 3.1 Core Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | Before any engine implementation begins, the two premises ADR-0001 was accepted without verifying SHALL be confirmed and recorded: the Extensions Platform archive size limit, and whether prebuilt CUDA-extension wheels exist for the target GPU generation. If either contradicts ADR-0001, implementation SHALL stop and the ADR SHALL be reopened. |
| FR-002 | The engine SHALL be a separate OS process with its own Python environment, containing no `bpy` import and no dependency on Blender. |
| FR-003 | The engine SHALL expose an HTTP API bound to `127.0.0.1` only. It SHALL NOT bind to any externally reachable interface. |
| FR-004 | The engine SHALL expose `GET /health` returning its protocol version, engine version, CUDA availability, GPU name and total VRAM in GB. |
| FR-005 | The engine SHALL expose `POST /reconstruct` accepting resolved absolute weight paths, image data and view labels, returning vertices, faces, optional vertex colours, and a confidence value. |
| FR-006 | The engine SHALL expose `POST /vision` for the segmentation, depth and feature stages, accepting resolved weight paths and image data. |
| FR-007 | The engine SHALL NOT resolve, download, or verify model weights. It SHALL accept only absolute paths supplied by the add-on, and SHALL reject a request whose paths do not exist rather than attempting to obtain them. |
| FR-008 | The engine SHALL NOT make any network call other than serving its own local HTTP endpoint. |
| FR-009 | The add-on SHALL verify weight integrity (SPEC-TS-0002 FR-007, FR-007a) and licence eligibility (FR-021, SEC-007) **before** sending any path to the engine. |
| FR-010 | The add-on SHALL provide an engine client exposing `is_available()`, `health()`, `reconstruct()` and `vision()`, raising `EngineUnavailableError` when the engine cannot be reached. |
| FR-011 | The add-on and engine SHALL exchange an integer protocol version. If the engine's version is not supported by the add-on, the client SHALL raise `EngineVersionError` naming both versions and the required action. |
| FR-012 | `AdapterRegistry` SHALL treat engine availability as an input to adapter selection: when the engine is unreachable or version-incompatible, engine-backed adapters SHALL be excluded and the existing `StubAdapter` fallback SHALL apply. |
| FR-013 | The add-on SHALL display engine status in the Tessera panel — one of `Not installed`, `Stopped`, `Starting`, `Ready`, or `Version mismatch` — with an action appropriate to each. |
| FR-014 | When the engine is not installed, the add-on SHALL NOT attempt inference and SHALL present installation guidance. It SHALL NOT fail inside `torch` or any engine-side import. |
| FR-015 | The engine SHALL be installable in a single user-initiated flow that does not require the user to run `pip`, edit a path, or modify Blender's bundled Python. |
| FR-016 | The engine SHALL be installable and updatable independently of the add-on; updating one SHALL NOT require reinstalling the other, subject to FR-011. |
| FR-017 | The add-on SHALL provide an engine host and port preference, defaulting to `127.0.0.1` and a fixed default port, so a user can run the engine on a non-default port. |
| FR-018 | The add-on SHOULD be able to start a locally installed engine on demand and SHOULD report startup failure with the engine's own error output rather than a timeout alone. |
| FR-019 | The engine SHALL return a structured error for insufficient VRAM, naming the required and available amounts, so the add-on can present the existing VRAM guidance (SPEC-TS-0004). |
| FR-020 | The engine SHALL free GPU memory after each request, whether it succeeded or failed. |
| FR-021 | The engine SHALL process one inference request at a time and SHALL reject a concurrent request with a documented busy response rather than queueing indefinitely or running both. |
| FR-022 | The add-on SHALL log engine interactions under the existing `tessera` logger, recording endpoint, duration and outcome, and SHALL NOT log image data or absolute paths containing a username (SPEC-TS-0002 §9.2). |
| FR-023 | The engine SHALL NOT load weights via `pickle` or `torch.load(weights_only=False)`; it SHALL use `safetensors` or `torch.load(..., weights_only=True)` (inherits SPEC-TS-0002 SEC-003, CON-008). |
| FR-024 | v1 SHALL target NVIDIA CUDA only (PRD-001 D7, NG8). The engine's device selection SHALL be a single replaceable component so that adding ROCm or Metal is an engine build change and not an add-on change. |

### 3.2 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| `engine_host` | `str` | Loopback address | Yes (default `127.0.0.1`) | `"127.0.0.1"` |
| `engine_port` | `int` | 1024–65535 | Yes (default fixed) | `8765` |
| `weight_paths` | `dict[str, str]` | Absolute paths that exist and have passed verification | Yes | `{"trellis": "/…/snapshots/ab12/"}` |
| `protocol_version` | `int` | Compared against the add-on's supported set | Yes | `1` |

### 3.3 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `health` | `dict` | `{"protocol_version": int, "engine_version": str, "cuda": bool, "gpu": str, "vram_gb": float}` | `{"protocol_version": 1, "cuda": true, "vram_gb": 32.0}` |
| `reconstruct` | `dict` | `{"vertices": [[float]], "faces": [[int]], "vertex_colors": [[float]] \| null, "confidence": float}` | — |
| `error` | `dict` | `{"error": str, "detail": str, "retryable": bool}` | `{"error": "insufficient_vram", "retryable": false}` |

---

## 4. CONSTRAINTS

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT vendor PyTorch, CUDA libraries or compiled extensions into the add-on archive. |
| CON-002 | SHALL NOT import `bpy` anywhere in the engine. |
| CON-003 | SHALL NOT touch `bpy` from the background threads that call the engine; UI updates go through `bpy.app.timers` (inherits SPEC-TS-0002 CON-003). |
| CON-004 | SHALL NOT bind the engine to any interface other than loopback. |
| CON-005 | SHALL NOT give the engine the ability to download, resolve or verify weights — that remains the add-on's single choke point. |
| CON-006 | SHALL NOT make network calls during inference (inherits PRD-001 D3, SPEC-TS-0002 CON-001). |
| CON-007 | SHALL NOT require the user to modify Blender's bundled Python environment. |
| CON-008 | SHALL NOT use `pickle.load()` or `torch.load(weights_only=False)` on any weight file. |
| CON-009 | Add-on source SHALL remain GPL-2.0-or-later with a licence header on each file. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Engine health check latency | Round trip | < 100 ms | Engine running on loopback |
| NFR-002 | Engine availability detection when absent | Time to report `Not installed` | < 500 ms | No process listening on the configured port |
| NFR-003 | IPC overhead relative to inference | Added wall-clock | < 2% of total, or < 500 ms | Single-image reconstruction |
| NFR-004 | Add-on archive size | `build_addon.sh` output | < 1 MB | Any build |
| NFR-005 | Engine startup to `Ready` | Cold start | < 30 s | Engine installed, weights cached |
| NFR-006 | UI responsiveness during inference | Blender viewport frame rate | ≥ 15 fps | Inference in flight |
| NFR-007 | GPU memory released after a request | Residual VRAM held by the engine | < 500 MB above idle | 10 sequential reconstructions |
| NFR-008 | Engine install, unaided completion | Supervised first-time users | ≥ 90% | Usability testing on each supported platform |

---

## 6. ACCEPTANCE CRITERIA

### AC-001: Generate Produces a Real Mesh
**Given** the add-on is installed, the engine is installed and `Ready`, and the default models are cached,
**When** the user loads a photograph and clicks Generate,
**Then** an engine-backed adapter is selected rather than `StubAdapter`, inference runs in the engine process, and a mesh with more than 8 vertices and more than 12 faces appears in the Blender scene.

### AC-002: Engine Absent Is an Actionable State, Not a Crash
**Given** the add-on is installed and no engine is installed,
**When** the user opens the Tessera panel and clicks Generate,
**Then** the panel shows engine status `Not installed` with installation guidance, no request is attempted, no `torch` import is evaluated in the Blender process, and the reconstruction registry falls back to `StubAdapter` without raising.

### AC-003: Version Skew Is Refused, Not Guessed
**Given** an installed engine reporting a protocol version the add-on does not support,
**When** the add-on performs its health check,
**Then** the status reads `Version mismatch`, `EngineVersionError` names both versions and the required action, and no inference request is sent.

### AC-004: The Engine Never Acquires Weights
**Given** a request referencing a weight path that does not exist on disk,
**When** the engine receives it,
**Then** the engine returns a structured error naming the missing path, makes no network call, and does not attempt to download or resolve anything.

### AC-005: Licence Gate Still Governs
**Given** a model whose `commercial_use` is `prohibited` and a user who has not opted in,
**When** any path that would lead to inference on that model is invoked,
**Then** the add-on refuses before contacting the engine, `ModelLicenseError` is raised as it is today, and the engine receives no request for that model.

### AC-006: Insufficient VRAM Is Reported, Not Crashed
**Given** an engine on a GPU with less VRAM than the selected model requires,
**When** a reconstruction is requested,
**Then** the engine returns `{"error": "insufficient_vram", "retryable": false}` naming required and available amounts, the add-on surfaces the existing VRAM guidance, and the engine remains `Ready` for the next request.

### AC-007: GPU Memory Is Released
**Given** an engine that has completed 10 sequential reconstructions, including at least one failure,
**When** idle VRAM is measured after the tenth,
**Then** the engine holds less than 500 MB above its idle baseline.

### AC-008: Concurrent Requests Are Refused Cleanly
**Given** an engine currently processing a reconstruction,
**When** a second reconstruction request arrives,
**Then** the engine returns a documented busy response, the first request completes normally, and neither request corrupts the other's result.

---

## 7. EDGE CASES

### EC-001: Engine Installed but Stopped
| Aspect | Detail |
|--------|--------|
| **Scenario** | The engine is installed but its process is not running |
| **Input Example** | Nothing listening on the configured port; the engine's install directory exists |
| **Expected Behavior** | The add-on SHALL distinguish `Stopped` from `Not installed` by checking for the installation, SHALL offer to start it (FR-018), and SHALL NOT present installation guidance for something already installed. |
| **Test ID** | TS-004 |

### EC-002: Engine Dies Mid-Request
| Aspect | Detail |
|--------|--------|
| **Scenario** | The engine process is killed, or exits on OOM, while a reconstruction is in flight |
| **Input Example** | `SIGKILL` during `POST /reconstruct` |
| **Expected Behavior** | The client SHALL raise `EngineUnavailableError` rather than hanging, the operator SHALL report that the engine stopped unexpectedly and point at its log, and Blender SHALL remain responsive and not crash. |
| **Test ID** | TS-005 |

### EC-003: Port Already In Use
| Aspect | Detail |
|--------|--------|
| **Scenario** | Another process occupies the configured port |
| **Input Example** | An unrelated service on the default port |
| **Expected Behavior** | Engine startup SHALL fail with a message naming the port, and the add-on SHALL point the user at the port preference (FR-017). The add-on SHALL NOT send inference requests to whatever is listening — the health check's protocol-version field SHALL be used to confirm it is a Tessera engine before any inference request. |
| **Test ID** | TS-006 |

### EC-004: Engine Updated, Add-on Not
| Aspect | Detail |
|--------|--------|
| **Scenario** | The user updates the engine independently and the protocol version moves ahead |
| **Input Example** | Engine protocol 2, add-on supports 1 |
| **Expected Behavior** | AC-003 applies. The message SHALL identify which side is behind, so the user knows whether to update the add-on or roll the engine back. |
| **Test ID** | TS-007 |

### EC-005: Weight Path Valid but Content Wrong
| Aspect | Detail |
|--------|--------|
| **Scenario** | A path passes existence and digest checks add-on side, but the engine cannot load it as the expected architecture |
| **Input Example** | A user-added model of a family whose adapter cannot load an arbitrary variant (SPEC-TS-0002 FR-027) |
| **Expected Behavior** | The engine SHALL return a structured load error naming the model and the failure, and SHALL NOT be left in a partially-loaded state. The add-on SHALL surface it against the model row. |
| **Test ID** | TS-008 |

---

## 8. OUT OF SCOPE

- ❌ Remote or networked engines — loopback only in v1
- ❌ Multi-GPU or distributed inference
- ❌ ROCm and Metal device paths — the boundary is designed not to obstruct them (FR-024), but v1 is CUDA only per PRD-001 D7/NG8; Apple Silicon is TASK-TS-0022
- ❌ Running more than one inference concurrently (FR-021 refuses it deliberately)
- ❌ Engine-side model downloading or licence evaluation — permanently out of scope, not deferred (CON-005)
- ❌ Shipping the engine inside the add-on archive — rejected as Option 1 in ADR-0001
- ❌ Training, fine-tuning, or weight modification
- ❌ Replacing TRELLIS with a different backend — worth revisiting as an engine-side choice, but not part of delivering the engine

---

## 9. SECURITY CONSIDERATIONS

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — loopback only, single-user desktop context |
| **Auth Method** | None; the protocol-version handshake identifies a Tessera engine but is not a security control |
| **Required Permissions** | Local file read for weights; bind one loopback port |
| **Rate Limiting** | N/A — single-user, one request at a time (FR-021) |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| Image data in transit | Internal | Loopback only; never logged, never persisted by the engine |
| Weight paths | Internal | May contain a username; log basename only (SPEC-TS-0002 §9.2) |
| Mesh output | Internal | Returned to the add-on; not persisted by the engine |
| GPU name / VRAM | Internal | Shown in UI; not transmitted off the machine |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL bind only to `127.0.0.1`. SHALL NOT bind `0.0.0.0` or any routable interface. |
| SEC-002 | SHALL NOT load weights via `pickle` or `torch.load(weights_only=False)`. |
| SEC-003 | SHALL treat every request field as untrusted input: weight paths SHALL be canonicalised with `Path.resolve()` and confirmed to sit within the configured cache directory before being opened, so a crafted request cannot read arbitrary files. |
| SEC-004 | SHALL NOT execute or import Python code from any downloaded weight file. |
| SEC-005 | SHALL NOT write image data or mesh output to disk except under an explicit debug setting that is off by default. |
| SEC-006 | The add-on SHALL confirm a health response carries a recognised protocol version before sending image data, so data is not sent to an unrelated process occupying the port (EC-003). |

---

## 10. API CONTRACT

### 10.1 Engine HTTP API

```
GET  /health
  200 {"protocol_version": 1, "engine_version": "1.0.0",
       "cuda": true, "gpu": "NVIDIA GeForce RTX 5090", "vram_gb": 32.0}

POST /vision
  {"stage": "segment"|"depth"|"features",
   "weight_paths": {"sam2": "/abs/path/"}, "image": "<base64 png>"}
  200 {"result": {...}, "duration_s": 1.4}

POST /reconstruct
  {"weight_paths": {"trellis": "/abs/path/"},
   "inputs": [{"image": "<base64 png>", "mask": "<base64 png>",
               "depth": "<base64 png>", "view_label": "front"}]}
  200 {"vertices": [[x,y,z]], "faces": [[a,b,c]],
       "vertex_colors": [[r,g,b]] | null, "confidence": 0.82,
       "duration_s": 41.2}

Errors (any endpoint)
  4xx/5xx {"error": "<slug>", "detail": "<human readable>", "retryable": bool}
  Slugs: insufficient_vram | weights_missing | load_failed |
         busy | unsupported_stage | internal
```

### 10.2 Add-on Engine Client

```python
from tessera.engine.client import EngineClient

client = EngineClient()          # host/port from preferences (FR-017)

client.is_available()            # -> bool, never raises
client.health()                  # -> dict; raises EngineUnavailableError
                                 #          raises EngineVersionError (FR-011)
client.reconstruct(weight_paths, inputs)   # -> dict
client.vision(stage, weight_paths, image)  # -> dict

# Raises: EngineUnavailableError — not installed, stopped, or died mid-request
#         EngineVersionError     — protocol mismatch (AC-003, EC-004)
#         EngineRequestError     — structured engine error, carries .slug
```

---

## 11. OBSERVABILITY

### 11.1 Logging Requirements
| Event | Log Level | Required Fields | PII Check |
|-------|-----------|-----------------|-----------|
| Engine health check | DEBUG | `status`, `protocol_version`, `duration_ms` | ⚠️ No PII |
| Engine became available | INFO | `engine_version`, `gpu` | ⚠️ No PII |
| Engine unavailable | WARN | `reason`, `host`, `port` | ⚠️ No full paths |
| Version mismatch | ERROR | `addon_protocol`, `engine_protocol` | ⚠️ No PII |
| Inference started | INFO | `endpoint`, `model_id` | ⚠️ No image data |
| Inference completed | INFO | `endpoint`, `duration_s`, `vertex_count` | ⚠️ No image data |
| Inference failed | ERROR | `endpoint`, `error_slug`, `retryable` | ⚠️ No image data |
| Engine died mid-request | ERROR | `endpoint`, `elapsed_s` | ⚠️ No PII |

> Add-on logging uses `tessera.engine`; engine logging writes to its own log file, whose path the add-on displays on failure (EC-002).

### 11.2 Metrics

N/A — local add-on, no telemetry collected per PRD-001 D3.

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — engine presence is itself the gate (FR-012) |
| **Default State** | Engine absent; `StubAdapter` fallback applies |
| **Rollout Plan** | Add-on ships first and remains functional without the engine; the engine is offered on first Generate |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| ADR-0001 | ✅ Accepted | The decision this implements |
| SPEC-TS-0002 (weights) | Yes | Supplies verified paths; the licence gate stays add-on side |
| Engine installer artifacts | Yes | One per supported platform |
| SPEC-TS-0004 amendment | Yes | Currently assumes in-process inference |
| SPEC-TS-0015 amendment | Before listing | The engine install changes what a buyer agrees to install |

### 12.3 Rollback Plan
1. The user uninstalls the engine; the add-on returns to `Not installed` and the `StubAdapter` fallback, still functional
2. A previous engine version can be reinstalled independently of the add-on (FR-016)
3. Protocol mismatch is reported rather than silently tolerated (FR-011), so a rollback that breaks compatibility is visible immediately

---

## 13. TEST SCENARIOS

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Premises verified and recorded before implementation | Manual | FR-001 | Must Pass |
| TS-002 | Generate with engine `Ready` produces a mesh, not the stub cube | Integration | AC-001 | Must Pass |
| TS-003 | Engine absent: status, guidance, no request, no `torch` import in Blender | Integration | AC-002, FR-014 | Must Pass |
| TS-004 | Installed but stopped is distinguished from not installed | Unit | EC-001 | Must Pass |
| TS-005 | Engine killed mid-request raises `EngineUnavailableError`; Blender survives | Integration | EC-002 | Must Pass |
| TS-006 | Occupied port: named error, and no image data sent to a foreign listener | Integration | EC-003, SEC-006 | Must Pass |
| TS-007 | Protocol mismatch refuses and names which side is behind | Unit | AC-003, EC-004 | Must Pass |
| TS-008 | Non-existent weight path returns a structured error and no network call | Unit | AC-004, FR-007 | Must Pass |
| TS-009 | Licence-gated model never reaches the engine | Unit | AC-005, FR-009 | Must Pass |
| TS-010 | Insufficient VRAM returns the documented slug; engine stays `Ready` | Integration | AC-006, FR-019 | Must Pass |
| TS-011 | Ten sequential reconstructions leave < 500 MB residual VRAM | Performance | AC-007, NFR-007 | Must Pass |
| TS-012 | Concurrent request receives the busy response; neither result corrupted | Integration | AC-008, FR-021 | Must Pass |
| TS-013 | Engine binds loopback only; a routable bind is rejected | Unit | SEC-001, CON-004 | Must Pass |
| TS-014 | Path outside the cache directory is refused | Unit | SEC-003 | Must Pass |
| TS-015 | No `bpy` import anywhere in the engine package | Unit | CON-002 | Must Pass |
| TS-016 | Add-on archive stays under 1 MB | Script | NFR-004, CON-001 | Must Pass |
| TS-017 | Engine-side adapter tests run without Blender | Unit | FR-002 | Must Pass |
| TS-018 | Health check reports `Not installed` in < 500 ms | Performance | NFR-002 | Should Pass |
| TS-019 | Viewport holds ≥ 15 fps during inference | Performance | NFR-006 | Should Pass |
| TS-020 | Load failure leaves no partially-loaded engine state | Integration | EC-005 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| ADR-0001 | Required | Accepted | Tessera | No |
| SPEC-TS-0002 (Model weights) | Required | Approved | Tessera | No |
| SPEC-TS-0004 (Reconstruction engine) | Required | Approved — needs amending | Tessera | Yes — assumes in-process inference |
| TASK-TS-0016 (Vision adapters) | Downstream | Pending | Tessera | Blocked by this |
| TASK-TS-0017 (Trellis inference) | Downstream | Pending | Tessera | Blocked by this |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| PyTorch with CUDA | Required | [pytorch.org](https://pytorch.org) | None — engine-side hard requirement |
| TRELLIS + compiled CUDA extensions | Required | [github.com/microsoft/TRELLIS](https://github.com/microsoft/TRELLIS) | Alternative backend is an engine-side choice, not a fallback |
| `safetensors` | Required | [github.com/huggingface/safetensors](https://github.com/huggingface/safetensors) | None — secure weight loading |

---

## 15. APPROVAL

| Role | Name | Date | Status |
|------|------|------|--------|
| Author | Derek | 2026-09-22 | ☐ Submitted |
| CSO Approval | Derek | | ☐ Approved / ☐ Changes Requested |
| Deputy Review | — | — | ☑ N/A |

**Approval Notes:**
[Space for CSO feedback]

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-09-22 | Derek | Initial draft implementing ADR-0001: thin add-on plus a local engine process. Defines the process boundary, the loopback HTTP contract, protocol-version negotiation, and the rule that weight resolution, digest verification and licence gating stay add-on side so the licence gate remains a single choke point. Carries forward the two premises ADR-0001 was accepted without verifying as FR-001, gating implementation on confirming them. |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0023-local-inference-engine.md`
