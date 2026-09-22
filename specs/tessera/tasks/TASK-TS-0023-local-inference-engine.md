# Task: Local Inference Engine

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0023 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-09-22 |
| **Assignment Method** | ADR-0001 acceptance |
| **Sprint/Iteration** | Phase 6 — Integration & Pre-Launch |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🔴 P0 | XL | High | Architecture | ADR-0001 |

**Note:** This is the task that makes Tessera produce a real mesh. Every inference adapter needs PyTorch, which cannot ship inside the add-on archive, so the generate pipeline currently falls back to `StubAdapter` and returns a placeholder cube.

---

## ⚠️ Special Instructions

> **Verify the two unconfirmed premises before writing engine code.** ADR-0001 was accepted with the Extensions Platform archive size limit and the availability of prebuilt CUDA-extension wheels unverified. Both would change the decision if wrong. Confirm them first and report back; do not build on an unchecked premise.

---

## Business Context

### Why This Matters

No configuration of Tessera currently produces a real 3D mesh. Weights download, verify and licence-gate correctly, but nothing can run inference on them: `tessera/models/families.py` records `adapter_ready=False` for `sam2`, `dinov2` and `trellis`. The generate button returns a test cube. This task delivers the runtime that changes that.

### Why Now

It blocks everything downstream. TASK-TS-0016 (SAM 2, DINOv2 adapters) and TASK-TS-0017 (TRELLIS) were previously tracked as independent work; they are not. SAM 2 has 10 PyTorch references, DINOv2 has 12, and both fail for the same reason TRELLIS does. One runtime unblocks all three.

### User Story

**As a** Tessera user who has installed the add-on and downloaded the models,
**I want** the Generate button to produce an actual 3D mesh from my photo,
**So that** the product does the thing it is for.

### Master PRD Reference

- **PRD Section:** §5.2 3D Reconstruction Engine, §8 Technology Stack, D7 (NVIDIA CUDA only in v1), NG8
- **ADR:** ADR-0001 — How the GPU inference runtime is delivered
- **Spec:** SPEC-TS-0023

---

## Initial Requirements

### What Needs to Be Built

1. **Premise verification (do this first)**
   - Confirm the Extensions Platform archive size limit
   - Confirm whether prebuilt CUDA-extension wheels exist for the target GPU generation, or whether they build from source
   - Report both before proceeding — if either contradicts ADR-0001, reopen the ADR rather than working around it

2. **Engine process**
   - Its own virtual environment, independent of Blender's bundled Python
   - PyTorch plus the CUDA stack and TRELLIS's compiled extensions
   - Hosts the existing adapter implementations, which move out of the add-on largely unchanged

3. **Transport and protocol**
   - Localhost IPC between add-on and engine
   - A negotiated protocol version checked on connect, so add-on and engine cannot silently run skewed

4. **Add-on side**
   - Detects whether the engine is present, running and version-compatible
   - Reports absence as an actionable state in the UI, not a failure inside `torch`
   - Continues to own weight resolution, digest verification and the licence gate; the engine receives resolved paths and never resolves its own

5. **Engine installation**
   - One-time install, as close to one click as achievable
   - Per-platform artifacts
   - An update path that does not require reinstalling the add-on

6. **Lifecycle**
   - Decide and implement: add-on spawns and supervises the engine, or the user runs it as a service
   - Health check, startup timeout, and clean shutdown

### Known Constraints

- The add-on stays GPL-2.0-or-later and small enough for the Extensions Platform; the engine's dependency stack must not be vendored into the archive (ADR-0001 D3)
- The licence gate remains the single download choke point — the engine must not acquire weights itself (SPEC-TS-0002 FR-023, SEC-007)
- `bpy` must not be touched off the main thread (SPEC-TS-0002 CON-003); IPC callbacks are subject to the same rule
- v1 targets NVIDIA CUDA only (PRD-001 D7/NG8), but the engine boundary must not make ROCm or Metal harder later
- Inference must remain local — no network calls during inference (PRD-001 D3, SPEC-TS-0002 CON-001)

### Success Looks Like

A user installs the add-on, is prompted once to install the engine, accepts, and then loads a photo and clicks Generate. A recognisable mesh appears in the viewport. If the engine is missing, stopped or version-skewed, the add-on says exactly that and offers the fix — it never fails inside `torch`.

---

## Context & References

### Key Documents

| Document | Location | Why Relevant |
|----------|----------|--------------|
| ADR-0001 | `specs/tessera/adr/ADR-0001-inference-runtime-delivery.md` | The decision this task implements |
| Model weight management | `specs/tessera/feature-spec/active/SPEC-TS-0002-model-weight-management.md` | Weight resolution, licence gate, digests — all stay add-on side |
| Reconstruction engine | `specs/tessera/feature-spec/active/SPEC-TS-0004-reconstruction-engine.md` | Assumes in-process inference; needs amending |
| Model licences | `MODEL-LICENSES.md` | Notes this split as the route that also unlocks ROCm and Metal |
| Trellis adapter | `tessera/reconstruction/adapters/trellis_adapter.py` | Moves engine-side; weight resolution stays behind |

### Dependencies

| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| ADR-0001 | ✅ Accepted | Blocks this | Decision made 2026-09-22 |
| TASK-TS-0016 (Vision adapters) | Pending | Blocked **by** this | Adapters move engine-side |
| TASK-TS-0017 (Trellis inference) | Pending | Blocked **by** this | Same |
| TASK-TS-0022 (Apple Silicon) | Not started | Cheaper **after** this | Re-estimate once the engine boundary exists |
| SPEC-TS-0004 | Approved | Needs amending | Assumes in-process inference |
| SPEC-TS-0015 (Marketplace) | Draft | Needs amending | Engine install changes what a buyer agrees to install |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Premises verified** | TBD |
| **Protocol agreed** | TBD |
| **Engine runs one adapter end to end** | TBD |
| **Install flow usable by a non-engineer** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. **Engine distribution** — platform installer, `pipx`-style bootstrap, or container? This is the main risk: if the install is not close to one click, ADR-0001's own driver D2 is violated.
2. **IPC transport** — HTTP on localhost is simplest and debuggable; a socket is faster for large payloads. Mesh payloads are modest, so start simple unless measurement says otherwise.
3. **Lifecycle** — add-on spawns and supervises, or user-run service? Spawning is better UX; a service is easier to debug.
4. **Does this subsume TASK-TS-0022?** If the engine carries per-platform builds, Apple Silicon may become an engine build rather than an adapter rewrite.
5. **Does the engine ship weights-aware at all?** Recommended no — it receives resolved, verified paths. Confirm.

---

## Escalation

| Need | Contact | Channel |
|------|---------|---------|
| Technical questions | TBD | DM |
| Business/Requirements | Derek | DM |
| Blocked | — | #blocked |

---

## Engineer Acknowledgment

| Item | Status |
|------|--------|
| Task reviewed and understood | ☐ |
| Premises verified and reported | ☑ 2026-09-22 — `specs/tessera/adr/ADR-0001-premise-verification.md` |
| Questions resolved with CSO | ☐ |
| Ready to begin Spec | ☐ |

**Acknowledged Date:** [Date]
**Target Spec Submission:** [Date]
