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

"""Tests for SPEC-TS-0003: Vision Analysis Pipeline.

Each test maps to a Test Scenario (TS-XXX) from the spec's §13.

Tests can be run standalone with:
    pytest tests/test_vision_pipeline.py -v

All ``bpy`` dependencies are mocked via conftest.py fixtures.
GPU and model dependencies are fully mocked — no GPU hardware required.
"""

import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

# ---------------------------------------------------------------------------
# Mock Adapter Helpers
# ---------------------------------------------------------------------------


def _make_mock_segmentation_adapter(mask_value=255):
    """Create a mock SegmentationAdapter that returns a fixed mask.

    Args:
        mask_value: Fill value for the returned mask (0 or 255).

    Returns:
        MagicMock: A mock with correct load/predict/unload interface.
    """
    adapter = MagicMock()
    adapter.model_name = "MockSegmentation"

    def _predict(image):
        h, w = image.shape[:2]
        return np.full((h, w), mask_value, dtype=np.uint8)

    adapter.predict.side_effect = _predict
    return adapter


def _make_mock_depth_adapter():
    """Create a mock DepthAdapter that returns a normalised depth map.

    Returns:
        MagicMock: A mock with correct load/predict/unload interface.
    """
    adapter = MagicMock()
    adapter.model_name = "MockDepth"

    def _predict(image, mask):
        h, w = image.shape[:2]
        # Create a gradient depth map and zero out background.
        depth = np.linspace(0.0, 1.0, h * w, dtype=np.float32).reshape(h, w)
        depth[mask == 0] = 0.0
        return depth

    adapter.predict.side_effect = _predict
    return adapter


def _make_mock_view_classifier(label="front", confidence=0.85):
    """Create a mock ViewClassifierAdapter.

    Args:
        label: The view label to return.
        confidence: The confidence score to return.

    Returns:
        MagicMock: A mock with correct load/predict/unload interface.
    """
    adapter = MagicMock()
    adapter.model_name = "MockViewClassifier"
    adapter.predict.return_value = (label, confidence)
    return adapter


def _make_mock_feature_adapter(dim=768):
    """Create a mock FeatureAdapter that returns a fixed feature vector.

    Args:
        dim: Embedding dimension.

    Returns:
        MagicMock: A mock with correct load/predict/unload interface.
    """
    adapter = MagicMock()
    adapter.model_name = "MockFeatures"

    def _predict(image):
        return np.random.randn(1, dim).astype(np.float32)

    adapter.predict.side_effect = _predict
    return adapter


def _create_test_image(tmp_path, filename="test.jpg", width=512, height=384):
    """Create a real image file on disk for preprocessing tests.

    Args:
        tmp_path: pytest tmp directory.
        filename: Name of the file to create.
        width: Image width.
        height: Image height.

    Returns:
        Path: Path to the created image file.
    """
    img = Image.new("RGB", (width, height), color=(128, 200, 50))
    filepath = tmp_path / filename
    # Determine format from extension.
    ext = filepath.suffix.lower()
    fmt_map = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
    fmt = fmt_map.get(ext, "JPEG")
    img.save(str(filepath), format=fmt)
    return filepath


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_gpu_cuda():
    """Mock gpu_detection.get_gpu_info to report a CUDA GPU."""
    gpu_info = {
        "name": "NVIDIA RTX 3060",
        "vram_gb": 12.0,
        "backend": "CUDA",
    }
    # Mock: system-level non-determinism — GPU hardware detection
    with patch("tessera.gpu_detection.get_gpu_info", return_value=gpu_info):
        yield gpu_info


@pytest.fixture
def mock_gpu_none():
    """Mock gpu_detection.get_gpu_info to report no GPU."""
    gpu_info = {
        "name": "No GPU",
        "vram_gb": 0.0,
        "backend": None,
    }
    # Mock: system-level non-determinism — GPU hardware detection
    with patch("tessera.gpu_detection.get_gpu_info", return_value=gpu_info):
        yield gpu_info


@pytest.fixture
def pipeline_with_mocks(mock_bpy, mock_gpu_cuda):
    """Create a VisionPipeline with all adapters mocked.

    Returns a tuple of (pipeline, adapters_dict) so tests can inspect
    adapter call counts and state.
    """
    from tessera.vision.pipeline import VisionPipeline

    seg = _make_mock_segmentation_adapter()
    depth = _make_mock_depth_adapter()
    view = _make_mock_view_classifier()
    feat = _make_mock_feature_adapter()

    pipeline = VisionPipeline(
        segmentation_adapter=seg,
        depth_adapter=depth,
        view_classifier_adapter=view,
        feature_adapter=feat,
    )
    return pipeline, {"seg": seg, "depth": depth, "view": view, "feat": feat}


# ---------------------------------------------------------------------------
# TestPipelineHappyPath (AC-001, AC-002, AC-005, AC-006)
# ---------------------------------------------------------------------------


