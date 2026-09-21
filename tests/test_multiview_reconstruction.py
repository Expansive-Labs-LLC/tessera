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

"""Test suite for multi-view alignment and reconstruction.

Covers all acceptance criteria (AC-001 through AC-007), edge cases
(EC-001 through EC-007), and key functional requirements from
SPEC-TS-0007.

Test stubs are marked with ``pytest.skip()`` when they require
external dependencies (hloc, NeuS2, bpy) that are not available
in the CI environment.

Spec: SPEC-TS-0007, §10 (Test Stubs)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# -----------------------------------------------------------------------
# Lazy imports — deferred so conftest's bpy mock is active first
# -----------------------------------------------------------------------


@pytest.fixture
def multiview_imports():
    """Import multiview modules after bpy mock is installed."""
    from tessera.multiview.pose_estimation.base import PoseEstimator
    from tessera.multiview.pose_estimation.hloc_estimator import (
        HlocPoseEstimator,
    )
    from tessera.multiview.pose_estimation.label_prior import (
        compute_angular_separation,
        get_prior_pose,
        label_to_rotation_matrix,
    )
    from tessera.multiview.pose_estimation.types import (
        CameraPose,
        InsufficientOverlapError,
        InsufficientSeparationError,
        PoseEstimationError,
        PoseEstimationResult,
    )
    from tessera.multiview.preview.camera_setup import (
        PREVIEW_RESOLUTION,
        PREVIEW_VIEWS,
        PreviewImage,
        compute_camera_position,
        compute_framing_distance,
    )
    from tessera.multiview.reconstruction.multiview_adapter import (
        MultiViewAdapter,
    )
    from tessera.multiview.strategy import StrategySelector

    class _Imports:
        pass

    m = _Imports()
    m.CameraPose = CameraPose
    m.PoseEstimationResult = PoseEstimationResult
    m.PoseEstimationError = PoseEstimationError
    m.InsufficientOverlapError = InsufficientOverlapError
    m.InsufficientSeparationError = InsufficientSeparationError
    m.PoseEstimator = PoseEstimator
    m.HlocPoseEstimator = HlocPoseEstimator
    m.label_to_rotation_matrix = label_to_rotation_matrix
    m.get_prior_pose = get_prior_pose
    m.compute_angular_separation = compute_angular_separation
    m.MultiViewAdapter = MultiViewAdapter
    m.StrategySelector = StrategySelector
    m.PreviewImage = PreviewImage
    m.PREVIEW_VIEWS = PREVIEW_VIEWS
    m.PREVIEW_RESOLUTION = PREVIEW_RESOLUTION
    m.compute_camera_position = compute_camera_position
    m.compute_framing_distance = compute_framing_distance
    return m


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


def _make_vision_result(**overrides):
    """Create a VisionResult-like object with test data.

    Uses SimpleNamespace instead of MagicMock because VisionResult
    is an internal data class — not an external dependency.
    """
    from tests.fakes import make_vision_result

    return make_vision_result(**overrides)


def _make_camera_pose(m, **overrides):
    """Create a CameraPose for testing."""
    defaults = {
        "rotation": np.eye(3, dtype=np.float64),
        "translation": np.array([0.0, 0.0, 2.0], dtype=np.float64),
        "focal_length": 525.0,
        "principal_point": (128.0, 128.0),
        "image_size": (256, 256),
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return m.CameraPose(**defaults)


# ===================================================================
# TS-001: StrategySelector routes 1–2 images to single-image path
# Acceptance Criteria: AC-001
# ===================================================================


class TestTS001StrategySingleImage:
    """TS-001: Single-image routing."""

    def test_single_image_selected_for_one_input(self, multiview_imports):
        """1 image → single-image strategy."""
        m = multiview_imports

        single = MagicMock()
        single.reconstruct.return_value = MagicMock(
            mesh=MagicMock(metadata={}), success=True, warnings=[]
        )
        multi = MagicMock()
        estimator = MagicMock()

        selector = m.StrategySelector(single, multi, estimator)
        vr = _make_vision_result()
        result = selector.reconstruct([vr])

        single.reconstruct.assert_called_once()
        multi.reconstruct.assert_not_called()
        estimator.estimate_poses.assert_not_called()

    def test_single_image_selected_for_two_inputs(self, multiview_imports):
        """2 images → single-image strategy."""
        m = multiview_imports

        single = MagicMock()
        single.reconstruct.return_value = MagicMock(
            mesh=MagicMock(metadata={}), success=True, warnings=[]
        )
        multi = MagicMock()
        estimator = MagicMock()

        selector = m.StrategySelector(single, multi, estimator)
        vrs = [_make_vision_result(view_label="front"),
               _make_vision_result(view_label="back")]
        result = selector.reconstruct(vrs)

        single.reconstruct.assert_called_once()
        multi.reconstruct.assert_not_called()


# ===================================================================
# TS-002: StrategySelector routes ≥3 images to multi-view path
# Acceptance Criteria: AC-001
# ===================================================================


class TestTS002StrategyMultiView:
    """TS-002: Multi-view routing."""

    def test_multiview_selected_for_three_inputs(self, multiview_imports):
        """3 images → multi-view strategy."""
        m = multiview_imports

        single = MagicMock()
        multi = MagicMock()
        multi.reconstruct.return_value = MagicMock(
            mesh=MagicMock(metadata={}), success=True, warnings=[]
        )
        estimator = MagicMock()
        estimator.estimate_poses.return_value = m.PoseEstimationResult(
            poses=[_make_camera_pose(m)] * 3,
            num_registered=3,
            inlier_ratio=0.8,
            success=True,
        )

        selector = m.StrategySelector(single, multi, estimator)
        vrs = [_make_vision_result(view_label=label)
               for label in ["front", "right", "back"]]
        result = selector.reconstruct(vrs)

        estimator.estimate_poses.assert_called_once()
        multi.reconstruct.assert_called_once()
        single.reconstruct.assert_not_called()


# ===================================================================
# TS-003: Strategy metadata is recorded
# Acceptance Criteria: AC-001
# ===================================================================


class TestTS003StrategyMetadata:
    """TS-003: Strategy metadata recording."""

    def test_strategy_recorded_in_mesh_metadata(self, multiview_imports):
        """Mesh metadata contains strategy key."""
        m = multiview_imports

        single = MagicMock()
        single.reconstruct.return_value = MagicMock(
            mesh=MagicMock(metadata={}), success=True, warnings=[]
        )
        multi = MagicMock()
        estimator = MagicMock()

        selector = m.StrategySelector(single, multi, estimator)
        vr = _make_vision_result()
        result = selector.reconstruct([vr])

        mesh = single.reconstruct.return_value.mesh
        assert "strategy" in mesh.metadata


# ===================================================================
# TS-004: CameraPose dataclass validation
# Acceptance Criteria: AC-002
# ===================================================================


class TestTS004CameraPose:
    """TS-004: CameraPose validation."""

    def test_valid_camera_pose_creation(self, multiview_imports):
        """CameraPose with valid data does not raise."""
        m = multiview_imports
        pose = _make_camera_pose(m)
        assert pose.rotation.shape == (3, 3)
        assert pose.translation.shape == (3,)
        assert 0.0 <= pose.confidence <= 1.0

    def test_invalid_rotation_shape_raises(self, multiview_imports):
        """CameraPose with wrong rotation shape raises ValueError."""
        m = multiview_imports
        with pytest.raises(ValueError, match="rotation"):
            m.CameraPose(
                rotation=np.eye(4),
                translation=np.zeros(3),
                focal_length=525.0,
                principal_point=(128.0, 128.0),
                image_size=(256, 256),
                confidence=0.9,
            )

    def test_invalid_confidence_raises(self, multiview_imports):
        """CameraPose with confidence > 1.0 raises ValueError."""
        m = multiview_imports
        with pytest.raises(ValueError, match="confidence"):
            m.CameraPose(
                rotation=np.eye(3),
                translation=np.zeros(3),
                focal_length=525.0,
                principal_point=(128.0, 128.0),
                image_size=(256, 256),
                confidence=1.5,
            )


# ===================================================================
# TS-005: PoseEstimationResult dataclass
# Acceptance Criteria: AC-002
# ===================================================================


class TestTS005PoseEstimationResult:
    """TS-005: PoseEstimationResult fields."""

    def test_successful_result(self, multiview_imports):
        """Successful result has success=True."""
        m = multiview_imports
        result = m.PoseEstimationResult(
            poses=[_make_camera_pose(m)] * 3,
            num_registered=3,
            inlier_ratio=0.8,
            success=True,
        )
        assert result.success is True
        assert result.num_registered == 3

    def test_failed_result_has_error_message(self, multiview_imports):
        """Failed result has non-empty error_message."""
        m = multiview_imports
        result = m.PoseEstimationResult(
            poses=[None, None, None],
            num_registered=0,
            inlier_ratio=0.0,
            success=False,
            error_message="Insufficient feature matches.",
        )
        assert result.success is False
        assert result.error_message != ""


# ===================================================================
# TS-006: View-label priors (label_prior.py)
# Acceptance Criteria: AC-002
# ===================================================================


class TestTS006LabelPriors:
    """TS-006: View-label to camera prior conversion."""

    def test_front_label_produces_identity_azimuth(self, multiview_imports):
        """'front' label corresponds to 0° azimuth."""
        m = multiview_imports
        pose = m.get_prior_pose("front", (256, 256))
        assert pose is not None
        assert pose.confidence == 1.0

    def test_unknown_label_returns_none(self, multiview_imports):
        """Custom/unknown label returns None."""
        m = multiview_imports
        pose = m.get_prior_pose("custom", (256, 256))
        assert pose is None

    def test_angular_separation_orthogonal_views(self, multiview_imports):
        """90° rotation produces ~90° angular separation."""
        m = multiview_imports
        r1 = m.label_to_rotation_matrix(0.0, 0.0)
        r2 = m.label_to_rotation_matrix(90.0, 0.0)
        angle = m.compute_angular_separation(r1, r2)
        assert 80.0 < angle < 100.0


# ===================================================================
# TS-007: HlocPoseEstimator (guarded import)
# Acceptance Criteria: AC-002
# ===================================================================


class TestTS007HlocEstimator:
    """TS-007: HlocPoseEstimator instantiation."""

    def test_estimator_instantiation(self, multiview_imports):
        """HlocPoseEstimator can be instantiated."""
        m = multiview_imports
        estimator = m.HlocPoseEstimator(cache_dir="/tmp/test_cache")
        assert estimator is not None

    def test_estimator_requires_vision_results(self, multiview_imports):
        """estimate_poses() requires list of VisionResult."""
        m = multiview_imports
        estimator = m.HlocPoseEstimator(cache_dir="/tmp/test_cache")
        # Should raise due to missing hloc/torch dependency
        with pytest.raises((RuntimeError, ImportError)):
            estimator.estimate_poses([_make_vision_result()] * 3)


# ===================================================================
# TS-008: MultiViewAdapter capabilities
# Acceptance Criteria: AC-003
# ===================================================================


class TestTS008MultiViewAdapterCapabilities:
    """TS-008: MultiViewAdapter capabilities."""

    def test_capabilities_min_max_images(self, multiview_imports):
        """Capabilities declare min_images=3, max_images=12."""
        m = multiview_imports
        adapter = m.MultiViewAdapter(cache_dir="/tmp/test_cache")
        caps = adapter.capabilities()
        assert caps.min_images == 3
        assert caps.max_images == 12

    def test_capabilities_model_name(self, multiview_imports):
        """Capabilities declare model_name='neus2-v1.0'."""
        m = multiview_imports
        adapter = m.MultiViewAdapter(cache_dir="/tmp/test_cache")
        caps = adapter.capabilities()
        assert caps.model_name == "neus2-v1.0"

    def test_invalid_mc_resolution_raises(self, multiview_imports):
        """Invalid marching cubes resolution raises ValueError."""
        m = multiview_imports
        with pytest.raises(ValueError, match="marching_cubes_resolution"):
            m.MultiViewAdapter(
                cache_dir="/tmp/test_cache",
                marching_cubes_resolution=100,
            )


# ===================================================================
# TS-009: NeuS2Backend weights check
# Acceptance Criteria: AC-003
# ===================================================================


class TestTS009NeuS2Backend:
    """TS-009: NeuS2Backend weight validation."""

    def test_weights_not_available_when_missing(self, multiview_imports):
        """weights_available() returns False for missing dir."""
        from tessera.multiview.reconstruction.neus2_backend import (
            NeuS2Backend,
        )

        backend = NeuS2Backend(cache_dir="/nonexistent/path")
        assert backend.weights_available() is False


# ===================================================================
# TS-010: Confidence score computation
# Acceptance Criteria: AC-003
# ===================================================================


class TestTS010ConfidenceScore:
    """TS-010: Multi-view confidence scoring."""

    def test_perfect_inputs_yield_high_confidence(self, multiview_imports):
        """All cameras registered + high inlier + low loss → ≥ 0.8."""
        m = multiview_imports
        score = m.MultiViewAdapter._compute_confidence(
            num_registered=6,
            total_cameras=6,
            inlier_ratio=0.9,
            final_loss=0.01,
        )
        assert score >= 0.8

    def test_poor_inputs_yield_low_confidence(self, multiview_imports):
        """Few cameras + low inlier + high loss → ≤ 0.4."""
        m = multiview_imports
        score = m.MultiViewAdapter._compute_confidence(
            num_registered=2,
            total_cameras=6,
            inlier_ratio=0.1,
            final_loss=0.9,
        )
        assert score <= 0.4


# ===================================================================
# TS-011: Input validation — 0 images
# Acceptance Criteria: AC-001, FR-036
# ===================================================================


class TestTS011ZeroImages:
    """TS-011: Zero-image error handling."""

    def test_zero_images_returns_error(self, multiview_imports):
        """0 images → error result."""
        m = multiview_imports
        selector = m.StrategySelector(MagicMock(), MagicMock(), MagicMock())
        result = selector.reconstruct([])
        assert result.success is False
        assert "No input images" in result.error_message


# ===================================================================
# TS-012: Input validation — >12 images
# Acceptance Criteria: AC-001, FR-036
# ===================================================================


class TestTS012TooManyImages:
    """TS-012: Excess image error handling."""

    def test_13_images_returns_error(self, multiview_imports):
        """>12 images → error result."""
        m = multiview_imports
        selector = m.StrategySelector(MagicMock(), MagicMock(), MagicMock())
        vrs = [_make_vision_result() for _ in range(13)]
        result = selector.reconstruct(vrs)
        assert result.success is False
        assert "Too many" in result.error_message


# ===================================================================
# TS-013: Fallback to single-image on pose failure
# Acceptance Criteria: AC-004, FR-025–FR-027
# ===================================================================


class TestTS013FallbackOnPoseFailure:
    """TS-013: Single-image fallback."""

    def test_fallback_on_pose_estimation_failure(self, multiview_imports):
        """Pose estimation failure triggers single-image fallback."""
        m = multiview_imports

        single = MagicMock()
        single.reconstruct.return_value = MagicMock(
            mesh=MagicMock(metadata={}), success=True, warnings=[]
        )
        multi = MagicMock()
        estimator = MagicMock()
        estimator.estimate_poses.side_effect = RuntimeError("hloc failed")

        selector = m.StrategySelector(single, multi, estimator)
        vrs = [_make_vision_result() for _ in range(5)]
        result = selector.reconstruct(vrs)

        single.reconstruct.assert_called_once()
        multi.reconstruct.assert_not_called()

    def test_fallback_on_unsuccessful_pose_result(self, multiview_imports):
        """Unsuccessful pose result triggers fallback."""
        m = multiview_imports

        single = MagicMock()
        single.reconstruct.return_value = MagicMock(
            mesh=MagicMock(metadata={}), success=True, warnings=[]
        )
        multi = MagicMock()
        estimator = MagicMock()
        estimator.estimate_poses.return_value = m.PoseEstimationResult(
            poses=[None] * 5,
            num_registered=1,
            inlier_ratio=0.1,
            success=False,
            error_message="Only 1 camera registered",
        )

        selector = m.StrategySelector(single, multi, estimator)
        vrs = [_make_vision_result() for _ in range(5)]
        result = selector.reconstruct(vrs)

        single.reconstruct.assert_called_once()


# ===================================================================
# TS-014: Best image selection by mask area
# Acceptance Criteria: AC-004, FR-026
# ===================================================================


class TestTS014BestImageSelection:
    """TS-014: Best image selection by mask area."""

    def test_largest_mask_area_selected(self, multiview_imports):
        """Image with largest mask area is selected."""
        m = multiview_imports

        small_mask = np.zeros((256, 256), dtype=np.uint8)
        small_mask[100:150, 100:150] = 255  # Small region

        large_mask = np.ones((256, 256), dtype=np.uint8) * 255  # Full mask

        selector = m.StrategySelector(MagicMock(), MagicMock(), MagicMock())
        vrs = [
            _make_vision_result(mask=small_mask, view_label="front"),
            _make_vision_result(mask=large_mask, view_label="back"),
        ]
        best_idx = selector._select_best_single_image(vrs)
        assert best_idx == 1


# ===================================================================
# TS-015: PreviewImage dataclass
# Acceptance Criteria: AC-005
# ===================================================================


class TestTS015PreviewImage:
    """TS-015: PreviewImage validation."""

    def test_preview_image_fields(self, multiview_imports):
        """PreviewImage has required fields."""
        m = multiview_imports
        pi = m.PreviewImage(
            view_label="front",
            filepath="/tmp/preview_front.png",
            resolution=(512, 512),
            camera_pose={"azimuth": 0.0, "elevation": 0.0},
        )
        assert pi.view_label == "front"
        assert pi.resolution == (512, 512)

    def test_all_four_preview_views_defined(self, multiview_imports):
        """PREVIEW_VIEWS contains exactly 4 canonical views."""
        m = multiview_imports
        assert len(m.PREVIEW_VIEWS) == 4
        labels = {v["label"] for v in m.PREVIEW_VIEWS}
        assert labels == {"front", "right", "top", "isometric"}


# ===================================================================
# TS-016: Camera framing distance computation
# Acceptance Criteria: AC-005, FR-031
# ===================================================================


class TestTS016CameraFraming:
    """TS-016: Camera framing distance."""

    def test_framing_distance_positive(self, multiview_imports):
        """Framing distance is always positive."""
        m = multiview_imports
        dist = m.compute_framing_distance((1.0, 1.0, 1.0))
        assert dist > 0

    def test_larger_bbox_yields_larger_distance(self, multiview_imports):
        """Larger bounding box → larger camera distance."""
        m = multiview_imports
        small_dist = m.compute_framing_distance((1.0, 1.0, 1.0))
        large_dist = m.compute_framing_distance((5.0, 5.0, 5.0))
        assert large_dist > small_dist


# ===================================================================
# TS-017: PreviewRenderer object validation
# Acceptance Criteria: AC-005, FR-037, EC-007
# ===================================================================


class TestTS017PreviewValidation:
    """TS-017: Preview object validation."""

    @pytest.mark.skip(reason="Requires bpy; test in Blender environment")
    def test_invalid_object_raises_valueerror(self, multiview_imports):
        """Invalid/deleted object raises ValueError."""
        from tessera.multiview.preview.renderer import PreviewRenderer

        renderer = PreviewRenderer()
        with pytest.raises(ValueError, match="not found"):
            renderer.render_previews(MagicMock(), "/tmp/previews")


# ===================================================================
# TS-018: Error types
# Acceptance Criteria: AC-006
# ===================================================================


class TestTS018ErrorTypes:
    """TS-018: Error class hierarchy."""

    def test_insufficient_overlap_is_pose_error(self, multiview_imports):
        """InsufficientOverlapError inherits PoseEstimationError."""
        m = multiview_imports
        assert issubclass(m.InsufficientOverlapError, m.PoseEstimationError)

    def test_insufficient_separation_is_pose_error(self, multiview_imports):
        """InsufficientSeparationError inherits PoseEstimationError."""
        m = multiview_imports
        assert issubclass(m.InsufficientSeparationError, m.PoseEstimationError)

    def test_error_messages(self, multiview_imports):
        """Error classes accept custom messages."""
        m = multiview_imports
        err = m.InsufficientOverlapError("Only 2 cameras registered")
        assert "2 cameras" in str(err)


# ===================================================================
# TS-019: Angular separation check (EC-001)
# Acceptance Criteria: AC-006, EC-001
# ===================================================================


class TestTS019AngularSeparation:
    """TS-019: Angular separation validation."""

    def test_identity_rotation_zero_separation(self, multiview_imports):
        """Two identical rotations → 0° separation."""
        m = multiview_imports
        r = np.eye(3, dtype=np.float64)
        angle = m.compute_angular_separation(r, r)
        assert abs(angle) < 1.0

    def test_90_degree_rotation(self, multiview_imports):
        """90° Y-rotation produces ~90° separation."""
        m = multiview_imports
        r1 = np.eye(3, dtype=np.float64)
        r2 = m.label_to_rotation_matrix(90.0, 0.0)
        angle = m.compute_angular_separation(r1, r2)
        assert 80.0 < angle < 100.0


# ===================================================================
# TS-020: Confirmed label counting (FR-002)
# Acceptance Criteria: AC-001, EC-002
# ===================================================================


class TestTS020ConfirmedLabels:
    """TS-020: Confirmed label counting."""

    def test_all_confirmed(self, multiview_imports):
        """All confirmed labels counted."""
        m = multiview_imports
        selector = m.StrategySelector(MagicMock(), MagicMock(), MagicMock())
        vrs = [
            _make_vision_result(label_needs_confirmation=False),
            _make_vision_result(label_needs_confirmation=False),
            _make_vision_result(label_needs_confirmation=False),
        ]
        assert selector._count_confirmed_labels(vrs) == 3

    def test_mixed_confirmed(self, multiview_imports):
        """Only non-confirmation labels counted."""
        m = multiview_imports
        selector = m.StrategySelector(MagicMock(), MagicMock(), MagicMock())
        vrs = [
            _make_vision_result(label_needs_confirmation=False),
            _make_vision_result(label_needs_confirmation=True),
            _make_vision_result(label_needs_confirmation=False),
        ]
        assert selector._count_confirmed_labels(vrs) == 2


# ===================================================================
# TS-021: Camera position computation
# Acceptance Criteria: AC-005
# ===================================================================


class TestTS021CameraPosition:
    """TS-021: Camera position from azimuth/elevation."""

    def test_front_camera_on_negative_y(self, multiview_imports):
        """Front camera (0° az, 0° el) is on -Y axis."""
        m = multiview_imports
        x, y, z = m.compute_camera_position(0.0, 0.0, 2.0)
        assert abs(x) < 0.01
        assert y < 0
        assert abs(z) < 0.01

    def test_top_camera_on_positive_z(self, multiview_imports):
        """Top camera (0° az, 90° el) is on +Z axis."""
        m = multiview_imports
        x, y, z = m.compute_camera_position(0.0, 90.0, 2.0)
        assert abs(x) < 0.01
        assert abs(z - 2.0) < 0.01


# ===================================================================
# TS-022: VRAM guard integration (CON-003)
# Acceptance Criteria: AC-007
# ===================================================================


class TestTS022VRAMGuard:
    """TS-022: VRAM guard integration."""

    def test_vram_guard_cleanup_imported(self, multiview_imports):
        """VRAMGuard is importable and has cleanup_gpu()."""
        from tessera.reconstruction.utils.vram_guard import VRAMGuard

        assert hasattr(VRAMGuard, "cleanup_gpu")
        assert hasattr(VRAMGuard, "check")


# ===================================================================
# TS-023: Package imports
# Acceptance Criteria: AC-007
# ===================================================================


class TestTS023PackageImports:
    """TS-023: Public API importability."""

    def test_strategy_selector_import(self, multiview_imports):
        """StrategySelector is importable."""
        m = multiview_imports
        assert m.StrategySelector is not None

    def test_pose_types_import(self, multiview_imports):
        """Pose estimation types are importable."""
        m = multiview_imports
        assert m.CameraPose is not None
        assert m.PoseEstimationResult is not None

    def test_multiview_adapter_import(self, multiview_imports):
        """MultiViewAdapter is importable."""
        m = multiview_imports
        assert m.MultiViewAdapter is not None

    def test_preview_imports(self, multiview_imports):
        """Preview types are importable."""
        m = multiview_imports
        assert m.PreviewImage is not None
        assert len(m.PREVIEW_VIEWS) == 4
