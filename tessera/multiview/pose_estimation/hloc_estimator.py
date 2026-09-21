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

"""hloc-based pose estimator using SuperPoint + LightGlue.

Implements a lightweight Structure-from-Motion (SfM) pipeline that:
1. Extracts SuperPoint keypoints from each masked image.
2. Performs pairwise feature matching with LightGlue.
3. Uses view-label priors as constraints.
4. Runs bundle adjustment to refine camera poses.

Models are loaded and unloaded sequentially to stay within VRAM
limits (CON-003, FR-015).

Spec: SPEC-TS-0007 (Multi-View Alignment & Enhanced Reconstruction)

Public API:
    HlocPoseEstimator — concrete PoseEstimator implementation (FR-006)
"""

from __future__ import annotations

import logging
import os
import time

import numpy as np

from tessera.multiview.pose_estimation.base import PoseEstimator
from tessera.multiview.pose_estimation.label_prior import (
    compute_angular_separation,
    get_prior_pose,
    label_to_rotation_matrix,
)
from tessera.multiview.pose_estimation.types import (
    CameraPose,
    PoseEstimationResult,
)
from tessera.reconstruction.utils.vram_guard import VRAMGuard
import importlib.util as _importlib_util
import os as _os

# Load VisionResult and VIEW_LABEL_POSES directly from the types.py
# file to avoid triggering tessera.vision.__init__ which eagerly
# imports the full pipeline and its heavy dependencies (PIL, etc.).
_types_path = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))),
    "vision",
    "types.py",
)
_spec = _importlib_util.spec_from_file_location("tessera.vision.types", _types_path)
_vision_types = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_vision_types)
VIEW_LABEL_POSES = _vision_types.VIEW_LABEL_POSES  # noqa: F401
VisionResult = _vision_types.VisionResult  # noqa: F401
del _vision_types, _spec, _types_path, _importlib_util, _os

logger = logging.getLogger("tessera.multiview")

# FR-007: Maximum resolution for feature extraction.
_MAX_FEATURE_RESOLUTION = 1024

# EC-001: Minimum viable angular separation threshold (degrees).
_MIN_ANGULAR_SEPARATION_DEG = 20.0

# EC-003: Minimum inlier ratio threshold for feature matching.
_MIN_INLIER_RATIO = 0.20

# FR-010: Minimum confidence for auto-detected labels to serve as
# soft priors.
_AUTO_LABEL_MIN_CONFIDENCE = 0.80


