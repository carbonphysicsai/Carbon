"""VERIFY-R on the Q3 quiz: the verify-aware leg `v` (VERIFY-AWARE-SCORE-01)
replayed on the battery tuning quiz's already-solved decision lattices.

Each Q3 scenario is one VERIFY-R question. Its action bank is the scenario's
117-point lattice (`quiz.q3_candidates`), each point's reference outcome
taken from the quiz's settled references. A model commits its top `k`
lattice points: the points it predicts feasible, best predicted objective
first, under the contract's selector and tie order (`decision.select`), so
`k = 1` is exactly its Q3 pick. The commitment is a function of the model's
stored quiz predictions alone, which were written before any reference was
read (`challenge_validator.tuning predict`). The verifier replays the
already-solved panels in that order under the registered budget, and the
leg is `v = 1 / (1 + mean bounded regret)` (`verify_aware.aggregate`).
Nothing is solved here.

The owner's values (OWNER-VERIFY-R-DEFAULTS-01, 2026-10-11, "approve VERIFY-R
defaults"): `k` at 1, 3 and 5 (3 picked), a budget of `k` complete panels at
120 s wall each, and a regret unit of 1,200 s (EV4's false-acceptance cost of
10 times its 120 s minimum useful improvement).

Replay conventions, reported with every result:
- every verified panel is charged the registered 120 s allotment (wall and
  core), so the budget is exactly k panels (SCORE-PROOF-01 amendment 9).
  The reference solve's recorded `wall_s` measures the solver host, not the
  model, and charging it stopped lists early on slow (near-limit, refined)
  lattice points, a bias against near-limit picks. Panels whose recorded
  solve ran over the allotment are counted (`panels_over_allotment`), and
  records with no `wall_s` are counted (`cost_unmeasured_panels`);
- inference overhead is not charged: the stored quiz predictions carry no
  timings (`overhead_charged: false`).

DEVELOPMENT only. No solve, no LIVE authority, no threshold adopted.
"""

from __future__ import annotations

from carbon.design_search import verify_aware as va

from . import contract as ev
from . import decision as d
from . import quiz

#: OWNER-VERIFY-R-DEFAULTS-01 (2026-10-11): the registered k points, the
#: per-panel wall allotment and the regret unit.
K_POINTS = (1, 3, 5)
WALL_PER_PANEL_S = 120.0
REGRET_UNIT_S = 1200.0
#: The leg name for each k (`score_tuning.LEGS`).
LEG = {k: f"v{k}" for k in K_POINTS}
#: Registry v10's `v3s` (SCORE-PROOF-01 amendment 11): v3, except that a
#: question on which any verified pick is INFEASIBLE costs `KAPPA` regret
#: units instead of its bounded regret (at most one). KAPPA is a registered
#: candidate value; adopting it is HUMAN_INPUT.
HARSH_K = 3
HARSH_LEG = "v3s"
KAPPA = 3.0

SELECTOR_VERSION = "q3-predicted-feasible-selector-order-v1"
REFERENCE_POLICY = "battery-quiz-q3-settled-references"
ELIGIBILITY_POLICY = "none-in-leg: a score rule's gates apply separately"
POPULATION = "battery-tuning-quiz-q3-scenarios"
PROPOSAL = "q3-lattice-117"
WEIGHT_LAW = "equal-per-scenario"
OBJECTIVE = {"direction": "min", "unit": "s"}
ZERO = {"wall_s": 0.0, "core_s": 0.0}

#: decision.assess_reference status -> VERIFY-R reference state.
_STATES = {
    d.FEASIBLE: "FEASIBLE",
    d.INFEASIBLE: "INFEASIBLE",
    d.UNRESOLVED: "UNRESOLVED",
}


class VerifyQuizRefused(ValueError):
    """The quiz cannot be replayed under the registered rule."""


