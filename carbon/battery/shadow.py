"""The battery shadow scorer (M2): submissions scored on committed private pools.

A submission arrives the way every Carbon submission does: a declarative
strategy plus the contract digest its author compiled against. The scorer:
1. admits it through `compile_submission`, which refuses another Challenge's
   contract, an unknown field or a digest mismatch by name;
2. rebuilds it from the recipe on pinned public TRAIN v1 with Carbon's seed;
3. predicts only the committed pool's inputs;
4. gates and scores it with the OD-2 provisional DEVELOPMENT rule.

The pool is built only from `CommittedBatch` values, so nothing is scored on a
batch whose fingerprint was not committed first. Rotation retires the oldest
batch in the seed journal, which then permits its reveal.

The scorer is a shadow: it grants no reward, frontier, qualification or chain
authority. The public projection is built field by field from an allow-list.
It never filters the internal record, so a new internal field cannot leak by
omission. Before reveal it carries no case id, input, reference value,
per-case error, seed or root.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from carbon.reconstruction.challenge_contracts import compile_submission

from . import exam
from .challenge import CAPACITY_CYCLES, CHALLENGE, GRID_POINTS, INPUTS
from .compile import rebuild
from .recipes import to_predictions
from .seeds import CommittedBatch

PREPARE_PATH = "docs/development/evidence/exam-design-2026-09-24/prepare.json"
PREPARE_SHA256 = "b23e3151d21eadd7fa63950ad41f6460d9fe21d75a345f825adcfa44182d5e99"
SHAPES = {
    "voltage_v": (GRID_POINTS,),
    "temperature_c": (GRID_POINTS,),
    "plating_margin_v": (),
    "capacity_ah": (len(CAPACITY_CYCLES),),
}
PUBLIC_SCHEMA = "carbon.battery.shadow-result.public.v1"
#: A rebuild in the scoring process itself: fresh model, Carbon's seed, pinned
#: TRAIN, but not the validator's isolated reconstruction worker.
DIRECT_RECONSTRUCTION = {"backend": "DIRECT_TRUSTED_PROCESS", "validator_path": False}


def frozen_calibration(root="."):
    """The campaign's frozen tolerances and TRAIN scales (OD-2), pinned by the
    exact bytes of the committed prepare record."""
    body = (Path(root) / PREPARE_PATH).read_bytes()
    if hashlib.sha256(body).hexdigest() != PREPARE_SHA256:
        raise ValueError("the frozen calibration does not match its pinned digest")
    prep = json.loads(body)
    tol = exam.Tolerances(
        **{
            k: prep["tolerances"][k]
            for k in (
                "tau_v0",
                "tau_t0",
                "tau_vmax",
                "tau_vmin",
                "q_bound",
                "v_max",
                "v_min",
            )
        }
    )
    return tol, prep["scales"]


class ShadowPool:
    """The OD-2 screening pool over committed private batches."""

    def __init__(self, committed, references, material, journal, *, root="."):
        if not committed or not all(type(c) is CommittedBatch for c in committed):
            raise TypeError("a pool is built only from committed batches")
        rule = exam.DEVELOPMENT_RULE
        # A committed batch is the pool's batch: whole, so its hidden
        # duplicates are always inside what is scored.
        if any(len(c.batch.cases) != rule["screening_batch_size"] for c in committed):
            raise ValueError("each committed batch holds exactly one screening batch")
        self.committed, self.journal = list(committed), journal
        twins = {d: o for c in committed for d, o in c.batch.duplicates}
        refs = dict(references)
        for dup, orig in twins.items():
            if orig in refs:
                refs[dup] = dict(refs[orig], case_id=dup, duplicate_of=orig)
        ocv = {
            cid: float(np.interp(r["inputs"]["soc0"], material.ocv_soc, material.ocv_v))
            for cid, r in refs.items()
            if r.get("inputs")
        }
        tol, scales = frozen_calibration(root)
        self.store = exam.CaseStore(refs, ocv, tol, scales, SHAPES, twins)
        self.inputs = {c: dict(x) for batch in committed for c, x in batch.batch.cases}
        self.pool = exam.ScreeningPool(
            [[c for c, _ in batch.batch.cases] for batch in committed],
            rule["rotate_after_admitted"],
            rule["active_batches"],
        )
        self.bank = exam.PredictionBank()
        self.material = material

    def score(
        self, submission_id, strategy, contract_digest, seed, *, reconstruction=None
    ):
        """Admit, rebuild and score one submission; returns the internal
        record and its public projection.

        `reconstruction` names how the rebuild actually ran. It defaults to
        this process, and the record says so: a direct rebuild is never
        reported as the validator's isolated reconstruction path."""
        admitted = compile_submission(strategy, contract_digest=contract_digest)
        recipe = admitted.construction
        model, stats = rebuild(recipe, self.material, seed)

        def predict(ids):
            x = np.array([[self.inputs[c][k] for k in INPUTS] for c in ids], float)
            return to_predictions(model.predict(x), ids)

        self.bank.predictors[submission_id] = predict
        before = self.pool.pool_version
        record = self.pool.score(submission_id, self.bank, self.store)
        if self.pool.pool_version != before:
            self.journal.retire(self.committed[self.pool.retired[-1]])
        internal = {
            **record,
            "submission_id": submission_id,
            "recipe_digest": recipe.recipe_digest,
            "contract_digest": admitted.contract_digest,
            "params_sha256": stats["params_sha256"],
            "seed": seed,
            "reconstruction": dict(reconstruction or DIRECT_RECONSTRUCTION),
        }
        return internal, public_projection(internal, self.committed)


def _round(value, digits=4):
    return None if value is None else round(float(value), digits)


def public_projection(internal, committed):
    """The only shape a shadow result is published in (allow-list)."""
    active = internal["active_batches"]
    return {
        "schema": PUBLIC_SCHEMA,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "submission_id": str(internal["submission_id"]),
        "recipe_digest": str(internal["recipe_digest"]),
        "contract_digest": str(internal["contract_digest"]),
        "pool_version": int(internal["pool_version"]),
        "pool_fingerprints": [committed[b].fingerprint for b in active],
        "eligible": bool(internal["eligible"]),
        "score": _round(internal["score"]),
        "important_score": _round(internal["important_score"]),
        "gates_failed": sorted(str(g) for g in internal["gate_failures"]),
        "cases": {
            "scored": int(internal["n_scored"]),
            "reference_invalid": int(internal["n_reference_invalid"]),
            "failed_infra": int(internal["n_failed_infra"]),
        },
        "reconstruction": {
            "backend": str(internal["reconstruction"]["backend"]),
            "validator_path": bool(internal["reconstruction"]["validator_path"]),
        },
        "evidence": "DEVELOPMENT_SHADOW",
        "rule": exam.DEVELOPMENT_RULE["status"],
        "qualification": False,
        "reward": False,
    }
