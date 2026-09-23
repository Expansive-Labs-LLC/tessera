# SPDX-License-Identifier: GPL-2.0-or-later
"""Tests for the Linux engine installer (SPEC-TS-0023 FR-030 – FR-032, FR-042).

These check the packaging contract the add-on depends on — where the marker
goes, what it says, and that the build refuses to produce an artifact whose
kernels would not launch. They do not build an artifact: that needs a CUDA
toolkit and several gigabytes, and belongs in CI.

Maps to SPEC-TS-0023: FR-030, FR-031, FR-042, TS-038, TS-040, TS-041.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PACKAGING = Path(__file__).resolve().parent.parent / "packaging" / "linux"
BUILD = PACKAGING / "build_engine_installer.sh"
INSTALL = PACKAGING / "install.sh"


class TestScriptsAreWellFormed:
    def test_both_scripts_exist_and_are_executable(self):
        for script in (BUILD, INSTALL):
            assert script.exists(), f"{script.name} is missing"
            assert os.access(script, os.X_OK), f"{script.name} is not executable"

    @pytest.mark.parametrize("script", [BUILD, INSTALL], ids=lambda p: p.name)
    def test_scripts_parse(self, script):
        assert subprocess.run(["bash", "-n", str(script)]).returncode == 0

    @pytest.mark.parametrize("script", [BUILD, INSTALL], ids=lambda p: p.name)
    def test_scripts_fail_fast(self, script):
        """A partially-installed engine is worse than one that refused."""
        assert "set -euo pipefail" in script.read_text()

    @pytest.mark.parametrize("script", [BUILD, INSTALL], ids=lambda p: p.name)
    def test_scripts_carry_the_licence_identifier(self, script):
        assert "GPL-2.0-or-later" in script.read_text()


class TestBuildRefusesAnUnusableToolchain:
    def test_build_requires_a_version_argument(self, tmp_path):
        result = subprocess.run(
            ["bash", str(BUILD)], capture_output=True, text=True, cwd=tmp_path
        )
        assert result.returncode == 1
        assert "Usage" in result.stderr

    @pytest.mark.skipif(
        shutil.which("nvcc") is None, reason="no CUDA toolkit on this machine"
    )
    def test_build_refuses_architectures_the_toolkit_cannot_target(self, tmp_path):
        """The premise this whole split rests on, enforced at build time.

        An artifact built for an architecture the toolkit does not know
        produces kernels that will not launch — a failure that surfaces on
        the user's GPU rather than on the build machine.
        """
        result = subprocess.run(
            ["bash", str(BUILD), "0.0.0-test", str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CUDA_ARCH_LIST": "99.9"},
        )
        assert result.returncode == 2
        assert "cannot target sm_999" in result.stderr

    def test_build_refuses_when_no_toolkit_is_present(self, tmp_path):
        """TRELLIS's extensions build from source; without nvcc there is no
        artifact to make, and saying so beats failing inside pip.

        CUDA_HOME is pointed at an empty directory so the project-local
        toolchain, if one has been provisioned, does not satisfy the check.
        """
        empty_bin = tmp_path / "bin"
        empty_bin.mkdir()
        for needed in ("bash", "mktemp", "rm", "date", "dirname", "cd"):
            found = shutil.which(needed)
            if found:
                (empty_bin / needed).symlink_to(found)
        result = subprocess.run(
            ["bash", str(BUILD), "0.0.0-test", str(tmp_path)],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": str(empty_bin),
                "CUDA_HOME": str(tmp_path / "no-toolkit-here"),
            },
        )
        assert result.returncode == 2
        assert "nvcc not found" in result.stderr
        assert "provision_toolchain.sh" in result.stderr


class TestInstallerContract:
    """FR-031: what the add-on's discovery actually reads."""

    def test_marker_path_matches_what_discovery_looks_for(self, mock_bpy):
        from tessera.engine.discovery import install_marker_path

        text = INSTALL.read_text()
        assert "XDG_DATA_HOME:-$HOME/.local/share" in text
        assert "tessera/engine" in text
        assert "install.json" in text
        # The client resolves the same location.
        assert install_marker_path().name == "install.json"
        assert install_marker_path().parent.as_posix().endswith("tessera/engine")

    def test_marker_carries_every_field_discovery_expects(self):
        text = INSTALL.read_text()
        for field in ("engine_version", "protocol_versions", "executable"):
            assert f'"{field}"' in text, f"marker does not record {field}"

    def test_install_is_per_user_and_never_asks_for_root(self):
        """Nothing the engine does needs system-wide privilege."""
        text = INSTALL.read_text()
        assert "sudo" not in text
        assert "$HOME/.local/share" in text or "XDG_DATA_HOME" in text

    def test_launcher_invokes_the_engine_module(self):
        text = INSTALL.read_text()
        assert "-m tessera_engine" in text

    def test_reinstall_replaces_rather_than_layers(self):
        """A venv merged over an older one is a debugging problem nobody wants."""
        text = INSTALL.read_text()
        assert "rm -rf" in text and "Replacing the existing installation" in text


