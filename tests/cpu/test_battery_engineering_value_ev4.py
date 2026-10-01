"""EV4 and the Problem-C optimizer: fixture checks only (no PyBaMM, no network).

- the EV4 contract is valid, keeps EV2's decision rules and uses fresh
  conditions;
- the 100-member panel is unique, keeps EV2's members and compiles;
- H1's paired bootstrap is deterministic under the fixed seed;
- the optimizer's grids, Mode D, Mode X, member rule and budget refusals;
- pod outputs round-trip into an experiment root, and the whole EV4 +
  optimizer path runs end to end on a small fixture panel;
- the pod controls' budget, allowance and file-fetch checks.
"""

from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_engineering_value import (
    FixtureBackend,
    fixture_solver,
    outputs_for,
    scoring_refs,  # noqa: F401 - fixture
)

from carbon.battery.compile import compile_recipe
from carbon.battery.truth import TruthService
from carbon.battery.value import contract as ev
from carbon.battery.value import decision as d
from carbon.battery.value import hypotheses as hy
from carbon.battery.value import optimizer as op
from carbon.battery.value import panel as pn
from carbon.battery.value.experiment import Experiment
from scripts.dev.exam_design import value_phases, value_plans
from scripts.dev.exam_design.runpod import pod_control as pc

EV4_PATH = ev.CONTRACTS / "ev4-charge-protocol-selection.v1.json"
EV4, EV4_DIGEST = ev.load(EV4_PATH)
EV2, _ = ev.load(ev.CONTRACTS / "ev2-charge-protocol-selection.v1.json")
EV1, _ = ev.load()


# --- the contract ----------------------------------------------------------------------------


def test_ev4_contract_is_valid_and_keeps_ev2s_decision_rules():
    assert EV4["contract_id"] == "ev4-battery-charge-protocol-selection"
    assert EV4["status"] == "PROVISIONAL_DEVELOPMENT"
    assert EV4["case_prefix"] == "ev4" and EV4["panel"] == "ev4"
    for key in (
        "objective",
        "constraints",
        "minimum_useful_improvement_s",
        "mistake_costs",
        "baseline",
        "tie_rule",
        "design_variables",
        "reference",
        "models",
        "scoring_candidates",
        "data_scope",
        "operating_conditions",
    ):
        assert EV4[key] == EV2[key], key
    assert EV4["acceptance"]["rule_selection"] == EV2["acceptance"]["rule_selection"]
    assert len(ev.candidates(EV4)) == 35
    assert len(ev.decision_cases(EV4)) == 840 == EV4["budgets"]["reference_solves_max"]
    assert EV4["budgets"]["reconstructions_max"] == 100
    assert all(c["case_id"].startswith("ev4:") for c in ev.decision_cases(EV4))
    authority = EV4["authority"]
    assert not any(
        authority[k]
        for k in ("chain", "reward", "changes_testnet_rule", "qualification")
    )
    assert "I approve runpod use for EV4" in authority["record"]
    paired = EV4["acceptance"]["paired_comparison"]
    assert (paired["proposed_rule"], paired["deciding_rule"]) == (
        "dar-p0-r100-a0",
        "control-exam-v1",
    )
    assert (paired["replicates"], paired["rng_seed"], paired["level"]) == (
        10000,
        20261001,
        0.95,
    )


def test_ev4_contract_digest_is_the_preregistered_one():
    # BATTERY_ENGINEERING_VALUE_EV4.md records this digest; a change to the
    # contract after pre-registration must be a new, reported version.
    assert EV4_DIGEST == (
        "sha256:fedd753c0e7aa69d2fd4d6efbf3d877ac8eeb211859d9f32d76a61f38bbe38d1"
    )
    text = (
        REPOSITORY / "docs/development/BATTERY_ENGINEERING_VALUE_EV4.md"
    ).read_text()
    assert EV4_DIGEST in text


