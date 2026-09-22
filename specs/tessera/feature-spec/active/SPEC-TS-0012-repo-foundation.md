# Feature Specification: Repository Foundation & Open-Source Readiness

> **Quick Start:** Fill sections in order. Use the AI-Readiness Self-Score at the end to verify ≥80 before submitting for CSO approval. Sections marked [CONDITIONAL] can be skipped if not applicable.

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | SPEC-TS-0012 |
| **Task ID** | TASK-TS-0012 |
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
Tessera is transitioning from a private development codebase to an open-source project published at `Expansive-Labs-LLC/tessera` on GitHub. The repository already exists but is empty — nothing has been pushed. Before the first public push, the repo needs a professional foundation: proper licensing (GPL-2.0-or-later, mandated by Blender's add-on distribution policy and PRD decision D6), contributor documentation, a security policy, structured issue/PR workflows, and a README that serves dual audiences — open-source contributors evaluating the project AND marketplace buyers considering a purchase. This is the first impression for both audiences and the gate for all subsequent Phase 5 publication tasks (CI pipeline, marketplace listings, documentation site).

### 1.2 User Story
**As a** developer discovering Tessera on GitHub,  
**I want** a clear README, license, and contribution guidelines,  
**So that** I understand what the project does, how to use it, and how to contribute.

### 1.3 Proposed Approach
Create 9 files in the repository root and `.github/` directory that establish the open-source foundation: (1) `LICENSE` containing the full GPL-2.0-or-later text matching existing `SPDX-License-Identifier` headers in all source files, (2) `README.md` with hero section, feature highlights, system requirements, dual install paths (marketplace + build-from-source), and CI/status badges, (3) `CONTRIBUTING.md` with dev environment setup, Conventional Commits requirements (for semantic-release compatibility with `Expansive-Labs-LLC/github-actions/versioning`), and PR/testing workflow, (4) `CODE_OF_CONDUCT.md` adopting Contributor Covenant v2.1, (5) `SECURITY.md` with vulnerability reporting process emphasizing local-only inference, (6) `.gitignore` tailored for Python/Blender/ML with `.agent/` exclusion, (7) `.github/ISSUE_TEMPLATE/bug_report.yml` and `feature_request.yml` with structured fields, (8) `.github/PULL_REQUEST_TEMPLATE.md` with a PR checklist, and (9) `.github/FUNDING.yml` linking to marketplace listings.

---

## 2. TECHNICAL CONTEXT

> ⚠️ **AI needs this context BEFORE generating code.** Provide patterns and references here.

### 2.1 Related Code Patterns
| File/Module | Purpose | Use As Reference For |
|-------------|---------|----------------------|
| `tessera/__init__.py` | Add-on entry point with `bl_info` and GPL header | License text, version info (`(0, 1, 0)`), Blender minimum version (`(4, 2, 0)`), feature description for README |
| `PRD-001_Tessera.md` | Master PRD with §1 Executive Summary, §2 Problem Statement, §3 Goals, §8 Tech Stack | README content: value proposition, feature list, system requirements, architecture overview |
| `Expansive-Labs-LLC/github-actions/versioning/action.yml` | Reusable composite action using `cycjimmy/semantic-release-action@v4` with `@semantic-release/changelog@6.0.0` | CONTRIBUTING.md: Conventional Commits format required for semantic-release |
| `Expansive-Labs-LLC/github-actions/.releaserc.yml` | Semantic-release config: branches `[main, github/template]`, tag format `${version}`, plugins: `commit-analyzer`, `release-notes-generator`, `changelog`, `github` | CONTRIBUTING.md: commit message format, release branch strategy |
| `specs/tessera/feature-spec/active/SPEC-TS-0011-production-hardening.md` | Latest spec with GPL-2.0+ header, CON-007 license constraint | License consistency, documentation licensing (CC-BY-4.0 for docs) |

### 2.2 Tech Stack & Standards
- **Language:** Markdown, YAML (GitHub-flavored)
- **Platform:** GitHub (repository settings, issue templates, PR templates, funding)
- **License tooling:** SPDX identifiers, GPL-2.0-or-later full text
- **Commit conventions:** [Conventional Commits v1.0.0](https://www.conventionalcommits.org/)
- **Semantic release:** `cycjimmy/semantic-release-action@v4` with `@semantic-release/changelog@6.0.0`, `@semantic-release/git`
- **Testing:** `pytest` run via `blender --background --python` (documented in CONTRIBUTING)
- **Code style:** PEP 8, `black` formatter, `isort` for imports (documented in CONTRIBUTING)

### 2.3 Architecture Notes
This spec produces **static files only** — no Python code, no runtime behavior. All 9 deliverables are Markdown, YAML, or plain text files that live in the repository root or `.github/` directory. They configure GitHub's native features (issue templates, PR templates, funding, license detection) and document project conventions for human contributors.

**File tree produced by this spec:**
```
/                               (repository root)
├── LICENSE                     # GPL-2.0-or-later full text
├── README.md                   # Project overview, install, badges
├── CONTRIBUTING.md             # Dev setup, commit conventions, PR process
├── CODE_OF_CONDUCT.md          # Contributor Covenant v2.1
├── SECURITY.md                 # Vulnerability reporting policy
├── .gitignore                  # Python/Blender/ML exclusions
└── .github/
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.yml      # Structured bug report form
    │   └── feature_request.yml # Feature request form
    ├── PULL_REQUEST_TEMPLATE.md # PR checklist
    └── FUNDING.yml             # Marketplace links
```

---

## 3. FUNCTIONAL REQUIREMENTS

> ⚠️ **Use precise language:** SHALL (required), SHALL NOT (prohibited), SHOULD (recommended), SHOULD NOT (discouraged), MAY (optional). The keyword IS the priority.

### 3.1 LICENSE (FR-001 – FR-003)

| ID | Requirement |
|----|-------------|
| FR-001 | The repository SHALL contain a `LICENSE` file at the root containing the exact full text of the GNU General Public License version 2 as published by the Free Software Foundation, with the "or later" clause included. The file SHALL NOT contain any project-specific modifications to the license text. |
| FR-002 | The `LICENSE` file SHALL be detected by GitHub's license detection system as `GPL-2.0-or-later` when viewed on github.com. This requires using the canonical GPL-2.0 text from https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt with the preamble that permits "any later version." |
| FR-003 | The license declared in `LICENSE` SHALL be consistent with: (a) the `SPDX-License-Identifier: GPL-2.0-or-later` header present in all existing `.py` source files, (b) PRD §8 Tech Stack (`GPL v2+`), and (c) PRD Decision D6 (`GPL accepted`). |

### 3.2 README.md (FR-004 – FR-013)

| ID | Requirement |
|----|-------------|
| FR-004 | The `README.md` SHALL begin with a hero section containing: (a) the project name "Tessera", (b) a one-line tagline: "AI-powered Blender add-on that turns reference images into 3D-printable models" (intentionally differs from `bl_info["description"]` for marketing clarity), (c) a brief 2–3 sentence value proposition summarizing PRD §1 and §2. |
| FR-005 | The `README.md` SHALL include a "Features" section with a bulleted list of at minimum 8 capabilities extracted from the implemented specs (SPEC-TS-0001 through SPEC-TS-0011): (1) multi-view and single-image 3D reconstruction, (2) sketch-to-3D pathway, (3) AI-powered mesh cleanup and topology optimization, (4) print-readiness validation (manifold, watertight, wall thickness), (5) STL/3MF/OBJ export with metadata, (6) natural-language refinement loop, (7) real-world scaling and print orientation, (8) local GPU inference — no cloud dependencies. |
| FR-006 | The `README.md` SHALL include a "System Requirements" section specifying: (a) Blender ≥ 4.2 LTS, (b) NVIDIA GPU with CUDA support or Apple Silicon with MPS backend, (c) minimum 8 GB VRAM (12 GB recommended), (d) minimum 16 GB system RAM, (e) 5 GB disk space for model weights, (f) Python 3.11+ (bundled with Blender). |
| FR-007 | The `README.md` SHALL include an "Installation" section with two subsections: (a) **Marketplace Install** — one-click install instructions with a placeholder URL format `[Marketplace link coming soon]`, (b) **Build from Source** — step-by-step instructions covering: `git clone`, navigating to the add-on directory, creating the `.zip`, and installing via Blender's Preferences → Add-ons. The build-from-source instructions SHALL contain ≤ 6 numbered steps. |
| FR-008 | The `README.md` SHALL include a "Quick Start" section with ≤ 5 numbered steps showing the workflow from first launch to first exported STL. |
| FR-009 | The `README.md` SHALL include a badges row at the top (immediately after the hero title) with at minimum 4 badges: (a) CI status badge (GitHub Actions, using placeholder workflow path `.github/workflows/ci.yml`), (b) license badge showing `GPL-2.0-or-later`, (c) Blender version badge showing `4.2+`, (d) latest release badge (GitHub Releases). Badge images SHALL use `shields.io` or GitHub's native badge URLs. |
| FR-010 | The `README.md` SHALL include a "Documentation" section linking to the full documentation site (placeholder URL `https://expansivelabs.io/tessera/`) and listing key doc pages: Installation Guide, User Guide, API Reference, Troubleshooting. |
| FR-011 | The `README.md` SHALL include a "Contributing" section with a brief summary (2–3 sentences) and a link to `CONTRIBUTING.md`. |
| FR-012 | The `README.md` SHALL include a "License" section stating the project is licensed under GPL-2.0-or-later, linking to the `LICENSE` file. |
| FR-013 | The `README.md` SHALL include a "Security" section with a brief statement that all inference runs locally and a link to `SECURITY.md`. |

### 3.3 CONTRIBUTING.md (FR-014 – FR-021)

| ID | Requirement |
|----|-------------|
| FR-014 | The `CONTRIBUTING.md` SHALL include a "Development Environment Setup" section with step-by-step instructions (≤ 8 steps) covering: (a) cloning the repository, (b) creating a Python virtual environment, (c) installing development dependencies (pytest, black, isort, flake8, mypy), (d) symlinking or copying the `tessera/` directory into Blender's add-on path, (e) verifying the add-on loads in Blender. |
| FR-015 | The `CONTRIBUTING.md` SHALL include a "Commit Messages" section documenting the Conventional Commits v1.0.0 format with: (a) the format `<type>(<scope>): <description>`, (b) a table of allowed types (`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`), (c) a note that this format is **mandatory** because it drives automated semantic versioning via `semantic-release`, (d) at least 3 concrete commit message examples: one `feat`, one `fix`, one `docs`, (e) a note that additional types `spec` and `task` are accepted for specification and task file changes (aligned with the engineering playbook's extended commitlint configuration) but are not required for typical contributions. |
| FR-016 | The `CONTRIBUTING.md` SHALL include a "Pull Request Process" section describing: (a) fork and branch workflow, (b) branch naming convention `<type>/<short-description>` (e.g., `feat/add-obj-export`), (c) requirement that all PR checks pass before merge, (d) requirement that at least 1 reviewer approves, (e) reference to the PR template checklist. |
| FR-017 | The `CONTRIBUTING.md` SHALL include a "Testing" section documenting: (a) how to run the full test suite (`pytest tests/`), (b) how to run tests in Blender headless mode (`blender --background --python -m pytest`), (c) requirement that all tests pass before submitting a PR, (d) how to add new tests following the existing `tests/test_*.py` pattern. |
| FR-018 | The `CONTRIBUTING.md` SHALL include a "Code Style" section specifying: (a) PEP 8 compliance, (b) `black` formatter with default settings, (c) `isort` for import sorting with `profile = "black"`, (d) `flake8` for linting, (e) `mypy` for optional type checking. All tool configurations SHALL reference their respective config files if they exist (e.g., `pyproject.toml`). |
| FR-019 | The `CONTRIBUTING.md` SHALL include a "Spec Workflow" section with a brief description of the Task → Spec → Implement → Review workflow, noting that contributors should update or create specs in `specs/` when proposing significant changes. This section SHALL describe the spec format inline (sections: Metadata, Problem Statement, Functional Requirements, Constraints, Acceptance Criteria, Test Scenarios) rather than linking to the `.agent/` directory, which is excluded from the public repository. |
| FR-020 | The `CONTRIBUTING.md` SHALL include a "License" section reminding contributors that: (a) all contributions must be licensed under GPL-2.0-or-later, (b) every new `.py` file must include the following exact 14-line SPDX license header as a copy-paste template: ```# SPDX-License-Identifier: GPL-2.0-or-later``` ```#``` ```# This program is free software: you can redistribute it and/or modify``` ```# it under the terms of the GNU General Public License as published by``` ```# the Free Software Foundation, either version 2 of the License, or``` ```# (at your option) any later version.``` ```#``` ```# This program is distributed in the hope that it will be useful,``` ```# but WITHOUT ANY WARRANTY; without even the implied warranty of``` ```# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the``` ```# GNU General Public License for more details.``` ```#``` ```# You should have received a copy of the GNU General Public License``` ```# along with this program.  If not, see <https://www.gnu.org/licenses/>.```, (c) documentation content is licensed under CC-BY-4.0. |
| FR-021 | The `CONTRIBUTING.md` SHALL include a "Getting Help" section listing: (a) GitHub Issues for bug reports and feature requests, (b) GitHub Discussions (if enabled) for questions, (c) the project's communication channels (placeholder). |

### 3.4 CODE_OF_CONDUCT.md (FR-022 – FR-023)

| ID | Requirement |
|----|-------------|
| FR-022 | The `CODE_OF_CONDUCT.md` SHALL contain the full text of the Contributor Covenant v2.1 (https://www.contributor-covenant.org/version/2/1/code_of_conduct/), with the following customizations: (a) `[INSERT CONTACT METHOD]` replaced with the project's reporting email address (placeholder `conduct@tessera.dev`), (b) enforcement section referencing the project maintainers. |
| FR-023 | The `CODE_OF_CONDUCT.md` SHALL include the Contributor Covenant badge at the top: `[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)`. |

### 3.5 SECURITY.md (FR-024 – FR-027)

| ID | Requirement |
|----|-------------|
| FR-024 | The `SECURITY.md` SHALL include a "Security Model" section stating: (a) all AI inference runs locally on the user's GPU — no data leaves the user's machine, (b) the only network activity is optional model weight downloads from configured URLs (SPEC-TS-0002), (c) no telemetry, analytics, or crash reporting is collected (PRD decision D3). |
| FR-025 | The `SECURITY.md` SHALL include a "Reporting a Vulnerability" section with: (a) instruction to use GitHub's private vulnerability reporting feature (Security → Advisories → "Report a vulnerability"), (b) a fallback email address (placeholder `security@tessera.dev`) for reporters who cannot use GitHub, (c) expected response time of ≤ 5 business days for acknowledgment, (d) a statement that reporters will receive credit in the advisory unless they prefer to remain anonymous. |
| FR-026 | The `SECURITY.md` SHALL include a "Supported Versions" table listing which versions receive security updates. For the initial release, this SHALL show: `0.x.x — ✅ Supported` (development releases). |
| FR-027 | The `SECURITY.md` SHALL include a "Disclosure Policy" section stating that: (a) vulnerabilities will be disclosed publicly after a fix is available, (b) patches will be released as a new version following semantic versioning, (c) CVE identifiers will be requested for vulnerabilities with CVSS ≥ 7.0. |

### 3.6 .gitignore (FR-028 – FR-031)

| ID | Requirement |
|----|-------------|
| FR-028 | The `.gitignore` SHALL exclude the following Python artifacts: `__pycache__/`, `*.py[cod]`, `*$py.class`, `*.so`, `*.egg-info/`, `*.egg`, `dist/`, `build/`, `.eggs/`. |
| FR-029 | The `.gitignore` SHALL exclude the following development/environment directories: `.venv/`, `venv/`, `env/`, `.env`, `.pytest_cache/`, `.mypy_cache/`, `.tox/`, `htmlcov/`, `.coverage`, `*.cover`. |
| FR-030 | The `.gitignore` SHALL exclude the following Blender and ML-specific artifacts: `*.blend1` (Blender backup files), model weight files (`*.pt`, `*.pth`, `*.onnx`, `*.safetensors`, `*.bin` — except those in `tests/`), and model cache directories (`model_cache/`, `weights/`). |
| FR-031 | The `.gitignore` SHALL exclude `.agent/` (internal AI tooling). The `.gitignore` SHALL NOT exclude `specs/` or `tasks/` — these directories SHALL remain visible and tracked because contributors need them to follow the Task → Spec → Implement workflow (per CSO decision in TASK-TS-0012 Open Questions #1). |

### 3.7 Issue Templates (FR-032 – FR-036)

| ID | Requirement |
|----|-------------|
| FR-032 | The repository SHALL contain `.github/ISSUE_TEMPLATE/bug_report.yml` as a GitHub issue form (YAML format, not Markdown template) with `name: "🐛 Bug Report"` and `description: "Report a bug in Tessera"`. |
| FR-033 | The bug report form SHALL include the following required fields: (a) `description` — textarea, "Describe the bug", minimum 20 characters, (b) `steps_to_reproduce` — textarea, "Steps to Reproduce", minimum 20 characters, (c) `expected_behavior` — textarea, "Expected Behavior", (d) `actual_behavior` — textarea, "Actual Behavior". |
| FR-034 | The bug report form SHALL include the following required environment fields: (a) `blender_version` — dropdown with options: `4.2 LTS`, `4.3`, `4.4`, `Other (specify in description)`, (b) `os` — dropdown with options: `Windows 10`, `Windows 11`, `macOS (Intel)`, `macOS (Apple Silicon)`, `Ubuntu 22.04`, `Ubuntu 24.04`, `Other Linux`, (c) `gpu` — input field, placeholder: `e.g., NVIDIA RTX 3060 12 GB`, (d) `vram` — dropdown with options: `4 GB`, `6 GB`, `8 GB`, `10 GB`, `12 GB`, `16 GB`, `24 GB+`. |
| FR-035 | The bug report form SHALL include optional fields: (a) `tessera_version` — input field, placeholder: `e.g., 0.1.0`, (b) `error_code` — input field, placeholder: `e.g., BF-E001`, (c) `screenshots` — textarea for pasting images, (d) `logs` — textarea with render type `pre` for log output. |
| FR-036 | The repository SHALL contain `.github/ISSUE_TEMPLATE/feature_request.yml` as a GitHub issue form with `name: "✨ Feature Request"` and the following fields: (a) `summary` — textarea, required, "Feature Summary", (b) `use_case` — textarea, required, "Use Case / Problem", (c) `proposed_solution` — textarea, optional, "Proposed Solution", (d) `alternatives` — textarea, optional, "Alternatives Considered". |

### 3.8 Pull Request Template (FR-037 – FR-038)

| ID | Requirement |
|----|-------------|
| FR-037 | The repository SHALL contain `.github/PULL_REQUEST_TEMPLATE.md` with the following sections: (a) "## Description" — placeholder for PR description, (b) "## Type of Change" — checkbox list: `[ ] Bug fix`, `[ ] New feature`, `[ ] Documentation`, `[ ] Refactor`, `[ ] CI/Build`, (c) "## Checklist" — checkbox list containing at minimum: `[ ] Tests pass (pytest)`, `[ ] Code formatted (black, isort)`, `[ ] Lint clean (flake8)`, `[ ] Conventional commit messages used`, `[ ] Documentation updated (if applicable)`, `[ ] GPL-2.0-or-later header on new files`. |
| FR-038 | The PR template checklist SHALL include: `[ ] Spec updated (if behavior changes)` to reinforce the Task → Spec → Implement workflow for contributors. |

### 3.9 FUNDING.yml (FR-039)

| ID | Requirement |
|----|-------------|
| FR-039 | The repository SHALL contain `.github/FUNDING.yml` with `custom` key containing placeholder URLs for marketplace listings: `["https://extensions.blender.org/tessera", "https://blendermarket.com/products/tessera"]`. The file MAY be updated with actual URLs once marketplace listings are live. |

### 3.10 Input Specifications

N/A — This spec produces static files. There are no runtime inputs.

### 3.11 Output Specifications

| Output | Type | Format | Location |
|--------|------|--------|----------|
| `LICENSE` | Text file | GPL-2.0-or-later full text, no file extension | Repository root |
| `README.md` | Markdown | GitHub-Flavored Markdown with badges, sections, code blocks | Repository root |
| `CONTRIBUTING.md` | Markdown | GitHub-Flavored Markdown with numbered steps, tables, code examples | Repository root |
| `CODE_OF_CONDUCT.md` | Markdown | Contributor Covenant v2.1 full text | Repository root |
| `SECURITY.md` | Markdown | GitHub-Flavored Markdown with tables | Repository root |
| `.gitignore` | Text file | One pattern per line, comments with `#` | Repository root |
| `bug_report.yml` | YAML | GitHub issue form schema v2 | `.github/ISSUE_TEMPLATE/` |
| `feature_request.yml` | YAML | GitHub issue form schema v2 | `.github/ISSUE_TEMPLATE/` |
| `PULL_REQUEST_TEMPLATE.md` | Markdown | GitHub PR template format with checkboxes | `.github/` |
| `FUNDING.yml` | YAML | GitHub Sponsors/Funding schema | `.github/` |

---

## 4. CONSTRAINTS

> ⚠️ **Critical for AI code generation.** These are hard prohibitions the AI must follow.

| ID | Constraint |
|----|------------|
| CON-001 | SHALL NOT use any license other than GPL-2.0-or-later for the `LICENSE` file. This is mandated by Blender's add-on distribution policy and PRD decision D6. |
| CON-002 | SHALL NOT exclude `specs/` or `tasks/` directories in `.gitignore`. Contributors need these directories to follow the Task → Spec → Implement workflow (CSO decision). |
| CON-003 | SHALL NOT include any active URLs to marketplace listings that do not yet exist. Use clearly marked placeholder URLs with `[coming soon]` annotations where actual URLs are not yet available. |
| CON-004 | SHALL NOT reference internal tooling paths (e.g., `.agent/` contents) in any user-facing documentation (README, CONTRIBUTING, SECURITY). The `.agent/` directory is excluded from the public repo via `.gitignore`. |
| CON-005 | SHALL NOT include any personal email addresses, phone numbers, or private contact information. Security and conduct reporting SHALL use placeholder project-specific email addresses. |
| CON-006 | SHALL NOT include any model weight files, binary artifacts, or large files in `.gitignore` exceptions for `tests/` that would bloat the repository. Test fixture `.npz` files (≤ 1 MB each per SPEC-TS-0011 CON-009) ARE tracked. |
| CON-007 | SHALL NOT deviate from Conventional Commits v1.0.0 format in CONTRIBUTING.md. The existing `Expansive-Labs-LLC/github-actions/versioning` action depends on this format for `semantic-release`. |

---

## 5. NON-FUNCTIONAL REQUIREMENTS

> ⚠️ **All NFRs must be quantified.** Replace vague terms with specific numbers.

| ID | Requirement | Metric | Target | Measurement Condition |
|----|-------------|--------|--------|----------------------|
| NFR-001 | README.md readability | Flesch-Kincaid grade level | ≤ 10 (accessible to high-school reading level) | Full README text excluding code blocks and badges, measured via `textstat` Python library or equivalent online calculator |
| NFR-002 | README.md length | Word count | 400–800 words (concise but comprehensive) | Full README text excluding code blocks |
| NFR-003 | CONTRIBUTING.md dev setup steps | Step count | ≤ 8 steps from clone to running tests | "Development Environment Setup" section |
| NFR-004 | Bug report form completion time | Minutes | ≤ 3 minutes for a user to fill out all required fields | User has bug details ready, filling out the form on github.com |
| NFR-005 | .gitignore effectiveness | Tracked file count | 0 generated/build artifacts committed to repository | After fresh clone and full build cycle |
| NFR-006 | GitHub license detection | Detection accuracy | GitHub displays "GPL-2.0-or-later" on repository page | Verified on github.com repository page after push |
| NFR-007 | README badge rendering | Badge display | All 4 badges render as visible images on github.com | Viewed on default branch |

---

## 6. ACCEPTANCE CRITERIA

> ⚠️ **Minimum 3 criteria in Given-When-Then format.** These drive test implementation.

### AC-001: License Consistency
**Given** the `LICENSE` file contains the GPL-2.0-or-later full text,  
**When** a reviewer compares the `LICENSE` file against the SPDX-License-Identifier headers in `tessera/__init__.py` and any 5 other `.py` files,  
**Then** the license identifier `GPL-2.0-or-later` is consistent across all files, and GitHub's license detection on the repository page displays "GPL-2.0-or-later".

### AC-002: README Dual-Audience Completeness
**Given** the `README.md` exists with all sections defined in FR-004 through FR-013,  
**When** a developer reads the README on github.com,  
**Then** the README contains: (a) a hero section with project name and tagline, (b) at least 4 rendered badges, (c) a features list with ≥ 8 items, (d) system requirements with GPU, VRAM, Blender version, and RAM specs, (e) both "Marketplace Install" and "Build from Source" install paths, (f) a quick-start section with ≤ 5 steps, (g) links to CONTRIBUTING.md, LICENSE, and SECURITY.md.

### AC-003: Conventional Commits Documented
**Given** the `CONTRIBUTING.md` exists with the "Commit Messages" section,  
**When** a contributor reads the commit conventions section,  
**Then** the section contains: (a) the `<type>(<scope>): <description>` format, (b) a table of ≥ 8 allowed commit types, (c) a note that Conventional Commits are mandatory for semantic-release, (d) at least 3 concrete example commit messages.

### AC-004: Bug Report Form Captures GPU Context
**Given** the `.github/ISSUE_TEMPLATE/bug_report.yml` exists,  
**When** a user creates a new issue on GitHub and selects "🐛 Bug Report",  
**Then** the form displays structured fields for: Blender version (dropdown), operating system (dropdown), GPU model (text input), VRAM (dropdown), and optional error code field — all rendering as a GitHub issue form (not a Markdown template).

### AC-005: .gitignore Excludes .agent/ But Keeps specs/ and tasks/
**Given** the `.gitignore` file exists with patterns defined in FR-028 through FR-031,  
**When** `git status` is run after a full development build (including `__pycache__/`, `.venv/`, `.pytest_cache/`),  
**Then** (a) `.agent/` is ignored, (b) `specs/` is tracked, (c) `tasks/` is tracked, (d) `__pycache__/` is ignored, (e) `.venv/` is ignored, (f) `*.blend1` is ignored, (g) `*.safetensors` is ignored.

### AC-006: PR Template Enforces Workflow
**Given** the `.github/PULL_REQUEST_TEMPLATE.md` exists,  
**When** a contributor opens a new pull request on GitHub,  
**Then** the PR description is pre-populated with: (a) a "Description" section, (b) a "Type of Change" checkbox list, (c) a checklist including items for tests, formatting, linting, conventional commits, documentation, GPL headers, and spec updates.

### AC-007: Security Policy Documents Local-Only Model
**Given** the `SECURITY.md` exists with sections defined in FR-024 through FR-027,  
**When** a security researcher reads the security policy,  
**Then** the document states: (a) all inference is local, (b) the only network activity is model weight downloads, (c) vulnerability reporting via GitHub Security Advisories with ≤ 5 business day acknowledgment SLA, (d) a supported versions table.

---

## 7. EDGE CASES

> ⚠️ **Minimum 2 edge cases required.** Document non-obvious scenarios AI might miss.

### EC-001: License Text Must Not Include "Version 3" Language
| Aspect | Detail |
|--------|--------|
| **Scenario** | The GPL has multiple versions. Using GPL-3.0 text instead of GPL-2.0 text would create an inconsistency with the `SPDX-License-Identifier: GPL-2.0-or-later` headers in all existing source files and bl_info. Blender itself is GPL-2.0-or-later, and mixing GPL-3.0-only with GPL-2.0-or-later code creates legal ambiguity. |
| **Input Example** | Accidentally using the GPL v3 preamble: "Version 3, 29 June 2007" instead of the GPL v2 preamble "Version 2, June 1991". |
| **Expected Behavior** | The `LICENSE` file SHALL contain the GPL version 2 text with the preamble dated "June 1991". The "or later" clause is conveyed by the individual file headers (`SPDX-License-Identifier: GPL-2.0-or-later`), not by the LICENSE file body. The LICENSE file body SHALL be the standard GPL-2.0 text. |
| **Test ID** | TS-001 |

### EC-002: .gitignore Must Not Exclude Golden-Mesh Test Fixtures
| Aspect | Detail |
|--------|--------|
| **Scenario** | The `.gitignore` broadly excludes binary/ML files (`*.pt`, `*.pth`, `*.safetensors`). However, golden-mesh test fixtures stored as `.npz` files in `tests/golden_meshes/` must be tracked in git (per SPEC-TS-0011 FR-024). An overly broad `.gitignore` could accidentally exclude test data. |
| **Input Example** | A `.gitignore` containing `*.npz` would exclude `tests/golden_meshes/mug_simple.npz`. |
| **Expected Behavior** | The `.gitignore` SHALL NOT contain patterns that match `.npz` files. Model weight extensions (`*.pt`, `*.pth`, `*.onnx`, `*.safetensors`, `*.bin`) SHALL be excluded, but `.npz` SHALL NOT appear in the exclusion list. |
| **Test ID** | TS-002 |

### EC-003: README Badges Must Work Before CI Exists
| Aspect | Detail |
|--------|--------|
| **Scenario** | The CI badge references `.github/workflows/ci.yml`, but this workflow is delivered by TASK-TS-0013 (CI/CD Pipeline), not this task. The badge will show "no status" or fail to render until CI is set up. |
| **Input Example** | Badge URL: `![CI](https://github.com/Expansive-Labs-LLC/tessera/actions/workflows/ci.yml/badge.svg)` when `ci.yml` does not yet exist. |
| **Expected Behavior** | The CI badge SHALL use the standard GitHub Actions badge URL format. If the workflow does not exist yet, GitHub renders a neutral gray badge (not a broken image). The README SHALL include an HTML/Markdown comment near the badge noting: `<!-- CI badge will activate once .github/workflows/ci.yml is added in TASK-TS-0013 -->`. |
| **Test ID** | TS-003 |

---

## 8. OUT OF SCOPE

> ⚠️ **Explicitly list what this feature does NOT include.** Prevents AI scope creep.

The following are explicitly **excluded** from this feature:

- ❌ CI/CD pipeline (`.github/workflows/`) — delivered by TASK-TS-0014
- ❌ GitHub Actions workflow files — delivered by TASK-TS-0014
- ❌ MkDocs documentation site (`docs/`, `mkdocs.yml`) — delivered by TASK-TS-0013
- ❌ Example gallery content — delivered by SPEC-TS-0011 FR-040
- ❌ `pyproject.toml` or `setup.py` — packaging configuration is separate from repo foundation
- ❌ GitHub repository settings (branch protection rules, required reviews, etc.) — manual configuration by repo admin
- ❌ Actual marketplace listings (Blender Extensions, Blender Market) — FUNDING.yml uses placeholder URLs
- ❌ `CHANGELOG.md` — auto-generated by `semantic-release` via the versioning GitHub Action
- ❌ Git hooks or pre-commit configuration — optional enhancement, not part of foundation
- ❌ GitHub Discussions setup — optional, can be enabled via repo settings later
- ❌ Internationalization (i18n) of any documentation — English only

---

## 9. SECURITY CONSIDERATIONS

> ⚠️ **Required for all features.** AI-generated code needs explicit security constraints.

### 9.1 Authentication & Authorization
| Aspect | Specification |
|--------|---------------|
| **Auth Required** | No — static repository files, no runtime behavior |
| **Auth Method** | None |
| **Required Permissions** | Repository write access to push files (GitHub user permission, handled by git) |
| **Rate Limiting** | N/A |

### 9.2 Data Classification
| Data Element | Classification | Handling Requirements |
|--------------|----------------|----------------------|
| License text | Public | Standard GPL-2.0 text, no restrictions |
| README content | Public | No sensitive information |
| CONTRIBUTING instructions | Public | No credentials, no internal URLs |
| Security reporting email | Public | Project-specific address only, no personal emails |
| FUNDING URLs | Public | Marketplace URLs, no financial data |

### 9.3 Security Requirements
| ID | Requirement |
|----|-------------|
| SEC-001 | SHALL NOT include any API keys, tokens, credentials, or secrets in any file. |
| SEC-002 | SHALL NOT include personal email addresses or phone numbers. Security and conduct reporting SHALL use project-specific placeholder addresses. |
| SEC-003 | SHALL NOT include internal infrastructure URLs, server addresses, or deployment details in any user-facing documentation. |
| SEC-004 | The `SECURITY.md` SHALL direct vulnerability reports to GitHub's private Security Advisories feature to prevent public disclosure of unpatched vulnerabilities. |
| SEC-005 | The `.gitignore` SHALL exclude `.env` files to prevent accidental commit of environment variables containing secrets. |

---

## 10. API CONTRACT [CONDITIONAL]

> **Skip** — This spec produces static files only. No APIs are exposed or consumed.

---

## 11. OBSERVABILITY

> N/A — Static files produce no runtime telemetry, logs, or metrics.

---

## 12. DEPLOYMENT CONSIDERATIONS

### 12.1 Feature Flag
| Aspect | Specification |
|--------|---------------|
| **Flag Name** | N/A — static files, always present |
| **Default State** | All files present in repository after push |
| **Rollout Plan** | Single commit or PR with all 9 deliverables; pushed to `main` branch |

### 12.2 Dependencies & Rollout Order
| Dependency | Must Deploy First | Notes |
|------------|-------------------|-------|
| GitHub repository `Expansive-Labs-LLC/tessera` | Yes | Already exists (empty). This spec provides the first push content. |
| No prior specs required | N/A | This is the Phase 5 foundation — all other Phase 5 tasks depend on it |

### 12.3 Rollback Plan
1. Revert the commit that adds the foundation files
2. The repository returns to empty state
3. No runtime impact — these are static configuration files

---

## 13. TEST SCENARIOS

> Map tests to acceptance criteria and edge cases for traceability.

| Test ID | Scenario | Type | Maps To | Priority |
|---------|----------|------|---------|----------|
| TS-001 | `LICENSE` file contains GPL-2.0 text (preamble dated "June 1991"), not GPL-3.0 | Manual | AC-001, EC-001 | Must Pass |
| TS-002 | `.gitignore` excludes `*.safetensors` but does NOT exclude `*.npz` | Manual | AC-005, EC-002 | Must Pass |
| TS-003 | README CI badge uses valid GitHub Actions badge URL format that degrades gracefully | Manual | AC-002, EC-003 | Must Pass |
| TS-004 | `LICENSE` SPDX matches headers in ≥ 5 source files | Script | AC-001 | Must Pass |
| TS-005 | `README.md` contains ≥ 8 feature bullet points | Manual | AC-002, FR-005 | Must Pass |
| TS-006 | `README.md` contains system requirements with GPU, VRAM ≥ 8 GB, Blender ≥ 4.2 | Manual | AC-002, FR-006 | Must Pass |
| TS-007 | `README.md` contains both "Marketplace Install" and "Build from Source" sections | Manual | AC-002, FR-007 | Must Pass |
| TS-008 | `CONTRIBUTING.md` "Commit Messages" section has ≥ 3 examples and type table with ≥ 8 types | Manual | AC-003, FR-015 | Must Pass |
| TS-009 | `bug_report.yml` is valid GitHub issue form YAML with required fields: description, steps, expected, actual, Blender version, OS, GPU, VRAM | Script | AC-004, FR-033, FR-034 | Must Pass |
| TS-010 | `feature_request.yml` is valid GitHub issue form YAML with required fields: summary, use_case | Script | FR-036 | Must Pass |
| TS-011 | `.gitignore` excludes `.agent/` but does NOT exclude `specs/` or `tasks/` | Script | AC-005, FR-031 | Must Pass |
| TS-012 | `PULL_REQUEST_TEMPLATE.md` contains checklist with ≥ 7 items including spec update checkbox | Manual | AC-006, FR-037, FR-038 | Must Pass |
| TS-013 | `SECURITY.md` states local-only inference and ≤ 5 business day response SLA | Manual | AC-007, FR-024, FR-025 | Must Pass |
| TS-014 | `CODE_OF_CONDUCT.md` contains Contributor Covenant v2.1 text with customized contact | Manual | FR-022, FR-023 | Must Pass |
| TS-015 | `FUNDING.yml` contains valid YAML with `custom` key listing marketplace placeholder URLs | Script | FR-039 | Must Pass |
| TS-016 | `CONTRIBUTING.md` dev setup section has ≤ 8 numbered steps | Manual | NFR-003, FR-014 | Must Pass |
| TS-017 | `CONTRIBUTING.md` includes GPL header copy-paste template | Manual | FR-020 | Must Pass |
| TS-018 | `README.md` word count is between 400–800 words (excluding code blocks) | Script | NFR-002 | Should Pass |

> **Note on "Script" tests:** Script-type tests (TS-004, TS-009, TS-010, TS-011, TS-015, TS-018) are one-off verification scripts run by the implementor during review. They do not need to be committed to the repository as part of the test suite.

---

## 14. DEPENDENCIES

### 14.1 Internal Dependencies
| Dependency | Type | Status | Owner | Blocked? |
|------------|------|--------|-------|----------|
| SPEC-TS-0001 through SPEC-TS-0011 (all Phase 1–4 specs) | Reference | Complete / In Progress | Tessera | No — README feature list references implemented capabilities |
| PRD-001_Tessera.md | Reference | Available | Derek | No — README content sourced from PRD §1, §2, §3, §6, §8 |
| `tessera/__init__.py` bl_info | Reference | Available | Tessera | No — version and license info for README and CONTRIBUTING |
| `Expansive-Labs-LLC/github-actions/versioning` | Reference | Available | Expansive Labs | No — Conventional Commits format documented in CONTRIBUTING |

### 14.2 External Dependencies
| Dependency | Type | Documentation | Fallback |
|------------|------|---------------|----------|
| GPL-2.0-or-later license text | Required | [gnu.org/licenses](https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt) | N/A — canonical source |
| Contributor Covenant v2.1 | Required | [contributor-covenant.org](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) | N/A — canonical source |
| GitHub issue form schema | Required | [docs.github.com](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) | Fall back to Markdown issue templates |
| GitHub FUNDING.yml schema | Required | [docs.github.com](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/displaying-a-sponsor-button-in-your-repository) | N/A |
| shields.io badge service | Optional | [shields.io](https://shields.io/) | Use GitHub's native badge URLs |

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
| SHALL/SHOULD/MAY requirements | 20 | 20 | 39 requirements (FR-001 – FR-039) with precise SHALL/SHOULD/MAY language |
| Quantified NFRs | 15 | 15 | 7 NFRs quantified with measurement tools specified (word count range, step count, grade level via `textstat`, completion time, file count, detection accuracy, badge count) |
| Given-When-Then criteria (3+) | 20 | 20 | 7 acceptance criteria in Given-When-Then format with specific values |
| Edge cases (2+) | 15 | 15 | 3 edge cases with concrete input examples and expected behaviors |
| Out of scope defined | 10 | 10 | 11 explicit exclusions with cross-references to other tasks |
| Security constraints | 10 | 10 | 5 security requirements + data classification table |
| No ambiguous language | 10 | 10 | All ambiguous terms resolved; FR-019 .agent/ contradiction fixed |
| **TOTAL** | **100** | **92** | **Target: ≥80 ✅ (independent review score)** |

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
- [x] "fast" / "efficient" / "performant" → not used
- [x] "secure" → replaced with SEC-001 through SEC-005
- [x] "user-friendly" / "intuitive" / "seamless" → not used
- [x] "robust" / "reliable" → not used
- [x] "reasonable" / "adequate" / "sufficient" → not used
- [x] "optimized" → not used

---

## VERSION HISTORY

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-04-16 | Orchestrator (AI) | Initial draft |
| 1.1 | 2026-04-16 | Antigravity (AI) | Spec review fixes: corrected .releaserc.yml plugin list (MAJ-001), resolved CON-004/FR-019 contradiction (MAJ-002), embedded GPL header in FR-020 (MIN-001), acknowledged tagline divergence (MIN-002), clarified script tests (MIN-003), specified Flesch-Kincaid measurement tool (MIN-004) |
| 1.2 | 2026-04-17 | Antigravity (AI) | Second review fixes: added extended commit types `spec`/`task` note to FR-015 (MIN-001), corrected TASK ID cross-references in out-of-scope — CI/CD→TASK-TS-0014, docs→TASK-TS-0013 (MIN-002), adjusted self-score to match independent review (92/100) |

---

**File Location:** `specs/tessera/feature-spec/active/SPEC-TS-0012-repo-foundation.md`
