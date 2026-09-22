# SPDX-License-Identifier: GPL-2.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for SPEC-TS-0013: Comprehensive User Manual & Documentation Site.

Each test maps to a Test Scenario (TS-XXX) from the spec's §13.

Tests can be run standalone with:
    pytest tests/test_user_manual_docs.py -v

Documentation content tests read files from disk directly.
Python code tests (TS-011, TS-012) use the ``bpy`` mock from conftest.py.
"""

import re
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DOCS_ROOT = _PROJECT_ROOT / "docs" / "docs"
_MKDOCS_YML = _PROJECT_ROOT / "docs" / "mkdocs.yml"
_REQUIREMENTS_TXT = _PROJECT_ROOT / "docs" / "requirements.txt"
_USER_GUIDE_DIR = _DOCS_ROOT / "user-guide"
_REFERENCE_DIR = _DOCS_ROOT / "reference"
_SCREENSHOTS_README = _DOCS_ROOT / "assets" / "screenshots" / "README.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    """Read a file as UTF-8 text."""
    return path.read_text(encoding="utf-8")


def _count_h2(text: str) -> int:
    """Count ``## `` headings in *text* (not ``###`` or deeper)."""
    return len(re.findall(r"^## ", text, re.MULTILINE))


def _count_h3(text: str) -> int:
    """Count ``### `` headings in *text*."""
    return len(re.findall(r"^### ", text, re.MULTILINE))


def _parse_mkdocs_nav(yml_path: Path) -> list:
    """Parse the ``nav`` key from a mkdocs.yml that may contain !ENV tags.

    The ``!ENV`` YAML tag used by MkDocs is not understood by the
    standard PyYAML loader, so we add a custom constructor that simply
    returns the default value from the ``[KEY, default]`` list.
    """

    class _Loader(yaml.SafeLoader):
        pass

    def _env_constructor(loader, node):
        value = loader.construct_sequence(node)
        # !ENV [VAR_NAME, default] → return the default
        if isinstance(value, list) and len(value) == 2:
            return value[1]
        return value

    _Loader.add_constructor("!ENV", _env_constructor)

    with open(yml_path, "r", encoding="utf-8") as fh:
        cfg = yaml.load(fh, Loader=_Loader)  # noqa: S506
    return cfg.get("nav", [])


# ---------------------------------------------------------------------------
# TestExistingPagePreservation (TS-001, EC-001, CON-008)
# ---------------------------------------------------------------------------
class TestExistingPagePreservation:
    """TS-001: All existing page filenames are preserved."""

    # Pages that existed prior to SPEC-TS-0013 and MUST NOT be removed.
    PRESERVED_PAGES = [
        "index.md",
        "installation.md",
        "quickstart.md",
        "troubleshooting.md",
        "user-guide/image-input.md",
        "user-guide/reconstruction.md",
        "user-guide/refinement.md",
        "user-guide/export.md",
        "api/pipeline.md",
        "api/adapters.md",
        "gallery/index.md",
    ]

    @pytest.mark.parametrize("page", PRESERVED_PAGES)
    def test_TS001_existing_page_exists(self, page):
        """TS-001 → EC-001, CON-008: Existing page file is preserved.

        Given: The documentation site had a page at ``docs/docs/{page}``
        When:  The SPEC-TS-0013 implementation is applied
        Then:  The file still exists at the same path.

        Type: Script | Priority: Must Pass
        """
        # Given / When
        full_path = _DOCS_ROOT / page

        # Then
        assert (
            full_path.exists()
        ), f"Preserved page '{page}' is missing — CON-008 violation"

    def test_TS016_total_page_count_ge_18(self):
        """TS-016 → NFR-002: Total .md page count in docs/docs/ is ≥ 18.

        Given: The complete documentation directory
        When:  All .md files are counted
        Then:  The count is at least 18.

        Type: Script | Priority: Must Pass
        """
        # Given / When
        md_files = list(_DOCS_ROOT.rglob("*.md"))

        # Then
        assert len(md_files) >= 18, f"Expected ≥ 18 .md pages, found {len(md_files)}"