def rule(k):
    """The registered VERIFY-R rule at `k` (owner values only)."""
    if k not in K_POINTS:
        raise VerifyQuizRefused(f"verify_r_k_not_registered:{k}")
    return va.register_rule(
        {
            "schema": va.RULE_SCHEMA,
            "rule_id": f"VERIFY-R-Q3-k{k}",
            "evidence_class": "DEVELOPMENT",
            "selector_version": SELECTOR_VERSION,
            "k": k,
            "budget": {
                "complete_panels": k,
                "wall_s": k * WALL_PER_PANEL_S,
                "core_s": k * WALL_PER_PANEL_S,
            },
            "objective": dict(OBJECTIVE),
            "regret_unit": {"value": REGRET_UNIT_S, "unit": "s"},
            "reference_policy_id": REFERENCE_POLICY,
            "eligibility_policy_id": ELIGIBILITY_POLICY,
            "population_id": POPULATION,
            "proposal_id": PROPOSAL,
            "weight_law_id": WEIGHT_LAW,
        }
    )


def _lattice(contract, scenario, candidates=None):
    """The question's bank: the Q3 lattice, or `candidates` (for example EV4's
    35 actions on a public development question, PUBLIC-DEV-DECISIONS-01)."""
    candidates = quiz.q3_candidates() if candidates is None else candidates
    return [
        (candidate, ev.case_id(contract, scenario, candidate, 0))
        for candidate in candidates
    ]


def _cost(record, unmeasured, over):
    """The registered allotment, charged for every panel (amendment 9); the
    recorded solve time is only counted."""
    wall = record.get("wall_s") if isinstance(record, dict) else None
    if not isinstance(wall, (int, float)) or wall <= 0:
        unmeasured.append(1)
    elif wall > WALL_PER_PANEL_S:
        over.append(1)
    charge = {"wall_s": WALL_PER_PANEL_S, "core_s": WALL_PER_PANEL_S}
    return dict(charge), dict(charge)


def question(
    contract, the_rule, scenario, grid_refs, unmeasured, over, candidates=None
):
    """One scenario as a sealed VERIFY-R question over its bank."""
    lattice = _lattice(contract, scenario, candidates)
    candidates = [c for c, _ in lattice]
    refs = {
        (c["id"], 0): grid_refs[case_id]
        for c, case_id in lattice
        if case_id in grid_refs
    }
    reference = d.assess_reference(contract, scenario, candidates, refs)
    bank = []
    for candidate, case_id in lattice:
        row = reference[candidate["id"]]
        record = grid_refs.get(case_id)
        state = _STATES.get(row["status"])
        if state is None:
            failed = isinstance(record, dict) and record.get("status") == "FAILED_INFRA"
            state = "FAILED_INFRA" if failed else "MISSING"
        planning, actual = _cost(record, unmeasured, over)
        bank.append(
            {
                "action_id": candidate["id"],
                "action_family_id": PROPOSAL,
                "reference": {
                    "status": state,
                    "value": row["objective"] if state == "FEASIBLE" else None,
                },
                "planning_bound": planning,
                "actual_cost": actual,
            }
        )
    return va.seal_question(
        {
            "schema": va.QUESTION_SCHEMA,
            "question_id": scenario["id"],
            "action_family_id": PROPOSAL,
            "rule_digest": the_rule["rule_digest"],
            "reference_policy_id": REFERENCE_POLICY,
            "population_id": POPULATION,
            "proposal_id": PROPOSAL,
            "weight_law_id": WEIGHT_LAW,
            "weight": 1.0,
            "objective": dict(OBJECTIVE),
            "bank": bank,
        }
    )


def ordered_actions(contract, scenario, grid_predictions, candidates=None):
    """The model's lattice points it predicts feasible, in the selector's
    order (lowest predicted objective, ties by lower c1 then c2), or None
    when a prediction is missing. Its first entry is `decision.select`'s."""
    lattice = _lattice(contract, scenario, candidates)
    quantities = {}
    for candidate, case_id in lattice:
        outputs = grid_predictions.get(case_id)
        if outputs is None:
            return None
        quantities[(candidate["id"], 0)] = d.measure(contract, outputs)
    candidates = [c for c, _ in lattice]
    predicted = d.assess_predicted(contract, scenario, candidates, quantities)
    pool = sorted(
        (d._tie_key(c, predicted[c["id"]]["objective"]), c["id"])
        for c in candidates
        if predicted[c["id"]]["feasible"]
        and predicted[c["id"]]["objective"] is not None
    )
    return [cid for _, cid in pool]


def _reliability(losses):
    from .score_proof import value_ceiling

    c = value_ceiling(losses) if losses else {"status": "NOT_MEASURABLE"}
    keep = (
        "status",
        "members",
        "informative_questions",
        "per_question_reliability",
        "reliability",
        "tau_ceiling",
    )
    return {k: c[k] for k in keep if k in c}


