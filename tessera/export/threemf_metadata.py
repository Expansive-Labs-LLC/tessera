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

"""3MF metadata embedding for Tessera exports.

Post-processes exported 3MF files to inject Tessera-specific print
settings and validation report metadata into the 3MF XML (model.xml
inside the ZIP archive).

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-017, FR-018, FR-019, FR-020, FR-021, FR-022,
    CON-008, SEC-002.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("tessera.export")

# FR-019: Custom Tessera XML namespace.
TESSERA_NS = "http://tessera.org/spec/2026/04"
TESSERA_NS_PREFIX = "bf"

# Standard 3MF namespace.
_3MF_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"


@dataclass
class PrintSettings:
    """Print settings to embed into the 3MF file.

    All values are computed during the pipeline and passed
    in for metadata embedding.

    Attributes:
        printer_type: Target printer type (e.g., ``"FDM"``, ``"SLA"``).
        wall_thickness_mm: Minimum wall thickness in mm.
        infill_suggestion: Infill percentage suggestion based on
            volume analysis.
        support_suggestion: Support structure recommendation based
            on overhang angles.
        source_images: Number of source reference images used.

    Implements: FR-019.
    """

    printer_type: str = "FDM"
    wall_thickness_mm: float = 1.2
    infill_suggestion: str = "20%"
    support_suggestion: str = "None required"
    source_images: int = 1


@dataclass
class ValidationReport:
    """Validation results to embed into the 3MF file.

    Attributes:
        manifold_status: ``"Pass"`` or ``"Fail"`` from manifold check.
        wall_thickness_status: ``"Pass"`` or ``"Fail"`` from
            wall-thickness check.
        overhang_status: ``"Pass"`` or ``"Fail"`` from overhang check.
        volume_mm_cubed: Object volume in cubic millimeters.

    Implements: FR-020.
    """

    manifold_status: str = "Pass"
    wall_thickness_status: str = "Pass"
    overhang_status: str = "Pass"
    volume_mm_cubed: float = 0.0


@dataclass
class StandardMetadata:
    """Standard 3MF metadata fields.

    Attributes:
        title: Object title.
        designer: Designer name.
        description: Object description.
        creation_date: ISO 8601 timestamp of creation.
        modification_date: ISO 8601 timestamp of last modification.

    Implements: FR-018.
    """

    title: str = "Tessera Export"
    designer: str = "Tessera"
    description: str = ""
    creation_date: str = ""
    modification_date: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.creation_date:
            self.creation_date = now
        if not self.modification_date:
            self.modification_date = now


class ThreeMFMetadataExporter:
    """Embeds Tessera metadata into exported 3MF files.

    Manipulates the ``3D/3dmodel.model`` XML inside the 3MF ZIP
    to add standard metadata (title, designer, dates) and custom
    Tessera-namespaced metadata (print settings, validation report).

    FR-021: This class modifies metadata ONLY — never alters the
    mesh geometry.

    SEC-002: All user-provided strings are XML-escaped to prevent
    injection.

    Usage::

        exporter = ThreeMFMetadataExporter()
        exporter.embed(
            filepath="/path/to/output.3mf",
            standard=StandardMetadata(title="My Object"),
            print_settings=PrintSettings(wall_thickness_mm=1.5),
            validation=ValidationReport(manifold_status="Pass"),
        )

    Implements: FR-017 through FR-022, CON-008, SEC-002.
    """

    # 3MF model XML path inside the ZIP archive.
    _MODEL_PATH = "3D/3dmodel.model"

    def embed(
        self,
        filepath: str,
        standard: Optional[StandardMetadata] = None,
        print_settings: Optional[PrintSettings] = None,
        validation: Optional[ValidationReport] = None,
    ) -> bool:
        """Embed metadata into a 3MF file.

        Args:
            filepath: Path to the 3MF file.
            standard: Standard 3MF metadata fields.
            print_settings: Tessera print settings.
            validation: Tessera validation report.

        Returns:
            ``True`` if metadata was successfully embedded,
            ``False`` if the file could not be processed.

        Implements: FR-017, FR-018, FR-019, FR-020.
        """
        if not os.path.exists(filepath):
            logger.error(
                "3MF metadata failed: file not found: %s",
                os.path.basename(filepath),
            )
            return False

        if standard is None:
            standard = StandardMetadata()

        try:
            # Read the existing 3MF ZIP.
            model_xml = self._read_model_xml(filepath)
            if model_xml is None:
                logger.error(
                    "3MF metadata failed: no model XML found in: %s",
                    os.path.basename(filepath),
                )
                return False

            # Parse the XML.
            # Register Tessera namespace before parsing so it appears
            # as a proper prefix in the output.
            ET.register_namespace(TESSERA_NS_PREFIX, TESSERA_NS)
            ET.register_namespace("", _3MF_NS)

            root = ET.fromstring(model_xml)

            # Inject standard metadata (FR-018).
            self._inject_standard_metadata(root, standard)

            # Inject print settings (FR-019).
            if print_settings is not None:
                self._inject_print_settings(root, print_settings)

            # Inject validation report (FR-020).
            if validation is not None:
                self._inject_validation_report(root, validation)

            # Write the modified XML back to the ZIP.
            modified_xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
            self._write_model_xml(filepath, modified_xml)

            logger.info(
                "3MF metadata embedded: file=%s",
                os.path.basename(filepath),
            )
            return True

        except Exception as exc:
            logger.error(
                "3MF metadata embedding failed: %s",
                str(exc),
            )
            return False

    def _read_model_xml(self, filepath: str) -> Optional[str]:
        """Read model.xml from a 3MF ZIP file.

        Args:
            filepath: Path to the 3MF file.

        Returns:
            XML string or ``None`` if not found.
        """
        try:
            with zipfile.ZipFile(filepath, "r") as zf:
                if self._MODEL_PATH in zf.namelist():
                    return zf.read(self._MODEL_PATH).decode("utf-8")
        except (zipfile.BadZipFile, KeyError, OSError) as exc:
            logger.error("Cannot read 3MF archive: %s", str(exc))
        return None

    def _write_model_xml(self, filepath: str, xml_content: str) -> None:
        """Write modified model.xml back to the 3MF ZIP.

        Creates a temporary file, copies all entries, replaces
        model.xml, then atomically replaces the original.

        Args:
            filepath: Path to the original 3MF file.
            xml_content: Modified XML string.
        """
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".3mf")
        os.close(tmp_fd)

        try:
            with zipfile.ZipFile(filepath, "r") as zf_in:
                with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf_out:
                    for item in zf_in.infolist():
                        if item.filename == self._MODEL_PATH:
                            zf_out.writestr(item, xml_content.encode("utf-8"))
                        else:
                            zf_out.writestr(item, zf_in.read(item.filename))

            # Atomic replace.
            shutil.move(tmp_path, filepath)
        except Exception:
            # Clean up temp file on failure.
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _inject_standard_metadata(
        self,
        root: ET.Element,
        meta: StandardMetadata,
    ) -> None:
        """Inject standard 3MF metadata elements.

        Adds or updates: Title, Designer, CreationDate,
        ModificationDate, Description.

        Args:
            root: XML root element.
            meta: Standard metadata values.

        Implements: FR-018, SEC-002.
        """
        metadata_fields = {
            "Title": meta.title,
            "Designer": meta.designer,
            "CreationDate": meta.creation_date,
            "ModificationDate": meta.modification_date,
            "Description": meta.description,
        }

        for name, value in metadata_fields.items():
            if not value:
                continue

            # SEC-002: ElementTree escapes text content automatically
            # when serializing via ET.tostring(). No manual escape needed.
            text_value = str(value)

            # Find existing metadata element or create new one.
            existing = root.find(f".//{{{_3MF_NS}}}metadata[@name='{name}']")
            if existing is not None:
                existing.text = text_value
            else:
                elem = ET.SubElement(root, f"{{{_3MF_NS}}}metadata")
                elem.set("name", name)
                elem.text = text_value

    def _inject_print_settings(
        self,
        root: ET.Element,
        settings: PrintSettings,
    ) -> None:
        """Inject Tessera print settings as custom-namespaced metadata.

        Adds: bf:PrinterType, bf:WallThicknessMM,
        bf:InfillSuggestion, bf:SupportSuggestion, bf:SourceImages.

        Args:
            root: XML root element.
            settings: Print settings values.

        Implements: FR-019, SEC-002.
        """
        # SEC-002: ElementTree escapes text automatically.
        ns_fields = {
            f"{{{TESSERA_NS}}}PrinterType": settings.printer_type,
            f"{{{TESSERA_NS}}}WallThicknessMM": str(settings.wall_thickness_mm),
            f"{{{TESSERA_NS}}}InfillSuggestion": settings.infill_suggestion,
            f"{{{TESSERA_NS}}}SupportSuggestion": settings.support_suggestion,
            f"{{{TESSERA_NS}}}SourceImages": str(settings.source_images),
        }

        for tag, value in ns_fields.items():
            elem = ET.SubElement(root, f"{{{_3MF_NS}}}metadata")
            elem.set("name", tag)
            elem.text = value

    def _inject_validation_report(
        self,
        root: ET.Element,
        report: ValidationReport,
    ) -> None:
        """Inject Tessera validation report as custom-namespaced metadata.

        Adds: bf:ManifoldStatus, bf:WallThicknessStatus,
        bf:OverhangStatus, bf:VolumeMMCubed.

        Args:
            root: XML root element.
            report: Validation report values.

        Implements: FR-020, SEC-002.
        """
        # SEC-002: ElementTree escapes text automatically.
        ns_fields = {
            f"{{{TESSERA_NS}}}ManifoldStatus": report.manifold_status,
            f"{{{TESSERA_NS}}}WallThicknessStatus": report.wall_thickness_status,
            f"{{{TESSERA_NS}}}OverhangStatus": report.overhang_status,
            f"{{{TESSERA_NS}}}VolumeMMCubed": str(report.volume_mm_cubed),
        }

        for tag, value in ns_fields.items():
            elem = ET.SubElement(root, f"{{{_3MF_NS}}}metadata")
            elem.set("name", tag)
            elem.text = value
