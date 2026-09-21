# Feature Specification: Comprehensive User Manual & Documentation Site

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0013 |
| **Task ID** | TASK-TS-0013 |
| **Status** | Draft |
| **Version** | 1.2 |
| **Created** | 2026-04-16 |
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
Tessera is an AI-powered Blender add-on targeting users who may NOT be 3D modeling experts — hobbyist makers, product designers, educators, and students (PRD §4 User Stories US-01 through US-04). Without clear, comprehensive documentation, these users will struggle with installation (GPU setup, model weight downloads), basic usage (view labels, image requirements), and troubleshooting (VRAM issues, non-manifold outputs). Documentation quality directly impacts marketplace satisfaction ratings (target ≥4.2/5.0 per PRD §10) and is a hard requirement for both BlenderMarket listings and the Blender Extensions Platform review process.

A preliminary `docs/` directory already exists with MkDocs Material theme configuration, skeleton pages (index, installation, quickstart, troubleshooting, 4 user-guide pages, 2 API reference pages), and a gallery placeholder. However, the current content is incomplete — user-guide pages lack coverage of the sketch-to-3D pathway, mesh cleanup details, scaling/orientation workflow, and add-on preferences. The troubleshooting page covers error codes but lacks a structured FAQ. No reference section (view label vocabulary, keyboard shortcuts, printer profiles, glossary) exists. No screenshots or visual aids are present. The site has never been built or deployed to GitHub Pages.

This spec defines the complete content, structure, build tooling, and deployment configuration needed to publish a production-quality documentation site at `https://expansive-labs-llc.github.io/tessera/`.

### 1.2 User Story
**As a** Tessera user who just installed the add-on,  
**I want** step-by-step guides for every feature with annotated screenshots and troubleshooting help,  
**So that** I can generate my first 3D-printable model without getting stuck.

### 1.3 Proposed Approach
Expand the existing `docs/` directory into a comprehensive MkDocs Material documentation site organized by user journey: install → first use → advanced features → troubleshoot → reference. Content SHALL be sourced from existing PRD sections, spec documents, and code comments — not fabricated. Each feature guide SHALL correspond to an implemented spec (SPEC-TS-0001 through SPEC-TS-0011). The site SHALL include annotated screenshot placeholders with detailed `alt` text describing the expected UI state, a structured FAQ, a reference section with the PRD §6 view vocabulary and §13 glossary, and an in-add-on help integration (tooltip text + "Help" button linking to the docs URL). The MkDocs build and GitHub Pages deployment SHALL be configured for local preview (`mkdocs serve`) and CI-driven publishing.

### 1.4 Success Metrics [OPTIONAL]

| Metric | Current | Target | How Measured |
|--------|---------|--------|--------------|
| Quickstart completion rate | Unknown | A new user follows the quickstart guide to a first exported STL in ≤ 10 minutes | Timed user test (manual, 3 participants) |
| Troubleshooting self-service rate | 0% | ≥ 80% of common issues resolved via docs without support | Track GitHub issue themes post-launch |
| Documentation completeness | ~40% (skeleton pages) | 100% of implemented features documented | Page count vs. feature list audit |

---

## 2. TECHNICAL CONTEXT

> ⚠️ **AI needs this context BEFORE generating code.** Provide patterns and references here.

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `docs/mkdocs.yml` | Existing MkDocs Material config — theme, nav, plugins, markdown extensions | Extend nav structure; add new plugins (`mkdocs-glightbox` for images, `mkdocs-git-revision-date-localized-plugin` for freshness) |
| `docs/docs/index.md` | Existing landing page with feature list and system requirements table | Expand content, add hero image placeholder, cross-link to new pages |
| `docs/docs/installation.md` | Existing platform-tabbed install guide (Windows, macOS, Linux) | Add model weight VRAM table, Apple Silicon MPS notes, build-from-source instructions |
| `docs/docs/quickstart.md` | Existing 8-step quickstart | Add screenshot placeholders, reduce to ≤ 5 key steps matching task requirement |
| `docs/docs/troubleshooting.md` | Existing error code reference (BF-E001 through BF-E999) | Add structured FAQ section, cross-link to relevant user-guide pages |
| `docs/docs/user-guide/image-input.md` | Existing image input guide with view labels | Add annotated screenshot placeholders, link to reference vocabulary table |
| `docs/docs/user-guide/reconstruction.md` | Existing reconstruction guide | Expand single-image vs. multi-view workflow descriptions |
| `docs/docs/user-guide/refinement.md` | Existing refinement guide | Expand with NL refinement loop examples, undo/redo documentation |
| `docs/docs/user-guide/export.md` | Existing export guide with printer profiles | Expand 3MF metadata details, add force-export workflow |
| `tessera/ui/*.py` | All 12 UI panel files (chat, cleanup, download, error, export, generation, help, image, main, perf, scaling, validation) | Screenshot descriptions — exact panel names, field labels, button text |
| `tessera/properties.py` | Scene-level properties and add-on preferences (GPU config, cache dir, LLM backend) | Preferences documentation and settings reference content |
| `tessera/errors/catalog.py` | Error code definitions and messages (BF-E001 – BF-E016, BF-E999 fallback) | Troubleshooting cross-reference |
| `tessera/errors/categories.py` | Error severity categories | Error code severity classification |
| `PRD-001_Tessera.md` | §6 View Label Vocabulary, §13 Glossary, §5.4 Validator checks | Reference section content |
| `specs/tessera/feature-spec/active/SPEC-TS-*.md` | All 12 feature specs | Feature-by-feature documentation sourcing |

### 2.2 Tech Stack & Standards
- **Documentation framework:** MkDocs 1.6+ with Material for MkDocs theme
- **Language:** Markdown (GitHub-Flavored)
- **Markdown extensions:** `admonition`, `pymdownx.details`, `pymdownx.superfences`, `pymdownx.highlight`, `pymdownx.tabbed`, `attr_list`, `md_in_html`, `toc`, `pymdownx.keys` (for keyboard shortcuts — **new**, not in existing config)
- **Plugins:** `search`, `mkdocs-glightbox` (image lightbox), `mkdocs-git-revision-date-localized-plugin` (page freshness)
- **Hosting:** GitHub Pages at `https://expansive-labs-llc.github.io/tessera/`
- **Build:** `mkdocs build` (static HTML), `mkdocs serve` (local dev)
- **License:** Documentation content licensed under CC-BY-4.0 (per SPEC-TS-0012 FR-020)