def test_ev4_conditions_are_fresh_and_as_registered():
    def conditions(contract, split=None):
        return {
            tuple(c) for s in ev.scenarios(contract, split) for c in s["conditions"]
        }

    assert all(len(s["conditions"]) == 1 for s in ev.scenarios(EV4))
    assert conditions(EV4, "development") == {
        (float(t), s) for t in (5, 14, 24, 34) for s in (0.12, 0.33, 0.48)
    }
    assert conditions(EV4, "verification") == {
        (float(t), s) for t in (9, 19, 29, 38) for s in (0.06, 0.22, 0.40)
    }
    assert not conditions(EV4) & (conditions(EV1) | conditions(EV2))


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda c: c["acceptance"]["paired_comparison"].update(
                proposed_rule="control-exam-v1"
            ),
            "paired_comparison",
        ),
        (
            lambda c: c["acceptance"]["paired_comparison"].update(replicates=0),
            "paired_comparison",
        ),
        (lambda c: c.update(panel="ev3"), "panel"),
    ],
)
def test_the_paired_comparison_is_refused_by_name(mutate, code):
    document = copy.deepcopy(EV4)
    mutate(document)
    with pytest.raises(ev.ContractError) as refused:
        ev.validate(document)
    assert refused.value.code == code


# --- the panel -------------------------------------------------------------------------------


def test_the_ev4_panel_has_100_unique_members_and_keeps_ev2s():
    members = pn.members("ev4")
    ids = [m for m, *_ in members]
    assert len(ids) == len(set(ids)) == 100 == EV4["budgets"]["reconstructions_max"]
    ev2 = pn.members("ev2")
    assert members[: len(ev2)] == ev2
    added = members[len(ev2) :]
    labels = {label for _m, label, *_ in added}
    assert len(added) == 85 and len(labels) == 70
    assert sum(1 for _m, _l, _s, seed in added if seed > 0) == 15
    assert {pn.family(s) for _m, _l, s, _seed in members} == {"mlp", "deeponet", "knn"}
    # Member ids keep the "<recipe>-s<seed>" form the seed-band code reads.
    assert all(m.rsplit("-s", 1)[0] == label for m, label, *_ in members)


def test_every_ev4_recipe_compiles():
    digests = set()
    for _member, _label, strategy, _seed in pn.members("ev4"):
        _, recipe = compile_recipe(strategy)
        digests.add(recipe.recipe_digest)
    assert len(digests) == 80  # EV2's 10 recipes and 70 added ones


# --- H1: the paired bootstrap ----------------------------------------------------------------


def test_vectorized_tau_b_equals_the_reference_implementation():
    rng = np.random.default_rng(7)
    for _ in range(20):
        x = rng.integers(0, 5, 12).astype(float)
        y = rng.integers(0, 4, 12).astype(float)
        assert hy.tau_b(x, y) == pytest.approx(d.kendall_tau_b(x.tolist(), y.tolist()))
    assert hy.tau_b([1.0, 1.0], [2.0, 3.0]) is None


def _bootstrap_inputs(n=30, k=12, seed=3):
    rng = np.random.default_rng(seed)
    quality = rng.normal(size=n)
    losses = np.clip(
        2.0 - quality[:, None] + rng.normal(scale=0.5, size=(n, k)), 0.0, None
    )
    losses[0, 0] = np.nan  # an undefined (unresolved) condition
    proposed = quality + rng.normal(scale=0.2, size=n)
    deciding = rng.normal(size=n)
    return proposed, deciding, losses


def test_paired_bootstrap_is_deterministic_with_the_fixed_seed():
    proposed, deciding, losses = _bootstrap_inputs()
    kwargs = {"replicates": 400, "seed": 20261001, "level": 0.95}
    first = hy.paired_bootstrap(proposed, deciding, losses, **kwargs)
    second = hy.paired_bootstrap(proposed, deciding, losses, **kwargs)
    assert first == second
    assert first["decision"] == hy.PROPOSED_BETTER
    assert first["interval"][0] > 0
    other = hy.paired_bootstrap(
        proposed, deciding, losses, replicates=400, seed=1, level=0.95
    )
    assert other["interval"] != first["interval"]
    # Swapping the rules flips the sign and the decision.
    flipped = hy.paired_bootstrap(deciding, proposed, losses, **kwargs)
    assert flipped["decision"] == hy.DECIDING_BETTER
    assert flipped["delta_tau"] == pytest.approx(-first["delta_tau"])


