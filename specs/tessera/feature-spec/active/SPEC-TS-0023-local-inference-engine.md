# Feature Specification: Local Inference Engine

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0023 |
| **Task ID** | TASK-TS-0023 |
| **Status** | Approved |
| **Version** | 1.4 |
| **Created** | 2026-09-22 |
| **Last Updated** | 2026-09-22 |
| **Author** | Derek |
| **Pod** | Tessera |
| **CSO Approver** | Derek |
| **Spec Type** | Feature |
| **Score** | 91 |

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

Three questions ADR-0001 left open are settled here:

| Question | Decision | Why |
|---|---|---|
| **Distribution** | A signed platform-native installer per platform, each carrying its own pinned CPython, virtual environment and prebuilt wheels — Windows x64 and Linux x64 in v1 (FR-030) | A `pipx` bootstrap presumes a Python the user does not have and a toolchain they cannot be asked to install; a container presumes Docker. Only a native installer meets ADR-0001 D2 for an audience of artists. macOS is excluded because v1 is CUDA-only |
| **Lifecycle** | The add-on spawns and supervises the engine, and attaches to one already running rather than starting a second (FR-018, FR-039, FR-040) | Spawning is the only option that makes the engine invisible in the ordinary case, which is what D2 asks for. Attaching preserves the debuggability a user-run service would have given |
| **Trust** | The engine authenticates every request with a per-start token from its runtime descriptor, validates `Host`, and rejects any request carrying `Origin` (FR-037, SEC-007) | Loopback is not a trust boundary on a desktop. Without this, any local process — including a web page in the user's own browser, via DNS rebinding — can drive inference |

One mechanism carries most of the add-on's knowledge of the engine: a **runtime descriptor** the engine writes at startup and deletes on clean exit (FR-032), holding the port, protocol version, log path, cache root and token. An **installation marker** written by the installer (FR-031) is what makes *installed* distinguishable from *running* without probing the port.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Generate produces a real mesh | 0% — stub cube | 100% with engine installed | Manual generate on the test image set |
| Engine install completed unaided | N/A | ≥ 90% of first-time users | Install funnel telemetry is out of scope; measured by supervised testing |
| Add-on archive size | < 400 KB | < 1 MB | `scripts/build_addon.sh` output |
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
- **Engine HTTP server:** stdlib `http.server.ThreadingHTTPServer` — no third-party web framework. Threading is required so `/health` and `/cancel` answer while an inference holds the engine (FR-034)
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

**Version negotiation:** the add-on and engine exchange a protocol version on connect, and every subsequent request restates it (FR-036), so an engine restarted at a different version underneath a long-lived client is caught rather than misread. A mismatch is reported as an actionable state, never worked around.

**Array transport:** every numeric array crosses as a base64 raw little-endian buffer with an explicit dtype and shape (FR-027). Nested JSON numbers would put a 200,000-vertex mesh near 30 MB and well outside the NFR-003 budget; raw buffers put it under 8 MB and let the add-on rebuild the arrays with `np.frombuffer`.

---

## 3. FUNCTIONAL REQUIREMENTS

