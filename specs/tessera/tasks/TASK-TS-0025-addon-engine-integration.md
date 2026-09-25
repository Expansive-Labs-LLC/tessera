# Task: Add-on Engine Integration

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0025 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-09-24 |
| **Assignment Method** | SPEC-TS-0023 implementation split |
| **Sprint/Iteration** | Phase 6 — Integration & Pre-Launch |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🔴 P0 | L | Low | Feature | SPEC-TS-0023 |

---

## ⚠️ Special Instructions

> **Everything this task needs already exists and is tested.** `tessera/engine/`
> holds the client, discovery, status model, lifecycle and codec, all covered by
> 75 passing tests. None of it is reachable from the UI. This task is wiring,
> not design — if it starts to feel like design, something in SPEC-TS-0023 was
> wrong and should be raised rather than worked around.

---

## Business Context

### Why This Matters

`tessera.engine` is imported in exactly one place in the whole add-on
(`tessera/reconstruction/registry.py:133`). A user has no way to set the engine
port, no indication of whether the engine is running, no way to start it, and
no path from the Generate button to it. The boundary is built and invisible.

### Why Now

It is independent of the model work and is what turns a tested library into
something a user can see. It can proceed in parallel with TASK-TS-0026.

### User Story

**As a** Tessera user,
**I want** the panel to tell me whether the engine is ready and offer the fix
when it is not,
**So that** a missing runtime is something I can act on rather than a button
that silently does the wrong thing.

### Master PRD Reference

- **PRD Section:** §5.2 3D Reconstruction Engine, §8 Technology Stack, D10
- **Strategic Goal:** G1 — a user can go from photo to printable mesh inside
  Blender without leaving it

---

## Initial Requirements

> ⚠️ **Starting points only.** These expand into the full Spec.

### What Needs to Be Built

1. **Engine preferences (SPEC-TS-0023 FR-017)**
   - `engine_host` and `engine_port` in `tessera/preferences.py`, defaulting to
     `127.0.0.1` and `8765`
   - Host field refuses any non-loopback value

2. **Engine status in the panel (FR-013, FR-014)**
   - Render all six states from `EngineStatus` with the action each one calls
     for: Install, Start, disabled-while-Starting, Generate-enabled, the
     version message, and the port preference for an unrecognised listener
   - Poll off the main thread; update through the existing `bpy.app.timers`
     queue (CON-003)

3. **Lifecycle wiring (FR-018, FR-039, FR-040)**
   - Spawn on demand; attach rather than spawn a second engine
   - Stop an engine this add-on spawned when Blender exits
   - Report startup failure with the engine's captured stderr and log path

4. **Generate through the engine**
   - `tessera/operators/generate_ops.py` calls `EngineClient.reconstruct()`
   - Encode inputs with `tessera.engine.codec`; rebuild `StandardMesh` and
     `ReconstructionResult` from the response with nothing defaulted
   - Map every documented error slug to an actionable message

5. **Vision stages through the engine**
   - Same for segmentation, depth and feature extraction via `vision()`

6. **Installer download (FR-041)**
   - Fetch the engine artifact through `DownloadManager` against a pinned URL
     and manifest digest; verify before running it

### Known Constraints

- `bpy` is never touched from the background threads that call the engine
  (CON-003); results reach the UI through `bpy.app.timers`
- The add-on keeps weight resolution, digest verification and the licence gate.
  The engine receives resolved absolute paths and nothing else (CON-005)
- No new add-on dependency — the client is stdlib only, and the archive stays
  under 1 MB (NFR-004, enforced by TS-016)
- Engine absence is a UI state, never an exception reaching the user (AC-002)

### Success Looks Like

A user opens the Tessera panel with no engine installed and sees `Not installed`
with an Install button. After installing, the panel reads `Ready`, and Generate
runs inference in the engine process instead of returning the stub cube.

---

## Context & References

### Key Documents

| Document | Location | Why Relevant |
|----------|----------|--------------|
| Local inference engine | `specs/tessera/feature-spec/active/SPEC-TS-0023-local-inference-engine.md` | FR-013, FR-014, FR-017, FR-018, FR-039 – FR-041 |
| Model weight management | `specs/tessera/feature-spec/active/SPEC-TS-0002-model-weight-management.md` | The licence gate and download manager this reuses |

### Key Code to Review

| File | Purpose |
|------|---------|
| `tessera/engine/client.py` | The client to call; already handles timeouts, cancel and protocol skew |
| `tessera/engine/status.py` | `resolve_status()` returns the state, message and action the panel renders |
| `tessera/engine/lifecycle.py` | `spawn_engine` / `stop_engine`, currently called from nowhere |
| `tessera/engine/codec.py` | Wire encoding for inputs and mesh results |
| `tessera/preferences.py` | Where the host and port fields belong |
| `tessera/ui/generation_panel.py` | Where engine status most plausibly renders |
| `tessera/operators/generate_ops.py` | The operator that must stop returning a stub |
| `tessera/models/download_manager.py` | Resume, progress and retry for the FR-041 download |

### Dependencies

| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| SPEC-TS-0023 | Approved | Blocks this | Proceed |
| TASK-TS-0026 (TRELLIS adapter) | Not started | Neither blocks the other | Proceed in parallel; test against an engine with no adapters, which returns `load_failed` |
| SPEC-TS-0002 amendment | Not started | Blocked by this | The download manager gains one non-weight artifact |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Spec Approved** | TBD |
| **PR Submitted** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO
> Questions or unknowns the CSO is aware of:

1. **Should Generate offer to install the engine, or only point at it?**
   - **Suggested resolution:** Offer. FR-041 already routes the download
     through the existing download manager, so the machinery exists and a
     link-out wastes it.
2. **Does the add-on stop an engine it attached to but did not spawn?**
   - **Suggested resolution:** No. `stop_engine` already distinguishes the
     two; someone debugging with a hand-started engine should keep it.

### For Engineer to Add
> Space to add questions before starting the Spec:

1. _[Add questions here after reviewing the task]_

---

## Escalation

| Need | Contact | Channel |
|------|---------|---------|
| Technical questions | TBD | DM |
| Business/Requirements | Derek | DM |
| Blocked | — | #blocked |

---

## Engineer Acknowledgment

> **Complete this section within 24 hours of assignment.**

| Item | Status |
|------|--------|
| Task reviewed and understood | ☐ |
| Questions added above (if any) | ☐ |
| Questions resolved with CSO | ☐ |
| Ready to begin Spec | ☐ |

**Acknowledged Date:** [Date]
**Target Spec Submission:** [Date]

---

**Tracking:** Tasks are managed in Jira. This file structures the assignment.