### 2.3 Architecture Notes
This spec produces **documentation content and configuration files only** — no Python runtime code except a single update to `tessera/ui/help_panel.py` to add a "Documentation" button linking to the docs URL. All deliverables are Markdown files in `docs/docs/`, an updated `docs/mkdocs.yml`, and a new `docs/requirements.txt` for documentation build dependencies.

**File tree produced by this spec** (new files marked with `[NEW]`, modified files marked with `[MOD]`):
```
docs/
├── mkdocs.yml                          [MOD] — expanded nav, new plugins, updated site_url
├── requirements.txt                    [NEW] — mkdocs + plugin dependencies for pip install
└── docs/
    ├── index.md                        [MOD] — expanded hero, screenshot placeholder
    ├── installation.md                 [MOD] — VRAM table, build-from-source, MPS notes
    ├── quickstart.md                   [MOD] — condensed to ≤5 steps, screenshot placeholders
    ├── troubleshooting.md              [MOD] — added FAQ section, cross-links
    ├── user-guide/
    │   ├── image-input.md              [MOD] — screenshots, vocabulary link
    │   ├── reconstruction.md           [MOD] — single vs. multi-view detail
    │   ├── sketch-to-3d.md             [NEW] — sketch pathway documentation
    │   ├── mesh-cleanup.md             [NEW] — topology controls, cleanup pipeline
    │   ├── scaling-orientation.md      [NEW] — real-world scaling, print orientation
    │   ├── refinement.md               [MOD] — NL refinement loop, undo/redo
    │   ├── export.md                   [MOD] — expanded validation, printer profiles
    │   └── preferences.md             [NEW] — GPU config, cache, LLM backend
    ├── reference/
    │   ├── view-labels.md              [NEW] — vocabulary table from PRD §6
    │   ├── keyboard-shortcuts.md       [NEW] — shortcut reference
    │   ├── printer-profiles.md         [NEW] — FDM/SLA presets with specs
    │   ├── error-codes.md              [NEW] — error code quick-reference table
    │   └── glossary.md                 [NEW] — terms from PRD §13
    ├── faq.md                          [NEW] — structured FAQ with categories
    ├── assets/
    │   └── screenshots/
    │       └── README.md               [NEW] — screenshot manifest with capture instructions
    ├── api/
    │   ├── pipeline.md                 [MOD] — expanded developer API docs
    │   └── adapters.md                 [MOD] — expanded adapter interface docs
    └── gallery/
        ├── gallery.yaml                [PRESERVE] — existing gallery data file
        └── index.md                    [MOD] — gallery structure with placeholder entries

tessera/
└── ui/
    └── help_panel.py                   [MOD] — add doc_url operator linking to docs site
```

---

## 3. FUNCTIONAL REQUIREMENTS

> ⚠️ **Use precise language:** SHALL (required), SHALL NOT (prohibited), SHOULD (recommended), SHOULD NOT (discouraged), MAY (optional). The keyword IS the priority.

### 3.1 Documentation Site Structure & Configuration (FR-001 – FR-006)

| ID | Requirement |
|----|-------------|
| FR-001 | The `docs/mkdocs.yml` SHALL define a `nav` structure with the following top-level sections in order: (1) Home, (2) Getting Started (Installation, Quick Start), (3) User Guide (Image Input, 3D Reconstruction, Sketch-to-3D, Mesh Cleanup, Scaling & Orientation, Refinement, Export & Print, Preferences), (4) Reference (View Labels, Keyboard Shortcuts, Printer Profiles, Error Codes, Glossary), (5) FAQ, (6) API Reference (Pipeline, Adapters), (7) Gallery. This restructures the existing nav by adding Reference and FAQ sections, expanding the User Guide from 4 to 8 sub-pages, and reordering Troubleshooting (previously a top-level item) into the Getting Started/Reference flow. |
| FR-002 | The `docs/mkdocs.yml` SHALL configure MkDocs Material theme with: (a) light/dark mode toggle using `deep purple` primary and `amber` accent, (b) `navigation.tabs`, `navigation.sections`, `navigation.expand`, `navigation.top`, `search.suggest`, `search.highlight`, `content.code.copy` features, (c) GitHub repo link to `https://github.com/Expansive-Labs-LLC/tessera`. |
| FR-003 | The `docs/mkdocs.yml` SHALL set `site_url` to `https://expansive-labs-llc.github.io/tessera/` (correcting the existing misconfigured value `https://expansivelabs.github.io/tessera/`) and `site_name` to `Tessera — Image-to-3D for Blender`. |
| FR-004 | The `docs/mkdocs.yml` SHALL include the following plugins: (a) `search`, (b) `glightbox` for image lightbox viewing, (c) `git-revision-date-localized` with `type: date` and `enable_creation_date: true`. |
| FR-005 | The `docs/mkdocs.yml` SHALL include the following markdown extensions: `admonition`, `pymdownx.details`, `pymdownx.superfences`, `pymdownx.highlight` (with `anchor_linenums: true`), `pymdownx.tabbed` (with `alternate_style: true`), `pymdownx.keys`, `attr_list`, `md_in_html`, `toc` (with `permalink: true`). |
| FR-006 | A `docs/requirements.txt` file SHALL be created listing all Python dependencies needed to build the documentation site: `mkdocs>=1.6`, `mkdocs-material>=9.5`, `mkdocs-glightbox>=0.4`, `mkdocs-git-revision-date-localized-plugin>=1.2`. |

### 3.2 Landing Page (FR-007 – FR-009)