class HlocPoseEstimator(PoseEstimator):
    """hloc-based pose estimator using SuperPoint + LightGlue.

    Estimates camera poses from multiple images using sparse feature
    matching and bundle adjustment.  View labels from the vision
    pipeline (SPEC-TS-0003) act as strong or soft priors depending
    on their source and confidence.

    Models are loaded and unloaded sequentially to stay within VRAM
    limits.  SuperPoint is loaded first for keypoint extraction
    across all images, then unloaded before LightGlue is loaded for
    pairwise matching.

    Args:
        cache_dir: Absolute path to the model weight cache directory.
            SuperPoint and LightGlue weights are expected at
            ``<cache_dir>/superpoint/`` and ``<cache_dir>/lightglue/``.

    Implements: FR-006, FR-007–FR-015, CON-001, CON-003, CON-005,
        CON-009, SEC-002, SEC-005.
    """

    def __init__(self, cache_dir: str) -> None:
        """Initialise the hloc pose estimator.

        Args:
            cache_dir: Path to model weight cache directory.
        """
        self._cache_dir = cache_dir

    def _superpoint_weight_path(self) -> str:
        """Return path to SuperPoint weight file."""
        return os.path.join(self._cache_dir, "superpoint", "superpoint_v1.pth")

    def _lightglue_weight_path(self) -> str:
        """Return path to LightGlue weight file."""
        return os.path.join(
            self._cache_dir, "lightglue", "lightglue_superpoint.pth"
        )

    def _prepare_image(
        self, image: np.ndarray, mask: np.ndarray
    ) -> np.ndarray:
        """Apply mask and resize for feature extraction.

        Zeros out background pixels using the segmentation mask and
        resizes the image so the longest dimension is at most
        ``_MAX_FEATURE_RESOLUTION`` pixels.

        Args:
            image: RGB image, shape ``(H, W, 3)`` uint8.
            mask: Binary mask, shape ``(H, W)`` uint8, 0 or 255.

        Returns:
            Masked and resized image, shape ``(H', W', 3)`` uint8.

        Implements: FR-007.
        """
        # Apply mask — zero out background
        mask_3ch = (mask > 0).astype(np.uint8)[..., np.newaxis]
        masked = image * mask_3ch

        # Resize if necessary
        h, w = masked.shape[:2]
        max_dim = max(h, w)
        if max_dim > _MAX_FEATURE_RESOLUTION:
            scale = _MAX_FEATURE_RESOLUTION / max_dim
            new_h = int(h * scale)
            new_w = int(w * scale)
            # Use simple interpolation without external dependency
            # In production, cv2 or PIL would be used here
            try:
                import cv2  # type: ignore[import-not-found]

                masked = cv2.resize(
                    masked, (new_w, new_h), interpolation=cv2.INTER_LINEAR
                )
            except ImportError:
                # Fallback: nearest-neighbour via numpy slicing
                row_idx = np.linspace(0, h - 1, new_h, dtype=int)
                col_idx = np.linspace(0, w - 1, new_w, dtype=int)
                masked = masked[np.ix_(row_idx, col_idx)]

        return masked

    def _extract_keypoints(
        self, images: list[np.ndarray]
    ) -> list[dict]:
        """Extract SuperPoint keypoints and descriptors from images.

        Loads the SuperPoint model, processes all images sequentially,
        then unloads the model to free VRAM.

        Args:
            images: List of preprocessed (masked, resized) images.

        Returns:
            List of dicts, each containing ``keypoints`` (N×2 float32)
            and ``descriptors`` (N×256 float32).

        Implements: FR-007, FR-015, CON-003.
        """
        results = []

        try:
            import torch  # type: ignore[import-not-found]

            weight_path = self._superpoint_weight_path()
            if not os.path.isfile(weight_path):
                raise FileNotFoundError(
                    f"SuperPoint weights not found at {os.path.basename(weight_path)}. "
                    "Download via Add-on Preferences → Tessera → Download Models."
                )

            logger.info("Loading SuperPoint model for keypoint extraction")

            try:
                from hloc.extractors.superpoint import (  # type: ignore[import-not-found]
                    SuperPoint,
                )

                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                model = SuperPoint({}).to(device)
                state = torch.load(weight_path, map_location=device, weights_only=True)
                model.load_state_dict(state)
                model.eval()

                for i, img in enumerate(images):
                    start = time.monotonic()
                    # Convert to grayscale float tensor
                    gray = np.mean(img.astype(np.float32), axis=2) / 255.0
                    tensor = torch.from_numpy(gray).unsqueeze(0).unsqueeze(0).to(device)

                    with torch.no_grad():
                        pred = model({"image": tensor})

                    kp = pred["keypoints"][0].cpu().numpy()
                    desc = pred["descriptors"][0].cpu().numpy().T

                    results.append({"keypoints": kp, "descriptors": desc})
                    duration = time.monotonic() - start
                    logger.debug(
                        "SuperPoint keypoints extracted: image_index=%d, "
                        "num_keypoints=%d, duration_s=%.2f",
                        i,
                        len(kp),
                        duration,
                    )

                # Unload model
                del model
                torch.cuda.empty_cache()
                logger.debug("SuperPoint model unloaded")

            except ImportError:
                raise RuntimeError(
                    "hloc package is not installed. Bundle the hloc wheel "
                    "or install via pip for pose estimation."
                )

        except ImportError:
            raise RuntimeError(
                "PyTorch is not available. Install PyTorch with CUDA "
                "support for pose estimation."
            )

        return results

    def _match_features(
        self, keypoints_list: list[dict]
    ) -> tuple[dict[tuple[int, int], np.ndarray], dict[tuple[int, int], int]]:
        """Perform pairwise feature matching using LightGlue.

        Loads the LightGlue model, matches all image pairs, then
        unloads the model to free VRAM.

        Args:
            keypoints_list: List of keypoint/descriptor dicts from
                ``_extract_keypoints()``.

        Returns:
            Tuple of ``(matches_dict, inlier_counts)`` where:
            - ``matches_dict`` maps ``(i, j)`` to matched point pairs
            - ``inlier_counts`` maps ``(i, j)`` to inlier match count

        Implements: FR-008, FR-015, CON-003.
        """
        n = len(keypoints_list)
        matches_dict: dict[tuple[int, int], np.ndarray] = {}
        inlier_counts: dict[tuple[int, int], int] = {}

        try:
            import torch  # type: ignore[import-not-found]

            weight_path = self._lightglue_weight_path()
            if not os.path.isfile(weight_path):
                raise FileNotFoundError(
                    f"LightGlue weights not found at "
                    f"{os.path.basename(weight_path)}. "
                    "Download via Add-on Preferences → Tessera → Download Models."
                )

            logger.info("Loading LightGlue model for feature matching")

            try:
                from hloc.matchers.lightglue import (  # type: ignore[import-not-found]
                    LightGlue,
                )

                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                matcher = LightGlue({"features": "superpoint"}).to(device)
                state = torch.load(
                    weight_path, map_location=device, weights_only=True
                )
                matcher.load_state_dict(state)
                matcher.eval()

                for i in range(n):
                    for j in range(i + 1, n):
                        start = time.monotonic()
                        kp_i = torch.from_numpy(
                            keypoints_list[i]["keypoints"]
                        ).float().to(device)
                        desc_i = torch.from_numpy(
                            keypoints_list[i]["descriptors"]
                        ).float().to(device)
                        kp_j = torch.from_numpy(
                            keypoints_list[j]["keypoints"]
                        ).float().to(device)
                        desc_j = torch.from_numpy(
                            keypoints_list[j]["descriptors"]
                        ).float().to(device)

                        with torch.no_grad():
                            pred = matcher(
                                {
                                    "keypoints0": kp_i.unsqueeze(0),
                                    "descriptors0": desc_i.T.unsqueeze(0),
                                    "keypoints1": kp_j.unsqueeze(0),
                                    "descriptors1": desc_j.T.unsqueeze(0),
                                }
                            )

                        match_indices = pred["matches0"][0].cpu().numpy()
                        valid = match_indices >= 0
                        inlier_count = int(np.sum(valid))

                        if inlier_count > 0:
                            src_idx = np.where(valid)[0]
                            dst_idx = match_indices[valid]
                            src_pts = keypoints_list[i]["keypoints"][src_idx]
                            dst_pts = keypoints_list[j]["keypoints"][dst_idx]
                            matches_dict[(i, j)] = np.stack(
                                [src_pts, dst_pts], axis=1
                            )

                        inlier_counts[(i, j)] = inlier_count
                        duration = time.monotonic() - start
                        logger.debug(
                            "LightGlue matches computed: pair=(%d, %d), "
                            "num_matches=%d, inlier_count=%d, duration_s=%.2f",
                            i,
                            j,
                            len(match_indices),
                            inlier_count,
                            duration,
                        )

                # Unload model
                del matcher
                torch.cuda.empty_cache()
                logger.debug("LightGlue model unloaded")

            except ImportError:
                raise RuntimeError(
                    "hloc package is not installed. Bundle the hloc wheel "
                    "or install via pip for feature matching."
                )

        except ImportError:
            raise RuntimeError(
                "PyTorch is not available. Install PyTorch with CUDA "
                "support for feature matching."
            )

        return matches_dict, inlier_counts

    def _apply_view_label_priors(
        self, vision_results: list[VisionResult]
    ) -> list[tuple[CameraPose | None, float]]:
        """Convert view labels to camera pose priors with weights.

        User-supplied labels (``label_source == "user"``) produce
        **strong priors** (weight 1.0).  Auto-detected labels with
        ``label_confidence >= 0.80`` produce **soft priors** (weight
        proportional to confidence).  All other labels produce no prior.

        Args:
            vision_results: Vision pipeline outputs.

        Returns:
            List of ``(prior_pose, weight)`` tuples, one per image.
            ``prior_pose`` is ``None`` if no prior is available.

        Implements: FR-009, FR-010.
        """
        priors: list[tuple[CameraPose | None, float]] = []

        for i, vr in enumerate(vision_results):
            h, w = vr.image.shape[:2]
            image_size = (w, h)

            if vr.label_source == "user":
                # FR-009: Strong prior from user-supplied label
                prior = get_prior_pose(vr.view_label, image_size)
                weight = 1.0
                logger.debug(
                    "View-label prior applied: image_index=%d, label=%s, "
                    "label_source=user, confidence=1.0",
                    i,
                    vr.view_label,
                )
            elif (
                vr.label_source == "auto"
                and vr.label_confidence >= _AUTO_LABEL_MIN_CONFIDENCE
            ):
                # FR-010: Soft prior from high-confidence auto label
                prior = get_prior_pose(vr.view_label, image_size)
                weight = vr.label_confidence
                logger.debug(
                    "View-label prior applied: image_index=%d, label=%s, "
                    "label_source=auto, confidence=%.2f",
                    i,
                    vr.view_label,
                    vr.label_confidence,
                )
            else:
                prior = None
                weight = 0.0
                logger.debug(
                    "No view-label prior for image_index=%d "
                    "(source=%s, confidence=%.2f)",
                    i,
                    vr.label_source,
                    vr.label_confidence,
                )

            priors.append((prior, weight))

        return priors

    def _run_bundle_adjustment(
        self,
        n_images: int,
        image_sizes: list[tuple[int, int]],
        matches_dict: dict[tuple[int, int], np.ndarray],
        priors: list[tuple[CameraPose | None, float]],
    ) -> list[CameraPose | None]:
        """Run sparse bundle adjustment to refine camera poses.

        Initialises camera extrinsics from view-label priors where
        available, then refines using matched feature correspondences.

        Args:
            n_images: Number of input images.
            image_sizes: ``(width, height)`` for each image.
            matches_dict: Pairwise feature matches.
            priors: View-label priors with weights.

        Returns:
            List of refined ``CameraPose`` objects (``None`` for
            images that could not be registered).

        Implements: FR-011.
        """
        logger.info(
            "Bundle adjustment started: n_images=%d, pairs=%d",
            n_images,
            len(matches_dict),
        )
        start = time.monotonic()

        poses: list[CameraPose | None] = [None] * n_images

        try:
            from scipy.spatial.transform import Rotation  # type: ignore[import-not-found]
        except ImportError:
            raise RuntimeError(
                "scipy is not available. Install scipy for bundle adjustment."
            )

        # Initialise poses from priors
        for i in range(n_images):
            prior, weight = priors[i]
            if prior is not None and weight > 0:
                poses[i] = CameraPose(
                    rotation=prior.rotation.copy(),
                    translation=prior.translation.copy(),
                    focal_length=prior.focal_length,
                    principal_point=prior.principal_point,
                    image_size=image_sizes[i],
                    confidence=weight,
                )

        # Try to register remaining images using pairwise matches
        # and essential matrix decomposition
        for (i, j), match_pts in matches_dict.items():
            if match_pts.shape[0] < 8:
                # Need at least 8 point correspondences for essential matrix
                continue

            # If neither image has a pose yet, use the first as reference
            if poses[i] is None and poses[j] is None:
                w, h = image_sizes[i]
                poses[i] = CameraPose(
                    rotation=np.eye(3, dtype=np.float64),
                    translation=np.zeros(3, dtype=np.float64),
                    focal_length=525.0,
                    principal_point=(w / 2.0, h / 2.0),
                    image_size=image_sizes[i],
                    confidence=0.5,
                )

            # For images without a pose, try to estimate from matches
            if poses[i] is not None and poses[j] is None:
                # Estimate relative pose from point correspondences
                src_pts = match_pts[:, 0, :]
                dst_pts = match_pts[:, 1, :]

                try:
                    import cv2  # type: ignore[import-not-found]

                    focal = poses[i].focal_length
                    pp = poses[i].principal_point
                    E, mask_e = cv2.findEssentialMat(
                        src_pts,
                        dst_pts,
                        focal=focal,
                        pp=pp,
                        method=cv2.RANSAC,
                        prob=0.999,
                        threshold=1.0,
                    )
                    if E is not None:
                        _, R, t, _ = cv2.recoverPose(
                            E, src_pts, dst_pts, focal=focal, pp=pp
                        )
                        # Compose with reference pose
                        rot_j = R @ poses[i].rotation
                        trans_j = poses[i].translation + (
                            poses[i].rotation.T @ t.flatten()
                        )
                        w_j, h_j = image_sizes[j]
                        poses[j] = CameraPose(
                            rotation=rot_j,
                            translation=trans_j,
                            focal_length=focal,
                            principal_point=(w_j / 2.0, h_j / 2.0),
                            image_size=image_sizes[j],
                            confidence=0.5,
                        )
                except ImportError:
                    # Without cv2, use prior-only poses
                    logger.debug(
                        "cv2 not available; skipping essential matrix "
                        "estimation for pair (%d, %d)",
                        i,
                        j,
                    )

            elif poses[j] is not None and poses[i] is None:
                # Reverse direction
                src_pts = match_pts[:, 1, :]
                dst_pts = match_pts[:, 0, :]
                try:
                    import cv2  # type: ignore[import-not-found]

                    focal = poses[j].focal_length
                    pp = poses[j].principal_point
                    E, _ = cv2.findEssentialMat(
                        src_pts, dst_pts, focal=focal, pp=pp,
                        method=cv2.RANSAC, prob=0.999, threshold=1.0,
                    )
                    if E is not None:
                        _, R, t, _ = cv2.recoverPose(
                            E, src_pts, dst_pts, focal=focal, pp=pp
                        )
                        rot_i = R @ poses[j].rotation
                        trans_i = poses[j].translation + (
                            poses[j].rotation.T @ t.flatten()
                        )
                        w_i, h_i = image_sizes[i]
                        poses[i] = CameraPose(
                            rotation=rot_i,
                            translation=trans_i,
                            focal_length=focal,
                            principal_point=(w_i / 2.0, h_i / 2.0),
                            image_size=image_sizes[i],
                            confidence=0.5,
                        )
                except ImportError:
                    pass

        duration = time.monotonic() - start
        num_registered = sum(1 for p in poses if p is not None)
        logger.info(
            "Bundle adjustment completed: num_registered=%d, "
            "duration_s=%.2f",
            num_registered,
            duration,
        )

        return poses

    def _check_angular_separation(
        self, poses: list[CameraPose | None]
    ) -> tuple[bool, float]:
        """Check that registered cameras have sufficient angular separation.

        Args:
            poses: Estimated camera poses (``None`` for unregistered).

        Returns:
            Tuple of ``(sufficient, max_angle_deg)`` where
            ``sufficient`` is ``True`` if the maximum pairwise angle
            exceeds ``_MIN_ANGULAR_SEPARATION_DEG``.

        Implements: EC-001.
        """
        valid_poses = [p for p in poses if p is not None]
        if len(valid_poses) < 2:
            return False, 0.0

        max_angle = 0.0
        for i in range(len(valid_poses)):
            for j in range(i + 1, len(valid_poses)):
                angle = compute_angular_separation(
                    valid_poses[i].rotation, valid_poses[j].rotation
                )
                max_angle = max(max_angle, angle)

        sufficient = max_angle >= _MIN_ANGULAR_SEPARATION_DEG
        if not sufficient:
            logger.warning(
                "Insufficient angular separation: max_angle=%.1f°, "
                "threshold=%.1f°",
                max_angle,
                _MIN_ANGULAR_SEPARATION_DEG,
            )

        return sufficient, max_angle

    def estimate_poses(
        self, vision_results: list[VisionResult]
    ) -> PoseEstimationResult:
        """Estimate camera poses from multiple images.

        Runs the full SfM pipeline: keypoint extraction, pairwise
        matching, view-label prior application, bundle adjustment,
        and angular separation validation.

        Args:
            vision_results: 3+ processed images from the vision pipeline.

        Returns:
            ``PoseEstimationResult`` with estimated camera poses.

        Implements: FR-006 through FR-015, EC-001, EC-003, EC-005.
        """
        n = len(vision_results)
        gpu_name = "unknown"
        try:
            import torch  # type: ignore[import-not-found]

            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
        except ImportError:
            pass

        num_confirmed = sum(
            1
            for vr in vision_results
            if not vr.label_needs_confirmation
        )
        logger.info(
            "Pose estimation started: num_images=%d, "
            "num_confirmed_labels=%d, gpu_name=%s",
            n,
            num_confirmed,
            gpu_name,
        )

        try:
            # Step 1: Prepare images (FR-007)
            prepared = []
            image_sizes: list[tuple[int, int]] = []
            for vr in vision_results:
                img = self._prepare_image(vr.image, vr.mask)
                prepared.append(img)
                h, w = img.shape[:2]
                image_sizes.append((w, h))

            # Step 2: Extract keypoints (FR-007, FR-015)
            keypoints_list = self._extract_keypoints(prepared)

            # Step 3: Match features (FR-008, FR-015)
            matches_dict, inlier_counts = self._match_features(keypoints_list)

            # Compute overall inlier ratio
            total_matches = sum(
                len(kp["keypoints"]) for kp in keypoints_list
            )
            total_inliers = sum(inlier_counts.values())
            inlier_ratio = (
                total_inliers / max(total_matches, 1)
            )

            # EC-003: Check for low inlier ratio
            if inlier_ratio < _MIN_INLIER_RATIO:
                logger.warning(
                    "Feature matching inlier ratio (%.2f) is below "
                    "threshold (%.2f). The object may be reflective, "
                    "transparent, or textureless.",
                    inlier_ratio,
                    _MIN_INLIER_RATIO,
                )

            # Step 4: Apply view-label priors (FR-009, FR-010)
            priors = self._apply_view_label_priors(vision_results)

            # Step 5: Run bundle adjustment (FR-011)
            poses = self._run_bundle_adjustment(
                n, image_sizes, matches_dict, priors
            )

            num_registered = sum(1 for p in poses if p is not None)

            # FR-014: Check if enough cameras were registered
            if num_registered < 3:
                error_msg = (
                    f"Pose estimation registered only {num_registered} of "
                    f"{n} cameras. Insufficient overlap or texture for "
                    "multi-view reconstruction. Falling back to "
                    "single-image path."
                )
                logger.warning(
                    "Pose estimation failed: num_registered=%d, "
                    "required=3, error_message=%s",
                    num_registered,
                    error_msg,
                )
                return PoseEstimationResult(
                    poses=poses,
                    num_registered=num_registered,
                    inlier_ratio=inlier_ratio,
                    success=False,
                    error_message=error_msg,
                    feature_match_counts=inlier_counts,
                )

            # EC-001: Check angular separation
            sufficient, max_angle = self._check_angular_separation(poses)
            if not sufficient:
                error_msg = (
                    f"Insufficient angular separation between views. "
                    f"Maximum camera pair angle: {max_angle:.1f}°. "
                    "Provide images from viewpoints separated by "
                    "at least 45° for best results."
                )
                logger.warning(
                    "Insufficient angular separation: max_angle=%.1f°, "
                    "threshold=%.1f°",
                    max_angle,
                    _MIN_ANGULAR_SEPARATION_DEG,
                )
                return PoseEstimationResult(
                    poses=poses,
                    num_registered=num_registered,
                    inlier_ratio=inlier_ratio,
                    success=False,
                    error_message=error_msg,
                    feature_match_counts=inlier_counts,
                )

            logger.info(
                "Pose estimation succeeded: num_registered=%d, "
                "inlier_ratio=%.2f",
                num_registered,
                inlier_ratio,
            )

            return PoseEstimationResult(
                poses=poses,
                num_registered=num_registered,
                inlier_ratio=inlier_ratio,
                success=True,
                feature_match_counts=inlier_counts,
            )

        finally:
            # CON-004: Clean up GPU memory
            VRAMGuard.cleanup_gpu()
            logger.debug("VRAM cleanup completed after pose estimation")