# ---------------------------------------------------------------------------
# TestMkDocsConfig (TS-002, TS-004, TS-013, FR-001 – FR-005)
# ---------------------------------------------------------------------------
class TestMkDocsConfig:
    """Tests for MkDocs configuration (TS-002, TS-004, TS-013)."""

    def test_TS002_git_dates_fallback_configured(self):
        """TS-002 → EC-002: git-revision-date-localized has fallback_to_build_date.

        Given: ``docs/mkdocs.yml`` configures the git-dates plugin
        When:  Running ``mkdocs build`` in a shallow clone without git history
        Then:  The plugin falls back gracefully because
               ``fallback_to_build_date: true`` is set.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_MKDOCS_YML)

        # Then
        assert (
            "fallback_to_build_date: true" in content
        ), "git-revision-date-localized must have fallback_to_build_date: true"

    def test_TS002_git_dates_env_toggle(self):
        """TS-002 (ext): git-dates plugin can be disabled via ENABLE_GIT_DATES env.

        Given: ``docs/mkdocs.yml`` configures the git-dates plugin
        When:  ``ENABLE_GIT_DATES`` environment variable is set to ``false``
        Then:  Plugin is disabled (configured via ``!ENV``).

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_MKDOCS_YML)

        # Then
        assert (
            "ENABLE_GIT_DATES" in content
        ), "git-dates plugin must support !ENV [ENABLE_GIT_DATES, ...] toggle"

    def test_TS013_nav_has_7_top_level_sections(self):
        """TS-013 → AC-007, FR-001: mkdocs.yml nav has 7 top-level sections.

        Given: The mkdocs.yml nav structure
        When:  Top-level items are counted
        Then:  There are exactly 7 sections.

        Type: Script | Priority: Must Pass
        """
        # Given
        nav = _parse_mkdocs_nav(_MKDOCS_YML)

        # Then
        assert len(nav) == 7, (
            f"Expected 7 top-level nav sections, found {len(nav)}: "
            f"{[list(x.keys())[0] if isinstance(x, dict) else x for x in nav]}"
        )

    def test_TS013_nav_section_names(self):
        """TS-013 (ext): Nav section names match spec FR-001 exactly.

        Given: The mkdocs.yml nav structure
        When:  Section names are extracted
        Then:  They are: Home, Getting Started, User Guide, Reference,
               FAQ, API Reference, Gallery.

        Type: Script | Priority: Must Pass
        """
        # Given
        nav = _parse_mkdocs_nav(_MKDOCS_YML)

        # When
        names = []
        for item in nav:
            if isinstance(item, dict):
                names.append(list(item.keys())[0])
            elif isinstance(item, str):
                names.append(item)

        # Then
        expected = [
            "Home",
            "Getting Started",
            "User Guide",
            "Reference",
            "FAQ",
            "API Reference",
            "Gallery",
        ]
        assert names == expected, (
            f"Nav section names mismatch.\n"
            f"Expected: {expected}\n"
            f"Got:      {names}"
        )

    def test_FR003_site_url_correct(self):
        """FR-003: site_url is the correct GitHub Pages domain.

        Given: The mkdocs.yml configuration
        When:  ``site_url`` is read
        Then:  It matches ``https://expansive-labs-llc.github.io/tessera/``.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_MKDOCS_YML)

        # Then
        assert "site_url: https://expansive-labs-llc.github.io/tessera/" in content

    def test_FR004_plugins_present(self):
        """FR-004: Required plugins are configured.

        Given: The mkdocs.yml configuration
        When:  Plugin list is inspected
        Then:  ``search``, ``glightbox``, and ``git-revision-date-localized``
               are all present.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_MKDOCS_YML)

        # Then
        assert "- search" in content
        assert "- glightbox" in content
        assert "- git-revision-date-localized:" in content

    def test_FR005_markdown_extensions_present(self):
        """FR-005: Required markdown extensions are configured.

        Given: The mkdocs.yml configuration
        When:  Extensions list is inspected
        Then:  All required extensions are present.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_MKDOCS_YML)

        # Then
        required_extensions = [
            "admonition",
            "pymdownx.details",
            "pymdownx.superfences",
            "pymdownx.highlight",
            "pymdownx.tabbed",
            "pymdownx.keys",
            "attr_list",
            "md_in_html",
            "toc",
        ]
        for ext in required_extensions:
            assert ext in content, f"Missing markdown extension: {ext}"


# ---------------------------------------------------------------------------
# TestRequirementsTxt (TS-014, FR-006)
# ---------------------------------------------------------------------------
class TestRequirementsTxt:
    """TS-014: docs/requirements.txt exists with ≥ 4 dependencies."""

    def test_TS014_requirements_file_exists(self):
        """TS-014 → FR-006: requirements.txt exists.

        Given: The docs/ directory
        When:  Checking for requirements.txt
        Then:  The file exists.

        Type: Script | Priority: Must Pass
        """
        assert _REQUIREMENTS_TXT.exists(), "docs/requirements.txt is missing"

    def test_TS014_requirements_has_ge_4_deps(self):
        """TS-014 → FR-006: requirements.txt lists ≥ 4 dependencies.

        Given: The docs/requirements.txt file
        When:  Non-empty, non-comment lines are counted
        Then:  There are at least 4 dependency lines.

        Type: Script | Priority: Must Pass
        """
        # Given
        lines = [
            line.strip()
            for line in _read(_REQUIREMENTS_TXT).splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        # Then
        assert (
            len(lines) >= 4
        ), f"Expected ≥ 4 dependencies, found {len(lines)}: {lines}"

    @pytest.mark.parametrize(
        "dep",
        ["mkdocs", "mkdocs-material", "mkdocs-glightbox", "mkdocs-git-revision-date"],
    )
    def test_TS014_required_dependency_present(self, dep):
        """TS-014 (ext): Each required dependency is listed.

        Given: The docs/requirements.txt file
        When:  Searching for the dependency name prefix
        Then:  The dependency is found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_REQUIREMENTS_TXT)

        # Then
        assert dep in content, f"Missing required dependency: {dep}"


