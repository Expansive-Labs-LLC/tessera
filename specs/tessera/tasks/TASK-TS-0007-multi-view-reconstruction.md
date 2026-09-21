# Task: Multi-View Alignment & Enhanced Reconstruction

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0007 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-03-26 |
| **Assignment Method** | Sprint Planning |
| **Sprint/Iteration** | Phase 2 — Multi-View & Quality |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🟡 P2 | XL | High | Feature | PRD |

**Note:** High risk due to structure-from-motion complexity. Spike recommended.

---

## Business Context

### Why This Matters
Single-image reconstruction has inherent ambiguity — the back of the object is always guessed. Multi-view reconstruction using 3+ images dramatically improves accuracy, captures detail on all sides, and produces meshes that are closer to the real object. This is the quality leap from "cool demo" to "actually printable replica."

### Why Now
Phase 2 (M2.1) — builds on the Phase 1 reconstruction engine. This is the primary quality improvement after the MVP is working.

### User Story
**As a** user who took photos of an object from multiple angles,  
**I want** the agent to combine all my photos into a more accurate 3D model,  
**So that** the printed result closely matches the real object from every angle.

### Master PRD Reference
- **PRD Section:** §5.1 (Multi-view alignment), §5.2 (Multi-view reconstruction), §9 Phase 2 (M2.1)
- **Strategic Goal:** G1 — Accept ≥1 reference image and infer geometry

---

## Initial Requirements

### What Needs to Be Built
1. **Camera pose estimation** — Structure-from-motion (SfM) lite to estimate relative camera positions from multiple images. View labels from TASK-TS-0003 act as strong priors.
2. **Pose graph optimization** — Use labeled view directions as constraints; refine with feature matching (SIFT/SuperPoint + SuperGlue or LightGlue)
3. **Multi-view reconstruction backend** — New adapter for the reconstruction engine (TASK-TS-0004 interface): NeuS2 or Instant-NGP → marching cubes mesh extraction
4. **Strategy selection** — Automatic routing: 1-2 images → single-image path; 3+ images → multi-view path
5. **Preview render pipeline** — Generate 4-view preview renders (front, side, top, perspective) via Eevee/Workbench after reconstruction (M2.5)

### Known Constraints
- Local GPU only
- SfM can fail on textureless or reflective objects — need graceful fallback to single-image path
- Multi-view reconstruction is significantly slower than single-image — target <5 min for 3–6 images

### Success Looks Like
Given 3–6 images with view labels, produce a mesh with correct proportions on all visible sides. Quality noticeably better than single-image reconstruction. Preview renders match input photos.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | §5.1, §5.2, §9 Phase 2 |
| NeuS2 | GitHub | Multi-view neural surface reconstruction |
| Instant-NGP | [github.com/NVlabs/instant-ngp](https://github.com/NVlabs/instant-ngp) | Fast NeRF → mesh |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0003 (Vision Pipeline) | Pending | Blocks this | View labels + features for pose estimation |
| TASK-TS-0004 (Reconstruction Engine) | Pending | Blocks this | Adapter interface to implement |
| TASK-TS-0005 (Mesh Import) | Pending | Blocks this | Cleanup pipeline for output mesh |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Spike: SfM Evaluation** | TBD |
| **Spec Approved** | TBD |
| **PR Submitted** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. Use existing SfM library (COLMAP, hloc) or build lightweight custom solution?
   - **Suggested resolution:** Start with hloc (hierarchical localization) — lighter than COLMAP, GPU-accelerated
2. Minimum number of images needed for reliable multi-view reconstruction?
   - **Suggested resolution:** 3 images with at least 90° angular separation; document as recommendation

### For Orchestrator to Add

1. _[Orchestrator adds questions here after reviewing task]_

---

## Escalation

| Need | Contact | Channel |
|------|---------|---------|
| Technical questions | TBD | DM |
| Business/Requirements | Derek | DM |
| Blocked | — | #blocked |

---

## Orchestrator Acknowledgment

| Item | Status |
|------|--------|
| Task reviewed and understood | ☐ |
| Questions added above (if any) | ☐ |
| Questions resolved with CSO/Deputy | ☐ |
| Ready to begin Spec | ☐ |

**Acknowledged Date:** [Date]  
**Target Spec Submission:** [Date]
