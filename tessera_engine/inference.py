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

"""Wire payloads in, adapter calls out.

Everything that is *not* model-specific lives here: validating the
request, resolving weight paths against the cache root, decoding arrays,
enforcing the result ceiling and encoding the response. The adapters below
this layer see decoded arrays and verified paths, and know nothing about
HTTP.

That split is what lets the adapters move from the add-on largely
unchanged, and what lets this whole path be tested without a GPU — every
failure mode below except the inference itself is reachable with no torch
installed.

Spec: SPEC-TS-0023 (FR-005, FR-006, FR-007, FR-019, FR-025 – FR-029,
SEC-003, SEC-009)

Public API:
    reconstruct — handler for POST /reconstruct
    vision — handler for POST /vision
    register_adapter — make an adapter available to the engine
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict

from . import MAX_FACES, MAX_VERTICES
from .codec import CodecError, decode_vision_input, encode_array, encode_mesh_result
from .errors import EngineFault
from .runtime import EngineRuntime, probe_device

logger = logging.getLogger("tessera_engine")

#: Stages ``/vision`` serves (FR-029). Anything else is refused by name
#: rather than attempted.
VISION_STAGES = ("segment", "depth", "features")

#: Registered adapters, keyed by the model id the add-on asks for. Adapters
#: register themselves at import; nothing is discovered from disk, and
#: nothing beside a weight file is ever imported (SEC-009).
_RECONSTRUCTION: Dict[str, Callable] = {}
_VISION: Dict[str, Callable] = {}


def register_adapter(kind: str, model_id: str, fn: Callable) -> None:
    """Register one adapter implementation.

    Args:
        kind: ``"reconstruction"`` or ``"vision"``.
        model_id: The id the add-on names in ``weight_paths``.
        fn: The implementation.
    """
    table = _RECONSTRUCTION if kind == "reconstruction" else _VISION
    table[model_id] = fn


def _require_weights(runtime: EngineRuntime, payload: Any) -> Dict[str, Any]:
    """Resolve every weight path in the request against the cache root.

    Args:
        runtime: Engine runtime holding the launch-argument cache root.
        payload: The decoded request body.

    Returns:
        ``{model_id: resolved Path}``.

    Raises:
        EngineFault: ``bad_request`` if the field is malformed,
            ``weights_missing`` if a path is absent or outside the root.
    """
    raw = payload.get("weight_paths")
    if not isinstance(raw, dict) or not raw:
        raise EngineFault(
            "bad_request",
            "weight_paths must be a non-empty object",
            field="weight_paths",
        )
    return {
        model_id: runtime.resolve_weight_path(path, model_id)
        for model_id, path in raw.items()
    }


def _check_vram(required_gb: float) -> None:
    """Refuse before loading when the device cannot hold the model (FR-019).

    Failing here rather than inside the allocator is the difference
    between a message naming two numbers and a CUDA traceback.
    """
    device = probe_device()
    if not device.available:
        raise EngineFault(
            "load_failed",
            f"No usable CUDA device: {device.name}.",
        )
    if required_gb and device.free_vram_gb < required_gb:
        raise EngineFault(
            "insufficient_vram",
            "Not enough free GPU memory for this model.",
            required_gb=round(float(required_gb), 2),
            available_gb=device.free_vram_gb,
        )


def reconstruct(runtime: EngineRuntime, payload: dict, request_id: str) -> dict:
    """Handle ``POST /reconstruct`` (FR-005, FR-025 – FR-028).

    Args:
        runtime: Engine runtime.
        payload: Decoded request body.
        request_id: Identity of this request.

    Returns:
        The response body, every field of which the add-on needs to build
        a ``StandardMesh`` and a ``ReconstructionResult`` (FR-026).

    Raises:
        EngineFault: For every documented failure in §10.1.
    """
    weights = _require_weights(runtime, payload)

    raw_inputs = payload.get("inputs")
    if not isinstance(raw_inputs, list) or not raw_inputs:
        raise EngineFault(
            "bad_request", "inputs must be a non-empty array", field="inputs"
        )
    try:
        inputs = [decode_vision_input(item, i) for i, item in enumerate(raw_inputs)]
    except CodecError as exc:
        raise EngineFault("bad_request", str(exc), field=exc.field) from exc

    model_id = next(iter(weights))
    adapter = _RECONSTRUCTION.get(model_id)
    if adapter is None:
        raise EngineFault(
            "load_failed",
            f"This engine has no adapter for {model_id!r}.",
            model_id=model_id,
        )

    _check_vram(float(payload.get("required_vram_gb") or 0.0))

    try:
        result = adapter(weights[model_id], inputs)
    except EngineFault:
        raise
    except MemoryError as exc:
        raise EngineFault("insufficient_vram", str(exc)) from exc
    except Exception as exc:
        # A partially-loaded adapter must not survive into the next
        # request (EC-005). The adapter owns its own teardown; this makes
        # sure the failure is reported as a load failure rather than as an
        # internal error the add-on cannot act on.
        logger.exception("adapter %s failed", model_id)
        raise EngineFault(
            "load_failed", f"{model_id}: {exc}", model_id=model_id
        ) from exc

    vertices = result["vertices"]
    faces = result["faces"]
    if len(vertices) > MAX_VERTICES or len(faces) > MAX_FACES:
        raise EngineFault(
            "mesh_too_large",
            "The generated mesh exceeds what this protocol carries.",
            vertex_count=int(len(vertices)),
            face_count=int(len(faces)),
        )

    metadata = dict(result.get("metadata") or {})
    metadata.setdefault("vertex_count", int(len(vertices)))
    metadata.setdefault("face_count", int(len(faces)))
    try:
        return encode_mesh_result(
            vertices,
            faces,
            result.get("vertex_colors"),
            metadata,
            warnings=result.get("warnings"),
            source_adapter=result.get("source_adapter", model_id),
        )
    except CodecError as exc:
        # The adapter returned something this contract cannot carry. That
        # is an engine bug, not a caller error.
        logger.error("adapter %s produced an unencodable result: %s", model_id, exc)
        raise EngineFault("internal", str(exc)) from exc


def vision(runtime: EngineRuntime, payload: dict, request_id: str) -> dict:
    """Handle ``POST /vision`` (FR-006, FR-029).

    Args:
        runtime: Engine runtime.
        payload: Decoded request body.
        request_id: Identity of this request.

    Returns:
        The per-stage response shape of FR-029.

    Raises:
        EngineFault: ``unsupported_stage`` for anything outside
            :data:`VISION_STAGES`, plus the shared failures.
    """
    stage = payload.get("stage")
    if stage not in VISION_STAGES:
        raise EngineFault(
            "unsupported_stage",
            f"Stage must be one of {', '.join(VISION_STAGES)}.",
            stage=stage,
        )
    weights = _require_weights(runtime, payload)
    model_id = next(iter(weights))
    adapter = _VISION.get(f"{stage}:{model_id}") or _VISION.get(model_id)
    if adapter is None:
        raise EngineFault(
            "load_failed",
            f"This engine has no {stage} adapter for {model_id!r}.",
            model_id=model_id,
        )

    _check_vram(float(payload.get("required_vram_gb") or 0.0))

    try:
        result = adapter(stage, weights[model_id], payload.get("image"))
    except EngineFault:
        raise
    except Exception as exc:
        logger.exception("vision adapter %s failed at %s", model_id, stage)
        raise EngineFault(
            "load_failed", f"{model_id}: {exc}", model_id=model_id
        ) from exc

    if stage == "segment":
        return {"mask": result["mask"], "coverage": float(result["coverage"])}
    if stage == "depth":
        return {"depth_map": encode_array(result["depth_map"], "float32")}
    return {"features": encode_array(result["features"], "float32")}
