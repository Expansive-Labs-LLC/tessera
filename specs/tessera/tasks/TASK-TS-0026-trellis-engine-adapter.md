# Task: TRELLIS Engine Adapter

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0026 |
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
| 🔴 P0 | XL | High | Spike + Feature | SPEC-TS-0023 |

---

## ⚠️ Special Instructions

> **This is a spike before it is a feature.** Whether TRELLIS's compiled
> extensions build for Blackwell is genuinely unknown, and the answer decides
> both the installer's real contents and the shape of its CI job. Establish
> that first and report, before writing adapter code on top of an assumption.

---

## Business Context

### Why This Matters

This is the task that makes Tessera produce a real mesh. `tessera_engine`
registers no adapters at all, so every reconstruction request returns
`load_failed`, and `tessera/models/families.py` still records
`adapter_ready=False` for `trellis`.

### Why Now

Nothing downstream is worth much until one real mesh exists. It is also the
only remaining item with genuine unknown risk.

### User Story

**As a** Tessera user with a photo and a CUDA GPU,
**I want** Generate to produce a recognisable 3D model of my object,
**So that** the product does the thing it is for.

### Master PRD Reference

- **PRD Section:** §5.2 3D Reconstruction Engine (TRELLIS in v1), §8, D10
- **Strategic Goal:** G1 — photo to printable mesh without leaving Blender

---

## Initial Requirements

> ⚠️ **Starting points only.** These expand into the full Spec.

### What Needs to Be Built

1. **Spike: the extension set (do this first)**
   - Pin TRELLIS to a commit — the repository has no releases, and a moving
     default branch would change an installer's contents without changing its
     version
   - Establish which extensions (sparse-voxel rasterisation, attention kernels
     and their dependencies) compile against CUDA 12.8 for `sm_120`
   - Report before proceeding. Whatever it takes to build here is what CI has
     to reproduce per architecture

2. **Reconstruction adapter, engine-side**
   - Register via `register_adapter("reconstruction", "trellis", ...)`
   - Accept decoded `VisionPipelineOutput` fields; return vertices, faces,
     optional vertex colours and the five required metadata keys
   - Move the existing `tessera/reconstruction/adapters/trellis_adapter.py`
     logic engine-side; weight resolution stays add-on side

3. **VRAM and failure behaviour**
   - Declare a minimum so `insufficient_vram` is refused before load, not
     inside the allocator (FR-019)
   - Leave no partially-loaded state after a failure (EC-005)
   - Free GPU memory after every request, success or failure (FR-020)

4. **Weight loading (FR-023, SEC-004, SEC-009)**
   - `safetensors` or `torch.load(..., weights_only=True)` only
   - No `trust_remote_code` path, no importing code found beside weights

5. **Flip the flag**
   - `adapter_ready=True` for `trellis` in `tessera/models/families.py`

### Known Constraints

- The engine never resolves, downloads or verifies weights. It receives
  absolute paths inside the launch-argument cache root (FR-007, CON-005, CON-011)
- No `bpy` anywhere in the engine (CON-002)
- Results are bounded at 1,000,000 vertices / 2,000,000 faces (FR-028)
- Engine source is GPL-2.0-or-later like the add-on (CON-010)
- v1 is CUDA-only; device selection stays one replaceable component (FR-024)

### Success Looks Like

A user loads a photograph, clicks Generate, and a recognisable mesh with more
than 8 vertices and 12 faces appears in the viewport — AC-001, which no
configuration of Tessera currently satisfies.

---

## Context & References

### Key Documents

| Document | Location | Why Relevant |
|----------|----------|--------------|
| Local inference engine | `specs/tessera/feature-spec/active/SPEC-TS-0023-local-inference-engine.md` | AC-001, FR-005, FR-019, FR-020, FR-023, FR-028 |
| Premise verification | `specs/tessera/adr/ADR-0001-premise-verification.md` | Why the extensions build from source and what that costs |
| Reconstruction engine | `specs/tessera/feature-spec/active/SPEC-TS-0004-reconstruction-engine.md` | `StandardMesh`, `ReconstructionResult`, VRAM behaviour |
| Model licences | `MODEL-LICENSES.md` | TRELLIS is MIT; confirm before shipping |

### Key Code to Review

| File | Purpose |
|------|---------|
| `tessera/reconstruction/adapters/trellis_adapter.py` | The implementation that moves engine-side |
| `tessera_engine/inference.py` | `register_adapter` and the dispatch layer that calls it |
| `tessera_engine/runtime.py` | `probe_device`, VRAM reporting, cache-root resolution |
| `tessera/reconstruction/mesh_output.py` | `StandardMesh.metadata` required keys the response must carry |
| `packaging/linux/requirements-engine.txt` | Where the pin and extension set go |
| `packaging/linux/provision_toolchain.sh` | Gets a CUDA 12.8 toolchain without root |

### Dependencies

| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| SPEC-TS-0023 | Approved | Blocks this | Proceed |
| CUDA ≥ 12.8 toolchain | Available | Blocks the build | `packaging/linux/provision_toolchain.sh` |
| TASK-TS-0025 (add-on wiring) | Not started | Neither blocks the other | Parallel |
| SPEC-TS-0003 / 0011 amendments | Not started | Blocked by this | Their `torch.cuda.*` concerns move engine-side |

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

1. **Which TRELLIS extensions actually build for `sm_120`?**
   - **Suggested resolution:** Unknown, and it is the reason this is a spike.
     Timebox the build; if an extension cannot be made to compile, report
     before writing adapter code around it.
2. **If an extension will not build, is a different backend acceptable?**
   - **Suggested resolution:** ADR-0001 Option 4 was "not rejected, but not
     sufficient" and explicitly revisitable as an engine-side choice. Raise it
     rather than deciding alone — PRD-001 §5.2 names TRELLIS in v1.
3. **Should the engine refuse a GPU outside its built architecture list?**
   - **Suggested resolution:** Yes. `build-info.json` already records
     `cuda_arch_list`; refusing with a clear message beats a kernel that will
     not launch.

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
