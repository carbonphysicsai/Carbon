"""Scoring a window's design questions (VALIDATOR-23 slice 3c): report-only.

Under rule `v2-bank-design`, each screening window carries `k` battery Q3
design questions (slice 3b). For a scored submission, the retained model
predicts every question's truth jobs (the 117-point lattice at the
question's scenario), each prediction is projected as v8 projects truth
(`battery_q3_v8._projection`), and the window's questions are scored through
the neutral design score (#827, `design_search.score_bridge`) under the
registered rule below.

**The rule** is the q leg of OWNER-BATTERY-SCORE-RULE-01 (#815): battery v8
Q3 decision regret, with v8's refined-truth settle (the bank's references are
settled truth) and pessimistic UNRESOLVED pricing, exactly as `score_tuning`
computed it for the curves (`tests/cpu/test_challenge_validator_design_scoring`
pins the parity). Registered by the Test Lead, 2026-10-08 (slice 3 decision
D3). Its costs are read from EV4's contract, never restated here.

**Failures, typed:** a model's missing or malformed prediction is the
candidate's (`INELIGIBLE`); a reference or bank failure is `VOID` or
`FAILED_INFRA`, never a penalty. The daemon retries FAILED_INFRA.

**Cross-window evidence** (`evidence`): per miner, the per-question loss
against a registered good reference (the exhaustive optimizer on the settled
reference itself), summed per question (questions cluster by the shared
bank), and the one-sided exact sign test over the clusters, as the power
report's method (`one-sided-exact-sign-test-by-shared-bank.v1`). Only a
window's own q is a score candidate (VALIDATOR-26's rule v3 decides); the
pooled evidence is a diagnostic until the owner approves its score use.

Operator-only: nothing here reaches a miner surface.

    python -m carbon.challenge_validator.design_scoring report --config DEPLOYMENT.json
    python -m carbon.challenge_validator.design_scoring evidence --config DEPLOYMENT.json --hotkey SS58
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
RULE_VERSION = "battery-q3-v8-q.v1"
#: The rule's registration record. The bridge's rule body has an exact key
#: set, so who registered it, when and for what use is recorded here.
RULE_RECORD = {
    "rule_version": RULE_VERSION,
    "registered_by": "Test Lead",
    "registered_on": "2026-10-08",
    "authority": (
        "OWNER-BATTERY-SCORE-RULE-01 (#815), its q leg; VALIDATOR-23 slice 3 "
        "decision D3"
    ),
    "score_use": (
        "a window's own q only, from VALIDATOR-26's rule v3; the pooled "
        "cross-window evidence is a diagnostic until the owner approves its "
        "score use"
    ),
}
EVIDENCE_SCHEMA = "carbon.battery.design-evidence.v1"
EVIDENCE_METHOD = "one-sided-exact-sign-test-by-shared-bank.v1"
#: The truth job inputs a model predicts (`battery.quiz_document`).
GRID = ("c1", "c2", "t_amb_c", "soc0")


@functools.cache
def battery_q3_rule(repository=REPOSITORY):
    """The registered battery Q3 score rule (#827's `register_score_rule`)."""
    from carbon.battery import quiz_stratum as qs
    from carbon.design_search import battery_q3_v8 as v8
    from carbon.design_search import indexed
    from carbon.design_search import score_bridge as bridge

    contract = qs.contract(repository)
    costs = contract["mistake_costs"]
    return bridge.register_score_rule(
        {
            "schema": bridge.RULE_SCHEMA,
            "version": RULE_VERSION,
            "challenge": v8.JOB,
            "contract_version": contract["version"],
            "objective": {
                "quantity": "time_to_cv_onset_s",
                "unit": "s",
                "sense": "min",
            },
            "value_equivalence": {
                "quantity": "time_to_cv_onset_s",
                "unit": "s",
                "tolerance": 0,
                "rule": indexed.EQUIVALENCE_RULE,
            },
            "loss": {
                "unit": costs["unit"],
                "regret_multiplier": costs["regret_per_minimum_useful_improvement"],
                "regret_divisor": contract["minimum_useful_improvement_s"],
            },
            "kind_costs": {
                "SELECTED_INFEASIBLE": costs["false_acceptance"],
                "MISSED_OPPORTUNITY": costs["missed_opportunity"],
                "SELECTED_UNRESOLVED": costs["false_acceptance"],
                "ABSTENTION_UNRESOLVED": costs["missed_opportunity"],
                "CORRECT_ABSTENTION": 0,
            },
            "question_aggregate": bridge.QUESTION_AGGREGATE,
            "q_transform": bridge.Q_TRANSFORM,
        }
    )


def _public(result):
    """What a window's report keeps of the bridge's result."""
    return {
        "status": result["status"],
        "cause": result.get("cause"),
        "eligible": result.get("eligible"),
        "q": result.get("q"),
        "mean_loss": result.get("mean_loss"),
        "mean_regret": result.get("mean_regret"),
        "per_question": [
            {
                "question_id": row["question_id"],
                "outcome": row["outcome"],
                "loss": row["loss"],
            }
            for row in result.get("per_question") or []
        ],
    }


class BatteryQ3Measures:
    """The design measures a battery validator is given
    (`BatteryValidator.design_measures`): its truth jobs, then its scores."""

    def __init__(self, repository=REPOSITORY):
        from carbon.battery import quiz_stratum as qs

        self.repository = Path(repository)
        self.contract = qs.contract(self.repository)
        self.rule = battery_q3_rule(self.repository)

    def _grid(self, draw):
        from carbon.battery import quiz_stratum as qs
        from carbon.battery.value import quiz as bq

        return bq.q3_grid(self.contract, qs.scenario(draw))

    def inputs(self, designs):
        """`{case_id: inputs}`: every question's lattice jobs."""
        asked = {}
        for design in designs.values():
            for question in design["questions"].values():
                for job in self._grid(question["draw"]):
                    asked[job["case_id"]] = {k: job[k] for k in GRID}
        return asked

    def _panel(self, draw, outputs):
        """The model's panel: each candidate's prediction, projected. A
        candidate the model gave no output for is left out, so the bridge
        refuses the panel as the candidate's (INELIGIBLE)."""
        from carbon.battery.value import quiz as bq
        from carbon.design_search import battery_q3_v8 as v8

        rows = []
        for candidate, job in zip(bq.q3_candidates(), self._grid(draw), strict=True):
            found = outputs.get(job["case_id"])
            values = (
                None
                if not isinstance(found, dict)
                else v8._projection(self.contract, {"status": "OK", "outputs": found})
            )
            if values is not None:
                rows.append(
                    {
                        "candidate": candidate["id"],
                        "condition": "one-condition",
                        "values": values,
                    }
                )
        return rows

    @staticmethod
    def _questions(design):
        return [
            {
                "question_id": question_id,
                "task": question["task"],
                "reference": {
                    "status": question["reference"]["status"],
                    "panel": question["reference"]["panel"],
                },
            }
            for question_id, question in sorted(design["questions"].items())
        ]

    def score(self, design, panels, model_id):
        """One window's result through the bridge. `panels` maps question id
        to the model's panel."""
        from carbon.battery.worker import WorkerFailure
        from carbon.design_search import score_bridge as bridge

        try:
            sealed = bridge.seal_score_bank(self._questions(design))
        except bridge.ReferenceMaterialFailure:
            return {**_public({"status": "VOID"}), "cause": "reference_unavailable"}
        except bridge.InfrastructureFailure:
            raise WorkerFailure("design_bank_unavailable", candidate=False) from None
        rows = [
            {
                "question_id": question_id,
                "task_digest": question["task"]["task_digest"],
                "panel": panels[question_id],
            }
            for question_id, question in sorted(design["questions"].items())
        ]
        try:
            committed = bridge.commit_prediction_panels(model_id, rows)
        except bridge.CandidatePredictionFailure:
            return {
                **_public({"status": "INELIGIBLE", "eligible": False}),
                "cause": "q_candidate_failed",
            }
        result = bridge.evaluate_design_score(sealed, committed, self.rule)
        if result["status"] == "FAILED_INFRA":
            raise WorkerFailure("design_" + str(result.get("cause")), candidate=False)
        return _public(result)

    def measure(self, designs, predictions):
        """Each window's report entry, and the rule record."""
        found = {}
        for fingerprint, design in designs.items():
            panels = {
                question_id: self._panel(question["draw"], predictions)
                for question_id, question in design["questions"].items()
            }
            found[fingerprint] = self.score(design, panels, "design-candidate")
        return {"rule": RULE_RECORD, "batches": found}

    def reference_losses(self, designs):
        """The registered good reference's loss per question: the exhaustive
        optimizer on the settled reference panels themselves."""
        losses = {}
        for design in designs.values():
            panels = {
                question_id: question["reference"]["panel"]
                for question_id, question in design["questions"].items()
            }
            result = self.score(design, panels, "REFERENCE")
            for row in result["per_question"]:
                losses[row["question_id"]] = row["loss"]
        return losses


def evidence(reports, reference_losses):
    """One miner's pooled cross-window evidence from its measured design
    reports: the per-question loss minus the good reference's, summed per
    question (clustered by the shared bank), and the one-sided exact sign
    test that the miner does worse. A diagnostic only."""
    from carbon.design_search.power import _sign_test_p

    clusters, windows, per_window = {}, set(), []
    for report in reports:
        if report.get("state") != "MEASURED":
            continue
        for fingerprint, window in sorted(report["batches"].items()):
            per_window.append(
                {
                    "submission_id": report["submission_id"],
                    "fingerprint": fingerprint,
                    "status": window.get("status"),
                    "q": window.get("q"),
                }
            )
            if window.get("status") != "OK":
                continue
            windows.add(fingerprint)
            for row in window["per_question"]:
                question = row["question_id"]
                difference = row["loss"] - reference_losses.get(question, 0.0)
                clusters[question] = clusters.get(question, 0.0) + difference
    p_value, nonzero = _sign_test_p(clusters)
    return {
        "schema": EVIDENCE_SCHEMA,
        "method": EVIDENCE_METHOD,
        "diagnostic": True,
        "rule": RULE_RECORD,
        "windows": len(windows),
        "questions": len(clusters),
        "nonzero": nonzero,
        "p_value": p_value,
        "per_window": per_window,
    }


def install(target, repository=REPOSITORY):
    """Give a battery validator its design measures. Returns the target."""
    from carbon.battery.daemon import BatteryValidator

    if type(target) is not BatteryValidator:
        raise TypeError("a BatteryValidator is required")
    target.design_measures = BatteryQ3Measures(repository)
    return target


def report(target):
    """Measure the design questions of every scored submission that has no
    measured report yet, under the deployment's writer lock. Counts only."""
    from carbon.battery import deployment

    install(target, target.repository)
    states = {}
    with deployment.writer(target):
        with target.store.db() as db:
            scored = [r[0] for r in db.execute("SELECT submission_id FROM scores")]
        for submission_id in scored:
            result = target.design_report(submission_id)
            state = "NO_DESIGN" if result is None else result["state"]
            states[state] = states.get(state, 0) + 1
    return {"scored": len(scored), "states": states}


def miner_evidence(target, hotkey):
    """`evidence` for one miner's hotkey, from this validator's reports."""
    store = target.store
    reports = [
        r
        for r in store.design_reports()
        if (store.submission(r["submission_id"]) or {}).get("hotkey") == hotkey
    ]
    fingerprints = {f for r in reports for f in r.get("batches", {})}
    designs = {f: store.design(f) for f in fingerprints}
    designs = {f: d for f, d in designs.items() if d is not None}
    losses = BatteryQ3Measures(target.repository).reference_losses(designs)
    return {"hotkey": hotkey, **evidence(reports, losses)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.design_scoring")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("report").add_argument("--config", required=True)
    found = sub.add_parser("evidence")
    found.add_argument("--config", required=True)
    found.add_argument("--hotkey", required=True)
    args = parser.parse_args(argv)
    from carbon.battery import deployment

    target = deployment.validator(Path(args.config), repository=REPOSITORY)
    if args.command == "report":
        result = report(target)
    else:
        result = miner_evidence(target, args.hotkey)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    from carbon.challenge_validator.design_scoring import main as _main

    sys.exit(_main())


__all__ = ["RULE_RECORD", "BatteryQ3Measures", "battery_q3_rule", "evidence", "install"]
