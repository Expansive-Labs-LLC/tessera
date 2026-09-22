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
"""

#: Protocol versions this add-on understands. The engine reports one in its
#: health response; anything outside this set is refused rather than guessed
#: at (SPEC-TS-0023 FR-011).
PROTOCOL_VERSIONS = frozenset({1})

#: Default loopback endpoint. Overridable via add-on preferences (FR-017).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


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
