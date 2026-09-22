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

"""Tests for model weight licence gating.

Model weights are third-party and are not covered by Tessera's GPL
licence. Weights whose terms restrict or prohibit commercial use — or
that declare no terms — must not be downloaded without an explicit
opt-in.

Maps to SPEC-TS-0002 v1.2 test scenarios TS-018 and TS-019
(FR-020 – FR-024, SEC-007, AC-008).

Reference: MODEL-LICENSES.md, tessera/models/licensing.py

Tests can be run standalone with:
    pytest tests/test_model_licensing.py -v
"""

import json
from pathlib import Path

import pytest

MANIFEST_PATH = (
    Path(__file__).resolve().parents[1] / "tessera" / "models" / "manifest.json"
)


@pytest.fixture
def licensing(mock_bpy):
    """Import the licensing module with a clean opt-in flag."""
    from tessera.models import licensing as mod

    mod.set_restricted_models_allowed(False)
    yield mod
    mod.set_restricted_models_allowed(False)


@pytest.fixture
def shipped_manifest():
    """The manifest that ships with the add-on."""
    return json.loads(MANIFEST_PATH.read_text())


def _entry(licensing, **overrides):
    """Build a minimal ModelEntry-like object for gate tests."""
    from tessera.models.registry import ModelEntry

    defaults = dict(
        model_id="test-model",
        repo_id="org/test-model",
        revision="abc123",
        description="Test model",
        files=["model.safetensors"],
        sha256={"model.safetensors": "aaa"},
        size_bytes=1,
        min_vram_gb=1.0,
    )
    defaults.update(overrides)
    return ModelEntry(**defaults)


class TestShippedManifest:
    """TS-018 → FR-020: the shipped manifest declares licences for every model."""

    def test_every_model_declares_license_metadata(self, shipped_manifest):
        """Each entry carries license, license_url and commercial_use."""
        for model in shipped_manifest["models"]:
            for key in ("license", "license_url", "commercial_use"):
                assert key in model and model[key], (
                    f"Model '{model['model_id']}' is missing '{key}'. "
                    f"Every weight must declare its terms — see MODEL-LICENSES.md."
                )

    def test_commercial_use_values_are_recognised(self, shipped_manifest, licensing):
        """Classifications are limited to the known vocabulary."""
        allowed = {
            licensing.COMMERCIAL_USE_ALLOWED,
            licensing.COMMERCIAL_USE_RESTRICTED,
            licensing.COMMERCIAL_USE_PROHIBITED,
            licensing.COMMERCIAL_USE_UNKNOWN,
        }
        for model in shipped_manifest["models"]:
            assert model["commercial_use"] in allowed, (
                f"Model '{model['model_id']}' declares unknown classification "
                f"'{model['commercial_use']}'"
            )

    def test_noncommercial_depth_model_is_marked_prohibited(self, shipped_manifest):
        """Depth Anything V2 Large is CC-BY-NC-4.0 and must be flagged."""
        large = next(
            m
            for m in shipped_manifest["models"]
            if m["model_id"] == "depth-anything-v2-large"
        )
        assert large["commercial_use"] == "prohibited"
        assert "NC" in large["license"].upper()

    def test_default_depth_model_is_commercial_friendly(self, shipped_manifest):
        """The default depth checkpoint must be usable commercially."""
        from tessera.vision.depth.depth_anything_adapter import _MODEL_ID

        default = next(
            m for m in shipped_manifest["models"] if m["model_id"] == _MODEL_ID
        )
        assert default["commercial_use"] == "allowed", (
            f"The default depth model '{_MODEL_ID}' must be commercial-friendly; "
            f"it declares '{default['commercial_use']}'."
        )
        assert default["license"] == "Apache-2.0"

    def test_revisions_are_pinned_not_floating(self, shipped_manifest):
        """Pinned revisions stop upstream changing weights or terms silently."""
        floating = [
            m["model_id"] for m in shipped_manifest["models"] if m["revision"] == "main"
        ]
        assert not floating, f"Models pinned to a moving ref: {floating}"