def test_an_interval_that_includes_zero_is_unresolved():
    proposed, _deciding, losses = _bootstrap_inputs()
    same = hy.paired_bootstrap(
        proposed, proposed, losses, replicates=50, seed=20261001, level=0.95
    )
    assert same["delta_tau"] == 0.0
    assert same["decision"] == hy.UNRESOLVED


# --- the optimizer: grids, Mode D, Mode X ------------------------------------------------------


def test_the_optimizer_grids_are_as_registered():
    assert len(op.C1) == 31 and op.C1[0] == 0.5 and op.C1[-1] == 2.0
    assert len(op.C2) == 33 and op.C2[0] == 0.2 and op.C2[-1] == 1.0
    assert len(op.DESIGNS) == 1023
    assert len(op.MODEL_CONDITIONS) == 32
    assert {t for t, _ in op.MODEL_CONDITIONS} == {
        5.0,
        10.0,
        15.0,
        20.0,
        25.0,
        30.0,
        35.0,
        40.0,
    }
    assert {s for _, s in op.MODEL_CONDITIONS} == {0.05, 0.20, 0.35, 0.50}
    assert len(op.VERIFY_CONDITIONS) == 90
    temps = sorted({t for t, _ in op.VERIFY_CONDITIONS})
    socs = sorted({s for _, s in op.VERIFY_CONDITIONS})
    assert len(temps) == 18 and temps[0] == 5.0 and temps[-1] == 40.0
    assert socs == [float(v) for v in np.linspace(0.05, 0.5, 5)]
    base = EV4["baseline"]["protocol"]
    assert (base["c1"], base["c2"]) in op.DESIGNS
    assert (op.K, op.MAX_MODE_D_SOLVES, op.MAX_MODE_X_SOLVES, op.MAX_TOTAL_SOLVES) == (
        50,
        540,
        250,
        1630,
    )
    envelope = EV4["operating_conditions"]["envelope"]
    for t, s in op.MODEL_CONDITIONS + op.VERIFY_CONDITIONS:
        assert envelope["t_amb_c"][0] <= t <= envelope["t_amb_c"][1]
        assert envelope["soc0"][0] <= s <= envelope["soc0"][1]


def synthetic_grid(quantity, member="m-s0"):
    """A grid document from `quantity(c1, c2, t_amb, soc0) -> (time, margin, peak)`."""
    q = {name: [] for name in op.QUANTITIES}
    for c1, c2 in op.DESIGNS:
        rows = [quantity(c1, c2, t, s) for t, s in op.MODEL_CONDITIONS]
        for name, column in zip(op.QUANTITIES, zip(*rows)):
            q[name].append(list(column))
    return op.grid_document(EV4, member, "sha256:x", 0, q)


def _world(c1, c2, t, s):
    rate = 0.55 * c1 + 0.45 * c2
    time = (1.0 - s) * 1500.0 / rate
    margin = 0.03 - 0.02 * c1 + 0.0005 * (t - 15.0)
    peak = t + 3.0 * c1 + 1.0 * c2
    return time, margin, peak


def test_mode_d_takes_the_lowest_worst_case_design_feasible_everywhere():
    grid = synthetic_grid(_world)
    result = op.mode_d(EV4, grid)
    assert result["status"] == "DESIGN"
    # Brute force over the same rule.
    best = None
    for c1, c2 in op.DESIGNS:
        rows = [_world(c1, c2, t, s) for t, s in op.MODEL_CONDITIONS]
        if all(r[0] <= 3480.0 and r[1] >= 0.0 and r[2] <= 45.0 for r in rows):
            key = (max(r[0] for r in rows), c1, c2)
            best = key if best is None or key < best else best
    assert (result["c1"], result["c2"]) == best[1:]
    assert result["predicted_worst_time_to_cv_s"] == best[0]


