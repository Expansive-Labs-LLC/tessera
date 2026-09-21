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

"""Tests for the centralized error handler.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Covers: TS-001, TS-002, TS-007, TS-008, TS-009, TS-010, TS-012,
    TS-015, TS-020, TS-022, TS-023.

All ``bpy`` dependencies are mocked via conftest.py fixtures.
Imports from ``tessera.*`` are deferred to test body to allow
the conftest ``mock_bpy`` fixture to inject ``bpy`` first.
"""

from __future__ import annotations

import re

import pytest


# -------------------------------------------------------------------
# TS-001: ErrorHandler classifies OutOfMemoryError → BF-E001/BF-E002
# -------------------------------------------------------------------
class TestErrorClassification:
    """Test exception-to-error-code classification."""

    def test_oom_during_loading_returns_bf_e001(self) -> None:
        """OutOfMemoryError during model loading → BF-E001."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.categories import ErrorSeverity
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = RuntimeError("CUDA out of memory")
        result = handler.catch(exc, "vision", {"phase": "loading"})
        assert result.code == "BF-E001"
        assert result.severity == ErrorSeverity.CRITICAL

    def test_oom_during_inference_returns_bf_e002(self) -> None:
        """OutOfMemoryError during inference → BF-E002."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = RuntimeError("CUDA out of memory")
        result = handler.catch(exc, "vision", {"phase": "inference"})
        assert result.code == "BF-E002"

    def test_file_not_found_returns_bf_e006(self) -> None:
        """FileNotFoundError → BF-E006."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = FileNotFoundError("model.safetensors")
        result = handler.catch(exc, "model_loading")
        assert result.code == "BF-E006"

    def test_value_error_unsupported_format_returns_bf_e003(self) -> None:
        """ValueError with 'unsupported format' → BF-E003."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = ValueError("unsupported format .bmp")
        result = handler.catch(exc, "preprocessing")
        assert result.code == "BF-E003"

    def test_timeout_error_returns_bf_e009(self) -> None:
        """TimeoutError → BF-E009."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = TimeoutError("reconstruction exceeded 120s")
        result = handler.catch(exc, "reconstruction")
        assert result.code == "BF-E009"

    def test_permission_error_returns_bf_e011(self) -> None:
        """PermissionError → BF-E011."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = PermissionError("write access denied")
        result = handler.catch(exc, "export")
        assert result.code == "BF-E011"

    def test_import_error_returns_bf_e014(self) -> None:
        """ImportError → BF-E014."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = ImportError("No module named 'torch'")
        result = handler.catch(exc, "initialization")
        assert result.code == "BF-E014"

    def test_unknown_error_returns_bf_e999(self) -> None:
        """Unclassifiable exception → BF-E999 fallback."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = ZeroDivisionError("division by zero")
        result = handler.catch(exc, "unknown")
        assert result.code == "BF-E999"


