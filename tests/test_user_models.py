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

"""Tests for the user-extensible model manifest.

Maps to SPEC-TS-0002 v1.3 test scenarios TS-024 – TS-027
(FR-026 – FR-033, SEC-008, AC-010).

A user can add a model from Hugging Face; it must be licence-classified
and checksum-verified before it is registered, and must never be able to
shadow or remove a bundled model.

Reference: MODEL-LICENSES.md, docs/docs/user-guide/custom-models.md
"""

import hashlib
import io
import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest

REPO = "depth-anything/Depth-Anything-V2-Base"
REVISION = "a" * 40
CONFIG_BODY = b'{"model_type": "depth_anything"}'
CONFIG_SHA = hashlib.sha256(CONFIG_BODY).hexdigest()
WEIGHT_SHA = "b" * 64


def _model_payload(license_value="apache-2.0", files=None):
    """A minimal /api/models/{repo} response."""
    files = files or ["depth_anything_v2_vitb.pth", "README.md"]
    return {
        "sha": REVISION,
        "cardData": {"license": license_value} if license_value else {},
        "siblings": [{"rfilename": f, "size": 400_000_000} for f in files],
    }


def _paths_info(paths):
    """A minimal paths-info response: LFS digests for weights, none for JSON."""
    out = []
    for path in paths:
        if path.endswith(".json"):
            out.append({"path": path, "size": len(CONFIG_BODY)})
        else:
            out.append({"path": path, "size": 400_000_000, "lfs": {"oid": WEIGHT_SHA}})
    return out


@contextmanager
def _mock_hub(model_payload=None, paths_payload=None, file_body=CONFIG_BODY):
    """Patch urlopen so no test touches the network."""

    def fake_urlopen(request, timeout=None):
        url = request if isinstance(request, str) else request.full_url
        if "/paths-info/" in url:
            paths = json.loads(request.data.decode())["paths"]
            body = json.dumps(paths_payload or _paths_info(paths)).encode()
        elif "/api/models/" in url:
            body = json.dumps(model_payload or _model_payload()).encode()
        else:
            body = file_body

        stream = io.BytesIO(body)
        stream.__enter__ = lambda: stream
        stream.__exit__ = lambda *a: None
        return stream

    with patch("tessera.models.hf_metadata.urllib.request.urlopen", fake_urlopen):
        yield


@pytest.fixture
def registry_with_user_file(mock_bpy, tmp_path):
    """A registry backed by the shipped manifest plus a temp user list."""
    from tessera.models.registry import ModelRegistry

    user_path = tmp_path / "user_models.json"
    return ModelRegistry(user_manifest_path=user_path), user_path


class TestLicenseClassification:
    """TS-024 → FR-030: licence identifiers map to the right classification."""

    @pytest.mark.parametrize(
        "license_id,expected",
        [
            ("apache-2.0", "allowed"),
            ("mit", "allowed"),
            ("MIT", "allowed"),
            ("bsd-3-clause", "allowed"),
            ("cc-by-4.0", "allowed"),
            ("cc-by-nc-4.0", "prohibited"),
            ("cc-by-nc-sa-4.0", "prohibited"),
            ("creativeml-openrail-m", "restricted"),
            ("openrail", "restricted"),
            ("llama3.1", "restricted"),
            ("gemma", "restricted"),
            ("other", "unknown"),
            ("", "unknown"),
            (None, "unknown"),
            ("some-bespoke-licence", "unknown"),
        ],
    )
    def test_classification(self, mock_bpy, license_id, expected):
        from tessera.models.licensing import classify_license

        assert classify_license(license_id) == expected

    def test_unrecognised_fails_closed(self, mock_bpy):
        """An identifier nobody has vetted is gated, not allowed."""
        from tessera.models import licensing

        entry_like = type(
            "E",
            (),
            {"commercial_use": licensing.classify_license("mystery-licence-9000")},
        )
        assert licensing.is_gated(entry_like) is True


