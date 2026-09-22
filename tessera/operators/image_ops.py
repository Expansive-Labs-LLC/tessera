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

"""Image operators for Tessera.

Provides operators for adding, removing, and reordering reference images
in the Tessera image list.

Implements: FR-005, FR-006, FR-013, FR-014, EC-002, EC-005,
            SEC-001, SEC-004.
"""

import logging
import os
import sys
from pathlib import Path

from bpy.props import StringProperty
from bpy.types import Operator

logger = logging.getLogger("tessera")

# Supported image extensions (always available)
_BASE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
# HEIC support flag — determined at runtime
_HEIC_SUPPORTED = False


def _check_heic_support():
    """Check if HEIC decoding is available on this platform.

    HEIC is supported on macOS natively, or when ``pillow-heif`` is
    available as a bundled dependency.

    Returns:
        bool: True if HEIC image decoding is available.
    """
    # macOS has native HEIC support via ImageIO
    if sys.platform == "darwin":
        return True

    # Check for pillow-heif availability
    try:
        import pillow_heif  # noqa: F401

        return True
    except ImportError:
        return False


# Initialize HEIC support on module load
_HEIC_SUPPORTED = _check_heic_support()


def _get_supported_extensions():
    """Get the set of supported image file extensions.

    Returns:
        set[str]: Supported extensions including ``.heic`` if available.
    """
    extensions = set(_BASE_IMAGE_EXTENSIONS)
    if _HEIC_SUPPORTED:
        extensions.add(".heic")
    return extensions


def _build_file_filter():
    """Build the file filter string for the file browser.

    Returns:
        str: Semicolon-separated filter string for Blender's file browser.
    """
    extensions = _get_supported_extensions()
    return ";".join(f"*{ext}" for ext in sorted(extensions))


def _validate_image_path(filepath):
    """Validate and canonicalize an image file path.

    Applies SEC-001 (path traversal validation) and SEC-004 (path
    canonicalization via ``pathlib.Path.resolve()``).

    Args:
        filepath: Raw file path string from user input.

    Returns:
        tuple[Path | None, str]: (resolved_path, error_message).
            resolved_path is None if validation fails.
    """
    if not filepath:
        return None, "No file path provided."

    try:
        resolved = Path(filepath).resolve(strict=True)
    except (OSError, RuntimeError) as e:
        return None, f"Invalid file path: {e}"

    # SEC-001: Verify the resolved path is a regular file
    if not resolved.is_file():
        return None, f"Path is not a file: {resolved}"

    # Check extension
    ext = resolved.suffix.lower()
    supported = _get_supported_extensions()
    if ext not in supported:
        # EC-005: HEIC on unsupported platform
        if ext == ".heic" and not _HEIC_SUPPORTED:
            return None, (
                "HEIC format is not supported on this platform. "
                "Please convert to JPG, PNG, or WebP."
            )
        # EC-002: Unsupported format
        return None, "Unsupported image format. Please use JPG, PNG, WebP, or HEIC."

    return resolved, ""


class TESSERA_OT_AddImage(Operator):
    """Add a reference image to the Tessera image list.

    Opens a file browser dialog filtered to supported image formats.
    Validates the selected file and adds it to the scene's image list.

    Implements: FR-005, EC-002, EC-005, SEC-001, SEC-004.
    """

    bl_idname = "tessera.add_image"
    bl_label = "Add Image"
    bl_description = "Add a reference image to the list"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(
        name="File Path",
        description="Path to the image file",
        subtype="FILE_PATH",
    )  # type: ignore[assignment]

    # File browser filter
    filter_glob: StringProperty(
        default="*.jpg;*.jpeg;*.png;*.webp",
        options={"HIDDEN"},
    )  # type: ignore[assignment]

    def invoke(self, context, event):
        """Open the file browser dialog."""
        # Dynamically set filter based on HEIC support
        if _HEIC_SUPPORTED:
            self.filter_glob = "*.jpg;*.jpeg;*.png;*.webp;*.heic"
        else:
            self.filter_glob = "*.jpg;*.jpeg;*.png;*.webp"

        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        """Validate and add the selected image file."""
        resolved_path, error = _validate_image_path(self.filepath)

        if resolved_path is None:
            self.report({"WARNING"}, error)
            logger.warning(
                "Image rejected: %s (ext: %s)",
                os.path.basename(self.filepath),
                Path(self.filepath).suffix.lower() if self.filepath else "none",
            )
            return {"CANCELLED"}

        # Add to scene image list (FR-012)
        props = context.scene.tessera
        item = props.images.add()
        item.filepath = str(resolved_path)
        item.name = resolved_path.name
        item.view_label = "UNLABELED"

        # Set as active
        props.active_image_index = len(props.images) - 1

        logger.debug(
            "Image added: %s (label: %s)",
            resolved_path.name,
            item.view_label,
        )
        return {"FINISHED"}


class TESSERA_OT_RemoveImage(Operator):
    """Remove the selected image from the Tessera image list.

    Implements: FR-014.
    """

    bl_idname = "tessera.remove_image"
    bl_label = "Remove Image"
    bl_description = "Remove the selected image from the list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """Remove the currently selected image."""
        props = context.scene.tessera
        index = props.active_image_index

        if index < 0 or index >= len(props.images):
            self.report({"WARNING"}, "No image selected.")
            return {"CANCELLED"}

        # Log before removal (basename only per §11.1)
        removed_name = props.images[index].name
        logger.debug("Image removed: %s", removed_name)

        props.images.remove(index)

        # Adjust active index
        props.active_image_index = min(max(0, index - 1), max(0, len(props.images) - 1))
        return {"FINISHED"}


class TESSERA_OT_MoveImageUp(Operator):
    """Move the selected image up in the list.

    Implements: FR-013.
    """

    bl_idname = "tessera.move_image_up"
    bl_label = "Move Image Up"
    bl_description = "Move the selected image up in the list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """Swap the selected image with the one above it."""
        props = context.scene.tessera
        index = props.active_image_index

        if index <= 0:
            return {"CANCELLED"}

        props.images.move(index, index - 1)
        props.active_image_index = index - 1
        return {"FINISHED"}


class TESSERA_OT_MoveImageDown(Operator):
    """Move the selected image down in the list.

    Implements: FR-013.
    """

    bl_idname = "tessera.move_image_down"
    bl_label = "Move Image Down"
    bl_description = "Move the selected image down in the list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """Swap the selected image with the one below it."""
        props = context.scene.tessera
        index = props.active_image_index

        if index >= len(props.images) - 1:
            return {"CANCELLED"}

        props.images.move(index, index + 1)
        props.active_image_index = index + 1
        return {"FINISHED"}


# Classes to register
classes = [
    TESSERA_OT_AddImage,
    TESSERA_OT_RemoveImage,
    TESSERA_OT_MoveImageUp,
    TESSERA_OT_MoveImageDown,
]
