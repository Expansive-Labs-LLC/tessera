# Task: Local Model Weight Management

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0002 |
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
| 🔴 P1 | M | Med | Feature | PRD |

---

## ⚠️ Special Instructions

> All model weights must be downloaded from official/verified sources. No network calls during inference — weights are cached locally.

---

## Business Context

### Why This Matters
Tessera runs entirely locally — no cloud APIs. The vision, depth, segmentation, and reconstruction models all require downloading multi-GB weight files. This task builds the infrastructure to download, cache, version, and manage disk usage for all model weights in a user-friendly way.

### Why Now
Every AI pipeline task (0003–0005) depends on weights being available locally. This must be completed or co-developed alongside the first pipeline tasks.

### User Story
**As a** Tessera user,  
**I want** model weights to download automatically on first use and be cached locally,  
**So that** I don't have to manually manage AI model files or worry about disk space.

### Master PRD Reference
- **PRD Section:** §8 Technology Stack, §9 Phase 1 (M1.2), §11 Risks (model weight download size)
- **Strategic Goal:** D3 — Local/self-hosted only

---

## Initial Requirements

### What Needs to Be Built
1. Model registry — manifest of all required models with: name, version, download URL, expected SHA256, file size, minimum VRAM
2. Download manager — background download with progress reporting in Blender UI, resume support for interrupted downloads
3. Cache directory management — configurable path (default: add-on preferences), disk usage display, clear/re-download options
4. Version management — detect when a newer model version is available, allow user to upgrade
5. VRAM-aware model selection — detect available GPU VRAM, recommend/select appropriate model variant (e.g., fp16 vs fp32)

### Known Constraints
- Downloads happen via HTTPS from official model repos (HuggingFace, GitHub Releases)
- No inference-time network calls — all weights must be local before pipeline runs
- Must handle users with limited disk space gracefully

### Success Looks Like
User installs Tessera, triggers first generation, sees a progress bar as models download (~2-5 GB), and subsequent uses load instantly from cache. User can see disk usage and clear cache from preferences.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | Requirements source |
| HuggingFace Hub API | [huggingface.co/docs](https://huggingface.co/docs/huggingface_hub) | Potential download mechanism |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0001 (Add-on Scaffold) | Pending | Blocks this | Preferences panel needed for cache config |

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

1. Should we use `huggingface_hub` Python library or build custom download logic?
   - **Suggested resolution:** Use `huggingface_hub` — well-tested, handles caching natively
2. Total disk footprint target for all models combined?
   - **Suggested resolution:** Discuss with Derek — target <10 GB for core models

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
