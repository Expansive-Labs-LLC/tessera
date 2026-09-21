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

"""Stub adapter for testing and development.

Returns a unit cube mesh without requiring a GPU or model weights.
Used as a fallback when no production adapter is available.

Spec: SPEC-TS-0004 (Single-Image 3D Reconstruction Engine)

Public API:
    StubAdapter — test/development adapter (FR-005)
"""

from __future__ import annotations

import logging
import time

import numpy as np

from tessera.reconstruction.adapter import (
    ReconstructionAdapter,
    VisionPipelineOutput,
)
from tessera.reconstruction.mesh_output import (
    AdapterCapabilities,
    ReconstructionResult,
)
from tessera.reconstruction.utils.mesh_conversion import normalize_to_standard_mesh

logger = logging.getLogger("tessera.reconstruction")

# Unit cube geometry: 8 vertices, 12 triangular faces.
_CUBE_VERTICES = np.array(
    [
        [-0.5, -0.5, -0.5],
        [0.5, -0.5, -0.5],
        [0.5, 0.5, -0.5],
        [-0.5, 0.5, -0.5],
        [-0.5, -0.5, 0.5],
        [0.5, -0.5, 0.5],
        [0.5, 0.5, 0.5],
        [-0.5, 0.5, 0.5],
    ],
    dtype=np.float32,
)

_CUBE_FACES = np.array(
    [
        # Front
        [0, 1, 2],
        [0, 2, 3],
        # Back
        [4, 6, 5],
        [4, 7, 6],
        # Left
        [0, 3, 7],
        [0, 7, 4],
        # Right
        [1, 5, 6],
        [1, 6, 2],
        # Top
        [3, 2, 6],
        [3, 6, 7],
        # Bottom
        [0, 4, 5],
        [0, 5, 1],
    ],
    dtype=np.int32,
)

# Neutral grey vertex colours for the stub cube.
_CUBE_COLORS = np.full((8, 3), 0.6, dtype=np.float32)


class StubAdapter(ReconstructionAdapter):
    """Test/development adapter returning a unit cube.

    Does not require a GPU, model weights, or any external
    dependencies.  Useful for:

    - Running integration tests without a real model
    - Verifying downstream pipeline stages (mesh import, cleanup)
    - Development when GPU is unavailable

    Implements: FR-005.
    """

    def reconstruct(self, inputs: list[VisionPipelineOutput]) -> ReconstructionResult:
        """Return a unit cube mesh.

        Accepts any valid input and returns immediately.

        Args:
            inputs: Vision pipeline outputs (contents ignored).

        Returns:
            ReconstructionResult with a unit cube ``StandardMesh``.
        """
        start = time.monotonic()

        mesh = normalize_to_standard_mesh(
            vertices=_CUBE_VERTICES.copy(),
            faces=_CUBE_FACES.copy(),
            vertex_colors=_CUBE_COLORS.copy(),
            metadata={
                "model_name": "stub",
                "inference_time_s": time.monotonic() - start,
                "confidence": 1.0,
            },
        )

        logger.info(
            "StubAdapter: returned unit cube (%d vertices, %d faces)",
            mesh.metadata["vertex_count"],
            mesh.metadata["face_count"],
        )

        return ReconstructionResult(
            mesh=mesh,
            success=True,
            source_adapter="stub",
        )

    def capabilities(self) -> AdapterCapabilities:
        """Declare stub adapter capabilities.

        The stub adapter accepts 1–2 images, requires no GPU VRAM,
        and does not use depth maps or masks.
        """
        return AdapterCapabilities(
            model_name="stub",
            min_images=1,
            max_images=2,
            requires_depth=False,
            requires_mask=False,
            min_vram_gb=0.0,
            supported_view_labels=[
                "front",
                "back",
                "left",
                "right",
                "top",
                "bottom",
                "front-left",
                "front-right",
                "isometric",
                "unlabeled",
            ],
            output_types=["mesh"],
        )