class TestSigning:
    """FR-042: the artifact is signed, and the add-on's gate is the digest."""

    def test_build_emits_a_sha256_beside_the_artifact(self):
        assert "sha256sum" in BUILD.read_text()

    def test_build_signs_when_a_key_is_configured(self):
        text = BUILD.read_text()
        assert "TESSERA_SIGNING_KEY" in text
        assert "--detach-sign" in text and "--armor" in text

    def test_unsigned_build_warns_loudly(self):
        """A release that quietly ships unsigned is the failure mode here."""
        text = BUILD.read_text()
        assert re.search(r"UNSIGNED", text), "no warning for an unsigned build"


class TestBuildRecordsWhatItCanRun:
    def test_build_info_records_the_architectures_served(self):
        """So the engine can refuse a GPU it was not built for, rather than
        failing inside a kernel launch."""
        text = BUILD.read_text()
        assert "build-info.json" in text
        assert "cuda_arch_list" in text

    def test_torch_comes_from_the_cu128_index_not_pypi(self):
        """PyPI's torch has no sm_120 support; that failure appears at kernel
        launch on the user's GPU, not at install."""
        assert "download.pytorch.org/whl/cu128" in BUILD.read_text()
        reqs = (PACKAGING / "requirements-engine.txt").read_text()
        assert not re.search(
            r"^torch[=<>~]", reqs, re.M
        ), "torch pinned in requirements would resolve against PyPI"


PROVISION = PACKAGING / "provision_toolchain.sh"


class TestToolchainProvisioning:
    """The build needs a toolkit newer than most distros ship."""

    def test_provision_script_exists_and_parses(self):
        assert PROVISION.exists()
        assert os.access(PROVISION, os.X_OK)
        assert subprocess.run(["bash", "-n", str(PROVISION)]).returncode == 0

    def test_toolkit_version_follows_torch_not_the_newest(self):
        """A toolkit ahead of torch compiles extensions that fail at import."""
        text = PROVISION.read_text()
        assert "torch.version.cuda" in text

    def test_provisioning_is_user_local(self):
        text = PROVISION.read_text()
        assert "sudo" not in text
        assert ".cuda-toolchain" in text

    def test_provisioning_installs_ninja(self):
        """Torch's extension builder shells out to it by name."""
        assert "pip" in PROVISION.read_text()
        assert "ninja" in PROVISION.read_text()

    def test_build_puts_the_venv_bin_on_path_for_the_extension_build(self):
        """Installing ninja is not enough — it has to be findable."""
        text = BUILD.read_text()
        assert 'PATH="$PAYLOAD/venv/bin:$PATH"' in text

    def test_build_prefers_the_project_toolchain_over_the_system_one(self):
        """The distro nvcc is frequently too old, and failing through to it
        produces a confusing error rather than a clear one."""
        text = BUILD.read_text()
        assert ".cuda-toolchain/bin/nvcc" in text
        assert "provision_toolchain.sh" in text


class TestArtifactBudget:
    """NFR-012: a real build measures 3.7 GiB before TRELLIS is in it."""

    def test_size_budget_is_stated_in_the_spec(self):
        spec = (
            Path(__file__).resolve().parent.parent
            / "specs/tessera/feature-spec/active"
            / "SPEC-TS-0023-local-inference-engine.md"
        )
        text = spec.read_text(encoding="utf-8")
        assert "NFR-012" in text and "6 GiB" in text

    def test_build_reports_the_size_it_produced(self):
        """So a build that blows the budget is visible in its own output."""
        assert "du -h" in BUILD.read_text()