class TestHuggingFaceLookup:
    """TS-025 → FR-027, FR-028, SEC-008: resolving a repository into an entry."""

    def test_happy_path_pins_revision_and_licence(self, mock_bpy):
        from tessera.models.hf_metadata import fetch_model_metadata

        with _mock_hub():
            meta = fetch_model_metadata(REPO, "depth-anything-v2")

        assert meta.repo_id == REPO
        assert meta.revision == REVISION
        assert meta.license_id == "apache-2.0"
        assert meta.commercial_use == "allowed"
        # README.md is not a weight file and must be filtered out.
        assert meta.files == ["depth_anything_v2_vitb.pth"]

    def test_malformed_repo_id_rejected(self, mock_bpy):
        from tessera.models.hf_metadata import MetadataError, fetch_model_metadata

        with pytest.raises(MetadataError, match="repository id"):
            fetch_model_metadata("not-a-repo", "depth-anything-v2")

    def test_unsupported_family_rejected(self, mock_bpy):
        from tessera.models.hf_metadata import MetadataError, fetch_model_metadata

        with pytest.raises(MetadataError, match="Tessera can load"):
            fetch_model_metadata(REPO, "stable-diffusion")

    def test_repository_without_usable_files_rejected(self, mock_bpy):
        from tessera.models.hf_metadata import MetadataError, fetch_model_metadata

        with _mock_hub(model_payload=_model_payload(files=["README.md"])):
            with pytest.raises(MetadataError, match="no files Tessera can use"):
                fetch_model_metadata(REPO, "depth-anything-v2")

    def test_undeclared_licence_is_unknown(self, mock_bpy):
        from tessera.models.hf_metadata import fetch_model_metadata

        with _mock_hub(model_payload=_model_payload(license_value=None)):
            meta = fetch_model_metadata(REPO, "depth-anything-v2")

        assert meta.license_id is None
        assert meta.commercial_use == "unknown"

    def test_non_huggingface_url_refused(self, mock_bpy):
        from tessera.models.hf_metadata import MetadataError, _get_json

        with pytest.raises(MetadataError, match="non-Hugging Face"):
            _get_json("https://example.invalid/api/models/foo/bar")


class TestEntryConstruction:
    """TS-026 → FR-029: every added model carries verified digests."""

    def test_entry_has_digests_for_every_file(self, mock_bpy):
        """Both digest paths: the Hub's LFS oid, and hashing a small file."""
        from tessera.models.hf_metadata import build_user_entry, fetch_model_metadata

        with _mock_hub(
            model_payload=_model_payload(
                files=["model.safetensors", "config.json", "README.md"]
            )
        ):
            meta = fetch_model_metadata("facebook/sam2-hiera-small", "sam2")
            entry = build_user_entry(meta, "sam2")

        assert set(entry["sha256"]) == set(entry["files"])
        assert "README.md" not in entry["files"]
        # LFS digest passed through; small JSON downloaded and hashed.
        assert entry["sha256"]["model.safetensors"] == WEIGHT_SHA
        assert entry["sha256"]["config.json"] == CONFIG_SHA
        assert entry["revision"] == REVISION
        assert entry["source"] == "user"
        assert entry["family"] == "sam2"

    def test_depth_entry_records_its_variant(self, mock_bpy):
        from tessera.models.hf_metadata import build_user_entry, fetch_model_metadata

        with _mock_hub():
            meta = fetch_model_metadata(REPO, "depth-anything-v2")
            entry = build_user_entry(meta, "depth-anything-v2", variant_id="vitb")

        assert entry["family"] == "depth-anything-v2"
        assert entry["variant"] == "vitb"
        assert entry["sha256"]["depth_anything_v2_vitb.pth"] == WEIGHT_SHA

    def test_unverifiable_large_file_refused(self, mock_bpy):
        """A big file with no published checksum is not added."""
        from tessera.models.hf_metadata import (
            MetadataError,
            build_user_entry,
            fetch_model_metadata,
        )

        with _mock_hub(
            paths_payload=[{"path": "depth_anything_v2_vitb.pth", "size": 400_000_000}]
        ):
            meta = fetch_model_metadata(REPO, "depth-anything-v2")
            with pytest.raises(MetadataError, match="no published checksum"):
                build_user_entry(meta, "depth-anything-v2")

    def test_oversized_model_refused(self, mock_bpy):
        from tessera.models.hf_metadata import (
            MetadataError,
            build_user_entry,
            fetch_model_metadata,
        )

        with _mock_hub():
            meta = fetch_model_metadata(REPO, "depth-anything-v2")
            with pytest.raises(MetadataError, match="above Tessera's"):
                build_user_entry(meta, "depth-anything-v2", max_total_bytes=1000)

    def test_model_id_derived_from_repo(self, mock_bpy):
        from tessera.models.hf_metadata import suggest_model_id

        assert suggest_model_id(REPO) == "depth-anything-v2-base"
        assert suggest_model_id("owner/Weird__Name!!") == "weird-name"