def test_mode_d_ties_go_to_lower_c1_then_c2_and_it_abstains_when_nothing_fits():
    flat = synthetic_grid(lambda c1, c2, t, s: (1000.0, 0.01, 30.0))
    tie = op.mode_d(EV4, flat)
    assert (tie["c1"], tie["c2"]) == (0.5, 0.2)
    # Feasible everywhere except one model condition: never chosen.
    partly = synthetic_grid(
        lambda c1, c2, t, s: (1000.0, -0.001 if (t, s) == (5.0, 0.05) else 0.01, 30.0)
    )
    assert op.mode_d(EV4, partly) == {"status": "ABSTAIN", "feasible_designs": 0}
    unreached = synthetic_grid(lambda c1, c2, t, s: (None, 0.01, 30.0))
    assert op.mode_d(EV4, unreached)["status"] == "ABSTAIN"


def test_mode_x_ranks_by_band_normalised_margin_and_caps_at_k():
    grid = synthetic_grid(_world)
    points = op.mode_x(EV4, grid)
    assert len(points) == op.K
    margins = [p["predicted_margin_bands"] for p in points]
    assert margins == sorted(margins)
    assert len({p["case_id"] for p in points}) == op.K
    bands = EV4["reference"]["uncertainty"]["bands"]
    first = points[0]
    expected = op.margins(EV4, first["predicted"])
    assert first["predicted_margin_bands"] == min(expected.values())
    assert expected["no_plating_onset"] == pytest.approx(
        first["predicted"]["plating_margin_v"] / bands["plating_margin_v"]
    )
    # Only predicted-feasible points are candidates.
    for p in points:
        assert op._predicted_pass(EV4, p["predicted"])
    with pytest.raises(op.OptimizerError) as refused:
        op.mode_x(EV4, grid, k=op.K + 1)
    assert refused.value.code == "budget_exceeded"


def test_verification_plans_refuse_to_exceed_the_maxima():
    designs = {
        f"m{i}": {"status": "DESIGN", "c1": op.C1[i], "c2": 0.2} for i in range(5)
    }
    plan = op.verification_plan(EV4, designs, {})
    assert plan["mode_d_solves"] == 6 * 90 == op.MAX_MODE_D_SOLVES
    too_many = {**designs, "m5": {"status": "DESIGN", "c1": op.C1[6], "c2": 0.2}}
    with pytest.raises(op.OptimizerError) as refused:
        op.verification_plan(EV4, too_many, {})
    assert refused.value.code == "budget_exceeded"
    grid = synthetic_grid(_world)
    points = op.mode_x(EV4, grid)
    plan = op.verification_plan(EV4, {}, {f"m{i}": points for i in range(5)})
    assert plan["mode_x_solves"] == 250
    assert len(plan["jobs"]) == 90 + 50  # the baseline, and Mode X points deduplicated
    with pytest.raises(op.OptimizerError):
        op.verification_plan(EV4, {}, {f"m{i}": points for i in range(6)})
    with pytest.raises(op.OptimizerError):
        op.verification_plan(EV4, {}, {"m": points + points[:1]})


def _results(rows):
    """A minimal EV4 result: member -> (control score, proposed score, loss)."""
    members, scores = {}, {}
    for m, (control, proposed, loss) in rows.items():
        members[m] = {
            "kind": "RECONSTRUCTED",
            "eligible": control is not None,
            "loss_development": loss,
            "loss_verification": loss,
        }
        scores[m] = {"control-exam-v1": control, "dar-p0-r100-a0": proposed}
    return {"summary": {"members": members}, "rule_scores": scores}


