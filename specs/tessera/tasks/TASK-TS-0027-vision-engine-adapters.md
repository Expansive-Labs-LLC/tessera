# Task: Vision Engine Adapters — SAM 2, DINOv2, Depth Anything V2

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0027 |
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
| 🟡 P1 | L | Med | Feature | SPEC-TS-0023 |

---

## ⚠️ Special Instructions

> **These three are not blocked on each other.** SAM 2 and DINOv2 carry the
> most torch references (10 and 12), but each stage is an independent adapter
> behind one dispatch layer. Land them one at a time rather than as a batch.

---

## Business Context

### Why This Matters

The vision pipeline feeds reconstruction. Segmentation isolates the object,
depth gives geometry hints, and DINOv2 features are consumed by the
reconstruction adapter. `families.py` records `adapter_ready=False` for `sam2`
and `dinov2`, so none of it runs.

### Why Now

Reconstruction quality depends on these inputs being real rather than
placeholder. Follows TASK-TS-0026 because a mesh from real photos is the first
thing worth measuring.

### User Story

**As a** Tessera user photographing an object against a cluttered background,
**I want** the object isolated and its depth estimated before reconstruction,
**So that** the mesh is of my object and not of my kitchen table.

### Master PRD Reference

- **PRD Section:** §5.1 Vision Analysis Pipeline, §8 Technology Stack
- **Strategic Goal:** G1 — photo to printable mesh; G3 — quality good enough
  to print without manual repair

---

## Initial Requirements

> ⚠️ **Starting points only.** These expand into the full Spec.

### What Needs to Be Built

1. **SAM 2 segmentation adapter** — `segment` stage; returns a base64 8-bit
   mask plus a coverage float (FR-029)
2. **Depth Anything V2 adapter** — `depth` stage; returns a float32 `(H, W)`
   depth map in `[0.0, 1.0]` as a raw buffer, not a PNG (FR-027)
3. **DINOv2 feature adapter** — `features` stage; returns a float32 `(1, D)`
   CLS embedding
4. **Per-stage VRAM declaration** so `insufficient_vram` is refused before load
5. **Flip `adapter_ready=True`** for `sam2` and `dinov2` as each lands

### Known Constraints

- Response shapes are fixed by FR-029 and must match exactly; the add-on
  decodes against declared dtype and shape and refuses a mismatch
- `safetensors` or `weights_only=True` loading only (FR-023, SEC-009)
- One inference at a time; the dispatch layer holds the lock (FR-021)
- The engine receives resolved verified paths only (CON-005)

### Success Looks Like

A photograph with a cluttered background produces a clean object mask, a
plausible depth map and a feature embedding, all computed in the engine
process, with the add-on none the wiser that torch exists.

---

## Context & References

### Key Documents

| Document | Location | Why Relevant |
|----------|----------|--------------|
| Local inference engine | `specs/tessera/feature-spec/active/SPEC-TS-0023-local-inference-engine.md` | FR-006, FR-029 per-stage response shapes |
| Vision pipeline | `specs/tessera/feature-spec/active/SPEC-TS-0003-vision-pipeline.md` | `VisionResult` and the stage contracts; needs amending |

### Key Code to Review

| File | Purpose |
|------|---------|
| `tessera/vision/segmentation/sam2_adapter.py` | Moves engine-side; 10 torch references |
| `tessera/vision/features/dinov2_adapter.py` | Moves engine-side; 12 torch references |
| `tessera/vision/depth/depth_anything_adapter.py` | Moves engine-side |
| `tessera/vision/types.py` | `VisionResult` — the shape the wire projection must preserve |
| `tessera_engine/inference.py` | `vision()` dispatch and `register_adapter` |
| `tessera_engine/codec.py` | Array encoding the responses must use |

### Dependencies

| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0026 (TRELLIS) | Not started | Not blocking, but proves the pattern | Follow it |
| SPEC-TS-0003 amendment | Not started | Blocked by this | NFR-003 and the OOM edge case become engine-side |
| TASK-TS-0016 | Superseded | — | Its scope is absorbed here; close or redirect it |

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

1. **Do all three stages share one model cache in the engine?**
   - **Suggested resolution:** Probably, but it interacts with SPEC-TS-0011's
     LRU cache requirement, which is itself pending amendment. Decide with that
     amendment rather than ahead of it.
2. **Is `features` still needed on the wire if DINOv2 runs engine-side too?**
   - **Suggested resolution:** Yes. FR-025 carries it because the multi-view
     path and the reconstruction adapter both consume it, and the add-on may
     hold a result across calls.

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