# ---------------------------------------------------------------------------
# TestQuickstart (TS-005, AC-002, FR-015 – FR-017, NFR-004)
# ---------------------------------------------------------------------------
class TestQuickstart:
    """TS-005: quickstart.md contains ≤ 5 numbered steps."""

    def test_TS005_quickstart_le_5_steps(self):
        """TS-005 → AC-002, FR-015, NFR-004: Quickstart has ≤ 5 steps.

        Given: The quickstart.md page
        When:  ``## Step`` headings are counted
        Then:  There are at most 5 steps.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "quickstart.md")

        # When
        step_count = len(re.findall(r"^## Step", content, re.MULTILINE))

        # Then
        assert step_count <= 5, f"Quickstart has {step_count} steps (max 5)"
        assert step_count >= 1, "Quickstart has no steps at all"

    def test_FR016_each_step_has_screenshot_placeholder(self):
        """FR-016: Each quickstart step has a screenshot placeholder.

        Given: The quickstart.md page
        When:  Screenshot placeholders are matched to steps
        Then:  Each step references a ``quickstart-step`` image.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "quickstart.md")

        # When
        screenshots = re.findall(r"!\[.*?\]\(.*?quickstart-step\d+\.png\)", content)

        # Then
        step_count = len(re.findall(r"^## Step", content, re.MULTILINE))
        assert (
            len(screenshots) >= step_count
        ), f"Expected ≥ {step_count} quickstart screenshots, found {len(screenshots)}"

    def test_FR017_next_steps_section_exists(self):
        """FR-017: Quickstart has a 'Next Steps' section linking to ≥ 3 pages.

        Given: The quickstart.md page
        When:  The 'Next Steps' section is located
        Then:  It contains at least 3 links to other pages.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "quickstart.md")

        # Then
        assert (
            "## Next Steps" in content or "## What's Next" in content
        ), "Quickstart is missing a 'Next Steps' section"
        # Count markdown links after the Next Steps heading
        next_steps_match = re.split(
            r"^## (?:Next Steps|What's Next)", content, flags=re.MULTILINE
        )
        assert len(next_steps_match) >= 2, "Could not locate Next Steps section"
        links = re.findall(r"\[.*?\]\(.*?\.md.*?\)", next_steps_match[-1])
        assert len(links) >= 3, f"Next Steps has {len(links)} links (need ≥ 3)"


# ---------------------------------------------------------------------------
# TestUserGuide (TS-006, TS-017, AC-003, FR-018, FR-027 – FR-029)
# ---------------------------------------------------------------------------
class TestUserGuide:
    """TS-006, TS-017: User guide page count and cross-linking."""

    EXPECTED_PAGES = [
        "image-input.md",
        "reconstruction.md",
        "sketch-to-3d.md",
        "mesh-cleanup.md",
        "scaling-orientation.md",
        "refinement.md",
        "export.md",
        "preferences.md",
    ]

    def test_TS006_user_guide_has_exactly_8_pages(self):
        """TS-006 → AC-003, FR-018: User-guide contains exactly 8 .md files.

        Given: The user-guide directory
        When:  .md files are counted
        Then:  There are exactly 8 files.

        Type: Script | Priority: Must Pass
        """
        # Given / When
        md_files = sorted(f.name for f in _USER_GUIDE_DIR.glob("*.md"))

        # Then
        assert (
            len(md_files) == 8
        ), f"Expected 8 user-guide pages, found {len(md_files)}: {md_files}"

    @pytest.mark.parametrize("page", EXPECTED_PAGES)
    def test_TS006_expected_page_exists(self, page):
        """TS-006 (ext): Each expected user-guide page exists.

        Given: The user-guide directory
        When:  Checking for ``{page}``
        Then:  The file exists.

        Type: Script | Priority: Must Pass
        """
        assert (_USER_GUIDE_DIR / page).exists(), f"Missing user-guide page: {page}"

    @pytest.mark.parametrize("page", EXPECTED_PAGES)
    def test_TS017_user_guide_page_has_see_also(self, page):
        """TS-017 → FR-027, NFR-006: Each user-guide page has a See Also section.

        Given: A user-guide page
        When:  The content is searched for a 'See Also' heading
        Then:  The heading exists.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_USER_GUIDE_DIR / page)

        # Then
        assert "## See Also" in content, f"'{page}' is missing a '## See Also' section"

    @pytest.mark.parametrize("page", EXPECTED_PAGES)
    def test_FR028_user_guide_page_has_admonition(self, page):
        """FR-028: Each user-guide page has ≥ 1 admonition.

        Given: A user-guide page
        When:  The content is searched for admonition markers
        Then:  At least one admonition is found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_USER_GUIDE_DIR / page)

        # Then — admonitions start with !!! or ???
        admonitions = re.findall(r"^(?:!!!|\?\?\?)\s+\w+", content, re.MULTILINE)
        assert len(admonitions) >= 1, f"'{page}' has no admonitions (need ≥ 1)"

    @pytest.mark.parametrize("page", EXPECTED_PAGES)
    def test_FR029_user_guide_page_has_screenshot_placeholder(self, page):
        """FR-029: Each user-guide page has ≥ 1 screenshot placeholder.

        Given: A user-guide page
        When:  Content is searched for image references to assets/screenshots/
        Then:  At least one placeholder is found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_USER_GUIDE_DIR / page)

        # Then
        screenshots = re.findall(r"!\[.*?\]\(.*?assets/screenshots/.*?\.png\)", content)
        assert len(screenshots) >= 1, f"'{page}' has no screenshot placeholders"