### 3.1 Core Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | ✅ **Satisfied 2026-09-22.** Before any engine-side implementation begins, the two premises ADR-0001 was accepted without verifying SHALL be confirmed and recorded: the Extensions Platform archive size limit, and whether prebuilt CUDA-extension wheels exist for the target GPU generation. If either contradicts ADR-0001, implementation SHALL stop and the ADR SHALL be reopened. Both are confirmed in `specs/tessera/adr/ADR-0001-premise-verification.md`; neither contradicts the decision. The verification refines FR-030: TRELLIS's extensions build from source against a toolkit matching the GPU architecture, so the installer's build matrix is per architecture and not only per platform. |
| FR-002 | The engine SHALL be a separate OS process with its own Python environment, containing no `bpy` import and no dependency on Blender. |
| FR-003 | The engine SHALL expose an HTTP API bound to `127.0.0.1` only. It SHALL NOT bind to any externally reachable interface. |
| FR-004 | The engine SHALL expose `GET /health` returning its protocol version, engine version, CUDA availability, GPU name and total VRAM in GB. |
| FR-005 | The engine SHALL expose `POST /reconstruct` accepting resolved absolute weight paths and a list of vision-pipeline inputs, returning a mesh. Its request and response are defined field by field in §3.1.1 (FR-025 – FR-028) and §10.1; neither side SHALL carry a field those requirements do not name. |
| FR-006 | The engine SHALL expose `POST /vision` for the segmentation, depth and feature stages, accepting resolved weight paths and image data, and returning the per-stage response of FR-029. |
| FR-007 | The engine SHALL NOT resolve, download, or verify model weights. It SHALL accept only absolute paths supplied by the add-on, and SHALL reject a request whose paths do not exist rather than attempting to obtain them. |
| FR-008 | The engine SHALL NOT make any network call other than serving its own local HTTP endpoint. |
| FR-009 | The add-on SHALL verify weight integrity (SPEC-TS-0002 FR-007, FR-007a) and licence eligibility (FR-021, SEC-007) **before** sending any path to the engine. |
| FR-010 | The add-on SHALL provide an engine client exposing `is_available()`, `health()`, `reconstruct()`, `vision()`, `cancel()` and `shutdown()` (§10.2), raising `EngineUnavailableError` when the engine cannot be reached and `EngineTimeoutError` when it does not answer inside the FR-035 budget. |
| FR-011 | The add-on and engine SHALL exchange an integer protocol version. If the engine's version is not supported by the add-on, the client SHALL raise `EngineVersionError` naming both versions and the required action. |
| FR-012 | `AdapterRegistry` SHALL treat engine availability as an input to adapter selection: when the engine is unreachable or version-incompatible, engine-backed adapters SHALL be excluded and the existing `StubAdapter` fallback SHALL apply. |
| FR-013 | The add-on SHALL display engine status in the Tessera panel as exactly one of `Not installed`, `Stopped`, `Starting`, `Ready`, `Version mismatch` or `Unrecognised process on port`, each with its own action: `Not installed` → an **Install Engine** button opening the installation guidance of FR-014; `Stopped` → a **Start Engine** button invoking FR-018, or, when the engine is listening but not answering (EC-006), a **Restart Engine** button naming the log path; `Starting` → Generate disabled with elapsed seconds shown against the FR-040 budget and no start action offered, so a spawn in flight cannot be started twice; `Ready` → Generate enabled; `Version mismatch` → the FR-011 message plus **Update Add-on** or **Update Engine** according to which side is behind (EC-004); `Unrecognised process on port` → the port preference of FR-017, because something is listening that did not identify itself as a Tessera engine (EC-003, SEC-006). |
| FR-014 | When the engine is not installed, the add-on SHALL NOT attempt inference and SHALL present installation guidance. It SHALL NOT fail inside `torch` or any engine-side import. |
| FR-015 | The engine SHALL be installable in a single user-initiated flow that does not require the user to run `pip`, edit a path, or modify Blender's bundled Python. The only step asked of the user beyond consent is the operating system's own elevation or confirmation prompt. |
| FR-016 | The engine SHALL be installable and updatable independently of the add-on; updating one SHALL NOT require reinstalling the other, subject to FR-011. |
| FR-017 | The add-on SHALL provide engine host and port preferences, defaulting to `127.0.0.1` and port `8765`, so a user can run the engine on a non-default port. The host preference SHALL refuse any value that is not a loopback address (CON-004). |
| FR-018 | The add-on SHALL start a locally installed engine on demand: when the Tessera panel is opened or Generate is pressed, the FR-031 installation marker is present, and nothing answers on the configured port, the add-on SHALL spawn the engine executable named in that marker. If an engine already answers `GET /health` on the configured port, the add-on SHALL attach to it rather than spawning a second one, so an engine started by hand for debugging is used as it stands. Startup failure is reported per FR-040. |
| FR-019 | The engine SHALL return the `insufficient_vram` error carrying `required_gb` and `available_gb`. The add-on SHALL render it as the message SPEC-TS-0004 FR-012 already defines — `"Insufficient GPU VRAM. Required: {required_gb} GB, Available: {available_gb} GB. Close other GPU applications or select a lighter model."` — so the process boundary does not change the text the user reads. |
| FR-020 | The engine SHALL free GPU memory after each request, whether it succeeded or failed. |
| FR-021 | The engine SHALL process one inference request at a time and SHALL reject a concurrent request with `409` and `{"error": "busy", "retryable": true}` plus a `Retry-After` header, rather than queueing indefinitely or running both. |
| FR-022 | The add-on SHALL log engine interactions under the existing `tessera` logger, recording endpoint, duration and outcome, and SHALL NOT log image data or absolute paths containing a username (SPEC-TS-0002 §9.2). |
| FR-023 | The engine SHALL NOT load weights via `pickle` or `torch.load(weights_only=False)`; it SHALL use `safetensors` or `torch.load(..., weights_only=True)` (inherits SPEC-TS-0002 SEC-003, CON-008). |
| FR-024 | v1 SHALL target NVIDIA CUDA only (PRD-001 D7, NG8). The engine's device selection SHALL be a single replaceable component so that adding ROCm or Metal is an engine build change and not an add-on change. |

### 3.1.1 Wire Contract

| ID | Requirement |
|----|-------------|
| FR-025 | Each element of the `/reconstruct` request's `inputs` array SHALL be the complete wire projection of one `VisionPipelineOutput` — the alias of `VisionResult` in `tessera/vision/types.py` — carrying `image`, `mask`, `depth_map`, `view_label`, `label_confidence`, `label_source`, `label_needs_confirmation`, `features`, `original_size`, and the optional `camera_pose` that SPEC-TS-0007's `MultiViewAdapter` attaches. No field SHALL be dropped at the boundary. An input missing a required field SHALL be refused with `bad_request` naming the field. |
| FR-026 | The `/reconstruct` response SHALL carry every field needed to reconstitute `ReconstructionResult` and its `StandardMesh` without inventing values: `vertices`, `faces`, `vertex_colors`, `model_name`, `inference_time_s`, `confidence`, `vertex_count`, `face_count`, `warnings` and `source_adapter`. The add-on SHALL build both objects from these fields alone, and SHALL NOT substitute a default for a field the engine did not send. |
| FR-027 | Numeric arrays SHALL cross the boundary as base64-encoded raw little-endian buffers carrying an explicit `dtype` and `shape`, never as nested JSON numbers: `vertices` float32 `(N, 3)`; `faces` int32 `(M, 3)` zero-indexed; `vertex_colors` float32 `(N, 3)` in `[0.0, 1.0]`; `depth_map` float32 `(H, W)` in `[0.0, 1.0]`; `features` float32 `(1, D)`; `camera_pose` float32 `(4, 4)`. `image` SHALL be a base64 8-bit RGB PNG and `mask` a base64 8-bit grayscale PNG with values 0 or 255. |
| FR-028 | The engine SHALL return at most 1,000,000 vertices and 2,000,000 faces from `/reconstruct`. A result exceeding either bound SHALL be refused with `mesh_too_large` naming both counts, rather than truncated silently. |
| FR-029 | `/vision` SHALL return a response whose shape is fixed per stage: `segment` → `{"mask": <base64 PNG>, "coverage": float}`; `depth` → `{"depth_map": {"b64": str, "dtype": "float32", "shape": [H, W]}}`; `features` → `{"features": {"b64": str, "dtype": "float32", "shape": [1, D]}}`. Any other stage SHALL be refused with `unsupported_stage`. |

### 3.1.2 Installation, Discovery and Lifecycle

