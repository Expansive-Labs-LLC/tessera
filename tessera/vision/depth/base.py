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

"""Abstract base class for depth estimation adapters.

Defines the interface that all depth model backends must implement.
Concrete implementations (e.g., Depth Anything V2, Marigold) inherit
from this class.

Spec: SPEC-TS-0003, FR-018.

Public API:
    DepthAdapter — abstract adapter for monocular depth models.
"""

from abc import ABC, abstractmethod

import numpy as np


class DepthAdapter(ABC):
    """Abstract base class for depth estimation model adapters.

    Each adapter manages the lifecycle of a single depth model:
    load to GPU, infer on images with masking, and unload from GPU.

    Subclasses must implement ``load()``, ``predict()``, ``unload()``,
    and the ``model_name`` property.

    Implements: FR-018.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model name for logging and error messages.

        Returns:
            str: The model name (e.g., ``"Depth Anything V2 Large"``).
        """
        ...

    @abstractmethod
    def load(self) -> None:
        """Load model weights to GPU.

        Weights are resolved via the model weight manager API (CON-005).

        Raises:
            InsufficientVRAMError: If GPU VRAM is insufficient (EC-005).
        """
        ...

    @abstractmethod
    def predict(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Run depth estimation on a single image and apply mask.

        Args:
            image: Preprocessed RGB image, ``(H, W, 3)`` uint8.
            mask: Binary segmentation mask, ``(H, W)`` uint8, 0/255.

        Returns:
            np.ndarray: Masked depth map ``(H, W)`` float32 in
                ``[0.0, 1.0]``, with background regions (mask == 0)
                set to 0.0 (FR-006, FR-007).
        """
        ...

    @abstractmethod
    def unload(self) -> None:
        """Unload model weights from GPU, freeing VRAM.

        FR-017: Called after all images in a batch are processed.
        """
        ...
