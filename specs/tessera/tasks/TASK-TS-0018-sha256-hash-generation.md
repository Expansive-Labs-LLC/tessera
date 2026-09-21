# Task: SHA256 Hash Generation for Model Manifest

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0018 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-04-18 |
| **Assignment Method** | Handoff from Pipeline Wiring |
| **Sprint/Iteration** | Phase 1 — Security |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🔴 P0 | S | Medium | Security | SEC-001 |

**Note:** Small effort, high impact. All model file SHA256 hashes in `manifest.json` are `"TODO"` placeholders. This is a security requirement — model files must be verified against known hashes to prevent supply-chain tampering.

---

## ⚠️ Special Instructions

> This is a security-critical task. SHA256 hashes must be computed from files downloaded from the canonical HuggingFace repositories. Do NOT compute hashes from locally modified files.

---

## Business Context

### Why This Matters
Without hash verification, a malicious actor could replace model weight files with trojaned versions. The download manager currently skips verification for `"TODO"` hashes and logs a warning — this must be fixed before any public release.

### Why Now
Models have been downloaded successfully. The files exist on disk. Computing hashes is a one-time operation that must happen before marketplace publication.

### User Story
**As a** security-conscious user,  
**I want** the addon to verify downloaded model files against known checksums,  
**So that** I can trust that the AI models haven't been tampered with.

### Master PRD Reference
- **PRD Section:** §7 Security Requirements
- **Spec:** SPEC-TS-0002 (Model Weight Management), SEC-001

---

## Initial Requirements

### What Needs to Be Done

1. **Compute SHA256 Hashes**
   - For each file listed in `tessera/models/manifest.json`
   - Download fresh from HuggingFace (or use verified local copies)
   - Compute `sha256sum` for each file
   - Replace `"TODO"` with the actual hex digest

2. **Files Requiring Hashes** (from manifest.json)
   | Model | File | Current Hash |
   |-------|------|-------------|
   | depth-anything-v2-large | `depth_anything_v2_vitl.pth` | `TODO` |
   | sam2-hiera-large | `model.safetensors`, `config.json`, `preprocessor_config.json` | `TODO` |
   | dinov2-base | `model.safetensors`, `config.json`, `preprocessor_config.json` | `TODO` |
   | zero123plus-v1.2 | `model_index.json` | `TODO` |
   | instantmesh-large | `instant_mesh_large.ckpt` | `TODO` |

3. **Remove Skip Logic**
   - `tessera/models/download_manager.py` lines 391-401: Remove the `"TODO"` bypass in hash verification
   - `tessera/models/cache_manager.py` line 315-318: Remove the `"TODO"` skip logic
   - Ensure hash verification is enforced for all downloads

4. **Verify**
   - Re-run model downloads and confirm hash checks pass
   - Verify that a file with wrong hash is rejected

### Known Constraints
- HuggingFace model files may be updated by upstream — pin to specific commits/revisions if possible
- Hash computation is I/O-bound, not GPU-bound — can run on any machine
- The `zero123plus-v1.2` entry is a diffusers pipeline — may need to hash multiple files

### Success Looks Like
All `"TODO"` entries in `manifest.json` are replaced with valid SHA256 hex digests. The download manager verifies every file. Attempting to use a corrupted model file triggers a clear error.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Model Manifest | `tessera/models/manifest.json` | File to update |
| Download Manager | `tessera/models/download_manager.py` | Skip logic to remove |
| Cache Manager | `tessera/models/cache_manager.py` | Skip logic to remove |
| Model Weight Spec | `specs/tessera/feature-spec/active/SPEC-TS-0002-model-weight-management.md` | SHA256 requirements |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| Model Downloads | ✅ Complete | Needed | Files must exist on disk to compute hashes |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Hashes Computed** | TBD |
| **Manifest Updated** | TBD |
| **Skip Logic Removed** | TBD |
| **Verification Tested** | TBD |

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
| Ready to begin | ☐ |

**Acknowledged Date:** [Date]  
**Target Completion:** [Date]
