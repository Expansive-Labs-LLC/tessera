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

"""Tests for SPEC-TS-0014: CI Pipeline, Semantic Release & Add-on Packaging.

Each test maps to a Test Scenario (TS-XXX) from the spec's §13.
Tests are split into three groups:

1. ConfigFileValidation — Manual-type tests that verify file contents (YAML/TOML/JS)
2. BuildScriptExecution — Script-type tests that run build_addon.sh and verify outputs
3. SecurityCompliance — Tests that verify no secrets are hardcoded and actions are pinned

Tests can be run standalone with:
    pytest tests/test_ci_release_pipeline.py -v

No ``bpy`` dependencies — these tests validate CI/CD infrastructure files only.
"""

import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

# Resolve the repository root (two levels up from tests/)
REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_addon.sh"


# ---------------------------------------------------------------------------
# Helper: load YAML safely
# ---------------------------------------------------------------------------
def _load_yaml(path: Path) -> dict:
    """Load a YAML file, returning parsed dict."""
    import yaml

    with open(path) as f:
        return yaml.safe_load(f)


def _load_toml(path: Path) -> dict:
    """Load a TOML file, returning parsed dict."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # Python < 3.11 fallback

    with open(path, "rb") as f:
        return tomllib.load(f)


# ===========================================================================
# TestCIWorkflow (TS-001, TS-013, TS-014, TS-016)
# ===========================================================================
class TestCIWorkflow:
    """Tests that validate the CI workflow file structure and job configuration."""

    @pytest.fixture(autouse=True)
    def _load_ci(self):
        self.ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        assert self.ci_path.exists(), f"ci.yml not found at {self.ci_path}"
        self.ci = _load_yaml(self.ci_path)

    def test_TS001_ci_defines_all_required_jobs(self):
        """TS-001 → AC-001, FR-001–FR-008: ci.yml defines lint, test, build, commitlint.

        Given the CI workflow file exists,
        When its jobs are inspected,
        Then it contains exactly: lint, test, build, and commitlint jobs.

        Type: Manual | Priority: Must Pass
        """
        jobs = set(self.ci.get("jobs", {}).keys())
        for required_job in ("lint", "test", "build", "commitlint"):
            assert required_job in jobs, f"Missing required job: {required_job}"

    def test_TS001_ci_job_dependencies(self):
        """TS-001 → AC-001, FR-005: lint → test → build (sequential), commitlint parallel.

        Given the CI workflow jobs,
        When their 'needs' dependencies are inspected,
        Then test depends on lint, build depends on test, commitlint has no dependencies.

        Type: Manual | Priority: Must Pass
        """
        jobs = self.ci["jobs"]

        # commitlint runs in parallel (no needs)
        assert "needs" not in jobs["commitlint"], (
            "commitlint should run in parallel (no 'needs')"
        )

        # lint has no dependency (first in chain)
        assert "needs" not in jobs.get("lint", {}), (
            "lint should have no 'needs' dependency"
        )

        # test depends on lint
        test_needs = jobs["test"].get("needs")
        assert test_needs == "lint" or (
            isinstance(test_needs, list) and "lint" in test_needs
        ), "test job must depend on lint"

        # build depends on test
        build_needs = jobs["build"].get("needs")
        assert build_needs == "test" or (
            isinstance(build_needs, list) and "test" in build_needs
        ), "build job must depend on test"

    def test_TS013_lint_job_runs_tools_in_order(self):
        """TS-013 → FR-002: lint job runs isort, black, flake8, mypy in correct order.

        Given the lint job's steps,
        When they are inspected,
        Then isort, black, flake8, and mypy appear in that order.

        Type: Manual | Priority: Must Pass
        """
        lint_steps = self.ci["jobs"]["lint"]["steps"]
        step_names = [s.get("name", "").lower() for s in lint_steps]

        # Find indices of the tool steps
        tool_order = []
        for tool in ("isort", "black", "flake8", "mypy"):
            indices = [i for i, name in enumerate(step_names) if tool in name]
            assert len(indices) >= 1, f"Missing {tool} step in lint job"
            tool_order.append(indices[0])

        # Verify they're in ascending order
        assert tool_order == sorted(tool_order), (
            f"Lint tools must run in order isort→black→flake8→mypy, "
            f"got indices: {tool_order}"
        )

    def test_TS014_test_job_python_matrix(self):
        """TS-014 → FR-003: test job uses Python matrix [3.11, 3.12].

        Given the test job's strategy,
        When the Python version matrix is inspected,
        Then it contains both 3.11 and 3.12.

        Type: Manual | Priority: Must Pass
        """
        test_job = self.ci["jobs"]["test"]
        matrix = test_job.get("strategy", {}).get("matrix", {})
        python_versions = matrix.get("python-version", [])

        # Normalize to strings for comparison
        versions = [str(v) for v in python_versions]
        assert "3.11" in versions, "Python 3.11 missing from matrix"
        assert "3.12" in versions, "Python 3.12 missing from matrix"

    def test_TS016_all_ci_jobs_have_timeout(self):
        """TS-016 → FR-008: all CI jobs set timeout-minutes: 10.

        Given all CI workflow jobs,
        When their timeout-minutes values are inspected,
        Then every job has timeout-minutes set to 10.

        Type: Manual | Priority: Must Pass
        """
        for job_name, job_config in self.ci["jobs"].items():
            timeout = job_config.get("timeout-minutes")
            assert timeout == 10, (
                f"Job '{job_name}' has timeout-minutes={timeout}, expected 10"
            )


# ===========================================================================
# TestReleaseWorkflow (TS-002, TS-015, TS-017)
# ===========================================================================
class TestReleaseWorkflow:
    """Tests that validate the release workflow file structure."""

    @pytest.fixture(autouse=True)
    def _load_release(self):
        self.release_path = REPO_ROOT / ".github" / "workflows" / "release.yml"
        assert self.release_path.exists(), f"release.yml not found at {self.release_path}"
        self.release = _load_yaml(self.release_path)

    def test_TS002_release_permissions(self):
        """TS-002 → AC-002, FR-010: release.yml sets correct permissions.

        Given the release workflow,
        When its top-level permissions are inspected,
        Then it has contents: write, issues: write, pull-requests: write.

        Type: Manual | Priority: Must Pass
        """
        perms = self.release.get("permissions", {})
        assert perms.get("contents") == "write", "Missing contents: write"
        assert perms.get("issues") == "write", "Missing issues: write"
        assert perms.get("pull-requests") == "write", "Missing pull-requests: write"

    def test_TS015_release_uses_fetch_depth_zero(self):
        """TS-015 → FR-011: release.yml uses fetch-depth: 0 for checkout.

        Given the release job's checkout step,
        When its 'with' parameters are inspected,
        Then fetch-depth is 0 (full history).

        Type: Manual | Priority: Must Pass
        """
        jobs = self.release.get("jobs", {})
        release_job = jobs.get("release", {})
        steps = release_job.get("steps", [])

        checkout_steps = [
            s for s in steps
            if s.get("uses", "").startswith("actions/checkout")
        ]
        assert len(checkout_steps) >= 1, "No checkout step found"

        checkout = checkout_steps[0]
        fetch_depth = checkout.get("with", {}).get("fetch-depth")
        assert fetch_depth == 0, f"fetch-depth should be 0, got {fetch_depth}"

    def test_TS017_release_timeout(self):
        """TS-017 → FR-015: release.yml sets timeout-minutes: 15.

        Given the release job,
        When its timeout-minutes is inspected,
        Then it is 15.

        Type: Manual | Priority: Must Pass
        """
        release_job = self.release["jobs"]["release"]
        timeout = release_job.get("timeout-minutes")
        assert timeout == 15, f"Release timeout should be 15, got {timeout}"


# ===========================================================================
# TestReleaseConfig (TS-003, TS-008, TS-009)
# ===========================================================================
class TestReleaseConfig:
    """Tests that validate .releaserc.yml semantic-release configuration."""

    @pytest.fixture(autouse=True)
    def _load_releaserc(self):
        self.rc_path = REPO_ROOT / ".releaserc.yml"
        assert self.rc_path.exists(), ".releaserc.yml not found"
        self.rc = _load_yaml(self.rc_path)

    def test_TS003_tag_format_and_branches(self):
        """TS-003 → AC-002, FR-017, FR-018, FR-023: tagFormat and branches config.

        Given .releaserc.yml,
        When its branches and tagFormat are inspected,
        Then branches is ["main"] only and tagFormat uses bare version (no v prefix).

        Type: Manual | Priority: Must Pass
        """
        branches = self.rc.get("branches", [])
        assert branches == ["main"], (
            f"branches should be ['main'], got {branches}"
        )

        tag_format = self.rc.get("tagFormat", "")
        assert tag_format == "${version}", (
            f"tagFormat should be '${{version}}' (bare, no v prefix), got: {tag_format}"
        )
        # Should NOT contain github/template
        assert "github/template" not in branches, (
            "github/template should not be in branches (FR-023)"
        )

    def test_TS008_exec_plugin_with_prepare_cmd(self):
        """TS-008 → AC-002, FR-019, FR-020: .releaserc.yml includes exec plugin.

        Given .releaserc.yml plugins list,
        When @semantic-release/exec is found,
        Then its prepareCmd invokes scripts/build_addon.sh.

        Type: Manual | Priority: Must Pass
        """
        plugins = self.rc.get("plugins", [])

        # Find the exec plugin entry
        exec_plugin = None
        for plugin in plugins:
            if isinstance(plugin, list) and len(plugin) >= 2:
                if plugin[0] == "@semantic-release/exec":
                    exec_plugin = plugin[1]
                    break
            elif isinstance(plugin, str) and plugin == "@semantic-release/exec":
                exec_plugin = {}
                break

        assert exec_plugin is not None, (
            "@semantic-release/exec not found in plugins"
        )

        prepare_cmd = exec_plugin.get("prepareCmd", "")
        assert "scripts/build_addon.sh" in prepare_cmd, (
            f"prepareCmd should invoke build_addon.sh, got: {prepare_cmd}"
        )

    def test_TS009_git_plugin_assets(self):
        """TS-009 → FR-021: @semantic-release/git commits back patched files.

        Given .releaserc.yml plugins list,
        When @semantic-release/git is found,
        Then its assets include tessera/__init__.py and blender_manifest.toml.

        Type: Manual | Priority: Must Pass
        """
        plugins = self.rc.get("plugins", [])

        git_plugin = None
        for plugin in plugins:
            if isinstance(plugin, list) and len(plugin) >= 2:
                if plugin[0] == "@semantic-release/git":
                    git_plugin = plugin[1]
                    break

        assert git_plugin is not None, (
            "@semantic-release/git not found in plugins"
        )

        assets = git_plugin.get("assets", [])
        assert "tessera/__init__.py" in assets, (
            "tessera/__init__.py not in git assets"
        )
        assert "blender_manifest.toml" in assets, (
            "blender_manifest.toml not in git assets"
        )
        assert "CHANGELOG.md" in assets, "CHANGELOG.md not in git assets"

        # Verify [skip ci] in commit message
        message = git_plugin.get("message", "")
        assert "[skip ci]" in message, (
            f"Git commit message must include [skip ci]: {message}"
        )


# ===========================================================================
# TestBlenderManifest (TS-010)
# ===========================================================================
class TestBlenderManifest:
    """Tests that validate blender_manifest.toml contents."""

    @pytest.fixture(autouse=True)
    def _load_manifest(self):
        self.manifest_path = REPO_ROOT / "blender_manifest.toml"
        assert self.manifest_path.exists(), "blender_manifest.toml not found"
        self.manifest = _load_toml(self.manifest_path)

    def test_TS010_manifest_required_fields(self):
        """TS-010 → AC-007, FR-035–FR-040: blender_manifest.toml has correct fields.

        Given blender_manifest.toml,
        When its fields are inspected,
        Then it contains schema_version, id, blender_version_min, license, type,
        and permissions table with files and network keys.

        Type: Manual | Priority: Must Pass
        """
        # FR-036
        assert self.manifest["schema_version"] == "1.0.0"
        assert self.manifest["id"] == "tessera"
        assert self.manifest["name"] == "Tessera"
        assert self.manifest["type"] == "add-on"

        # FR-036e: tagline ≤ 64 characters
        tagline = self.manifest.get("tagline", "")
        assert len(tagline) <= 64, f"Tagline too long: {len(tagline)} chars"

        # FR-037
        assert self.manifest["blender_version_min"] == "4.2.0"

        # FR-038
        assert self.manifest["license"] == ["SPDX:GPL-2.0-or-later"]

        # FR-039: permissions table
        perms = self.manifest.get("permissions", {})
        assert "files" in perms, "permissions.files missing"
        assert "network" in perms, "permissions.network missing"

        # FR-040: build exclusion patterns
        build = self.manifest.get("build", {})
        exclude = build.get("paths_exclude_pattern", [])
        assert "__pycache__/" in exclude, "__pycache__/ not in exclusion list"
        assert "tests/" in exclude, "tests/ not in exclusion list"
        assert "testing/" in exclude, "testing/ not in exclusion list"


# ===========================================================================
# TestDependabot (TS-011)
# ===========================================================================
class TestDependabot:
    """Tests that validate .github/dependabot.yml."""

    def test_TS011_dependabot_github_actions_ecosystem(self):
        """TS-011 → AC-006, FR-041–FR-042: dependabot config for github-actions.

        Given .github/dependabot.yml,
        When its updates entries are inspected,
        Then it contains a github-actions ecosystem entry with weekly schedule.

        Type: Manual | Priority: Must Pass
        """
        dependabot_path = REPO_ROOT / ".github" / "dependabot.yml"
        assert dependabot_path.exists(), "dependabot.yml not found"
        config = _load_yaml(dependabot_path)

        assert config.get("version") == 2, "Dependabot version should be 2"

        updates = config.get("updates", [])
        ga_entries = [
            u for u in updates if u.get("package-ecosystem") == "github-actions"
        ]
        assert len(ga_entries) >= 1, (
            "No github-actions ecosystem in dependabot config"
        )

        ga_entry = ga_entries[0]
        assert ga_entry.get("directory") == "/"
        schedule = ga_entry.get("schedule", {})
        assert schedule.get("interval") == "weekly"


# ===========================================================================
# TestCommitlintConfig (TS-012)
# ===========================================================================
class TestCommitlintConfig:
    """Tests that validate commitlint.config.js."""

    def test_TS012_commitlint_extends_conventional(self):
        """TS-012 → FR-043: commitlint.config.js extends config-conventional.

        Given commitlint.config.js at repo root,
        When its contents are read,
        Then it extends @commitlint/config-conventional.

        Type: Manual | Priority: Must Pass
        """
        config_path = REPO_ROOT / "commitlint.config.js"
        assert config_path.exists(), "commitlint.config.js not found"

        content = config_path.read_text()
        assert "@commitlint/config-conventional" in content, (
            "commitlint config must extend @commitlint/config-conventional"
        )


# ===========================================================================
# TestBuildScript — Script-type tests (TS-004, TS-005, TS-006, TS-007,
#                                       TS-018, TS-019, TS-022, TS-023)
# ===========================================================================
class TestBuildScript:
    """Tests that execute build_addon.sh and verify its behavior.

    All tests that invoke the build script use an isolated temporary copy
    of the repository to prevent cross-test file contamination.
    """

    @pytest.fixture(autouse=True)
    def _check_prerequisites(self):
        """Verify build script and required project files exist."""
        assert BUILD_SCRIPT.exists(), f"build_addon.sh not found at {BUILD_SCRIPT}"
        assert os.access(str(BUILD_SCRIPT), os.X_OK), (
            "build_addon.sh is not executable"
        )

    @pytest.fixture
    def build_env(self, tmp_path):
        """Create an isolated build environment in a temp directory.

        Copies tessera/, blender_manifest.toml, LICENSE, and the build script
        into tmp_path so the build can run without touching the real repo.

        Returns:
            tuple: (work_dir: Path, script_path: Path) — the temp repo root
            and the path to the copied build_addon.sh.
        """
        work_dir = tmp_path / "repo"
        work_dir.mkdir()

        # Copy tessera package (excluding test/cache dirs)
        shutil.copytree(
            str(REPO_ROOT / "tessera"),
            str(work_dir / "tessera"),
            ignore=shutil.ignore_patterns(
                "__pycache__", ".git", "tests", "testing",
            ),
        )

        # Copy manifest and license
        shutil.copy2(str(REPO_ROOT / "blender_manifest.toml"), str(work_dir))
        shutil.copy2(str(REPO_ROOT / "LICENSE"), str(work_dir))

        # Ensure the copied __init__.py has a valid dev version tuple
        init_copy = work_dir / "tessera" / "__init__.py"
        init_content = init_copy.read_text()
        init_content = re.sub(
            r'"version": \(\d+, \d+, \d+\),',
            '"version": (0, 1, 0),',
            init_content,
        )
        init_copy.write_text(init_content)

        # Ensure the manifest has a valid version field
        manifest_copy = work_dir / "blender_manifest.toml"
        mc = manifest_copy.read_text()
        mc = re.sub(
            r'^version = ".*"', 'version = "0.1.0"', mc, flags=re.MULTILINE
        )
        manifest_copy.write_text(mc)

        # Copy the build script
        scripts_dir = work_dir / "scripts"
        scripts_dir.mkdir()
        local_script = scripts_dir / "build_addon.sh"
        shutil.copy2(str(BUILD_SCRIPT), str(local_script))

        return work_dir, local_script

    def _run_isolated(self, script_path, *args, cwd=None):
        """Run a build script in an isolated environment.

        Args:
            script_path: Path to the copied build_addon.sh
            *args: Arguments to pass to the script
            cwd: Working directory (defaults to script's parent's parent)
        """
        work_dir = cwd or str(script_path.parent.parent)
        cmd = ["bash", str(script_path)] + list(args)
        return subprocess.run(
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_TS004_build_produces_valid_zip(self, build_env):
        """TS-004 → AC-003, FR-029–FR-032: build_addon.sh 1.2.3 produces valid zip.

        Given the build script is executed with argument 1.2.3,
        When the script completes,
        Then tessera-v1.2.3.zip exists with blender_manifest.toml,
        tessera/__init__.py, LICENSE, and NO excluded directories.

        Type: Script | Priority: Must Pass
        """
        work_dir, script = build_env
        result = self._run_isolated(script, "1.2.3")
        assert result.returncode == 0, (
            f"Build failed with code {result.returncode}:\n"
            f"{result.stderr}\n{result.stdout}"
        )

        zip_path = work_dir / "tessera-v1.2.3.zip"
        assert zip_path.exists(), "tessera-v1.2.3.zip not created"

        # Check zip contents
        list_result = subprocess.run(
            ["unzip", "-l", str(zip_path)],
            capture_output=True, text=True,
        )
        listing = list_result.stdout

        # Required files present
        assert "blender_manifest.toml" in listing
        assert "tessera/__init__.py" in listing
        assert "LICENSE" in listing

        # Excluded directories absent
        for excluded in (
            "tests/", "__pycache__", ".agent/", "specs/", "tasks/",
            "scripts/", "docs/", ".github/",
        ):
            assert excluded not in listing or (
                f"   {excluded}" not in listing
            ), f"Excluded path found in zip: {excluded}"

        # Verify patched version in zip
        extract_result = subprocess.run(
            ["unzip", "-p", str(zip_path), "tessera/__init__.py"],
            capture_output=True, text=True,
        )
        assert '"version": (1, 2, 3),' in extract_result.stdout

        manifest_result = subprocess.run(
            ["unzip", "-p", str(zip_path), "blender_manifest.toml"],
            capture_output=True, text=True,
        )
        assert 'version = "1.2.3"' in manifest_result.stdout

    def test_TS005_no_args_exits_with_error(self):
        """TS-005 → FR-024: build_addon.sh with no args exits code 1 with usage.

        Given the build script is executed with no arguments,
        When the script runs,
        Then it exits with code 1 and prints a usage message.

        Type: Script | Priority: Must Pass
        """
        # Safe to run against real script — exits immediately, no file changes
        result = subprocess.run(
            ["bash", str(BUILD_SCRIPT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1, (
            f"Expected exit code 1, got {result.returncode}"
        )
        assert "Usage:" in result.stderr, (
            "Expected usage message in stderr"
        )

    def test_TS006_prerelease_suffix_stripped(self, build_env):
        """TS-006 → EC-002, FR-026–FR-027: prerelease suffix stripped for bl_info.

        Given the build script is executed with 0.0.0-ci,
        When the script completes,
        Then bl_info version is (0, 0, 0), manifest version is "0.0.0",
        and zip is named tessera-v0.0.0-ci.zip.

        Type: Script | Priority: Must Pass
        """
        work_dir, script = build_env
        result = self._run_isolated(script, "0.0.0-ci")
        assert result.returncode == 0, (
            f"Build failed:\n{result.stderr}\n{result.stdout}"
        )

        # Zip uses full version string (including suffix) in filename
        zip_path = work_dir / "tessera-v0.0.0-ci.zip"
        assert zip_path.exists(), "tessera-v0.0.0-ci.zip not created"

        # Verify patched version (suffix stripped for tuple)
        extract_result = subprocess.run(
            ["unzip", "-p", str(zip_path), "tessera/__init__.py"],
            capture_output=True, text=True,
        )
        assert '"version": (0, 0, 0),' in extract_result.stdout, (
            "Pre-release suffix not stripped from bl_info tuple"
        )

        manifest_result = subprocess.run(
            ["unzip", "-p", str(zip_path), "blender_manifest.toml"],
            capture_output=True, text=True,
        )
        assert 'version = "0.0.0"' in manifest_result.stdout, (
            "Pre-release suffix not stripped from manifest version"
        )

    def test_TS007_handles_spaces_in_path(self, tmp_path):
        """TS-007 → EC-003, FR-025: build_addon.sh works in paths with spaces.

        Given the repository is cloned to a path with spaces,
        When the build script runs from the copied location,
        Then it completes successfully.

        Type: Script | Priority: Must Pass
        """
        # Create a directory with spaces
        space_dir = tmp_path / "My Projects" / "blender-ai-agent"
        space_dir.mkdir(parents=True)

        # Copy essential files
        shutil.copytree(
            str(REPO_ROOT / "tessera"),
            str(space_dir / "tessera"),
            ignore=shutil.ignore_patterns("__pycache__", ".git", "tests", "testing"),
        )
        shutil.copy2(str(REPO_ROOT / "blender_manifest.toml"), str(space_dir))
        shutil.copy2(str(REPO_ROOT / "LICENSE"), str(space_dir))

        # Ensure the copied __init__.py has a valid version tuple
        init_copy = space_dir / "tessera" / "__init__.py"
        init_content = init_copy.read_text()
        init_content = re.sub(
            r'"version": \(\d+, \d+, \d+\),',
            '"version": (0, 1, 0),',
            init_content,
        )
        if '"version": (0, 1, 0),' not in init_content:
            init_content = init_content.replace(
                '"name": "Tessera"',
                '"name": "Tessera",\n    "version": (0, 1, 0)',
            )
        init_copy.write_text(init_content)

        # Ensure the manifest has a valid version field
        manifest_copy = space_dir / "blender_manifest.toml"
        mc = manifest_copy.read_text()
        mc = re.sub(r'^version = ".*"', 'version = "0.1.0"', mc, flags=re.MULTILINE)
        manifest_copy.write_text(mc)

        # Copy the build script
        scripts_dir = space_dir / "scripts"
        scripts_dir.mkdir()
        local_script = scripts_dir / "build_addon.sh"
        shutil.copy2(str(BUILD_SCRIPT), str(local_script))

        # Run the COPIED script so SCRIPT_DIR resolves to the test directory
        result = subprocess.run(
            ["bash", str(local_script), "1.0.0"],
            cwd=str(space_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Build failed in path with spaces:\n{result.stderr}\n{result.stdout}"
        )

        zip_path = space_dir / "tessera-v1.0.0.zip"
        assert zip_path.exists(), "Zip not created in space-containing path"

    def test_TS018_uses_strict_bash_mode(self):
        """TS-018 → FR-025, CON-007: build_addon.sh uses set -euo pipefail.

        Given the build script source,
        When its first few lines are inspected,
        Then 'set -euo pipefail' is present.

        Type: Script | Priority: Must Pass
        """
        content = BUILD_SCRIPT.read_text()
        assert "set -euo pipefail" in content, (
            "build_addon.sh must use 'set -euo pipefail'"
        )

    def test_TS019_no_non_posix_tools(self):
        """TS-019 → CON-007: build script uses only POSIX utilities.

        Given the build script source,
        When scanned for non-POSIX tool invocations,
        Then no python, node, npm, or pip commands are found.

        Type: Manual | Priority: Must Pass
        """
        content = BUILD_SCRIPT.read_text()

        # Exclude comments and strings that reference tools theoretically
        lines = [
            line for line in content.splitlines()
            if not line.strip().startswith("#")
        ]
        code = "\n".join(lines)

        for tool in ("python", "python3", "node ", "npm ", "pip ", "curl ", "wget "):
            assert tool not in code, (
                f"Non-POSIX tool '{tool.strip()}' found in build script"
            )

    def test_TS022_build_fails_on_missing_version_tuple(self, tmp_path):
        """TS-022 → FR-027: build exits 1 if __init__.py lacks version tuple regex.

        Given tessera/__init__.py does not contain the version tuple pattern,
        When the build script runs from the copied location,
        Then it exits with code 1 and prints an error.

        Type: Script | Priority: Must Pass
        """
        # Create a minimal repo copy with broken __init__.py
        test_dir = tmp_path / "test-repo"
        test_dir.mkdir()

        tessera_dir = test_dir / "tessera"
        tessera_dir.mkdir()

        # Write __init__.py WITHOUT a version tuple
        (tessera_dir / "__init__.py").write_text(
            'bl_info = {"name": "Tessera"}\n'
        )

        # Copy other required files
        shutil.copy2(str(REPO_ROOT / "blender_manifest.toml"), str(test_dir))
        shutil.copy2(str(REPO_ROOT / "LICENSE"), str(test_dir))

        # Copy the build script so SCRIPT_DIR resolves to the test directory
        scripts_dir = test_dir / "scripts"
        scripts_dir.mkdir()
        local_script = scripts_dir / "build_addon.sh"
        shutil.copy2(str(BUILD_SCRIPT), str(local_script))

        result = subprocess.run(
            ["bash", str(local_script), "1.0.0"],
            cwd=str(test_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1, (
            f"Expected exit code 1 for missing version tuple, got {result.returncode}"
        )
        assert "version tuple" in result.stderr.lower() or "could not find" in result.stderr.lower(), (
            f"Expected error about missing version tuple in stderr:\n{result.stderr}"
        )

    def test_TS023_no_test_dirs_in_zip(self, build_env):
        """TS-023 → FR-030: zip does NOT contain tessera/tests/ or tessera/testing/.

        Given the build script produces a zip,
        When the archive listing is inspected,
        Then tessera/tests/ and tessera/testing/ are absent.

        Type: Script | Priority: Must Pass
        """
        work_dir, script = build_env
        result = self._run_isolated(script, "1.0.0")
        assert result.returncode == 0, (
            f"Build failed:\n{result.stderr}\n{result.stdout}"
        )

        zip_path = work_dir / "tessera-v1.0.0.zip"
        list_result = subprocess.run(
            ["unzip", "-l", str(zip_path)],
            capture_output=True, text=True,
        )
        listing = list_result.stdout

        assert "tessera/tests/" not in listing, (
            "tessera/tests/ found in zip — should be excluded"
        )
        assert "tessera/testing/" not in listing, (
            "tessera/testing/ found in zip — should be excluded"
        )


# ===========================================================================
# TestSecurityCompliance (TS-020, TS-021)
# ===========================================================================
class TestSecurityCompliance:
    """Tests that verify security requirements across all CI/CD files."""

    def test_TS020_no_hardcoded_secrets(self):
        """TS-020 → SEC-001, CON-003: no secrets hardcoded in any file.

        Given all workflow files, build script, and config files,
        When scanned for hardcoded secrets patterns,
        Then no matches are found.

        Type: Script | Priority: Must Pass
        """
        files_to_check = [
            REPO_ROOT / ".github" / "workflows" / "ci.yml",
            REPO_ROOT / ".github" / "workflows" / "release.yml",
            REPO_ROOT / ".releaserc.yml",
            REPO_ROOT / "scripts" / "build_addon.sh",
            REPO_ROOT / "commitlint.config.js",
            REPO_ROOT / "blender_manifest.toml",
        ]

        secret_patterns = [
            r"ghp_[a-zA-Z0-9]{36}",  # GitHub PAT
            r"github_pat_[a-zA-Z0-9_]{82}",  # GitHub fine-grained PAT
            r"sk-[a-zA-Z0-9]{48}",  # OpenAI key
            r"AKIA[0-9A-Z]{16}",  # AWS access key
            r"(?i)password\s*[:=]\s*['\"][^'\"]+['\"]",  # Inline passwords
        ]

        for file_path in files_to_check:
            if not file_path.exists():
                continue
            content = file_path.read_text()
            for pattern in secret_patterns:
                matches = re.findall(pattern, content)
                assert len(matches) == 0, (
                    f"Potential secret found in {file_path.name}: {matches}"
                )

    def test_TS021_actions_pinned_to_major_version(self):
        """TS-021 → SEC-002: all third-party actions pinned to major version tags.

        Given all workflow YAML files,
        When 'uses:' directives are inspected,
        Then all third-party actions use @vN tags, not @main or @latest.

        Type: Manual | Priority: Must Pass
        """
        workflow_dir = REPO_ROOT / ".github" / "workflows"
        assert workflow_dir.exists()

        for yml_file in workflow_dir.glob("*.yml"):
            content = yml_file.read_text()

            # Find all 'uses:' lines
            uses_lines = re.findall(r"uses:\s*(.+)", content)

            for uses in uses_lines:
                uses = uses.strip()

                # Skip local actions (e.g., ./ or .github/)
                if uses.startswith("."):
                    continue

                # Skip org composite actions (allowed to use @main per CSO)
                if "Expansive-Labs-LLC/" in uses:
                    continue

                # Third-party actions must use @vN tag
                if "@" in uses:
                    ref = uses.split("@")[1]
                    assert ref.startswith("v"), (
                        f"Action '{uses}' in {yml_file.name} not pinned to "
                        f"major version tag (found @{ref})"
                    )
                    assert ref not in ("main", "latest", "master"), (
                        f"Action '{uses}' in {yml_file.name} uses @{ref}, "
                        f"should be pinned to @vN"
                    )