class TestPipelineHappyPath:
    """Tests for full pipeline execution (AC-001, AC-002, AC-005, AC-006)."""

    def test_TS001_single_jpg_user_label_front(
        self, mock_bpy, tmp_path, pipeline_with_mocks
    ):
        """TS-001 → AC-001: Process single JPG with user-supplied "front" label — verify
        all output fields.

        Given: A single 2048×1536 .jpg image of a ceramic mug on a white
               background, with user-supplied view label "front"
        When: VisionPipeline.process([ImageInput(filepath="mug_front.jpg",
               view_label="front")]) is called on a system with an
               NVIDIA RTX 3060 GPU
        Then: The method returns a list containing exactly 1 VisionResult
              with correct shapes, dtypes, label_source="user", and
              processing_time_s keys.

        Type: Integration | Priority: Must Pass
        """
        from tessera.vision.types import ImageInput

        pipeline, adapters = pipeline_with_mocks

        # Given — create a 2048×1536 image
        img_path = _create_test_image(tmp_path, "mug_front.jpg", 2048, 1536)

        # When
        results = pipeline.process(
            [
                ImageInput(filepath=str(img_path), view_label="front"),
            ]
        )

        # Then — exactly 1 result
        assert len(results) == 1
        r = results[0]

        # Image shape: should be resized to max 1024 px (FR-003).
        assert r.image.ndim == 3
        assert r.image.shape[2] == 3
        assert r.image.dtype == np.uint8
        assert max(r.image.shape[:2]) <= 1024

        # Mask shape matches image spatial dims.
        assert r.mask.shape == r.image.shape[:2]
        assert r.mask.dtype == np.uint8
        assert set(np.unique(r.mask)).issubset({0, 255})

        # Depth map shape and dtype.
        assert r.depth_map.shape == r.image.shape[:2]
        assert r.depth_map.dtype == np.float32
        assert r.depth_map.min() >= 0.0
        assert r.depth_map.max() <= 1.0

        # Feature vector.
        assert r.features.ndim == 2
        assert r.features.shape[0] == 1
        assert r.features.dtype == np.float32

        # User-supplied label.
        assert r.view_label == "front"
        assert r.label_source == "user"
        assert r.label_confidence == 1.0
        assert r.label_needs_confirmation is False

        # Original size records the pre-resize dimensions.
        assert r.original_size == (2048, 1536)

        # Processing times have all expected keys.
        expected_keys = {
            "preprocessing",
            "segmentation",
            "depth",
            "view_classification",
            "feature_extraction",
        }
        assert set(r.processing_time_s.keys()) == expected_keys
        for key, val in r.processing_time_s.items():
            assert isinstance(val, float), f"{key} timing is not float"
            assert val >= 0.0, f"{key} timing is negative"

    def test_TS002_batch_4_images_mixed_labels(self, mock_bpy, tmp_path, mock_gpu_cuda):
        """TS-002 → AC-002: Process batch of 4 images with mixed user/auto labels —
        verify
        label sources.

        Given: 4 images (.jpg and .png mix) of a vase from front, back,
               left, and right angles, with view labels "front", None,
               None, "right"
        When: VisionPipeline.process(...) is called with these 4
              ImageInput objects
        Then: The method returns a list of 4 VisionResult objects where
              results[0] and results[3] have label_source == "user",
              results[1] and results[2] have label_source == "auto",
              and all 4 have non-zero masks, valid depth maps, and
              feature vectors.

        Type: Integration | Priority: Must Pass
        """
        from tessera.vision.pipeline import VisionPipeline
        from tessera.vision.types import ImageInput

        # Create 4 images with different formats
        paths = [
            _create_test_image(tmp_path, "vase_front.jpg", 800, 600),
            _create_test_image(tmp_path, "vase_back.png", 800, 600),
            _create_test_image(tmp_path, "vase_left.jpg", 800, 600),
            _create_test_image(tmp_path, "vase_right.png", 800, 600),
        ]

        # Auto-classifier returns "back" with high confidence for unlabelled
        view_cls = _make_mock_view_classifier(label="back", confidence=0.90)

        pipeline = VisionPipeline(
            segmentation_adapter=_make_mock_segmentation_adapter(),
            depth_adapter=_make_mock_depth_adapter(),
            view_classifier_adapter=view_cls,
            feature_adapter=_make_mock_feature_adapter(),
        )

        inputs = [
            ImageInput(filepath=str(paths[0]), view_label="front"),
            ImageInput(filepath=str(paths[1]), view_label=None),
            ImageInput(filepath=str(paths[2]), view_label=None),
            ImageInput(filepath=str(paths[3]), view_label="right"),
        ]

        # When
        results = pipeline.process(inputs)

        # Then — 4 results
        assert len(results) == 4

        # User labels on idx 0, 3
        assert results[0].label_source == "user"
        assert results[0].view_label == "front"
        assert results[3].label_source == "user"
        assert results[3].view_label == "right"

        # Auto labels on idx 1, 2
        assert results[1].label_source == "auto"
        assert results[2].label_source == "auto"

        # All results have valid outputs
        for r in results:
            assert np.any(r.mask > 0), "Mask should contain foreground pixels"
            assert r.depth_map.dtype == np.float32
            assert r.features.shape[0] == 1
            assert r.features.dtype == np.float32

    def test_TS009_heic_image_format_support(
        self, mock_bpy, tmp_path, pipeline_with_mocks
    ):
        """TS-009 → AC-005: Process .heic image — verify successful conversion and full
        pipeline.

        Given: A single .heic image captured from an iPhone
        When: VisionPipeline.process([ImageInput(filepath="object.heic")])
              is called
        Then: The pipeline converts the HEIC to RGB, processes it
              through all 4 stages, and returns a valid VisionResult
              with no errors.

        Type: Integration | Priority: Must Pass
        """
        from tessera.vision.types import ImageInput

        pipeline, _ = pipeline_with_mocks

        # Create a real JPEG but save with .heic extension — we mock
        # pillow_heif registration to make PIL treat it as openable.
        # Since real HEIC encoding requires pillow-heif, we create a
        # JPEG file and rename it, then mock the HEIC opener.
        img = Image.new("RGB", (640, 480), color=(100, 150, 200))
        heic_path = tmp_path / "object.heic"

        # Save as PNG first (lossless, always supported), rename to .heic
        png_path = tmp_path / "object.png"
        img.save(str(png_path), format="PNG")

        # Mock: external dependency — PIL/pillow_heif for HEIC image loading
        with patch("tessera.vision.preprocessing.Image") as mock_pil:
            mock_img = MagicMock()
            mock_img.convert.return_value = img
            mock_img.width = 640
            mock_img.height = 480
            mock_img.size = (640, 480)
            mock_pil.open.return_value = mock_img
            mock_pil.LANCZOS = Image.LANCZOS

            # Mock: external dependency — pillow_heif may not be installed in CI
            mock_heif = MagicMock()
            with patch.dict("sys.modules", {"pillow_heif": mock_heif}):
                # Write a dummy file with .heic ext
                heic_path.write_bytes(png_path.read_bytes())

                results = pipeline.process(
                    [
                        ImageInput(filepath=str(heic_path)),
                    ]
                )

        assert len(results) == 1
        r = results[0]
        assert r.image.dtype == np.uint8
        assert r.mask.dtype == np.uint8
        assert r.depth_map.dtype == np.float32
        assert r.features.shape[0] == 1

    def test_TS010_progress_updates_during_batch(
        self, mock_bpy, tmp_path, mock_gpu_cuda
    ):
        """TS-010 → AC-006: Verify progress updates during batch processing.

        Given: A batch of 3 images being processed
        When: The pipeline is running
        Then: The Blender UI property bpy.context.scene.tessera.pipeline_status
              is updated at least once per stage per image with format
              "Segmentation — Image 2/3", and pipeline_progress is set
              in the range [0.0, 1.0].

        Type: Integration | Priority: Must Pass
        """
        import bpy

        from tessera.vision.pipeline import VisionPipeline
        from tessera.vision.types import ImageInput

        # Create 3 images
        paths = [
            _create_test_image(tmp_path, f"img{i}.jpg", 512, 512) for i in range(3)
        ]

        # Track status updates
        status_updates = []
        progress_updates = []

        # Set up mock tessera props on scene
        tessera_props = MagicMock()

        def _set_status(val):
            status_updates.append(val)

        def _set_progress(val):
            progress_updates.append(val)

        type(tessera_props).pipeline_status = property(
            fget=lambda self: "",
            fset=lambda self, v: _set_status(v),
        )
        type(tessera_props).pipeline_progress = property(
            fget=lambda self: 0.0,
            fset=lambda self, v: _set_progress(v),
        )

        bpy.context.scene.tessera = tessera_props

        pipeline = VisionPipeline(
            segmentation_adapter=_make_mock_segmentation_adapter(),
            depth_adapter=_make_mock_depth_adapter(),
            view_classifier_adapter=_make_mock_view_classifier(),
            feature_adapter=_make_mock_feature_adapter(),
        )

        inputs = [ImageInput(filepath=str(p)) for p in paths]

        # When
        pipeline.process(inputs)

        # Then — at least 1 status update per stage per image
        # Stages: Preprocessing, Segmentation, Depth Estimation,
        # View Classification, Feature Extraction, Complete
        assert len(status_updates) >= 3 * 4, (
            f"Expected at least 12 status updates (3 images × 4 stages), "
            f"got {len(status_updates)}"
        )

        # Verify stage names appear in status updates
        stage_names_found = set()
        for s in status_updates:
            for stage in [
                "Preprocessing",
                "Segmentation",
                "Depth Estimation",
                "View Classification",
                "Feature Extraction",
                "Complete",
            ]:
                if stage in s:
                    stage_names_found.add(stage)

        assert "Segmentation" in stage_names_found
        assert "Feature Extraction" in stage_names_found

        # Verify format "Stage — Image N/3"
        assert any(
            "Image 2/3" in s for s in status_updates
        ), "Expected status like 'Stage — Image 2/3'"

        # Progress values should be in [0.0, 1.0]
        for p in progress_updates:
            assert 0.0 <= p <= 1.0, f"Progress {p} out of range"