# ---------------------------------------------------------------------------
# TestScreenshotAltText (TS-003, EC-003, FR-029)
# ---------------------------------------------------------------------------
class TestScreenshotAltText:
    """TS-003: All screenshot placeholders have descriptive alt text (≥ 10 words)."""

    def test_TS003_all_screenshot_alts_ge_10_words(self):
        """TS-003 → EC-003, FR-029: Screenshot alt text is ≥ 10 words.

        Given: All .md files in docs/docs/
        When:  Screenshot image references are extracted
        Then:  Every alt text contains ≥ 10 words.

        Type: Script | Priority: Must Pass
        """
        # Given
        violations = []
        for md_file in _DOCS_ROOT.rglob("*.md"):
            content = _read(md_file)
            # Match ![alt text](path/to/screenshot.png)
            for match in re.finditer(
                r"!\[([^\]]*)\]\([^)]*assets/screenshots/[^)]*\.png\)", content
            ):
                alt_text = match.group(1)
                word_count = len(alt_text.split())
                if word_count < 10:
                    rel_path = md_file.relative_to(_DOCS_ROOT)
                    violations.append(
                        f"  {rel_path}: alt='{alt_text}' ({word_count} words)"
                    )

        # Then
        assert not violations, "Screenshot alt text must be ≥ 10 words:\n" + "\n".join(
            violations
        )


# ---------------------------------------------------------------------------
# TestViewLabels (TS-007, AC-004, FR-030)
# ---------------------------------------------------------------------------
class TestViewLabels:
    """TS-007: view-labels.md contains all 10 view labels from PRD §6."""

    REQUIRED_LABELS = [
        "front",
        "back",
        "left",
        "right",
        "top",
        "bottom",
        "front-left",
        "front-right",
        "isometric",
        "custom",
    ]

    @pytest.mark.parametrize("label", REQUIRED_LABELS)
    def test_TS007_view_label_present(self, label):
        """TS-007 → AC-004, FR-030: View label '{label}' is documented.

        Given: The view-labels.md reference page
        When:  Searching for the label in a table row
        Then:  The label is present.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_REFERENCE_DIR / "view-labels.md")

        # Then — label should appear as a code span in a table row
        assert (
            f"`{label}" in content
        ), f"View label '{label}' not found in view-labels.md"

    def test_TS007_view_labels_table_columns(self):
        """TS-007 (ext): View labels table has required columns.

        Given: The view-labels.md reference page
        When:  Table header is inspected
        Then:  Columns include Label, Camera Direction, Azimuth, Elevation.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_REFERENCE_DIR / "view-labels.md").lower()

        # Then
        assert "label" in content
        assert "azimuth" in content
        assert "elevation" in content


# ---------------------------------------------------------------------------
# TestGlossary (TS-008, AC-004, FR-034, NFR-007)
# ---------------------------------------------------------------------------
class TestGlossary:
    """TS-008: glossary.md contains ≥ 25 defined terms."""

    # 8 terms from PRD §13 that must be present.
    PRD_TERMS = [
        "Manifold",
        "Watertight",
        "FDM",
        "SLA",
        "STL",
        "3MF",
        "Slicer",
    ]

    def test_TS008_glossary_ge_25_terms(self):
        """TS-008 → AC-004, NFR-007: Glossary has ≥ 25 terms.

        Given: The glossary.md reference page
        When:  ``## `` headings are counted
        Then:  There are at least 25 terms.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_REFERENCE_DIR / "glossary.md")

        # When
        term_count = _count_h2(content)

        # Then
        assert term_count >= 25, f"Glossary has {term_count} terms (need ≥ 25)"

    @pytest.mark.parametrize("term", PRD_TERMS)
    def test_TS008_prd_glossary_term_present(self, term):
        """TS-008 (ext): PRD §13 term '{term}' is in the glossary.

        Given: The glossary.md reference page
        When:  Searching for the term as a heading
        Then:  The term is found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_REFERENCE_DIR / "glossary.md")

        # Then
        assert (
            f"## {term}" in content
        ), f"PRD glossary term '{term}' missing from glossary.md"