def test_the_member_rule_is_applied_as_registered():
    rows = {
        "a-s0": (-0.1, 0.5, 3.0),
        "b-s0": (-0.2, 0.9, 2.0),
        "c-s0": (-0.3, 0.4, 1.0),
        "d-s0": (-0.4, 0.3, 4.0),
        "knn-s0": (-0.5, 0.2, 5.0),
        "bad-s0": (None, 0.0, 0.0),  # ineligible: never selected
    }
    backbones = {m: ("knn" if m.startswith("knn") else "mlp") for m in rows}
    picks = op.select_members(_results(rows), backbones)
    assert [p["role"] for p in picks] == list(op.MEMBER_ROLES)
    assert [p["member"] for p in picks] == ["a-s0", "b-s0", "c-s0", "knn-s0", "d-s0"]
    # When the proposed rule's best is the deciding best, take its next best;
    # the lowest-loss member already chosen gives way to the next distinct one.
    rows["a-s0"] = (-0.1, 0.95, 0.5)
    picks = op.select_members(_results(rows), backbones)
    assert [p["member"] for p in picks] == ["a-s0", "b-s0", "c-s0", "knn-s0", "d-s0"]


# --- pod phases, import and the whole path -------------------------------------------------------


def test_truth_service_admission_stops_without_writing_records(tmp_path):
    jobs = [
        {"case_id": f"j{i}", "c1": 1.0, "c2": 0.6, "t_amb_c": 20.0, "soc0": 0.2}
        for i in range(5)
    ]
    service = TruthService(tmp_path / "r.jsonl", solver=fixture_solver, workers=1)
    # The admission window closes once two solves are recorded.
    summary = service.run(jobs, admit=lambda: len(service.records()) < 2)
    assert summary["not_admitted"] == 3
    assert len(service.records()) == 2


def test_plans_name_their_jobs_and_shard_deterministically(tmp_path):
    plans = value_plans.refs_plans(2)
    jobs = value_phases.reference_jobs(next(iter(plans.values())), REPOSITORY)
    shards = [value_phases.shard(jobs, i, 2) for i in range(2)]
    assert sorted(j["case_id"] for s in shards for j in s) == sorted(
        j["case_id"] for j in jobs
    )
    assert len(jobs) == 840 and len(shards[0]) == 420
    with pytest.raises(SystemExit):
        value_plans.refs_plans(4)
    for plan in value_plans.panel_plans(1).values():
        for path in plan["ship"][1:]:
            assert (REPOSITORY / path).is_file()


@pytest.fixture
def small_panel(monkeypatch):
    keep = {"mlp_half", "knn", "knn10"}  # four members: mlp_half has two seeds
    monkeypatch.setitem(
        pn.PANELS, "ev4", tuple(r for r in pn.PANELS["ev4"] if r[0] in keep)
    )
    monkeypatch.chdir(REPOSITORY)