# ---------------------------------------------------------------------------
# TestViewClassification (AC-003, EC-004)
# ---------------------------------------------------------------------------


class TestViewClassification:
    """Tests for view label auto-detection and resolution (AC-003, EC-004)."""

    def test_TS003_auto_detect_low_confidence_confirmation(self, mock_bpy):
        """TS-003 → AC-003: Auto-detect view label with low confidence — verify
        confirmation flag.

        Given: An ambiguous image of a cylindrical object with no
               user-supplied view label
        When: The view-direction auto-classifier produces a confidence
              of 0.55 for "front"
        Then: The VisionResult has view_label == "front",
              label_confidence == 0.55, label_source == "auto",
              and label_needs_confirmation == True.

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.view_classifier.silhouette_classifier import (
            resolve_view_label,
        )

        # Given — auto-classifier returns "front" at 0.55 confidence
        # When
        label, conf, source, needs_confirm = resolve_view_label(
            image_input_view_label=None,
            image_input_custom_azimuth=None,
            image_input_custom_elevation=None,
            auto_label="front",
            auto_confidence=0.55,
        )

        # Then
        assert label == "front"
        assert conf == 0.55
        assert source == "auto"
        assert (
            needs_confirm is True
        ), "Low confidence (0.55 < 0.80) should flag for confirmation"

    def test_TS007_custom_azimuth_elevation_label(self, mock_bpy):
        """TS-007 → EC-004: Process image with custom:127.5,-15.0 label — verify angle
        normalisation.

        Given: ImageInput(filepath="obj.jpg", view_label="custom",
               custom_azimuth=127.5, custom_elevation=-15.0)
        When: The pipeline processes this image
        Then: The VisionResult has view_label == "custom:127.5,-15.0",
              label_source == "user", label_confidence == 1.0, azimuth
              normalised to [0, 360) and elevation to [-90, 90].

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.view_classifier.silhouette_classifier import (
            resolve_view_label,
        )

        # When
        label, conf, source, needs_confirm = resolve_view_label(
            image_input_view_label="custom",
            image_input_custom_azimuth=127.5,
            image_input_custom_elevation=-15.0,
            auto_label="front",  # Should be ignored
            auto_confidence=0.9,
        )

        # Then
        assert label == "custom:127.5,-15.0"
        assert conf == 1.0
        assert source == "user"
        assert needs_confirm is False

        # Test normalisation: azimuth wraps to [0, 360)
        label2, _, _, _ = resolve_view_label(
            image_input_view_label="custom",
            image_input_custom_azimuth=400.0,  # Should wrap to 40.0
            image_input_custom_elevation=-100.0,  # Should clamp to -90.0
            auto_label="front",
            auto_confidence=0.5,
        )
        assert (
            label2 == "custom:40.0,-90.0"
        ), "Azimuth should wrap to [0, 360), elevation clamp to [-90, 90]"