# ---------------------------------------------------------------------------
# TestFAQ (TS-009, TS-010, AC-005, FR-036 – FR-038, NFR-005)
# ---------------------------------------------------------------------------
class TestFAQ:
    """TS-009, TS-010: FAQ question count and required questions."""

    # The 10 specific questions from FR-038 (matched by substring).
    REQUIRED_QUESTIONS = [
        "GPU do I need",
        "send my data to the cloud",
        "image formats are supported",
        "GPU Memory Exhausted",
        "manifold mesh",
        "without a GPU",
        "update Tessera",
        "difference between STL and 3MF",
        "report a bug",
        "work on macOS",
    ]

    def test_TS009_faq_ge_15_questions(self):
        """TS-009 → AC-005, NFR-005: FAQ has ≥ 15 questions.

        Given: The faq.md page
        When:  ``### `` headings are counted (questions)
        Then:  There are at least 15.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "faq.md")

        # When  — questions use ### headings
        question_count = _count_h3(content)

        # Then
        assert question_count >= 15, f"FAQ has {question_count} questions (need ≥ 15)"

    @pytest.mark.parametrize("substring", REQUIRED_QUESTIONS)
    def test_TS010_required_question_present(self, substring):
        """TS-010 → FR-038: FAQ contains the required question about '{substring}'.

        Given: The faq.md page
        When:  Searching for the question substring (case-insensitive)
        Then:  It is found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "faq.md").lower()

        # Then
        assert (
            substring.lower() in content
        ), f"Required FAQ question containing '{substring}' is missing"

    def test_FR036_faq_has_4_categories(self):
        """FR-036: FAQ is organized into 4 categories.

        Given: The faq.md page
        When:  ``## `` category headings are counted
        Then:  There are at least 4 categories.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "faq.md")

        # When — categories use ## headings (excl. title)
        h2_headings = re.findall(r"^## .+", content, re.MULTILINE)
        # Filter out the page title (usually "# FAQ" not "## FAQ")
        category_count = len(h2_headings)

        # Then
        assert (
            category_count >= 4
        ), f"FAQ has {category_count} categories (need ≥ 4): {h2_headings}"


# ---------------------------------------------------------------------------
# TestScreenshotManifest (TS-015, FR-041, FR-042)
# ---------------------------------------------------------------------------
class TestScreenshotManifest:
    """TS-015: Screenshot manifest lists ≥ 15 screenshots."""

    def test_TS015_manifest_exists(self):
        """TS-015 → FR-041: Screenshot manifest file exists.

        Given: The assets/screenshots/ directory
        When:  Checking for README.md
        Then:  The file exists.

        Type: Script | Priority: Must Pass
        """
        assert (
            _SCREENSHOTS_README.exists()
        ), "docs/docs/assets/screenshots/README.md is missing"

    def test_TS015_manifest_ge_15_screenshots(self):
        """TS-015 → FR-042: Manifest lists ≥ 15 screenshots.

        Given: The screenshot manifest (README.md)
        When:  Unique .png filenames are counted
        Then:  There are at least 15 unique screenshots.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_SCREENSHOTS_README)

        # When — find all unique .png filenames
        png_files = set(re.findall(r"\b[\w-]+\.png\b", content))

        # Then
        assert len(png_files) >= 15, (
            f"Manifest lists {len(png_files)} screenshots (need ≥ 15): "
            f"{sorted(png_files)}"
        )


# ---------------------------------------------------------------------------
# TestBlInfoDocUrl (TS-011, AC-006, FR-044)
# ---------------------------------------------------------------------------
class TestBlInfoDocUrl:
    """TS-011: bl_info['doc_url'] is set to the correct URL."""

    def test_TS011_bl_info_doc_url(self, mock_bpy):
        """TS-011 → AC-006, FR-044: bl_info doc_url is correct.

        Given: The tessera __init__.py module
        When:  bl_info['doc_url'] is inspected
        Then:  It equals 'https://expansive-labs-llc.github.io/tessera/'.

        Type: Script | Priority: Must Pass
        """
        # Given
        from tessera import bl_info

        # Then
        assert bl_info["doc_url"] == "https://expansive-labs-llc.github.io/tessera/", (
            f"bl_info['doc_url'] = '{bl_info['doc_url']}' — expected "
            "'https://expansive-labs-llc.github.io/tessera/'"
        )


