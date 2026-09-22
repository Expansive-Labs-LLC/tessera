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

"""Client side of the local inference engine boundary.

PyTorch and TRELLIS's compiled CUDA extensions cannot ship inside a Blender
add-on archive, so inference runs in a separately installed local process
and the add-on talks to it over loopback HTTP (ADR-0001, SPEC-TS-0023).

This package is the add-on half of that boundary. It contains no ML
dependency and imports nothing from the engine — the point of the split is
that Blender never loads the heavy stack.

**The add-on keeps weight governance.** It resolves paths, verifies digests
and applies the licence gate, then hands the engine absolute, already-
verified paths. The engine never acquires weights itself, so SPEC-TS-0002's
licence gate stays a single choke point rather than becoming two that have
to agree (SPEC-TS-0023 FR-007, FR-009, CON-005).

Spec: SPEC-TS-0023 (Local Inference Engine)

Public API:
    EngineStatus — what the UI shows and why
    EngineError and subclasses — failure modes callers distinguish
    PROTOCOL_VERSIONS — protocol versions this add-on can speak
    REQUEST_ID_HEADER, PROTOCOL_HEADER, TOKEN_HEADER — per-request headers
"""

#: Protocol versions this add-on understands. The engine reports one in its
#: health response; anything outside this set is refused rather than guessed
#: at (SPEC-TS-0023 FR-011).
PROTOCOL_VERSIONS = frozenset({1})

#: Default loopback endpoint. Overridable via add-on preferences (FR-017).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

#: Headers carried by every request. The protocol version travels on each
#: one, not only on the handshake, so an engine restarted at a different
#: version underneath a long-lived client is caught rather than misread
#: (SPEC-TS-0023 FR-036). The token is what makes the caller the add-on
#: rather than any other local process (FR-037, SEC-007).
REQUEST_ID_HEADER = "X-Tessera-Request-Id"
PROTOCOL_HEADER = "X-Tessera-Protocol"
TOKEN_HEADER = "X-Tessera-Token"


class EngineError(Exception):
    """Base class for every engine-boundary failure."""


class EngineUnavailableError(EngineError):
    """The engine could not be reached.

    Covers not installed, installed but stopped, and died mid-request
    (SPEC-TS-0023 EC-001, EC-002). Callers treat this as an actionable UI
    state, never as a crash.
    """


class EngineVersionError(EngineError):
    """The engine speaks a protocol this add-on does not support.

    Raised instead of attempting the request, so a skewed pair fails
    loudly rather than exchanging data it may misinterpret
    (SPEC-TS-0023 FR-011, AC-003, EC-004).
    """


class EngineTimeoutError(EngineError):
    """The engine accepted the request and then stopped answering.

    Distinct from :class:`EngineUnavailableError`, where the process is
    gone: here it is alive and wedged, which wants a different message and
    a different remedy (SPEC-TS-0023 EC-006, FR-035). The client issues
    ``POST /cancel`` before raising, so the engine is not left holding the
    inference lock for a request nobody is waiting on.

    Attributes:
        endpoint: The endpoint that did not answer.
        elapsed_s: Seconds waited before giving up.
    """

    def __init__(self, endpoint: str, elapsed_s: float):
        super().__init__(
            f"The Tessera engine did not respond to {endpoint} within "
            f"{elapsed_s:.0f} s. It is running but not answering — check "
            "the engine log, or restart it."
        )
        self.endpoint = endpoint
        self.elapsed_s = elapsed_s


class EngineRequestError(EngineError):
    """The engine returned a structured error.

    Attributes:
        slug: Machine-readable cause, e.g. ``"insufficient_vram"``.
        detail: Human-readable explanation from the engine.
        retryable: Whether retrying unchanged could succeed.
    """

    def __init__(self, slug: str, detail: str = "", retryable: bool = False):
        super().__init__(f"{slug}: {detail}" if detail else slug)
        self.slug = slug
        self.detail = detail
        self.retryable = retryable
