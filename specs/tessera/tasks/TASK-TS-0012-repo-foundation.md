# Task: Repository Foundation & Open-Source Readiness

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0012 |
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
| 🔴 P1 | M | Low | Feature | PRD |

**Size Guide:** S (≤4 hrs) • M (1-2 days) • L (3-5 days) • XL (>5 days → split it)  
**Risk Guide:** Low (well-understood) • Med (some unknowns) • High (significant uncertainty, spike recommended)

---

## ⚠️ Special Instructions

> GitHub repository already exists at `Expansive-Labs-LLC/tessera` (initialized but nothing pushed). All code is GPL-2.0-or-later as declared in `bl_info` and file headers. This task prepares the repo for first push and public visibility.

---

## Business Context

### Why This Matters
Tessera is going open-source and will also be sold on marketplaces. Before any code is pushed publicly, the repository needs proper licensing, contributor documentation, security policy, and a README that communicates the value proposition. This is the first impression for both open-source contributors and potential marketplace buyers evaluating the project.

### Why Now
Must be completed before the first public push. All other publication tasks (CI, docs, marketplace) depend on the repository foundation being in place.

### User Story
**As a** developer discovering Tessera on GitHub,  
**I want** a clear README, license, and contribution guidelines,  
**So that** I understand what the project does, how to use it, and how to contribute.

### Master PRD Reference
- **PRD Section:** §8 Technology Stack (GPL licensing), §9 Phase 4 (M4.5 — Documentation)
- **Strategic Goal:** Open-source publication + marketplace revenue

---

## Initial Requirements

> ⚠️ **Starting points only.** Orchestrator will expand into full Spec.

### What Needs to Be Built
1. **LICENSE** — GPL-2.0-or-later full text (already declared in all file headers and `bl_info`)
2. **README.md** — Hero section, feature highlights, system requirements (GPU/VRAM/Blender 4.2+), quick-start (marketplace install + build from source), badges (CI, license, Blender version, latest release), links to full docs
3. **CONTRIBUTING.md** — Dev environment setup, Conventional Commits requirement (for semantic-release), PR process, testing instructions, code style conventions
4. **CODE_OF_CONDUCT.md** — Contributor Covenant v2.1
5. **SECURITY.md** — Vulnerability reporting process; note that all inference is local (no network calls except model weight download)
6. **.gitignore** — Python, Blender, model weights, `.venv`, `__pycache__`, `.pytest_cache`, `.agent/` (internal tooling only — `specs/` and `tasks/` remain visible for contributors)
7. **.github/ISSUE_TEMPLATE/** — `bug_report.yml` (structured: GPU, Blender version, VRAM, OS, steps to reproduce), `feature_request.yml`
8. **.github/PULL_REQUEST_TEMPLATE.md** — Checklist (tests pass, conventional commits, docs updated)
9. **.github/FUNDING.yml** — Link to marketplace listings for supporters

### Known Constraints
- Must be GPL-2.0-or-later (Blender add-on requirement, already decided in PRD D6)
- README must work for two audiences: open-source contributors AND marketplace buyers evaluating the project
- `.gitignore` must exclude `.agent/` (internal tooling); `specs/` and `tasks/` stay visible — contributors need them to follow the Task → Spec → Implement workflow
- Conventional Commits are mandatory for semantic-release compatibility

### Success Looks Like
A developer can clone the repo, immediately understand what Tessera does, how to set up a dev environment, and how to contribute. The repo looks professional and well-maintained at first glance.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | Source for README content (§1, §2, §6, §8) |
| Existing `bl_info` | `tessera/__init__.py` | License and version info already declared |
| Existing versioning action | `Expansive-Labs-LLC/github-actions/versioning` | Referenced in CONTRIBUTING for commit conventions |

### Key Code to Review
| File | Purpose |
|------|---------|
| `tessera/__init__.py` | Existing `bl_info` with GPL header |
| `PRD-001_Tessera.md` | Content source for README |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| None — this is the foundation for Phase 5 | — | — | Proceed |

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

1. ~~Should `specs/` and `tasks/` directories be excluded from the public repo?~~
   - **Resolved:** Specs and tasks are **visible** — contributors need to update specs when contributing. Only `.agent/` is excluded.
2. Should the README include marketplace purchase links, or keep it purely open-source focused?
   - **Suggested resolution:** Include both — "Install from Marketplace" (one-click) AND "Build from Source" sections

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