# ---------------------------------------------------------------------------
# TestHelpPanel (TS-012, AC-006, FR-043, SEC-003)
# ---------------------------------------------------------------------------
class TestHelpPanel:
    """TS-012: help_panel.py uses url_open with the docs URL."""

    def test_TS012_docs_url_constant(self, mock_bpy):
        """TS-012 → FR-043: _DOCS_URL constant uses correct domain.

        Given: The help_panel.py module
        When:  _DOCS_URL is inspected
        Then:  It uses the 'expansive-labs-llc.github.io' domain.

        Type: Script | Priority: Must Pass
        """
        # Given
        from tessera.ui.help_panel import _DOCS_URL

        # Then
        assert (
            _DOCS_URL == "https://expansive-labs-llc.github.io/tessera/"
        ), f"_DOCS_URL = '{_DOCS_URL}' — wrong domain"

    def test_TS012_quickstart_url_constant(self, mock_bpy):
        """TS-012 (ext): _QUICKSTART_URL constant uses correct domain.

        Given: The help_panel.py module
        When:  _QUICKSTART_URL is inspected
        Then:  It uses the 'expansive-labs-llc.github.io' domain.

        Type: Script | Priority: Must Pass
        """
        # Given
        from tessera.ui.help_panel import _QUICKSTART_URL

        # Then
        assert _QUICKSTART_URL == (
            "https://expansive-labs-llc.github.io/tessera/quickstart/"
        )

    def test_SEC003_docs_url_is_hardcoded_https(self, mock_bpy):
        """SEC-003: _DOCS_URL is hardcoded HTTPS, not from user input.

        Given: The help_panel.py source code
        When:  _DOCS_URL assignment is inspected
        Then:  It is a string literal starting with ``https://``.

        Type: Script | Priority: Must Pass
        """
        # Given — read the source file directly
        source = _read(_PROJECT_ROOT / "tessera" / "ui" / "help_panel.py")

        # Then — verify the URL is a hardcoded string literal, not dynamic
        assert (
            '_DOCS_URL = "https://' in source
        ), "_DOCS_URL must be a hardcoded HTTPS string literal"

    def test_TS012_help_panel_uses_url_open(self, mock_bpy):
        """TS-012 → FR-043: Help panel uses wm.url_open operator.

        Given: The help_panel.py source code
        When:  Searching for wm.url_open usage
        Then:  The operator is used to open the docs URL.

        Type: Script | Priority: Must Pass
        """
        # Given
        source = _read(_PROJECT_ROOT / "tessera" / "ui" / "help_panel.py")

        # Then
        assert "wm.url_open" in source, "help_panel.py must use 'wm.url_open' operator"
        assert "_DOCS_URL" in source, "help_panel.py must reference _DOCS_URL"


# ---------------------------------------------------------------------------
# TestSecurityCompliance (TS-020, SEC-001, SEC-002)
# ---------------------------------------------------------------------------
class TestSecurityCompliance:
    """TS-020: No personal paths or credentials in documentation."""

    def test_TS020_no_personal_home_paths(self):
        """TS-020 → SEC-002: No /home/derek/ paths in docs.

        Given: All .md files in docs/docs/
        When:  Each file is searched for '/home/derek/'
        Then:  Zero matches are found.

        Type: Script | Priority: Must Pass
        """
        # Given
        violations = []
        for md_file in _DOCS_ROOT.rglob("*.md"):
            content = _read(md_file)
            if "/home/derek/" in content:
                rel_path = md_file.relative_to(_DOCS_ROOT)
                violations.append(str(rel_path))

        # Then
        assert not violations, f"Personal paths found in: {violations}"

    def test_TS020_no_windows_user_paths(self):
        """TS-020 (ext) → SEC-002: No C:\\Users\\derek paths in docs.

        Given: All .md files in docs/docs/
        When:  Each file is searched for personal Windows paths
        Then:  Zero matches are found.

        Type: Script | Priority: Must Pass
        """
        # Given
        violations = []
        for md_file in _DOCS_ROOT.rglob("*.md"):
            content = _read(md_file)
            if "Users\\derek" in content or "Users/derek" in content:
                violations.append(str(md_file.relative_to(_DOCS_ROOT)))

        # Then
        assert not violations, f"Personal Windows paths found in: {violations}"

    def test_SEC001_no_api_keys_in_docs(self):
        """SEC-001: No API keys or secrets in documentation.

        Given: All .md files in docs/docs/
        When:  Searching for common secret patterns
        Then:  No matches found.

        Type: Script | Priority: Must Pass
        """
        # Given
        secret_patterns = [
            r"sk-[a-zA-Z0-9]{20,}",  # OpenAI API key
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub PAT
            r"AKIA[0-9A-Z]{16}",  # AWS access key
            r"(?i)api[_-]?key\s*[:=]\s*['\"][a-zA-Z0-9]{16,}",
        ]
        violations = []
        for md_file in _DOCS_ROOT.rglob("*.md"):
            content = _read(md_file)
            for pattern in secret_patterns:
                if re.search(pattern, content):
                    violations.append(
                        f"{md_file.relative_to(_DOCS_ROOT)}: "
                        f"matches pattern '{pattern}'"
                    )

        # Then
        assert not violations, "Potential secrets found:\n" + "\n".join(violations)

    def test_SEC004_no_script_tags_in_docs(self):
        """SEC-004: No <script> tags in documentation.

        Given: All .md files in docs/docs/
        When:  Searching for ``<script`` tags
        Then:  No matches found (MkDocs Material sanitizes, but content
               should also avoid them).

        Type: Script | Priority: Must Pass
        """
        # Given
        violations = []
        for md_file in _DOCS_ROOT.rglob("*.md"):
            content = _read(md_file).lower()
            if "<script" in content:
                violations.append(str(md_file.relative_to(_DOCS_ROOT)))

        # Then
        assert not violations, f"<script> tags found in: {violations}"

    def test_CON004_no_agent_dir_references(self):
        """CON-004: No references to .agent/ directory in docs.

        Given: All .md files in docs/docs/
        When:  Searching for '.agent/' references
        Then:  No matches found.

        Type: Script | Priority: Must Pass
        """
        # Given
        violations = []
        for md_file in _DOCS_ROOT.rglob("*.md"):
            content = _read(md_file)
            if ".agent/" in content:
                violations.append(str(md_file.relative_to(_DOCS_ROOT)))

        # Then
        assert not violations, f".agent/ references found in: {violations}"