| ID | Requirement |
|----|-------------|
| FR-030 | The engine SHALL ship as a signed platform-native installer, one per supported platform, each carrying its own pinned CPython interpreter, virtual environment and prebuilt wheels, so installation requires no pre-existing Python, no compiler and no `pip` invocation by the user. v1 SHALL supply installers for **Windows x64 and Linux x64 only**; macOS is excluded because v1 is CUDA-only (FR-024, PRD-001 D7/NG8). PyTorch is consumed as a published `cu128` wheel and needs no build. TRELLIS's compiled extensions have no such wheel for current architectures and SHALL be built in CI against a CUDA toolkit that supports every target compute capability — the build matrix is per GPU architecture, not only per platform (ADR-0001 premise verification). |
| FR-031 | The installer SHALL write an installation marker recording `engine_version`, the protocol versions the engine speaks, and the absolute path of the engine executable, at `%LOCALAPPDATA%\Tessera\engine\install.json` on Windows and `${XDG_DATA_HOME:-~/.local/share}/tessera/engine/install.json` on Linux. A readable marker is the definition of *installed* (EC-001); the add-on SHALL NOT probe the port to answer that question. |
| FR-032 | On startup the engine SHALL write a runtime descriptor recording `pid`, `port`, `protocol_version`, `engine_version`, the absolute path of its log file, the `cache_root` it was started with, and a per-start random 256-bit `token` rendered as 64 hexadecimal characters. It SHALL live at `%LOCALAPPDATA%\Tessera\engine\runtime.json` on Windows and `${XDG_RUNTIME_DIR:-${XDG_STATE_HOME:-~/.local/state}}/tessera/engine/runtime.json` on Linux, SHALL be created owner-readable only, and SHALL be deleted on clean shutdown (FR-039). |
| FR-033 | The add-on SHALL pass the absolute cache root it governs to the engine as a launch argument. The engine SHALL hold that root for its process lifetime and SHALL NOT accept a cache root from any request. When attaching to an already-running engine (FR-018) the add-on SHALL compare the descriptor's `cache_root` with its own and SHALL refuse an engine whose root differs, naming the two paths that disagree. |
| FR-034 | The engine SHALL serve `GET /health` and `POST /cancel` concurrently with an in-flight inference. Only `POST /reconstruct` and `POST /vision` SHALL contend for the single inference lock of FR-021. |
| FR-035 | The add-on SHALL apply an explicit socket timeout to every engine call — 5 s for `/health` and `/cancel`, 300 s for `/vision`, 900 s for `/reconstruct`, the inference two overridable by preference. No call SHALL be made without one. These bound a *wedged* engine, not an absent one: nothing listening is refused by the kernel immediately, which is what keeps NFR-002's detection budget independent of them. On timeout the client SHALL issue `POST /cancel` for that request and raise `EngineTimeoutError` naming the endpoint and the elapsed time. |
| FR-036 | Every request SHALL carry a client-generated request id and the protocol version the add-on believes it is speaking, as the headers `X-Tessera-Request-Id` and `X-Tessera-Protocol`. Headers rather than body fields, so `GET /health` carries them on the same terms as every other call and there is one mechanism rather than two. The engine SHALL refuse a protocol version it does not serve with `protocol_mismatch`, so an engine restarted at a different version between the health check and the request is caught rather than misread. `POST /cancel` SHALL take a `request_id` in its body and SHALL abort that request if it is the one in flight. |
| FR-037 | The add-on SHALL present the `token` from the runtime descriptor on every request as an `X-Tessera-Token` header. The engine SHALL refuse, with `unauthorized` and without logging any part of the request body, a request whose token does not match, whose `Host` header names anything but the loopback address and port it bound, or which carries an `Origin` header at all. |
| FR-038 | The engine SHALL refuse a request body larger than 64 MiB with `payload_too_large`, decided from `Content-Length` before the body is read into memory, and SHALL refuse a chunked request that exceeds the bound while streaming. |
| FR-039 | The engine SHALL shut down cleanly on `POST /shutdown` and on `SIGTERM`: refuse new inference requests, wait up to 30 s for an in-flight request to finish or cancel, free GPU memory (FR-020), delete the runtime descriptor (FR-032), and exit 0. The add-on SHALL shut down an engine it spawned when Blender exits. |
| FR-040 | The add-on SHALL treat an engine it spawned that has not answered `GET /health` within 60 s as failed, SHALL terminate the process it started, and SHALL report the failure with the first 40 lines of the engine's captured standard error together with the log path from FR-032 — never a bare timeout. |
| FR-041 | The add-on SHALL fetch the engine installer through the existing download manager (SPEC-TS-0002), against a pinned release URL and a manifest digest, and SHALL verify that digest before handing the file to the operating system to run. It SHALL NOT open its own network path, so SPEC-TS-0002 CON-001's single network module and the integrity guarantees that go with it continue to hold for the engine as they do for weights. A digest mismatch SHALL delete the download and report it, exactly as FR-007 of SPEC-TS-0002 does. |

### 3.2 Input Specifications

