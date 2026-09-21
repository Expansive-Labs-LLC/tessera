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

"""View-direction classifier adapter sub-package.

Public API:
    ViewClassifierAdapter — abstract base class
    SilhouetteClassifier — silhouette + up-vector heuristic
    resolve_view_label — label resolution helper
"""

from .base import ViewClassifierAdapter
from .silhouette_classifier import SilhouetteClassifier, resolve_view_label

__all__ = [
    "SilhouetteClassifier",
    "ViewClassifierAdapter",
    "resolve_view_label",
]
