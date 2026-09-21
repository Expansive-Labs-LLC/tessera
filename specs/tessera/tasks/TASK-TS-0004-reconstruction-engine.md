# Task: Single-Image 3D Reconstruction Engine

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0004 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-03-26 |
| **Assignment Method** | Sprint Planning |
| **Sprint/Iteration** | Phase 1 — Foundation |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🔴 P1 | XL | High | Feature | PRD |

**Note:** XL size but cannot be split further — this is a single coherent pipeline. Risk is High due to model selection uncertainty; a spike is recommended before full implementation.

---

## ⚠️ Special Instructions

> Must use model-agnostic adapter pattern (PRD §5.2) so reconstruction models can be swapped. Start with a single model (Trellis or InstantMesh) and add alternatives later.

---

## Business Context

### Why This Matters
This is the core AI capability — turning a 2D image into a 3D mesh. It's what makes Tessera magical. Without this, the product is just an empty shell.

### Why Now
On the critical path for Phase 1 (M1.4). Produces the raw mesh that downstream tasks (mesh import, print validation, export) consume.

### User Story
**As a** user who uploaded a photo of an object,  
**I want** the agent to generate a 3D mesh that looks like the object in my photo,  
**So that** I can get a starting point for a 3D-printable model without any modeling skills.

### Master PRD Reference
- **PRD Section:** §5.2 3D Reconstruction Engine, §9 Phase 1 (M1.4)
- **Strategic Goal:** G1 — Accept ≥1 reference image and infer the 3D geometry

---

## Initial Requirements

### What Needs to Be Built
1. **Model adapter interface** — Abstract base class defining: `reconstruct(images, masks, depth_maps, view_labels) → Mesh`. All reconstruction backends implement this interface.
2. **Primary backend** — Integrate one image-conditioned 3D model (Trellis, InstantMesh, or OpenLRM) as the first adapter implementation
3. **Mesh output normalization** — Convert model-specific outputs (NeRF volumes, implicit surfaces, point clouds) to a standard mesh format: vertices, faces, optional vertex colors
4. **Single-image path** — Given 1 image + segmentation mask + depth map, produce a plausible 3D mesh
5. **Few-image path** — Given 2 images with view labels, improve reconstruction quality using both views
6. **Error handling** — Graceful failure with actionable messages (e.g., "Could not reconstruct — try adding more images or a different angle")

### Known Constraints
- Local GPU inference only — all model weights pre-downloaded via TASK-TS-0002
- Must complete single-image reconstruction in <60 seconds on a consumer GPU (RTX 3060+)
- Output mesh may be rough — downstream tasks (TASK-TS-0005) handle cleanup
- Model-agnostic adapter pattern required — no hard-coupling to a specific model

### Success Looks Like
Given a single photo of simple objects (mug, vase, figurine), the engine produces a recognizable 3D mesh within 60 seconds. The mesh has correct general proportions and is ready for topology cleanup.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | §5.2 defines adapter pattern and model candidates |
| Trellis | [github.com/microsoft/TRELLIS](https://github.com/microsoft/TRELLIS) | Primary reconstruction model candidate |
| InstantMesh | [github.com/TencentARC/InstantMesh](https://github.com/TencentARC/InstantMesh) | Alternative reconstruction model |
| OpenLRM | [github.com/3DTopia/OpenLRM](https://github.com/3DTopia/OpenLRM) | Alternative reconstruction model |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0002 (Model Weights) | Pending | Blocks this | Reconstruction model weights must be cached |
| TASK-TS-0003 (Vision Pipeline) | Pending | Blocks this | Needs segmentation masks, depth maps, view labels |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Spike: Model Evaluation** | TBD |
| **Spec Approved** | TBD |
| **PR Submitted** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. Which model to start with — Trellis vs InstantMesh vs OpenLRM?
   - **Suggested resolution:** Run a spike to evaluate all three on 10 test images; pick best quality/speed/VRAM tradeoff
2. How to handle objects with concavities or interior detail that single-image models hallucinate?
   - **Suggested resolution:** Document known limitations; flag to user when confidence is low

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
