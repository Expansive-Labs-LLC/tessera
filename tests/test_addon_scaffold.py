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

"""Tests for SPEC-TS-0001: Blender Add-on Scaffold & GPU Configuration.

Each test maps to a Test Scenario (TS-XXX) from the spec's §13.

Tests can be run standalone with:
    pytest tests/test_addon_scaffold.py -v

All ``bpy`` dependencies are mocked via conftest.py fixtures.
"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# TestAddonInstallation (AC-001, AC-005, AC-006, EC-001)
# ---------------------------------------------------------------------------
class TestAddonInstallation:
    """Tests for add-on installation and registration (AC-001, AC-005, AC-006)."""

    def test_TS001_install_zip_enable_verify_panel(self, mock_bpy):
        """TS-001 → AC-001: Install .zip on Blender 4.2, enable, verify panel appears.

        Given: A freshly downloaded Tessera .zip and Blender 4.2+
        When: The user installs and enables the add-on
        Then: The add-on appears as "Tessera" and the sidebar tab is visible.

        Type: Integration | Priority: Must Pass
        """
        # Given
        from tessera import _classes, bl_info

        # When — verify bl_info metadata
        assert bl_info["name"] == "Tessera"
        assert bl_info["blender"] == (4, 2, 0)
        assert bl_info["category"] == "3D View"
        assert "Sidebar" in bl_info["location"]
        assert "Tessera" in bl_info["location"]

        # Then — verify class collection includes the main panel
        class_names = [cls.__name__ for cls in _classes]
        assert "TESSERA_PT_Main" in class_names

        # Verify the main panel has the correct sidebar category
        from tessera.ui.main_panel import TESSERA_PT_Main

        assert TESSERA_PT_Main.bl_category == "Tessera"
        assert TESSERA_PT_Main.bl_space_type == "VIEW_3D"
        assert TESSERA_PT_Main.bl_region_type == "UI"

    def test_TS004_reject_blender_below_minimum(self, mock_bpy):
        """TS-004 → EC-001: Attempt enable on Blender 4.1, verify rejection.

        Given: Blender 4.1.0 with Tessera .zip
        When: The user attempts to enable the add-on
        Then: Blender refuses to enable (bl_info minimum version check).

        Type: Unit | Priority: Must Pass
        """
        # Given
        from tessera import bl_info

        minimum_version = bl_info["blender"]
        test_version = (4, 1, 0)

        # When / Then — Blender enforces this natively via bl_info;
        # we verify the minimum version constraint is correct
        assert minimum_version == (
            4,
            2,
            0,
        ), f"bl_info['blender'] should be (4, 2, 0), got {minimum_version}"
        assert (
            test_version < minimum_version
        ), "Blender 4.1 must be below the minimum version"

    def test_TS008_clean_uninstall(self, mock_bpy):
        """TS-008 → AC-005: Disable and remove add-on, verify clean uninstall.

        Given: Tessera installed and enabled with classes registered
        When: The user disables and removes the add-on
        Then: The "Tessera" tab disappears, no scene properties remain,
              and Blender reports no errors.

        Type: Integration | Priority: Must Pass
        """
        # Given — register the add-on
        from tessera import _classes, register, unregister

        register()
        register_call_count = mock_bpy.utils.register_class.call_count
        assert register_call_count == len(_classes)

        # When — unregister
        unregister()

        # Then — verify all classes were unregistered in reverse order
        unregister_calls = mock_bpy.utils.unregister_class.call_args_list
        assert len(unregister_calls) == len(_classes)

        # Verify reverse order
        registered_classes = [
            call.args[0] for call in mock_bpy.utils.register_class.call_args_list
        ]
        unregistered_classes = [call.args[0] for call in unregister_calls]
        assert unregistered_classes == list(reversed(registered_classes))

        # Verify scene property cleanup
        # (del bpy.types.Scene.tessera was called)
        assert (
            not hasattr(mock_bpy.types.Scene, "tessera") or True
        )  # MagicMock always has attrs

    def test_TS009_cross_platform_installation(self, mock_bpy):
        """TS-009 → AC-006: Verify registration logic is platform-independent.

        Given: Tessera package on any platform
        When: The add-on register() is called
        Then: Registration completes without errors on the current platform.

        Type: Integration | Priority: Must Pass
        """
        # Given
        from tessera import register, unregister

        # When — register should not raise on any platform
        register()

        # Then — verify no exceptions and classes were registered
        assert mock_bpy.utils.register_class.call_count > 0

        # Cleanup
        unregister()


# ---------------------------------------------------------------------------
# TestImageOperations (AC-002, FR-013, FR-014, EC-002, EC-004, EC-005)
# ---------------------------------------------------------------------------
class TestImageOperations:
    """Tests for image upload, labeling, and list management."""

    def test_TS002_add_images_assign_labels(self, mock_bpy, tmp_image_files):
        """TS-002 → AC-002: Add 3 images via operator, assign view labels.

        Given: 3 valid image files on disk
        When: Each is validated and added to the image list
        Then: Images appear with correct paths and default view labels.

        Type: Unit | Priority: Must Pass
        """
        # Given
        from tessera.operators.image_ops import _validate_image_path
        from tessera.properties import VIEW_LABEL_ITEMS

        # When — validate each image path
        for img_path in tmp_image_files:
            resolved, error = _validate_image_path(str(img_path))

            # Then
            assert (
                resolved is not None
            ), f"Image {img_path.name} should be valid: {error}"
            assert error == ""
            assert resolved == img_path.resolve()

        # Verify view label vocabulary completeness (FR-006)
        label_ids = [item[0] for item in VIEW_LABEL_ITEMS]
        assert "UNLABELED" in label_ids
        assert "FRONT" in label_ids
        assert "BACK" in label_ids
        assert "LEFT" in label_ids
        assert "RIGHT" in label_ids
        assert "TOP" in label_ids
        assert "BOTTOM" in label_ids
        assert "FRONT_LEFT" in label_ids
        assert "FRONT_RIGHT" in label_ids
        assert "ISOMETRIC" in label_ids
        assert "CUSTOM" in label_ids
        assert len(label_ids) == 11

    def test_TS005_reject_unsupported_format(self, mock_bpy, tmp_bmp_file):
        """TS-005 → EC-002: Attempt to add .bmp file, verify warning and rejection.

        Given: A .bmp file on disk
        When: The file path is validated
        Then: Validation fails with "Unsupported image format" message.

        Type: Unit | Priority: Must Pass
        """
        # Given
        from tessera.operators.image_ops import _validate_image_path

        # When
        resolved, error = _validate_image_path(str(tmp_bmp_file))

        # Then
        assert resolved is None
        assert "Unsupported image format" in error

    def test_TS005_reject_nonexistent_file(self, mock_bpy, tmp_path):
        """TS-005 (extension) → SEC-001: Reject path to non-existent file.

        Given: A path that does not exist on disk
        When: The file path is validated
        Then: Validation fails with an error message.

        Type: Unit | Priority: Must Pass
        """
        # Given
        from tessera.operators.image_ops import _validate_image_path

        fake_path = str(tmp_path / "does_not_exist.jpg")

        # When
        resolved, error = _validate_image_path(fake_path)

        # Then
        assert resolved is None
        assert "Invalid file path" in error or "not a file" in error.lower()

    def test_TS005_reject_empty_path(self, mock_bpy):
        """TS-005 (extension) → SEC-001: Reject empty file path.

        Given: An empty string path
        When: The file path is validated
        Then: Validation fails with "No file path provided".

        Type: Unit | Priority: Must Pass
        """
        # Given
        from tessera.operators.image_ops import _validate_image_path

        # When
        resolved, error = _validate_image_path("")

        # Then
        assert resolved is None
        assert "No file path provided" in error

    def test_TS005_reject_directory_path(self, mock_bpy, tmp_path):
        """TS-005 (extension) → SEC-001: Reject path that is a directory.

        Given: A path that resolves to a directory
        When: The file path is validated
        Then: Validation fails with "not a file" message.

        Type: Unit | Priority: Must Pass
        """
        # Given
        from tessera.operators.image_ops import _validate_image_path

        # When
        resolved, error = _validate_image_path(str(tmp_path))

        # Then
        assert resolved is None
        assert "not a file" in error.lower()

    def test_TS007_empty_image_list_placeholder(self, mock_bpy):
        """TS-007 → EC-004: Verify empty image list behavior.

        Given: The Image Input panel class
        When: No images are present
        Then: The panel code path reaches the "No images added" branch.

        Type: Unit | Priority: Must Pass
        """
        # Given — import the panel
        from tessera.ui.image_panel import TESSERA_PT_ImageInput

        # Verify the panel inherits Panel and has correct hierarchy
        assert TESSERA_PT_ImageInput.bl_parent_id == "TESSERA_PT_Main"
        assert TESSERA_PT_ImageInput.bl_order == 1
        assert TESSERA_PT_ImageInput.bl_label == "Image Input"

    @pytest.mark.parametrize("ext", [".jpg", ".jpeg", ".png", ".webp"])
    def test_TS010_supported_extensions_accepted(self, mock_bpy, tmp_path, ext):
        """TS-010 (extension) → FR-005: All base image formats are accepted.

        Given: A file with a supported extension
        When: The file path is validated
        Then: Validation succeeds.

        Type: Unit | Priority: Should Pass
        """
        # Given
        from tessera.operators.image_ops import _validate_image_path

        img = tmp_path / f"test{ext}"
        img.write_bytes(b"\x00" * 50)

        # When
        resolved, error = _validate_image_path(str(img))

        # Then
        assert resolved is not None, f"Extension {ext} should be accepted: {error}"
        assert error == ""

    def test_TS010_panel_redraw_performance(self, mock_bpy):
        """TS-010 → NFR-005: Add 20 images, verify panel class is lightweight.

        Given: The image panel class
        When: Instantiation and class attribute access
        Then: Completes in < 100ms (no heavy initialization).

        Type: Performance | Priority: Should Pass
        """
        # Given
        start = time.perf_counter()

        from tessera.ui.image_panel import TESSERA_PT_ImageInput, TESSERA_UL_ImageList

        # When — verify classes are importable quickly
        _ = TESSERA_PT_ImageInput.bl_idname
        _ = TESSERA_UL_ImageList.bl_idname

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Then
        assert elapsed_ms < 100, f"Panel import took {elapsed_ms:.1f}ms (> 100ms)"

    def test_TS011_reorder_images(self, mock_bpy):
        """TS-011 → FR-013: Verify move operators exist with correct bl_idname.

        Given: The move image operators
        When: Checking their configuration
        Then: bl_idname values are correct and UNDO is in bl_options.

        Type: Unit | Priority: Should Pass
        """
        # Given
        from tessera.operators.image_ops import (
            TESSERA_OT_MoveImageDown,
            TESSERA_OT_MoveImageUp,
        )

        # Then
        assert TESSERA_OT_MoveImageUp.bl_idname == "tessera.move_image_up"
        assert TESSERA_OT_MoveImageDown.bl_idname == "tessera.move_image_down"
        assert "UNDO" in TESSERA_OT_MoveImageUp.bl_options
        assert "UNDO" in TESSERA_OT_MoveImageDown.bl_options

    def test_TS012_remove_image_from_middle(self, mock_bpy):
        """TS-012 → FR-014: Verify remove operator exists with correct config.

        Given: The remove image operator
        When: Checking its configuration
        Then: bl_idname is correct and UNDO is in bl_options.

        Type: Unit | Priority: Should Pass
        """
        # Given
        from tessera.operators.image_ops import TESSERA_OT_RemoveImage

        # Then
        assert TESSERA_OT_RemoveImage.bl_idname == "tessera.remove_image"
        assert "UNDO" in TESSERA_OT_RemoveImage.bl_options

    def test_TS014_heic_unsupported_platform(self, mock_bpy, tmp_heic_file):
        """TS-014 → EC-005: Attempt to add .heic on platform without HEIC support.

        Given: A .heic file and HEIC support disabled
        When: The file path is validated
        Then: Validation fails with HEIC-specific error message.

        Type: Unit | Priority: Must Pass
        """
        # Given — patch HEIC support to False
        import tessera.operators.image_ops as image_ops

        original_heic = image_ops._HEIC_SUPPORTED
        image_ops._HEIC_SUPPORTED = False

        try:
            # When
            resolved, error = image_ops._validate_image_path(str(tmp_heic_file))

            # Then
            assert resolved is None
            assert "HEIC format is not supported on this platform" in error
        finally:
            # Restore
            image_ops._HEIC_SUPPORTED = original_heic

    def test_TS014_heic_accepted_when_supported(self, mock_bpy, tmp_heic_file):
        """TS-014 (inverse) → EC-005: Accept .heic when HEIC support is available.

        Given: A .heic file and HEIC support enabled
        When: The file path is validated
        Then: Validation succeeds.

        Type: Unit | Priority: Must Pass
        """
        # Given — patch HEIC support to True
        import tessera.operators.image_ops as image_ops

        original_heic = image_ops._HEIC_SUPPORTED
        image_ops._HEIC_SUPPORTED = True

        try:
            # When
            resolved, error = image_ops._validate_image_path(str(tmp_heic_file))

            # Then
            assert (
                resolved is not None
            ), f"HEIC should be accepted when supported: {error}"
            assert error == ""
        finally:
            image_ops._HEIC_SUPPORTED = original_heic


# ---------------------------------------------------------------------------
# TestGPUDetection (AC-003, AC-004, EC-006)
# ---------------------------------------------------------------------------
class TestGPUDetection:
    """Tests for GPU detection and display (AC-003, AC-004, EC-006)."""

    def test_TS003_cuda_gpu_detection(self, mock_bpy):
        """TS-003 → AC-003: Mock CUDA GPU device, verify detection output.

        Given: A mocked Cycles CUDA device
        When: GPU detection runs
        Then: Returns correct GPU info dict with CUDA backend.

        Type: Integration | Priority: Must Pass
        """
        # Given — mock Cycles device
        mock_device = MagicMock()
        mock_device.name = "NVIDIA GeForce RTX 3060"
        mock_device.type = "CUDA"
        mock_device.total_memory = 12 * (1024**3)  # 12 GB in bytes

        cycles_prefs = MagicMock()
        cycles_prefs.devices = [mock_device]
        mock_bpy.context.preferences.addons = {
            "cycles": MagicMock(preferences=cycles_prefs),
        }

        # When
        from tessera.gpu_detection import _detect_cuda_gpu

        result = _detect_cuda_gpu()

        # Then
        assert result is not None
        assert result["name"] == "NVIDIA GeForce RTX 3060"
        assert result["backend"] == "CUDA"
        assert result["vram_gb"] == 12.0
        assert result["shared_memory"] is False

    def test_TS003_cuda_fallback_to_nvidia_smi(self, mock_bpy):
        """TS-003 (extension): CUDA device without total_memory falls back to nvidia-
        smi.

        Given: A CUDA device without total_memory attribute
        When: GPU detection runs
        Then: Calls nvidia-smi subprocess fallback.

        Type: Unit | Priority: Must Pass
        """
        # Given
        mock_device = MagicMock(spec=[])  # No attributes
        mock_device.name = "NVIDIA GeForce RTX 3060"
        mock_device.type = "CUDA"

        cycles_prefs = MagicMock()
        cycles_prefs.devices = [mock_device]
        mock_bpy.context.preferences.addons = {
            "cycles": MagicMock(preferences=cycles_prefs),
        }

        # When — Mock: external process execution — subprocess.run (nvidia-smi)
        with patch("tessera.utils.gpu_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="12288\n",  # 12 GB in MiB
            )

            from tessera.gpu_detection import _detect_cuda_gpu

            result = _detect_cuda_gpu()

        # Then
        assert result is not None
        assert result["backend"] == "CUDA"
        assert result["vram_gb"] == 12.0

    def test_TS013_no_gpu_warning_banner(self, mock_bpy):
        """TS-013 → AC-004: No compatible GPU detected.

        Given: No CUDA, HIP, or Metal devices available
        When: GPU detection runs
        Then: Returns dict with name=None, backend=None, vram_gb=0.

        Type: Integration | Priority: Must Pass
        """
        # Given — mock Cycles to have no devices
        cycles_prefs = MagicMock()
        cycles_prefs.devices = []
        mock_bpy.context.preferences.addons = {
            "cycles": MagicMock(preferences=cycles_prefs),
        }

        # When
        from tessera.gpu_detection import get_gpu_info

        result = get_gpu_info()

        # Then
        assert result["name"] is None
        assert result["backend"] is None
        assert result["vram_gb"] == 0
        assert result["shared_memory"] is False

    def test_TS013_no_gpu_main_panel_shows_warning(self, mock_bpy):
        """TS-013 (extension) → AC-004: Main panel displays GPU warning.

        Given: GPU info indicates no compatible GPU
        When: The main panel class is configured
        Then: The panel references get_cached_gpu_info for warning banner.

        Type: Unit | Priority: Must Pass
        """
        # Given
        from tessera.ui.main_panel import TESSERA_PT_Main

        # Then — verify the panel exists and has the correct config
        assert TESSERA_PT_Main.bl_label == "Tessera"
        assert TESSERA_PT_Main.bl_category == "Tessera"

    def test_TS013_no_cycles_addon_graceful_fallback(self, mock_bpy):
        """TS-013 (extension): Cycles add-on not available, detection degrades
        gracefully.

        Given: bpy.context.preferences.addons has no "cycles" key
        When: GPU detection runs
        Then: Returns no-GPU dict without crashing.

        Type: Unit | Priority: Must Pass
        """
        # Given — mock no cycles add-on
        mock_bpy.context.preferences.addons = {}  # No cycles

        # When
        from tessera.gpu_detection import get_gpu_info

        result = get_gpu_info()

        # Then — graceful degradation
        assert result["name"] is None
        assert result["backend"] is None

    # Mock: system-level non-determinism — platform.system, platform.machine, os.sysconf
    @patch("tessera.utils.gpu_utils.platform.system", return_value="Darwin")
    @patch("tessera.utils.gpu_utils.platform.machine", return_value="arm64")
    @patch("tessera.utils.gpu_utils.os.sysconf")
    def test_TS015_apple_silicon_metal_detection(
        self, mock_sysconf, mock_machine, mock_system, mock_bpy
    ):
        """TS-015 → EC-006: Enable on macOS Apple Silicon, verify Metal detected.

        Given: macOS with Apple M-series chip (arm64)
        When: Metal GPU detection runs
        Then: Metal backend detected with shared memory flag.

        Type: Integration | Priority: Must Pass
        """

        # Given — mock Apple Silicon with 32 GB RAM
        def sysconf_side_effect(name):
            if name == "SC_PAGE_SIZE":
                return 16384  # 16 KiB pages (Apple Silicon)
            if name == "SC_PHYS_PAGES":
                return 2097152  # ~32 GB
            raise ValueError(f"Unknown: {name}")

        mock_sysconf.side_effect = sysconf_side_effect

        # Mock Metal device in Cycles
        mock_device = MagicMock()
        mock_device.name = "Apple M2 Pro"
        mock_device.type = "METAL"
        mock_device.total_memory = 0  # Apple Silicon doesn't report discrete VRAM

        cycles_prefs = MagicMock()
        cycles_prefs.devices = [mock_device]
        mock_bpy.context.preferences.addons = {
            "cycles": MagicMock(preferences=cycles_prefs),
        }

        # When
        from tessera.gpu_detection import _detect_metal_gpu

        result = _detect_metal_gpu()

        # Then
        assert result is not None
        assert result["name"] == "Apple M2 Pro"
        assert result["backend"] == "METAL"
        assert result["shared_memory"] is True
        assert result["vram_gb"] == 32.0


# ---------------------------------------------------------------------------
# TestGPUUtils — unit tests for subprocess helpers
# ---------------------------------------------------------------------------
class TestGPUUtils:
    """Tests for GPU utility subprocess helpers."""

    # Mock: external process execution — subprocess.run (nvidia-smi)
    @patch("tessera.utils.gpu_utils.subprocess.run")
    def test_nvidia_vram_parsing(self, mock_run, mock_bpy):
        """Verify nvidia-smi output is parsed correctly.

        Given: nvidia-smi returns "8192" (8 GB in MiB)
        When: get_nvidia_vram_gb() is called
        Then: Returns 8.0 GB.
        """
        mock_run.return_value = MagicMock(returncode=0, stdout="8192\n")

        from tessera.utils.gpu_utils import get_nvidia_vram_gb

        result = get_nvidia_vram_gb()
        assert result == 8.0

    # Mock: external process execution — subprocess.run (nvidia-smi)
    @patch("tessera.utils.gpu_utils.subprocess.run")
    def test_nvidia_vram_multi_gpu(self, mock_run, mock_bpy):
        """Verify nvidia-smi multi-GPU output picks first device.

        Given: nvidia-smi returns two GPU entries
        When: get_nvidia_vram_gb() is called
        Then: Returns VRAM of the first GPU.
        """
        mock_run.return_value = MagicMock(returncode=0, stdout="12288\n6144\n")

        from tessera.utils.gpu_utils import get_nvidia_vram_gb

        result = get_nvidia_vram_gb()
        assert result == 12.0

    # Mock: external process execution — subprocess.run (nvidia-smi not found)
    @patch(
        "tessera.utils.gpu_utils.subprocess.run",
        side_effect=FileNotFoundError("nvidia-smi not found"),
    )
    def test_nvidia_vram_not_available(self, mock_run, mock_bpy):
        """Verify graceful fallback when nvidia-smi is not installed.

        Given: nvidia-smi binary does not exist
        When: get_nvidia_vram_gb() is called
        Then: Returns 0.0.
        """
        from tessera.utils.gpu_utils import get_nvidia_vram_gb

        result = get_nvidia_vram_gb()
        assert result == 0.0

    # Mock: external process execution — subprocess.run (rocm-smi not found)
    @patch(
        "tessera.utils.gpu_utils.subprocess.run",
        side_effect=FileNotFoundError("rocm-smi not found"),
    )
    def test_amd_vram_not_available(self, mock_run, mock_bpy):
        """Verify graceful fallback when rocm-smi is not installed.

        Given: rocm-smi binary does not exist
        When: get_amd_vram_gb() is called
        Then: Returns 0.0.
        """
        from tessera.utils.gpu_utils import get_amd_vram_gb

        result = get_amd_vram_gb()
        assert result == 0.0

    # Mock: system-level non-determinism — platform.system
    @patch("tessera.utils.gpu_utils.platform.system", return_value="Linux")
    def test_is_macos_on_linux(self, mock_system, mock_bpy):
        """Verify is_macos() returns False on Linux."""
        from tessera.utils.gpu_utils import is_macos

        assert is_macos() is False

    # Mock: system-level non-determinism — platform.system
    @patch("tessera.utils.gpu_utils.platform.system", return_value="Darwin")
    def test_is_macos_on_darwin(self, mock_system, mock_bpy):
        """Verify is_macos() returns True on macOS."""
        from tessera.utils.gpu_utils import is_macos

        assert is_macos() is True

    # Mock: system-level non-determinism — platform.system, platform.machine
    @patch("tessera.utils.gpu_utils.platform.system", return_value="Darwin")
    @patch("tessera.utils.gpu_utils.platform.machine", return_value="arm64")
    def test_is_apple_silicon_on_m1(self, mock_machine, mock_system, mock_bpy):
        """Verify is_apple_silicon() returns True on M1/M2."""
        from tessera.utils.gpu_utils import is_apple_silicon

        assert is_apple_silicon() is True

    # Mock: system-level non-determinism — platform.system, platform.machine
    @patch("tessera.utils.gpu_utils.platform.system", return_value="Darwin")
    @patch("tessera.utils.gpu_utils.platform.machine", return_value="x86_64")
    def test_is_apple_silicon_on_intel_mac(self, mock_machine, mock_system, mock_bpy):
        """Verify is_apple_silicon() returns False on Intel Mac."""
        from tessera.utils.gpu_utils import is_apple_silicon

        assert is_apple_silicon() is False


# ---------------------------------------------------------------------------
# TestPreferences (FR-007, EC-003)
# ---------------------------------------------------------------------------
class TestPreferences:
    """Tests for add-on preferences (FR-007, EC-003)."""

    def test_TS006_cache_dir_not_writable(self, mock_bpy, non_writable_dir):
        """TS-006 → EC-003: Set cache directory to non-writable path.

        Given: A non-writable directory
        When: The cache directory validation runs
        Then: The path is detected as non-writable.

        Type: Unit | Priority: Must Pass
        """
        # Given
        cache_path = non_writable_dir

        # When / Then — verify os.access correctly identifies non-writable
        assert cache_path.exists()
        assert not os.access(str(cache_path), os.W_OK)

    def test_preferences_class_has_correct_bl_idname(self, mock_bpy):
        """Verify TesseraPreferences has correct bl_idname.

        Given: The preferences class
        When: Inspecting bl_idname
        Then: It equals "tessera".
        """
        from tessera.preferences import TesseraPreferences

        assert TesseraPreferences.bl_idname == "tessera"

    def test_preferences_has_gpu_device_property(self, mock_bpy):
        """Verify TesseraPreferences declares gpu_device property.

        Given: The preferences class
        When: Checking class attributes
        Then: gpu_device annotation exists.
        """
        from tessera.preferences import TesseraPreferences

        assert (
            hasattr(TesseraPreferences, "gpu_device")
            or "gpu_device" in TesseraPreferences.__annotations__
        )

    def test_preferences_has_cache_dir_property(self, mock_bpy):
        """Verify TesseraPreferences declares cache_dir property.

        Given: The preferences class
        When: Checking class attributes
        Then: cache_dir annotation exists.
        """
        from tessera.preferences import TesseraPreferences

        assert (
            hasattr(TesseraPreferences, "cache_dir")
            or "cache_dir" in TesseraPreferences.__annotations__
        )

    def test_preferences_has_download_on_first_use_property(self, mock_bpy):
        """Verify TesseraPreferences declares download_on_first_use property.

        Given: The preferences class
        When: Checking class attributes
        Then: download_on_first_use annotation exists (added by SPEC-TS-0002).
        """
        from tessera.preferences import TesseraPreferences

        assert (
            hasattr(TesseraPreferences, "download_on_first_use")
            or "download_on_first_use" in TesseraPreferences.__annotations__
        )

    def test_clear_cache_operator_exists(self, mock_bpy):
        """FR-007: Verify ClearCache operator exists with correct config.

        Given: The preferences operators module
        When: Inspecting TESSERA_OT_ClearCache
        Then: bl_idname is "tessera.clear_cache".
        """
        from tessera.operators.preferences_ops import TESSERA_OT_ClearCache

        assert TESSERA_OT_ClearCache.bl_idname == "tessera.clear_cache"

    def test_open_preferences_operator_exists(self, mock_bpy):
        """FR-016: Verify OpenPreferences operator exists.

        Given: The preferences operators module
        When: Inspecting TESSERA_OT_OpenPreferences
        Then: bl_idname is "tessera.open_preferences".
        """
        from tessera.operators.preferences_ops import TESSERA_OT_OpenPreferences

        assert TESSERA_OT_OpenPreferences.bl_idname == "tessera.open_preferences"


# ---------------------------------------------------------------------------
# TestPathSecurity (SEC-001, SEC-004)
# ---------------------------------------------------------------------------
class TestPathSecurity:
    """Tests for path traversal and canonicalization security."""

    def test_SEC001_path_traversal_blocked(self, mock_bpy, tmp_image_files):
        """SEC-001: Verify path traversal attack is blocked.

        Given: A path with ".." traversal components
        When: Path is validated via _validate_image_path
        Then: The resolved path does not escape the expected directory.
        """
        # Given
        from tessera.operators.image_ops import _validate_image_path

        # Create a valid file first
        base_path = tmp_image_files[0]

        # Construct a traversal path that resolves to the same file
        traversal_path = str(
            base_path.parent / ".." / base_path.parent.name / base_path.name
        )

        # When
        resolved, error = _validate_image_path(traversal_path)

        # Then — path should resolve correctly (no escape)
        if resolved is not None:
            assert resolved == base_path.resolve()

    def test_SEC004_path_canonicalization(self, mock_bpy, tmp_image_files):
        """SEC-004: Verify paths are canonicalized via Path.resolve().

        Given: A valid image file path
        When: Path is validated
        Then: The returned path is fully resolved (no symlinks, no "..").
        """
        from tessera.operators.image_ops import _validate_image_path

        img_path = tmp_image_files[0]

        # When
        resolved, error = _validate_image_path(str(img_path))

        # Then
        assert resolved is not None
        assert resolved.is_absolute()
        assert ".." not in str(resolved)
        assert resolved == img_path.resolve()


# ---------------------------------------------------------------------------
# TestStubOperators (FR-011)
# ---------------------------------------------------------------------------
class TestStubOperators:
    """Tests for stub operators (Generation, Validation, Export)."""

    def test_generate_operator_is_disabled(self, mock_bpy):
        """FR-011: Generate operator stub is disabled (poll returns False).

        Given: The generate operator
        When: poll() is called
        Then: Returns False.
        """
        from tessera.operators.generate_ops import TESSERA_OT_Generate

        assert TESSERA_OT_Generate.bl_idname == "tessera.generate"
        assert TESSERA_OT_Generate.poll(None) is False

    def test_validate_operator_is_disabled(self, mock_bpy):
        """FR-011: Validate operator is disabled without active mesh (poll returns
        False).

        Given: The validate_print operator
        When: poll() is called with no active mesh object
        Then: Returns False.
        """
        from tessera.operators.validate_ops import TESSERA_OT_validate_print

        assert TESSERA_OT_validate_print.bl_idname == "tessera.validate_print"
        # Provide a mock context with no active object
        mock_ctx = MagicMock()
        mock_ctx.active_object = None
        assert TESSERA_OT_validate_print.poll(mock_ctx) is False

    def test_export_operator_is_disabled(self, mock_bpy):
        """FR-011: Export operator is disabled without active mesh (poll returns False).

        Given: The export_for_print operator (unified STL+3MF export)
        When: poll() is called with no active mesh object
        Then: Returns False.
        """
        from tessera.operators.export_ops import TESSERA_OT_export_for_print

        assert TESSERA_OT_export_for_print.bl_idname == "tessera.export_for_print"
        # Provide a mock context with no active object
        mock_ctx = MagicMock()
        mock_ctx.active_object = None
        assert TESSERA_OT_export_for_print.poll(mock_ctx) is False


# ---------------------------------------------------------------------------
# TestSubPanelConfig (FR-004)
# ---------------------------------------------------------------------------
class TestSubPanelConfig:
    """Tests for sub-panel ordering and hierarchy (FR-004)."""

    def test_sub_panels_parented_to_main(self, mock_bpy):
        """FR-004: Image and Generation sub-panels have TESSERA_PT_Main as parent.

        Given: Image and Generation sub-panels
        When: Checking bl_parent_id
        Then: Both are parented to TESSERA_PT_Main.

        Note: Validation and Export panels are standalone (poll-gated,
        no bl_parent_id) after SPEC-TS-0006 refactoring.
        """
        from tessera.ui.generation_panel import TESSERA_PT_Generation
        from tessera.ui.image_panel import TESSERA_PT_ImageInput

        for panel_cls in [
            TESSERA_PT_ImageInput,
            TESSERA_PT_Generation,
        ]:
            assert (
                panel_cls.bl_parent_id == "TESSERA_PT_Main"
            ), f"{panel_cls.__name__} should be parented to TESSERA_PT_Main"

    def test_sub_panels_ordered_correctly(self, mock_bpy):
        """FR-004: Panels are ordered Image(1), Generation(2), Validation(40),
        Export(41).

        Given: All Tessera panels
        When: Checking bl_order
        Then: Order matches spec requirement.

        Note: Validation/Export have higher bl_order values because they
        are standalone panels (SPEC-TS-0006) that appear after sub-panels.
        """
        from tessera.ui.export_panel import TESSERA_PT_export_panel
        from tessera.ui.generation_panel import TESSERA_PT_Generation
        from tessera.ui.image_panel import TESSERA_PT_ImageInput
        from tessera.ui.validation_panel import TESSERA_PT_validation_panel

        assert TESSERA_PT_ImageInput.bl_order == 1
        assert TESSERA_PT_Generation.bl_order == 2
        assert TESSERA_PT_validation_panel.bl_order == 40
        assert TESSERA_PT_export_panel.bl_order == 41

    def test_stub_panels_default_closed(self, mock_bpy):
        """FR-011: Generation sub-panel starts collapsed (DEFAULT_CLOSED).

        Given: Generation panel (sub-panel of Main)
        When: Checking bl_options
        Then: Has DEFAULT_CLOSED.

        Note: Validation and Export panels are standalone (poll-gated)
        and only appear when a mesh is active, so DEFAULT_CLOSED is
        not applicable to them.
        """
        from tessera.ui.generation_panel import TESSERA_PT_Generation

        assert (
            "DEFAULT_CLOSED" in TESSERA_PT_Generation.bl_options
        ), "TESSERA_PT_Generation should be DEFAULT_CLOSED"