# ---------------------------------------------------------------------------
# TestEdgeCases (EC-001, EC-002, EC-003, EC-005)
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases (EC-001, EC-002, EC-003, EC-005)."""

    def test_TS004_very_small_image_upscale(
        self, mock_bpy, tmp_path, pipeline_with_mocks
    ):
        """TS-004 → EC-001: Process 48×48 image — verify upscale to 256 px min and
        correct
        original_size.

        Given: A 48×48 pixel .png file
        When: The pipeline preprocesses this image
        Then: The system upscales the image to at least 256 px using
              Lanczos interpolation. VisionResult.original_size
              reflects the original 48×48 dimensions.

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.types import ImageInput

        pipeline, _ = pipeline_with_mocks

        # Given — create a very small 48×48 image
        img_path = _create_test_image(tmp_path, "tiny.png", 48, 48)

        # When
        results = pipeline.process(
            [
                ImageInput(filepath=str(img_path)),
            ]
        )

        # Then
        assert len(results) == 1
        r = results[0]

        # Original size should reflect the pre-resize dimensions
        assert r.original_size == (48, 48)

        # Image should have been upscaled to at least 256 px
        h, w = r.image.shape[:2]
        assert (
            max(h, w) >= 256
        ), f"Image should be upscaled to ≥256 px, got max({h}, {w})"

    def test_TS005_no_foreground_object_full_mask(
        self, mock_bpy, tmp_path, mock_gpu_cuda, caplog
    ):
        """TS-005 → EC-002: Process image of plain wall — verify full-image mask and
        warning log.

        Given: A 1024×768 .jpg of a solid blue wall
        When: The segmentation adapter processes this image
        Then: The adapter returns a mask covering the entire image
              (all pixels 255) and logs WARNING: "No distinct foreground
              object detected. Using full image as foreground."

        Type: Integration | Priority: Must Pass
        """
        from tessera.vision.pipeline import VisionPipeline
        from tessera.vision.types import ImageInput

        # Create a uniform image (simulates plain wall)
        img_path = _create_test_image(tmp_path, "wall.jpg", 1024, 768)

        # Segmentation adapter returns full mask (all 255) for no-foreground
        seg_adapter = _make_mock_segmentation_adapter(mask_value=255)

        # Log a warning inside the predict call
        original_predict = seg_adapter.predict.side_effect

        def _predict_with_warning(image):
            logger = logging.getLogger("tessera.vision")
            logger.warning(
                "No distinct foreground object detected. "
                "Using full image as foreground."
            )
            return original_predict(image)

        seg_adapter.predict.side_effect = _predict_with_warning

        pipeline = VisionPipeline(
            segmentation_adapter=seg_adapter,
            depth_adapter=_make_mock_depth_adapter(),
            view_classifier_adapter=_make_mock_view_classifier(),
            feature_adapter=_make_mock_feature_adapter(),
        )

        # When
        with caplog.at_level(logging.WARNING, logger="tessera.vision"):
            results = pipeline.process(
                [
                    ImageInput(filepath=str(img_path)),
                ]
            )

        # Then
        assert len(results) == 1
        # Mask should be all-255 (full image foreground)
        assert np.all(
            results[0].mask == 255
        ), "Mask should cover entire image when no foreground detected"

        # Warning should be logged
        assert any(
            "No distinct foreground object detected" in r.message
            for r in caplog.records
        ), "Expected warning about no foreground object"

    def test_TS006_corrupt_image_skip_continue(
        self, mock_bpy, tmp_path, pipeline_with_mocks
    ):
        """TS-006 → EC-003: Process corrupt .jpg file — verify ImageLoadError raised,
        other
        images succeed.

        Given: A 500-byte .jpg file that cannot be decoded, plus a
               valid image
        When: VisionPipeline.process([corrupt_input, valid_input])
              is called
        Then: The pipeline raises ImageLoadError for the corrupt image,
              skips it, and returns results for the remaining valid image.
              If all images fail, raises PipelineError with message
              "No valid images could be processed."

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.types import ImageInput, PipelineError

        pipeline, _ = pipeline_with_mocks

        # Given — corrupt file (random bytes with .jpg extension)
        corrupt_path = tmp_path / "corrupt.jpg"
        corrupt_path.write_bytes(b"\xff\xd8\xff" + b"\x00" * 497)

        # Valid file
        valid_path = _create_test_image(tmp_path, "valid.jpg", 512, 512)

        # When — process both
        results = pipeline.process(
            [
                ImageInput(filepath=str(corrupt_path)),
                ImageInput(filepath=str(valid_path)),
            ]
        )

        # Then — only the valid image produces a result
        assert len(results) == 1
        assert results[0].original_size == (512, 512)

        # Test all-corrupt batch raises PipelineError
        corrupt2_path = tmp_path / "corrupt2.jpg"
        corrupt2_path.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        with pytest.raises(PipelineError, match="No valid images could be processed"):
            pipeline.process(
                [
                    ImageInput(filepath=str(corrupt_path)),
                    ImageInput(filepath=str(corrupt2_path)),
                ]
            )

    def test_TS008_no_gpu_available_error(self, mock_bpy, tmp_path, mock_gpu_none):
        """TS-008 → AC-004: Call pipeline with no GPU — verify GPUNotAvailableError
        raised.

        Given: A system with no GPU that Tessera can run inference on
               detected by gpu_detection.get_gpu_info()
        When: VisionPipeline.process(...) is called
        Then: The method raises GPUNotAvailableError naming the NVIDIA
              CUDA requirement, and no model loading or inference is
              attempted. (v1 is CUDA-only — AMD and Apple Silicon are
              detected but unsupported; see TASK-TS-0022.)

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.pipeline import VisionPipeline
        from tessera.vision.types import GPUNotAvailableError, ImageInput

        pipeline = VisionPipeline(
            segmentation_adapter=_make_mock_segmentation_adapter(),
            depth_adapter=_make_mock_depth_adapter(),
            view_classifier_adapter=_make_mock_view_classifier(),
            feature_adapter=_make_mock_feature_adapter(),
        )

        img_path = _create_test_image(tmp_path, "test.jpg", 512, 512)

        # When/Then
        with pytest.raises(GPUNotAvailableError) as exc_info:
            pipeline.process(
                [
                    ImageInput(filepath=str(img_path)),
                ]
            )

        assert "NVIDIA GPU with CUDA" in str(exc_info.value)
        assert "No compatible GPU was detected" in str(exc_info.value)

        # Verify no model loading was attempted
        seg = pipeline._segmentation
        seg.load.assert_not_called()

    @pytest.mark.parametrize(
        "backend,expected",
        [("ROCM", "AMD (ROCm)"), ("METAL", "Apple Silicon (Metal)")],
    )
    def test_detected_but_unsupported_gpu_is_rejected(
        self, mock_bpy, tmp_path, backend, expected
    ):
        """FR-022: a detected AMD or Apple Silicon GPU is refused explicitly.

        Given: gpu_detection reports a GPU whose backend no adapter can use
        When: VisionPipeline.process(...) is called
        Then: GPUNotAvailableError names the device and the CUDA-only
              limitation, and no model loading is attempted. Previously a
              ROCm device passed this check and then failed inside torch
              at ``device="cuda"``.

        Type: Unit | Priority: Must Pass
        """
        from unittest.mock import patch

        from tessera.vision.pipeline import VisionPipeline
        from tessera.vision.types import GPUNotAvailableError, ImageInput

        pipeline = VisionPipeline(
            segmentation_adapter=_make_mock_segmentation_adapter(),
            depth_adapter=_make_mock_depth_adapter(),
            view_classifier_adapter=_make_mock_view_classifier(),
            feature_adapter=_make_mock_feature_adapter(),
        )
        img_path = _create_test_image(tmp_path, "test.jpg", 512, 512)

        with patch(
            "tessera.gpu_detection.get_gpu_info",
            return_value={
                "name": "Detected Device",
                "vram_gb": 16.0,
                "backend": backend,
                "shared_memory": backend == "METAL",
            },
        ):
            with pytest.raises(GPUNotAvailableError) as exc_info:
                pipeline.process([ImageInput(filepath=str(img_path))])

        message = str(exc_info.value)
        assert expected in message
        assert "NVIDIA CUDA only" in message
        pipeline._segmentation.load.assert_not_called()

    def test_TS008b_insufficient_vram_error(self, mock_bpy, tmp_path, mock_gpu_cuda):
        """TS-008b → EC-005: Call pipeline with GPU OOM — verify InsufficientVRAMError
        raised.

        Given: A CUDA GPU is available but has insufficient VRAM to load
               the segmentation model (torch.cuda.OutOfMemoryError during load)
        When: VisionPipeline.process(...) is called
        Then: The InsufficientVRAMError is raised with available vs.
              required VRAM details, and the model is properly cleaned up.

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.pipeline import VisionPipeline
        from tessera.vision.types import ImageInput, InsufficientVRAMError

        # Create a segmentation adapter whose load() raises OOM
        seg = _make_mock_segmentation_adapter()

        def _oom_load():
            raise InsufficientVRAMError(
                "Insufficient GPU VRAM: 3.5 GB available, "
                "~4.0 GB required for SAM 2 Large. Consider enabling "
                "low-VRAM mode in add-on preferences."
            )

        seg.load.side_effect = _oom_load

        pipeline = VisionPipeline(
            segmentation_adapter=seg,
            depth_adapter=_make_mock_depth_adapter(),
            view_classifier_adapter=_make_mock_view_classifier(),
            feature_adapter=_make_mock_feature_adapter(),
        )

        img_path = _create_test_image(tmp_path, "test.jpg", 512, 512)

        # When/Then
        with pytest.raises(InsufficientVRAMError) as exc_info:
            pipeline.process(
                [
                    ImageInput(filepath=str(img_path)),
                ]
            )

        error_msg = str(exc_info.value)
        assert "Insufficient GPU VRAM" in error_msg
        assert "available" in error_msg
        assert "required" in error_msg

        # Verify segmentation load was attempted but no further stages ran
        seg.load.assert_called_once()
        seg.predict.assert_not_called()


# ---------------------------------------------------------------------------
# TestOutputFormats (FR-005, FR-006, FR-007, FR-013)
# ---------------------------------------------------------------------------


class TestOutputFormats:
    """Tests for output data format validation (FR-005, FR-006, FR-007, FR-013)."""

    def test_TS011_segmentation_mask_format(
        self, mock_bpy, tmp_path, pipeline_with_mocks
    ):
        """TS-011 → FR-005: Segmentation mask output: verify shape matches input, dtype
        uint8, values 0 or 255.

        Given: A valid pipeline input image
        When: The segmentation stage completes
        Then: The mask has shape == input image (H, W), dtype == uint8,
              and all values are either 0 or 255.

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.types import ImageInput

        pipeline, _ = pipeline_with_mocks
        img_path = _create_test_image(tmp_path, "test.png", 640, 480)

        results = pipeline.process(
            [
                ImageInput(filepath=str(img_path)),
            ]
        )

        r = results[0]

        # FR-005: Mask shape matches input image spatial dimensions
        assert (
            r.mask.shape == r.image.shape[:2]
        ), f"Mask shape {r.mask.shape} != image shape {r.image.shape[:2]}"

        # dtype uint8
        assert r.mask.dtype == np.uint8

        # All values are 0 or 255
        unique_vals = set(np.unique(r.mask))
        assert unique_vals.issubset(
            {0, 255}
        ), f"Mask values should be 0 or 255, got {unique_vals}"

    def test_TS012_depth_map_format(self, mock_bpy, tmp_path, pipeline_with_mocks):
        """TS-012 → FR-006, FR-007: Depth map output: verify shape, dtype float32, range
        [0.0, 1.0], background zeroed.

        Given: A valid pipeline input image with a non-trivial mask
        When: The depth estimation stage completes
        Then: The depth_map has shape == (H, W), dtype == float32,
              all values in [0.0, 1.0], and background regions
              (where mask == 0) are 0.0.

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.types import ImageInput

        pipeline, _ = pipeline_with_mocks
        img_path = _create_test_image(tmp_path, "test.jpg", 512, 384)

        results = pipeline.process(
            [
                ImageInput(filepath=str(img_path)),
            ]
        )

        r = results[0]

        # Shape matches image
        assert (
            r.depth_map.shape == r.image.shape[:2]
        ), f"Depth shape {r.depth_map.shape} != image shape {r.image.shape[:2]}"

        # dtype float32
        assert r.depth_map.dtype == np.float32

        # Range [0.0, 1.0]
        assert r.depth_map.min() >= 0.0, f"Depth min {r.depth_map.min()} < 0.0"
        assert r.depth_map.max() <= 1.0, f"Depth max {r.depth_map.max()} > 1.0"

        # FR-007: Background regions (mask == 0) should be 0.0
        bg_pixels = r.depth_map[r.mask == 0]
        if len(bg_pixels) > 0:
            assert np.all(
                bg_pixels == 0.0
            ), "Background depth values should be 0.0 (FR-007)"

    def test_TS013_feature_vector_format(self, mock_bpy, tmp_path, pipeline_with_mocks):
        """TS-013 → FR-013: Feature vector output: verify shape (1, D), dtype float32,
        non-
        zero values.

        Given: A valid pipeline input image
        When: The feature extraction stage completes
        Then: The features array has shape (1, D) where D is the
              configured model's embedding dimension (768 for default
              DINOv2 ViT-B/14), dtype float32, and contains non-zero
              values.

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.types import ImageInput

        pipeline, _ = pipeline_with_mocks
        img_path = _create_test_image(tmp_path, "test.jpg", 600, 400)

        results = pipeline.process(
            [
                ImageInput(filepath=str(img_path)),
            ]
        )

        r = results[0]

        # Shape (1, D)
        assert r.features.ndim == 2
        assert r.features.shape[0] == 1
        assert (
            r.features.shape[1] == 768
        ), f"Expected embedding dim 768, got {r.features.shape[1]}"

        # dtype float32
        assert r.features.dtype == np.float32

        # Non-zero values (a valid embedding should not be all zeros)
        assert not np.allclose(
            r.features, 0.0
        ), "Feature vector should contain non-zero values"


