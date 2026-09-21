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

"""Tessera UI panel modules.

Collects all panel classes for registration.
"""

from . import (
    chat_panel,
    cleanup_panel,
    download_panel,
    error_panel,
    export_panel,
    generation_panel,
    help_panel,
    image_panel,
    main_panel,
    multiview_panel,
    perf_panel,
    scaling_panel,
    sketch_panel,
    validation_panel,
)

classes = (
    main_panel.classes
    + download_panel.classes
    + image_panel.classes
    + generation_panel.classes
    + multiview_panel.classes
    + sketch_panel.classes
    + validation_panel.classes
    + export_panel.classes
    + cleanup_panel.classes
    + scaling_panel.classes
    + chat_panel.classes
    + error_panel.classes
    + perf_panel.classes
    + help_panel.classes
)
