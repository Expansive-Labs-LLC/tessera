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

"""Post-edit preview renderer for the refinement loop.

Renders a 512×512 px Workbench snapshot after each edit, storing
the result as a Blender image data block.

Spec: SPEC-TS-0009 (Natural-Language Refinement Loop)

Implements: FR-037, FR-038.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger("tessera.refinement")


class PreviewRenderer:
    """Renders post-edit preview images via Blender's Workbench engine.

    Generates 512×512 px renders using the active viewport angle
    or scene camera, stored as ``"BF_Preview_{timestamp}"`` image
    data blocks.

    Implements: FR-037, FR-038.
    """

    #: FR-037: Preview image resolution.
    PREVIEW_SIZE = 512

    def render(self, obj: Any) -> Optional[str]:
        """Render a preview of the current mesh state.

        Uses Blender's Workbench engine for fast rendering.

        Args:
            obj: The mesh object to render.

        Returns:
            The name of the created image data block
            (``"BF_Preview_{timestamp}"``), or ``None`` on failure.

        Implements: FR-037, FR-038.
        """
        import bpy

        start = time.perf_counter()
        timestamp = int(time.time() * 1000)

        # FR-038: Image data block naming.
        image_name = f"BF_Preview_{timestamp}"

        try:
            scene = bpy.context.scene

            # Save current render settings.
            orig_engine = scene.render.engine
            orig_x = scene.render.resolution_x
            orig_y = scene.render.resolution_y
            orig_pct = scene.render.resolution_percentage
            orig_film = scene.render.film_transparent

            # Configure Workbench render.
            scene.render.engine = "BLENDER_WORKBENCH"
            scene.render.resolution_x = self.PREVIEW_SIZE
            scene.render.resolution_y = self.PREVIEW_SIZE
            scene.render.resolution_percentage = 100
            scene.render.film_transparent = True

            # Render.
            bpy.ops.render.render(write_still=False)

            # Copy result to named image data block.
            render_result = bpy.data.images.get("Render Result")
            if render_result is None:
                logger.warning("Preview render produced no result")
                return None

            # Create a copy as a named image.
            preview_image = bpy.data.images.new(
                name=image_name,
                width=self.PREVIEW_SIZE,
                height=self.PREVIEW_SIZE,
                alpha=True,
            )
            preview_image.pixels = render_result.pixels[:]

            # Restore render settings.
            scene.render.engine = orig_engine
            scene.render.resolution_x = orig_x
            scene.render.resolution_y = orig_y
            scene.render.resolution_percentage = orig_pct
            scene.render.film_transparent = orig_film

            elapsed = time.perf_counter() - start
            logger.debug(
                "Preview rendered: image_name=%s, "
                "resolution=%dx%d, render_time_seconds=%.2f",
                image_name,
                self.PREVIEW_SIZE,
                self.PREVIEW_SIZE,
                elapsed,
            )

            return image_name

        except Exception as exc:
            logger.warning(
                "Preview render failed: error=%s",
                str(exc),
            )
            return None

    def cleanup_old_previews(self, max_keep: int = 5) -> int:
        """Remove old preview images to conserve memory.

        Keeps only the most recent ``max_keep`` preview images.

        Args:
            max_keep: Maximum number of preview images to retain.

        Returns:
            Number of images removed.
        """
        import bpy

        # Find all BF_Preview images.
        preview_images = sorted(
            [img for img in bpy.data.images if img.name.startswith("BF_Preview_")],
            key=lambda img: img.name,
        )

        removed = 0
        while len(preview_images) > max_keep:
            old_img = preview_images.pop(0)
            bpy.data.images.remove(old_img)
            removed += 1

        if removed > 0:
            logger.debug(
                "Cleaned up %d old preview images (kept %d)",
                removed,
                len(preview_images),
            )

        return removed
