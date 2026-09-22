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

"""The engine's error envelope.

One shape for every failure, so the add-on can branch on a slug rather
than parse prose: ``{"error", "detail", "retryable", "request_id"}`` plus
whatever fields that particular slug carries.

``retryable`` means retrying *unchanged* could succeed. Insufficient VRAM
is not retryable even though closing another application would fix it,
because the retry alone would not.

Spec: SPEC-TS-0023 §10.1, FR-019, FR-028, FR-038

Public API:
    EngineFault — a failure with a slug, a status and its extra fields
    SLUG_STATUS — the documented slug-to-status mapping
"""

from typing import Any, Optional

#: Slug → (HTTP status, retryable). The single place the mapping lives;
#: §10.1 of the spec is this table in prose.
#:
#: 499 is not an RFC 9110 code. It is the widely used convention for a
#: request the client abandoned, chosen so a cancelled request cannot be
#: mistaken for a server-side failure. It is only ever seen on loopback.
SLUG_STATUS: dict = {
    "unauthorized": (401, False),
    "bad_request": (400, False),
    "protocol_mismatch": (400, False),
    "payload_too_large": (413, False),
    "unsupported_stage": (400, False),
    "weights_missing": (400, False),
    "load_failed": (422, False),
    "insufficient_vram": (503, False),
    "mesh_too_large": (422, False),
    "busy": (409, True),
    "cancelled": (499, False),
    "internal": (500, False),
}


class EngineFault(Exception):
    """A failure the engine reports in its documented envelope.

    Attributes:
        slug: Machine-readable cause; must appear in :data:`SLUG_STATUS`.
        detail: Human-readable explanation.
        extra: Slug-specific fields, e.g. ``required_gb``.
        status: HTTP status for this slug.
        retryable: Whether retrying unchanged could succeed.
    """

    def __init__(self, slug: str, detail: str = "", **extra: Any):
        if slug not in SLUG_STATUS:
            # An undocumented slug is a bug in the engine, not a new kind
            # of failure. Report it as internal rather than inventing a
            # contract the add-on has never seen.
            detail = f"{slug}: {detail}" if detail else slug
            slug = "internal"
            extra = {}
        super().__init__(detail or slug)
        self.slug = slug
        self.detail = detail
        self.extra = extra
        self.status, self.retryable = SLUG_STATUS[slug]

    def body(self, request_id: Optional[str] = None) -> dict:
        """Render the response body for this fault.

        Args:
            request_id: The request this failed, echoed back.

        Returns:
            The error object described in §10.1.
        """
        return {
            "error": self.slug,
            "detail": self.detail,
            "retryable": self.retryable,
            "request_id": request_id or "",
            **self.extra,
        }
