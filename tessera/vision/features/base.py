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

"""Abstract base class for feature extraction adapters.

Defines the interface that all feature extraction backends must implement.
Concrete implementations (e.g., DINOv2) inherit from this class.

Spec: SPEC-TS-0003, FR-018.

Public API:
    FeatureAdapter — abstract adapter for feature extraction models.
"""

from abc import ABC, abstractmethod

import numpy as np


class FeatureAdapter(ABC):
    """Abstract base class for feature extraction model adapters.

    Each adapter manages the lifecycle of a feature extraction model:
    load to GPU, extract per-image feature vectors, and unload.

    Subclasses must implement ``load()``, ``predict()``, ``unload()``,
    and the ``model_name`` property.

    Implements: FR-018.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model name for logging and error messages.

        Returns:
            str: The model name (e.g., ``"DINOv2 ViT-B/14"``).
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
        """Extract feature vector from a single image.

        Args:
            image: Preprocessed RGB image, ``(H, W, 3)`` uint8.

        Returns:
            np.ndarray: Feature vector ``(1, D)`` float32, where ``D``
                is the model's embedding dimension (FR-013).
        """
        ...

    @abstractmethod
    def unload(self) -> None:
        """Unload model weights from GPU, freeing VRAM.

        FR-017: Called after all images in a batch are processed.
        """
        ...
