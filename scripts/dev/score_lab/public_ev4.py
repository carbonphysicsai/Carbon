"""Read only the explicitly public EV4 copy; compact it for repeatable replay."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from carbon.battery import exam
from carbon.battery.calibration import SHAPES, frozen_calibration
from carbon.battery.challenge import PublicMaterial
from carbon.battery.value import contract as ct
from carbon.battery.value import decision as d
from carbon.battery.value import score_tuning as st

from .core import SCHEMA, LabRefused

# RES-08's frozen public reference copy, not an official or hidden role.
PUBLIC_REFERENCE_SHA256 = (
    "72ea300b42fe1ca4e54b9c6131cb126ca7217ebddd5f1dddca8044a7bcef2dbf"
)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _question(contract, scenario, candidates, refs):
    assessed = d.assess_reference(
        contract,
        scenario,
        candidates,
        {
            (c["id"], i): refs.get(ct.case_id(contract, scenario, c, i))
            for c in candidates
            for i in range(len(scenario["conditions"]))
        },
    )
    fallback = ct.candidate_id(contract["baseline"]["protocol"])
    return {
        "id": scenario["id"],
        "block": scenario["id"],
        "fallback": fallback,
        "weight": 1.0,  # EV4's historical uniform scenario diagnostic
        "actions": {
            aid: {
                "status": row["status"],
                "objective": row["objective"],
                "solves": len(scenario["conditions"]),
            }
            for aid, row in assessed.items()
        },
    }, assessed


def _predicted(contract, scenario, candidates, predictions):
    quantities = {}
    for candidate in candidates:
        for i in range(len(scenario["conditions"])):
            cid = ct.case_id(contract, scenario, candidate, i)
            raw = predictions.get(cid)
            if raw is None:
                return None, None
            quantities[(candidate["id"], i)] = d.measure(contract, raw)
    assessed = d.assess_predicted(contract, scenario, candidates, quantities)
    return {
        aid: {"objective": row["objective"], "feasible": row["feasible"]}
        for aid, row in assessed.items()
    }, assessed


def build(public_dir, repository):
    """One-time offline preparation; no inference, reconstruction or solves."""
    public_dir, repository = Path(public_dir), Path(repository)
    source = repository / "Business/research/value-metric-v2-stress/results.json"
    manifest = json.loads(source.read_text(encoding="utf-8"))
    names = manifest["real_members"]
    if len(names) != 100 or len(set(names)) != 100:
        raise LabRefused("ev4_member_manifest_mismatch")
    bundle_pins = {
        (r["folder"], r["file"]): r["sha256"]
        for r in manifest["inventory"]["bundle_manifest"]
    }
    reference_path = public_dir / "ev4-decision-references.jsonl"
    if _sha(reference_path) != PUBLIC_REFERENCE_SHA256:
        raise LabRefused("ev4_public_reference_digest_mismatch")
    contract, contract_digest = ct.load(
        repository / "carbon/battery/value/contracts/ev4-dev-proof-v1.json"
    )
    jobs = ct.decision_cases(contract)
    allowed = {job["case_id"] for job in jobs}
    refs = {}
    for line in reference_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["case_id"] in allowed and not row.get("refined"):
            refs[row["case_id"]] = row
    if set(refs) != allowed:
        raise LabRefused("ev4_public_reference_coverage")
    candidates = ct.candidates(contract)
    scenarios = {s["id"]: s for s in ct.scenarios(contract)}
    score_ids = [s["id"] for s in ct.scenarios(contract, "development")]
    value_ids = [s["id"] for s in ct.scenarios(contract, "verification")]
    questions, assessed = {}, {}
    for qid, scenario in scenarios.items():
        questions[qid], assessed[qid] = _question(contract, scenario, candidates, refs)
    score_case_ids = sorted(
        ct.case_id(contract, scenarios[qid], c, i)
        for qid in score_ids
        for c in candidates
        for i in range(len(scenarios[qid]["conditions"]))
        if refs[ct.case_id(contract, scenarios[qid], c, i)]["status"] == "OK"
    )
    # Only public records are used in this store. The frozen calibration and
    # public OCV table are repository-pinned, shared with the scorer.
    material = PublicMaterial.load(repository)
    ocv = {
        cid: float(
            np.interp(refs[cid]["inputs"]["soc0"], material.ocv_soc, material.ocv_v)
        )
        for cid in score_case_ids
    }
    tol, scales = frozen_calibration(repository)
    store = exam.CaseStore(refs, ocv, tol, scales, SHAPES, {})
    members = []
    used_bundles = {}
    for name in names:
        file = name + ".json.gz"
        path = public_dir / "experiment-predictions" / file
        expected = bundle_pins.get(("experiment-predictions", file))
        if expected is None or _sha(path) != expected:
            raise LabRefused("ev4_public_bundle_digest_mismatch")
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            bundle = json.load(handle)
        if bundle.get("member") != name:
            raise LabRefused("ev4_public_member_mismatch")
        predictions = {cid: bundle["predictions"].get(cid) for cid in allowed}
        score_predictions, value_losses = {}, {}
        for qid, scenario in scenarios.items():
            predicted, assessed_predicted = _predicted(
                contract, scenario, candidates, predictions
            )
            if qid in score_ids:
                score_predictions[qid] = predicted or {}
            if qid in value_ids:
                if assessed_predicted is None:
                    value_losses[qid] = None
                else:
                    pick = d.select(candidates, assessed_predicted)
                    value_losses[qid] = d.outcome(
                        contract,
                        candidates,
                        pick,
                        assessed[qid],
                        questions[qid]["fallback"],
                    )["decision_loss"]
        score_row = st.member_legs(contract, predictions, store, score_case_ids)
        # EV4 did not have Q3 design questions. Never synthesize a q leg from
        # the value-side questions or relabel this as battery v3 evidence.
        score_row["legs"]["q"] = None
        members.append(
            {
                "id": name,
                "recipe": name.rsplit("-s", 1)[0],
                "kind": "MODEL",
                "score_predictions": score_predictions,
                "score_row": score_row,
                "value_losses": value_losses,
            }
        )
        used_bundles[name] = expected
    # The cheap arm is a separate RES-08 public diagnostic. Its score-row
    # requires its own prediction bundle; absence is explicitly unmeasured.
    return {
        "schema": SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "assumption": {
            "job": "battery-EV4-CV-onset-proxy",
            "score_split": "EV4 development",
            "value_split": "EV4 verification",
            "q_leg": "UNMEASURED_NO_Q3_BANK",
            "cheap_rank": "UNMEASURED_NO_SCORE_BUNDLE",
        },
        "score_questions": {q: questions[q] for q in score_ids},
        "value_questions": {q: questions[q] for q in value_ids},
        "members": members,
        "provenance": {
            "contract_digest": contract_digest,
            "reference_sha256": PUBLIC_REFERENCE_SHA256,
            "bundle_sha256": used_bundles,
            "res08_results_sha256": _sha(source),
        },
    }
