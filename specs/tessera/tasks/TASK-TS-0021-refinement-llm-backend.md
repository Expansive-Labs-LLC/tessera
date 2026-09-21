# Task: Refinement LLM Backend Configuration

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0021 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-04-18 |
| **Assignment Method** | Handoff from Pipeline Wiring |
| **Sprint/Iteration** | Phase 2 — Features |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🟡 P1 | M | Medium | Feature | SPEC-TS-0009 |

---

## Business Context

### Why This Matters
The refinement chat lets users edit meshes with natural language ("make it taller", "smooth the top"). The operators are wired and the chat panel works, but the LLM backend that parses natural language into mesh operations needs configuration.

### User Story
**As a** user who generated a 3D model,  
**I want** to type "make it 20% taller" in the chat and see the mesh update,  
**So that** I can refine my model without learning Blender's complex interface.

### Master PRD Reference
- **PRD Section:** §5.6 Natural-Language Refinement
- **Spec:** SPEC-TS-0009

---

## Initial Requirements

### What Needs to Be Built

1. **API Key Configuration** — Add to addon preferences
   - OpenAI API key field (encrypted/hidden)
   - Anthropic API key field (alternative)
   - Model selector (gpt-4o, claude-sonnet, etc.)
   - Optional: Ollama/local model endpoint URL

2. **Backend Wiring** — `tessera/refinement/llm_backend.py`
   - Connect the existing `LLMBackend` interface to real API calls
   - Implement `APIBackend` using OpenAI/Anthropic SDK
   - Implement `LocalBackend` using Ollama HTTP API
   - Error handling when no backend is configured

3. **UI Feedback**
   - Show warning in chat panel when no LLM is configured
   - Link to preferences from the warning

### Existing Code (already written)
- `tessera/refinement/chat_manager.py` — Session management, message history
- `tessera/refinement/intent_parser.py` — Parses LLM response into mesh operations
- `tessera/refinement/edit_executor.py` — Executes parsed operations
- `tessera/refinement/undo_manager.py` — Undo/redo stack
- `tessera/operators/refinement_ops.py` — All 5 operators registered and wired
- `tessera/ui/chat_panel.py` — Full chat UI with message history

---

## Context & References

| Document | Location |
|----------|----------|
| Refinement Spec | `specs/tessera/feature-spec/active/SPEC-TS-0009-nl-refinement-loop.md` |
| LLM Backend | `tessera/refinement/llm_backend.py` |
| Intent Parser | `tessera/refinement/intent_parser.py` |
| Chat Panel | `tessera/ui/chat_panel.py` |
| Preferences | `tessera/preferences.py` |

### Dependencies
| Task/Item | Status | Dependency |
|-----------|--------|------------|
| Generate Pipeline | ✅ Complete | Need a mesh to refine |
| Refinement Operators | ✅ Wired | Operators call LLM backend |

---

## Open Questions

1. Should we ship with a default API provider or require user configuration?
2. Is local-only inference (Ollama) viable for intent parsing, or do we need GPT-4/Claude quality?
3. How do we handle API costs? Should there be a token budget/warning?

---

## Orchestrator Acknowledgment

| Item | Status |
|------|--------|
| Task reviewed and understood | ☐ |
| Ready to begin | ☐ |

**Acknowledged Date:** [Date]
