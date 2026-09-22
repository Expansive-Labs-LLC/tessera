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

"""Hugging Face metadata lookup for user-added models.

Builds a manifest entry for a repository the user chooses, resolving the
two things the curated manifest supplies by hand:

* **Licence** — the repository's declared ``license`` tag, classified by
  :func:`tessera.models.licensing.classify_license`. An undeclared licence
  is classified ``unknown`` and is therefore gated.
* **Integrity** — a SHA-256 digest per file, so a user-added model is
  verified exactly like a curated one. For LFS-tracked files the Hub's
  ``paths-info`` endpoint returns the digest directly (an LFS ``oid`` *is*
  the file's SHA-256); small non-LFS files are fetched and hashed.

The resolved commit SHA is pinned into the entry, so a repository cannot
change its weights — or its terms — underneath a model the user already
approved.

Spec: SPEC-TS-0002 FR-025 – FR-032. SEC-002 (huggingface.co over HTTPS
only), SEC-004 (data files only).

Public API:
    HFModelMetadata — what the Hub reports about a repository
    fetch_model_metadata — look up a repository
    build_user_entry — turn a lookup into a manifest entry
    MetadataError — lookup failed
"""

import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from .cache_manager import ALLOWED_EXTENSIONS
from .families import get_family
from .licensing import classify_license

logger = logging.getLogger("tessera.models")

# SEC-002: the only host this module contacts.
_HF_HOST = "https://huggingface.co"

# Hugging Face repository ids: "owner/name".
_REPO_ID_RE = re.compile(r"^[A-Za-z0-9][\w.\-]*/[A-Za-z0-9][\w.\-]*$")

# Files small enough to fetch and hash locally when the Hub has no LFS
# digest for them (config.json and friends are a few KB).
_INLINE_HASH_MAX_BYTES = 1_000_000

# Refuse to build an entry larger than this without an explicit override.
_DEFAULT_MAX_TOTAL_BYTES = 20_000_000_000

_TIMEOUT_SECONDS = 15


class MetadataError(Exception):
    """Raised when a repository cannot be resolved into a manifest entry."""


@dataclass
class HFModelMetadata:
    """What the Hub reports about a repository.

    Attributes:
        repo_id: Repository identifier, ``owner/name``.
        revision: Resolved commit SHA — pinned, never a moving ref.
        license_id: Declared licence tag, or ``None`` if the publisher
            declared none.
        commercial_use: Classification from ``classify_license``.
        files: Candidate file paths, already filtered to allowed suffixes.
        sizes: Byte size per file path.
    """

    repo_id: str
    revision: str
    license_id: Optional[str]
    commercial_use: str
    files: list[str] = field(default_factory=list)
    sizes: dict[str, int] = field(default_factory=dict)

    @property
    def total_bytes(self) -> int:
        """Total size of the candidate files."""
        return sum(self.sizes.values())

    @property
    def license_display(self) -> str:
        """Licence text for the UI."""
        return self.license_id or "not declared"


def _get_json(url: str, data: Optional[bytes] = None) -> object:
    """Fetch JSON from the Hub.

    Args:
        url: Absolute https://huggingface.co URL.
        data: Optional request body, which makes the call a POST.

    Raises:
        MetadataError: On any network, HTTP, or decoding failure.
    """
    if not url.startswith(_HF_HOST + "/"):
        raise MetadataError(f"Refusing to contact a non-Hugging Face URL: {url}")

    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            raise MetadataError(
                "That repository is private or gated. Tessera can only add "
                "publicly downloadable models."
            ) from e
        if e.code == 404:
            raise MetadataError(
                "No such model on Hugging Face. Check the repository id — "
                "it looks like 'owner/name'."
            ) from e
        raise MetadataError(f"Hugging Face returned HTTP {e.code}.") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise MetadataError(f"Could not reach Hugging Face: {e}") from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise MetadataError(f"Unexpected response from Hugging Face: {e}") from e


def _declared_license(payload: dict) -> Optional[str]:
    """Extract the declared licence tag from a model payload."""
    card = payload.get("cardData") or {}
    for value in (card.get("license"), payload.get("license")):
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            return str(value[0]).strip()

    for tag in payload.get("tags", []):
        if isinstance(tag, str) and tag.startswith("license:"):
            return tag.split(":", 1)[1].strip()
    return None


def fetch_model_metadata(
    repo_id: str,
    family_id: str,
    revision: Optional[str] = None,
) -> HFModelMetadata:
    """Look up a repository and classify it for download.

    Args:
        repo_id: Repository identifier, ``owner/name``.
        family_id: Architecture family the user says this model belongs to.
        revision: Optional commit SHA or tag. Defaults to the repository's
            current head, which is then pinned.

    Returns:
        HFModelMetadata: Resolved metadata, licence already classified.

    Raises:
        MetadataError: If the id is malformed, the family is unsupported,
            the repository cannot be read, or it holds no loadable files.
    """
    repo_id = (repo_id or "").strip().strip("/")
    if not _REPO_ID_RE.match(repo_id):
        raise MetadataError(
            f"'{repo_id}' is not a Hugging Face repository id. "
            "Expected the form 'owner/name', for example "
            "'depth-anything/Depth-Anything-V2-Base'."
        )

    family = get_family(family_id)
    if family is None:
        raise MetadataError(
            f"'{family_id}' is not an architecture family Tessera can load."
        )

    # blobs=true so the listing carries file sizes — needed for the size
    # guard in build_user_entry() and for the Models table.
    payload = _get_json(f"{_HF_HOST}/api/models/{repo_id}?blobs=true")
    if not isinstance(payload, dict):
        raise MetadataError("Unexpected response from Hugging Face.")

    resolved = revision or payload.get("sha")
    if not resolved:
        raise MetadataError("Hugging Face did not report a commit for that model.")

    allowed = tuple(s for s in family.allowed_suffixes if s in ALLOWED_EXTENSIONS)
    files: list[str] = []
    sizes: dict[str, int] = {}
    for sibling in payload.get("siblings", []):
        name = sibling.get("rfilename")
        if not name or not name.endswith(allowed):
            continue
        files.append(name)
        size = sibling.get("size")
        if isinstance(size, int):
            sizes[name] = size

    if not files:
        raise MetadataError(
            f"That repository holds no files Tessera can use for the "
            f"{family.display_name} family (expected "
            f"{', '.join(allowed)})."
        )

    license_id = _declared_license(payload)
    metadata = HFModelMetadata(
        repo_id=repo_id,
        revision=str(resolved),
        license_id=license_id,
        commercial_use=classify_license(license_id),
        files=files,
        sizes=sizes,
    )
    logger.info(
        "Resolved Hugging Face model: repo=%s, revision=%s, license=%s (%s), "
        "files=%d",
        metadata.repo_id,
        metadata.revision,
        metadata.license_display,
        metadata.commercial_use,
        len(metadata.files),
    )
    return metadata