| Field | Type | Constraints | Required | Example |
|-------|------|-------------|----------|---------|
| `engine_host` | `str` | Loopback address; non-loopback refused (FR-017) | Yes (default `127.0.0.1`) | `"127.0.0.1"` |
| `engine_port` | `int` | 1024–65535 | Yes (default `8765`) | `8765` |
| `cache_root` | `str` | Absolute directory; a launch argument, never a request field (FR-033) | Yes | `"/home/u/.cache/tessera/models"` |
| `weight_paths` | `dict[str, str]` | Absolute paths under `cache_root` that exist and have passed verification | Yes | `{"trellis": "/…/snapshots/ab12/"}` |
| `X-Tessera-Protocol` | header | Sent on every request; compared against the engine's served set (FR-036) | Yes | `1` |
| `X-Tessera-Request-Id` | header | Client-generated; the handle `POST /cancel` takes (FR-036) | Yes | `"a3f1c2…"` |
| `X-Tessera-Token` | header | 64 hex characters from the runtime descriptor (FR-037) | Yes | `"9f2c…"` |
| `inputs[].image` | `str` | Base64 8-bit RGB PNG (FR-027) | Yes | — |
| `inputs[].mask` | `str` | Base64 8-bit grayscale PNG, values 0 or 255 | Yes | — |
| `inputs[].depth_map` | `array` | `{b64, dtype: "float32", shape: [H, W]}`, values in `[0.0, 1.0]` | Yes | — |
| `inputs[].features` | `array` | `{b64, dtype: "float32", shape: [1, D]}` — DINOv2 CLS embedding | Yes | — |
| `inputs[].view_label` | `str` | View-label vocabulary (PRD-001 §6) | Yes | `"front"` |
| `inputs[].label_confidence` | `float` | `[0.0, 1.0]` | Yes | `0.94` |
| `inputs[].label_source` | `str` | `"user"` or `"auto"` | Yes | `"user"` |
| `inputs[].label_needs_confirmation` | `bool` | — | Yes | `false` |
| `inputs[].original_size` | `[int, int]` | `(width, height)` in pixels before resizing | Yes | `[3024, 4032]` |
| `inputs[].camera_pose` | `array \| null` | `{b64, dtype: "float32", shape: [4, 4]}`; present for the multi-view path (SPEC-TS-0007) | No | `null` |

### 3.3 Output Specifications

| Field | Type | Format | Example |
|-------|------|--------|---------|
| `health` | `dict` | `{"protocol_version": int, "protocol_versions": [int], "engine_version": str, "cuda": bool, "gpu": str, "vram_gb": float, "busy": bool, "log_path": str, "cache_root": str}` | `{"protocol_version": 1, "cuda": true, "vram_gb": 32.0, "busy": false}` |
| `reconstruct` | `dict` | `{"vertices": {b64, dtype, shape}, "faces": {b64, dtype, shape}, "vertex_colors": {b64, dtype, shape} \| null, "model_name": str, "inference_time_s": float, "confidence": float, "vertex_count": int, "face_count": int, "warnings": [str], "source_adapter": str, "duration_s": float}` — every field `StandardMesh` and `ReconstructionResult` require (FR-026) | — |
| `vision` | `dict` | Per stage, per FR-029; plus `duration_s` | — |
| `error` | `dict` | `{"error": str, "detail": str, "retryable": bool, "request_id": str}`, plus slug-specific fields (`required_gb`/`available_gb` for `insufficient_vram`, `vertex_count`/`face_count` for `mesh_too_large`, `field` for `bad_request`) | `{"error": "insufficient_vram", "required_gb": 16.0, "available_gb": 7.8, "retryable": false}` |

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
| CON-010 | Engine source SHALL also be GPL-2.0-or-later with a licence header on each file. The adapter implementations move between two programs under one licence, so no relicensing question arises, and PyTorch (BSD-3-Clause) and TRELLIS (MIT) are both compatible with it. The split exists to keep the add-on archive small and its distribution surface narrow (ADR-0001 D3), not to change the terms either half ships under. |
| CON-011 | SHALL NOT accept a cache root, weight-cache location or any other filesystem root from a request body — the engine receives its root as a launch argument only (FR-033). |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Engine health check latency | Round trip | < 100 ms | Engine running on loopback |
| NFR-002 | Engine availability detection when absent | Time to report `Not installed` | < 500 ms | No process listening on the configured port |
| NFR-003 | IPC overhead relative to inference | Add-on `reconstruct()` duration minus the engine's reported `inference_time_s` | < 500 ms | Single-image reconstruction returning ≤ 200,000 vertices, encoded per FR-027. Encode, serialise, parse and decode measure 45 ms of that budget at this size and 190 ms at the FR-028 ceiling, leaving the remainder for transport |
| NFR-004 | Add-on archive size | `scripts/build_addon.sh` output | < 1 MB | Any build |
| NFR-005 | Engine startup to `Ready` | Cold start | < 30 s | Engine installed, weights cached |
| NFR-006 | UI responsiveness during inference | Blender viewport frame rate | ≥ 15 fps | Inference in flight |
| NFR-007 | Per-request GPU memory leak | Residual VRAM above the engine's post-load idle baseline | < 50 MB | 10 sequential reconstructions including at least one failure. Same property and same figure as SPEC-TS-0004 NFR-004, which measured it in-process |
| NFR-008 | Engine install, unaided completion | Supervised first-time users | ≥ 90%, n ≥ 10 per platform | Usability testing on Windows x64 and Linux x64 (FR-030) |
| NFR-009 | Engine VRAM at rest | VRAM held by the engine process with no model loaded | < 300 MB | Engine `Ready`, no inference performed since start. Distinguishes the resident-model baseline from the NFR-007 leak |
| NFR-010 | Reconstruction response size | Encoded body for a 200,000-vertex, 400,000-face mesh | < 12 MB | Base64 raw buffers per FR-027. Measured at 9.60 MB: base64 costs a third on top of 7.2 MB of raw float32 and int32. At the FR-028 ceiling of 1,000,000 vertices the body is 48 MB, which loopback carries but no wider transport should be assumed to |
| NFR-011 | Health latency while busy | `GET /health` round trip during an in-flight reconstruction | < 100 ms | Concurrency model of FR-034 |

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
**Then** the engine holds less than 50 MB above its post-load idle baseline — the same figure SPEC-TS-0004 NFR-004 sets for the same property.

### AC-008: Concurrent Requests Are Refused Cleanly
**Given** an engine currently processing a reconstruction,
**When** a second reconstruction request arrives,
**Then** the engine returns `409` with `{"error": "busy", "retryable": true}` and a `Retry-After` header, the first request completes normally, and neither request corrupts the other's result.

### AC-009: Multi-View Inputs Survive the Boundary
**Given** three images whose `VisionPipelineOutput` objects carry `features`, `original_size`, `label_confidence` and the `camera_pose` attached by SPEC-TS-0007's `MultiViewAdapter`,
**When** the add-on sends them to `POST /reconstruct`,
**Then** the engine receives every one of those fields with its dtype and shape intact, and the adapter running engine-side observes inputs equal — field by field, array by array — to the objects the add-on held.