# ---------------------------------------------------------------------------
# TestInstallationContent (TS-018, TS-019, FR-011, FR-012, FR-014)
# ---------------------------------------------------------------------------
class TestInstallationContent:
    """TS-018, TS-019: Installation page content validation."""

    def test_TS018_vram_requirements_table(self):
        """TS-018 → FR-012: Installation has a VRAM requirements table.

        Given: The installation.md page
        When:  Content is searched for 'VRAM' and a table structure
        Then:  A VRAM table with at least 4 rows is found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "installation.md")

        # Then
        assert "VRAM" in content, "installation.md must mention VRAM"
        # Count table data rows (lines starting with |, excluding header/separator)
        vram_section = content[content.index("VRAM") :]
        table_rows = re.findall(r"^\|[^-].*\|$", vram_section, re.MULTILINE)
        # Subtract header row
        data_rows = max(0, len(table_rows) - 1)
        assert data_rows >= 4, f"VRAM table has {data_rows} data rows (need ≥ 4)"

    def test_TS019_build_from_source_section(self):
        """TS-019 → FR-011: Installation has a 'Build from Source' section.

        Given: The installation.md page
        When:  Content is searched for 'Build from Source'
        Then:  The section exists.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "installation.md")

        # Then
        assert (
            "Build from Source" in content
        ), "installation.md is missing a 'Build from Source' section"

    def test_TS019_build_from_source_le_6_steps(self):
        """TS-019 (ext) → FR-011: Build from Source has ≤ 6 steps.

        Given: The installation.md page
        When:  Numbered list items in the Build from Source section are counted
        Then:  There are at most 6 steps.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "installation.md")

        # When — extract Build from Source section
        bfs_match = re.split(
            r"(?:##|###)\s*Build from Source", content, flags=re.IGNORECASE
        )
        assert len(bfs_match) >= 2, "Could not locate Build from Source section"
        # Get text until next heading
        bfs_text = re.split(r"^##", bfs_match[1], maxsplit=1, flags=re.MULTILINE)[0]
        steps = re.findall(r"^\d+\.", bfs_text, re.MULTILINE)

        # Then
        assert len(steps) <= 6, f"Build from Source has {len(steps)} steps (max 6)"

    def test_FR014_apple_silicon_admonition(self):
        """FR-014: Installation has an Apple Silicon / MPS admonition.

        Given: The installation.md page
        When:  Content is searched for Apple Silicon mention
        Then:  An admonition about MPS/Metal is present.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "installation.md").lower()

        # Then
        assert (
            "apple silicon" in content or "mps" in content
        ), "installation.md must mention Apple Silicon or MPS"


