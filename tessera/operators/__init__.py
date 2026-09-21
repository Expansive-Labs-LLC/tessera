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

"""Tessera operator modules.

Collects all operator classes for registration.
"""

from . import (
    cleanup_ops,
    export_ops,
    generate_ops,
    image_ops,
    model_ops,
    multiview_ops,
    preferences_ops,
    refinement_ops,
    scaling_ops,
    sketch_ops,
    validate_ops,
)

classes = (
    image_ops.classes
    + generate_ops.classes
    + multiview_ops.classes
    + sketch_ops.classes
    + validate_ops.classes
    + export_ops.classes
    + preferences_ops.classes
    + model_ops.classes
    + cleanup_ops.classes
    + scaling_ops.classes
    + refinement_ops.classes
)