### AC-010: The Response Reconstitutes a Valid StandardMesh
**Given** a completed reconstruction,
**When** the add-on decodes the response,
**Then** it constructs a `StandardMesh` whose `metadata` carries all five required keys (`model_name`, `inference_time_s`, `confidence`, `vertex_count`, `face_count`) and a `ReconstructionResult` carrying `warnings` and `source_adapter`, all taken from the response, with no value defaulted or invented by the client.

### AC-011: A Wedged Engine Times Out and Is Cancelled
**Given** an engine that accepts a reconstruction and then stops responding,
**When** the client's 900 s reconstruct timeout elapses,
**Then** the client issues `POST /cancel` for that `request_id`, raises `EngineTimeoutError` naming the endpoint and elapsed time, releases the worker thread, and leaves Blender responsive.

### AC-012: An Untrusted Local Caller Is Refused
**Given** a running engine and a local process that is not the add-on,
**When** that process posts to `/reconstruct` without the runtime descriptor's token, or with an `Origin` header, or with a `Host` header naming a rebound name rather than the bound loopback address,
**Then** the engine returns `401` with `{"error": "unauthorized"}`, performs no inference, and logs no part of the request body.

### AC-013: Shutdown Is Clean
**Given** an engine spawned by the add-on and currently idle,
**When** Blender exits,
**Then** the add-on shuts the engine down, the engine frees GPU memory, deletes its runtime descriptor, exits 0, and the configured port is free for the next start.

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

### EC-006: Engine Alive but Wedged
| Aspect | Detail |
|--------|--------|
| **Scenario** | The engine process is alive and its socket is open, but a request never completes — a deadlocked CUDA kernel, or a driver hang |
| **Input Example** | `POST /reconstruct` accepted, no response after 900 s |
| **Expected Behavior** | Distinct from EC-002, where the process dies. The client SHALL time out per FR-035, issue `POST /cancel`, raise `EngineTimeoutError`, and — if the engine still does not answer `GET /health` within 5 s — offer to restart it, naming the log path from FR-032. The worker thread SHALL be released either way. |
| **Test ID** | TS-022 |

---

## 8. OUT OF SCOPE

- ❌ Remote or networked engines — loopback only in v1
- ❌ Multi-GPU or distributed inference
- ❌ ROCm and Metal device paths — the boundary is designed not to obstruct them (FR-024), but v1 is CUDA only per PRD-001 D7/NG8; Apple Silicon is TASK-TS-0022
- ❌ Running more than one inference concurrently (FR-021 refuses it deliberately)
- ❌ Engine-side model downloading or licence evaluation — permanently out of scope, not deferred (CON-005)
- ❌ Shipping the engine inside the add-on archive — rejected as Option 1 in ADR-0001
- ❌ Training, fine-tuning, or weight modification
- ❌ Mid-request progress reporting — v1 reports request start and completion only; a progress channel is an additive protocol change, not a v1 deliverable
- ❌ macOS and Apple Silicon engine builds — v1 installers are Windows x64 and Linux x64 (FR-030), because v1 is CUDA-only
- ❌ Replacing TRELLIS with a different backend — worth revisiting as an engine-side choice, but not part of delivering the engine

---

## 9. SECURITY CONSIDERATIONS

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | Yes. Loopback is not a trust boundary on a desktop: any local process running as the same user can reach the port, and a web page in the user's browser can issue cross-origin requests to `127.0.0.1`, with DNS rebinding defeating origin separation |
| **Auth Method** | A per-start 256-bit token, written owner-readable into the runtime descriptor (FR-032) and presented as `X-Tessera-Token` on every request, combined with `Host` validation and outright rejection of any request carrying an `Origin` header (FR-037). The protocol-version handshake identifies a Tessera engine (EC-003) but is not a security control |
| **Required Permissions** | Local file read under the launch-argument cache root; write to the runtime-descriptor directory; bind one loopback port |
| **Rate Limiting** | N/A for inference — one request at a time (FR-021). Unauthorised requests are refused before any body is read (FR-037, FR-038) |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| Image data in transit | Internal | Loopback only; never logged, never persisted by the engine |
| Weight paths | Internal | May contain a username; log basename only (SPEC-TS-0002 §9.2) |
| Mesh output | Internal | Returned to the add-on; not persisted by the engine |
| GPU name / VRAM | Internal | Shown in UI; not transmitted off the machine |
| Cache root in `/health` | Internal | May contain a username. Crosses loopback so the add-on can verify it is talking to an engine governing the same cache (FR-033); never logged, never displayed in full |
| Engine request token | Secret | Owner-readable file only (FR-032); regenerated on every start; never logged, never shown in the UI |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL bind only to `127.0.0.1`. SHALL NOT bind `0.0.0.0` or any routable interface. |
| SEC-002 | SHALL NOT load weights via `pickle` or `torch.load(weights_only=False)`. |
| SEC-003 | SHALL treat every request field as untrusted input. Weight paths SHALL be canonicalised with `Path.resolve()` and confirmed to sit within the cache root the engine was **launched with** (FR-033) — never one supplied by a request (CON-011) — before being opened. A path resolving outside that root SHALL be refused with `weights_missing`, the same slug as a genuinely absent path, so the response does not confirm the existence of files outside the root. |
| SEC-004 | SHALL NOT execute or import Python code from any downloaded weight file. |
| SEC-005 | SHALL NOT write image data or mesh output to disk except under an explicit debug setting that is off by default. |
| SEC-006 | The add-on SHALL confirm a health response carries a recognised protocol version before sending image data, so data is not sent to an unrelated process occupying the port (EC-003). |
| SEC-007 | The engine SHALL authenticate every request with the FR-032 token, SHALL reject any request carrying an `Origin` header, and SHALL reject any request whose `Host` header is not the loopback address and port it bound — defeating cross-origin and DNS-rebinding access from a browser running on the same machine. The token SHALL be regenerated on every engine start and its file SHALL be owner-readable only. |
| SEC-008 | The engine's own log file SHALL follow the same PII rules as the add-on's (SPEC-TS-0002 §9.2): no image data, no mesh data, and weight paths recorded by basename only. It is the file a user will attach to a support request (EC-002), so it SHALL be safe to share unedited. |
| SEC-009 | The engine SHALL NOT import or execute Python supplied by, or alongside, a weight file — no `trust_remote_code` loader path, no `sys.path` entry derived from a weight directory, no auto-import of a module found beside the weights. Adapter code is what the installer shipped and nothing else. |

