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

"""Abstract base class for view-direction classifier adapters.

Defines the interface that all view-label classifiers must implement.
Concrete implementations (e.g., silhouette heuristic) inherit from
this class.

Spec: SPEC-TS-0003, FR-018.

Public API:
    ViewClassifierAdapter — abstract adapter for view-direction classifiers.
"""

from abc import ABC, abstractmethod

import numpy as np


class ViewClassifierAdapter(ABC):
    """Abstract base class for view-direction classifier adapters.

    Each adapter infers a canonical view label and confidence from
    an image and its segmentation mask.

    Subclasses must implement ``load()``, ``predict()``, ``unload()``,
    and the ``model_name`` property.

    Implements: FR-018.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model name for logging and error messages.

        Returns:
            str: The model name (e.g., ``"Silhouette Classifier"``).
        """
        ...

    @abstractmethod
    def load(self) -> None:
        """Load any model resources.

        For lightweight heuristic classifiers this may be a no-op.
        """
        ...

    @abstractmethod
    def predict(self, image: np.ndarray, mask: np.ndarray) -> tuple[str, float]:
        """Classify the view direction of an image.

        Args:
            image: Preprocessed RGB image, ``(H, W, 3)`` uint8.
            mask: Binary segmentation mask, ``(H, W)`` uint8, 0/255.

        Returns:
            tuple: ``(label, confidence)`` where ``label`` is one of the
                PRD §6 vocabulary strings and ``confidence`` is in
                ``[0.0, 1.0]`` (FR-010).
        """
        ...

    @abstractmethod
    def unload(self) -> None:
        """Release any model resources."""
        ...
