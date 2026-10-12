"""Synthetic arithmetic/custody only, not contact or customer evidence."""

import copy
import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline import bolted_rehearsal as joint
from carbon.design_search import bolted_budget as bb
from carbon.design_search import budget_registration as br
from carbon.design_search import equal_budget as eb
from carbon.design_search import tasks
from carbon.development_comparison import portfolio_baselines as pb

DOCS = (
    Path(__file__).parents[2] / "docs/development/challenge_pipeline/bolted-rehearsal"
)


def case():
    return joint.case(joint.actions()[40], joint.conditions()[0], 1)


def history():
    sections = []
    for stage in joint.STEPS:
        increments = []
        for i in (1, 2):
            increments.append(
                {
                    "increment": i,
                    "converged": True,
                    "step_complete": i == 2,
                    "signed_gaps_mm": [-0.01, 0.002 * i],
                    "relative_slips_mm": [0.001 * i, -0.002 * i],
                    "normal_contact_n": [3000, 4000],
                    "bolt_forces_n": [5000, 6000],
                    "stress_mpa": [10, 20],
                    "stress_volumes_mm3": [3, 1],
                    "displacement_mm": -0.01 * i,
                    "external_force_n": [100, 0, 200],
                    "support_force_n": [-100, 0, -200],
                    "external_moment_nmm": [0, 1000, 0],
                    "support_moment_nmm": [0, -1000, 0],
                }
            )
        sections.append(
            {
                "stage": stage,
                "source_sha256": "a" * 64,
                "declared_increments": 2,
                "increments": increments,
            }
        )
    return sections


def export(*, needs_opening=False):
    designs = {f"a{i}": joint.actions()[i] for i in range(3)}
    contexts = joint.conditions()
    task = tasks.task(
        "representative-toy",
        identity={
            "challenge": "representative-bolted-toy",
            "contract_version": "synthetic-v1",
            "action_grammar": {
                "schema": tasks.GRAMMAR_SCHEMA,
                "version": "synthetic-v1",
                "variables": [
                    {"name": k, "type": "integer", "min": lo, "max": hi, "step": step}
                    for k, (lo, hi), step in zip(
                        joint.FIELDS, joint.BOUNDS, (2, 15, 4, 4000)
                    )
                ],
                "rules": [],
            },
            "optimizer": {"class": "exhaustive", "version": "v1"},
            "query_budget": 12,
            "seed": 0,
            "observer_version": joint.PINS["observer"],
            "reference_bank": "synthetic-not-physical-evidence",
        },
        conditions=[{"id": c["id"], "stratum": c["id"]} for c in contexts],
        strata={c["id"]: {"p": 0.25, "q": 0.25, "w": 0.25} for c in contexts},
        candidates=list(designs),
        actions=designs,
        objective={
            "quantity": "bolt_force_n",
            "unit": "N",
            "sense": "min",
            "aggregate": "worst",
        },
        limits=[
            {
                "quantity": "opening_mm" if needs_opening else "clamp_n",
                "unit": "mm" if needs_opening else "N",
                "op": "<=" if needs_opening else ">=",
                "value": 0.1 if needs_opening else 10000,
            }
        ],
    )
    rows, reference = [], []
    for name, a in designs.items():
        for c in contexts:
            row = joint.case(a, c, 1)
            hand = joint.hand_calculation(
                row, bolt_stiffness_n_per_mm=1000, member_stiffness_n_per_mm=4000
            )
            rows.append(
                {
                    "candidate": name,
                    "condition": c["id"],
                    "case": row,
                    "bolt_stiffness_n_per_mm": 1000,
                    "member_stiffness_n_per_mm": 4000,
                }
            )
            reference.append(
                {
                    "candidate": name,
                    "condition": c["id"],
                    "values": {**hand["values"], "opening_mm": 0.05},
                }
            )
    body = {
        "scope": joint.SCOPE,
        "family": joint.FAMILY,
        "questions": [
            {"case": "representative-toy", "task": task, "reference": reference}
        ],
        "rows": rows,
        "costs": {k: None for k in pb.COST_FIELDS},
    }
    return {**body, "export_digest": joint.digest(body)}


