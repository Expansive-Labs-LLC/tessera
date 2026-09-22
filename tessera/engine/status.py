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

"""Engine availability as a UI state rather than an exception.

The defect this exists to prevent: a missing runtime surfacing as a
traceback from inside ``torch``, or as nothing at all. The add-on must be
able to say which of a small number of situations it is in, and what the
user should do about each (SPEC-TS-0023 FR-013, FR-014, AC-002, EC-001).

"Not installed" and "Stopped" are deliberately distinguished. Telling
someone to install software they have already installed is worse than
saying nothing.

Spec: SPEC-TS-0023 (FR-012, FR-013, FR-014, FR-031, EC-001, EC-003,
EC-004)

Public API:
    EngineStatus — the states the UI renders
    EngineState — a status with its message and suggested action
    resolve_status — compute the current state
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from . import EngineTimeoutError, EngineUnavailableError, EngineVersionError
from .client import EngineClient
from .discovery import is_installed

logger = logging.getLogger("tessera.engine")


class EngineStatus(Enum):
    """States the add-on can distinguish and act on."""

    NOT_INSTALLED = "Not installed"
    STOPPED = "Stopped"
    STARTING = "Starting"
    READY = "Ready"
    VERSION_MISMATCH = "Version mismatch"
    UNKNOWN_LISTENER = "Unrecognised process on port"


@dataclass(frozen=True)
class EngineState:
    """A resolved status with what to show and what to offer.

    Attributes:
        status: The state itself.
        message: One line suitable for the preferences panel.
        action: Suggested next step, or ``None`` when there is nothing
            for the user to do.
        health: The engine's health payload when reachable.
    """

    status: EngineStatus
    message: str
    action: Optional[str] = None
    health: Optional[dict] = None

    @property
    def is_ready(self) -> bool:
        """Whether engine-backed adapters may be selected (FR-012)."""
        return self.status is EngineStatus.READY


def resolve_status(
    client: Optional[EngineClient] = None,
    installed: Optional[bool] = None,
    starting: bool = False,
) -> EngineState:
    """Determine the current engine state.

    Args:
        client: Client to probe with. Defaults to a client on the
            configured host and port.
        installed: Whether an engine installation exists on disk. Defaults
            to reading the installation marker (FR-031). Passing it
            explicitly is for tests and for callers that already know.
        starting: Whether the add-on has spawned an engine that has not
            answered yet. Reported as ``Starting`` rather than ``Stopped``,
            because offering to start something already starting produces
            two engines racing for one port.

    Returns:
        The resolved state, never raising.
    """
    client = client or EngineClient()
    if installed is None:
        installed = is_installed()

    try:
        health = client.health()
    except EngineTimeoutError as exc:
        # Alive, listening, not answering. Not the same as stopped: there
        # is a process to look at and a log to read (EC-006).
        return EngineState(
            status=EngineStatus.STOPPED,
            message=str(exc),
            action="Restart the engine, then check its log.",
        )
    except EngineVersionError as exc:
        return EngineState(
            status=EngineStatus.VERSION_MISMATCH,
            message=str(exc),
            action="Update the component that is behind, then reconnect.",
        )
    except EngineUnavailableError as exc:
        # EC-003: something answered but is not a Tessera engine.
        if "did not identify itself" in str(exc):
            return EngineState(
                status=EngineStatus.UNKNOWN_LISTENER,
                message=str(exc),
                action="Change the engine port in add-on preferences.",
            )
        # A spawn in progress is neither stopped nor absent.
        if starting:
            return EngineState(
                status=EngineStatus.STARTING,
                message="The Tessera engine is starting.",
                action=None,
            )
        # EC-001: installed but stopped is not the same as not installed.
        if installed:
            return EngineState(
                status=EngineStatus.STOPPED,
                message="The Tessera engine is installed but not running.",
                action="Start the engine.",
            )
        return EngineState(
            status=EngineStatus.NOT_INSTALLED,
            message=(
                "The Tessera engine is not installed. Generation needs it "
                "to run the AI models; the add-on alone cannot."
            ),
            action="Install the Tessera engine.",
        )
    except Exception:  # pragma: no cover — defensive
        logger.exception("Unexpected failure resolving engine status")
        return EngineState(
            status=EngineStatus.NOT_INSTALLED,
            message="The Tessera engine could not be reached.",
            action="Check the engine installation.",
        )

    gpu = health.get("gpu") or "unknown GPU"
    return EngineState(
        status=EngineStatus.READY,
        message=f"Engine ready — {gpu}",
        action=None,
        health=health,
    )
