# Feature Specification: Marketplace Strategy & Multi-Channel Publication

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0015 |
| **Task ID** | TASK-TS-0015 |
| **Status** | Draft |
| **Version** | 1.0 |
| **Created** | 2026-04-17 |
| **Last Updated** | 2026-04-17 |
| **Author** | Orchestrator (AI) |
| **Pod** | Tessera |
| **CSO Approver** | Derek |
| **Spec Type** | Feature |

### Status Transitions
| From | To | Trigger |
|------|----|---------| 
| Draft | In Review | Author submits, AI-Readiness ≥80 |
| In Review | Approved | CSO approves |
| In Review | Draft | CSO requests changes |
| Approved | In Progress | Orchestrator begins implementation |
| In Progress | Complete | PR merged |

---

## 1. PROBLEM STATEMENT

### 1.1 Business Context
Tessera's CI/CD pipeline (SPEC-TS-0014) produces versioned `.zip` artifacts on every merge to `main`, and the documentation site (SPEC-TS-0013) is published at `https://expansive-labs-llc.github.io/tessera/`. However, the add-on is not yet available on any marketplace where Blender users discover, evaluate, and install add-ons. Without marketplace presence, Tessera remains invisible to its target audience — hobbyist makers, product designers, educators, and students (PRD §4 US-01 through US-04) who search for "AI 3D print" or "image to 3D" on marketplace platforms.