def harsh_leg(rows, kappa=KAPPA):
    """`v3s` from one member's k = 3 question results: `1 / (1 + mean loss)`,
    where a question with an INFEASIBLE verified pick costs `kappa` and every
    other question its bounded regret. None when any question is unscored
    (never a partial leg)."""
    losses = []
    for row in rows:
        if row["score"] is None:
            return None
        harsh = "INFEASIBLE" in row.get("attempt_statuses", ())
        losses.append(kappa if harsh else row["score"])
    if not losses:
        return None
    return 1.0 / (1.0 + sum(losses) / len(losses))


def member_scores(contract, scenarios, predictions, refs, receipt_id, candidates=None):
    """Every member's VERIFY-R result at each registered k.

    `scenarios`: the quiz's Q3 entries (each with `scenario_id`, `condition`
    and `grid`); `predictions`: member to {case_id: outputs}; `refs`: the
    quiz's settled references by case id; `receipt_id`: the quiz digest the
    predictions were made for. Returns `{leg: {member: v or None}}` and the
    diagnostics."""
    from carbon.battery import quiz_stratum as qs

    if not scenarios:
        raise VerifyQuizRefused("verify_r_no_q3_scenario")
    legs, diagnostics = {}, {}
    orders = {}
    for entry in scenarios:
        scenario = entry if candidates is not None else qs.scenario(entry)
        for member, member_predictions in predictions.items():
            orders[(member, scenario["id"])] = ordered_actions(
                contract, scenario, member_predictions, candidates
            )
    for k in K_POINTS:
        the_rule = rule(k)
        unmeasured, over = [], []
        questions = [
            question(
                contract,
                the_rule,
                entry if candidates is not None else qs.scenario(entry),
                refs,
                unmeasured,
                over,
                candidates,
            )
            for entry in scenarios
        ]
        ids = [q["question_id"] for q in questions]
        legs[LEG[k]], stopped, statuses, losses = {}, 0, {}, []
        for member in sorted(predictions):
            commitments, receipts = {}, {}
            for qid in ids:
                order = orders[(member, qid)]
                if order is None:
                    continue
                commitment = va.commit_list(
                    {
                        "schema": va.COMMIT_SCHEMA,
                        "model_id": member,
                        "question_id": qid,
                        "action_family_id": PROPOSAL,
                        "selector_version": SELECTOR_VERSION,
                        "ordered_actions": order[:k],
                        "commitment_receipt_id": f"{receipt_id}:{member}",
                    }
                )
                commitments[qid] = commitment
            for qid in ids:
                receipts[qid] = {
                    "origin": "independent_verifier",
                    "commitment_digest": (
                        commitments[qid]["commitment_digest"]
                        if qid in commitments
                        else "none"
                    ),
                    "startup_cost": dict(ZERO),
                    "search_cost": dict(ZERO),
                }
            eligibility = {
                qid: {"policy_id": ELIGIBILITY_POLICY, "verdict": "PASS"} for qid in ids
            }
            report = va.score_model(
                the_rule, member, questions, commitments, receipts, eligibility
            )
            legs[LEG[k]][member] = report["aggregate"]["v"]
            if k == HARSH_K:
                legs.setdefault(HARSH_LEG, {})[member] = harsh_leg(report["questions"])
            if all(row["score"] is not None for row in report["questions"]):
                losses.append([row["score"] for row in report["questions"]])
            for row in report["questions"]:
                stopped += bool(row.get("budget_stopped"))
                statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        diagnostics[LEG[k]] = {
            "rule_digest": the_rule["rule_digest"],
            "questions": len(ids),
            "members": len(predictions),
            "budget_stopped": stopped,
            "question_statuses": dict(sorted(statuses.items())),
            "cost_unmeasured_panels": len(unmeasured),
            "panels_over_allotment": len(over),
            "overhead_charged": False,
            # The power check: the leg's own per-question reliability and the
            # tau a perfect score could reach against it (SCORE-CEILING-01).
            "reliability": _reliability(losses),
        }
    diagnostics[HARSH_LEG] = {
        "of": LEG[HARSH_K],
        "kappa": KAPPA,
        "rule": "a question with an INFEASIBLE verified pick costs kappa regret units",
    }
    return legs, diagnostics
