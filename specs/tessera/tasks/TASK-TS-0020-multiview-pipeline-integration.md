# Task: Multi-View Reconstruction Pipeline Integration

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0020 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-04-18 |
| **Assignment Method** | Handoff from Pipeline Wiring |
| **Sprint/Iteration** | Phase 2 — Features |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🟡 P1 | L | High | Feature | SPEC-TS-0007 |

---

## Business Context

### Why This Matters
Multi-view reconstruction produces significantly higher quality meshes than single-image. When users provide 3+ photos from different angles, the system should route to NeuS2 for proper multi-view reconstruction instead of the single-image path.

### User Story
**As a** user who took multiple photos of an object from different angles,  
**I want** the system to use all my photos for better reconstruction quality,  
**So that** the resulting 3D model is more accurate and detailed.

### Master PRD Reference
- **PRD Section:** §5.3 Multi-view Reconstruction
- **Spec:** SPEC-TS-0007

---

## Initial Requirements

### What Needs to Be Built

1. **Engine Routing** — Update `ReconstructionEngine` to route 3+ images to multi-view path
   - Currently caps at `_MAX_INPUTS = 2` in `tessera/reconstruction/engine.py`
   - Need strategy selector to choose single-image vs multi-view

2. **Multi-View Adapter** — Wire `tessera/multiview/` code as a reconstruction adapter
   - NeuS2 backend: `tessera/multiview/reconstruction/neus2_backend.py`
   - HLoc pose estimation: `tessera/multiview/pose/hloc_adapter.py`
   - Camera setup: `tessera/multiview/camera/camera_setup.py`

3. **UI Updates**
   - Show multi-view indicator when 3+ images loaded
   - Display pose estimation progress

### Existing Code (already written)
- `tessera/multiview/reconstruction/neus2_backend.py` — NeuS2 training + mesh extraction
- `tessera/multiview/pose/hloc_adapter.py` — HLoc pose estimation
- `tessera/multiview/camera/camera_setup.py` — Camera intrinsics/extrinsics
- `tessera/multiview/preview/renderer.py` — Preview images

---

## Context & References

| Document | Location |
|----------|----------|
| Multi-View Spec | `specs/tessera/feature-spec/active/SPEC-TS-0007-multi-view-reconstruction.md` |
| Multi-View Code | `tessera/multiview/` |
| Engine | `tessera/reconstruction/engine.py` |

### Dependencies
| Task/Item | Status | Dependency |
|-----------|--------|------------|
| TASK-TS-0016 (Vision Adapter Validation) | Pending | Multi-view needs valid vision outputs |
| TASK-TS-0017 (Trellis Inference) | Pending | Single-image must work first |

---

## Orchestrator Acknowledgment

| Item | Status |
|------|--------|
| Task reviewed and understood | ☐ |
| Ready to begin | ☐ |

**Acknowledged Date:** [Date]