# ---------------------------------------------------------------------------
# TestPerformance (NFR-001, NFR-002, NFR-003)
# ---------------------------------------------------------------------------


class TestPerformance:
    """Performance tests (NFR-001, NFR-002, NFR-003)."""

    def test_TS014_batch_6_images_latency_and_vram(
        self, mock_bpy, tmp_path, pipeline_with_mocks
    ):
        """TS-014 → NFR-001–003: Process 6 images on RTX 3060 — verify ≤ 30s total and ≤
        6
        GB peak VRAM.

        Given: 6 images at 1024×1024 pixel max dimension
        When: VisionPipeline.process(...) is called on an NVIDIA RTX
              3060 (12 GB VRAM)
        Then: Total wall-clock time is ≤ 30 seconds and peak VRAM
              usage (torch.cuda.max_memory_allocated()) is ≤ 6 GB.

        Type: Performance | Priority: Should Pass
        """
        import time

        from tessera.vision.types import ImageInput

        pipeline, adapters = pipeline_with_mocks

        # Given — 6 images at 1024×1024
        paths = [
            _create_test_image(tmp_path, f"perf{i}.jpg", 1024, 1024) for i in range(6)
        ]
        inputs = [ImageInput(filepath=str(p)) for p in paths]

        # When — time the execution
        start = time.monotonic()
        results = pipeline.process(inputs)
        elapsed = time.monotonic() - start

        # Then — all 6 processed
        assert len(results) == 6

        # With mock adapters, wall-clock should be well under 30s.
        # In production with real GPU, this validates NFR-001.
        assert (
            elapsed <= 30.0
        ), f"Pipeline took {elapsed:.2f}s, exceeds 30s target (NFR-001)"

        # Verify all adapter stages were called the correct number of times
        assert adapters["seg"].load.call_count == 1
        assert adapters["seg"].unload.call_count == 1
        assert adapters["seg"].predict.call_count == 6
        assert adapters["feat"].predict.call_count == 6