def reseal(raw):
    raw["export_digest"] = joint.digest(
        {k: v for k, v in raw.items() if k != "export_digest"}
    )
    return raw


def replay():
    registration = bb.proposal()
    caps = bb.validate(registration)
    return eb.seal(
        {
            "schema": eb.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "evidence_scope": "REPRESENTATIVE",
            "customer_result": False,
            "challenge": joint.FAMILY,
            "source_digest": "sha256:" + "b" * 64,
            "decision_rule_id": "synthetic-only",
            "objective": {"direction": "min", "unit": "toy"},
            "cost_basis": "ASSUMPTION",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "registrations": {
                "solver_search": "toy",
                "model_screen": "toy",
                "baseline_screen": "toy",
                "cost_plan": bb.REGISTRATION_ID,
            },
            "budgets": [caps.cap(joint.FAMILY, t).time_compute for t in br.TIERS],
            "jobs": [
                {
                    "job_id": "toy",
                    "cluster_id": "toy",
                    "candidates": [
                        {
                            "design_id": "a",
                            "reference": {"status": "FEASIBLE", "value": 1},
                            "solve_cost": {"wall_s": 100, "core_s": 100},
                            "planning_bound": {"wall_s": 100, "core_s": 100},
                            "screen_rank": {"model": 0, "baseline": 0},
                        }
                    ],
                    "solver_order": ["a"],
                    "screen_cost": {
                        "model": {"wall_s": 1, "core_s": 1},
                        "baseline": {"wall_s": 1, "core_s": 1},
                    },
                }
            ],
        }
    )


def test_closed_deterministic_representative_space():
    assert len(joint.actions()) == 81
    assert len({joint.digest(a) for a in joint.actions()}) == 81
    assert joint.geometry(joint.actions()[0]) == joint.actions()[0]
    assert joint.actions() == joint.actions()
    for bad in (
        {**joint.actions()[0], "hidden": 1},
        {**joint.actions()[0], "bolt_diameter_mm": 7},
        {**joint.actions()[0], "bolt_diameter_mm": True},
    ):
        with pytest.raises(ValueError):
            joint.geometry(bad)


def test_panel_exact_reuse_and_geometry_disjoint_train():
    r = case()
    panel = joint.panel(
        [r["action"], r["action"]], rungs=[1, 2], completed=[r], scheduled=[]
    )
    assert len(panel["cases"]) == 8
    assert sum(x["reuse"] == "COMPLETED" for x in panel["cases"]) == 1
    assert not panel["dispatchable"] and not panel["customer_result"]
    changed = copy.deepcopy(r)
    changed["pins"]["observer"] = "bad"
    with pytest.raises(ValueError):
        joint.validate_case(changed)
    with pytest.raises(ValueError, match="conflicting"):
        joint.panel([r["action"]], rungs=[1], completed=[r], scheduled=[r])
    train = joint.train_plan([r["action"], joint.actions()[0]], [r])
    assert len(train["cases"]) == 4
    assert all(x["action"] != r["action"] for x in train["cases"])


def test_deck_keeps_contact_and_explicit_unsolved_lock_gap():
    d = joint.deck(case(), normal_penalty_mpa_per_mm=1000, stick_slope_mpa_per_mm=100)
    assert not d["dispatchable"]
    assert "TYPE=SURFACE TO SURFACE" in d["files"]["model.inp"]
    assert "*PRE-TENSION SECTION,SURFACE=BOLT_CUT_1" in d["files"]["model.inp"]
    assert "*CLOAD" in d["files"]["assembly-step.inc"]
    assert "HUMAN_INPUT" in d["files"]["service-step.template"]
    assert "hold the solved" in d["files"]["service-step.template"]
    with pytest.raises(ValueError):
        joint.deck(case(), normal_penalty_mpa_per_mm=0, stick_slope_mpa_per_mm=100)