---

## 10. API CONTRACT

### 10.1 Engine HTTP API

Every request carries three headers — `X-Tessera-Token` (FR-037),
`X-Tessera-Request-Id` and `X-Tessera-Protocol` (FR-036) — on GET and POST alike.
An `Array` is always `{"b64": str, "dtype": str, "shape": [int, ...]}` holding a
raw little-endian buffer (FR-027), never nested JSON numbers.

```
GET  /health                                    served during inference (FR-034)
  200 {"protocol_version": 1, "protocol_versions": [1],
       "engine_version": "1.0.0", "cuda": true,
       "gpu": "NVIDIA GeForce RTX 5090", "vram_gb": 32.0,
       "busy": false,
       "log_path": "/…/state/tessera/engine/engine.log",
       "cache_root": "/…/.cache/tessera/models"}

POST /vision
  {"stage": "segment" | "depth" | "features",
   "weight_paths": {"sam2": "/abs/path/"},
   "image": "<base64 8-bit RGB PNG>"}
  200 segment  {"mask": "<base64 8-bit grayscale PNG>", "coverage": 0.37,
                "duration_s": 1.4}
  200 depth    {"depth_map": Array(float32, [H, W]), "duration_s": 0.9}
  200 features {"features":  Array(float32, [1, D]), "duration_s": 0.3}

POST /reconstruct                               one at a time (FR-021)
  {"weight_paths": {"trellis": "/abs/path/"},
   "inputs": [{"image":        "<base64 8-bit RGB PNG>",
               "mask":         "<base64 8-bit grayscale PNG>",
               "depth_map":    Array(float32, [H, W]),
               "features":     Array(float32, [1, D]),
               "view_label":   "front",
               "label_confidence": 0.94,
               "label_source": "user",
               "label_needs_confirmation": false,
               "original_size": [3024, 4032],
               "camera_pose":  Array(float32, [4, 4]) | null}]}
  200 {"vertices":        Array(float32, [N, 3]),
       "faces":           Array(int32,   [M, 3]),     zero-indexed
       "vertex_colors":   Array(float32, [N, 3]) | null,
       "model_name":      "trellis-image-large-v1",
       "inference_time_s": 41.0,
       "confidence":      0.82,
       "vertex_count":    N,
       "face_count":      M,
       "warnings":        [str],
       "source_adapter":  "TrellisAdapter",
       "duration_s":      41.2}

POST /cancel
  {"request_id": str}
  200 {"cancelled": bool}          cancelled=false if it was not the in-flight request

POST /shutdown                                  clean shutdown (FR-039)
  202 {"stopping": true}

Errors (any endpoint)
  {"error": "<slug>", "detail": "<human readable>",
   "retryable": bool, "request_id": str, …slug-specific fields}

  slug               status  retryable  extra fields
  ─────────────────  ──────  ─────────  ─────────────────────────────
  unauthorized          401      false  —
  bad_request           400      false  field
  protocol_mismatch     400      false  engine_protocol, requested
  payload_too_large     413      false  limit_bytes
  unsupported_stage     400      false  stage
  weights_missing       400      false  model_id
  load_failed           422      false  model_id
  insufficient_vram     503      false  required_gb, available_gb
  mesh_too_large        422      false  vertex_count, face_count
  busy                  409      true   — (with Retry-After: 5)
  cancelled             499      false  —
  internal              500      false  —
```

`499` is not an RFC 9110 code. It is the widely used convention for a request the
client abandoned, and is chosen deliberately so a cancelled request cannot be
mistaken for a server-side failure. It is only ever seen on this loopback API.

### 10.2 Add-on Engine Client

