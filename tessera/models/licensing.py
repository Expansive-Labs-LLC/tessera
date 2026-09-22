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

"""Model weight licence gating for Tessera.

Model weights are downloaded from third-party repositories at runtime and
are **not** covered by Tessera's own GPL-2.0-or-later licence. Some carry
terms that forbid or restrict commercial use — notably
``depth-anything-v2-large`` (CC-BY-NC-4.0). Tessera therefore refuses to
download any weight whose terms are not unambiguously commercial-friendly
unless the user explicitly opts in.

The opt-in lives in add-on preferences. Because downloads run on worker
threads and ``bpy`` must not be touched from a thread (SPEC-TS-0002
CON-003), the preference is mirrored into a module-level flag that the
main thread sets via :func:`sync_from_preferences` or
:func:`set_restricted_models_allowed`.

Spec: SPEC-TS-0002 (Local Model Weight Management)
Reference: ``MODEL-LICENSES.md`` at the repository root.

Public API:
    COMMERCIAL_USE_* — commercial-use classifications
    classify_license — map a licence identifier to a classification
    is_gated — whether an entry requires explicit opt-in
    check_download_allowed — raise ModelLicenseError if not permitted
    license_summary — short human-readable licence line for the UI
    restricted_models_allowed / set_restricted_models_allowed
    sync_from_preferences — mirror the add-on preference (main thread only)
"""

import logging
import threading
from typing import Any

logger = logging.getLogger("tessera.models")

# Commercial-use classifications used by ``manifest.json``.
COMMERCIAL_USE_ALLOWED = "allowed"
COMMERCIAL_USE_RESTRICTED = "restricted"
COMMERCIAL_USE_PROHIBITED = "prohibited"
COMMERCIAL_USE_UNKNOWN = "unknown"

# Anything that is not unambiguously "allowed" requires an explicit opt-in.
# An unknown or missing classification fails closed, on purpose: a weight
# whose terms nobody has checked is treated as if it were restricted.
_GATED_CLASSIFICATIONS = frozenset(
    {
        COMMERCIAL_USE_RESTRICTED,
        COMMERCIAL_USE_PROHIBITED,
        COMMERCIAL_USE_UNKNOWN,
    }
)

# Licence identifiers that permit commercial use without behavioural
# restrictions. Compared lower-cased against Hugging Face's ``license`` tag.
_PERMISSIVE_LICENSES = frozenset(
    {
        "apache-2.0",
        "bsd",
        "bsd-2-clause",
        "bsd-3-clause",
        "cc0-1.0",
        "cc-by-4.0",
        "cc-by-3.0",
        "cc-by-sa-4.0",
        "isc",
        "mit",
        "mpl-2.0",
        "unlicense",
        "gpl-2.0",
        "gpl-3.0",
        "lgpl-3.0",
        "agpl-3.0",
        "artistic-2.0",
        "zlib",
        "openmdw-1.0",
    }
)

# Identifiers that permit commercial use but attach behavioural use
# restrictions which must be passed on to downstream users.
_RESTRICTED_MARKERS = ("openrail", "rail", "llama", "gemma", "deepfloyd")


def classify_license(license_id) -> str:
    """Classify a licence identifier for commercial use.

    Conservative by design: anything not recognised as permissive is gated.
    A weight whose terms nobody has read is not a weight to download by
    default.

    Args:
        license_id: Licence identifier, typically Hugging Face's ``license``
            tag (e.g. ``"apache-2.0"``, ``"cc-by-nc-4.0"``). ``None`` and
            ``"other"`` mean the publisher declared nothing usable.

    Returns:
        str: One of the ``COMMERCIAL_USE_*`` constants.
    """
    if not license_id:
        return COMMERCIAL_USE_UNKNOWN

    value = str(license_id).strip().lower()
    if not value or value in {"other", "unknown", "unlicensed"}:
        return COMMERCIAL_USE_UNKNOWN

    # Non-commercial variants of Creative Commons and anything else that
    # spells it out. "-nc-" and a trailing "-nc" both appear in the wild.
    if "-nc-" in value or value.endswith("-nc") or "noncommercial" in value:
        return COMMERCIAL_USE_PROHIBITED

    if any(marker in value for marker in _RESTRICTED_MARKERS):
        return COMMERCIAL_USE_RESTRICTED

    if value in _PERMISSIVE_LICENSES:
        return COMMERCIAL_USE_ALLOWED

    # An identifier we do not recognise — e.g. a bespoke community licence.
    return COMMERCIAL_USE_UNKNOWN


