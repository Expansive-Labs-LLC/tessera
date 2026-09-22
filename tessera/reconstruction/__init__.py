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

"""Tessera 3D reconstruction engine.

Provides a model-agnostic adapter layer for converting 2D vision
pipeline outputs into 3D meshes.  The engine selects the best
available adapter based on input requirements and GPU resources.

Spec: SPEC-TS-0004 (Single-Image 3D Reconstruction Engine)

Public API:
    ReconstructionEngine — main entry point (FR-020)
    ReconstructionAdapter — abstract adapter interface (FR-001)
    AdapterRegistry — adapter discovery and selection (FR-006)
    StandardMesh — normalised mesh output (FR-002)
    ReconstructionResult — result wrapper (FR-003)
    AdapterCapabilities — adapter declaration (FR-001)
    VisionPipelineOutput — type alias for VisionResult
"""

from ..reconstruction.adapter import (
    ReconstructionAdapter,
    VisionPipelineOutput,
)
from ..reconstruction.engine import ReconstructionEngine
from ..reconstruction.mesh_output import (
    AdapterCapabilities,
    ReconstructionResult,
    StandardMesh,
)
from ..reconstruction.registry import AdapterRegistry

__all__ = [
    "AdapterCapabilities",
    "AdapterRegistry",
    "ReconstructionAdapter",
    "ReconstructionEngine",
    "ReconstructionResult",
    "StandardMesh",
    "VisionPipelineOutput",
]