```python
from tessera.engine.client import EngineClient

client = EngineClient()          # host/port from preferences (FR-017)

client.is_available()            # -> bool, never raises
client.health()                  # -> dict; raises EngineUnavailableError
                                 #          raises EngineVersionError (FR-011)
client.reconstruct(weight_paths, inputs)   # -> dict; timeout 900 s (FR-035)
client.vision(stage, weight_paths, image)  # -> dict; timeout 300 s
client.cancel(request_id)                  # -> bool
client.shutdown()                          # -> None; clean stop (FR-039)

# Raises: EngineUnavailableError — not installed, stopped, or died mid-request
#         EngineVersionError     — protocol mismatch (AC-003, EC-004)
#         EngineTimeoutError     — no response inside the FR-035 budget (EC-006);
#                                  /cancel already issued when it is raised
#         EngineRequestError     — structured engine error, carries .slug and
#                                  the slug-specific fields from §10.1
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
| Request timed out, cancel issued | ERROR | `endpoint`, `request_id`, `elapsed_s` | ⚠️ No image data |
| Engine spawn failed | ERROR | `exit_code`, `stderr_head`, `log_path` | ⚠️ No full paths beyond the log path |
| Unauthorised request refused | WARN | `reason` (`token`, `host`, `origin`) | ⚠️ Body never logged (SEC-007) |
| Engine shut down | INFO | `trigger`, `exit_code` | ⚠️ No PII |

> Add-on logging uses `tessera.engine`. The engine writes to its own log file at the path it publishes in `GET /health` and in the runtime descriptor (FR-032); the add-on displays that path on failure (EC-002, FR-040). Engine logs carry no image data, no mesh data and weight basenames only (SEC-008), so a user can attach one to a support request unedited.

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
| PRD-001 §5.2, §8, D10 | Yes — same PR | The PRD describes a single add-on deployment; the engine is a second installed artifact and the PRD is updated alongside this spec |
| SPEC-TS-0002 (weights) | Yes — amendment in this PR | Supplies verified paths; the licence gate stays add-on side. Its download manager is extended to cover one non-weight artifact, the engine installer, so the digest-verified single network module of CON-001 still holds (FR-041) |
| Engine installer artifacts | Yes | Windows x64 and Linux x64 (FR-030) |
| SPEC-TS-0004 amendment | ✅ Done (v1.2) | CON-008 amended to permit the sanctioned engine boundary. **Still outstanding:** FR-012 and FR-015 describe an in-process VRAM check and cleanup, and NFR-004 measures residual VRAM in the Blender process. All three become engine-side; NFR-004's 50 MB figure is preserved unchanged as NFR-007 here |
| SPEC-TS-0007 amendment | ✅ Done (v1.1) | CON-009 amended. Its `MultiViewAdapter` enriches `VisionPipelineOutput` with `camera_pose`, which FR-025/FR-027 carry across the boundary |
| SPEC-TS-0010 amendment | ✅ Done (v1.1) | CON-008 amended |
| SPEC-TS-0003 amendment | Yes | NFR-003 measures `torch.cuda.max_memory_allocated()` and its OOM edge case catches `torch.cuda.OutOfMemoryError` — both now happen in another process and arrive as the structured errors of §10.1 |
| SPEC-TS-0011 amendment | Yes | FR-007, FR-011 and FR-013 define VRAM handling, the performance report and the LRU model cache in `torch.cuda.*` terms; all become engine-side concerns reached over this API |
| SPEC-TS-0015 amendment | Before listing | The engine install changes what a buyer agrees to install; FR-030's platform matrix narrows the listing's stated support |

### 12.3 Rollback Plan
1. The user uninstalls the engine through the platform uninstaller, which removes the installation marker (FR-031); the add-on then reads `Not installed` and returns to the `StubAdapter` fallback, still functional. A stale runtime descriptor is ignored once nothing answers on the port
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
| TS-011 | Ten sequential reconstructions leave < 50 MB residual VRAM above the post-load baseline | Performance | AC-007, NFR-007 | Must Pass |
| TS-012 | Concurrent request receives the busy response; neither result corrupted | Integration | AC-008, FR-021 | Must Pass |
| TS-013 | Engine binds loopback only; a routable bind is rejected | Unit | SEC-001, CON-004 | Must Pass |
| TS-014 | Path outside the cache directory is refused | Unit | SEC-003 | Must Pass |
| TS-015 | No `bpy` import anywhere in the engine package | Unit | CON-002 | Must Pass |
| TS-016 | Add-on archive stays under 1 MB | Script | NFR-004, CON-001 | Must Pass |
| TS-017 | Engine-side adapter tests run without Blender | Unit | FR-002 | Must Pass |
| TS-018 | Health check reports `Not installed` in < 500 ms | Performance | NFR-002 | Should Pass |
| TS-019 | Viewport holds ≥ 15 fps during inference | Performance | NFR-006 | Should Pass |
| TS-020 | Load failure leaves no partially-loaded engine state | Integration | EC-005 | Must Pass |
| TS-021 | Round trip preserves every `VisionPipelineOutput` field including `features` and `camera_pose` | Unit | AC-009, FR-025, FR-027 | Must Pass |
| TS-022 | Wedged engine: client times out, issues `/cancel`, releases the thread | Integration | AC-011, EC-006, FR-035 | Must Pass |
| TS-023 | Response reconstitutes `StandardMesh` metadata and `ReconstructionResult` with no defaulted field | Unit | AC-010, FR-026 | Must Pass |
| TS-024 | Request without a valid token, or with an `Origin` header, or with a foreign `Host`, returns 401 and runs nothing | Unit | AC-012, SEC-007, FR-037 | Must Pass |
| TS-025 | `GET /health` answers in < 100 ms while a reconstruction is in flight | Performance | NFR-011, FR-034 | Must Pass |
| TS-026 | Clean shutdown frees VRAM, deletes the runtime descriptor, releases the port | Integration | AC-013, FR-039 | Must Pass |
| TS-027 | Engine that never answers is terminated at 60 s and reported with captured stderr and log path | Integration | FR-040 | Must Pass |
| TS-028 | Installation marker present with no process listening yields `Stopped`, not `Not installed` | Unit | FR-031, EC-001 | Must Pass |
| TS-029 | Attaching to an engine whose `cache_root` differs is refused, naming both paths | Unit | FR-033 | Must Pass |
| TS-030 | Body over 64 MiB refused with `payload_too_large` before it is read | Unit | FR-038 | Must Pass |
| TS-031 | Result over 1,000,000 vertices refused with `mesh_too_large`, not truncated | Unit | FR-028 | Must Pass |
| TS-032 | Every error slug maps to its documented status, retryable flag and extra fields | Unit | §10.1 | Must Pass |
| TS-033 | 200,000-vertex response encodes under 8 MB and adds under 500 ms | Performance | NFR-003, NFR-010, FR-027 | Must Pass |
| TS-034 | Engine at rest with no model loaded holds < 300 MB VRAM | Performance | NFR-009 | Should Pass |
| TS-035 | Weight path resolving outside the launch-argument cache root returns `weights_missing` | Unit | SEC-003, CON-011 | Must Pass |
| TS-036 | No engine module imports code found beside a weight file | Unit | SEC-009 | Must Pass |
| TS-037 | Every engine source file carries a GPL-2.0-or-later header | Script | CON-010 | Must Pass |
| TS-038 | Windows x64 and Linux x64 installers complete with no pre-existing Python and no compiler | Manual | FR-030, NFR-008 | Must Pass |
| TS-039 | Installer download with a mismatched digest is deleted and reported; the file is never executed | Unit | FR-041 | Must Pass |

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| ADR-0001 | Required | Accepted | Tessera | No |
| PRD-001 (§5.2, §8, D10) | Required | Updated in this PR | Tessera | No |
| SPEC-TS-0002 (Model weights) | Required | Approved — small amendment for FR-041 | Tessera | No |
| SPEC-TS-0004 (Reconstruction engine) | Required | Reopened — CON-008 amended; FR-012, FR-015, NFR-004 outstanding | Tessera | No |
| SPEC-TS-0007 (Multi-view reconstruction) | Required | CON-009 amended | Tessera | No — `camera_pose` crosses the boundary per FR-025 |
| SPEC-TS-0010 (Sketch-to-3D) | Required | CON-008 amended | Tessera | No |
| SPEC-TS-0003 (Vision pipeline) | Required | Approved — needs amending | Tessera | Yes — NFR-003 and its OOM edge case are in-process measurements |
| SPEC-TS-0011 (Production hardening) | Required | Draft — needs amending | Tessera | Yes — FR-007, FR-011, FR-013 are `torch.cuda.*` in-process |
| SPEC-TS-0015 (Marketplace publication) | Required | Draft — needs amending | Tessera | Before listing only |
| TASK-TS-0016 (Vision adapters) | Downstream | Pending | Tessera | Blocked by this |
| TASK-TS-0017 (Trellis inference) | Downstream | Pending | Tessera | Blocked by this |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| PyTorch with CUDA | Required | [pytorch.org](https://pytorch.org) | None — engine-side hard requirement |
| TRELLIS + compiled CUDA extensions | Required | [github.com/microsoft/TRELLIS](https://github.com/microsoft/TRELLIS) | Alternative backend is an engine-side choice, not a fallback |
| `safetensors` | Required | [github.com/huggingface/safetensors](https://github.com/huggingface/safetensors) | None — secure weight loading |
| Code-signing certificates (Windows Authenticode, Linux detached signature) | Required | Platform vendor documentation | None — FR-030 requires signed installers; an unsigned installer trips SmartScreen and defeats ADR-0001 D2 |

---

## 15. APPROVAL

| Role | Name | Date | Status |
|------|------|------|--------|
| Author | Derek | 2026-09-22 | ☑ Submitted |
| CSO Approval | Derek | 2026-09-22 | ☑ Approved |
| Deputy Review | — | — | ☑ N/A |

**Approval Notes:**
[Space for CSO feedback]

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-09-22 | Derek | Initial draft implementing ADR-0001: thin add-on plus a local engine process. Defines the process boundary, the loopback HTTP contract, protocol-version negotiation, and the rule that weight resolution, digest verification and licence gating stay add-on side so the licence gate remains a single choke point. Carries forward the two premises ADR-0001 was accepted without verifying as FR-001, gating implementation on confirming them. |
| 1.1 | 2026-09-22 | Derek | Settled the three questions ADR-0001 left open — distribution is a signed native installer per platform (Windows x64, Linux x64), the add-on spawns and supervises the engine, and every request is authenticated. Replaced the sketch of the wire format with the full projection of `VisionPipelineOutput` and `ReconstructionResult`, so `features`, `camera_pose`, `original_size` and the `StandardMesh` metadata keys survive the boundary (FR-025 – FR-029); numeric arrays now cross as base64 raw buffers rather than nested JSON. Added installation marker and runtime descriptor as the basis for discovery, log-path reporting and the request token (FR-030 – FR-033, FR-037, SEC-007 – SEC-009). Added the concurrency model that keeps `/health` answerable during inference, request timeouts, cancellation, clean shutdown and startup failure reporting (FR-034 – FR-036, FR-039, FR-040). Set the engine's licence as GPL-2.0-or-later (CON-010). Reconciled residual-VRAM measurement with SPEC-TS-0004 NFR-004 at 50 MB and separated the at-rest baseline into NFR-009. Extended the amendment list to SPEC-TS-0003, SPEC-TS-0007, SPEC-TS-0010 and SPEC-TS-0011, and recorded the PRD update this PR carries. Routed the installer download through the existing download manager so it is digest-verified like a weight file and the add-on keeps one network module (FR-041). Gave every error slug a standard HTTP status. Added AC-009 – AC-013, EC-006 and TS-021 – TS-039. |
| 1.4 | 2026-09-22 | Derek | Recorded the ADR-0001 premise verification against FR-001, which is now satisfied: the Extensions Platform ceiling is 200 MB, and the target GPU's compute capability is one the installed CUDA toolkit cannot target at all. Both support the decision rather than contradicting it. Refined FR-030 with what the verification separated — PyTorch is a published wheel and needs no build, while TRELLIS's extensions build from source against a toolkit matching the architecture, making the installer build matrix per GPU architecture rather than only per platform. |
| 1.3 | 2026-09-22 | Derek | Corrected NFR-010 from 8 MB to 12 MB and recorded the measured figures behind both it and NFR-003. The original bound did not account for base64 costing a third on top of the raw buffers; a 200,000-vertex mesh encodes to 9.60 MB, and the codec accounts for 45 ms of the NFR-003 budget at that size. |
| 1.2 | 2026-09-22 | Derek | Moved the per-request identity fields from the JSON body to the headers `X-Tessera-Request-Id` and `X-Tessera-Protocol`, so `GET /health` carries them on the same terms as every other call and there is one mechanism rather than two. Replaced FR-035's separate connect bound with per-endpoint socket timeouts, and recorded why an absent engine is still detected inside the NFR-002 budget: the kernel refuses a closed port immediately, so the timeout governs a wedged engine rather than a missing one. Added `Unrecognised process on port` as a sixth engine status — something listening that does not identify itself is not the same as nothing listening, and it wants the port preference rather than an install button. |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0023-local-inference-engine.md`
