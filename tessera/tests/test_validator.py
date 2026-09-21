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

"""Comprehensive test suite for the print-readiness validator.

Tests the data types, validation report, and pure-Python helper
functions that do NOT depend on ``bmesh`` or ``bpy``.

Spec: SPEC-TS-0006 (Print-Readiness Validator & Export Pipeline)

AC: AC-001 through AC-010.
EC: EC-001 through EC-007.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest

# Import data types and report directly (no bmesh dependency chain).
from tessera.validator.data_types import (
    CheckResult,
    CheckStatus,
    ExportResult,
    RepairResult,
)
from tessera.validator.report import ValidationReport


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CheckStatus enum
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCheckStatus:
    """Tests for CheckStatus enum (FR-028)."""

    def test_enum_has_three_values(self):
        """CheckStatus defines exactly PASS, WARN, FAIL."""
        members = list(CheckStatus)
        assert len(members) == 3
        assert CheckStatus.PASS in members
        assert CheckStatus.WARN in members
        assert CheckStatus.FAIL in members

    @pytest.mark.parametrize(
        "member,expected_value",
        [
            (CheckStatus.PASS, "PASS"),
            (CheckStatus.WARN, "WARN"),
            (CheckStatus.FAIL, "FAIL"),
        ],
    )
    def test_enum_string_values(self, member, expected_value):
        """Each status serializes to its uppercase string."""
        assert member.value == expected_value


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CheckResult dataclass
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCheckResult:
    """Tests for CheckResult dataclass (FR-028)."""

    @pytest.fixture
    def pass_result(self) -> CheckResult:
        """Create a PASS CheckResult fixture."""
        return CheckResult(
            check_name="Non-Manifold Edges",
            status=CheckStatus.PASS,
            message="No non-manifold edges detected.",
            details={"non_manifold_edge_count": 0},
        )

    @pytest.fixture
    def fail_result(self) -> CheckResult:
        """Create a FAIL CheckResult with repair info."""
        return CheckResult(
            check_name="Wall Thickness",
            status=CheckStatus.FAIL,
            message="500 faces below 1.2 mm threshold.",
            details={
                "thin_face_count": 500,
                "min_thickness_mm": 0.8,
                "threshold_mm": 1.2,
            },
            repaired=True,
            repair_message="Applied Solidify modifier with 0.5 mm offset.",
        )

    def test_to_dict_serializes_all_fields(self, pass_result):
        """AC-001: to_dict() produces FR-028-conformant dict."""
        d = pass_result.to_dict()
        assert d["check_name"] == "Non-Manifold Edges"
        assert d["status"] == "PASS"
        assert d["message"] == "No non-manifold edges detected."
        assert d["details"] == {"non_manifold_edge_count": 0}
        assert d["repaired"] is False
        assert d["repair_message"] is None

    def test_to_dict_includes_repair_info(self, fail_result):
        """AC-001: to_dict() includes repair fields when set."""
        d = fail_result.to_dict()
        assert d["repaired"] is True
        assert d["repair_message"] == (
            "Applied Solidify modifier with 0.5 mm offset."
        )

    def test_to_dict_status_is_string_not_enum(self, pass_result):
        """FR-028: Status is serialized as string value, not enum."""
        d = pass_result.to_dict()
        assert isinstance(d["status"], str)
        assert d["status"] == "PASS"

    def test_defaults_for_optional_fields(self):
        """Unset optional fields have correct defaults."""
        r = CheckResult(
            check_name="Test",
            status=CheckStatus.WARN,
            message="Warning",
        )
        assert r.details == {}
        assert r.repaired is False
        assert r.repair_message is None

    def test_details_accepts_nested_data(self):
        """details dict supports nested structures."""
        r = CheckResult(
            check_name="Test",
            status=CheckStatus.PASS,
            message="ok",
            details={
                "intersection_pairs": 15,
                "elapsed_seconds": 1.23,
                "pair_indices": [(1, 2), (3, 4)],
            },
        )
        d = r.to_dict()
        assert d["details"]["intersection_pairs"] == 15
        assert len(d["details"]["pair_indices"]) == 2

    def test_to_dict_is_json_serializable(self, pass_result):
        """to_dict() output can be serialized to JSON."""
        d = pass_result.to_dict()
        json_str = json.dumps(d)
        roundtrip = json.loads(json_str)
        assert roundtrip == d


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RepairResult dataclass
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestRepairResult:
    """Tests for RepairResult dataclass."""

    def test_success_result(self):
        """success=True with message."""
        r = RepairResult(success=True, message="Fixed it.")
        assert r.success is True
        assert r.message == "Fixed it."

    def test_failure_result(self):
        """success=False with failure reason."""
        r = RepairResult(success=False, message="Cannot fix.")
        assert r.success is False
        assert r.message == "Cannot fix."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ExportResult dataclass
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestExportResult:
    """Tests for ExportResult dataclass."""

    def test_default_fields(self):
        """Defaults: empty list, success=False."""
        r = ExportResult(report=None)
        assert r.exported_files == []
        assert r.success is False

    def test_success_with_files(self):
        """Populated result with exported files."""
        r = ExportResult(
            report=MagicMock(),
            exported_files=["/tmp/Cube.stl", "/tmp/Cube.3mf"],
            success=True,
        )
        assert len(r.exported_files) == 2
        assert r.success is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ValidationReport
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestValidationReport:
    """Tests for ValidationReport (FR-028, FR-029, FR-030, FR-032)."""

    @pytest.fixture
    def empty_report(self) -> ValidationReport:
        """Create an empty report fixture."""
        return ValidationReport(object_name="Cube", printer_type="FDM")

    @pytest.fixture
    def mixed_report(self) -> ValidationReport:
        """Create a report with PASS, WARN, and FAIL checks."""
        report = ValidationReport(object_name="Bust", printer_type="SLA")
        report.add_check(
            CheckResult("Manifold", CheckStatus.PASS, "OK")
        )
        report.add_check(
            CheckResult("Overhang", CheckStatus.WARN, "Some overhangs")
        )
        report.add_check(
            CheckResult(
                "Wall Thickness",
                CheckStatus.FAIL,
                "Too thin",
                repaired=True,
                repair_message="Solidified",
            )
        )
        report.add_check(
            CheckResult("Volume", CheckStatus.PASS, "Positive volume")
        )
        report.validation_time_seconds = 2.345
        return report

    # ── Construction and add_check ─────────────────────────────────

    def test_init_creates_empty_checks_list(self, empty_report):
        """New report has zero checks."""
        assert empty_report.checks == []
        assert empty_report.object_name == "Cube"
        assert empty_report.printer_type == "FDM"

    def test_init_sets_utc_timestamp(self, empty_report):
        """Timestamp is set in UTC ISO format."""
        assert "T" in empty_report._timestamp
        assert "+" in empty_report._timestamp or "Z" in empty_report._timestamp

    def test_add_check_appends_to_list(self, empty_report):
        """add_check() appends CheckResult to checks list."""
        result = CheckResult("Test", CheckStatus.PASS, "ok")
        empty_report.add_check(result)
        assert len(empty_report.checks) == 1
        assert empty_report.checks[0] is result

    def test_add_check_preserves_order(self, mixed_report):
        """Checks maintain insertion order."""
        names = [c.check_name for c in mixed_report.checks]
        assert names == [
            "Manifold",
            "Overhang",
            "Wall Thickness",
            "Volume",
        ]

    # ── Summary counts ─────────────────────────────────────────────

    def test_passed_count(self, mixed_report):
        """passed property counts PASS checks."""
        assert mixed_report.passed == 2

    def test_warnings_count(self, mixed_report):
        """warnings property counts WARN checks."""
        assert mixed_report.warnings == 1

    def test_failures_count(self, mixed_report):
        """failures property counts FAIL checks."""
        assert mixed_report.failures == 1

    def test_auto_repairs_applied_count(self, mixed_report):
        """auto_repairs_applied counts checks where repaired=True."""
        assert mixed_report.auto_repairs_applied == 1

    def test_has_failures_true_when_fails_exist(self, mixed_report):
        """has_failures is True when at least one FAIL exists."""
        assert mixed_report.has_failures is True

    def test_has_failures_false_when_all_pass(self):
        """has_failures is False when no FAIL checks."""
        report = ValidationReport("Cube")
        report.add_check(
            CheckResult("A", CheckStatus.PASS, "ok")
        )
        report.add_check(
            CheckResult("B", CheckStatus.WARN, "warn")
        )
        assert report.has_failures is False

    def test_empty_report_counts_zero(self, empty_report):
        """All counts are 0 for empty report."""
        assert empty_report.passed == 0
        assert empty_report.warnings == 0
        assert empty_report.failures == 0
        assert empty_report.auto_repairs_applied == 0
        assert empty_report.has_failures is False

    # ── to_dict (FR-028, FR-032) ───────────────────────────────────

    def test_to_dict_schema(self, mixed_report):
        """FR-032: to_dict() produces complete schema."""
        d = mixed_report.to_dict()

        # Top-level keys.
        assert d["object_name"] == "Bust"
        assert d["printer_type"] == "SLA"
        assert "timestamp" in d
        assert isinstance(d["checks"], list)
        assert len(d["checks"]) == 4
        assert isinstance(d["summary"], dict)

    def test_to_dict_summary_fields(self, mixed_report):
        """FR-032: Summary contains all expected counters."""
        s = mixed_report.to_dict()["summary"]
        assert s["total_checks"] == 4
        assert s["passed"] == 2
        assert s["warnings"] == 1
        assert s["failures"] == 1
        assert s["auto_repairs_applied"] == 1
        assert s["validation_time_seconds"] == 2.35  # Rounded to 2 dp.
        assert s["export_time_seconds"] == 0.0

    def test_to_dict_checks_are_serialized(self, mixed_report):
        """Each check in to_dict() is a dict, not a CheckResult."""
        d = mixed_report.to_dict()
        for check_dict in d["checks"]:
            assert isinstance(check_dict, dict)
            assert "check_name" in check_dict
            assert "status" in check_dict

    # ── to_json (FR-028) ───────────────────────────────────────────

    def test_to_json_returns_valid_json(self, mixed_report):
        """AC-009: to_json() returns valid JSON string."""
        json_str = mixed_report.to_json()
        parsed = json.loads(json_str)
        assert parsed["object_name"] == "Bust"
        assert len(parsed["checks"]) == 4

    def test_to_json_roundtrips_with_to_dict(self, mixed_report):
        """JSON roundtrip matches to_dict() output."""
        d = mixed_report.to_dict()
        json_str = mixed_report.to_json()
        roundtrip = json.loads(json_str)
        assert roundtrip == d

    def test_to_json_custom_indent(self, mixed_report):
        """to_json(indent=4) produces wider indentation."""
        json_str = mixed_report.to_json(indent=4)
        # 4-space indent means lines start with "    ".
        lines = json_str.split("\n")
        indented = [l for l in lines if l.startswith("    ")]
        assert len(indented) > 0

    # ── save_json (FR-029) ─────────────────────────────────────────

    def test_save_json_creates_file(self, mixed_report, tmp_path):
        """FR-029: save_json() writes valid JSON file."""
        path = str(tmp_path / "report.json")
        mixed_report.save_json(path)

        assert os.path.exists(path)

        with open(path, "r", encoding="utf-8") as f:
            parsed = json.load(f)

        assert parsed["object_name"] == "Bust"
        assert parsed["summary"]["total_checks"] == 4

    def test_save_json_overwrites_existing(self, mixed_report, tmp_path):
        """save_json() overwrites existing file."""
        path = str(tmp_path / "report.json")

        # Write first report.
        mixed_report.save_json(path)

        # Write second report.
        report2 = ValidationReport("Sphere")
        report2.add_check(CheckResult("A", CheckStatus.PASS, "ok"))
        report2.save_json(path)

        with open(path, "r", encoding="utf-8") as f:
            parsed = json.load(f)

        assert parsed["object_name"] == "Sphere"
        assert parsed["summary"]["total_checks"] == 1

    # ── to_text (FR-030) ───────────────────────────────────────────

    def test_to_text_contains_object_name(self, mixed_report):
        """FR-030: Text report includes object name."""
        text = mixed_report.to_text()
        assert "Bust" in text

    def test_to_text_contains_printer_type(self, mixed_report):
        """FR-030: Text report includes printer type."""
        text = mixed_report.to_text()
        assert "SLA" in text

    def test_to_text_contains_header(self, mixed_report):
        """FR-030: Text report starts with header line."""
        text = mixed_report.to_text()
        assert text.startswith("=== Tessera Print Validation Report ===")

    def test_to_text_pass_check_format(self, mixed_report):
        """FR-030: PASS checks show [PASS] name only."""
        text = mixed_report.to_text()
        assert "[PASS] Manifold" in text

    def test_to_text_warn_check_format(self, mixed_report):
        """FR-030: WARN checks show [WARN] name: message."""
        text = mixed_report.to_text()
        assert "[WARN] Overhang: Some overhangs" in text

    def test_to_text_fail_check_with_repair(self, mixed_report):
        """FR-030: Repaired FAIL checks show (Auto-repaired) suffix."""
        text = mixed_report.to_text()
        assert "[FAIL] Wall Thickness: Too thin (Auto-repaired)" in text

    def test_to_text_summary_line(self, mixed_report):
        """FR-030: Summary line at end shows pass/total."""
        text = mixed_report.to_text()
        assert "Result: 2/4 checks passed, 1 warnings, 1 failures." in text

    def test_to_text_all_passing(self):
        """FR-030: All-pass report shows N/N checks passed."""
        report = ValidationReport("Cube")
        report.add_check(CheckResult("A", CheckStatus.PASS, "ok"))
        report.add_check(CheckResult("B", CheckStatus.PASS, "ok"))
        text = report.to_text()
        assert "Result: 2/2 checks passed, 0 warnings, 0 failures." in text
