# Task: Blender Add-on Scaffold & GPU Configuration

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0001 |
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
| 🔴 P1 | L | Low | Feature | PRD |

**Size Guide:** S (≤4 hrs) • M (1-2 days) • L (3-5 days) • XL (>5 days → split it)  
**Risk Guide:** Low (well-understood) • Med (some unknowns) • High (significant uncertainty, spike recommended)

---

## ⚠️ Special Instructions

> All code must be GPL v2+ licensed. The add-on must target Blender 4.x+.

---

## Business Context

### Why This Matters
This is the foundational infrastructure for Tessera. Without a properly structured Blender add-on, no other features can be delivered to the user. This establishes the deployment model (local add-on), the UI surface area, and the GPU detection needed by all downstream tasks.

### Why Now
This is the first task in Phase 1 — every other task depends on this scaffold existing. It must be completed before image ingestion, reconstruction, or export work can begin.

### User Story
**As a** Blender user,  
**I want** to install Tessera as a standard Blender add-on,  
**So that** I can access AI-powered 3D generation directly from within Blender without switching tools.

### Master PRD Reference
- **PRD Section:** §5 System Architecture, §8 Technology Stack, §9 Phase 1 (M1.1)
- **Strategic Goal:** G2 — Produce geometry inside Blender so the user retains full editability

---

## Initial Requirements

> ⚠️ **Starting points only.** Orchestrator will expand into full Spec.

### What Needs to Be Built
1. Blender add-on boilerplate — `bl_info` registration, `register()`/`unregister()` lifecycle, proper module structure
2. Sidebar UI panel (N-panel) with sections for: image upload, view labeling, generation settings, output controls
3. Add-on preferences panel — GPU device selection (CUDA/ROCm auto-detect), VRAM reporting, model cache directory config
4. Operator stubs for the core workflow: upload images → generate → validate → export
5. Installable `.zip` packaging and basic install/uninstall testing

### Known Constraints
- Must be GPL v2+ compatible
- Must target Blender 4.x+ Python API (`bpy`)
- GPU required — add-on should check for CUDA/ROCm at install time and warn if not found (per D2)
- No external network calls for inference (per D3)

### Success Looks Like
User can install the add-on in Blender, see the Tessera panel in the sidebar, configure GPU preferences, and see stubs for image upload and generation — even though the AI pipeline isn't wired up yet.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | Source of all requirements |
| Blender Add-on Tutorial | [Blender docs](https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html) | Official guide for add-on structure |
| Blender Python API | [docs.blender.org/api](https://docs.blender.org/api/current/) | API reference |

### Key Code to Review
| File | Purpose |
|------|---------|
| `__init__.py` | Main add-on entry point (to be created) |
| `ui/panels.py` | UI panel definitions (to be created) |
| `preferences.py` | Add-on preferences (to be created) |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| None — this is the foundation | — | — | Proceed |

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

1. Minimum Blender version — 4.0 or 4.2 LTS?
   - **Suggested resolution:** Target 4.2 LTS as minimum for stability guarantees

### For Orchestrator to Add
> Space for Orchestrator to add questions before starting Spec:

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

> **Orchestrator: Complete this section within 24 hours of assignment.**

| Item | Status |
|------|--------|
| Task reviewed and understood | ☐ |
| Questions added above (if any) | ☐ |
| Questions resolved with CSO/Deputy | ☐ |
| Ready to begin Spec | ☐ |

**Acknowledged Date:** [Date]  
**Target Spec Submission:** [Date]

> 📋 **Next Step:** Create Spec using `/templates/spec-template.md` → Score for AI-Readiness (≥80) → Submit for CSO approval.