def test_observer_all_increments_signs_balance_and_no_verdict():
    result = joint.observe(case(), history())
    assert len(result["rows"]) == 6
    assert result["rows"][0]["stress_mean_mpa"] == 12.5
    assert result["rows"][1]["opening_mm"] == 0.004
    assert result["rows"][1]["slip_mm"] == 0.004
    assert result["rows"][1]["force_balance_n"] == 0
    assert result["buyer_verdict"] == "UNRESOLVED"
    assert not result["qualified"] and not result["customer_result"]


@pytest.mark.parametrize(
    "problem",
    ["drop", "reorder", "source", "incomplete", "negative-stress", "unaligned"],
)
def test_observer_rejects_incomplete_or_malformed_history(problem):
    h = history()
    if problem == "drop":
        h[0]["increments"].pop()
    elif problem == "reorder":
        h.reverse()
    elif problem == "source":
        h[0]["source_sha256"] = "unknown"
    elif problem == "incomplete":
        h[-1]["increments"][-1]["step_complete"] = False
    elif problem == "negative-stress":
        h[0]["increments"][0]["stress_mpa"][0] = -1
    else:
        h[0]["increments"][0]["normal_contact_n"].append(1)
    with pytest.raises(ValueError):
        joint.observe(case(), h)


def test_reference_failure_never_becomes_candidate_failure():
    for field, value in (("converged", False), ("normal_contact_n", [-1, 4])):
        h = history()
        h[0]["increments"][0][field] = value
        result = joint.observe(case(), h)
        assert result["status"] == "REFERENCE_FINDING"
        assert result["buyer_verdict"] == "UNRESOLVED"


def test_hand_calculation_distinguishes_preload_scatter_from_friction():
    row = case()
    hand = joint.hand_calculation(
        row, bolt_stiffness_n_per_mm=1000, member_stiffness_n_per_mm=4000
    )
    assert hand["phi"] == 0.2
    assert sum(hand["bolt_force_per_bolt_n"]) == pytest.approx(
        2 * joint.preload(row) + 0.2 * row["condition"]["opening_n"]
    )
    assert not {"opening_mm", "slip_mm", "stress_mean_mpa"} & set(hand["values"])
    assert hand["buyer_verdict"] == "UNRESOLVED"
    low = joint.case(joint.actions()[0], joint.conditions()[1], 1)
    assert joint.preload(low) == 4000
    assert joint.hand_calculation(
        low, bolt_stiffness_n_per_mm=1, member_stiffness_n_per_mm=1000
    )["outside_closed_contact"]


def test_comparator_partial_safety_abstains_and_exports_query_cost():
    report = joint.compare(export(needs_opening=True))
    assert report["V4"] == "NOT_DEMONSTRATED"
    assert report["decision"]["summary"]["abstentions"] == 1
    assert report["decision"]["summary"]["selected_infeasible"] == 0
    screen = report["equal_budget_screening"]
    assert screen["candidate_rankings"][0]["ranked_feasible"] == []
    assert len(screen["candidate_rankings"][0]["unranked_abstentions"]) == 3
    assert screen["query_cost"]["cpu_s"] >= 0
    assert screen["fold_fit_cost"]["cpu_s"] == 0
    assert report["retained_cost_status"] == "UNMEASURED"
    assert report["pointwise"]["quantities"]["clamp_n"]["mae"] == 0


