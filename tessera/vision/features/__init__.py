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

"""Feature extraction adapter sub-package.

Public API:
    FeatureAdapter — abstract base class
    DINOv2Adapter — DINOv2 ViT-B/14 feature extraction
"""

from .base import FeatureAdapter
from .dinov2_adapter import DINOv2Adapter

__all__ = [
    "DINOv2Adapter",
    "FeatureAdapter",
]
