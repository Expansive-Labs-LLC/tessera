# TASK-TS-0023 — Remaining Work

| Field | Value |
|---|---|
| **Implements** | SPEC-TS-0023 v1.6 (Approved) |
| **Status** | In Progress |
| **Updated** | 2026-09-24 |
| **Owner** | Derek |

Running list of what is left to make Generate produce a real mesh. Update it as
items land; it is the answer to "what is still missing", not a design document.

## Where this actually stands

The process boundary is built, tested and merged on both sides. **Neither end
is connected to anything yet**, and no model can run, so the original symptom
is unchanged: `tessera/models/families.py` still records `adapter_ready=False`
for `sam2`, `dinov2` and `trellis`, and Generate still returns the stub cube.

`tessera.engine` is imported in exactly one place in the whole add-on —
`tessera/reconstruction/registry.py:133`, for status resolution. That is the
measure of how much wiring is left.

---

## 1. Done and merged

| Area | Where |
|---|---|
| ADR-0001 accepted, both premises verified against real hardware | `specs/tessera/adr/` |
| SPEC-TS-0023 approved, v1.6 | `specs/tessera/feature-spec/active/` |
| Add-on client: health, protocol negotiation, timeouts, cancel, shutdown | `tessera/engine/client.py` |
| Discovery by install marker and runtime descriptor | `tessera/engine/discovery.py` |
| Six-state status model | `tessera/engine/status.py` |
| Spawn / supervise / stop | `tessera/engine/lifecycle.py` |
| Wire codec, duplicated both sides and pinned by test | `tessera/engine/codec.py`, `tessera_engine/codec.py` |
| Engine HTTP server: auth, routing, inference lock, cancel, shutdown | `tessera_engine/server.py` |
| Cache-root containment, runtime descriptor, device probe | `tessera_engine/runtime.py` |
| Error envelope with documented status per slug | `tessera_engine/errors.py` |
| Request validation and adapter dispatch | `tessera_engine/inference.py` |
| Engine CLI entry point | `tessera_engine/__main__.py` |
| Registry treats engine availability as a selection input (FR-012) | `tessera/reconstruction/registry.py` |
| Linux installer: build, install, GPG signing | `packaging/linux/` |
| User-local CUDA 12.8 toolchain provisioning | `packaging/linux/provision_toolchain.sh` |

---

## 2. Built but not wired — the add-on cannot reach any of it

This is the largest gap and none of it is hard; it is all connection work.

- [ ] **Engine preferences (FR-017).** `engine_host` and `engine_port` do not
      exist in `tessera/preferences.py`. The client defaults to
      `127.0.0.1:8765` and nothing can change it.
- [ ] **Engine status in the panel (FR-013).** No panel in `tessera/ui/` reads
      `resolve_status()`. All six states and their actions are implemented and
      unreachable.
- [ ] **Install guidance when absent (FR-014).** Needs the panel above.
- [ ] **Spawn on demand (FR-018) and stop on exit (FR-039).** `spawn_engine`
      and `stop_engine` are called from nowhere. Stopping on Blender exit needs
      a handler in the add-on's `unregister`.
- [ ] **Generate goes through the engine.** `tessera/operators/generate_ops.py`
      does not import `EngineClient`. This is the step that changes what the
      button does.
- [ ] **Vision stages go through the engine.** Same for the segmentation,
      depth and feature calls.
- [ ] **Installer download (FR-041).** Nothing fetches the engine artifact
      through `DownloadManager`. Needs a pinned release URL and digest in the
      manifest.

---

## 3. Not started — the models themselves

- [ ] **Pin TRELLIS and its extension set.** `packaging/linux/requirements-engine.txt`
      has the slot commented out. Needs a commit pin and the list of extensions
      that actually build against CUDA 12.8 for `sm_120` — that is the spike.
- [ ] **TRELLIS reconstruction adapter, engine-side.** Register through
      `register_adapter("reconstruction", ...)`. `tessera_engine` currently
      registers none.
- [ ] **SAM 2 segmentation adapter** (10 torch references to move).
- [ ] **DINOv2 feature adapter** (12 torch references to move).
- [ ] **Depth Anything V2 adapter.**
- [ ] **FR-023: weight loading via `safetensors` / `weights_only=True`.** No
      loading code exists yet, so the constraint is currently unexercised.
- [ ] **Flip `adapter_ready=True`** in `tessera/models/families.py` per family
      as each adapter lands. This is the flag that ends the stub-cube behaviour.

---

## 4. Deferred, with a reason

- [ ] **Windows installer** → SPEC-TS-0024. Blocked on a code-signing identity,
      not on engineering. Azure Trusted Signing sign-up was failing through the
      web interface as of 2026-09-23.
- [ ] **macOS / Apple Silicon** → TASK-TS-0022. v1 is CUDA-only (PRD-001
      D7/NG8), so there is no device path to install for.

---

## 5. Sibling specs this work obliges

Declared as dependencies in SPEC-TS-0023 §12.2/§14.1, none of them amended yet.

- [ ] **SPEC-TS-0002** — extend the download manager to cover the engine
      installer artifact (FR-041).
- [ ] **SPEC-TS-0003** — NFR-003 and the OOM edge case are in-process
      `torch.cuda.*` measurements; both now happen in another process.
- [ ] **SPEC-TS-0004** — FR-012, FR-015 and NFR-004 still describe an
      in-process VRAM check, cleanup and measurement. CON-008 is already done.
- [ ] **SPEC-TS-0011** — FR-007, FR-011 and FR-013 define VRAM handling, the
      performance report and the LRU model cache in `torch.cuda.*` terms.
- [ ] **SPEC-TS-0015** — must describe the engine install and the Linux-only
      v1 matrix before listing.

---

## Suggested order

1. **Pin TRELLIS and run the extension build spike.** Everything about the
   installer's real contents and CI shape depends on what it finds, and it is
   the only item with genuine unknown risk.
2. **Wire the add-on** (section 2). Independent of the spike, and it is what
   turns a tested library into something a user can see.
3. **Adapters** (section 3), TRELLIS first — one real mesh is the milestone
   the whole task exists for.
4. **Sibling spec amendments** (section 5) before CSO review of the next spec
   in this area.