def test_the_ev4_path_runs_end_to_end_through_pod_outputs(
    tmp_path, scoring_refs, small_panel  # noqa: F811
):
    # Pods: two reference shards and one panel shard.
    plan = {"contract": str(EV4_PATH.relative_to(REPOSITORY)), "shards": 2}
    outs = []
    for i in range(2):
        out = tmp_path / f"refs{i}"
        out.mkdir()
        value_phases.run_value_refs(
            {**plan, "shard": i, "max_workers": 2},
            str(out),
            solver=fixture_solver,
            host=lambda: {"cpu_quota": 2},
        )
        outs.append(out / "records.jsonl")
    panel_out = tmp_path / "panel"
    panel_out.mkdir()
    backend = FixtureBackend(scoring_refs)
    value_phases.run_value_panel(
        {"contract": plan["contract"]}, str(panel_out), backend=backend
    )
    assert json.loads((panel_out / "DONE.json").read_text())["done"]["written"] == 4

    # Local: freeze first, then import the pod outputs, write-once.
    experiment = Experiment(tmp_path / "ev4", repository=REPOSITORY)
    experiment.freeze(EV4_PATH)
    for records in outs:
        experiment.import_references(records)
    imported = experiment.import_predictions(panel_out / "predictions")
    assert len(imported["imported"]) == 4
    again = experiment.import_predictions(panel_out / "predictions")
    assert again == {"imported": [], "already_present": sorted(imported["imported"])}
    assert op.import_grids(experiment, panel_out / "grid")["imported"]
    status = experiment.status()
    assert status["references"]["terminal"] == 840 and not status["panel"]["missing"]

    results = experiment.evaluate()
    h = results["hypotheses"]
    assert set(h) == {"H1", "H2", "H3", "continuity"}
    assert h["H1"]["replicates"] == 10000 and h["H1"]["rng_seed"] == 20261001
    assert h["H1"]["decision"] in (
        hy.PROPOSED_BETTER,
        hy.DECIDING_BETTER,
        hy.UNRESOLVED,
    )
    assert set(results["families"]) == {"mlp", "knn"}
    report = (tmp_path / "ev4" / "results" / "report.md").read_text()
    assert report.startswith("# EV4") and "Pre-registered hypotheses" in report

    # The optimizer: select once, verify on "pods", report.
    selection = op.run_select(experiment)
    assert op.run_select(experiment) == selection  # never re-selected
    assert len(selection["jobs"]) <= op.MAX_MODE_D_SOLVES + op.MAX_MODE_X_SOLVES
    jobs_dir = tmp_path / "plans"
    value_plans.write(
        value_plans.verify_plans(1, str(tmp_path / "ev4" / "optimizer" / "jobs.json")),
        jobs_dir,
    )
    verify_out = tmp_path / "verify"
    verify_out.mkdir()
    value_phases.run_value_refs(
        {
            "jobs_file": str(tmp_path / "ev4" / "optimizer" / "jobs.json"),
            "max_workers": 2,
        },
        str(verify_out),
        solver=fixture_solver,
        host=lambda: {"cpu_quota": 2},
    )
    imported = op.import_references(experiment, verify_out / "records.jsonl")
    assert imported["missing"] == 0
    summary = op.run_report(experiment)
    assert summary["missing_references"] == 0
    result = json.loads((tmp_path / "ev4" / "optimizer" / "results.json").read_text())
    assert result["baseline"]["points"] == 90
    for finding in result["findings"]:
        assert finding["condition"] in ("SCORE_VALUE_DIVERGENCE", "OTHER_SIGNAL")
        assert finding["schema"] == "carbon.admission-condition.v1"
    assert (
        (tmp_path / "ev4" / "optimizer" / "report.md")
        .read_text()
        .startswith("# Problem C")
    )


def test_imports_refuse_foreign_or_mismatched_outputs(tmp_path, small_panel):
    experiment = Experiment(tmp_path / "ev4", repository=REPOSITORY)
    experiment.freeze(EV4_PATH)
    source = tmp_path / "src"
    source.mkdir()
    body = {"member": "knn-s0", "recipe_digest": "sha256:other", "seed": 0}
    (source / "knn-s0.json.gz").write_bytes(gzip.compress(json.dumps(body).encode()))
    with pytest.raises(Exception) as refused:
        experiment.import_predictions(source)
    assert refused.value.code == "artifact_mismatch"
    (source / "knn-s0.json.gz").unlink()
    (source / "intruder-s0.json.gz").write_bytes(gzip.compress(b"{}"))
    with pytest.raises(Exception) as refused:
        experiment.import_predictions(source)
    assert refused.value.code == "prediction_not_in_panel"


def test_verified_violations_split_by_the_deciding_rule_half():
    from carbon.battery.value import divergence as dv

    top = dv.verified_violation(
        member="a-s0", kind="RECONSTRUCTED", rank=2, eligible_members=4, detail={}
    )
    low = dv.verified_violation(
        member="b-s0", kind="RECONSTRUCTED", rank=3, eligible_members=4, detail={}
    )
    assert top["condition"] == "SCORE_VALUE_DIVERGENCE"
    assert low["condition"] == "OTHER_SIGNAL"
    assert top["schema"] == dv.SCHEMA and top["review_state"] == dv.REVIEW_STATE


def test_report_outcomes_on_synthetic_references():
    base = EV4["baseline"]["protocol"]
    references = {}
    for t, s in op.VERIFY_CONDITIONS:
        for c1, c2 in ((base["c1"], base["c2"]), (1.0, 0.6)):
            references[op.case_id(c1, c2, t, s)] = {
                "status": "OK",
                "outputs": outputs_for(c1, c2, t, s),
            }
    outcome = op.design_outcome(EV4, 1.0, 0.6, references)
    assert sum(outcome["verdicts"].values()) == 90
    missing = op.design_outcome(EV4, 1.5, 0.6, references)
    assert missing["verdicts"][d.UNAVAILABLE] == 90
    assert missing["feasible_at_every_point"] is False
    assert missing["worst_time_to_cv_s"] is None


