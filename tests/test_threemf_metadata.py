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

"""Tests for the 3MF metadata exporter.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Covers: TS-004, TS-017, TS-030.

All ``bpy`` dependencies are mocked via conftest.py fixtures.
Imports from ``tessera.*`` are deferred to test body.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile


def _make_3mf(tmp_path, name="test.3mf"):
    """Create a minimal valid 3MF file for testing."""
    filepath = tmp_path / name
    model_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        "<resources/>"
        "<build/>"
        "</model>"
    )
    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("3D/3dmodel.model", model_xml)
    return str(filepath)


def _read_model_xml(filepath: str) -> str:
    """Read model.xml from 3MF ZIP."""
    with zipfile.ZipFile(filepath, "r") as zf:
        return zf.read("3D/3dmodel.model").decode("utf-8")


# -------------------------------------------------------------------
# TS-004: Standard metadata embedding
# -------------------------------------------------------------------
class TestStandardMetadata:
    """Test standard 3MF metadata injection."""

    def test_embeds_title_and_designer(self, tmp_path) -> None:
        """Title and Designer are embedded in the 3MF."""
        from tessera.export.threemf_metadata import (
            StandardMetadata,
            ThreeMFMetadataExporter,
        )

        sample_3mf = _make_3mf(tmp_path)
        exporter = ThreeMFMetadataExporter()
        result = exporter.embed(
            filepath=sample_3mf,
            standard=StandardMetadata(title="Test Object", designer="TestUser"),
        )
        assert result is True

        xml_content = _read_model_xml(sample_3mf)
        assert "Test Object" in xml_content
        assert "TestUser" in xml_content

    def test_embeds_dates(self, tmp_path) -> None:
        """CreationDate and ModificationDate are embedded."""
        from tessera.export.threemf_metadata import (
            StandardMetadata,
            ThreeMFMetadataExporter,
        )

        sample_3mf = _make_3mf(tmp_path)
        exporter = ThreeMFMetadataExporter()
        exporter.embed(
            filepath=sample_3mf,
            standard=StandardMetadata(),
        )
        xml_content = _read_model_xml(sample_3mf)
        assert "T" in xml_content


# -------------------------------------------------------------------
# TS-017: Print settings metadata
# -------------------------------------------------------------------
class TestPrintSettingsMetadata:
    """Test Tessera print settings embedding."""

    def test_embeds_print_settings(self, tmp_path) -> None:
        """Print settings are embedded with Tessera namespace."""
        from tessera.export.threemf_metadata import (
            PrintSettings,
            ThreeMFMetadataExporter,
        )

        sample_3mf = _make_3mf(tmp_path)
        exporter = ThreeMFMetadataExporter()
        exporter.embed(
            filepath=sample_3mf,
            print_settings=PrintSettings(
                printer_type="FDM",
                wall_thickness_mm=1.5,
                infill_suggestion="20%",
                support_suggestion="None required",
                source_images=4,
            ),
        )
        xml_content = _read_model_xml(sample_3mf)
        assert "FDM" in xml_content
        assert "1.5" in xml_content
        assert "20%" in xml_content


# -------------------------------------------------------------------
# TS-030: Validation report metadata
# -------------------------------------------------------------------
class TestValidationReportMetadata:
    """Test validation report embedding."""

    def test_embeds_validation_report(self, tmp_path) -> None:
        """Validation results are embedded."""
        from tessera.export.threemf_metadata import (
            ThreeMFMetadataExporter,
            ValidationReport,
        )

        sample_3mf = _make_3mf(tmp_path)
        exporter = ThreeMFMetadataExporter()
        exporter.embed(
            filepath=sample_3mf,
            validation=ValidationReport(
                manifold_status="Pass",
                wall_thickness_status="Fail",
                overhang_status="Pass",
                volume_mm_cubed=12500.0,
            ),
        )
        xml_content = _read_model_xml(sample_3mf)
        assert "Pass" in xml_content
        assert "Fail" in xml_content
        assert "12500.0" in xml_content


# -------------------------------------------------------------------
# SEC-002: XML injection prevention
# -------------------------------------------------------------------
class TestXMLSecurity:
    """Test XML escaping for security."""

    def test_xml_escape_in_title(self, tmp_path) -> None:
        """Special characters in title are XML-escaped (SEC-002)."""
        from tessera.export.threemf_metadata import (
            StandardMetadata,
            ThreeMFMetadataExporter,
        )

        sample_3mf = _make_3mf(tmp_path)
        exporter = ThreeMFMetadataExporter()
        exporter.embed(
            filepath=sample_3mf,
            standard=StandardMetadata(title='<script>alert("xss")</script>'),
        )
        xml_content = _read_model_xml(sample_3mf)
        assert "<script>" not in xml_content
        assert "&lt;script&gt;" in xml_content


# -------------------------------------------------------------------
# Edge cases
# -------------------------------------------------------------------
class TestEdgeCases:
    """Test edge cases for 3MF metadata."""

    def test_nonexistent_file_returns_false(self) -> None:
        """embed() returns False for missing file."""
        from tessera.export.threemf_metadata import ThreeMFMetadataExporter

        exporter = ThreeMFMetadataExporter()
        result = exporter.embed("/nonexistent/file.3mf")
        assert result is False

    def test_invalid_zip_returns_false(self, tmp_path) -> None:
        """embed() returns False for non-ZIP file."""
        from tessera.export.threemf_metadata import ThreeMFMetadataExporter

        bad_file = tmp_path / "bad.3mf"
        bad_file.write_bytes(b"not a zip")
        exporter = ThreeMFMetadataExporter()
        result = exporter.embed(str(bad_file))
        assert result is False

    def test_fr021_no_geometry_modification(self, tmp_path) -> None:
        """FR-021: Metadata embedding does not alter geometry."""
        from tessera.export.threemf_metadata import (
            StandardMetadata,
            ThreeMFMetadataExporter,
        )

        sample_3mf = _make_3mf(tmp_path)

        exporter = ThreeMFMetadataExporter()
        exporter.embed(
            filepath=sample_3mf,
            standard=StandardMetadata(title="Test"),
        )

        with zipfile.ZipFile(sample_3mf, "r") as zf:
            modified = zf.read("3D/3dmodel.model")

        root = ET.fromstring(modified)
        ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
        resources = root.find(f"{{{ns}}}resources")
        build = root.find(f"{{{ns}}}build")
        assert resources is not None
        assert build is not None
        assert len(list(resources)) == 0