The dual distribution model (open-source + paid marketplaces) is a proven strategy in the Blender ecosystem. The add-on source code is freely available on GitHub (GPL-2.0-or-later, as mandated by Blender's add-on distribution policy and PRD decision D6). Marketplace listings sell **convenience** — pre-built `.zip` packages, one-click install, automatic update notifications, and seller support. This is NOT exclusive access to the code; it is a packaging and support service.

A critical constraint is the **Blender Extensions Platform**, which is free-only and prohibits commercial advertising, links to paid versions, or any mention of paid alternatives within the listing or the Blender UI. Tessera can be listed there for free distribution alongside separate paid listings on Gumroad and BlenderMarket. These channels operate independently and must not cross-reference each other in ways that violate platform policies.

This spec defines the complete set of marketplace listing assets, platform account configurations, pricing strategy, and version update procedures needed to publish Tessera across all four distribution channels.

### 1.2 User Story
**As a** Blender user who doesn't want to build from source,  
**I want** to purchase and install Tessera with one click from a marketplace,  
**So that** I get a tested, ready-to-use version with update support.

### 1.3 Proposed Approach
Create a multi-channel publication strategy with four distribution tiers: (1) **GitHub Releases** as the source of truth for versioned artifacts (already delivered by SPEC-TS-0014), (2) **Blender Extensions Platform** for free distribution to the widest Blender audience, (3) **Gumroad** as the primary paid channel with lower commission, and (4) **BlenderMarket** as the secondary paid channel for discoverability in the Blender community. Produce a complete set of listing assets — product copy, annotated screenshots (≥ 5), hero banner, and FAQ — adapted for each platform's requirements. Document the version update runbook for each marketplace so that post-CI release uploads are repeatable and deterministic. All listing assets and runbooks SHALL be committed to a `marketplace/` directory in the repository for version control and team access.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Marketplace presence | 0 platforms | 4 platforms (GitHub Releases, Extensions Platform, Gumroad, BlenderMarket) | Active listing on each platform |
| Blender Extensions Platform listing status | Not listed | Listed and approved by moderation | Extensions Platform listing page loads |
| Gumroad product page status | Not created | Active product page with pricing | Gumroad product URL loads |
| BlenderMarket listing status | Not applied | Seller approved + product listed | BlenderMarket product URL loads |

---

## 2. TECHNICAL CONTEXT

> ⚠️ **AI needs this context BEFORE generating code.** Provide patterns and references here.

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/__init__.py` L43-53 | `bl_info` dict — name, description, version, category | Product copy: official name, tagline, category keywords |
| `blender_manifest.toml` | Blender Extensions Platform manifest (SPEC-TS-0014 FR-035–FR-040): `id`, `tagline`, `maintainer`, `permissions`, `license` | Extensions Platform listing metadata must be consistent with manifest values |
| `PRD-001_Tessera.md` §1–§4 | Executive Summary, Problem Statement, Goals, User Stories | Product description copy, feature list, value proposition |
| `PRD-001_Tessera.md` §8 | Technology Stack — GPL v2+, local GPU inference, Blender 4.x+ | System requirements, license disclosure, privacy messaging |
| `PRD-001_Tessera.md` Appendix A | Competitive Landscape — Tripo, Meshy, Neural4D, OpenSCAD, Blender manual | Differentiation messaging for marketplace listings |
| `specs/tessera/feature-spec/active/SPEC-TS-0012-repo-foundation.md` FR-039 | `.github/FUNDING.yml` with placeholder marketplace URLs | Update FUNDING.yml with actual URLs once listings are live |
| `specs/tessera/feature-spec/active/SPEC-TS-0013-user-manual.md` | Documentation site at `https://expansive-labs-llc.github.io/tessera/` | Listings link to documentation |
| `specs/tessera/feature-spec/active/SPEC-TS-0014-ci-release-pipeline.md` | CI/CD produces `tessera-v<VERSION>.zip` attached to GitHub Releases; `blender_manifest.toml` at zip root | Marketplace uploads use the GitHub Release `.zip` artifact directly |
| `SPEC-TS-0014` FR-029 | `.zip` archive structure: `blender_manifest.toml` + `LICENSE` at root, `tessera/` subdirectory | Extensions Platform requires `blender_manifest.toml` at zip root; paid marketplaces accept any valid `.zip` |

### 2.2 Tech Stack & Standards
- **Distribution platforms:** GitHub Releases, Blender Extensions Platform, Gumroad, BlenderMarket
- **Asset formats:** Markdown (product copy), PNG (screenshots, 1920×1080 minimum), PNG/SVG (hero banner, 1920×600 minimum)
- **Manifest:** `blender_manifest.toml` (Blender Extensions Platform), Gumroad product settings (web UI), BlenderMarket product submission (web UI)
- **License:** GPL-2.0-or-later (code) — marketplace listings sell convenience packaging, not exclusive access
- **Version control:** All listing assets committed to `marketplace/` directory in repository

### 2.3 Architecture Notes
This spec produces **documentation assets, product copy, and operational runbooks** — no changes to the add-on's Python code or CI/CD pipeline. The only repository modification is the addition of a `marketplace/` directory containing listing assets and update runbooks. The `.github/FUNDING.yml` shall be updated with actual marketplace URLs once listings go live (replacing placeholders from SPEC-TS-0012 FR-039).

**Distribution channel architecture:**
```
GitHub Releases (source of truth)
  ├── tessera-v<VERSION>.zip
  │   ├── blender_manifest.toml
  │   ├── LICENSE
  │   └── tessera/
  │
  ├─→ Blender Extensions Platform (free)
  │   └── Upload same .zip — moderation review
  │
  ├─→ Gumroad (paid, primary)
  │   └── Upload same .zip — digital product delivery
  │
  └─→ BlenderMarket (paid, secondary)
      └── Upload same .zip — seller review
```

**Key architectural decisions:**

1. **Single `.zip` artifact for all channels:** The same `tessera-v<VERSION>.zip` produced by CI (SPEC-TS-0014 FR-029) is uploaded to every marketplace. No platform-specific builds are required. The Extensions Platform requires `blender_manifest.toml` at the zip root (already satisfied). Gumroad and BlenderMarket accept any valid `.zip`.

2. **Gumroad as primary paid channel over BlenderMarket:** Lower commission (10% + processing vs. 25–30%), no approval process, direct audience building via email list. BlenderMarket provides community-driven discovery but at higher cost.

3. **No cross-referencing between free and paid listings:** The Blender Extensions Platform prohibits links to paid versions. The Extensions Platform listing, the `blender_manifest.toml`, and any UI elements within the add-on SHALL NOT reference paid marketplace URLs. Paid channels may link to the free GitHub repository and documentation site.

4. **Pricing: $19 launch / $14 introductory (30 days) — pending CSO confirmation:** Competing AI Blender add-ons sell for $15–$49. GPL means free is always available from source. Low pricing ($5–$10) signals lower quality in a niche market. Commission math favors higher price point: at $19, Gumroad nets ~$17; at $5, Gumroad nets ~$4.50.

**File tree produced by this spec:**
```
marketplace/
├── copy/
│   ├── product-description.md         # Full product description (source of truth)
│   ├── feature-list.md                # Structured feature list for all platforms
│   ├── faq.md                         # Marketplace FAQ (GPL, requirements, support)
│   ├── changelog-template.md          # Template for version update notes
│   └── platform-adaptations/
│       ├── extensions-platform.md     # Blender Extensions Platform listing copy
│       ├── gumroad.md                 # Gumroad product page copy
│       └── blendermarket.md           # BlenderMarket product page copy
├── assets/
│   ├── screenshots/
│   │   ├── README.md                  # Screenshot manifest with capture instructions
│   │   ├── 01-image-upload.png        # [PLACEHOLDER — capture from running add-on]
│   │   ├── 02-reconstruction.png      # [PLACEHOLDER]
│   │   ├── 03-mesh-cleanup.png        # [PLACEHOLDER]
│   │   ├── 04-validation.png          # [PLACEHOLDER]
│   │   └── 05-export.png              # [PLACEHOLDER]
│   └── hero-banner.png               # [PLACEHOLDER — product key art]
├── pricing/
│   └── pricing-strategy.md            # Pricing analysis and decision rationale
└── runbooks/
    ├── extensions-platform-upload.md  # Step-by-step upload for Blender Extensions
    ├── gumroad-upload.md              # Step-by-step upload for Gumroad
    ├── blendermarket-upload.md        # Step-by-step upload for BlenderMarket
    └── release-checklist.md           # Unified post-release checklist for all channels
```

---

## 3. FUNCTIONAL REQUIREMENTS

> ⚠️ **Use precise language:** SHALL (required), SHALL NOT (prohibited), SHOULD (recommended), SHOULD NOT (discouraged), MAY (optional). The keyword IS the priority.

### 3.1 Product Copy — Source of Truth (FR-001 – FR-008)

| ID | Requirement |
|----|-------------|
| FR-001 | A `marketplace/copy/product-description.md` file SHALL be created containing the canonical product description used across all marketplace listings. The description SHALL include: (a) a title: "Tessera — AI-Powered Image-to-3D for Blender", (b) a tagline ≤ 80 characters: "Turn reference photos into print-ready 3D models, entirely within Blender", (c) a 150–250 word body paragraph sourced from PRD §1 Executive Summary and §2 Problem Statement, describing the problem (skill barrier, time cost, quality gap) and the solution (local GPU inference, print-ready output, no cloud dependencies). |
| FR-002 | The product description SHALL include a "Key Features" section with ≥ 10 bullet points covering: (1) AI-powered single-image and multi-view 3D reconstruction, (2) sketch-to-3D pathway for hand-drawn input, (3) automatic mesh cleanup and topology optimization, (4) print-readiness validation (manifold, watertight, wall thickness, overhang), (5) STL / OBJ / 3MF export with real-world mm scaling, (6) natural-language refinement ("make the base thicker"), (7) smart print orientation (minimize supports), (8) multiple reconstruction adapters (TripoSR, InstantMesh, CRM), (9) 100% local GPU inference — no cloud, no API keys, no data leaves your machine, (10) built-in printer profiles (Ender 3, Prusa MK4, Bambu Lab P1S, Elegoo Mars 3, and more). |
| FR-003 | The product description SHALL include a "System Requirements" section specifying: (a) Blender ≥ 4.2 LTS, (b) NVIDIA GPU with CUDA support or Apple Silicon with MPS backend, (c) minimum 8 GB VRAM (12 GB recommended for all features), (d) minimum 16 GB system RAM, (e) 5 GB disk space for AI model weights (downloaded on first use), (f) Windows 10+, macOS 13+ (Apple Silicon), or Linux. |
| FR-004 | The product description SHALL include a "What You Get" section clearly communicating the marketplace value proposition: (a) pre-built, tested `.zip` — install in one click, (b) update notifications when new versions are released, (c) seller email support for installation and usage questions, (d) a note that the source code is available on GitHub under GPL-2.0-or-later for users who prefer to build from source. This section SHALL NOT misrepresent the product as exclusive or closed-source. |
| FR-005 | A `marketplace/copy/feature-list.md` file SHALL be created containing a structured feature list organized by workflow stage: (1) Image Input (formats, view labels, auto-detection), (2) 3D Reconstruction (single-image, multi-view, sketch, adapter selection), (3) Mesh Processing (cleanup, remesh, decimation, topology optimization), (4) Validation (manifold, watertight, wall thickness, overhang, build volume), (5) Refinement (natural-language commands, undo/redo, version history), (6) Export (STL, OBJ, 3MF, printer profiles, force-export). |
| FR-006 | A `marketplace/copy/faq.md` file SHALL be created containing ≥ 8 frequently asked questions with answers tailored for marketplace buyers: (a) "Is Tessera open source?" — Yes, GPL-2.0-or-later. Your purchase supports development and gives you a ready-to-install package with update notifications. (b) "What GPU do I need?" — NVIDIA CUDA with ≥ 8 GB VRAM or Apple Silicon. (c) "Does Tessera send my data to the cloud?" — No. All AI inference runs locally on your GPU. (d) "What Blender versions are supported?" — Blender 4.2 LTS and newer. (e) "How do I get updates?" — [Platform-specific instructions]. (f) "Can I use Tessera commercially?" — Yes, under GPL-2.0-or-later terms. (g) "What if it doesn't work on my machine?" — Contact seller support; system requirements listed above. (h) "How is this different from Tripo/Meshy?" — Tessera runs locally, produces print-validated manifold meshes, and integrates directly into Blender. |
| FR-007 | A `marketplace/copy/changelog-template.md` file SHALL be created providing a template for version update notes posted to each marketplace. The template SHALL include sections: Version Number, Release Date, What's New (features), Bug Fixes, Breaking Changes (if any), Update Instructions. |
| FR-008 | Platform-specific adaptation files SHALL be created in `marketplace/copy/platform-adaptations/`: (a) `extensions-platform.md` — adapted for Blender Extensions Platform constraints (free-only, no commercial references, ≤ 64 character tagline matching `blender_manifest.toml`), (b) `gumroad.md` — adapted for Gumroad product page (includes price, purchase CTA, support email), (c) `blendermarket.md` — adapted for BlenderMarket product submission format (includes seller bio section, category tags, compatibility matrix). |

### 3.2 Listing Assets — Screenshots & Banner (FR-009 – FR-015)

| ID | Requirement |
|----|-------------|
| FR-009 | A `marketplace/assets/screenshots/README.md` file SHALL be created as a screenshot manifest listing every required screenshot with: (a) filename, (b) description, (c) capture instructions (which panel to open, what state to set up, Blender viewport at 1920×1080, using Blender's default dark theme). |
| FR-010 | The screenshot manifest SHALL define ≥ 5 annotated screenshots: (1) `01-image-upload.png` — Image Input panel with 3+ reference images loaded and view labels assigned, (2) `02-reconstruction.png` — Generation panel showing reconstruction in progress with progress bar visible, (3) `03-mesh-cleanup.png` — Mesh Cleanup panel showing topology controls and cleanup diagnostics, (4) `04-validation.png` — Print Validation results panel showing pass/fail checks (manifold ✅, watertight ✅, wall thickness ✅, overhang ⚠️), (5) `05-export.png` — Export panel with STL/3MF output format selected and printer profile dropdown visible. |
| FR-011 | Each screenshot capture instruction SHALL specify: (a) exact Blender window size (1920×1080), (b) viewport layout (default, with sidebar open), (c) the Tessera panel tab to select, (d) dummy data to load (e.g., "load 3 images of a mug from `tests/` directory"), (e) annotation overlays to add (callout arrows pointing to key UI elements with labels). |
| FR-012 | The screenshot manifest SHALL define ≥ 2 additional optional screenshots: (6) `06-refinement-chat.png` — NL Refinement chat panel with example conversation, (7) `07-scaling-panel.png` — Scaling & Orientation panel with dimension inputs. |
| FR-013 | A `marketplace/assets/hero-banner.png` entry SHALL be defined in the manifest with capture/creation instructions: (a) composite image showing the Tessera workflow (input images → 3D model → printed object), (b) minimum resolution 1920×600, (c) includes the Tessera name and tagline as text overlay, (d) dark background consistent with Blender's theme. |
| FR-014 | All screenshot placeholders SHALL be committed as 1×1 pixel transparent PNGs with the correct filename so that the `marketplace/assets/screenshots/` directory structure exists in the repository. Actual screenshots SHALL be captured from a running Blender instance with Tessera installed and replace the placeholders in a follow-up commit. |
| FR-015 | Annotations on screenshots SHOULD be added using a simple image editor (GIMP, Figma, or equivalent) with: (a) arrows pointing to key UI elements, (b) label text in a sans-serif font (≥ 14pt), (c) a semi-transparent dark background behind label text for readability, (d) consistent annotation color (#FFD700 gold on dark Blender UI). |

### 3.3 Blender Extensions Platform Listing (FR-016 – FR-021)

| ID | Requirement |
|----|-------------|
| FR-016 | The `marketplace/copy/platform-adaptations/extensions-platform.md` SHALL contain the complete listing copy for the Blender Extensions Platform, including: (a) name: "Tessera" (matching `blender_manifest.toml` `name` field), (b) tagline ≤ 64 characters: "AI-powered 3D-printable model generation from reference images" (matching `blender_manifest.toml` `tagline` field), (c) description body adapted from the canonical product description (FR-001) with all commercial references and pricing removed. |
| FR-017 | The Extensions Platform listing copy SHALL NOT contain: (a) links to Gumroad, BlenderMarket, or any paid marketplace, (b) pricing information or purchase calls-to-action, (c) references to "premium", "pro", "paid version", or any language implying a commercial tier, (d) links to the `.github/FUNDING.yml` or GitHub Sponsors. The listing SHALL be purely informational about the add-on's features, documentation, and open-source repository. |
| FR-018 | The Extensions Platform listing copy SHALL include: (a) a link to the documentation site (`https://expansive-labs-llc.github.io/tessera/`), (b) a link to the GitHub repository (`https://github.com/Expansive-Labs-LLC/tessera`), (c) a link to the issue tracker for bug reports. |
| FR-019 | The `marketplace/runbooks/extensions-platform-upload.md` SHALL document the step-by-step upload process: (1) Log in with Blender ID at `extensions.blender.org`, (2) Navigate to "Submit Extension", (3) Upload the `tessera-v<VERSION>.zip` from the GitHub Release, (4) Verify the manifest auto-populates metadata fields, (5) Paste the listing description from the adaptation file, (6) Select category: "3D View", (7) Add tags: `ai`, `3d-printing`, `reconstruction`, `mesh`, (8) Submit for moderation review, (9) Expected moderation timeline: 1–5 business days. |
| FR-020 | The Extensions Platform upload runbook SHALL include a "Version Update" section documenting: (1) Navigate to the existing extension page, (2) Click "Upload New Version", (3) Upload the new `tessera-v<VERSION>.zip`, (4) Add version notes from the `CHANGELOG.md`, (5) Submit for re-review. |
| FR-021 | The Extensions Platform upload runbook SHALL include a "First-Time Setup" section documenting: (1) Create a Blender ID account at `id.blender.org` if not already registered, (2) Accept the Extensions Platform developer agreement, (3) Note: there is no approval process for developer accounts — extensions themselves go through moderation. |

### 3.4 Gumroad Product Setup (FR-022 – FR-028)

| ID | Requirement |
|----|-------------|
| FR-022 | The `marketplace/copy/platform-adaptations/gumroad.md` SHALL contain the complete Gumroad product page copy, including: (a) product name: "Tessera — AI Image-to-3D for Blender", (b) the canonical product description adapted for Gumroad (includes pricing, purchase CTA, support email), (c) the "What You Get" section (FR-004), (d) the FAQ (FR-006) with Gumroad-specific update instructions. |
| FR-023 | The Gumroad product page copy SHALL include a "License & Open Source" section stating: "Tessera is licensed under GPL-2.0-or-later. The source code is freely available on GitHub. Your purchase supports continued development and includes: a pre-built, tested package; update notifications; and email support. If you prefer to build from source, visit our GitHub repository." This section SHALL link to the GitHub repository URL. |
| FR-024 | The `marketplace/runbooks/gumroad-upload.md` SHALL document the step-by-step Gumroad product setup: (1) Create a Gumroad account at `gumroad.com`, (2) Navigate to "New Product" → "Digital Product", (3) Set product name, description, and cover image (hero banner), (4) Upload the `tessera-v<VERSION>.zip` as the deliverable file, (5) Set price (see pricing strategy FR-036), (6) Configure product settings: delivery method = "Direct download", content = "Single file", (7) Add product tags: `blender`, `3d-printing`, `ai`, `add-on`, (8) Upload screenshots to the product gallery, (9) Publish the product page. |
| FR-025 | The Gumroad upload runbook SHALL include a "Version Update" section documenting: (1) Navigate to the product dashboard, (2) Click "Edit" on the existing product, (3) Replace the deliverable file with the new `tessera-v<VERSION>.zip`, (4) Update the version number in the product description, (5) Post a product update (email notification to existing buyers) with the changelog, (6) Save and publish. |
| FR-026 | The Gumroad upload runbook SHALL include configuration for: (a) support email: `hello@expansivelabs.com`, (b) refund policy: "30-day no-questions-asked refund (note: source code is freely available on GitHub)", (c) cover image: `marketplace/assets/hero-banner.png`, (d) custom URL slug: `tessera-blender`. |
| FR-027 | The Gumroad product page SHALL be configured with an introductory launch discount. The pricing strategy (FR-036) SHALL define: (a) standard price, (b) introductory price, (c) introductory period duration, (d) discount code or Gumroad sale configuration. |
| FR-028 | The Gumroad product page copy SHALL include standard disclaimer: "System Requirements: Blender 4.2+, NVIDIA CUDA GPU with 8+ GB VRAM or Apple Silicon. This add-on requires local GPU compute and does not work on integrated graphics or CPU-only systems." |

### 3.5 BlenderMarket Product Setup (FR-029 – FR-034)

| ID | Requirement |
|----|-------------|
| FR-029 | The `marketplace/copy/platform-adaptations/blendermarket.md` SHALL contain the complete BlenderMarket product submission copy, including: (a) product name: "Tessera — AI Image-to-3D for Blender", (b) category: "Add-ons → Modeling", (c) Blender version compatibility: "4.2, 4.3, 4.4", (d) the canonical product description adapted for BlenderMarket format, (e) a seller bio section for the Expansive Labs LLC account. |
| FR-030 | The `marketplace/runbooks/blendermarket-upload.md` SHALL document the step-by-step BlenderMarket setup: (1) Apply for a seller account at `blendermarket.com/account/become-a-creator`, (2) Complete the seller application (company name, tax information, payment details), (3) Wait for seller approval (expected timeline: 3–10 business days), (4) Once approved: navigate to "New Product", (5) Fill in product metadata (name, category, Blender versions, license: GPL-2.0-or-later), (6) Upload the `tessera-v<VERSION>.zip` as the deliverable, (7) Upload screenshots and hero banner, (8) Paste the listing description from the adaptation file, (9) Set price (see pricing strategy FR-036), (10) Submit for product review, (11) Expected product review timeline: 3–5 business days. |
| FR-031 | The BlenderMarket upload runbook SHALL include a "Version Update" section documenting: (1) Navigate to the product management page, (2) Upload the new `tessera-v<VERSION>.zip`, (3) Update the "What's New" section with changelog content, (4) Update the Blender version compatibility if needed, (5) Save — product updates are live immediately (no re-review required for version bumps). |
| FR-032 | The BlenderMarket product submission SHALL include compatibility tags: (a) Operating Systems: Windows, macOS, Linux, (b) Blender Versions: 4.2+, (c) License: GPL-2.0-or-later. |
| FR-033 | The BlenderMarket listing copy SHALL include a "Requires GPU" notice using BlenderMarket's product requirements field to set correct buyer expectations. The notice SHALL state: "Requires NVIDIA CUDA or Apple Silicon GPU with ≥ 8 GB VRAM. Does not support AMD GPUs or integrated graphics in v1." |
| FR-034 | The BlenderMarket seller application runbook SHALL note that the approval process is NOT instant and SHALL recommend submitting the seller application ≥ 14 days before the planned listing launch date to account for review time. |

### 3.6 Pricing Strategy (FR-035 – FR-038)

| ID | Requirement |
|----|-------------|
| FR-035 | A `marketplace/pricing/pricing-strategy.md` file SHALL be created documenting the pricing analysis and decision rationale. The analysis SHALL include: (a) competitive pricing survey of ≥ 5 Blender AI/3D-printing add-ons on BlenderMarket with their prices, (b) GPL implications — source code is free; marketplace price is for convenience/support, (c) commission impact analysis showing net revenue per sale on Gumroad (10% + ~3% processing) and BlenderMarket (25–30%), (d) recommended price point with rationale. |
| FR-036 | The pricing strategy SHALL recommend a pricing structure — **pending CSO final confirmation**: (a) standard retail price: **$19 USD**, (b) introductory launch price: **$14 USD** for the first 30 days, (c) rationale: competing AI add-ons sell for $15–$49; $19 positions Tessera in the lower-mid range while signaling quality; introductory discount creates urgency for launch buyers, (d) net revenue per sale at $19: Gumroad ~$16.52 (after 10% + 2.9% + $0.30), BlenderMarket ~$13.30 (after 30%), (e) net revenue per sale at $14 (intro): Gumroad ~$12.10, BlenderMarket ~$9.80. |
| FR-037 | The pricing strategy SHALL explicitly state: "Price applies to Gumroad and BlenderMarket only. The Blender Extensions Platform listing is free. GitHub Releases are free. The GPL-2.0-or-later source code is freely available. Marketplace price is for the convenience package: pre-built install, update notifications, and seller support." |
| FR-038 | The pricing strategy SHALL include a "Future Pricing Considerations" section noting: (a) price may increase after v1.0 stable release based on feature completeness and market response, (b) no "free tier" on paid marketplaces — Blender Extensions Platform serves as the free channel, (c) bundle pricing MAY be considered if future add-ons are developed. |

### 3.7 Release Checklist & FUNDING.yml Update (FR-039 – FR-042)

| ID | Requirement |
|----|-------------|
| FR-039 | A `marketplace/runbooks/release-checklist.md` file SHALL be created providing a unified post-release checklist. For each new version released by CI, the maintainer SHALL follow these steps in order: (1) Verify GitHub Release was created by CI with correct tag and `.zip` asset, (2) Download the `tessera-v<VERSION>.zip` from the GitHub Release, (3) Upload to Blender Extensions Platform (if version change warrants it), (4) Upload to Gumroad and send buyer update notification, (5) Upload to BlenderMarket, (6) Update product descriptions on each platform if feature list changed, (7) Post release announcement to relevant channels (GitHub Discussions, social media). |
| FR-040 | The release checklist SHALL include time estimates for each step: Gumroad upload (~5 minutes), BlenderMarket upload (~5 minutes), Extensions Platform upload + moderation wait (~5 minutes upload + 1–5 business days review), total manual effort per release ~20 minutes excluding moderation wait. |
| FR-041 | The `.github/FUNDING.yml` SHALL be updated (replacing SPEC-TS-0012 FR-039 placeholders) with actual marketplace URLs once listings are live. The `custom` key SHALL contain the Gumroad product URL. The file SHALL NOT contain the Blender Extensions Platform URL (free listing, not a funding source). |
| FR-042 | The release checklist SHALL include a "Pre-Launch Checklist" section for the initial publication (one-time tasks): (1) ☐ Blender ID account created, (2) ☐ Gumroad account created and verified, (3) ☐ BlenderMarket seller application submitted (≥ 14 days before launch), (4) ☐ BlenderMarket seller application approved, (5) ☐ All screenshots captured and annotated, (6) ☐ Hero banner created, (7) ☐ Product descriptions finalized, (8) ☐ Pricing confirmed by CSO, (9) ☐ Documentation site live at `https://expansive-labs-llc.github.io/tessera/`, (10) ☐ GitHub Release exists with `.zip` artifact. |

### 3.8 Input Specifications

N/A — This spec produces marketplace listing assets, product copy, and operational runbooks. Inputs are the existing PRD, spec documents, and CI-built `.zip` artifacts.

### 3.9 Output Specifications

| Output | Type | Format | Location |
|--------|------|--------|----------|
| Canonical product description | Markdown | GFM with structured sections | `marketplace/copy/product-description.md` |
| Feature list | Markdown | Bulleted list by workflow stage | `marketplace/copy/feature-list.md` |
| Marketplace FAQ | Markdown | Q&A format | `marketplace/copy/faq.md` |
| Changelog template | Markdown | Template with placeholder sections | `marketplace/copy/changelog-template.md` |
| Extensions Platform copy | Markdown | Platform-adapted listing | `marketplace/copy/platform-adaptations/extensions-platform.md` |
| Gumroad copy | Markdown | Platform-adapted listing with pricing | `marketplace/copy/platform-adaptations/gumroad.md` |
| BlenderMarket copy | Markdown | Platform-adapted listing with seller bio | `marketplace/copy/platform-adaptations/blendermarket.md` |
| Screenshot manifest | Markdown | Filename + capture instructions | `marketplace/assets/screenshots/README.md` |
| Screenshot placeholders | PNG | 1×1 transparent PNG per screenshot slot | `marketplace/assets/screenshots/*.png` |
| Hero banner placeholder | PNG | 1×1 transparent PNG | `marketplace/assets/hero-banner.png` |
| Pricing strategy | Markdown | Analysis document | `marketplace/pricing/pricing-strategy.md` |
| Extensions Platform runbook | Markdown | Step-by-step procedure | `marketplace/runbooks/extensions-platform-upload.md` |
| Gumroad runbook | Markdown | Step-by-step procedure | `marketplace/runbooks/gumroad-upload.md` |
| BlenderMarket runbook | Markdown | Step-by-step procedure | `marketplace/runbooks/blendermarket-upload.md` |
| Release checklist | Markdown | Unified post-release procedure | `marketplace/runbooks/release-checklist.md` |
| FUNDING.yml update | YAML | GitHub funding config | `.github/FUNDING.yml` (updated with actual URLs) |

---

## 4. CONSTRAINTS

> ⚠️ **Critical for AI code generation.** These are hard prohibitions the AI must follow.

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT modify any Python source files, CI workflows, or build scripts. This spec produces only marketplace documentation and asset files. |
| CON-002 | SHALL NOT include links to paid marketplaces (Gumroad, BlenderMarket) in the Blender Extensions Platform listing copy, the `blender_manifest.toml`, or any UI element within the add-on. The Extensions Platform prohibits commercial advertising. |
| CON-003 | SHALL NOT misrepresent the product as closed-source or exclusive. All marketplace listings SHALL clearly state that the source code is available under GPL-2.0-or-later on GitHub. |
| CON-004 | SHALL NOT hardcode prices in platform-adapted listing copy until CSO confirms the pricing strategy. Price fields SHALL use `$[PRICE]` placeholder syntax until confirmed, with a CSO confirmation note. |
| CON-005 | SHALL NOT include personal email addresses, phone numbers, or private contact information. Support and business contact SHALL use `hello@expansivelabs.com`. |
| CON-006 | SHALL NOT fabricate feature descriptions or capabilities not implemented in SPEC-TS-0001 through SPEC-TS-0011. All feature claims SHALL be sourced from or consistent with existing specs and PRD. |
| CON-007 | SHALL NOT include actual screenshots in this spec's initial deliverables. Placeholder 1×1 PNGs SHALL be committed. Actual screenshots require a working Blender instance with Tessera installed and representative test data. |
| CON-008 | SHALL NOT reference internal project paths (`.agent/`, `specs/`, `tasks/`) in any marketplace-facing copy. These directories are development infrastructure, not user-facing content. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

> ⚠️ **All NFRs must be quantified.** Replace vague terms with specific numbers.

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Product description word count | Word count of `product-description.md` body (excluding headers) | 400–700 words | Measured via `wc -w` minus header lines |
| NFR-002 | Feature list completeness | Feature bullets in `feature-list.md` | ≥ 30 individual features across all workflow stages | Counted via bullet point lines |
| NFR-003 | FAQ coverage | Questions in `marketplace/copy/faq.md` | ≥ 8 questions with answers | Counted via `## ` headings |
| NFR-004 | Screenshot count | Required screenshots in manifest | ≥ 5 annotated screenshots + 1 hero banner | Counted via manifest entries |
| NFR-005 | Runbook step precision | Each runbook step | ≤ 3 sentences per numbered step | Manual audit of all runbook files |
| NFR-006 | Release checklist completion time | Time to execute full post-release update across all 3 non-GitHub channels | ≤ 20 minutes of manual effort (excluding Extensions Platform moderation wait) | Timed execution by maintainer |
| NFR-007 | Marketplace directory size | Total size of `marketplace/` directory | ≤ 2 MB (placeholder images + markdown) | Measured via `du -sh marketplace/` |
| NFR-008 | Cross-platform copy consistency | Feature claims across all 3 platform adaptation files vs. canonical description | 100% feature parity — no platform-specific feature claims that differ from canonical | Manual diff audit |

---

## 6. ACCEPTANCE CRITERIA

> ⚠️ **Minimum 3 criteria in Given-When-Then format.** These drive test implementation.

### AC-001: Canonical Product Description Covers All Major Features
**Given** the `marketplace/copy/product-description.md` exists with all sections defined in FR-001 through FR-004,  
**When** a reviewer compares the feature list against the implemented spec list (SPEC-TS-0001 through SPEC-TS-0011),  
**Then** (a) the description contains ≥ 10 feature bullet points, (b) every user-facing capability from the implemented specs has a corresponding mention, (c) the "System Requirements" section matches the values in `bl_info` and `blender_manifest.toml`, (d) the "What You Get" section explicitly states the GPL-2.0-or-later license and links to the GitHub repository.

### AC-002: Extensions Platform Copy Contains Zero Commercial References
**Given** the `marketplace/copy/platform-adaptations/extensions-platform.md` exists,  
**When** a reviewer searches the file for any of the following terms: "Gumroad", "BlenderMarket", "buy", "purchase", "price", "$", "paid", "premium", "pro version", "upgrade",  
**Then** zero matches are found, and the listing contains only feature descriptions, documentation links, and the GitHub repository URL.

### AC-003: Gumroad Copy Includes GPL Disclosure and Pricing
**Given** the `marketplace/copy/platform-adaptations/gumroad.md` exists,  
**When** a reviewer reads the product copy,  
**Then** (a) the copy includes the "License & Open Source" section from FR-023, (b) the copy includes a system requirements notice (FR-028), (c) a price field is present (using `$[PRICE]` placeholder or confirmed value), (d) the copy links to the documentation site and GitHub repository.

### AC-004: Screenshot Manifest Defines ≥ 5 Captures with Instructions
**Given** the `marketplace/assets/screenshots/README.md` exists,  
**When** a reviewer reads the manifest,  
**Then** (a) ≥ 5 screenshot entries are defined, (b) each entry includes a filename, description, and capture instructions, (c) capture instructions specify exact panel names, UI state, and window size (1920×1080), (d) 1×1 placeholder PNGs exist for each filename in the manifest.

### AC-005: Release Checklist Covers All Distribution Channels
**Given** the `marketplace/runbooks/release-checklist.md` exists,  
**When** a maintainer follows the checklist after CI creates a new GitHub Release,  
**Then** the checklist includes numbered steps for: (a) verifying the GitHub Release artifact, (b) uploading to Blender Extensions Platform, (c) uploading to Gumroad with buyer notification, (d) uploading to BlenderMarket, and includes time estimates totaling ≤ 20 minutes of manual effort.

### AC-006: Pricing Strategy Documents Commission Analysis
**Given** the `marketplace/pricing/pricing-strategy.md` exists,  
**When** a reviewer reads the pricing analysis,  
**Then** (a) ≥ 5 competitor prices are listed, (b) net revenue per sale is calculated for both Gumroad and BlenderMarket at the recommended price, (c) the introductory discount terms are defined, (d) the document explicitly states that Blender Extensions Platform and GitHub Releases are free.

### AC-007: Platform Runbooks Are Complete and Actionable
**Given** all three platform runbooks exist (`extensions-platform-upload.md`, `gumroad-upload.md`, `blendermarket-upload.md`),  
**When** a new team member reads each runbook without prior marketplace experience,  
**Then** (a) each runbook contains a first-time setup section and a version update section, (b) each numbered step is ≤ 3 sentences, (c) the BlenderMarket runbook notes the seller approval timeline (3–10 business days), (d) the Extensions Platform runbook notes the moderation timeline (1–5 business days).

---

## 7. EDGE CASES

> ⚠️ **Minimum 2 edge cases required.** Document non-obvious scenarios AI might miss.

### EC-001: Blender Extensions Platform Rejects Listing for Commercial Language
| Aspect | Detail |
|--------|--------|
| **Scenario** | The Extensions Platform moderator rejects the listing because the description or `blender_manifest.toml` contains indirect references to commercial offerings — e.g., "support our development" with a link that eventually leads to a paid marketplace, or the Tessera README (visible on GitHub and linked from the listing) contains marketplace links. |
| **Input Example** | Extensions Platform description includes: "Full documentation and support available at our website" where "our website" links to a page with Gumroad purchase buttons. |
| **Expected Behavior** | The Extensions Platform listing copy (FR-016–FR-018) SHALL contain only direct links to the documentation site (`https://expansive-labs-llc.github.io/tessera/`) and the GitHub repository. The documentation site itself MAY contain marketplace links (it's not hosted on the Extensions Platform), but the listing copy SHALL NOT link to pages whose primary purpose is selling. |
| **Test ID** | TS-001 |

### EC-002: BlenderMarket Seller Application Rejected or Delayed
| Aspect | Detail |
|--------|--------|
| **Scenario** | The BlenderMarket seller application is rejected (e.g., due to incomplete company information) or delayed beyond the planned launch date. Publication on the other three channels should not be blocked. |
| **Input Example** | Seller application submitted 7 days before planned launch; approval takes 12 days. |
| **Expected Behavior** | The release checklist (FR-039) SHALL treat each distribution channel independently. A delay or rejection on BlenderMarket SHALL NOT block publication on GitHub Releases, Blender Extensions Platform, or Gumroad. The checklist SHALL include a note: "If BlenderMarket approval is pending, proceed with other channels. Add BlenderMarket listing when approved." The BlenderMarket runbook (FR-034) SHALL recommend submitting the seller application ≥ 14 days before planned launch. |
| **Test ID** | TS-002 |

### EC-003: GPL Confusion — Buyer Requests Refund Because "It's Free on GitHub"
| Aspect | Detail |
|--------|--------|
| **Scenario** | A buyer discovers the source code on GitHub after purchasing on Gumroad or BlenderMarket and requests a refund, arguing the product was misrepresented. |
| **Input Example** | Buyer email: "I found this is open source on GitHub. Why did I pay $19 for it?" |
| **Expected Behavior** | The Gumroad and BlenderMarket listings SHALL preemptively address this by including the "License & Open Source" section (FR-023) and the "What You Get" section (FR-004) which clearly states: the source code is GPL-2.0-or-later on GitHub; the marketplace purchase is for the convenience package (pre-built install, updates, support). The refund policy (FR-026) SHALL offer a 30-day refund to handle any remaining dissatisfaction. This is standard practice for GPL Blender add-ons. |
| **Test ID** | TS-003 |

### EC-004: CI Produces a Pre-release or Development Version
| Aspect | Detail |
|--------|--------|
| **Scenario** | The CI pipeline produces a version tagged as a pre-release (e.g., `v1.0.0-beta.1`) via semantic-release branch configuration. Pre-release versions should NOT be uploaded to marketplaces. |
| **Input Example** | GitHub Release tagged `v1.0.0-beta.1` with `prerelease: true` flag. |
| **Expected Behavior** | The release checklist (FR-039) SHALL include a verification step: "Confirm the GitHub Release is NOT marked as a pre-release. Pre-release versions (beta, alpha, rc) are for testing only and SHALL NOT be uploaded to any marketplace." |
| **Test ID** | TS-004 |

---

## 8. OUT OF SCOPE

> ⚠️ **Explicitly list what this feature does NOT include.** Prevents AI scope creep.

The following are explicitly **excluded** from this feature:

- ❌ Actual screenshot capture — placeholders only; screenshots require a running Blender instance with Tessera and representative test data
- ❌ Hero banner design/creation — placeholder only; requires graphic design work
- ❌ Demo video production — high-impact but requires screen recording, editing, and voiceover tooling
- ❌ Automated marketplace upload — all uploads are manual via web UI; API-based automation is a future enhancement
- ❌ Marketplace analytics dashboard — conversion tracking, download counts, and revenue tracking are native platform features
- ❌ Customer support infrastructure — email support uses existing `hello@expansivelabs.com`; no ticketing system setup
- ❌ Social media marketing plan — release announcements and content strategy are a separate concern
- ❌ Localized listings (non-English) — English only for v1
- ❌ Code signing of `.zip` artifacts — deferred to future hardening task
- ❌ Auto-update mechanism within the add-on — Blender Extensions Platform handles updates natively; paid channels rely on buyer re-download
- ❌ Affiliate or referral program setup — deferred
- ❌ A/B testing of listing copy or pricing — deferred to post-launch optimization
- ❌ Changes to the CI/CD pipeline (SPEC-TS-0014) — release artifacts are consumed as-is
- ❌ Changes to the documentation site (SPEC-TS-0013) — docs are linked, not modified
- ❌ Changes to the `blender_manifest.toml` or add-on Python code — consumed as-is from SPEC-TS-0014

---

## 9. SECURITY CONSIDERATIONS

> ⚠️ **Required for all features.** AI-generated code needs explicit security constraints.

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | Yes — marketplace accounts require authentication for product management |
| **Auth Method** | Platform-specific: Blender ID (Extensions Platform), Gumroad account, BlenderMarket seller account |
| **Required Permissions** | Product creation and management on each platform; no programmatic API access |
| **Rate Limiting** | N/A — manual web UI operations |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| Marketplace account credentials | Restricted (secret) | Stored in individual platform accounts; never committed to repository; never shared in Slack/email |
| Product listing copy | Public | No sensitive information; reviewed before publishing |
| Screenshot images | Public | Must NOT contain PII (usernames, personal file paths, private data in viewport) |
| Pricing information | Internal (until published) | Do not publish pricing decisions in public channels until listings are live |
| Seller tax/payment information | Restricted (PII) | Entered directly into BlenderMarket/Gumroad; never stored in repository |
| Support email address | Public | Project-specific address only (`hello@expansivelabs.com`) |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL NOT commit marketplace account credentials, API keys, or payment information to the repository. All sensitive data SHALL remain in individual platform accounts. |
| SEC-002 | SHALL NOT include personal file paths (e.g., `/home/derek/...`, `C:\Users\derek\...`) in any listing copy, screenshot, or runbook. Use generic paths when examples are needed. |
| SEC-003 | Screenshots SHALL NOT contain PII — no usernames, personal file paths, private Blender project data, or identifiable personal content visible in the viewport or file browser. |
| SEC-004 | The `.github/FUNDING.yml` SHALL contain only public marketplace URLs. It SHALL NOT contain internal URLs, staging links, or unpublished product pages. |
| SEC-005 | Runbooks SHALL NOT document password recovery procedures or link to credential change pages for marketplace accounts. Account security is the individual user's responsibility. |

---

## 10. API CONTRACT [CONDITIONAL]

> **Skip** — This spec produces marketplace listing assets and operational runbooks. No APIs are exposed or consumed programmatically.

---

## 11. OBSERVABILITY

> N/A — Marketplace listing assets are static files. Platform-native analytics (Gumroad sales dashboard, BlenderMarket download counts, Extensions Platform stats) provide observability. No custom monitoring is required.

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — marketplace assets are static files committed to repository |
| **Default State** | All files present in `marketplace/` directory after merge |
| **Rollout Plan** | Single PR with all listing assets; actual marketplace publication is a manual process following the runbooks |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| SPEC-TS-0012 (Repo Foundation) | Yes | README, LICENSE, FUNDING.yml must exist; public repository on GitHub |
| SPEC-TS-0013 (User Manual) | Yes | Documentation site must be live for listing links |
| SPEC-TS-0014 (CI/Release Pipeline) | Yes | Must produce versioned `.zip` release artifacts |
| BlenderMarket seller approval | Yes (for BlenderMarket only) | Application takes 3–10 business days; submit early |
| CSO pricing confirmation | Yes (for paid channels) | Pricing placeholders are used until confirmed |

### 12.3 Rollback Plan
1. Remove or unlist products from marketplaces via their respective admin dashboards (no permanent commitment)
2. Revert the PR that adds `marketplace/` directory to remove listing assets from repository
3. Leave GitHub Releases intact (they are unaffected by marketplace status)
4. Blender Extensions Platform listing can be unlisted or withdrawn via the developer dashboard

---

## 13. TEST SCENARIOS

> Map tests to acceptance criteria and edge cases for traceability.

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | Extensions Platform listing copy contains zero instances of: "Gumroad", "BlenderMarket", "buy", "purchase", "price", "$", "paid", "premium", "pro version", "upgrade" | Script | AC-002, FR-017, EC-001 | Must Pass |
| TS-002 | Release checklist treats channels independently; includes note about proceeding without BlenderMarket if approval pending | Manual | AC-005, EC-002 | Must Pass |
| TS-003 | Gumroad and BlenderMarket listings include "License & Open Source" section with GPL and GitHub links | Manual | AC-003, FR-023, EC-003 | Must Pass |
| TS-004 | Release checklist includes pre-release version verification step | Manual | EC-004, FR-039 | Must Pass |
| TS-005 | `product-description.md` contains ≥ 10 feature bullet points covering capabilities from SPEC-TS-0001–0011 | Script | AC-001, FR-002 | Must Pass |
| TS-006 | `product-description.md` system requirements match `bl_info["blender"]` = (4, 2, 0) and `blender_manifest.toml` `blender_version_min` | Manual | AC-001, FR-003 | Must Pass |
| TS-007 | `marketplace/copy/faq.md` contains ≥ 8 Q&A entries | Script | NFR-003, FR-006 | Must Pass |
| TS-008 | Screenshot manifest lists ≥ 5 entries with filenames and capture instructions | Script | AC-004, FR-010 | Must Pass |
| TS-009 | 1×1 placeholder PNG files exist for all screenshots listed in manifest | Script | FR-014 | Must Pass |
| TS-010 | `pricing-strategy.md` includes ≥ 5 competitor prices and net revenue calculations for Gumroad and BlenderMarket | Manual | AC-006, FR-035, FR-036 | Must Pass |
| TS-011 | Extensions Platform runbook includes first-time setup and version update sections | Manual | AC-007, FR-019, FR-020, FR-021 | Must Pass |
| TS-012 | Gumroad runbook includes first-time setup and version update sections | Manual | AC-007, FR-024, FR-025 | Must Pass |
| TS-013 | BlenderMarket runbook includes seller application timeline (≥ 14 days) and version update sections | Manual | AC-007, FR-030, FR-031, FR-034 | Must Pass |
| TS-014 | All three platform adaptation files exist and contain platform-specific content | Script | FR-008 | Must Pass |
| TS-015 | `release-checklist.md` includes time estimates ≤ 20 minutes total | Manual | NFR-006, FR-040 | Must Pass |
| TS-016 | `changelog-template.md` includes Version Number, What's New, Bug Fixes, Breaking Changes sections | Manual | FR-007 | Must Pass |
| TS-017 | No file in `marketplace/` contains personal paths (`/home/derek/`, `C:\Users\derek\`) | Script | SEC-002 | Must Pass |
| TS-018 | `marketplace/` directory total size ≤ 2 MB | Script | NFR-007 | Must Pass |
| TS-019 | Feature claims across all 3 platform adaptations are consistent with canonical `product-description.md` | Manual | NFR-008 | Must Pass |
| TS-020 | Pre-launch checklist includes ≥ 10 items covering all account, asset, and pricing prerequisites | Manual | FR-042 | Must Pass |

> **Note on "Script" tests:** Script-type tests (TS-001, TS-005, TS-007, TS-008, TS-009, TS-014, TS-017, TS-018) are one-off verification scripts run by the implementor during review. They do not need to be committed to the repository as part of the permanent test suite.

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0012 (Repo Foundation) — README, LICENSE, FUNDING.yml | Required | In Review | Tessera | Yes — must be merged before marketplace links work |
| SPEC-TS-0013 (User Manual) — Documentation site at GitHub Pages | Required | In Review | Tessera | Yes — listings link to docs site |
| SPEC-TS-0014 (CI/Release Pipeline) — Versioned `.zip` artifacts | Required | In Review | Tessera | Yes — marketplaces need the `.zip` to upload |
| `PRD-001_Tessera.md` §1–§4, §8, Appendix A | Content reference | Available | Derek | No — product copy sourced from PRD |
| SPEC-TS-0001 through SPEC-TS-0011 | Content reference | Complete / In Progress | Tessera | No — feature descriptions sourced from specs |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| Blender Extensions Platform | Required | [extensions.blender.org](https://extensions.blender.org/) | Proceed with other channels; defer Extensions Platform listing |
| Gumroad | Required | [gumroad.com](https://gumroad.com/) | Alternative: Itch.io, Payhip, or direct download with payment link |
| BlenderMarket | Optional | [blendermarket.com](https://blendermarket.com/) | Proceed without; add later when seller application approved |
| Blender ID | Required (for Extensions Platform) | [id.blender.org](https://id.blender.org/) | N/A — required for Extensions Platform developer access |

---

## 15. APPROVAL

| Role | Name | Date | Status |
|------|------|------|--------|
| Author (Orchestrator) | AI | 2026-04-17 | ☐ Submitted |
| CSO Approval | Derek | | ☐ Approved / ☐ Changes Requested |
| Deputy Review | | | ☐ N/A |

**Approval Notes:**

> ⚠️ **CSO Decision Required — Pricing:** The pricing strategy (FR-036) recommends $19 standard / $14 introductory (30 days). CSO initial preference was $5–$10. See `marketplace/pricing/pricing-strategy.md` for detailed rationale. Decision needed before paid listings go live.

---

## AI-READINESS SELF-SCORE

> **Score your Spec before submitting for CSO approval. Target: ≥80/100**

| Criterion | Max | Score | Guidance |
|-----------|-----|-------|----------|
| SHALL/SHOULD/MAY requirements | 20 | 20 | 42 requirements (FR-001 – FR-042) with precise SHALL/SHALL NOT/SHOULD/MAY language throughout |
| Quantified NFRs | 15 | 14 | 8 NFRs quantified with specific targets; NFR-001 uses word count range, NFR-006 uses time target; minor deduction for NFR-008 relying on manual diff audit |
| Given-When-Then criteria (3+) | 20 | 20 | 7 acceptance criteria in Given-When-Then format with specific search terms, counts, and verifiable outcomes |
| Edge cases (2+) | 15 | 15 | 4 edge cases with concrete scenarios: moderation rejection, seller delay, GPL refund, pre-release version |
| Out of scope defined | 10 | 10 | 15 explicit exclusions with cross-references to other tasks and rationale |
| Security constraints | 10 | 10 | 5 security requirements + data classification table addressing credentials, PII in screenshots, and pricing confidentiality |
| No ambiguous language | 10 | 9 | All ambiguous terms resolved; "representative test data" in FR-014 is slightly subjective but bounded by screenshot manifest instructions |
| **TOTAL** | **100** | **98** | **Target: ≥80 ✅** |

### Score Decision
| Score | Action |
|-------|--------|
| ≥80 | Submit for CSO review ✅ |

### Ambiguous Language Checklist
> Verify **NONE** of these words appear without specific definitions:

- [x] "appropriate" → not used
- [x] "properly" → not used
- [x] "correctly" → not used
- [x] "as expected" → not used
- [x] "handle gracefully" → not used
- [x] "fast" / "efficient" / "performant" → replaced with specific time targets (≤ 20 min, 3–10 business days)
- [x] "secure" → replaced with SEC-001 through SEC-005
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → not used

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-17 | Orchestrator (AI) | Initial draft |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0015-marketplace-publication.md`