# --- pod controls ----------------------------------------------------------------------------


@pytest.fixture
def ev4_campaign(tmp_path, monkeypatch):
    # Every global use_campaign sets is restored after the test.
    for name in ("CAMPAIGN", "EVID", "LEDGER", "ACTIVE", "TOKEN_FILE", "CEILING_USD"):
        monkeypatch.setattr(pc, name, getattr(pc, name))
    monkeypatch.setattr(pc, "STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(pc, "REPO", str(tmp_path))
    pc.use_campaign("ev4")


def test_pod_allowance_never_exceeds_the_campaign_limit(ev4_campaign):
    assert pc.allowed_pods(3) == 3
    assert pc.allowed_pods(9) == 3
    pc.check_pod_allowance(["a", "b"], ["a", "b"], 3)
    with pytest.raises(SystemExit):
        pc.check_pod_allowance(["a", "b", "c"], [], 3)
    with pytest.raises(SystemExit):
        pc.check_pod_allowance([], ["x", "y", "z"], 3)
    pc.use_campaign("exam-design")
    assert pc.allowed_pods(3) == 1


def test_active_pods_are_recorded_per_pod_with_their_tokens(ev4_campaign):
    pc.record_active("pod1", "t1")
    pc.record_active("pod2", "t2")
    assert pc.active_pods() == ["pod1", "pod2"]
    assert pc.token_for("pod2") == "t2"
    assert pc.pick_pod("pod1") == "pod1"
    with pytest.raises(SystemExit):
        pc.pick_pod(None)  # two active: the pod must be named
    pc.clear_active("pod1")
    assert pc.pick_pod(None) == "pod2"


def test_the_combined_budget_and_the_cap_are_checked_before_spend(ev4_campaign):
    assert pc.start_cap(100.0, 15.0) == 15.0
    assert pc.start_cap(100.0, 50.0) == 15.0  # never above the ceiling
    assert pc.start_cap(10.0, 15.0) == 8.0  # never below the balance floor
    pc.check_budget(10.0, pc.pod_cost_usd(120), 15.0)
    with pytest.raises(SystemExit):
        pc.check_budget(13.0, pc.pod_cost_usd(240), 15.0)
    # Three 2-hour pods at the maximum rate fit inside the cap, as planned.
    assert 3 * pc.pod_cost_usd(120) + pc.CLEANUP_RESERVE_USD < 15.0


def test_large_manifests_travel_gzipped_and_decode_exactly():
    manifest = {
        f"carbon/f{i}.py": hashlib.sha256(str(i).encode()).hexdigest()
        for i in range(600)
    }
    env = pc.manifest_env(manifest)
    assert set(env) == {"CODE_MANIFEST_GZ_B64"}
    decoded = json.loads(gzip.decompress(base64.b64decode(env["CODE_MANIFEST_GZ_B64"])))
    assert decoded == manifest
    assert set(pc.manifest_env({"a": "b"})) == {"CODE_MANIFEST"}


def test_fetch_files_verifies_every_file_and_refuses_unsafe_paths(tmp_path):
    files = {"records.jsonl": b"x\n", "grid/m-s0.json.gz": b"\x1f\x8b"}
    listing = [
        {"path": p, "size": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        for p, b in files.items()
    ]
    summary = pc.fetch_files(listing, lambda p: (200, files[p]), str(tmp_path))
    assert summary["files"] == 2
    assert (tmp_path / "grid" / "m-s0.json.gz").read_bytes() == b"\x1f\x8b"
    with pytest.raises(SystemExit):
        pc.fetch_files(listing, lambda p: (200, b"tampered"), str(tmp_path / "b"))
    with pytest.raises(SystemExit):
        pc.fetch_files(
            [{"path": "../escape", "size": 0, "sha256": ""}],
            lambda p: (200, b""),
            str(tmp_path / "c"),
        )
