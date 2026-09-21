# Task: Natural-Language Refinement Loop

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0009 |
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
| 🟡 P2 | XL | High | Feature | PRD |

**Note:** High risk — natural language → geometry editing is an unsolved research-adjacent problem. Spike recommended.

---

## Business Context

### Why This Matters
The feedback loop is what turns Tessera from a one-shot generator into an interactive tool. Users can say "make the handle thicker" or "smooth the top" without knowing any Blender operations. This is the feature that makes Tessera feel like an AI assistant rather than a black box.

### Why Now
Phase 3 (M3.1, M3.2, M3.3). Depends on a working end-to-end pipeline from Phases 1–2. This is the "intelligence" upgrade.

### User Story
**As a** user looking at the generated model in Blender,  
**I want** to type "make the base 5 mm thicker" and have the model update accordingly,  
**So that** I can iteratively refine the model without learning Blender's editing tools.

### Master PRD Reference
- **PRD Section:** §5.5 Feedback & Refinement Loop, §9 Phase 3 (M3.1, M3.2, M3.3)
- **Strategic Goal:** G5 — Provide an iterative feedback loop via natural language

---

## Initial Requirements

### What Needs to Be Built
1. **Chat/command input UI** — Text input field in the sidebar panel for natural-language commands
2. **Intent parser** — LLM-powered (local) parsing of user commands into structured edits: `{operation, target_region, parameters}`
3. **Semantic part identification** — Map natural-language part names ("handle", "base", "lid", "top") to mesh regions via:
   - Named vertex groups set during initial reconstruction
   - Spatial heuristics (e.g., "base" = bottom 20% of mesh)
   - User-clickable selection as fallback
4. **Edit operations library** — Map intents to `bpy.ops` sequences:
   - Scale (directional), move, rotate
   - Solidify / thicken / hollow
   - Smooth / sharpen / bevel
   - Add/remove geometry (basic primitives)
5. **Undo / version history** — Snapshot-based undo stack; user can say "undo that" or "go back to version 2"
6. **Post-edit re-validation** — Re-run print-readiness validator (TASK-TS-0006) after each edit
7. **Preview render** — Generate and return a quick Eevee/Workbench render after each edit
8. **Ambiguity handling** — When the agent isn't sure what the user means, ask for clarification before applying

### Known Constraints
- LLM must run locally or via user's own API key (per D3)
- Must handle 5+ rounds of refinement without degrading mesh quality
- Each edit cycle should complete in <15 seconds
- Undo stack has finite depth (suggest 20 snapshots max to manage disk)

### Success Looks Like
User makes 5 successive text-based edits ("make it taller", "smooth the top", "thicken the walls", "rotate 45 degrees", "undo that"). Each edit applies correctly to the right mesh region. Model remains print-valid after each edit. Preview renders update after each change.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | §5.5 |
| Blender Operators API | [docs.blender.org](https://docs.blender.org/api/current/bpy.ops.html) | All available operations |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0001 (Add-on Scaffold) | Pending | Blocks this | UI panel for chat input |
| TASK-TS-0005 (Mesh Import) | Pending | Blocks this | Needs named vertex groups |
| TASK-TS-0006 (Print Validator) | Pending | Blocks this | Re-validation after edits |
| TASK-TS-0002 (Model Weights) | Pending | Blocks this | LLM weights if using local LLM |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Spike: LLM → bpy mapping** | TBD |
| **Spec Approved** | TBD |
| **PR Submitted** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. Local LLM (Llama 3.1 8B) vs user-provided API key (Claude/Gemini) for intent parsing?
   - **Suggested resolution:** Support both — local LLM as default, optional API key override in preferences
2. How to handle edits that conflict with print-readiness (e.g., "make the wall 0.1 mm thin")?
   - **Suggested resolution:** Apply edit, run validator, show warning with "this will make the model unprintable — proceed anyway?"

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
