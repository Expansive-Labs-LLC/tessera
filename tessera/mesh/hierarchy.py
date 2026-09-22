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

"""Object hierarchy helpers for Phase 2 cleanup.

Handles object origin placement, descriptive naming, and optional
session grouping via parent empties.

Spec: SPEC-TS-0005 (Mesh Import, Cleanup & Topology Optimization)

Implements: FR-013, FR-014, FR-015.
"""

from __future__ import annotations

import logging
from datetime import datetime

import bpy

from .data_types import SOURCE_MODEL_RE

logger = logging.getLogger("tessera.mesh")


def set_origin_to_bounds(context: "bpy.types.Context", obj: "bpy.types.Object") -> None:
    """Set the object origin to the center of its bounding box.

    Ensures the object is active before calling the origin
    operator.

    Args:
        context: Blender context.
        obj: Target mesh object.

    Implements: FR-013.
    """
    context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")

    logger.debug("Origin set to bounding box center for %s", obj.name)


def rename_object(
    obj: "bpy.types.Object",
    source_model: str,
    timestamp: str | None = None,
) -> None:
    """Assign a descriptive name to the mesh object.

    Format: ``BF_<source>_<timestamp>`` where ``<source>`` is
    the sanitized reconstruction model name.

    Args:
        obj: Target mesh object.
        source_model: Reconstruction model identifier (sanitized).
        timestamp: Optional timestamp override (``YYYYMMDD_HHMMSS``).
            If ``None``, uses the current time.

    Implements: FR-014.
    """
    sanitized = SOURCE_MODEL_RE.sub("_", source_model)[:32]
    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"BF_{sanitized}_{ts}"

    obj.name = new_name
    if obj.data:
        obj.data.name = new_name

    logger.debug("Object renamed to %s", new_name)


def create_session_parent(
    context: "bpy.types.Context",
    timestamp: str | None = None,
) -> "bpy.types.Object":
    """Create a parent empty to group session objects.

    Creates an ``EMPTY`` object named
    ``Tessera_Session_<timestamp>`` in the active collection.

    Args:
        context: Blender context.
        timestamp: Optional timestamp override.

    Returns:
        The newly created empty object.

    Implements: FR-015 (MAY).
    """
    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"Tessera_Session_{ts}"

    empty = bpy.data.objects.new(name=name, object_data=None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.1

    context.collection.objects.link(empty)

    logger.debug("Created session parent empty: %s", name)
    return empty