# -------------------------------------------------------------------
# TS-002: Error catalog completeness
# -------------------------------------------------------------------
class TestErrorCatalog:
    """Test error catalog structure and coverage."""

    def test_catalog_has_16_entries_plus_fallback(self) -> None:
        """Catalog contains 16 mandatory codes + BF-E999."""
        from tessera.errors.catalog import ERROR_CATALOG

        assert len(ERROR_CATALOG) == 17

    def test_all_entries_are_catalog_entry_instances(self) -> None:
        """Every catalog value is an ErrorCatalogEntry."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.categories import ErrorCatalogEntry

        for code, entry in ERROR_CATALOG.items():
            assert isinstance(entry, ErrorCatalogEntry), f"{code} not ErrorCatalogEntry"

    def test_all_messages_are_at_least_20_chars(self) -> None:
        """Every error message ≥ 20 characters."""
        from tessera.errors.catalog import ERROR_CATALOG

        for code, entry in ERROR_CATALOG.items():
            assert len(entry.message) >= 20, f"{code}: message too short"

    def test_all_entries_have_resolution_steps(self) -> None:
        """Every entry has ≥ 1 resolution step."""
        from tessera.errors.catalog import ERROR_CATALOG

        for code, entry in ERROR_CATALOG.items():
            assert len(entry.resolution_steps) >= 1, f"{code}: no resolution steps"

    def test_bf_e999_fallback_exists(self) -> None:
        """BF-E999 fallback entry exists."""
        from tessera.errors.catalog import ERROR_CATALOG

        assert "BF-E999" in ERROR_CATALOG

    def test_error_codes_have_consistent_format(self) -> None:
        """All error codes match BF-EXXX pattern."""
        from tessera.errors.catalog import ERROR_CATALOG

        for code in ERROR_CATALOG:
            assert re.match(r"^BF-E\d{3}$", code), f"{code}: bad format"


# -------------------------------------------------------------------
# TS-007: User-facing message format
# -------------------------------------------------------------------
class TestErrorMessageFormat:
    """Test error message formatting."""

    def test_message_starts_with_error_code(self) -> None:
        """User message starts with [BF-EXXX]."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = FileNotFoundError("model.safetensors")
        result = handler.catch(exc, "model_loading")
        assert result.user_message.startswith("[BF-E006]")

    def test_message_contains_try_prefix(self) -> None:
        """User message contains 'Try:' with a resolution step."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = FileNotFoundError("model.safetensors")
        result = handler.catch(exc, "model_loading")
        assert "Try:" in result.user_message


# -------------------------------------------------------------------
# TS-008: SEC-001 — No stack traces in user messages
# -------------------------------------------------------------------
class TestSecurityRequirements:
    """Test security requirements for error handling."""

    def test_no_traceback_in_user_message(self) -> None:
        """User message must not contain traceback lines (SEC-001)."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = ValueError("unsupported format .bmp")
        result = handler.catch(exc, "preprocessing")
        assert "Traceback" not in result.user_message
        assert "File " not in result.user_message

    def test_no_full_paths_in_user_message(self) -> None:
        """User message must not contain full paths (SEC-006)."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = FileNotFoundError("/home/user/models/model.safetensors")
        result = handler.catch(exc, "model_loading")
        assert "/home/" not in result.user_message


# -------------------------------------------------------------------
# TS-009: Input validation — unsupported format
# -------------------------------------------------------------------
class TestInputValidation:
    """Test image input validation."""

    def test_validate_unsupported_format(self, tmp_path) -> None:
        """Unsupported format returns BF-E003."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        bmp_file = tmp_path / "test.bmp"
        bmp_file.write_bytes(b"\x00" * 100)
        result = handler.validate_input_image(str(bmp_file))
        assert result is not None
        assert result.code == "BF-E003"

    def test_validate_supported_format(self, tmp_path) -> None:
        """Supported format returns None (valid)."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        png_file = tmp_path / "test.png"
        png_file.write_bytes(b"\x89PNG" + b"\x00" * 100)
        result = handler.validate_input_image(str(png_file))
        assert result is None

    def test_validate_missing_file(self) -> None:
        """Missing file returns BF-E006."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        result = handler.validate_input_image("/nonexistent/image.png")
        assert result is not None
        assert result.code == "BF-E006"

    def test_validate_empty_file(self, tmp_path) -> None:
        """Empty file returns BF-E003."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        empty = tmp_path / "empty.png"
        empty.write_bytes(b"")
        result = handler.validate_input_image(str(empty))
        assert result is not None
        assert result.code == "BF-E003"


# -------------------------------------------------------------------
# TS-010: Image dimensions validation
# -------------------------------------------------------------------
class TestDimensionValidation:
    """Test image dimension validation."""

    def test_low_resolution_returns_bf_e004(self) -> None:
        """Resolution < 256×256 → BF-E004."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        result = handler.validate_image_dimensions(128, 128)
        assert result is not None
        assert result.code == "BF-E004"

    def test_valid_resolution_returns_none(self) -> None:
        """Resolution ≥ 256×256 → valid."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        result = handler.validate_image_dimensions(512, 512)
        assert result is None


# -------------------------------------------------------------------
# TS-012: Blur detection
# -------------------------------------------------------------------
class TestBlurDetection:
    """Test blur detection."""

    def test_blurry_image_returns_bf_e005(self) -> None:
        """Low Laplacian variance → BF-E005 WARNING."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.categories import ErrorSeverity
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        result = handler.check_blur(50.0, "test.jpg")
        assert result is not None
        assert result.code == "BF-E005"
        assert result.severity == ErrorSeverity.WARNING

    def test_sharp_image_returns_none(self) -> None:
        """High Laplacian variance → valid."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        result = handler.check_blur(200.0, "test.jpg")
        assert result is None


# -------------------------------------------------------------------
# TS-015: Cascading error suppression (EC-001)
# -------------------------------------------------------------------
class TestCascadingSuppression:
    """Test cascading error suppression."""

    def test_first_error_is_reported(self) -> None:
        """First error is fully reported."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        exc = RuntimeError("CUDA out of memory")
        result = handler.catch(exc, "vision", {"phase": "loading"})
        assert result.user_message != ""

    def test_subsequent_errors_are_suppressed(self) -> None:
        """Subsequent errors have empty user_message."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        handler.catch(
            RuntimeError("CUDA out of memory"), "vision", {"phase": "loading"}
        )
        result = handler.catch(
            FileNotFoundError("missing"), "reconstruction"
        )
        assert result.user_message == ""

    def test_reset_clears_suppression(self) -> None:
        """reset() allows new errors to be reported."""
        from tessera.errors.catalog import ERROR_CATALOG
        from tessera.errors.handler import ErrorHandler

        handler = ErrorHandler(catalog=ERROR_CATALOG)
        handler.catch(
            RuntimeError("CUDA out of memory"), "vision", {"phase": "loading"}
        )
        handler.reset()
        result = handler.catch(
            FileNotFoundError("missing"), "reconstruction"
        )
        assert result.user_message != ""


# -------------------------------------------------------------------
# TS-020: UIReporter error log size limit
# -------------------------------------------------------------------
class TestUIReporter:
    """Test UIReporter functionality."""

    def test_log_capped_at_50(self) -> None:
        """Error log does not exceed 50 entries."""
        from tessera.errors.categories import ErrorSeverity
        from tessera.errors.ui_reporter import UIReporter

        reporter = UIReporter()
        for i in range(60):
            reporter.show(
                code=f"BF-E{i:03d}",
                message=f"Test error {i}",
                severity=ErrorSeverity.ERROR,
            )
        assert reporter.error_count == 50

    def test_clear_empties_log(self) -> None:
        """clear() removes all entries."""
        from tessera.errors.categories import ErrorSeverity
        from tessera.errors.ui_reporter import UIReporter

        reporter = UIReporter()
        reporter.show("BF-E001", "Test", ErrorSeverity.ERROR)
        reporter.clear()
        assert reporter.error_count == 0


# -------------------------------------------------------------------
# TS-022 / TS-023: ErrorResult serialization
# -------------------------------------------------------------------
class TestErrorResult:
    """Test ErrorResult dataclass."""

    def test_error_result_has_required_fields(self) -> None:
        """ErrorResult contains all required fields."""
        from tessera.errors.categories import ErrorResult, ErrorSeverity

        result = ErrorResult(
            code="BF-E001",
            user_message="Test",
            severity=ErrorSeverity.CRITICAL,
            resolution_steps=["step 1"],
        )
        assert result.code == "BF-E001"
        assert result.severity == ErrorSeverity.CRITICAL
        assert len(result.resolution_steps) == 1

    def test_error_log_entry_timestamp_format(self) -> None:
        """LogEntry timestamp_str formats as HH:MM:SS."""
        from tessera.errors.categories import ErrorSeverity
        from tessera.errors.ui_reporter import ErrorLogEntry

        entry = ErrorLogEntry(
            timestamp=1713300000.0,
            code="BF-E001",
            severity=ErrorSeverity.ERROR,
            message="Test",
        )
        assert re.match(r"\d{2}:\d{2}:\d{2}", entry.timestamp_str)

    def test_truncated_message_at_80_chars(self) -> None:
        """Messages > 80 chars are truncated with ellipsis."""
        from tessera.errors.categories import ErrorSeverity
        from tessera.errors.ui_reporter import ErrorLogEntry

        long_msg = "A" * 100
        entry = ErrorLogEntry(
            timestamp=0.0,
            code="BF-E001",
            severity=ErrorSeverity.ERROR,
            message=long_msg,
        )
        assert len(entry.truncated_message) == 80
        assert entry.truncated_message.endswith("...")