# ---------------------------------------------------------------------------
# TestPrinterProfiles (TS-021, AC-004, FR-032)
# ---------------------------------------------------------------------------
class TestPrinterProfiles:
    """TS-021: printer-profiles.md contains ≥ 7 profiles."""

    def test_TS021_ge_7_printer_profiles(self):
        """TS-021 → AC-004, FR-032: At least 7 printer profiles documented.

        Given: The printer-profiles.md reference page
        When:  Table data rows are counted
        Then:  There are at least 7 profile rows.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_REFERENCE_DIR / "printer-profiles.md")

        # When — count table rows (lines with | that aren't header separator)
        table_lines = re.findall(r"^\|[^-].*\|$", content, re.MULTILINE)
        # Subtract header row(s)
        data_rows = max(0, len(table_lines) - 1)

        # Then
        assert data_rows >= 7, f"Printer profiles has {data_rows} rows (need ≥ 7)"

    def test_TS021_required_profile_names(self):
        """TS-021 (ext): Required profiles are present.

        Given: The printer-profiles.md reference page
        When:  Content is searched for key profile names
        Then:  All required profiles are found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_REFERENCE_DIR / "printer-profiles.md")

        # Then
        required = [
            "Generic FDM",
            "Ender 3",
            "Prusa MK4",
            "Bambu Lab P1S",
            "Elegoo Mars",
            "Elegoo Saturn",
            "Custom",
        ]
        for profile in required:
            assert (
                profile in content
            ), f"Printer profile '{profile}' missing from printer-profiles.md"


# ---------------------------------------------------------------------------
# TestErrorCodes (TS-022, FR-033)
# ---------------------------------------------------------------------------
class TestErrorCodes:
    """TS-022: error-codes.md contains all defined error codes."""

    # Error codes BF-E001 through BF-E016 plus BF-E999.
    REQUIRED_CODES = [f"BF-E{i:03d}" for i in range(1, 17)] + ["BF-E999"]

    def test_TS022_error_code_count(self):
        """TS-022 → FR-033: error-codes.md has 17 error code entries.

        Given: The error-codes.md reference page
        When:  BF-E entries are counted
        Then:  There are at least 17 (BF-E001 – BF-E016 + BF-E999).

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_REFERENCE_DIR / "error-codes.md")

        # When
        codes_found = set(re.findall(r"BF-E\d{3}", content))

        # Then
        assert len(codes_found) >= 17, (
            f"Found {len(codes_found)} error codes (need ≥ 17): "
            f"{sorted(codes_found)}"
        )

    @pytest.mark.parametrize("code", REQUIRED_CODES)
    def test_TS022_required_error_code_present(self, code):
        """TS-022 (ext): Error code '{code}' is documented.

        Given: The error-codes.md reference page
        When:  Searching for the error code
        Then:  The code is found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_REFERENCE_DIR / "error-codes.md")

        # Then
        assert code in content, f"Error code '{code}' missing from error-codes.md"


# ---------------------------------------------------------------------------
# TestTroubleshooting (FR-039, FR-040)
# ---------------------------------------------------------------------------
class TestTroubleshooting:
    """FR-039, FR-040: Troubleshooting page expansion."""

    COMMON_ISSUES = [
        "download is slow",
        "panel doesn't appear",
        "looks wrong",
        "crashes during generation",
        "grayed out",
    ]

    def test_FR039_common_issues_section(self):
        """FR-039: Troubleshooting has a 'Common Issues' section.

        Given: The troubleshooting.md page
        When:  Content is searched for 'Common Issues'
        Then:  The section header exists.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "troubleshooting.md")

        # Then
        assert (
            "Common Issues" in content
        ), "troubleshooting.md is missing 'Common Issues' section"

    @pytest.mark.parametrize("issue_substr", COMMON_ISSUES)
    def test_FR039_common_issue_present(self, issue_substr):
        """FR-039 (ext): Common issue about '{issue_substr}' is documented.

        Given: The troubleshooting.md page
        When:  Content is searched (case-insensitive)
        Then:  The issue topic is found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "troubleshooting.md").lower()

        # Then
        assert (
            issue_substr.lower() in content
        ), f"Common issue '{issue_substr}' not found in troubleshooting.md"


# ---------------------------------------------------------------------------
# TestGallery (FR-046)
# ---------------------------------------------------------------------------
class TestGallery:
    """FR-046: Gallery has ≥ 3 placeholder entries."""

    def test_FR046_gallery_ge_3_entries(self):
        """FR-046: Gallery has ≥ 3 placeholder entries.

        Given: The gallery/index.md page
        When:  Screenshot placeholders are counted
        Then:  There are at least 3 entries.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "gallery" / "index.md")

        # When — count gallery input/output image pairs
        input_images = re.findall(r"!\[.*?\]\(.*?gallery-.*?-input\.png\)", content)

        # Then
        assert (
            len(input_images) >= 3
        ), f"Gallery has {len(input_images)} entries (need ≥ 3)"

    def test_FR046_gallery_entries_have_generation_time(self):
        """FR-046 (ext): Gallery entries include generation times.

        Given: The gallery/index.md page
        When:  Content is searched for time indicators
        Then:  At least 3 time values (e.g., ``~8s``) are found.

        Type: Script | Priority: Must Pass
        """
        # Given
        content = _read(_DOCS_ROOT / "gallery" / "index.md")

        # When — match time patterns like ~8s, ~18s, ~35s
        times = re.findall(r"~\d+s", content)

        # Then
        assert len(times) >= 3, f"Gallery has {len(times)} generation times (need ≥ 3)"
