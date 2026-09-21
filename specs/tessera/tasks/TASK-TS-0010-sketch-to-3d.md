# Task: Sketch-to-3D Pathway

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0010 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-03-26 |
| **Assignment Method** | Sprint Planning |
| **Sprint/Iteration** | Phase 3 — Intelligence & Refinement |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🟢 P3 | L | High | Feature | PRD |

**Note:** P3 because the photo-based path (TASK-TS-0004) serves the primary use case. This extends coverage to hand-drawn input. High risk — sketch interpretation is less mature than photo-to-3D.

---

## Business Context

### Why This Matters
Not every user has a photo of what they want to create. Designers, students, and hobbyists often start with a sketch on paper or a tablet drawing. Supporting sketch input dramatically broadens the user base and enables the US-04 user story (educator/student photographing a hand-drawn shape).

### Why Now
Phase 3 (M3.4). The core pipeline must be stable before adding a new input modality. This builds on the existing reconstruction adapter pattern.

### User Story
**As a** student who drew a shape on paper,  
**I want** to photograph my drawing and have the agent turn it into a 3D object,  
**So that** I can hold a physical version of my sketch.

### Master PRD Reference
- **PRD Section:** §5.2 (Sketch-to-3D strategy), §4 User Stories (US-04), §9 Phase 3 (M3.4)
- **Strategic Goal:** G1 — Accept ≥1 reference image and infer geometry

---

## Initial Requirements

### What Needs to Be Built
1. **Sketch detection** — Classify whether an uploaded image is a photo or a sketch/line drawing (edge density heuristic + classifier)
2. **Sketch preprocessing** — Clean up: thresholding, noise removal, line thinning, optional perspective correction
3. **Sketch-conditioned reconstruction adapter** — New adapter for the reconstruction engine interface; uses a sketch-specialized model with symmetry priors
4. **Symmetry-aware generation** — Sketches often depict only one side. Apply bilateral symmetry by default; allow user to disable
5. **Multi-view sketch support** — Allow user to upload front + side sketch → combine into 3D

### Known Constraints
- Sketch quality varies wildly — pencil on paper vs. digital vector art vs. crayon
- Must handle perspective distortion from phone camera photographing paper
- Reconstruction from sketches is inherently more ambiguous than from photos

### Success Looks Like
User photographs a simple pencil sketch of a vase → agent detects it's a sketch → applies symmetry → produces a recognizable 3D vase that prints successfully.

---

## Context & References

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0003 (Vision Pipeline) | Pending | Blocks this | Segmentation + preprocessing |
| TASK-TS-0004 (Reconstruction Engine) | Pending | Blocks this | Adapter interface to implement |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Spike: Sketch Model Eval** | TBD |
| **Spec Approved** | TBD |
| **PR Submitted** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. Which sketch-conditioned 3D model to use? This is a less mature space than photo-to-3D.
   - **Suggested resolution:** Run a spike; evaluate candidates from recent papers
2. Should we support digital vector sketches (SVG) in addition to raster photos of hand-drawn sketches?
   - **Suggested resolution:** Defer SVG support; focus on raster (photo of paper) for v1

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
