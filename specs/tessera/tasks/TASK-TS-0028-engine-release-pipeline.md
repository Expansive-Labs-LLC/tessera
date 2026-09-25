# Task: Engine Release Pipeline and Installer Delivery

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0028 |
| **Pod** | Tessera |
| **Assigned To** | TBD |
| **Assigned By** | Derek |
| **Assigned Date** | 2026-09-24 |
| **Assignment Method** | SPEC-TS-0023 implementation split |
| **Sprint/Iteration** | Phase 6 — Integration & Pre-Launch |

---

## Classification

| Priority | Size | Risk | Type | Source |
|----------|------|------|------|--------|
| 🟡 P1 | M | Med | Tech Debt | SPEC-TS-0023 |

---

## ⚠️ Special Instructions

> **Resolved 2026-09-24: trim, do not move off GitHub.** Measured on a real
> payload — 3.7 GiB gzipped untrimmed, 2.12 GiB after trimming build-time
> content and Triton and switching to `xz -9`, and **1.97 GiB once NCCL is
> stubbed. That is 29 MB of headroom, and TRELLIS is not in it yet.**
>
> Treat the margin as the live risk in this task. `packaging/linux/trim_payload.sh`
> and the build's size check exist, so an oversized artifact fails the build
> rather than the upload — but if TRELLIS pushes it over, splitting across
> assets comes back, and it changes the manifest and the add-on's download path.

---

## Business Context

### Why This Matters

The installer exists and builds locally, but nothing publishes it and nothing
fetches it. A user has no way to obtain the engine, which makes the add-on's
Install button unimplementable.

### Why Now

TASK-TS-0025 needs something to download. The size question also affects what
TASK-TS-0026 can put in the artifact, so leaving it unanswered risks building
something undeliverable.

### User Story

**As a** Tessera user prompted to install the engine,
**I want** the download to start, show progress and survive my connection
dropping,
**So that** a multi-gigabyte install is something I can actually complete.

### Master PRD Reference

- **PRD Section:** §8 Technology Stack, D10 (inference runtime delivery)
- **Strategic Goal:** G1 — a user can get to a mesh; G5 — installation stays
  within what a Blender artist will tolerate (ADR-0001 D2)

---

## Initial Requirements

> ⚠️ **Starting points only.** These expand into the full Spec.

### What Needs to Be Built

1. **Resolve artifact delivery (decide first)**
   - Decided: trim rather than move off GitHub. `trim_payload.sh` and the
     build's size check implement it; NFR-012 is now a 2 GiB ceiling
   - Re-measure once TRELLIS lands — current headroom is 29 MB

2. **CI build job**
   - Runner with a CUDA toolkit supporting every target compute capability
   - `CUDA_ARCH_LIST` honoured and recorded in `build-info.json`
   - Fails when the toolkit cannot target a listed architecture, as the local
     script already does

3. **Signing and publication (FR-042)**
   - Detached OpenPGP signature; key fingerprint published with the release
   - SHA256 recorded where the add-on's manifest can pin it

4. **Add-on download path (FR-041, NFR-013)**
   - Manifest entry with pinned URL and digest
   - Fetch through `DownloadManager` — resume, progress and retry are
     load-bearing at this size, not incidental
   - Verify the digest before handing the file to the OS; a mismatch deletes
     and reports, as SPEC-TS-0002 FR-007 does for weights

5. **Release runbook** in `packaging/linux/README.md`

### Known Constraints

- The add-on opens no network path of its own; everything goes through the
  existing download manager so SPEC-TS-0002 CON-001 keeps holding
- Signing key material never enters the repository or CI logs
- The add-on archive stays under 1 MB regardless of engine size (NFR-004)

### Success Looks Like

A user clicks Install Engine, watches a progress bar, loses their connection,
reconnects, and the download resumes and completes. The engine installs and
the panel reads `Ready`.

---

## Context & References

### Key Documents

| Document | Location | Why Relevant |
|----------|----------|--------------|
| Local inference engine | `specs/tessera/feature-spec/active/SPEC-TS-0023-local-inference-engine.md` | FR-041, FR-042, NFR-012, NFR-013 |
| Linux packaging | `packaging/linux/README.md` | The build and signing procedure to automate |
| CI/release pipeline | `specs/tessera/feature-spec/active/SPEC-TS-0014-ci-release-pipeline.md` | The existing release workflow this extends |

### Key Code to Review

| File | Purpose |
|------|---------|
| `packaging/linux/build_engine_installer.sh` | The build to run in CI |
| `packaging/linux/provision_toolchain.sh` | How CI gets a usable CUDA toolkit |
| `tessera/models/download_manager.py` | Resume, progress and retry already implemented |
| `tessera/models/manifest.json` | Where the pinned URL and digest belong |
| `.github/workflows/ci.yml` | Existing release job to extend |

### Dependencies

| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0026 (TRELLIS) | Not started | Decides the real artifact size | Coordinate — a build without adapters is not worth publishing |
| TASK-TS-0025 (add-on wiring) | Not started | Consumes this | Coordinate on the manifest shape |
| SPEC-TS-0002 amendment | Not started | Blocked by this | Download manager gains one non-weight artifact |
| SPEC-TS-0015 amendment | Not started | Blocked by this | Listing must describe the engine install |

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

1. **Does the artifact still fit once TRELLIS is in it?**
   - **Suggested resolution:** Unknown, and the headroom is 29 MB. Measure as
     soon as TASK-TS-0026 pins the extension set. If it does not fit, split
     across assets — hosting elsewhere was considered and rejected.
   - Levers already spent: build-time content, Triton, `xz -9`, the NCCL stub.
     Levers already ruled out: `nvprune` rejects linked shared libraries, and
     cuSPARSELt is called during torch initialisation so it cannot be stubbed.
2. **One artifact for all architectures, or one per generation?**
   - **Suggested resolution:** One fat artifact is simpler and larger; per
     generation is smaller and multiplies the build matrix. Measure before
     choosing.

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