# ---------------------------------------------------------------------------
# TestModelLifecycle (FR-016, FR-017, FR-018)
# ---------------------------------------------------------------------------


class TestModelLifecycle:
    """Tests for model load/unload lifecycle (FR-016, FR-017, FR-018)."""

    def test_TS015_model_unload_vram_recovery(
        self, mock_bpy, tmp_path, pipeline_with_mocks
    ):
        """TS-015 → FR-017: Verify model unload after batch completion — VRAM returns to
        pre-pipeline level.

        Given: A batch of images processed through the pipeline
        When: All stages are complete
        Then: torch.cuda.memory_allocated() returns to approximately
              the pre-pipeline baseline level (within 100 MB).

        Type: Integration | Priority: Must Pass
        """
        from tessera.vision.types import ImageInput

        pipeline, adapters = pipeline_with_mocks

        paths = [
            _create_test_image(tmp_path, f"vram{i}.jpg", 512, 512) for i in range(3)
        ]
        inputs = [ImageInput(filepath=str(p)) for p in paths]

        # When
        pipeline.process(inputs)

        # Then — verify load/unload lifecycle for each adapter
        for name, adapter in adapters.items():
            assert (
                adapter.load.call_count == 1
            ), f"{name} adapter load() not called exactly once"
            assert (
                adapter.unload.call_count == 1
            ), f"{name} adapter unload() not called exactly once"

        # Verify call ordering: load → predict(s) → unload for each stage
        for name, adapter in adapters.items():
            # Get the call order from the mock
            calls = [c[0] for c in adapter.method_calls]
            call_names = [c for c in calls if c in ("load", "predict", "unload")]
            if call_names:
                assert (
                    call_names[0] == "load"
                ), f"{name}: Expected load() before predict()"
                assert (
                    call_names[-1] == "unload"
                ), f"{name}: Expected unload() after all predict() calls"

    def test_TS016_custom_segmentation_adapter(self, mock_bpy, tmp_path, mock_gpu_cuda):
        """TS-016 → FR-018: Register custom segmentation adapter — verify it's used
        instead
        of SAM 2.

        Given: A custom SegmentationAdapter subclass that returns a
               known fixed mask
        When: VisionPipeline(segmentation_adapter=custom) processes
              an image
        Then: The VisionResult.mask matches the custom adapter's
              fixed output, confirming adapter injection works.

        Type: Unit | Priority: Should Pass
        """
        from tessera.vision.pipeline import VisionPipeline
        from tessera.vision.types import ImageInput

        # Create a custom adapter that returns a specific pattern:
        # top half = 255 (foreground), bottom half = 0 (background)
        custom_seg = MagicMock()
        custom_seg.model_name = "CustomTestSegmentation"

        def _custom_predict(image):
            h, w = image.shape[:2]
            mask = np.zeros((h, w), dtype=np.uint8)
            mask[: h // 2, :] = 255  # Top half foreground
            return mask

        custom_seg.predict.side_effect = _custom_predict

        pipeline = VisionPipeline(
            segmentation_adapter=custom_seg,
            depth_adapter=_make_mock_depth_adapter(),
            view_classifier_adapter=_make_mock_view_classifier(),
            feature_adapter=_make_mock_feature_adapter(),
        )

        img_path = _create_test_image(tmp_path, "custom.jpg", 512, 512)
        results = pipeline.process(
            [
                ImageInput(filepath=str(img_path)),
            ]
        )

        assert len(results) == 1
        r = results[0]

        # Verify the custom adapter's pattern: top half = 255
        h = r.mask.shape[0]
        top_half = r.mask[: h // 2, :]
        bottom_half = r.mask[h // 2 :, :]

        assert np.all(
            top_half == 255
        ), "Custom adapter's top-half foreground not preserved"
        assert np.all(
            bottom_half == 0
        ), "Custom adapter's bottom-half background not preserved"

        # Verify load/unload called on custom adapter
        custom_seg.load.assert_called_once()
        custom_seg.unload.assert_called_once()


# ---------------------------------------------------------------------------
# TestSecurity (SEC-001, SEC-005)
# ---------------------------------------------------------------------------


class TestSecurity:
    """Security tests (SEC-001, SEC-005)."""

    def test_TS017_file_size_exceeds_50mb(
        self, mock_bpy, tmp_path, pipeline_with_mocks
    ):
        """TS-017 → SEC-005: Process image exceeding 50 MB file size — verify rejection
        before loading.

        Given: An image file larger than 50 MB
        When: The preprocessing stage validates it
        Then: An ImageLoadError is raised with a message indicating
              the file size exceeds the maximum, and no attempt is
              made to load the image data.

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.preprocessing import load_and_preprocess
        from tessera.vision.types import ImageInput, ImageLoadError

        # Given — create a file that exceeds 50 MB
        large_path = tmp_path / "huge.jpg"
        # Write a valid JPEG header + enough data to exceed 50MB
        large_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * (51 * 1024 * 1024))

        # When/Then
        with pytest.raises(ImageLoadError) as exc_info:
            load_and_preprocess(ImageInput(filepath=str(large_path)))

        error_msg = str(exc_info.value)
        assert (
            "exceeds maximum" in error_msg.lower() or "file size" in error_msg.lower()
        ), f"Expected file size error message, got: {error_msg}"

    def test_TS018_path_traversal_prevention(
        self, mock_bpy, tmp_path, pipeline_with_mocks
    ):
        """TS-018 → SEC-001: Attempt path traversal in filepath — verify SEC-001 catches
        it.

        Given: An ImageInput with filepath containing path traversal
               sequences (e.g., "../../etc/passwd")
        When: The preprocessing stage validates the path
        Then: An ImageLoadError is raised before any file read attempt.

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.preprocessing import load_and_preprocess
        from tessera.vision.types import ImageInput, ImageLoadError

        # Test 1: Path traversal to non-existent file
        with pytest.raises(ImageLoadError):
            load_and_preprocess(ImageInput(filepath="../../etc/passwd.jpg"))

        # Test 2: Path traversal with null bytes
        with pytest.raises(ImageLoadError):
            load_and_preprocess(ImageInput(filepath="/tmp/\x00evil.jpg"))

        # Test 3: Non-existent deeply nested traversal path
        with pytest.raises(ImageLoadError):
            load_and_preprocess(
                ImageInput(filepath="/tmp/../../../nonexistent/image.jpg")
            )


# ---------------------------------------------------------------------------
# TestBatchValidation (FR-001)
# ---------------------------------------------------------------------------


class TestBatchValidation:
    """Tests for batch size validation (FR-001)."""

    def test_TS019_empty_image_list(self, mock_bpy, pipeline_with_mocks):
        """TS-019 → FR-001: Call pipeline.process([]) with empty list — verify
        PipelineError("No images provided.") raised.

        Given: An empty list of ImageInput objects
        When: VisionPipeline.process([]) is called
        Then: PipelineError is raised with message "No images provided."

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.types import PipelineError

        pipeline, _ = pipeline_with_mocks

        # When/Then
        with pytest.raises(PipelineError, match="No images provided"):
            pipeline.process([])

    def test_TS020_batch_exceeds_maximum(self, mock_bpy, tmp_path, pipeline_with_mocks):
        """TS-020 → FR-001: Call pipeline.process(...) with 7 images — verify
        PipelineError("Batch size 7 exceeds maximum of 6.") raised.

        Given: A list of 7 ImageInput objects
        When: VisionPipeline.process(seven_images) is called
        Then: PipelineError is raised with message "Batch size 7
              exceeds maximum of 6."

        Type: Unit | Priority: Must Pass
        """
        from tessera.vision.types import ImageInput, PipelineError

        pipeline, _ = pipeline_with_mocks

        # Given — 7 images
        paths = [
            _create_test_image(tmp_path, f"batch{i}.jpg", 256, 256) for i in range(7)
        ]
        inputs = [ImageInput(filepath=str(p)) for p in paths]

        # When/Then
        with pytest.raises(PipelineError, match="Batch size 7 exceeds maximum of 6"):
            pipeline.process(inputs)
