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

"""Abstract base class for segmentation adapters.

Defines the interface that all segmentation model backends must implement.
Concrete implementations (e.g., SAM 2, FastSAM) inherit from this class.

Spec: SPEC-TS-0003, FR-018.

Public API:
    SegmentationAdapter — abstract adapter for segmentation models.
"""

from abc import ABC, abstractmethod

import numpy as np


class SegmentationAdapter(ABC):
    """Abstract base class for segmentation model adapters.

    Each adapter manages the lifecycle of a single segmentation model:
    load to GPU, infer on images, and unload from GPU.

    Subclasses must implement ``load()``, ``predict()``, ``unload()``,
    and the ``model_name`` property.

    Implements: FR-018.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model name for logging and error messages.

        Returns:
            str: The model name (e.g., ``"SAM 2 Large"``).
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
    def predict(self, image: np.ndarray) -> np.ndarray:
        """Run segmentation inference on a single image.

        Args:
            image: Preprocessed RGB image, ``(H, W, 3)`` uint8.

        Returns:
            np.ndarray: Binary mask ``(H, W)`` uint8, where 255 = foreground
                and 0 = background (FR-005).
        """
        ...

    @abstractmethod
    def unload(self) -> None:
        """Unload model weights from GPU, freeing VRAM.

        FR-017: Called after all images in a batch are processed.
        """
        ...