def fetch_digests(metadata: HFModelMetadata) -> dict[str, str]:
    """Resolve a SHA-256 digest for every file in ``metadata``.

    LFS-tracked files carry their digest in the Hub's ``paths-info``
    response. Small non-LFS files are downloaded and hashed locally.

    Args:
        metadata: Result of :func:`fetch_model_metadata`.

    Returns:
        dict[str, str]: Digest per file path.

    Raises:
        MetadataError: If any file's digest cannot be established — a model
            that cannot be verified is not added.
    """
    body = json.dumps({"paths": metadata.files}).encode("utf-8")
    payload = _get_json(
        f"{_HF_HOST}/api/models/{metadata.repo_id}/paths-info/{metadata.revision}",
        data=body,
    )
    if not isinstance(payload, list):
        raise MetadataError("Unexpected paths-info response from Hugging Face.")

    entries = {e.get("path"): e for e in payload if isinstance(e, dict)}
    digests: dict[str, str] = {}

    for path in metadata.files:
        entry = entries.get(path)
        if entry is None:
            raise MetadataError(f"Hugging Face did not report a digest for {path}.")

        lfs_oid = (entry.get("lfs") or {}).get("oid")
        if lfs_oid:
            digests[path] = str(lfs_oid)
            continue

        size = entry.get("size", 0)
        if size > _INLINE_HASH_MAX_BYTES:
            raise MetadataError(
                f"{path} has no published checksum and is too large to "
                f"verify by download ({size} bytes). Tessera will not add a "
                f"model it cannot verify."
            )

        url = f"{_HF_HOST}/{metadata.repo_id}/resolve/{metadata.revision}/{path}"
        try:
            with urllib.request.urlopen(url, timeout=_TIMEOUT_SECONDS) as response:
                content = response.read(_INLINE_HASH_MAX_BYTES + 1)
        except (urllib.error.URLError, TimeoutError) as e:
            raise MetadataError(f"Could not download {path} to verify it: {e}") from e

        if len(content) > _INLINE_HASH_MAX_BYTES:
            raise MetadataError(f"{path} is larger than reported; refusing to add.")
        digests[path] = hashlib.sha256(content).hexdigest()

    return digests


def suggest_model_id(repo_id: str) -> str:
    """Derive a manifest model id from a repository id.

    Args:
        repo_id: Repository identifier, ``owner/name``.

    Returns:
        str: A lower-cased, hyphenated id derived from the repository name.
    """
    name = repo_id.split("/")[-1].lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return cleaned[:64] or "user-model"


def build_user_entry(
    metadata: HFModelMetadata,
    family_id: str,
    model_id: Optional[str] = None,
    variant_id: Optional[str] = None,
    min_vram_gb: float = 0.0,
    max_total_bytes: int = _DEFAULT_MAX_TOTAL_BYTES,
) -> dict:
    """Build a manifest entry for a user-added model.

    Args:
        metadata: Result of :func:`fetch_model_metadata`.
        family_id: Architecture family this model belongs to.
        model_id: Optional explicit manifest id; derived from the repository
            name when omitted.
        variant_id: Optional variant within the family (e.g. ``"vitb"``).
        min_vram_gb: Minimum VRAM to report, if known.
        max_total_bytes: Refuse entries larger than this.

    Returns:
        dict: A manifest entry, digests included, ready to persist.

    Raises:
        MetadataError: If the model is too large or cannot be verified.
    """
    if metadata.total_bytes > max_total_bytes:
        raise MetadataError(
            f"That model is {metadata.total_bytes / 1e9:.1f} GB, above "
            f"Tessera's {max_total_bytes / 1e9:.0f} GB limit for added models."
        )

    digests = fetch_digests(metadata)
    family = get_family(family_id)

    entry = {
        "model_id": model_id or suggest_model_id(metadata.repo_id),
        "repo_id": metadata.repo_id,
        "revision": metadata.revision,
        "description": (
            f"{family.display_name if family else family_id} "
            f"(added from Hugging Face)"
        ),
        "license": metadata.license_id or "not declared",
        "license_url": f"{_HF_HOST}/{metadata.repo_id}",
        "commercial_use": metadata.commercial_use,
        "files": list(metadata.files),
        "sha256": digests,
        "size_bytes": metadata.total_bytes,
        "min_vram_gb": float(min_vram_gb),
        "family": family_id,
        "source": "user",
        "variants": [],
    }
    if variant_id:
        entry["variant"] = variant_id
    return entry
