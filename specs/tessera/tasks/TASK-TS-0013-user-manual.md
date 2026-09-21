# Task: Comprehensive User Manual & Documentation Site

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0013 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-04-16 |
| **Assignment Method** | Sprint Planning |
| **Sprint/Iteration** | Phase 5 — Open Source & Publication |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🔴 P1 | XL | Med | Feature | PRD |

**Size Guide:** S (≤4 hrs) • M (1-2 days) • L (3-5 days) • XL (>5 days → split it)  
**Risk Guide:** Low (well-understood) • Med (some unknowns) • High (significant uncertainty, spike recommended)

---

## ⚠️ Special Instructions

> This is user-facing documentation that will be the primary support resource for both free and paid users. Quality and completeness directly impact marketplace reviews and support burden. Consider splitting into sub-tasks if scope exceeds XL.

---

## Business Context

### Why This Matters
Tessera is an AI-powered tool targeting users who may not be 3D modeling experts. Without clear, comprehensive documentation, users will struggle with installation (GPU setup, model weight downloads), basic usage (view labels, image requirements), and troubleshooting (VRAM issues, non-manifold outputs). Good documentation reduces support burden and increases marketplace satisfaction ratings.

### Why Now
Documentation is a hard requirement before marketplace listing. BlenderMarket and Gumroad buyers expect a professional user guide. The Blender Extensions Platform review process also evaluates documentation quality.

### User Story
**As a** Tessera user who just installed the add-on,  
**I want** step-by-step guides for every feature with troubleshooting help,  
**So that** I can generate my first 3D-printable model without getting stuck.

### Master PRD Reference
- **PRD Section:** §9 Phase 4 (M4.5 — Documentation, tutorials, example gallery)
- **Strategic Goal:** User satisfaction ≥4.2/5.0 (§10 Success Metrics)

---

## Initial Requirements

> ⚠️ **Starting points only.** Orchestrator will expand into full Spec.

### What Needs to Be Built
1. **Documentation site structure** — `docs/` directory with Markdown files, organized by user journey (install → first use → advanced → troubleshoot)
2. **Installation guides** — System requirements (GPU, VRAM minimums per feature, OS), marketplace install (one-click from BlenderMarket/Extensions), manual install (build from source), model weight first-run download walkthrough
3. **Usage guides** — Per-feature documentation covering:
   - Image input & view labels (vocabulary table from PRD §6)
   - Single-image reconstruction
   - Multi-view pipeline (3+ images)
   - Sketch-to-3D pathway
   - Mesh cleanup & topology controls
   - Real-world scaling & print orientation
   - Natural language refinement loop
   - Print validation & export (STL/3MF/OBJ)
   - Add-on preferences & GPU configuration
4. **Troubleshooting & FAQ** — GPU/VRAM issues, model download failures, common print-readiness problems, error message reference
5. **Reference section** — View label vocabulary, keyboard shortcuts, printer profile presets (FDM/SLA), glossary (from PRD §13)
6. **Screenshots & visual aids** — Annotated UI screenshots for each major panel and workflow step
7. **MkDocs + GitHub Pages** — Publishable documentation site with search, navigation, and mobile-friendly layout from day one (not a follow-up)

### Known Constraints
- Must cover Windows, macOS (Apple Silicon), and Linux installation paths
- Must document GPU requirements per feature tier (VRAM thresholds from SPEC-TS-0001)
- Content should be pulled from existing PRD sections and spec documents where possible
- Screenshots require a working Blender installation with the add-on enabled
- Must be maintainable — docs should reference features in a way that survives refactoring

### Success Looks Like
A new user can follow the quickstart guide to go from installation to their first exported STL in under 10 minutes. Advanced users can find reference documentation for every feature. Troubleshooting section resolves 80%+ of common issues without requiring support.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | §4 User Stories, §5 Architecture, §6 Input Spec, §7 Output Spec, §13 Glossary |
| All feature specs | `specs/tessera/feature-spec/active/SPEC-TS-*.md` | Detailed feature behavior and acceptance criteria |
| TASK-TS-0011 | `tasks/TASK-TS-0011-production-hardening.md` | M4.5 overlaps — coordinate scope |

### Key Code to Review
| File | Purpose |
|------|---------|
| `tessera/ui/*.py` | UI panel layouts for screenshot reference |
| `tessera/preferences.py` | Add-on preferences for GPU config documentation |
| `tessera/properties.py` | Property definitions for settings documentation |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0012 (Repo Foundation) | Pending | Soft dependency | README links to docs |
| All Phase 1–3 feature tasks | Complete | Content dependency | Features must exist to document them |
| TASK-TS-0011 (Production Hardening) | Pending | Scope absorbed | **TASK-TS-0013 fully owns all documentation scope** — M4.5 docs removed from 0011 |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Spec Approved** | TBD |
| **Docs Structure PR** | TBD |
| **Full Content PR** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. ~~Documentation format — hosted site or Markdown files only?~~
   - **Resolved:** MkDocs + GitHub Pages from the start. Markdown source files in `docs/`, published via MkDocs.
2. Should we bundle a help panel inside the add-on UI, or just link to the docs site?
   - **Suggested resolution:** Both — in-add-on tooltips + "Help" button that opens docs URL
3. Example gallery — do we have sample input images and output meshes to showcase?
   - **Suggested resolution:** Generate examples using the add-on; include input images + output screenshots + STL files in docs

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
