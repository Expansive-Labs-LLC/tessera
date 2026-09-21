# Task: Marketplace Strategy & Publication

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | TASK-TS-0015 |
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
| 🟡 P2 | L | Med | Feature | PRD |

**Size Guide:** S (≤4 hrs) • M (1-2 days) • L (3-5 days) • XL (>5 days → split it)  
**Risk Guide:** Low (well-understood) • Med (some unknowns) • High (significant uncertainty, spike recommended)

---

## ⚠️ Special Instructions

> **GPL-2.0+ and marketplace sales coexistence:** Tessera is GPL-licensed (required for Blender add-ons). The source code is freely available. Marketplace value is **convenience** — pre-built, one-click install, automatic updates, and seller support. The listing copy must clearly communicate this value prop without misrepresenting what buyers get.

> **Blender Extensions Platform is NOT a commercial marketplace.** It is free-only and prohibits links to paid versions. The add-on can be listed there for free alongside paid marketplace listings elsewhere, but cannot advertise paid versions from within the Blender UI or the Extensions Platform listing.

---

## Business Context

### Why This Matters
The dual distribution model (open-source + paid marketplaces) enables Tessera to reach the broadest audience while generating revenue to fund continued development. Marketplace buyers get convenience; open-source users get full access. This model is proven in the Blender ecosystem (many successful add-ons follow it).

### Why Now
After CI/CD produces reliable versioned releases (TASK-TS-0014), the next step is preparing marketplace listings. This must be done before launch to ensure a coordinated release across all channels.

### User Story
**As a** Blender user who doesn't want to build from source,  
**I want** to purchase and install Tessera with one click from a marketplace,  
**So that** I get a tested, ready-to-use version with update support.

### Master PRD Reference
- **PRD Section:** §8 Technology Stack (deployment model), §9 Phase 4 (M4.5)
- **Strategic Goal:** Revenue generation + broad distribution

---

## Initial Requirements

> ⚠️ **Starting points only.** Orchestrator will expand into full Spec.

### What Needs to Be Built

#### Marketplace Strategy Decision
1. **Recommended multi-channel approach:**

   | Platform | Purpose | Revenue Model | Commission | Effort |
   |----------|---------|---------------|------------|--------|
   | **GitHub Releases** | Free download (source of truth) | Free | 0% | Already done via TASK-TS-0014 |
   | **Blender Extensions Platform** | Free distribution (widest Blender reach) | Free only | 0% | Low — upload zip + manifest |
   | **Gumroad** | Primary paid channel | Paid ($X) | 10% + processing | Med — listing + assets |
   | **BlenderMarket** | Secondary paid channel (discovery) | Paid ($X) | 25-30% | Med — application + listing |

   Strategy rationale:
   - **Gumroad as primary paid** — Lower commission (10% vs 25-30%), no approval process, direct audience building
   - **BlenderMarket as secondary** — Worth the higher commission for the built-in Blender community traffic and discoverability
   - **Blender Extensions Platform** — Free tier builds awareness, some free users convert to paid for support/updates
   - **GitHub Releases** — Always available for source-builders; satisfies GPL obligation

#### Listing Assets
2. **Product copy** — Title, tagline, full description (adapted from PRD §1-§4), feature list, requirements, FAQ
3. **Screenshots** — Minimum 5 annotated screenshots:
   - Image upload panel with view labels
   - Reconstruction in progress (progress bar)
   - Mesh cleanup panel showing topology controls
   - Print validation results (pass/fail checks)
   - Export panel with STL/3MF output
4. **Hero banner image** — Product key art for marketplace header
5. **Demo video** (optional, high-impact) — 60-90 second screen recording: upload images → generate → validate → export
6. **Version update process** — Document how to upload new versions to each marketplace after CI produces a release

#### Platform-Specific Requirements
7. **Blender Extensions Platform** — `blender_manifest.toml` (from TASK-TS-0014), Blender ID account, moderation review
8. **Gumroad** — Account setup, product page, pricing, download delivery config
9. **BlenderMarket** — Seller application, product submission, review process
10. **Pricing strategy** — Research competitive pricing for Blender AI add-ons; consider introductory pricing

### Known Constraints
- GPL code is freely available — marketplace value is convenience, not exclusivity
- Blender Extensions Platform **prohibits** commercial advertising or links to paid versions in the listing or Blender UI
- BlenderMarket has an application/approval process (not instant)
- Screenshots require a working demo with representative output
- Demo video significantly increases conversion but requires screen recording tooling

### Success Looks Like
Tessera is listed on all target marketplaces with professional, consistent branding. A user searching for "AI 3D print" or "image to 3D" on BlenderMarket discovers Tessera. The listing clearly communicates the value proposition and links to documentation.

---

## Context & References

### Key Documents
| Document | Location | Why Relevant |
|----------|----------|--------------|
| Master PRD | `PRD-001_Tessera.md` | §1 Executive Summary, §2 Problem Statement — listing copy source |
| Competitive landscape | `PRD-001_Tessera.md` Appendix A | Differentiation messaging for listings |
| TASK-TS-0014 | `tasks/TASK-TS-0014-ci-release-pipeline.md` | Produces the `.zip` artifacts for upload |

### Dependencies
| Task/Item | Status | Dependency | Action |
|-----------|--------|------------|--------|
| TASK-TS-0012 (Repo Foundation) | Pending | Blocks this | README content informs listing copy |
| TASK-TS-0013 (User Manual) | Pending | Blocks this | Listings link to documentation |
| TASK-TS-0014 (CI/Release) | Pending | Blocks this | Must produce release artifacts first |

---

## Timeline

| Milestone | Target Date |
|-----------|-------------|
| **Spec Approved** | TBD |
| **Marketplace accounts created** | TBD |
| **Listing assets produced** | TBD |
| **Listings published** | TBD |
| **Target Complete** | TBD |

---

## Open Questions

### Flagged by CSO

1. What price point for marketplace listings?
   - **CSO initial preference:** $5-$10
   - **Recommendation:** $19 with a limited launch discount to $14 for first 30 days. Rationale: competing AI add-ons sell for $15-$49; GPL means free is always available from source; low pricing signals lower quality; commission math favors higher price in a niche market. **Decision pending — CSO to confirm.**
2. Should there be a free tier on Gumroad (pay-what-you-want with $0 minimum)?
   - **Suggested resolution:** No — use Blender Extensions Platform for free distribution; paid channels should have a floor price
3. When should the Blender Extensions Platform listing go live relative to paid listings?
   - **Suggested resolution:** Launch simultaneously — the Extensions Platform listing drives awareness, paid listings capture convenience buyers

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
