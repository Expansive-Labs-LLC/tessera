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

"""Core data types for the Tessera reconstruction engine.

Defines the normalized mesh output, reconstruction result wrapper,
and adapter capabilities declaration used across the reconstruction
pipeline.

Spec: SPEC-TS-0004 (Single-Image 3D Reconstruction Engine)

Public API:
    StandardMesh — normalized mesh output (FR-002)
    ReconstructionResult — result wrapper (FR-003)
    AdapterCapabilities — adapter declaration (FR-001, FR-006)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class StandardMesh:
    """Normalized mesh output from any reconstruction adapter.

    All adapters convert their model-specific representations (NeRF
    volumes, implicit surfaces, point clouds, raw triangles) into this
    common format before returning results.

    Attributes:
        vertices: Vertex positions, shape ``(N, 3)`` float32.
        faces: Triangle face indices, shape ``(M, 3)`` int32, zero-indexed.
        vertex_colors: Per-vertex RGB colors, shape ``(N, 3)`` float32,
            range ``[0.0, 1.0]``. ``None`` if unavailable.
        metadata: Reconstruction metadata. Required keys:
            ``model_name``, ``inference_time_s``, ``confidence``,
            ``vertex_count``, ``face_count``.

    Implements: FR-002, FR-018.
    """

    vertices: np.ndarray  # (N, 3) float32
    faces: np.ndarray  # (M, 3) int32, zero-indexed
    vertex_colors: np.ndarray | None = None  # (N, 3) float32, 0.0–1.0
    metadata: dict = field(
        default_factory=lambda: {
            "model_name": "",
            "inference_time_s": 0.0,
            "confidence": 0.0,
            "vertex_count": 0,
            "face_count": 0,
        }
    )


@dataclass
class ReconstructionResult:
    """Result returned by the reconstruction engine.

    Wraps the output mesh with success/failure status and
    diagnostic information.

    Attributes:
        mesh: Normalized mesh data, ``None`` on failure.
        success: ``True`` if reconstruction succeeded.
        error_message: Empty string on success; actionable error
            message on failure.
        warnings: Non-fatal issues encountered during reconstruction.
        source_adapter: Name of the adapter that produced the result.

    Implements: FR-003.
    """

    mesh: StandardMesh | None  # None on failure
    success: bool
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)
    source_adapter: str = ""


@dataclass
class AdapterCapabilities:
    """Declares what a reconstruction adapter supports.

    Used by the ``AdapterRegistry`` selection algorithm to match
    adapters to available inputs and GPU resources.

    Attributes:
        model_name: Model identifier, e.g. ``"trellis-v1.0"``.
        min_images: Minimum number of input images required.
        max_images: Maximum number of input images supported.
        requires_depth: Whether the adapter uses depth maps.
        requires_mask: Whether the adapter requires segmentation masks.
        min_vram_gb: Minimum GPU VRAM in GB.
        supported_view_labels: View labels this adapter can utilise.
        output_types: Output representations, e.g.
            ``["mesh", "point_cloud", "nerf"]``.

    Implements: FR-001, FR-006.
    """

    model_name: str  # e.g. "trellis-v1.0"
    min_images: int  # Minimum input images (1)
    max_images: int  # Maximum input images
    requires_depth: bool  # Whether depth maps are used
    requires_mask: bool  # Whether masks are required
    min_vram_gb: float  # Minimum GPU VRAM in GB
    supported_view_labels: list[str]  # View labels this adapter uses
    output_types: list[str]  # e.g. ["mesh", "point_cloud", "nerf"]
