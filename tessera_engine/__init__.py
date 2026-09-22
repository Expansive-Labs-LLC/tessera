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

"""The Tessera local inference engine.

A separate program from the add-on, installed separately, carrying its own
Python, PyTorch, CUDA runtime and TRELLIS's compiled extensions. It exists
because none of that fits in a Blender add-on archive (ADR-0001).

It imports no ``bpy`` and depends on nothing from the add-on. The only
thing shared between the two is ``codec.py``, which is duplicated
verbatim on both sides and pinned by a test — a wire contract defined
twice in code rather than once in prose.

**It never acquires weights.** It is handed absolute paths the add-on has
already resolved, digest-verified and licence-checked, and refuses
anything outside the cache root it was launched with. That keeps
SPEC-TS-0002's licence gate a single choke point rather than two that
have to agree (SPEC-TS-0023 FR-007, CON-005, CON-011).

**It trusts nothing that arrives on the socket.** Loopback is not a trust
boundary on a desktop: any local process can reach the port, and so can a
page in the user's own browser. Every request presents the per-start
token, and anything carrying an ``Origin`` header is refused outright
(FR-037, SEC-007).

Spec: SPEC-TS-0023 (Local Inference Engine)
Licence: GPL-2.0-or-later, the same terms as the add-on (CON-010)
"""

#: Protocol versions this engine serves. Reported on /health and checked
#: against the header every request carries (SPEC-TS-0023 FR-036).
PROTOCOL_VERSIONS = frozenset({1})

#: Engine version, independent of the add-on's (FR-016).
ENGINE_VERSION = "1.0.0"

#: Default loopback endpoint (FR-017).
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

#: Per-request headers (FR-036, FR-037). Duplicated from the add-on side
#: deliberately: the two halves ship separately and must not import each
#: other, so shared constants are part of the wire contract.
REQUEST_ID_HEADER = "X-Tessera-Request-Id"
PROTOCOL_HEADER = "X-Tessera-Protocol"
TOKEN_HEADER = "X-Tessera-Token"

#: Largest request body accepted, refused before it is read (FR-038).
MAX_REQUEST_BYTES = 64 * 1024 * 1024

#: Result ceiling; beyond this the engine refuses rather than truncating
#: a mesh the user would not recognise as theirs (FR-028).
MAX_VERTICES = 1_000_000
MAX_FACES = 2_000_000
