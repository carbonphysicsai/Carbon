"""Optional trusted-controller evidence from two source-free full-tensor queries.

This does not admit a task, retrain a model, compare predictions, select a
tolerance or change historical single-query records. The caller owns retained
model custody, campaign admission, cancellation/reconciliation and collection.
Each query uses the maintained carrier and its ordinary budget/cleanup controls.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import sqlite3
import time
from dataclasses import dataclass

import numpy as np

from carbon.reconstruction.worker.model import WorkerImageIdentity

from .bundle_construction_worker import (
    MAX_STATE_BYTES,
    _accelerator_kwargs,
    _checked_binding,
    _digest,
    _exact_numeric_dtype,
    _infer_state,
    _private_controls_digest,
    _tensors,
    _trusted_allowlist,
    verify_direct_resource_policy,
)
from .bundle_graph_state import load
from .construction_recipe import RecipeRefused

SCHEMA = "carbon.source-free-inference-pair.v1"


def pair_identities(identity: str) -> tuple[str, str]:
    """Expose both ledger children before dispatch for cancellation/recovery."""
    if type(identity) is not str or not identity:
        raise RecipeRefused("inference_pair_identity_invalid")
    prefix = "inference-pair-" + hashlib.sha256(identity.encode()).hexdigest()
    return prefix + "-primary", prefix + "-repeat"


def _accounting(ledger, owner: str, identity: str) -> dict | None:
    with ledger.db() as db:
        row = db.execute(
            "SELECT state,reservation,actual,result FROM operations "
            "WHERE id=? AND owner=?",
            (identity, owner),
        ).fetchone()
    if row is None:
        return None
    return {
        "ledger_identity": identity,
        "state": row[0],
        "reservation": json.loads(row[1]),
        "actual": json.loads(row[2]) if row[2] is not None else None,
        "worker_result": json.loads(row[3]) if row[3] is not None else None,
    }


def _original(ledger, *, owner, identity, result, provenance, runner):
    if re.fullmatch(r"operation-[0-9a-f]{64}", result.worker_operation) is None:
        raise RecipeRefused("inference_pair_operation_binding_invalid")
    accounting = _accounting(ledger, owner, identity)
    if (
        accounting is None
        or accounting["state"] != "SUCCEEDED"
        or type(accounting["actual"]) is not dict
        or type(accounting["actual"].get("numerical_milliseconds")) is not int
        or accounting["actual"]["numerical_milliseconds"] < 0
        or type(accounting["worker_result"]) is not dict
        or accounting["worker_result"].get("operation") != result.worker_operation
    ):
        raise RecipeRefused("inference_pair_accounting_unavailable")
    controls = (
        _private_controls_digest(
            ledger,
            owner=owner,
            identity=identity,
            operation=result.worker_operation,
            provenance=provenance,
        )
        if runner is None
        else None
    )
    snapshot = ledger.root / result.worker_operation / "snapshot"
    originals = {}
    for name, ceiling in (("predictions.json", 16 * 1024**2), ("receipt.json", 65536)):
        path = snapshot / name
        if (
            snapshot.is_symlink()
            or path.is_symlink()
            or not path.is_file()
            or not 0 < path.stat().st_size <= ceiling
        ):
            raise RecipeRefused("inference_pair_original_unavailable")
        raw = path.read_bytes()
        if accounting["worker_result"].get("files", {}).get(name) != _digest(raw):
            raise RecipeRefused("inference_pair_original_changed")
        originals[name] = {
            "sha256": _digest(raw),
            "raw_base64": base64.b64encode(raw).decode(),
        }
    if (
        originals["predictions.json"]["sha256"] != result.predictions_digest
        or json.loads(base64.b64decode(originals["receipt.json"]["raw_base64"]))
        != result.receipt
    ):
        raise RecipeRefused("inference_pair_original_changed")
    return {
        "worker_operation": result.worker_operation,
        "controls_digest": controls,
        "originals": originals,
        "accounting": accounting,
    }


@dataclass(frozen=True)
class InferencePairResult:
    evidence: dict


class InferencePairFailure(RuntimeError):
    """Incomplete measurement, with successful originals and failed cost kept.

    No scientific/candidate verdict is inferred from this wrapper. The caller
    retains the typed underlying error and ledger state, including RESERVED or
    unknown actual consumption, and reconciles before reuse/cleanup.
    """

    def __init__(self, phase, originals, attempts, cause):
        super().__init__("inference_pair_incomplete")
        self.phase = phase
        self.originals = originals
        self.attempts = attempts
        self.cause = cause


def _failure_accounting(ledger, owner, identity):
    try:
        return _accounting(ledger, owner, identity)
    except (ValueError, OSError, sqlite3.Error):
        # Failure to read accounting must not erase the carrier's actual error
        # or pretend its reservation was released or its cost was zero.
        return {
            "ledger_identity": identity,
            "state": "UNKNOWN",
            "reservation": None,
            "actual": None,
            "worker_result": None,
        }


def infer_frozen_pair(
    ledger,
    *,
    owner,
    identity,
    inference_image,
    recipe,
    challenge_binding,
    limits_document,
    state_bytes,
    expected_state_digest,
    inputs,
    expected_output_shape,
    expected_output_dtype,
    allowlist_bytes,
    seconds,
    total_seconds,
    accelerator=None,
    runner=None,
) -> InferencePairResult:
    """Run two actual full-tensor queries of one already validated inert model.

    The registered full-tensor query is unchanged; logical rows are not forward
    calls or independently timed cases. The supplied pair identity must be new
    within this campaign. Old ledger identities are refused, never replayed.
    """
    identities = pair_identities(identity)
    binding = _checked_binding(recipe, challenge_binding)
    verify_direct_resource_policy(binding, limits_document)
    policy = limits_document["reconstruction_resource_policy"]
    if (
        type(inference_image) is not WorkerImageIdentity
        or type(state_bytes) is not bytes
        or not 0 < len(state_bytes) <= MAX_STATE_BYTES
        or _digest(state_bytes) != expected_state_digest
        or type(inputs) is not np.ndarray
        or inputs.ndim < 1
        or not len(inputs)
        or type(expected_output_shape) is not tuple
        or not expected_output_shape
        or any(type(n) is not int or n < 1 for n in expected_output_shape)
        or expected_output_shape[0] != len(inputs)
        or not _exact_numeric_dtype(expected_output_dtype, expected_output_dtype)
        or type(seconds) is not int
        or not 40 <= seconds <= policy["inference_wall_seconds_max"]
        or type(total_seconds) is not int
        or not 40 <= total_seconds <= policy["total_reconstruction_wall_seconds_max"]
    ):
        raise RecipeRefused("inference_pair_binding_invalid")
    load(state_bytes, recipe, _trusted_allowlist(allowlist_bytes))
    accelerator_kwargs = _accelerator_kwargs(accelerator)
    for child in identities:
        if _accounting(ledger, owner, child) is not None:
            raise RecipeRefused("inference_pair_identity_already_used")
    fixed_inputs = inputs.copy()
    fixed_inputs.flags.writeable = False
    inputs_digest = _digest(_tensors(inputs=fixed_inputs))
    provenance = (
        "DIRECT_GRAPH_PUBLIC_INFERENCE"
        if recipe.to_dict()["source"]["kind"] == "graph"
        else "DIRECT_BUNDLE_PUBLIC_INFERENCE"
    )
    started = time.monotonic()
    originals = {}
    for phase, child in zip(("primary", "repeat"), identities, strict=True):
        try:
            remaining = math.floor(total_seconds - (time.monotonic() - started))
            if remaining < 40:
                raise RecipeRefused("inference_pair_deadline_reached")
            result = _infer_state(
                ledger,
                owner=owner,
                identity=child,
                inference_image=inference_image,
                recipe=recipe,
                binding=binding,
                state=state_bytes,
                state_digest=expected_state_digest,
                inputs=fixed_inputs,
                expected_output_shape=expected_output_shape,
                expected_output_dtype=expected_output_dtype,
                measure_query=True,
                allowlist_bytes=allowlist_bytes,
                input_name=(
                    "inputs/forcing"
                    if provenance == "DIRECT_GRAPH_PUBLIC_INFERENCE"
                    else "inputs/x"
                ),
                provenance=provenance,
                seconds=min(seconds, remaining),
                runner=runner,
                **accelerator_kwargs,
            )
            if (
                result.receipt.get("inputs_digest") != inputs_digest
                or result.state_digest != expected_state_digest
                or result.recipe_digest != recipe.digest
                or any(
                    v["worker_operation"] == result.worker_operation
                    for v in originals.values()
                )
            ):
                raise RecipeRefused("inference_pair_operation_binding_invalid")
            originals[phase] = _original(
                ledger,
                owner=owner,
                identity=child,
                result=result,
                provenance=provenance,
                runner=runner,
            )
            if time.monotonic() - started > total_seconds:
                raise RecipeRefused("inference_pair_deadline_reached")
        except Exception as error:
            raise InferencePairFailure(
                phase,
                originals.copy(),
                {
                    name: _failure_accounting(ledger, owner, key)
                    for name, key in zip(("primary", "repeat"), identities, strict=True)
                },
                error,
            ) from error
    return InferencePairResult(
        {
            "schema": SCHEMA,
            "execution_boundary": (
                "C03_DOCKER" if runner is None else "TEST_ONLY_LOCAL_RUNNER"
            ),
            "recipe_digest": recipe.digest,
            "state_digest": expected_state_digest,
            "inputs_digest": inputs_digest,
            "inference_image_id": inference_image.image_id,
            "inference_operation_attempts": 2,
            "logical_prediction_rows_per_operation": len(fixed_inputs),
            "logical_prediction_row_attempts": 2 * len(fixed_inputs),
            "forward_calls": None,
            "elapsed_seconds": time.monotonic() - started,
            "primary": originals["primary"],
            "repeat": originals["repeat"],
            "scientific_qualification": False,
            "official_eligible": False,
        }
    )
