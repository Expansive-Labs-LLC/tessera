# Task: Real-World Scaling & Print Orientation

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0008 |
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
| 🟡 P2 | M | Med | Feature | PRD |

---

## Business Context

### Why This Matters
AI-generated meshes have arbitrary scale — they exist in "unit space" with no real-world dimensions. For 3D printing, exact mm dimensions are critical. A mug that prints at 5 mm tall or 500 mm tall is useless. This task ensures correct scaling and optimal orientation to minimize print supports.

### Why Now
Phase 2 (M2.3, M2.4). Once multi-view reconstruction improves quality, scaling and orientation become the next barrier to successful prints.

### User Story
**As a** user who specified my object should be 80 mm wide,  
**I want** the generated model to be exactly 80 mm wide in the exported STL,  
**So that** it prints at the correct size on my 3D printer.

### Master PRD Reference
- **PRD Section:** §5.3 Blender Orchestrator (steps 4–5), §6 Input Specification (target dimensions), §9 Phase 2 (M2.3, M2.4)
- **Strategic Goal:** G4, G6 — Configurable print constraints, correct unit scaling

---

## Initial Requirements

### What Needs to Be Built
1. **Dimension input UI** — Fields for target width/height/depth in mm; optional "auto" mode
2. **Auto-dimension inference** — Use object-class heuristics (e.g., "mug" → ~80mm tall) when user doesn't specify dimensions; prompt user to confirm
3. **Scale application** — Map mesh bounding box to user-specified dimensions; apply `bpy` scale transform
4. **Printer profile presets** — Build volume definitions for common printers (Ender 3, Prusa MK4, Elegoo Mars, etc.); user selects from dropdown
5. **Print orientation optimizer** — Analyze mesh geometry to find orientation minimizing overhangs > 45°; option to auto-orient or let user choose
6. **Bottom flattening** — Identify the flattest face region and align it to the build plate (Z=0)
7. **Scale sanity check** — Verify bounding box fits within selected printer's build volume; warn if too large/small

### Known Constraints
- Dimension inference is inherently approximate — must always confirm with user
- Orientation optimization is NP-hard in general; use heuristic (e.g., test 6 canonical orientations + gradient descent)

### Success Looks Like
User specifies "80 mm wide" → mesh exports at exactly 80 mm wide. Object auto-orients to minimize supports. Build volume check catches and warns about oversized models.

---

## Context & References

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0005 (Mesh Import) | Pending | Blocks this | Needs clean mesh with correct origin |
| TASK-TS-0006 (Print Validator) | Pending | Co-dependent | Scale sanity check integrates with validator |

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

1. How to handle objects with no obvious "front" or "bottom" — e.g., a sphere?
   - **Suggested resolution:** Default to lowest-surface-area base; let user override via rotation widget

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
