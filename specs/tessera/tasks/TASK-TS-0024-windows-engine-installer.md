# Task: Windows Engine Installer

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0024 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-09-24 |
| **Assignment Method** | SPEC-TS-0023 FR-030 deferral |
| **Sprint/Iteration** | Phase 6 — Integration & Pre-Launch |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🟡 P2 | M | Low | Packaging | SPEC-TS-0023 |

---

## ⚠️ Special Instructions

> **Do not ship an unsigned Windows installer.** SmartScreen will flag it, and
> an audience of artists reading a security warning is a worse outcome for
> ADR-0001 D2 than having no Windows build yet. Acquire the signing identity
> before building anything.

---

## Business Context

### Why This Matters

Windows is the larger share of the Blender user base. v1 ships a Linux-only
engine (SPEC-TS-0023 FR-030), so most prospective users cannot generate a mesh
at all — the add-on installs, reports `Not installed`, and stops there.

### Why Now

It is the only remaining platform gap for CUDA hardware, and the critical path
is procurement lead time rather than code. Starting the identity now means it
is ready when the artifact is.

### User Story

**As a** Windows Blender user with an NVIDIA GPU,
**I want** to install the Tessera engine as easily as a Linux user can,
**So that** the add-on I already installed can actually produce a mesh.

### Master PRD Reference

- **PRD Section:** §8 Technology Stack, D10 (inference runtime delivery)
- **Strategic Goal:** G1 — photo to printable mesh inside Blender; G5 —
  installation stays within what a Blender artist will tolerate

---

## Initial Requirements

> ⚠️ **Starting points only.** These expand into the full Spec.

### What Needs to Be Built

1. **Signing identity (start first — it is the lead time)**
   - Azure Trusted Signing (~$10/month; the three-year trading-history rule was
     dropped in 2026 and it now covers US/CA/EU/UK businesses and the
     self-employed), or an EV certificate from a CA (~$279–580/year, one-year
     maximum lifespan from 2026-02-15)
   - Azure sign-up was failing through the web interface as of 2026-09-23.
     Retry or escalate through support before concluding the route is closed

2. **Installer artifact**
   - Same payload as Linux: pinned CPython, virtual environment, PyTorch
     `cu128`, TRELLIS extensions built per architecture
   - Native installer format, Authenticode-signed

3. **Marker and descriptor**
   - Write `%LOCALAPPDATA%\Tessera\engine\install.json`. The add-on's
     discovery already resolves this path, so no client change is required
   - Confirm the runtime descriptor's owner-only permissions behave as intended
     on NTFS — `os.chmod(0o600)` does not mean on Windows what it means on POSIX,
     and that file carries the request token

4. **CI**
   - Windows runner with a CUDA toolkit supporting every target compute
     capability, failing the build when it cannot target one

### Known Constraints

- The add-on should need no change. If it does, something in SPEC-TS-0023's
  discovery design was wrong and should be raised rather than worked around
- `codec.py` stays byte-identical between the two halves; its equality test
  enforces that
- Engine source is GPL-2.0-or-later on every platform (CON-010)
- v1 is CUDA-only, so there is no non-NVIDIA Windows build to consider

### Success Looks Like

A Windows user downloads one signed installer, runs it, sees no SmartScreen
warning, and the Tessera panel reports `Ready` without them configuring
anything.

---

## Context & References

### Key Documents

| Document | Location | Why Relevant |
|----------|----------|--------------|
| Local inference engine | `specs/tessera/feature-spec/active/SPEC-TS-0023-local-inference-engine.md` | FR-030 defers Windows here; FR-031/FR-032 define the paths |
| Premise verification | `specs/tessera/adr/ADR-0001-premise-verification.md` | Why the build matrix is per GPU architecture |
| Linux packaging | `packaging/linux/README.md` | The procedure to mirror |

### Key Code to Review

| File | Purpose |
|------|---------|
| `packaging/linux/build_engine_installer.sh` | The build to port, including the toolchain gate |
| `packaging/linux/install.sh` | Marker contents and per-user install shape |
| `tessera/engine/discovery.py` | Already resolves the Windows paths this must write |
| `tessera_engine/runtime.py` | Descriptor writing and the `0o600` assumption to re-check |

### Dependencies

| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| Code-signing identity | Not acquired | Blocks this | Retry Azure Trusted Signing; fall back to an EV certificate |
| TASK-TS-0026 (TRELLIS adapter) | Not started | Blocks a *useful* artifact | An installer with no adapters installs nothing worth running |
| TASK-TS-0028 (release pipeline) | Not started | Shares the delivery problem | Coordinate — the size question is platform-independent |

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

1. **Installer format — MSI or a signed self-extracting executable?**
   - **Suggested resolution:** MSI is more familiar on IT-managed machines; an
     exe is simpler to produce. Discuss with Deputy.
2. **Per-user or per-machine install?**
   - **Suggested resolution:** Per-user, matching Linux. It avoids a UAC prompt,
     at the cost of a multi-gigabyte payload in the user profile.
3. **Is the Azure web-interface failure an eligibility rejection or a bug?**
   - **Suggested resolution:** Unknown. Escalate through Azure support before
     spending on an EV certificate.

### For Engineer to Add
> Space to add questions before starting the Spec:

1. _[Add questions here after reviewing the task]_

---

## Escalation

| Need | Contact | Channel |
|------|---------|---------|
| Technical questions | TBD | DM |
| Business/Requirements | Derek | DM |
| Blocked | — | #blocked |

---

## Engineer Acknowledgment

> **Complete this section within 24 hours of assignment.**

| Item | Status |
|------|--------|
| Task reviewed and understood | ☐ |
| Questions added above (if any) | ☐ |
| Questions resolved with CSO | ☐ |
| Ready to begin Spec | ☐ |

**Acknowledged Date:** [Date]
**Target Spec Submission:** [Date]

---

**Tracking:** Tasks are managed in Jira. This file structures the assignment.