class TestLicenseGate:
    """TS-019 → FR-021, FR-022, SEC-007: the gate fails closed."""

    def test_allowed_model_is_not_gated(self, licensing):
        entry = _entry(licensing, commercial_use="allowed", license="Apache-2.0")
        assert licensing.is_gated(entry) is False
        licensing.check_download_allowed(entry)  # must not raise

    @pytest.mark.parametrize("classification", ["prohibited", "restricted", "unknown"])
    def test_gated_models_raise_without_optin(self, licensing, classification):
        from tessera.models import ModelLicenseError

        entry = _entry(licensing, commercial_use=classification)
        assert licensing.is_gated(entry) is True
        with pytest.raises(ModelLicenseError):
            licensing.check_download_allowed(entry)

    def test_missing_classification_fails_closed(self, licensing):
        """An entry with no declared terms is treated as gated."""
        from tessera.models import ModelLicenseError

        entry = _entry(licensing)  # ModelEntry defaults to "unknown"
        assert licensing.is_gated(entry) is True
        with pytest.raises(ModelLicenseError):
            licensing.check_download_allowed(entry)

    def test_optin_permits_gated_download(self, licensing):
        entry = _entry(licensing, commercial_use="prohibited", license="CC-BY-NC-4.0")
        licensing.set_restricted_models_allowed(True)
        licensing.check_download_allowed(entry)  # must not raise

    def test_error_message_is_actionable(self, licensing):
        from tessera.models import ModelLicenseError

        entry = _entry(
            licensing,
            model_id="depth-anything-v2-large",
            commercial_use="prohibited",
            license="CC-BY-NC-4.0",
        )
        with pytest.raises(ModelLicenseError) as exc:
            licensing.check_download_allowed(entry)
        message = str(exc.value)
        assert "depth-anything-v2-large" in message
        assert "CC-BY-NC-4.0" in message
        assert "MODEL-LICENSES.md" in message

    def test_license_summary_flags_noncommercial(self, licensing):
        entry = _entry(licensing, commercial_use="prohibited", license="CC-BY-NC-4.0")
        assert "non-commercial" in licensing.license_summary(entry)

    def test_license_summary_plain_for_allowed(self, licensing):
        entry = _entry(licensing, commercial_use="allowed", license="Apache-2.0")
        assert licensing.license_summary(entry) == "Apache-2.0"


class TestRegistryParsing:
    """Licence fields survive the manifest → ModelEntry round trip."""

    def test_fields_are_parsed(self, mock_bpy, tmp_path):
        from tessera.models.registry import ModelRegistry

        manifest = {
            "version": "1.1",
            "models": [
                {
                    "model_id": "licensed-model",
                    "repo_id": "org/licensed-model",
                    "revision": "abc123",
                    "description": "Licensed model",
                    "license": "Apache-2.0",
                    "license_url": "https://example.invalid/licence",
                    "commercial_use": "allowed",
                    "files": ["model.safetensors"],
                    "sha256": {"model.safetensors": "aaa"},
                    "size_bytes": 1,
                    "min_vram_gb": 1.0,
                    "variants": [],
                }
            ],
        }
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(manifest))

        entry = ModelRegistry(manifest_path=path).get_model("licensed-model")
        assert entry.license == "Apache-2.0"
        assert entry.commercial_use == "allowed"
        assert entry.license_url == "https://example.invalid/licence"

    def test_legacy_entry_without_license_defaults_to_unknown(self, mock_bpy, tmp_path):
        """Older manifests still load, but their entries are gated."""
        from tessera.models import licensing as lic
        from tessera.models.registry import ModelRegistry

        manifest = {
            "version": "1.0",
            "models": [
                {
                    "model_id": "legacy-model",
                    "repo_id": "org/legacy-model",
                    "revision": "abc123",
                    "description": "Legacy model",
                    "files": ["model.safetensors"],
                    "sha256": {"model.safetensors": "aaa"},
                    "size_bytes": 1,
                    "min_vram_gb": 1.0,
                    "variants": [],
                }
            ],
        }
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(manifest))

        entry = ModelRegistry(manifest_path=path).get_model("legacy-model")
        assert entry.commercial_use == "unknown"
        assert lic.is_gated(entry) is True


class TestDepthAdapterDefault:
    """The depth adapter must default to the Apache-2.0 checkpoint."""

    def test_default_model_id_is_small(self, mock_bpy):
        from tessera.vision.depth.depth_anything_adapter import _MODEL_ID

        assert _MODEL_ID == "depth-anything-v2-small"

    def test_default_adapter_reports_small_checkpoint(self, mock_bpy):
        from tessera.vision.depth.depth_anything_adapter import DepthAnythingAdapter

        adapter = DepthAnythingAdapter()
        assert adapter.model_name == "Depth Anything V2 Small"
        assert adapter._config["checkpoint"] == "depth_anything_v2_vits.pth"
        assert adapter._config["encoder"] == "vits"

    def test_large_checkpoint_still_selectable(self, mock_bpy):
        """Non-commercial users may still opt into Large explicitly."""
        from tessera.vision.depth.depth_anything_adapter import DepthAnythingAdapter

        adapter = DepthAnythingAdapter(model_id="depth-anything-v2-large")
        assert adapter.model_name == "Depth Anything V2 Large"
        assert adapter._config["encoder"] == "vitl"

    def test_unknown_model_id_rejected(self, mock_bpy):
        from tessera.vision.depth.depth_anything_adapter import DepthAnythingAdapter

        with pytest.raises(ValueError, match="Unknown depth model"):
            DepthAnythingAdapter(model_id="depth-anything-v2-giant")