class TestUserRegistry:
    """TS-027 → FR-026, FR-032, FR-033: persistence and isolation."""

    def _entry(self, **overrides):
        data = {
            "model_id": "my-depth-model",
            "repo_id": REPO,
            "revision": REVISION,
            "description": "Depth Anything V2 (added from Hugging Face)",
            "license": "apache-2.0",
            "license_url": f"https://huggingface.co/{REPO}",
            "commercial_use": "allowed",
            "files": ["depth_anything_v2_vitb.pth"],
            "sha256": {"depth_anything_v2_vitb.pth": WEIGHT_SHA},
            "size_bytes": 400_000_000,
            "min_vram_gb": 2.5,
            "family": "depth-anything-v2",
            "variant": "vitb",
            "variants": [],
        }
        data.update(overrides)
        return data

    def test_added_model_persists_across_reload(self, registry_with_user_file):
        from tessera.models.registry import ModelRegistry

        registry, user_path = registry_with_user_file
        registry.add_user_model(self._entry())

        assert user_path.exists()
        reloaded = ModelRegistry(user_manifest_path=user_path)
        entry = reloaded.get_model("my-depth-model")
        assert entry.source == "user"
        assert entry.variant == "vitb"
        assert reloaded.is_user_model("my-depth-model") is True

    def test_user_model_cannot_shadow_bundled(self, registry_with_user_file):
        from tessera.models import ManifestLoadError

        registry, _ = registry_with_user_file
        with pytest.raises(ManifestLoadError, match="already registered"):
            registry.add_user_model(self._entry(model_id="depth-anything-v2-small"))

    def test_bundled_model_cannot_be_removed(self, registry_with_user_file):
        from tessera.models import ManifestLoadError

        registry, _ = registry_with_user_file
        with pytest.raises(ManifestLoadError, match="ships with Tessera"):
            registry.remove_user_model("depth-anything-v2-small")

    def test_remove_user_model(self, registry_with_user_file):
        from tessera.models.registry import ModelRegistry

        registry, user_path = registry_with_user_file
        registry.add_user_model(self._entry())

        assert registry.remove_user_model("my-depth-model") is True
        assert registry.remove_user_model("my-depth-model") is False
        assert "my-depth-model" not in ModelRegistry(user_manifest_path=user_path)

    def test_malformed_user_file_does_not_break_registry(self, mock_bpy, tmp_path):
        """A broken user list must not take bundled models down with it."""
        from tessera.models.registry import ModelRegistry

        user_path = tmp_path / "user_models.json"
        user_path.write_text("{ not json")

        registry = ModelRegistry(user_manifest_path=user_path)
        assert registry.get_model("depth-anything-v2-small") is not None
        assert registry.list_user_models() == []

    def test_added_model_is_gated_by_licence(self, registry_with_user_file):
        from tessera.models import ModelLicenseError, licensing

        registry, _ = registry_with_user_file
        licensing.set_restricted_models_allowed(False)
        registry.add_user_model(
            self._entry(
                model_id="nc-depth-model",
                license="cc-by-nc-4.0",
                commercial_use="prohibited",
            )
        )

        entry = registry.get_model("nc-depth-model")
        assert licensing.is_gated(entry) is True
        with pytest.raises(ModelLicenseError):
            licensing.check_download_allowed(entry)


class TestAdapterUsesUserVariant:
    """A user-added depth checkpoint is loadable by the depth adapter."""

    def test_explicit_variant_resolves_architecture(self, mock_bpy):
        from tessera.vision.depth.depth_anything_adapter import DepthAnythingAdapter

        adapter = DepthAnythingAdapter(model_id="my-depth-model", variant_id="vitb")
        assert adapter.model_name == "Depth Anything V2 Base"
        assert adapter._config["encoder"] == "vitb"
        assert adapter._config["checkpoint"] == "depth_anything_v2_vitb.pth"

    def test_unknown_variant_rejected(self, mock_bpy):
        from tessera.vision.depth.depth_anything_adapter import DepthAnythingAdapter

        with pytest.raises(ValueError, match="Unknown Depth Anything V2 encoder"):
            DepthAnythingAdapter(model_id="x", variant_id="vit-nope")

    def test_unresolvable_model_id_rejected(self, mock_bpy):
        from tessera.vision.depth.depth_anything_adapter import DepthAnythingAdapter

        with pytest.raises(ValueError, match="Unknown depth model"):
            DepthAnythingAdapter(model_id="never-heard-of-it")


class TestFamilies:
    """Families declare what an adapter can actually load."""

    def test_every_family_declares_adapter_readiness(self, mock_bpy):
        from tessera.models.families import list_families

        for family in list_families():
            assert family.stage and family.adapter and family.allowed_suffixes
            if not family.adapter_ready:
                assert family.pending_task, (
                    f"Family '{family.family_id}' is not adapter-ready but "
                    f"names no task that would make it ready."
                )

    def test_family_choices_are_enum_shaped(self, mock_bpy):
        from tessera.models.families import family_choices

        for item in family_choices():
            assert len(item) == 3
            assert all(isinstance(part, str) for part in item)