# Mirror of the ``allow_restricted_license_models`` add-on preference.
# Set from the main thread; read from download worker threads.
_lock = threading.Lock()
_allow_restricted = False


def restricted_models_allowed() -> bool:
    """Return whether licence-gated model downloads are currently permitted.

    Returns:
        bool: ``True`` if the user has opted in to restricted weights.
    """
    with _lock:
        return _allow_restricted


def set_restricted_models_allowed(value: bool) -> None:
    """Set the licence opt-in flag.

    Call from the main thread only — typically from the add-on preference
    update callback or an operator's ``execute()``.

    Args:
        value: ``True`` to permit downloading licence-gated weights.
    """
    global _allow_restricted
    with _lock:
        _allow_restricted = bool(value)
    logger.info("Restricted-licence model downloads allowed: %s", bool(value))


def sync_from_preferences() -> bool:
    """Mirror the add-on preference into the module-level flag.

    Safe to call when ``bpy`` is unavailable (tests, headless tooling) —
    the flag is left untouched and ``False`` is returned.

    Returns:
        bool: The value now in effect.

    Note:
        Main thread only (CON-003). Worker threads read
        :func:`restricted_models_allowed` instead.
    """
    try:
        import bpy

        prefs = bpy.context.preferences.addons["tessera"].preferences
        value = bool(getattr(prefs, "allow_restricted_license_models", False))
    except Exception:  # pragma: no cover — bpy absent or add-on not registered
        logger.debug("Could not read licence preference; leaving flag unchanged.")
        return restricted_models_allowed()

    set_restricted_models_allowed(value)
    return value


def commercial_use(entry: Any) -> str:
    """Return the commercial-use classification for a model entry.

    Args:
        entry: A ``ModelEntry`` (or anything exposing ``commercial_use``).

    Returns:
        str: One of the ``COMMERCIAL_USE_*`` constants; ``unknown`` when
        the manifest entry does not declare one.
    """
    value = getattr(entry, "commercial_use", None) or COMMERCIAL_USE_UNKNOWN
    return str(value).strip().lower()


def is_gated(entry: Any) -> bool:
    """Return whether an entry requires explicit user opt-in to download.

    Args:
        entry: A ``ModelEntry``.

    Returns:
        bool: ``True`` when the entry's terms are restricted, prohibited,
        or undeclared.
    """
    return commercial_use(entry) in _GATED_CLASSIFICATIONS


def license_summary(entry: Any) -> str:
    """Return a one-line licence description for UI display.

    Args:
        entry: A ``ModelEntry``.

    Returns:
        str: For example ``"Apache-2.0"`` or
        ``"CC-BY-NC-4.0 — non-commercial only"``.
    """
    name = getattr(entry, "license", None) or "licence not declared"
    classification = commercial_use(entry)

    if classification == COMMERCIAL_USE_PROHIBITED:
        return f"{name} — non-commercial only"
    if classification == COMMERCIAL_USE_RESTRICTED:
        return f"{name} — use restrictions apply"
    if classification == COMMERCIAL_USE_UNKNOWN:
        return f"{name} — unverified"
    return str(name)


def check_download_allowed(entry: Any) -> None:
    """Raise if this model may not be downloaded under current settings.

    Args:
        entry: A ``ModelEntry``.

    Raises:
        ModelLicenseError: If the entry is licence-gated and the user has
            not opted in.
    """
    if not is_gated(entry) or restricted_models_allowed():
        return

    from . import ModelLicenseError

    model_id = getattr(entry, "model_id", "<unknown>")
    classification = commercial_use(entry)
    name = getattr(entry, "license", None) or "no declared licence"

    if classification == COMMERCIAL_USE_PROHIBITED:
        reason = (
            f"'{model_id}' is published under {name}, which prohibits "
            f"commercial use."
        )
    elif classification == COMMERCIAL_USE_RESTRICTED:
        reason = (
            f"'{model_id}' is published under {name}, which attaches use "
            f"restrictions you must pass on to anyone you share output with."
        )
    else:
        reason = (
            f"'{model_id}' does not declare a licence that has been "
            f"verified as commercial-friendly."
        )

    raise ModelLicenseError(
        f"{reason} Tessera will not download it by default. Enable "
        f"'Allow restricted-licence models' in Preferences → Add-ons → "
        f"Tessera if your use complies with those terms. See "
        f"MODEL-LICENSES.md for the full breakdown."
    )