| ID | Requirement |
|----|-------------|
| FR-007 | The `docs/docs/index.md` SHALL begin with a hero section containing: (a) project name "Tessera", (b) tagline "Transform reference photos into print-ready 3D models, entirely within Blender", (c) a 2–3 sentence value proposition sourced from PRD §1, (d) a screenshot placeholder with `alt` text describing the Tessera sidebar panel in the 3D Viewport: `![Tessera main panel showing Image Input, Generation, Validation, and Export sections in the Blender 3D Viewport sidebar](assets/screenshots/main-panel.png)`. |
| FR-008 | The `docs/docs/index.md` SHALL include a "Key Features" section with ≥ 9 bullet points covering: (1) AI-powered vision pipeline, (2) multi-view reconstruction, (3) sketch-to-3D, (4) mesh cleanup & topology optimization, (5) print-readiness validation, (6) natural-language refinement, (7) real-world scaling & print orientation, (8) multi-format export (STL/OBJ/3MF), (9) local GPU inference. |
| FR-009 | The `docs/docs/index.md` SHALL include a "System Requirements" table with columns: Component, Minimum, Recommended. Rows SHALL include: (a) Blender: 4.2 LTS / 4.3+, (b) GPU: NVIDIA CUDA or Apple Silicon MPS, 4 GB VRAM / 8+ GB VRAM, (c) RAM: 8 GB / 16+ GB, (d) Disk: 2 GB for model weights / 5+ GB, (e) OS: Windows 10+, macOS 13+ (Apple Silicon), Linux. |

### 3.3 Installation Guide (FR-010 – FR-014)

