# Task: Vision Analysis Pipeline — Segmentation, Depth & View Labels

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0003 |
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
| 🔴 P1 | L | Med | Feature | PRD |

---

## ⚠️ Special Instructions

> All inference must run locally on GPU. The pipeline must handle the view-label vocabulary defined in PRD §6.

---

## Business Context

### Why This Matters
The vision pipeline is the "eyes" of Tessera — it processes user-uploaded reference images into structured data (depth maps, segmentation masks, view labels) that the reconstruction engine needs to build a 3D mesh. Without this, the agent can't understand what it's looking at.

### Why Now
This is on the critical path for Phase 1 (M1.3). The reconstruction engine (TASK-TS-0004) cannot function without vision pipeline output.

### User Story
**As a** user uploading reference images of an object,  
**I want** the agent to automatically segment the object from the background, estimate depth, and understand which angle each image shows,  
**So that** the 3D reconstruction is accurate and doesn't include background clutter.

### Master PRD Reference
- **PRD Section:** §5.1 Vision Analysis Pipeline, §6 Input Specification (View Labels)
- **Strategic Goal:** G1 — Accept ≥1 reference image and infer the 3D geometry

---

## Initial Requirements

### What Needs to Be Built
1. **Image ingestion** — Load images from user file browser; support `.jpg`, `.png`, `.webp`, `.heic`
2. **View-label UI** — Per-image dropdown/label assignment using PRD §6 vocabulary (`front`, `back`, `left`, `right`, `top`, `bottom`, `front-left`, `front-right`, `isometric`, `custom:<az>,<el>`)
3. **Object segmentation** — SAM 2 (or equivalent) to isolate the target object from background; output binary mask per image
4. **Monocular depth estimation** — Depth Anything V2 (or Marigold) to produce a depth map per image; run on local GPU
5. **View-label auto-detection** — Lightweight classifier to infer view direction when labels are omitted; confidence threshold at 80% with user confirmation fallback
6. **Feature extraction** — Extract shape priors, symmetry cues, and surface-normal hints (e.g., via DINOv2 features)
7. **Pipeline output format** — Standardized data structure per image: `{image, mask, depth_map, view_label, features}`

### Known Constraints
- All inference local GPU only — no external API calls
- Must handle variable image sizes and aspect ratios
- Must work with as few as 1 image
- View labels are optional — auto-detection must degrade gracefully

### Success Looks Like
User uploads 1–6 images, optionally labels them. Pipeline produces clean segmentation masks, depth maps, and confirmed view labels for each. Output is ready for consumption by the reconstruction engine.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | §5.1 and §6 define pipeline requirements |
| SAM 2 | [github.com/facebookresearch/sam2](https://github.com/facebookresearch/sam2) | Segmentation model |
| Depth Anything V2 | [github.com/DepthAnything](https://github.com/DepthAnything/Depth-Anything-V2) | Depth estimation model |
| DINOv2 | [github.com/facebookresearch/dinov2](https://github.com/facebookresearch/dinov2) | Feature extraction |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0001 (Add-on Scaffold) | Pending | Blocks this | UI panel for image upload + labeling |
| TASK-TS-0002 (Model Weights) | Pending | Blocks this | SAM 2, Depth Anything, DINOv2 weights must be cached |

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

1. SAM 2 vs lighter alternative — SAM 2 is large. Should we evaluate FastSAM or MobileSAM for lower VRAM usage?
   - **Suggested resolution:** Spike both; use model adapter pattern to support swapping
2. Minimum GPU VRAM for the full vision pipeline (SAM 2 + Depth Anything + DINOv2 running sequentially)?
   - **Suggested resolution:** Profile and document; target 8 GB VRAM minimum

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