def test_comparator_supported_toy_decision_and_lineage():
    report = joint.compare(export())
    assert report["decision"]["summary"]["exact_pick_agreement_rate"] == 1
    raw = export()
    raw["rows"][0]["case"]["action"]["preload_max_n"] = 12000
    with pytest.raises(ValueError, match="physical"):
        joint.compare(reseal(raw))
    raw = export()
    raw["scope"] = "CUSTOMER"
    with pytest.raises(ValueError):
        joint.compare(reseal(raw))
    raw = export()
    raw["costs"]["money_eur"] = -1
    with pytest.raises(ValueError, match="nonnegative"):
        joint.compare(reseal(raw))
    raw = export()
    raw["questions"][0]["task"]["objective"]["unit"] = "changed"
    with pytest.raises(ValueError, match="altered"):
        joint.compare(reseal(raw))
    raw = export()
    t = raw["questions"][0]["task"]
    t["identity"]["action_grammar"]["variables"][0]["type"] = "number"
    t["task_digest"] = tasks.digest({k: v for k, v in t.items() if k != "task_digest"})
    with pytest.raises(ValueError, match="canonical digest"):
        joint.compare(reseal(raw))


def test_kit_requires_full_history_and_actual_coverage():
    domain = {
        "scope": joint.SCOPE,
        "action_bounds": dict(zip(joint.FIELDS, joint.BOUNDS)),
        "condition_ids": [c["id"] for c in joint.conditions()],
        "observables": joint.OUTPUTS,
        "observer": joint.PINS["observer"],
        "history": joint.STEPS,
    }
    assert joint.kit_domain(domain, [case()])
    domain["history"] = ["service"]
    assert not joint.kit_domain(domain, [case()])


def test_isolated_budget_and_representative_replay():
    p = bb.proposal()
    assert bb.validate(p).cap(joint.FAMILY, "base").solver_evaluations == 8
    with pytest.raises(br.BudgetRegistrationError):
        br.validate(p)
    with pytest.raises(eb.EqualBudgetError, match="proposal"):
        eb.compare(replay(), bootstrap_replicates=100, confidence=0.95, seed=0)
    report = eb.compare(
        replay(), bootstrap_replicates=100, confidence=0.95, seed=0, registration=p
    )
    assert report["evidence_scope"] == joint.SCOPE and not report["customer_result"]
    assert report["curves"][1]["solver_evaluation_limit"] == 8
    body = {k: v for k, v in replay().items() if k != "panel_digest"}
    body["jobs"][0]["candidates"][0]["reference"] = {
        "status": "UNRESOLVED",
        "value": None,
    }
    report = eb.compare(
        eb.seal(body), bootstrap_replicates=100, confidence=0.95, seed=0, registration=p
    )
    assert (
        report["status"] == "UNRESOLVED_PANEL"
        and report["evidence_scope"] == joint.SCOPE
    )
    p["evidence_scope"] = "PRODUCTION"
    with pytest.raises(br.BudgetRegistrationError):
        bb.validate(p)
    body["evidence_scope"] = "CUSTOMER"
    with pytest.raises(eb.EqualBudgetError, match="non-customer"):
        eb.compare(
            eb.seal(body),
            bootstrap_replicates=100,
            confidence=0.95,
            seed=0,
            registration=bb.proposal(),
        )


def test_docs_sources_pilot_and_no_earned_readiness():
    inputs = json.loads((DOCS / "inputs.json").read_text())
    assert len(inputs["sources"]) == 4
    assert inputs["P"] is None and inputs["w"] is None
    assert all(r["readiness_test"] and r["customer_replaces"] for r in inputs["inputs"])
    pilot = json.loads((DOCS / "measurement-pilot.json").read_text())
    assert pilot["cap_eur"] == 10 and not pilot["run_authorized"]
    assert [
        v * 1.37 for v in pilot["time_hypotheses"]["total_serial_host_h_low_base_high"]
    ] == pytest.approx(pilot["compute_component_eur_low_base_high"])
    pointers = json.loads((DOCS / "readiness-binding.json").read_text())
    assert [r["item"] for r in pointers["items"]] == list(range(1, 8))
    assert all(
        r["state"] == "PLANNED" and r["owner"] and r["gap"] for r in pointers["items"]
    )
    for r in pointers["items"]:
        assert (DOCS.parents[3] / r["pointer"].split(":")[0]).exists()


def test_cli_outputs_only_representative_proposals(capsys):
    assert joint.main(["actions"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["scope"] == joint.SCOPE and not out["customer_result"]
