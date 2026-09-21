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

"""Error catalog mapping 16 error codes to structured entries.

Each entry contains a user-facing message, severity, category,
and concrete resolution steps.

Spec: SPEC-TS-0011 (Production Hardening, Testing & Documentation)

Implements: FR-002, FR-003.
"""

from __future__ import annotations

from .categories import ErrorCatalogEntry, ErrorCategory, ErrorSeverity

# FR-003: 16 mandatory error scenarios + BF-E999 fallback.
ERROR_CATALOG: dict[str, ErrorCatalogEntry] = {
    # --- VRAM Errors ---
    "BF-E001": ErrorCatalogEntry(
        code="BF-E001",
        message=(
            "GPU memory exhausted while loading model. "
            "The model requires more VRAM than is currently available."
        ),
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.VRAM,
        resolution_steps=[
            "Close other GPU applications (games, other AI tools, video editors).",
            "Switch to a smaller model variant in add-on preferences.",
            "Restart Blender to free leaked GPU memory.",
        ],
    ),
    "BF-E002": ErrorCatalogEntry(
        code="BF-E002",
        message=(
            "GPU memory exhausted during inference. "
            "Not enough VRAM to complete the current operation."
        ),
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.VRAM,
        resolution_steps=[
            "Close other GPU applications to free VRAM.",
            "Reduce input image resolution before processing.",
            "Switch to a smaller model variant in add-on preferences.",
        ],
    ),
    # --- Input Errors ---
    "BF-E003": ErrorCatalogEntry(
        code="BF-E003",
        message="Unsupported image format. Supported formats: .jpg, .jpeg, .png, .webp, .heic.",
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.INPUT,
        resolution_steps=[
            "Convert the image to PNG or JPEG format.",
            "Use a different image file with a supported extension.",
        ],
    ),
    "BF-E004": ErrorCatalogEntry(
        code="BF-E004",
        message=(
            "Image resolution is too low (minimum 256×256 pixels required). "
            "Higher resolution images produce better 3D reconstructions."
        ),
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.INPUT,
        resolution_steps=[
            "Use a higher resolution image (at least 256×256 pixels).",
            "Re-capture the reference photo at a higher resolution.",
        ],
    ),
    "BF-E005": ErrorCatalogEntry(
        code="BF-E005",
        message=(
            "Image appears blurry. Results may be lower quality."
        ),
        severity=ErrorSeverity.WARNING,
        category=ErrorCategory.INPUT,
        resolution_steps=[
            "Use a sharper reference image.",
            "Ensure the camera is focused on the object before capturing.",
        ],
    ),
    # --- Model Errors ---
    "BF-E006": ErrorCatalogEntry(
        code="BF-E006",
        message=(
            "Model weight file not found. "
            "The required AI model weights have not been downloaded."
        ),
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.MODEL,
        resolution_steps=[
            "Download model weights via the Tessera Model Manager panel.",
            "Check that the cache directory path is correct in add-on preferences.",
            "Verify your internet connection and retry the download.",
        ],
    ),
    "BF-E007": ErrorCatalogEntry(
        code="BF-E007",
        message=(
            "Model weight file is corrupted (hash mismatch). "
            "The downloaded file does not match the expected checksum."
        ),
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.MODEL,
        resolution_steps=[
            "Delete the corrupted weight file and re-download via the Model Manager.",
            "Check available disk space — incomplete downloads cause corruption.",
            "Verify your internet connection is stable before re-downloading.",
        ],
    ),
    "BF-E008": ErrorCatalogEntry(
        code="BF-E008",
        message=(
            "Reconstruction produced an empty mesh. "
            "The AI model could not generate geometry from the input."
        ),
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.MODEL,
        resolution_steps=[
            "Try a different reference image with clearer object boundaries.",
            "Ensure the object is well-lit and centered in the image.",
            "Try a different reconstruction adapter in add-on preferences.",
        ],
    ),
    "BF-E009": ErrorCatalogEntry(
        code="BF-E009",
        message=(
            "Reconstruction timed out (exceeded 120 seconds). "
            "The operation took too long to complete."
        ),
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.MODEL,
        resolution_steps=[
            "Try a simpler object or lower-resolution input image.",
            "Switch to a faster reconstruction adapter (e.g., InstantMesh).",
            "Close other GPU applications to free processing resources.",
        ],
    ),
    # --- Export Errors ---
    "BF-E010": ErrorCatalogEntry(
        code="BF-E010",
        message=(
            "Mesh cleanup failed to produce manifold output. "
            "The mesh geometry could not be fully repaired."
        ),
        severity=ErrorSeverity.WARNING,
        category=ErrorCategory.EXPORT,
        resolution_steps=[
            "Try enabling 'Auto Voxel Fallback' in cleanup settings.",
            "Manually inspect the mesh for severe topology issues in Edit Mode.",
            "Try a different reconstruction adapter for a cleaner initial mesh.",
        ],
    ),
    "BF-E011": ErrorCatalogEntry(
        code="BF-E011",
        message=(
            "Export directory is not writable. "
            "Cannot save files to the specified location."
        ),
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.EXPORT,
        resolution_steps=[
            "Choose a different export directory with write permissions.",
            "Check that the disk has sufficient free space.",
            "Save the .blend file first to establish a default export directory.",
        ],
    ),
    # --- Blender Errors ---
    "BF-E012": ErrorCatalogEntry(
        code="BF-E012",
        message=(
            "Blender version is incompatible. "
            "Tessera requires Blender 4.2 or newer."
        ),
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.BLENDER,
        resolution_steps=[
            "Update Blender to version 4.2 LTS or newer from blender.org.",
            "Check the Tessera documentation for supported Blender versions.",
        ],
    ),
    "BF-E013": ErrorCatalogEntry(
        code="BF-E013",
        message=(
            "No CUDA or ROCm GPU detected. "
            "Tessera requires a compatible GPU for AI model inference."
        ),
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.BLENDER,
        resolution_steps=[
            "Install the latest GPU drivers from NVIDIA or AMD.",
            "Verify GPU is recognized in Blender Preferences → System → GPU Backend.",
            "On macOS with Apple Silicon, ensure MPS backend is available.",
        ],
    ),
    "BF-E014": ErrorCatalogEntry(
        code="BF-E014",
        message=(
            "Required Python dependency is missing. "
            "A required library could not be imported."
        ),
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.BLENDER,
        resolution_steps=[
            "Re-install the Tessera add-on from the latest release ZIP.",
            "Check the Tessera documentation for dependency requirements.",
            "Report this issue on GitHub with your Blender and Python version.",
        ],
    ),
    # --- System Errors ---
    "BF-E015": ErrorCatalogEntry(
        code="BF-E015",
        message=(
            "Insufficient disk space for model weights. "
            "At least 2 GB of free disk space is required."
        ),
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.SYSTEM,
        resolution_steps=[
            "Free disk space by deleting unused files.",
            "Change the model cache directory to a drive with more space.",
            "Check available disk space with your system's disk utility.",
        ],
    ),
    "BF-E016": ErrorCatalogEntry(
        code="BF-E016",
        message=(
            "3MF exporter add-on not available in Blender. "
            "The built-in 3MF export functionality could not be found."
        ),
        severity=ErrorSeverity.WARNING,
        category=ErrorCategory.BLENDER,
        resolution_steps=[
            "Enable 'Import/Export: 3MF' in Blender Preferences → Add-ons.",
            "Update Blender to version 4.2+ which includes built-in 3MF support.",
            "Export to STL format instead if 3MF is not required.",
        ],
    ),
    # --- Fallback ---
    "BF-E999": ErrorCatalogEntry(
        code="BF-E999",
        message="An unexpected error occurred. Please try again.",
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.SYSTEM,
        resolution_steps=[
            "Restart Blender and try again.",
            "Check the Blender system console for detailed error information.",
            "Report this issue on GitHub with steps to reproduce.",
        ],
    ),
}