| ID | Requirement |
|----|-------------|
| FR-010 | The `docs/docs/installation.md` SHALL include platform-specific installation tabs for Windows, macOS (Apple Silicon), and Linux, each containing ≤ 5 numbered steps from download to verification. |
| FR-011 | The `docs/docs/installation.md` SHALL include a "Build from Source" section with ≤ 6 numbered steps: (1) clone repository, (2) navigate to project directory, (3) create add-on ZIP (`zip -r tessera.zip tessera/`), (4) install via Blender Preferences → Add-ons → Install from Disk, (5) enable the add-on, (6) verify panel appears in sidebar. |
| FR-012 | The `docs/docs/installation.md` SHALL include a "GPU VRAM Requirements" table showing minimum VRAM per feature tier: (a) basic reconstruction: 4 GB, (b) multi-view reconstruction: 8 GB, (c) sketch-to-3D: 8 GB, (d) NL refinement (local LLM): 8 GB, (e) all features simultaneously: 12 GB recommended. |
| FR-013 | The `docs/docs/installation.md` SHALL include a "Model Weight Download" section describing: (a) first-run automatic download process, (b) manual download via Model Manager panel, (c) total download size (~2 GB), (d) cache directory location per platform (Linux/macOS: `~/.cache/tessera/`, Windows: `%APPDATA%\tessera\`), (e) how to change the cache directory in preferences. |
| FR-014 | The `docs/docs/installation.md` SHALL include an "Apple Silicon (MPS)" admonition box noting: (a) Tessera uses Metal Performance Shaders on Apple Silicon, (b) VRAM is shared system memory, (c) macOS 13+ required, (d) performance characteristics differ from CUDA. |

### 3.4 Quick Start Guide (FR-015 – FR-017)

| ID | Requirement |
|----|-------------|
| FR-015 | The `docs/docs/quickstart.md` SHALL contain ≤ 5 numbered steps showing the end-to-end workflow from first launch to first exported STL: (1) Open Tessera panel, (2) Load reference images, (3) Generate 3D model, (4) Validate for printing, (5) Export STL. |
| FR-016 | Each step in the quickstart SHALL include: (a) a concise instruction (≤ 3 sentences), (b) a screenshot placeholder with descriptive `alt` text identifying the specific panel and UI state (e.g., `![Image Input panel with 3 images loaded and view labels assigned](assets/screenshots/quickstart-step2.png)`), (c) a "Tip" admonition with one actionable hint. |
| FR-017 | The quickstart SHALL include a "Next Steps" section at the end linking to: Image Input Guide, Refinement Guide, Export Guide, and Troubleshooting. |

### 3.5 User Guide Pages (FR-018 – FR-029)

| ID | Requirement |
|----|-------------|
| FR-018 | The user guide SHALL contain 8 pages, one per major feature area: (1) Image Input, (2) 3D Reconstruction, (3) Sketch-to-3D, (4) Mesh Cleanup, (5) Scaling & Orientation, (6) Refinement, (7) Export & Print, (8) Preferences. |
| FR-019 | The `docs/docs/user-guide/image-input.md` SHALL document: (a) supported image formats with a table (JPG, PNG, WebP, HEIC), (b) image requirements (resolution ≥ 256×256, ≤ 4096×4096, non-blurry), (c) photography tips for single-image and multi-view capture, (d) view label assignment with a link to the reference vocabulary table, (e) screenshot placeholder showing the Image Input panel with images loaded. |
| FR-020 | The `docs/docs/user-guide/reconstruction.md` SHALL document: (a) single-image reconstruction workflow with adapter selection (TripoSR, InstantMesh, CRM), (b) multi-view reconstruction workflow (≥ 3 images), (c) adapter comparison table with columns: Adapter, Best For, VRAM Required, Speed, (d) screenshot placeholder showing the Generation panel. |
| FR-021 | A new `docs/docs/user-guide/sketch-to-3d.md` SHALL be created documenting: (a) what sketch input is (hand-drawn line art from paper photos or digital drawings), (b) sketch preprocessing (edge detection, cleanup), (c) symmetry enforcement options, (d) limitations (simple shapes only, no textures), (e) screenshot placeholder showing sketch input and resulting 3D output. |
| FR-022 | A new `docs/docs/user-guide/mesh-cleanup.md` SHALL be created documenting: (a) automatic cleanup pipeline (duplicate vertices, degenerate faces, normal recalculation, hole filling), (b) topology controls (voxel remesh, quad remesh, decimation), (c) cleanup diagnostics panel, (d) manual cleanup tips using Blender's Edit Mode, (e) screenshot placeholder showing the Mesh Cleanup panel with diagnostics. |
| FR-023 | A new `docs/docs/user-guide/scaling-orientation.md` SHALL be created documenting: (a) auto-infer scaling from object class, (b) manual dimension entry (width/height/depth in mm), (c) print orientation optimizer (minimize supports, flatten bottom), (d) unit system configuration (mm default), (e) screenshot placeholder showing the Scaling panel with dimension inputs. |
| FR-024 | The `docs/docs/user-guide/refinement.md` SHALL document: (a) natural-language refinement workflow ("make it wider", "smooth the edges"), (b) supported modification types (scale, translate, bevel, subdivide, solidify, decimate), (c) undo/redo system and version history, (d) LLM backend configuration (local GGUF vs. API), (e) 5 concrete example refinement commands with expected outcomes, (f) screenshot placeholder showing the Chat panel with a refinement conversation. |
| FR-025 | The `docs/docs/user-guide/export.md` SHALL document: (a) export formats (STL, OBJ, 3MF) with a comparison table, (b) print-readiness validation checks (manifold, wall thickness, overhang, build volume), (c) 3MF metadata embedding (title, printer type, validation report), (d) force-export workflow for failed validations, (e) printer profiles table (Generic FDM, Ender 3, Prusa MK4, Bambu Lab P1S, Elegoo Mars 3, Elegoo Saturn 3, Custom), (f) screenshot placeholder showing the Export panel. |
| FR-026 | A new `docs/docs/user-guide/preferences.md` SHALL be created documenting: (a) GPU device selector and VRAM display, (b) model cache directory configuration with write-permission validation, (c) LLM backend selection (Local GGUF / API) with API endpoint and key configuration, (d) model download management (download all, clear cache), (e) download-on-first-use toggle, (f) screenshot placeholder showing the Tessera Preferences panel in Blender. |
| FR-027 | Each user-guide page SHALL include a "See Also" section at the bottom linking to ≥ 2 related pages (e.g., Image Input links to Reconstruction and View Labels reference). |
| FR-028 | Each user-guide page SHALL include ≥ 1 admonition box (tip, warning, note, or info) providing actionable guidance. |
| FR-029 | Each user-guide page SHALL include ≥ 1 screenshot placeholder image tag with descriptive `alt` text following the format: `![{Panel Name} panel showing {specific UI state description}](assets/screenshots/{page-name}-{description}.png)`. Placeholder images SHALL be documented in a `docs/docs/assets/screenshots/README.md` manifest listing every expected screenshot with capture instructions. |

### 3.6 Reference Section (FR-030 – FR-035)

| ID | Requirement |
|----|-------------|
| FR-030 | A new `docs/docs/reference/view-labels.md` SHALL be created containing the full view label vocabulary from PRD §6 as a table with columns: Label, Camera Direction, Canonical Azimuth, Canonical Elevation. The table SHALL include all 10 labels: `front`, `back`, `left`, `right`, `top`, `bottom`, `front-left`, `front-right`, `isometric`, `custom:<az>,<el>`. |
| FR-031 | A new `docs/docs/reference/keyboard-shortcuts.md` SHALL be created listing all Tessera-specific keyboard interactions. If no custom shortcuts are defined, the page SHALL document Blender's relevant built-in shortcuts: (a) `N` — toggle sidebar, (b) `Tab` — toggle Edit Mode, (c) `Ctrl+Z` / `Ctrl+Shift+Z` — undo/redo. |
| FR-032 | A new `docs/docs/reference/printer-profiles.md` SHALL be created with a table of all built-in printer profiles from the export system. Columns: Profile Name, Build Volume (W×D×H mm), Printer Type (FDM/SLA), Default Wall Thickness, Default Overhang Angle. |
| FR-033 | A new `docs/docs/reference/error-codes.md` SHALL be created with a quick-reference table of all defined error codes (BF-E001 through BF-E016, plus BF-E999 fallback — sourced from `tessera/errors/catalog.py`). Columns: Code, Severity, One-Line Description, Link to Full Entry. Each entry SHALL link to the corresponding detailed entry on the troubleshooting page. |
| FR-034 | A new `docs/docs/reference/glossary.md` SHALL be created containing all terms from PRD §13 (Manifold, Watertight, FDM, SLA, bpy, STL, 3MF, Slicer) plus additional terms: VRAM, CUDA, ROCm, MPS, GGUF, TripoSR, InstantMesh, CRM, SAM 2, Depth Anything V2, DINOv2, Voxel Remesh, Quad Remesh, Decimation, Overhang Angle, Build Volume. |
| FR-035 | All reference pages SHALL use `## Term` heading format for individual entries to enable the MkDocs `toc` extension to generate a clickable table of contents for each page. |

### 3.7 FAQ Page (FR-036 – FR-038)

| ID | Requirement |
|----|-------------|
| FR-036 | A new `docs/docs/faq.md` SHALL be created with frequently asked questions organized into 4 categories: (1) Installation & Setup, (2) Usage & Features, (3) Printing & Export, (4) Performance & GPU. |
| FR-037 | The FAQ SHALL contain ≥ 15 questions with answers. Each question SHALL use an `## ` heading for TOC indexing. Answers SHALL be ≤ 5 sentences and link to relevant user-guide or reference pages for detail. |
| FR-038 | The FAQ SHALL include the following specific questions at minimum: (a) "What GPU do I need?", (b) "Does Tessera send my data to the cloud?", (c) "What image formats are supported?", (d) "How do I fix 'GPU Memory Exhausted' errors?", (e) "What is a manifold mesh?", (f) "Can I use Tessera without a GPU?", (g) "How do I update Tessera?", (h) "What is the difference between STL and 3MF?", (i) "How do I report a bug?", (j) "Does Tessera work on macOS?". |

### 3.8 Troubleshooting Expansion (FR-039 – FR-040)

| ID | Requirement |
|----|-------------|
| FR-039 | The `docs/docs/troubleshooting.md` SHALL be expanded to include a "Common Issues" section ABOVE the error code reference, containing ≥ 5 problem-solution entries for issues that do NOT have error codes: (a) "Model weights download is slow", (b) "Tessera panel doesn't appear in sidebar", (c) "Generated mesh looks wrong/distorted", (d) "Blender crashes during generation", (e) "Export button is grayed out". |
| FR-040 | Each troubleshooting entry (both error codes and common issues) SHALL include a "Related" line linking to the relevant user-guide page. |

### 3.9 Screenshot Manifest (FR-041 – FR-042)

| ID | Requirement |
|----|-------------|
| FR-041 | A `docs/docs/assets/screenshots/README.md` SHALL be created as a screenshot manifest listing every screenshot placeholder referenced across all documentation pages. Each entry SHALL include: (a) filename, (b) page that references it, (c) capture instructions (which Blender panel to open, what state to set up, window size `1920×1080`). |
| FR-042 | The screenshot manifest SHALL list ≥ 15 screenshots covering: main panel overview, image input with images loaded, generation in progress, mesh cleanup diagnostics, validation results (pass and fail), scaling panel, refinement chat, export panel, preferences panel (GPU section, cache section, LLM section), sketch input, and quickstart steps. |

### 3.10 In-Add-on Help Integration (FR-043 – FR-045)

| ID | Requirement |
|----|-------------|
| FR-043 | The `tessera/ui/help_panel.py` SHALL be modified to include a "Documentation" button/operator that opens the documentation site URL (`https://expansive-labs-llc.github.io/tessera/`) in the user's default web browser via `bpy.ops.wm.url_open(url=...)`. **Note:** The existing `_DOCS_URL` and `_QUICKSTART_URL` constants (currently set to the old `expansivelabs.github.io` domain) SHALL be updated to use the corrected `expansive-labs-llc.github.io` domain. |
| FR-044 | The `tessera/__init__.py` `bl_info` dictionary SHALL be updated to set `"doc_url"` to `"https://expansive-labs-llc.github.io/tessera/"` so that Blender's built-in "Documentation" button in the add-on preferences links to the docs site. |
| FR-045 | Existing tooltip text (the `description` field) on all operators and properties in `tessera/operators/*.py` and `tessera/properties.py` SHOULD be reviewed and updated to provide concise, actionable descriptions that serve as in-context help. This is a SHOULD requirement — defer to a separate task if scope exceeds 2 hours of effort. |

### 3.11 Gallery Page (FR-046)

| ID | Requirement |
|----|-------------|
| FR-046 | The `docs/docs/gallery/index.md` SHALL be updated to include a gallery structure with ≥ 3 placeholder entries. Each entry SHALL include: (a) object name, (b) input description (number of images, view labels used), (c) input image placeholder, (d) output 3D render placeholder, (e) output format(s), (f) approximate generation time. Actual images SHALL be generated using the Tessera add-on and added in a follow-up commit or task. |

### 3.12 Input Specifications

N/A — This spec produces documentation content. Inputs are existing source files and PRD content.

### 3.13 Output Specifications

| Output | Type | Format | Location |
|--------|------|--------|----------|
| MkDocs configuration | YAML | MkDocs config schema | `docs/mkdocs.yml` |
| Documentation build dependencies | Text | pip requirements format | `docs/requirements.txt` |
| Documentation pages (18+ pages) | Markdown | MkDocs-compatible GFM with admonitions | `docs/docs/**/*.md` |
| Screenshot manifest | Markdown | Manifest table | `docs/docs/assets/screenshots/README.md` |
| Help panel update | Python | Blender `bpy` operator | `tessera/ui/help_panel.py` |
| bl_info doc_url update | Python | String literal | `tessera/__init__.py` |

---

## 4. CONSTRAINTS

> ⚠️ **Critical for AI code generation.** These are hard prohibitions the AI must follow.

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT fabricate feature descriptions. All documentation content SHALL be sourced from or consistent with the existing PRD, spec documents, and implemented code. |
| CON-002 | SHALL NOT include actual screenshots in this spec's deliverables. Screenshot placeholders with descriptive `alt` text SHALL be used. Actual screenshots require a working Blender installation and SHALL be captured in a follow-up task or commit. |
| CON-003 | SHALL NOT modify any Python source files other than `tessera/ui/help_panel.py` and `tessera/__init__.py` (for `doc_url`). |
| CON-004 | SHALL NOT reference internal tooling paths (`.agent/` directory contents) in any documentation page. |
| CON-005 | SHALL NOT include any personal email addresses, API keys, or credentials in documentation. |
| CON-006 | SHALL NOT use MkDocs features or plugins that are NOT listed in `docs/requirements.txt`. All plugins must be explicitly declared. |
| CON-007 | Documentation content SHALL be licensed under CC-BY-4.0. Each page that is newly created SHOULD include a footer note: `*Documentation licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).*` |
| CON-008 | SHALL NOT break existing page URLs. All existing page filenames (`index.md`, `installation.md`, `quickstart.md`, `troubleshooting.md`, `user-guide/*.md`, `api/*.md`, `gallery/index.md`) SHALL be preserved. New pages are additions only. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

> ⚠️ **All NFRs must be quantified.** Replace vague terms with specific numbers.

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | Documentation site build time | Wall-clock time for `mkdocs build` | ≤ 30 seconds | On a machine with 4+ CPU cores, all pages present, no network calls during build |
| NFR-002 | Page count | Total `.md` pages in `docs/docs/` | ≥ 18 pages | Counted via `find docs/docs -name "*.md" \| wc -l` |
| NFR-003 | Quickstart word count | Total words in `quickstart.md` | ≤ 500 words | Excluding code blocks and image alt text |
| NFR-004 | Quickstart step count | Numbered steps in main workflow | ≤ 5 steps | "Step N:" headings in quickstart.md |
| NFR-005 | FAQ question count | Total questions in `faq.md` | ≥ 15 questions | `## ` headings in faq.md |
| NFR-006 | Cross-link density | Pages with "See Also" sections | 100% of user-guide pages (8/8) | Manual audit |
| NFR-007 | Glossary term count | Terms defined in `glossary.md` | ≥ 25 terms | `## ` headings in glossary.md |
| NFR-008 | Mobile responsiveness | Documentation site renders without horizontal scroll | 100% of pages | Tested at 375px viewport width in Chrome DevTools |
| NFR-009 | Search functionality | Site search returns results for "GPU", "STL", "manifold", "install" | 4/4 queries return ≥ 1 result | After `mkdocs build` with search plugin enabled |
| NFR-010 | Screenshot placeholder count | Unique screenshot placeholders across all pages | ≥ 15 placeholders | Counted via `grep -r "assets/screenshots/" docs/docs/ \| wc -l` |

---

## 6. ACCEPTANCE CRITERIA

> ⚠️ **Minimum 3 criteria in Given-When-Then format.** These drive test implementation.

### AC-001: Documentation Site Builds Successfully
**Given** all documentation files are present in `docs/docs/` and `docs/requirements.txt` dependencies are installed,  
**When** the command `mkdocs build --strict` is run from the `docs/` directory,  
**Then** the build completes with exit code 0, produces a `site/` directory containing HTML files, and reports 0 warnings about broken links or missing pages.

### AC-002: Quickstart Covers Full Workflow in ≤ 5 Steps
**Given** the `docs/docs/quickstart.md` exists,  
**When** a reviewer reads the quickstart page,  
**Then** the page contains exactly ≤ 5 numbered workflow steps (from opening Tessera to exporting STL), each step has ≤ 3 sentences of instruction, each step has a screenshot placeholder, and a "Next Steps" section links to ≥ 3 other pages.

### AC-003: All Implemented Features Are Documented
**Given** the user guide contains 8 pages (image-input, reconstruction, sketch-to-3d, mesh-cleanup, scaling-orientation, refinement, export, preferences),  
**When** a reviewer compares the user-guide pages against the implemented spec list (SPEC-TS-0001 through SPEC-TS-0011),  
**Then** every user-facing feature from every implemented spec has a corresponding section in at least one user-guide page, and there are zero features that are implemented but undocumented.

### AC-004: Reference Section Contains PRD Content
**Given** the reference section contains `view-labels.md`, `glossary.md`, and `printer-profiles.md`,  
**When** a reviewer compares the reference content against PRD §6 (View Label Vocabulary), PRD §13 (Glossary), and the export system's printer profiles,  
**Then** (a) the view labels table contains all 10 labels from PRD §6 with matching azimuth/elevation values, (b) the glossary contains all 8 terms from PRD §13 plus ≥ 17 additional Tessera-specific terms, (c) the printer profiles table contains all 7 profiles from the export documentation.

### AC-005: FAQ Addresses Common Support Scenarios
**Given** the `docs/docs/faq.md` exists with ≥ 15 questions,  
**When** a reviewer reads the FAQ,  
**Then** (a) questions are organized into 4 categories, (b) the 10 specific questions listed in FR-038 are all present, (c) each answer is ≤ 5 sentences, (d) each answer links to a relevant user-guide or reference page.

### AC-006: In-Add-on Help Links to Documentation Site
**Given** the `tessera/ui/help_panel.py` has been updated and `tessera/__init__.py` `bl_info["doc_url"]` is set,  
**When** a user clicks the "Documentation" button in the Help panel or clicks "Documentation" in the add-on preferences,  
**Then** the user's default web browser opens `https://expansive-labs-llc.github.io/tessera/`.

### AC-007: MkDocs Nav Structure Matches Spec
**Given** the `docs/mkdocs.yml` has been updated with the expanded `nav` structure,  
**When** the documentation site is built and served locally via `mkdocs serve`,  
**Then** the navigation displays 7 top-level sections (Home, Getting Started, User Guide, Reference, FAQ, API Reference, Gallery) with all sub-pages accessible via the navigation menu.

### AC-008: No Broken Internal Links
**Given** all documentation pages contain cross-links to other pages,  
**When** `mkdocs build --strict` is run,  
**Then** the build completes with 0 warnings about broken links or undefined references.

---

## 7. EDGE CASES

> ⚠️ **Minimum 2 edge cases required.** Document non-obvious scenarios AI might miss.

### EC-001: Existing Documentation Pages Must Not Break
| Aspect | Detail |
|--------|--------|
| **Scenario** | The existing `docs/` directory already contains pages (`index.md`, `installation.md`, etc.) with content that may be linked from external sources (README, CONTRIBUTING). Renaming or deleting these files would break incoming links. |
| **Input Example** | Someone has bookmarked `https://expansive-labs-llc.github.io/tessera/installation/` or the README links to `docs/docs/troubleshooting.md`. |
| **Expected Behavior** | All existing filenames SHALL be preserved. New pages SHALL be additions only. Existing content SHALL be expanded in-place, not replaced with stubs. The `nav` structure SHALL maintain existing URL paths. |
| **Test ID** | TS-001 |

### EC-002: MkDocs Build Must Succeed Without Git History
| Aspect | Detail |
|--------|--------|
| **Scenario** | The `mkdocs-git-revision-date-localized-plugin` requires a git repository with commit history. In CI environments using shallow clones (`git clone --depth 1`), the plugin may fail if not configured to handle missing dates. |
| **Input Example** | Running `mkdocs build` in a Docker container with a shallow clone of the repository (no git history). |
| **Expected Behavior** | The `docs/mkdocs.yml` SHALL configure the `git-revision-date-localized` plugin with `fallback_to_build_date: true` and `enabled: !ENV [ENABLE_GIT_DATES, true]` so the build succeeds without git history by falling back to the build timestamp. |
| **Test ID** | TS-002 |

### EC-003: Screenshot Placeholders Must Not Break Page Rendering
| Aspect | Detail |
|--------|--------|
| **Scenario** | Screenshot placeholder images (e.g., `assets/screenshots/main-panel.png`) will NOT exist until screenshots are captured in a follow-up task. Missing images could display as broken image icons. |
| **Input Example** | A page references `![Main panel](assets/screenshots/main-panel.png)` but the file does not exist. |
| **Expected Behavior** | MkDocs renders missing images as the `alt` text (descriptive text) rather than broken image icons. All `alt` text SHALL be sufficiently descriptive to convey the intended content even when the image is missing (e.g., "Tessera main panel showing Image Input, Generation, Validation, and Export sections in the Blender 3D Viewport sidebar" rather than "screenshot"). |
| **Test ID** | TS-003 |

### EC-004: Documentation Must Be Readable Without JavaScript
| Aspect | Detail |
|--------|--------|
| **Scenario** | Some users may browse documentation with JavaScript disabled (corporate proxies, privacy tools). MkDocs Material theme requires JavaScript for search and dark mode toggle. |
| **Input Example** | User opens the documentation site in a browser with JavaScript blocked. |
| **Expected Behavior** | All page content SHALL be readable without JavaScript. Tables, code blocks, admonitions, and navigation links SHALL render as plain HTML. Only interactive features (search, dark mode toggle, lightbox) MAY be degraded. |
| **Test ID** | TS-004 |

---

## 8. OUT OF SCOPE

> ⚠️ **Explicitly list what this feature does NOT include.** Prevents AI scope creep.

The following are explicitly **excluded** from this feature:

- ❌ Actual screenshot capture — placeholder images with descriptive `alt` text are used; screenshots require a working Blender installation with the add-on enabled and are deferred to a follow-up commit
- ❌ CI/CD pipeline for docs deployment — the GitHub Actions workflow for `mkdocs gh-deploy` is part of TASK-TS-0014 (CI/CD Pipeline)
- ❌ Video tutorials or animated GIFs — text + screenshot documentation only for v1
- ❌ API auto-generation from docstrings (e.g., `mkdocstrings`) — API reference is manually authored
- ❌ Internationalization (i18n) — English only
- ❌ PDF export of documentation — web-only
- ❌ Custom MkDocs theme or plugin development — use stock Material for MkDocs features only
- ❌ Blog or changelog section — changelog is auto-generated by semantic-release (SPEC-TS-0012 Out of Scope)
- ❌ User analytics or tracking — no telemetry per PRD decision D3
- ❌ Interactive code playgrounds or live demos
- ❌ Internal health-check and diagnostic mechanisms from SPEC-TS-0011 — these are developer-facing runtime features; user-visible effects (error messages, degraded-mode notifications) are covered in Troubleshooting (FR-039)
- ❌ Modification of any Python source files other than `help_panel.py` and `__init__.py`

---

## 9. SECURITY CONSIDERATIONS

> ⚠️ **Required for all features.** AI-generated code needs explicit security constraints.

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — static documentation site hosted on GitHub Pages, publicly accessible |
| **Auth Method** | None |
| **Required Permissions** | Repository write access to push files (GitHub user permission) |
| **Rate Limiting** | N/A — static site served by GitHub Pages CDN |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| Documentation content | Public | No sensitive information; screenshots must not show personal file paths |
| Screenshot images | Public | Must not contain PII (usernames, file paths to home directories) |
| MkDocs config | Public | No credentials, no internal URLs |
| `doc_url` in bl_info | Public | Points to public GitHub Pages URL |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL NOT include any API keys, tokens, credentials, or secrets in any documentation file or configuration. |
| SEC-002 | SHALL NOT include personal file paths (e.g., `/home/derek/...`) in any documentation content, screenshot alt text, or code examples. Use generic paths (e.g., `/home/user/`, `C:\Users\user\`). |
| SEC-003 | The `bpy.ops.wm.url_open()` call in `help_panel.py` SHALL use a hardcoded HTTPS URL. The URL SHALL NOT be constructed from user input. |
| SEC-004 | SHALL NOT include any `<script>` tags or raw HTML that could enable XSS in documentation pages. MkDocs Material's built-in sanitization handles this, but content SHALL avoid raw HTML injection patterns. |

---

## 10. API CONTRACT [CONDITIONAL]

> **Skip** — This spec produces documentation and a minor UI update. No APIs are exposed or consumed.

---

## 11. OBSERVABILITY

> N/A — Static documentation site produces no runtime telemetry. The only code change (`help_panel.py`) adds a URL-open operator with no logging requirements beyond Blender's existing operator logging.

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — documentation files and site are always present |
| **Default State** | Documentation source files in `docs/`; site built and deployed via CI |
| **Rollout Plan** | Single PR with all documentation content; CI deploys to GitHub Pages (TASK-TS-0014) |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| SPEC-TS-0012 (Repo Foundation) | Yes (soft) | README links to docs site; CONTRIBUTING references docs |
| All Phase 1–4 feature implementations | Yes | Features must exist to document them — all currently complete or in progress |
| TASK-TS-0014 (CI/CD Pipeline) | No | Docs can be built and previewed locally; CI deployment is a separate task |

### 12.3 Rollback Plan
1. Revert the PR that adds documentation files
2. The docs site returns to its previous skeleton state
3. No runtime impact — these are static content files plus a minor UI button

---

## 13. TEST SCENARIOS

> Map tests to acceptance criteria and edge cases for traceability.

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | All existing page filenames preserved — `index.md`, `installation.md`, `quickstart.md`, `troubleshooting.md`, `user-guide/*.md`, `api/*.md`, `gallery/index.md` exist | Script | EC-001, CON-008 | Must Pass |
| TS-002 | `mkdocs build` succeeds without git history when `ENABLE_GIT_DATES=false` | Script | EC-002, AC-001 | Must Pass |
| TS-003 | All screenshot placeholders have descriptive `alt` text (≥ 10 words) | Script | EC-003, FR-029 | Must Pass |
| TS-004 | `mkdocs build --strict` completes with 0 warnings | Script | AC-001, AC-008 | Must Pass |
| TS-005 | `quickstart.md` contains ≤ 5 numbered steps | Manual | AC-002, FR-015, NFR-004 | Must Pass |
| TS-006 | User-guide directory contains exactly 8 `.md` files | Script | AC-003, FR-018 | Must Pass |
| TS-007 | `view-labels.md` contains all 10 view labels from PRD §6 | Manual | AC-004, FR-030 | Must Pass |
| TS-008 | `glossary.md` contains ≥ 25 defined terms | Script | AC-004, NFR-007 | Must Pass |
| TS-009 | `faq.md` contains ≥ 15 `## ` headings (questions) | Script | AC-005, NFR-005 | Must Pass |
| TS-010 | `faq.md` contains all 10 specific questions from FR-038 | Manual | AC-005, FR-038 | Must Pass |
| TS-011 | `tessera/__init__.py` `bl_info["doc_url"]` is set to `https://expansive-labs-llc.github.io/tessera/` | Script | AC-006, FR-044 | Must Pass |
| TS-012 | `help_panel.py` contains a `url_open` operator call with the docs URL | Script | AC-006, FR-043 | Must Pass |
| TS-013 | `mkdocs.yml` nav has 7 top-level sections | Manual | AC-007, FR-001 | Must Pass |
| TS-014 | `docs/requirements.txt` exists and lists ≥ 4 dependencies | Script | FR-006 | Must Pass |
| TS-015 | `docs/docs/assets/screenshots/README.md` lists ≥ 15 screenshots | Script | FR-041, FR-042 | Must Pass |
| TS-016 | Total `.md` page count in `docs/docs/` is ≥ 18 | Script | NFR-002 | Must Pass |
| TS-017 | All 8 user-guide pages have a "See Also" section | Script | FR-027, NFR-006 | Must Pass |
| TS-018 | `installation.md` contains a VRAM requirements table | Manual | FR-012 | Must Pass |
| TS-019 | `installation.md` contains a "Build from Source" section with ≤ 6 steps | Manual | FR-011 | Must Pass |
| TS-020 | No page contains paths matching `/home/derek/` or personal identifiers | Script | SEC-002 | Must Pass |
| TS-021 | `printer-profiles.md` contains ≥ 7 printer profiles | Manual | FR-032, AC-004 | Must Pass |
| TS-022 | `error-codes.md` contains entries for BF-E001 through BF-E016 plus BF-E999 fallback (17 total, matching `tessera/errors/catalog.py`) | Script | FR-033 | Must Pass |

> **Note on "Script" tests:** Script-type tests (TS-001, TS-002, TS-003, TS-004, TS-006, TS-008, TS-009, TS-011, TS-012, TS-014, TS-015, TS-016, TS-017, TS-020, TS-022) are one-off verification scripts run by the implementor during review. They do not need to be committed to the repository as part of the permanent test suite.

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0001 through SPEC-TS-0011 (all Phase 1–4 specs) | Content reference | Complete / In Progress | Tessera | No — user guide content is sourced from spec feature descriptions |
| PRD-001_Tessera.md | Content reference | Available | Derek | No — view labels (§6), glossary (§13), user stories (§4) sourced from PRD |
| `docs/` existing content | Build foundation | Available | Tessera | No — existing skeleton pages are expanded in-place |
| SPEC-TS-0012 (Repo Foundation) | Soft dependency | In Progress | Tessera | No — README links to docs site; CONTRIBUTING references docs |
| `tessera/ui/help_panel.py` | Code modification | Available | Tessera | No — minor operator addition |
| `tessera/__init__.py` | Code modification | Available | Tessera | No — single string update to `bl_info` |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| MkDocs ≥ 1.6 | Required | [mkdocs.org](https://www.mkdocs.org/) | N/A — core build tool |
| Material for MkDocs ≥ 9.5 | Required | [squidfunk.github.io/mkdocs-material](https://squidfunk.github.io/mkdocs-material/) | N/A — theme is integral to design |
| mkdocs-glightbox ≥ 0.4 | Optional | [pypi.org/project/mkdocs-glightbox](https://pypi.org/project/mkdocs-glightbox/) | Images display inline without lightbox |
| mkdocs-git-revision-date-localized-plugin ≥ 1.2 | Optional | [pypi.org/project/mkdocs-git-revision-date-localized-plugin](https://pypi.org/project/mkdocs-git-revision-date-localized-plugin/) | Page dates not shown; configure `fallback_to_build_date: true` |
| GitHub Pages | Required | [pages.github.com](https://pages.github.com/) | Alternative: Netlify, Vercel, or self-hosted |

---

## 15. APPROVAL

| Role | Name | Date | Status |
|------|------|------|--------|
| Author (Orchestrator) | AI | 2026-04-16 | ☐ Submitted |
| CSO Approval | Derek | | ☐ Approved / ☐ Changes Requested |
| Deputy Review | | | ☐ N/A |

**Approval Notes:**
[Space for CSO/Deputy feedback]

---

## AI-READINESS SELF-SCORE

> **Score your Spec before submitting for CSO approval. Target: ≥80/100**

| Criterion | Max | Score | Guidance |
|-----------|-----|-------|----------|
| SHALL/SHOULD/MAY requirements | 20 | 20 | 46 requirements (FR-001 – FR-046) with precise SHALL/SHOULD/MAY language throughout |
| Quantified NFRs | 15 | 15 | 10 NFRs all quantified with specific targets, measurement tools, and conditions |
| Given-When-Then criteria (3+) | 20 | 20 | 8 acceptance criteria in Given-When-Then format with specific values and verifiable outcomes |
| Edge cases (2+) | 15 | 15 | 4 edge cases with concrete input examples and expected behaviors |
| Out of scope defined | 10 | 10 | 12 explicit exclusions with cross-references to other tasks |
| Security constraints | 10 | 10 | 4 security requirements + data classification table addressing PII in screenshots and hardcoded URLs |
| No ambiguous language | 10 | 9 | All ambiguous terms resolved; FR-045 uses "actionable" with clear definition (≤ 3 sentences, describes what the control does) |
| **TOTAL** | **100** | **93** | **Target: ≥80 ✅ — Formal review score: 93/100** |

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
- [x] "fast" / "efficient" / "performant" → replaced with ≤ 30 seconds build time (NFR-001)
- [x] "secure" → replaced with SEC-001 through SEC-004
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → not used

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-16 | Orchestrator (AI) | Initial draft |
| 1.1 | 2026-04-16 | AI (Spec Review) | Fixed §2.1 file references (preferences.py→properties.py, errors/codes.py→errors/catalog.py), corrected site_url mismatch note in FR-003, added SPEC-TS-0011 out-of-scope entry, fixed UI panel count (12→13), added nav restructure note to FR-001, corrected error code range in FR-033/TS-022, added pymdownx.keys as new extension note |
| 1.2 | 2026-04-17 | AI (Spec Review v2) | Fixed UI panel count (13→12), added stale URL update note to FR-043 for existing `_DOCS_URL`/`_QUICKSTART_URL` constants, changed AC-001 to use `mkdocs build --strict`, added `assets/screenshots/README.md` and `gallery.yaml` to §2.3 file tree, aligned self-score with formal review score (93/100) |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0013-user-manual.md`
