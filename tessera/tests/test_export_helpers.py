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

"""Test suite for export pipeline helper functions.

Tests the pure-Python utility functions in ``tessera.export.export_pipeline``
that can be verified without Blender runtime.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

SEC-003: Filename sanitization.
SEC-006: Path traversal prevention.
CON-005: File collision avoidance.
EC-004: Export directory validation.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# bpy and related Blender modules are mocked globally in conftest.py.

from tessera.export.export_pipeline import (  # noqa: E402
    _resolve_file_path,
    _sanitize_filename,
    _validate_path_within_dir,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# _sanitize_filename (SEC-003)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestSanitizeFilename:
    """Tests for _sanitize_filename (SEC-003)."""

    def test_simple_name_unchanged(self):
        """Clean alphanumeric name passes through unchanged."""
        assert _sanitize_filename("MyCube") == "MyCube"

    def test_spaces_replaced(self):
        """Spaces replaced with underscores."""
        assert _sanitize_filename("My Cube") == "My_Cube"

    def test_special_chars_replaced(self):
        """Special characters replaced with underscores."""
        assert _sanitize_filename("My<Cube>!@#$%") == "My_Cube______"

    def test_dots_preserved(self):
        """Dots are allowed in filenames."""
        assert _sanitize_filename("Cube.001") == "Cube.001"

    def test_hyphens_preserved(self):
        """Hyphens are allowed in filenames."""
        assert _sanitize_filename("my-cube") == "my-cube"

    def test_underscores_preserved(self):
        """Underscores are allowed in filenames."""
        assert _sanitize_filename("my_cube") == "my_cube"

    def test_unicode_replaced(self):
        """Non-ASCII characters replaced with underscores."""
        assert _sanitize_filename("Würfel") == "W_rfel"

    def test_empty_string(self):
        """Empty string falls back to 'export' to avoid bare extension."""
        assert _sanitize_filename("") == "export"

    def test_path_traversal_chars_sanitized(self):
        """SEC-003: Path separators replaced with underscores."""
        assert "/" not in _sanitize_filename("../../../etc/passwd")
        assert "\\" not in _sanitize_filename("..\\..\\..\\etc\\passwd")

    def test_only_special_chars(self):
        """String of only special chars becomes all underscores."""
        result = _sanitize_filename("!@#$%^&*()")
        assert all(c == "_" for c in result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# _resolve_file_path (CON-005)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestResolveFilePath:
    """Tests for _resolve_file_path (CON-005: collision avoidance)."""

    def test_no_collision_returns_base_path(self, tmp_path):
        """Non-existing file returns base path without suffix."""
        result = _resolve_file_path(str(tmp_path), "Cube", "stl")
        assert result == os.path.join(str(tmp_path), "Cube.stl")

    def test_collision_appends_001(self, tmp_path):
        """First collision appends _001."""
        # Given: Cube.stl already exists.
        (tmp_path / "Cube.stl").touch()

        result = _resolve_file_path(str(tmp_path), "Cube", "stl")
        assert result == os.path.join(str(tmp_path), "Cube_001.stl")

    def test_multiple_collisions_increment(self, tmp_path):
        """Multiple collisions produce _001, _002, etc."""
        # Given: Cube.stl and Cube_001.stl already exist.
        (tmp_path / "Cube.stl").touch()
        (tmp_path / "Cube_001.stl").touch()

        result = _resolve_file_path(str(tmp_path), "Cube", "stl")
        assert result == os.path.join(str(tmp_path), "Cube_002.stl")

    def test_different_extensions_no_collision(self, tmp_path):
        """Different extension does not conflict."""
        # Given: Cube.stl exists.
        (tmp_path / "Cube.stl").touch()

        result = _resolve_file_path(str(tmp_path), "Cube", "3mf")
        assert result == os.path.join(str(tmp_path), "Cube.3mf")

    def test_three_digit_padding(self, tmp_path):
        """Suffix uses 3-digit zero-padded format."""
        (tmp_path / "Cube.stl").touch()
        result = _resolve_file_path(str(tmp_path), "Cube", "stl")
        # The result should contain _001 not _1.
        assert "_001" in os.path.basename(result)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# _validate_path_within_dir (SEC-006)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestValidatePathWithinDir:
    """Tests for _validate_path_within_dir (SEC-006)."""

    def test_path_within_dir_returns_true(self, tmp_path):
        """File inside directory is valid."""
        file_path = os.path.join(str(tmp_path), "export", "Cube.stl")
        assert _validate_path_within_dir(str(tmp_path), file_path) is True

    def test_path_escaping_dir_returns_false(self, tmp_path):
        """SEC-006: Path traversal outside directory is blocked."""
        file_path = os.path.join(str(tmp_path), "..", "evil.stl")
        assert _validate_path_within_dir(str(tmp_path), file_path) is False

    def test_exact_dir_match_returns_true(self, tmp_path):
        """File at directory root is valid."""
        file_path = os.path.join(str(tmp_path), "Cube.stl")
        assert _validate_path_within_dir(str(tmp_path), file_path) is True

    def test_symlink_resolved(self, tmp_path):
        """SEC-006: Symlinks are resolved before checking."""
        # Create a real subdirectory and a file path within it.
        sub = tmp_path / "exports"
        sub.mkdir()
        file_path = os.path.join(str(sub), "file.stl")
        assert _validate_path_within_dir(str(sub), file_path) is True

    def test_nested_path_traversal_blocked(self, tmp_path):
        """SEC-006: Deep path traversal (../../..) is blocked."""
        file_path = os.path.join(
            str(tmp_path), "a", "..", "..", "..", "etc", "passwd"
        )
        assert _validate_path_within_dir(str(tmp_path), file_path) is False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ExportPipeline._resolve_export_directory (EC-004, EC-006)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestResolveExportDirectory:
    """Tests for ExportPipeline._resolve_export_directory.

    We test the method directly using a fresh ExportPipeline instance
    with bpy mocked.
    """

    @pytest.fixture
    def pipeline(self):
        """Create an ExportPipeline instance with bpy mocked."""
        from tessera.export.export_pipeline import ExportPipeline
        return ExportPipeline()

    def test_explicit_directory_used(self, pipeline, tmp_path):
        """Explicit directory path is returned (resolved)."""
        result = pipeline._resolve_export_directory(str(tmp_path))
        assert result == os.path.realpath(str(tmp_path))

    def test_empty_string_falls_back_to_blend_path(self, pipeline, tmp_path):
        """EC-006: Empty directory falls back to .blend file dir."""
        blend_path = str(tmp_path / "project" / "file.blend")
        with patch("tessera.export.export_pipeline.bpy") as mock_bpy:
            mock_bpy.data.filepath = blend_path
            result = pipeline._resolve_export_directory("")
        expected = os.path.dirname(os.path.realpath(blend_path))
        assert result == expected

    def test_unsaved_blend_falls_back_to_home(self, pipeline):
        """EC-006: Unsaved .blend falls back to home directory."""
        with patch("tessera.export.export_pipeline.bpy") as mock_bpy:
            mock_bpy.data.filepath = ""
            result = pipeline._resolve_export_directory("")
        assert result == os.path.expanduser("~")
