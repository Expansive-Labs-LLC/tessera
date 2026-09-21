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

"""Abstract base class for reconstruction adapters.

Defines the ``ReconstructionAdapter`` interface that all model backends
must implement.  Follows the Strategy design pattern so that
reconstruction models can be swapped without changing the engine.

Spec: SPEC-TS-0004 (Single-Image 3D Reconstruction Engine)

Public API:
    ReconstructionAdapter — abstract base class (FR-001)
    VisionPipelineOutput — type alias for VisionResult (§3.2)
"""

from __future__ import annotations

import importlib.util as _importlib_util
import os as _os
from abc import ABC, abstractmethod

# Load VisionResult directly from the types.py file to avoid
# triggering tessera.vision.__init__ which eagerly imports the
# full pipeline and its heavy dependencies (PIL, etc.).
_types_path = _os.path.join(
    _os.path.dirname(_os.path.dirname(__file__)), "vision", "types.py"
)
_spec = _importlib_util.spec_from_file_location("tessera.vision.types", _types_path)
_vision_types = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_vision_types)
VisionPipelineOutput = _vision_types.VisionResult  # noqa: F401
del _vision_types, _spec, _types_path, _importlib_util, _os

from .mesh_output import AdapterCapabilities, ReconstructionResult  # noqa: E402


class ReconstructionAdapter(ABC):
    """Abstract base class for 3D reconstruction model adapters.

    Each concrete adapter wraps a specific reconstruction model
    (Trellis, InstantMesh, OpenLRM, etc.) behind this uniform
    interface.  The ``ReconstructionEngine`` interacts only with
    this interface — never with model-specific code directly.

    Subclasses must implement:
        - ``reconstruct()`` — run inference and return a result
        - ``capabilities()`` — declare model requirements

    Implements: FR-001, CON-002.
    """

    @abstractmethod
    def reconstruct(self, inputs: list[VisionPipelineOutput]) -> ReconstructionResult:
        """Run 3D reconstruction on the provided vision outputs.

        Args:
            inputs: One or more processed images from the vision
                pipeline.  Each entry contains the RGB image,
                segmentation mask, depth map, view label, and
                feature embeddings.

        Returns:
            ReconstructionResult with ``success=True`` and a
            ``StandardMesh`` on success, or ``success=False``
            with an actionable ``error_message`` on failure.
        """

    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Declare the capabilities and requirements of this adapter.

        Returns:
            AdapterCapabilities describing input requirements,
            VRAM needs, and supported output types.
        """
