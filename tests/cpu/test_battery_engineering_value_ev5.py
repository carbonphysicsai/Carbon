"""EV5 before its freeze: fixture checks only (no PyBaMM, no network, no pod).

- the fresh conditions are the draft's, inside the published box, never
  repeated, fresh against every EV1, EV2 and EV4 decision condition, and
  protected from research agents as EV4's are;
- the optimizer keeps EV4's shape and maxima on fresh grids
  (OWNER-EV5-Q2-01), its `best_proposed` is the SR-2 candidate's best among
  members the gate passes, and a plan above the maxima is refused;
- H2's bootstrap is stratified by verdict with EV4's B and seed
  (OWNER-EV5-Q4-01);
- the panel keeps EV4's 100 members, seeds and 5 controls byte for byte, and
  adds the Track A harness's admitted constructions as ATTACK_CONSTRUCTION
  members, rebuilt, scored and value-tested like real ones; participant code
  and GRAPHITE constructions are refused by name;
- the contract, plans and campaign are built as EV4's were, and nothing
  dispatches;
- the confirmation batch is sealed from the validator deployment's committed
  root, 120 + 4, committed to its journal and never recorded in its pool, and
  only its public commitment is printed;
- the freeze manifest refuses while the gate cutoff is unset, and builds once
  it is set (here monkeypatched; this file never sets it);
- EV5 is frozen (OWNER-EV5-FREEZE-01): the committed contract, plans and
  manifest bind the sealed batch, the code still builds what was frozen, and a
  second freeze is refused.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_engineering_value import (
    FixtureBackend,
    fixture_solver,
    scoring_refs,  # noqa: F401 - fixture
)

from carbon.agent_campaign import boundaries as b
from carbon.battery import deployment, seeds, track_a
from carbon.battery.challenge import INPUT_BOUNDS
from carbon.battery.compile import compile_recipe
from carbon.battery.value import admissibility, ev5
from carbon.battery.value import contract as ev
from carbon.battery.value import false_acceptance as fa
from carbon.battery.value import optimizer as op
from carbon.battery.value import panel as pn
from carbon.battery.value import search_commitment as search
from carbon.battery.value.ev4_protected_conditions import EV4_MODEL
from carbon.battery.value.experiment import Experiment
from carbon.challenge_readiness import combined_run as cr
from scripts.dev.exam_design import value_phases, value_plans
from scripts.dev.exam_design.runpod import pod_control as pc

DOC = (REPOSITORY / ev5.SOURCE).read_text()
EV4, _ = ev.load(ev5.EV4_CONTRACT)
SEALED = {"fingerprint": "sha256:" + "0" * 64, "journal_sequence": 0}  # synthetic
#: The batch sealed on the operator host and frozen (OWNER-EV5-FREEZE-01).
FROZEN_SEAL = {
    "fingerprint": (
        "sha256:0add08ed7a3c6568a0779b0becb123578eedee6ca8e4f9f014588ed4ba934f3e"
    ),
    "journal_sequence": 14,
}
EV5_DIGEST = "sha256:bb08f9794fcd24afc70764fd953c8828e31dad49445ddbbeedc548cc5640fc31"


def _doc_conditions():
    """The conditions the draft lists in §3, parsed from its text."""
    found = re.findall(
        r"- (development|verification): t_amb \{([^}]*)\} °C × soc0 \{([^}]*)\}", DOC
    )
    assert len(found) == 2
    return {
        split: {(float(t), float(s)) for t in temps.split(",") for s in socs.split(",")}
        for split, temps, socs in found
    }


# --- conditions ------------------------------------------------------------------------


def test_the_conditions_are_the_ones_the_draft_lists():
    built = ev5.conditions()
    assert {s: set(c) for s, c in built.items()} == _doc_conditions()
    assert set(built["development"]) == {
        (float(t), s) for t in (6, 16, 26, 35) for s in (0.10, 0.30, 0.46)
    }
    assert set(built["verification"]) == {
        (float(t), s) for t in (10, 20, 30, 39) for s in (0.07, 0.24, 0.38)
    }


def test_twelve_plus_twelve_conditions_without_a_duplicate():
    built = ev5.conditions()
    every = built["development"] + built["verification"]
    assert len(built["development"]) == len(built["verification"]) == 12
    assert len(set(every)) == 24


def test_every_condition_lies_inside_the_published_box():
    low_t, high_t, low_s, high_s = map(
        float, re.search(r"t_amb (\d+)-(\d+) °C, soc0 ([\d.]+)-([\d.]+)", DOC).groups()
    )
    assert ev5.box() == ((low_t, high_t), (low_s, high_s)) == ((5.0, 40.0), (0.05, 0.5))
    envelope = EV4["operating_conditions"]["envelope"]
    assert ev5.box() == (tuple(envelope["t_amb_c"]), tuple(envelope["soc0"]))
    for t, s in ev5.conditions()["development"] + ev5.conditions()["verification"]:
        assert low_t <= t <= high_t and low_s <= s <= high_s


def test_no_condition_repeats_an_ev1_ev2_or_ev4_condition():
    prior = ev5.prior_conditions()
    for name in ("ev1", "ev2", "ev4"):
        document, _ = ev.load(
            ev.CONTRACTS / f"{name}-charge-protocol-selection.v1.json"
        )
        used = {tuple(c) for s in ev.scenarios(document) for c in s["conditions"]}
        assert set(prior[name]) == used and len(used) >= 16
    built = ev5.conditions()
    every = set(built["development"] + built["verification"])
    for name in ev5.PRIOR_STUDIES:
        assert not every & set(prior[name]), name
    assert cr.repeats(built, {n: prior[n] for n in ev5.PRIOR_STUDIES}) == []


def test_no_condition_sits_on_ev4s_protected_optimizer_grid():
    # OWNER-EV5-Q1-01: EV4's protected optimizer grid counts as EV4
    # conditions, so the verification soc0 moved from 0.20 to 0.24.
    assert "ev4_protected" in ev5.FRESH_AGAINST
    found = cr.repeats(
        ev5.conditions(), {"ev4_protected": ev5.prior_conditions()["ev4_protected"]}
    )
    assert found == []
    every = ev5.conditions()["development"] + ev5.conditions()["verification"]
    assert not set(every) & set(EV4_MODEL)
    # Specimen: the old choice did sit on the grid, so the check is not empty.
    assert {(10.0, 0.2), (20.0, 0.2), (30.0, 0.2)} <= set(EV4_MODEL)


def test_ev5s_optimizer_grids_keep_ev4s_shape_on_fresh_conditions():
    # OWNER-EV5-Q2-01: EV4's grids count as EV4 conditions (OWNER-EV5-Q1-01),
    # so EV5's optimizer cannot reuse them.
    spec = ev5.optimizer_spec()
    model, verify = spec.model_conditions, spec.verify_conditions
    assert len(model) == 32 and len(verify) == 90
    assert len(spec.mode_d_conditions) == len(op.EV4_SPEC.mode_d_conditions) == 20
    assert len(spec.in_band_verify) == len(op.EV4_SPEC.in_band_verify)
    assert {t for t, _ in model} == {t for t, _ in op.MODEL_CONDITIONS}
    (lo_t, hi_t), (lo_s, hi_s) = ev5.box()
    assert all(lo_t <= t <= hi_t and lo_s <= s <= hi_s for t, s in model + verify)
    prior = ev5.prior_conditions()
    used = {cr.key(c) for name in ev5.FRESH_AGAINST for c in prior[name]}
    used |= {cr.key(c) for g in ev5.conditions().values() for c in g}
    assert not {cr.key(c) for c in model + verify} & used
    assert not set(model) & set(verify)
    # Every soc0 is one no earlier or EV5 condition uses, at any temperature.
    socs = {round(c[1], 9) for c in prior_all(prior) + ev5_all()}
    assert not {round(s, 9) for _, s in model + verify} & socs
    # Specimen: EV4's grids are refused as EV5's.
    with pytest.raises(cr.CombinedRunError, match="condition_not_fresh"):
        cr.check_conditions(
            {"optimizer_model": op.MODEL_CONDITIONS},
            ev5.box(),
            {"ev4_protected": prior["ev4_protected"]},
        )
    for t, s in model + verify:
        assert search._protected()(t, s)


def prior_all(prior):
    return [c for name in ev5.FRESH_AGAINST for c in prior[name]]


def ev5_all():
    return [c for g in ev5.conditions().values() for c in g]


def _results(rows):
    """A minimal EV5 result: member -> (deciding score, loss)."""
    members = {
        m: {
            "kind": "RECONSTRUCTED",
            "eligible": True,
            "loss_development": loss,
            "loss_verification": loss,
        }
        for m, (_score, loss) in rows.items()
    }
    scores = {m: {"control-exam-v1": score} for m, (score, _loss) in rows.items()}
    return {"summary": {"members": members}, "rule_scores": scores}


def test_best_proposed_is_the_sr2_candidates_best_among_members_the_gate_passes():
    spec = ev5.optimizer_spec()
    assert spec.proposed_rule == ev5.candidate_rule()["rule"]
    assert spec.gated_roles == ("best_proposed",)
    rows = {
        "a-s0": (-0.1, 3.0),
        "b-s0": (-0.2, 2.0),
        "c-s0": (-0.3, 1.0),
        "d-s0": (-0.4, 4.0),
        "knn-s0": (-0.5, 5.0),
    }
    backbones = {m: ("knn" if m.startswith("knn") else "mlp") for m in rows}
    sr2 = {spec.proposed_rule: {"a-s0": 0.5, "b-s0": 0.9, "c-s0": 0.4, "d-s0": 0.3}}
    picks = op.select_members(
        _results(rows), backbones, spec, scores=sr2, admissible=set(rows)
    )
    assert [p["member"] for p in picks] == ["a-s0", "b-s0", "c-s0", "knn-s0", "d-s0"]
    # The gate fails b: the candidate's next best that the gate passes.
    picks = op.select_members(
        _results(rows), backbones, spec, scores=sr2, admissible=set(rows) - {"b-s0"}
    )
    assert picks[1] == {"role": "best_proposed", "member": "c-s0"}
    # The gate binds best_proposed only: best_deciding stays a, as in EV4.
    assert picks[0] == {"role": "best_deciding", "member": "a-s0"}
    # Fail closed: no gate verdicts, or no candidate scores, selects nothing.
    with pytest.raises(op.OptimizerError, match="gate_missing"):
        op.select_members(_results(rows), backbones, spec, scores=sr2)
    with pytest.raises(op.OptimizerError, match="proposed_unscored"):
        op.select_members(_results(rows), backbones, spec, admissible=set(rows))


def test_the_ev5_contract_selects_ev5s_optimizer_and_ev4s_keeps_its_own():
    assert op.spec_for(ev5.contract()) == ev5.optimizer_spec()
    assert op.spec_for(EV4) is op.EV4_SPEC
    point = (1.0, 0.5, 20.0, 0.21)
    assert op.case_id(*point, ev5.optimizer_spec()).startswith("ev5opt:")
    assert op.case_id(*point).startswith("ev4opt:")


def test_h2s_bootstrap_is_stratified_with_ev4s_replicates_and_seed():
    from carbon.battery.value import hypotheses as hy

    spec = ev5.H2_BOOTSTRAP
    paired = EV4["acceptance"]["paired_comparison"]
    assert spec["replicates"] == paired["replicates"] == 10000
    assert spec["rng_seed"] == paired["rng_seed"] == 20261001
    assert spec["level"] == paired["level"] and spec["interval"] == paired["interval"]
    rng = __import__("numpy").random.default_rng(0)
    losses = rng.normal(1.0, 0.1, (12, 12))
    losses[:3] += 1.0  # three FAIL members decide worse
    losses[0, 0] = float("nan")
    failed = [True] * 3 + [False] * 9
    run = {"replicates": 500, "seed": spec["rng_seed"], "level": spec["level"]}
    out = hy.group_difference_bootstrap(losses, failed, **run)
    assert out == hy.group_difference_bootstrap(losses, failed, **run)
    assert out["members_failed"] == 3 and out["members_passed"] == 9
    assert 0.8 < out["difference"] < 1.2
    assert out["interval"][0] > 0 and out["excludes_zero"] is True
    assert out["replicates_skipped"] == 0  # stratified: both groups every time
    same = hy.group_difference_bootstrap(losses[3:], [True] * 4 + [False] * 5, **run)
    assert same["interval"][0] < 0 < same["interval"][1]
    assert same["excludes_zero"] is False
    # Either group empty: undefined, never zero.
    empty = hy.group_difference_bootstrap(losses, [False] * 12, **run)
    assert empty["difference"] is None and empty["interval"] == [None, None]
    assert empty["excludes_zero"] is False


def test_ev5_conditions_are_protected_from_research_agents_as_ev4s_are():
    import test_design_search_commitment as ts

    for t, s in ev5.conditions()["development"] + ev5.conditions()["verification"]:
        with pytest.raises(search.SearchError) as refused:
            search.request(contract=ts.CONTRACT, **ts.base(conditions=[[t, s]]))
        assert refused.value.code == "protected_material_requested"
    for path in (
        "carbon/battery/value/ev5_protected_conditions.py",
        "carbon/battery/value/ev5.py",
        "docs/development/BATTERY_ENGINEERING_VALUE_EV5.md",
    ):
        with pytest.raises(b.BoundaryError, match="denied"):
            b.checkout_manifest(REPOSITORY, b.Role.OPTIMIZER, paths=[path])


# --- the optimizer's maxima -------------------------------------------------------------


def test_ev5_keeps_ev4s_optimizer_maxima():
    assert ev5.optimizer_maxima() == {
        "mode_d_solves": 540,
        "mode_x_solves": 250,
        "designs": 6,
        "k": 50,
        "total_solves": 1630,
    }
    assert ev5.optimizer_maxima() == op.EV4_SPEC.maxima()
    assert op.EV4_SPEC.max_mode_d_solves == op.MAX_MODE_D_SOLVES
    assert "Mode D ≤ 540 + Mode X ≤ 250 solves" in DOC
    assert "Optimizer verification (≤ 790)" in DOC


def test_an_optimizer_plan_above_the_maxima_is_refused():
    jobs = [{"case_id": f"j{i}"} for i in range(540 + 250)]
    plans = ev5.optimizer_plans(jobs)
    assert sorted(plans) == [f"optimizer-verify-shard{i}-of3.json" for i in range(3)]
    assert {p["jobs_file"] for p in plans.values()} == {
        f"{ev5.PLANS}/optimizer-jobs.json"
    }
    with pytest.raises(SystemExit, match="over the maximum"):
        ev5.optimizer_plans(jobs + [{"case_id": "one-more"}])
    # The job builder refuses too, under EV5's contract.
    contract = ev5.contract()
    designs = {
        f"m{i}": {"status": "DESIGN", "c1": op.C1[i], "c2": 0.2} for i in range(6)
    }
    with pytest.raises(op.OptimizerError) as refused:
        op.verification_plan(contract, designs, {})
    assert refused.value.code == "budget_exceeded"
    point = {"c1": 0.5, "c2": 0.2, "t_amb_c": 5.0, "soc0": 0.05}
    with pytest.raises(op.OptimizerError):
        op.verification_plan(contract, {}, {f"m{i}": [point] for i in range(6)})


# --- the panel --------------------------------------------------------------------------


def test_ev4s_100_recipes_seeds_and_5_controls_stay_byte_identical():
    manifest_path = REPOSITORY / ev5.EV4_FREEZE_MANIFEST
    recorded = re.search(
        r"freeze-manifest\.json`\s*\(sha256 `([0-9a-f]{64})`",
        (REPOSITORY / "docs/development/BATTERY_ENGINEERING_VALUE_EV4.md").read_text(),
    ).group(1)
    # The committed manifest is EV4's frozen one, as its pre-registration records.
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == recorded
    frozen_panel, frozen_controls = ev5.ev4_frozen_panel()
    kinds = pn.kinds("ev5")
    real = [
        e for e in ev5.panel_entries("ev5") if kinds[e["member"]] == "RECONSTRUCTED"
    ]
    canonical = json.dumps(real, sort_keys=True, separators=(",", ":"))
    assert canonical == json.dumps(frozen_panel, sort_keys=True, separators=(",", ":"))
    assert len(real) == 100 and cr.digest(real) == cr.digest(frozen_panel)
    assert ev5.panel_entries("ev4") == frozen_panel  # EV4 itself is unchanged
    assert list(pn.CONTROLS) == frozen_controls and len(frozen_controls) == 5
    listed = REPOSITORY / "docs/development/evidence/ev4-2026-10-01/predictions.sha256"
    files = {line.split()[1] for line in listed.read_text().splitlines()}
    assert files == {f"{e['member']}.json.gz" for e in real}


def _is_strategy_document(value):
    return type(value) is dict and {
        "schema_version",
        "challenge_id",
        "backbone",
        "parameters",
    } <= set(value)


def test_attack_constructions_come_only_from_the_declarative_recipe_families():
    for family in track_a.FAMILIES:
        documents = [
            d
            for _name, value in family.attacks()
            for d in (value if type(value) is tuple else (value,))
        ]
        declarative = bool(documents) and all(map(_is_strategy_document, documents))
        assert (family.family_id in pn.ATTACK_FAMILIES) == declarative, family.family_id
    entries = pn.harness_constructions()
    assert {e["family"] for e in entries} == set(pn.ATTACK_FAMILIES)
    assert {e["origin"] for e in entries} == {"track_a_harness"}
    assert {e["material"] for e in entries} == {"declarative_recipe"}
    assert track_a.RECIPE_CONTROL not in [e["document"] for e in entries]


def test_admitted_constructions_join_the_panel_as_attack_construction_members():
    constructions = pn.attack_constructions()
    admitted, refused = constructions["admitted"], constructions["refused"]
    # Every recipe-surface attack is refused by a typed compiler issue and
    # never reaches a worker; every rebuild pair compiles and joins the panel.
    assert len(refused) == len(track_a.RECIPE_ATTACKS) == 21
    assert {r["family"] for r in refused} == {"recipe_surface"}
    assert all(
        r["codes"] and all("." in code for code, _ in r["codes"]) for r in refused
    )
    assert len(admitted) == 2 * len(track_a.REBUILD_PAIRS) == 10
    assert all(label.startswith("attack_rebuild_identity_") for label, *_ in admitted)
    digests = {
        compile_recipe(strategy)[1].recipe_digest for _l, strategy, _s in admitted
    }
    assert len(digests) == 10
    members = pn.members("ev5")
    ids = [m for m, *_ in members]
    assert len(ids) == len(set(ids)) == 110
    assert members[:100] == pn.members("ev4")
    kinds = pn.kinds("ev5")
    assert sum(k == "ATTACK_CONSTRUCTION" for k in kinds.values()) == 10
    assert sum(k == "RECONSTRUCTED" for k in kinds.values()) == 100
    assert set(pn.kinds("ev4").values()) == {"RECONSTRUCTED"}
    assert "Panel (about 110 members)" in DOC
    # A caller's edit never reaches the cached panel.
    admitted[0][1]["parameters"]["width"] = 1
    assert pn.attack_constructions()["admitted"][0][1]["parameters"] != {"width": 1}


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"material": "participant_code"}, "participant_code_out_of_scope"),
        (
            {"material": "participant_code", "origin": "graphite_attacker"},
            "participant_code_out_of_scope",
        ),
        ({"origin": "graphite_constructor"}, "attack_construction_origin"),
        ({"origin": "graphite_attacker"}, "attack_construction_origin"),
        ({"material": "executable"}, "attack_construction_material"),
        ({"document": "import os"}, "declarative_recipe_not_a_document"),
    ],
)
def test_participant_code_and_graphite_constructions_are_refused_by_name(change, code):
    entry = {**pn.harness_constructions()[0], **change}
    with pytest.raises(cr.CombinedRunError) as refused:
        cr.admit_attack_construction(entry, origins=(pn.ATTACK_ORIGIN,))
    assert refused.value.code == code


@pytest.fixture
def small_ev5(monkeypatch):
    """Three reconstructed members and two attack constructions."""
    keep = {"knn", "mlp_half"}  # mlp_half has two seeds
    monkeypatch.setitem(
        pn.PANELS, "ev5", tuple(r for r in pn.PANELS["ev5"] if r[0] in keep)
    )
    full = pn.attack_constructions()
    monkeypatch.setattr(
        pn,
        "attack_constructions",
        lambda: {"admitted": full["admitted"][:2], "refused": full["refused"]},
    )
    monkeypatch.chdir(REPOSITORY)


def test_attack_constructions_are_rebuilt_scored_and_value_tested_like_real_ones(
    tmp_path,
    scoring_refs,  # noqa: F811
    small_ev5,
):
    from carbon.battery.value import divergence

    contract_path = tmp_path / "ev5-contract.json"
    contract_path.write_text(json.dumps(ev5.contract()))
    experiment = Experiment(tmp_path / "ev5", repository=REPOSITORY)
    experiment.freeze(contract_path)
    experiment.references(workers=2, solver=fixture_solver)
    rebuilt = experiment.panel(backend=FixtureBackend(scoring_refs))["reconstructed"]
    attacks = sorted(
        m for m, k in pn.kinds("ev5").items() if k == "ATTACK_CONSTRUCTION"
    )
    assert len(attacks) == 2 and set(attacks) <= set(rebuilt) and len(rebuilt) == 5
    results = experiment.evaluate()
    members = results["summary"]["members"]
    for member in attacks:
        row = members[member]
        assert row["kind"] == "ATTACK_CONSTRUCTION"
        assert row["loss_development"] is not None
        assert row["loss_verification"] is not None
        assert set(results["rule_scores"][member]) == set(
            results["rule_scores"]["knn-s0"]
        )
        assert set(results["decisions"][member]) == set(results["decisions"]["knn-s0"])
    assert sorted(m for m, r in members.items() if r["kind"] == "RECONSTRUCTED") == [
        "knn-s0",
        "mlp_half-s0",
        "mlp_half-s1",
    ]
    # Kept out of the real-member pools: seed bands and family diversity.
    assert set(results["seed_variation"]) == {"knn", "mlp_half"}
    assert sum(row["members"] for row in results["families"].values()) == 3
    for condition in divergence.conditions(results):
        assert condition["kind"] == members[condition["member"]]["kind"]


# --- the contract, plans and campaign ----------------------------------------------------


def test_the_ev5_contract_is_ev4s_with_ev5s_conditions_and_panel():
    contract = ev5.contract()
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
        "challenge",
        "decision",
        "preferences_status",
    ):
        assert contract[key] == EV4[key], key
    assert (contract["case_prefix"], contract["panel"]) == ("ev5", "ev5")
    assert (
        contract["acceptance"]["rule_selection"] == EV4["acceptance"]["rule_selection"]
    )
    assert "paired_comparison" not in contract["acceptance"]
    assert len(ev.candidates(contract)) == 35
    cases = ev.decision_cases(contract)
    assert len(cases) == 840 == contract["budgets"]["reference_solves_max"]
    assert all(c["case_id"].startswith("ev5:") for c in cases)
    assert contract["budgets"]["reconstructions_max"] == 110
    assert "OWNER-EV5-CAP-01" in contract["authority"]["record"]
    assert not any(
        contract["authority"][k]
        for k in ("chain", "reward", "changes_testnet_rule", "qualification")
    )
    ids = [s["id"] for s in ev.scenarios(contract)]
    assert ids[0] == "D-T6-S0.10" and ids[-1] == "V-T39-S0.38"
    assert ev.validate(contract) is contract
    # Written at the freeze (OWNER-EV5-FREEZE-01); its digest is pinned here
    # and in the pre-registration, as EV4's is.
    _, digest = ev.load(REPOSITORY / ev5.CONTRACT)
    assert digest == ev.digest(contract) == EV5_DIGEST
    assert EV5_DIGEST in DOC


def test_the_plans_are_built_as_ev4s_and_name_ev5s_contract(tmp_path):
    plans = ev5.plans()
    assert sorted(plans) == [
        "ev5-panel-shard0-of1.json",
        "ev5-refs-shard0-of2.json",
        "ev5-refs-shard1-of2.json",
    ]
    committed = REPOSITORY / "docs/development/evidence/ev4-2026-10-01/plans"
    for name, plan in plans.items():
        ev4 = json.loads((committed / name.replace("ev5-", "ev4-")).read_text())
        assert plan == {**ev4, "contract": ev5.CONTRACT}, name
    for path in plans["ev5-panel-shard0-of1.json"]["ship"][1:]:
        assert (REPOSITORY / path).is_file()
    # Once the freeze writes the contract, each reference plan resolves.
    target = tmp_path / ev5.CONTRACT
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(ev5.contract()))
    plan = plans["ev5-refs-shard0-of2.json"]
    jobs = value_phases.reference_jobs(plan, tmp_path)
    shards = [value_phases.shard(jobs, i, 2) for i in range(2)]
    assert len(jobs) == 840 and len(shards[0]) == len(shards[1]) == 420
    assert {(j["t_amb_c"], j["soc0"]) for j in jobs} == {
        c for group in ev5.conditions().values() for c in group
    }
    # The CLI writes the same plans for `--study ev5`.
    out = tmp_path / "plans"
    value_plans.main(["refs", "--shards", "2", "--study", "ev5", "--out-dir", str(out)])
    value_plans.main(
        ["panel", "--shards", "1", "--study", "ev5", "--out-dir", str(out)]
    )
    assert {p.name: json.loads(p.read_text()) for p in out.iterdir()} == plans


@pytest.fixture
def ev5_campaign(tmp_path, monkeypatch):
    for name in (
        "CAMPAIGN",
        "EVID",
        "LEDGER",
        "PRIVATE_LEDGER",
        "ACTIVE",
        "TOKEN_FILE",
    ):
        monkeypatch.setattr(pc, name, getattr(pc, name))
    monkeypatch.setattr(pc, "STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(pc, "REPO", str(tmp_path))
    (tmp_path / "state").mkdir()
    pc.use_campaign("ev5")
    return tmp_path


def test_the_ev5_campaign_is_declared_without_figures(ev5_campaign):
    spec = pc.CAMPAIGNS["ev5"]
    assert spec["evidence"] == ev5.EVIDENCE and spec["max_pods"] == 3
    assert set(spec) == {"evidence", "active", "token", "max_pods", "name"}
    assert pc.LEDGER == str(ev5_campaign / ev5.EVIDENCE / "accounting/ledger.jsonl")
    assert pc.PRIVATE_LEDGER.endswith("/accounting/ev5.jsonl")
    assert pc.allowed_pods(9) == 3
    # The ceiling is operator configuration: a configuration without one for
    # ev5 refuses, and a synthetic one is read.
    config = ev5_campaign / "state" / pc.OPERATOR_CONFIG
    config.write_text(
        json.dumps({"balance_floor_usd": 1.0, "ceilings_usd": {"ev4": 2.0}})
    )
    with pytest.raises(SystemExit, match="ceilings_usd.ev5"):
        pc.operator_limits()
    config.write_text(
        json.dumps({"balance_floor_usd": 1.0, "ceilings_usd": {"ev5": 2.0}})
    )
    assert pc.operator_limits().ceiling_usd == 2.0
    # EV5 has run (OWNER-EV5-GO-01): its committed ledger is the public
    # projection only, with no balance, spend, cap or rate in any row.
    ledger = REPOSITORY / ev5.EVIDENCE / "accounting" / "ledger.jsonl"
    for line in ledger.read_text().splitlines():
        row = json.loads(line)
        allowed = {"utc", "event"} | pc.PUBLIC_FIELDS.get(row["event"], set())
        assert set(row) <= allowed, row["event"]


def test_nothing_dispatches_without_the_operator_limits(ev5_campaign, monkeypatch):
    for remote in ("pods", "account", "rest", "gql"):
        monkeypatch.setattr(pc, remote, lambda *a, r=remote: pytest.fail(f"{r} called"))

    class Args:
        max_pods = 3

    with pytest.raises(SystemExit, match="no operator configuration"):
        pc.cmd_dispatch(Args())


# --- the confirmation set ---------------------------------------------------------------


def test_the_confirmation_skeleton_holds_nothing_private():
    skeleton = ev5.confirmation()
    assert (skeleton["cases"], skeleton["hidden_duplicates"]) == (120, 4)
    assert skeleton["batch_size"] == 124
    assert "120 fresh private cases + 4 hidden duplicates" in DOC
    sheet = json.loads((REPOSITORY / ev5.STUDY_SHEET).read_text())
    population = sheet["population"]["confirmation"]
    for key in ("source", "law", "subgroups", "custody"):
        assert skeleton[key] == population[key]
    # OWNER-EV5-Q3-01: the private cases are solved on the operator host only.
    assert skeleton["solved_on"].startswith("the operator host only")
    assert "rented compute" in skeleton["solved_on"]
    # Counts and descriptions only: no case, input, seed, root or duplicate map.
    assert set(skeleton) == {
        "study_sheet",
        "source",
        "cases",
        "hidden_duplicates",
        "batch_size",
        "law",
        "subgroups",
        "custody",
        "role",
        "made_on",
        "solved_on",
    }
    assert all(type(v) in (str, int, type(None)) for v in skeleton.values())
    assert ev5.sealed(SEALED) == SEALED


@pytest.mark.parametrize(
    "commitment",
    [
        None,
        {},
        {"fingerprint": "sha256:" + "0" * 64},
        {"fingerprint": "sha256:xyz", "journal_sequence": 0},
        {"fingerprint": "sha256:" + "0" * 64, "journal_sequence": -1},
        {"fingerprint": "sha256:" + "0" * 64, "journal_sequence": True},
        {**SEALED, "batch": "plaintext"},
    ],
)
def test_an_unsealed_confirmation_batch_is_refused(commitment):
    assert ev5.sealed(commitment) is None


# --- sealing the confirmation batch (validator host) -------------------------------------


def _deployment(tmp_path, monkeypatch):
    """A validator deployment whose root `operate init` has committed."""
    from carbon.battery.daemon import rule_digest

    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin("sha256:" + "1" * 64, rule_digest()))
    path = tmp_path / "deployment.json"
    path.write_text(
        json.dumps(
            {
                "schema": deployment.SCHEMA,
                "state": str(tmp_path / "state.sqlite3"),
                "private_root": str(tmp_path / "root.bin"),
                "journal": str(tmp_path / "journal.jsonl"),
                "work": str(tmp_path / "work"),
                "backend": "direct",
                "require_commitment": False,
            }
        )
    )
    path.chmod(0o600)
    return path


def _confirmation_entries(tmp_path):
    return [
        e
        for e in seeds.SeedJournal(tmp_path / "journal.jsonl").public()
        if e["kind"] == "batch" and e["role"] == ev5.CONFIRMATION_ROLE
    ]


def _regenerated(tmp_path):
    """The batch, regenerated from the root as the operator host does."""
    root = seeds.PrivateRoot.load(tmp_path / "root.bin")
    pin = seeds.SeedJournal(tmp_path / "journal.jsonl").root_pin(root)
    return seeds.make_batch(root, pin, ev5.CONFIRMATION_ROLE, 124, 4)


def test_the_confirmation_batch_is_sealed_from_the_committed_root_outside_the_pool(
    tmp_path, monkeypatch
):
    from carbon.battery.daemon import BatteryValidator

    path = _deployment(tmp_path, monkeypatch)

    def forbidden(self):
        raise AssertionError("sealing started or recovered the validator")

    monkeypatch.setattr(BatteryValidator, "start", forbidden)
    monkeypatch.setattr(BatteryValidator, "recover", forbidden)
    result = ev5.seal_confirmation(path)
    assert result["newly_committed"] is True
    assert (result["cases"], result["hidden_duplicates"]) == (120, 4)
    commitment = result["commitment"]
    assert ev5.sealed(commitment) == commitment
    (entry,) = _confirmation_entries(tmp_path)
    assert entry["fingerprint"] == commitment["fingerprint"]
    assert entry["sequence"] == commitment["journal_sequence"]
    assert entry["cases"] == 124
    # The study sheet's batch: regenerated from the committed root it has the
    # same fingerprint, 120 fresh draws inside the published box and 4 hidden
    # duplicates.
    batch = _regenerated(tmp_path)
    assert batch.fingerprint == commitment["fingerprint"]
    assert len(batch.duplicates) == 4
    fresh = {inputs for _, inputs in batch.cases}
    assert len(fresh) == 120
    for inputs in fresh:
        for name, value in inputs:
            low, high = INPUT_BOUNDS[name]
            assert low <= value <= high
    # Never in the validator state: no screening rotation or finalist
    # comparison can claim it.
    target = deployment.validator(path, repository=REPOSITORY, readonly=True)
    assert target.store.batches() == []


def test_sealing_again_recalls_the_same_batch(tmp_path, monkeypatch):
    path = _deployment(tmp_path, monkeypatch)
    first = ev5.seal_confirmation(path)
    again = ev5.seal_confirmation(path)
    assert again["commitment"] == first["commitment"]
    assert again["newly_committed"] is False
    assert len(_confirmation_entries(tmp_path)) == 1


def test_a_second_batch_under_the_confirmation_role_is_refused(tmp_path, monkeypatch):
    # Draws are seeded by role and index, so another batch under the role
    # would share this one's cases.
    path = _deployment(tmp_path, monkeypatch)
    target = deployment.validator(path, repository=REPOSITORY, readonly=True)
    other = target.seal_batch(ev5.CONFIRMATION_ROLE, count=10, duplicates=2)
    with pytest.raises(cr.CombinedRunError) as refused:
        ev5.seal_confirmation(path)
    assert refused.value.code == "confirmation_role_reused"
    assert [e["fingerprint"] for e in _confirmation_entries(tmp_path)] == [
        other.fingerprint
    ]


def test_the_seal_command_prints_only_the_public_commitment(
    tmp_path, monkeypatch, capsys
):
    path = _deployment(tmp_path, monkeypatch)
    assert ev5.main(["seal-confirmation", "--config", str(path)]) == 0
    printed = capsys.readouterr().out
    result = json.loads(printed)
    assert set(result) == {
        "role",
        "cases",
        "hidden_duplicates",
        "newly_committed",
        "commitment",
    }
    assert set(result["commitment"]) == {"fingerprint", "journal_sequence"}
    # No case id, input or root: the output holds no number but the counts.
    for case_id, _ in _regenerated(tmp_path).cases:
        assert case_id not in printed
    assert "." not in printed
    assert (tmp_path / "root.bin").read_bytes().hex() not in printed
    # The printed commitment is what the freeze manifest takes.
    manifest = ev5.freeze_manifest(result["commitment"])
    assert manifest["confirmation"]["commitment"] == result["commitment"]


def test_the_seal_command_refuses_a_loose_deployment_config(
    tmp_path, monkeypatch, capsys
):
    path = _deployment(tmp_path, monkeypatch)
    path.chmod(0o644)
    assert ev5.main(["seal-confirmation", "--config", str(path)]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "unavailable": "evaluation_input_not_owner_only"
    }
    assert _confirmation_entries(tmp_path) == []


# --- the freeze manifest ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "blocker"),
    [
        (None, "gate_cutoff_unset"),
        ("HUMAN_INPUT", "gate_cutoff_unset"),
        (math.nan, "gate_cutoff_invalid"),
        (True, "gate_cutoff_invalid"),
        ("2.0", "gate_cutoff_invalid"),
    ],
)
def test_the_freeze_manifest_refuses_while_the_cutoff_is_unset(
    monkeypatch, value, blocker
):
    monkeypatch.setattr(admissibility, "THRESHOLD_BANDS", value)
    with pytest.raises(cr.CombinedRunError) as refused:
        ev5.freeze_manifest(SEALED)
    assert refused.value.code == "freeze_refused"
    assert blocker in refused.value.blockers


def test_the_freeze_manifest_refuses_when_the_cutoff_is_missing(monkeypatch):
    monkeypatch.delattr(admissibility, "THRESHOLD_BANDS")
    with pytest.raises(cr.CombinedRunError) as refused:
        ev5.freeze_manifest(SEALED)
    assert "gate_cutoff_missing" in refused.value.blockers


def test_the_freeze_names_every_blocker_today(monkeypatch):
    monkeypatch.setattr(admissibility, "THRESHOLD_BANDS", None)
    with pytest.raises(cr.CombinedRunError) as refused:
        ev5.freeze_manifest()
    blockers = refused.value.blockers
    # OWNER-EV5-Q1-01 moved the verification soc0 off EV4's optimizer grid,
    # so freshness no longer blocks; the cutoff and the seal remain.
    assert blockers == ("gate_cutoff_unset", "confirmation_not_sealed")


def test_the_freeze_manifest_builds_once_the_cutoff_is_set(monkeypatch):
    # A synthetic cutoff and the sealed batch's public commitment stand in;
    # freshness holds against EV4's protected grid too (OWNER-EV5-Q1-01).
    monkeypatch.setattr(admissibility, "THRESHOLD_BANDS", 1.2345)
    assert "ev4_protected" in ev5.FRESH_AGAINST
    manifest = ev5.freeze_manifest(SEALED)
    assert manifest == ev5.freeze_manifest(SEALED)  # deterministic
    json.dumps(manifest, allow_nan=False)
    assert manifest["gate_cutoff"]["THRESHOLD_BANDS"] == 1.2345
    assert manifest["conditions"]["development"][0] == [6.0, 0.1]
    assert len(manifest["conditions"]["verification"]) == 12
    rules = manifest["rules_compared"]
    assert rules["candidate"]["rule"] == "sr2-a0-r0.3-g0.6-m0.1"
    assert "`sr2-a0-r0.3-g0.6-m0.1`" in DOC
    assert rules["rules"] == [
        {"rule": "control-exam-v1", "gate": False},
        {"rule": "control-exam-v1", "gate": True},
        {"rule": "sr2-a0-r0.3-g0.6-m0.1", "gate": False},
        {"rule": "sr2-a0-r0.3-g0.6-m0.1", "gate": True},
    ]
    assert rules["gate"]["cutoff_bands"] == 1.2345
    hypotheses = manifest["hypotheses"]
    assert {"H1", "H2", "H3"} <= set(hypotheses) and hypotheses["blended"] is False
    assert hypotheses["H1"]["bootstrap"]["replicates"] == 10000
    assert hypotheses["H2"]["must_fail"] == ["control-boundary_optimist"]
    assert hypotheses["H2"]["cutoff_bands"] == 1.2345
    h3 = hypotheses["H3"]["localized_measurement"]
    assert h3["schema"] == fa.SCHEMA and h3["cutoff"] is None
    assert h3["module_digest"].startswith("sha256:")
    assert manifest["cap"]["decision"] == "OWNER-EV5-CAP-01"
    assert manifest["cap"]["hard_cap_usd"] == 6
    panel = manifest["panel"]
    assert (
        panel["members"] == 110 and len(panel["attack_constructions"]["members"]) == 10
    )
    assert panel["reconstructed"]["digest"] == cr.digest(ev5.ev4_frozen_panel()[0])
    assert sorted(manifest["plans"]["files"]) == sorted(ev5.plans())
    assert manifest["contract"]["digest"] == ev.digest(ev5.contract())
    assert manifest["confirmation"]["commitment"] == SEALED
    assert manifest["optimizer"]["maxima"] == ev5.optimizer_maxima()
    assert manifest["optimizer"]["decision"] == "OWNER-EV5-Q2-01"
    assert manifest["optimizer"]["gated_roles"] == ["best_proposed"]
    assert len(manifest["optimizer"]["verification_conditions"]) == 90
    assert hypotheses["H2"]["bootstrap"] == ev5.H2_BOOTSTRAP
    assert not any(manifest["claims"].values())
    # A synthetic build writes nothing: the frozen manifest is EV5's own.
    frozen = json.loads((REPOSITORY / ev5.FREEZE_MANIFEST).read_text())
    assert frozen["confirmation"]["commitment"] == FROZEN_SEAL


# --- the freeze (OWNER-EV5-FREEZE-01) ----------------------------------------------------


def _frozen_manifest():
    return json.loads((REPOSITORY / ev5.FREEZE_MANIFEST).read_text())


def test_the_frozen_manifest_binds_the_sealed_batch_and_the_frozen_files():
    manifest = _frozen_manifest()
    assert (manifest["schema"], manifest["study"]) == (ev5.SCHEMA, "EV5")
    assert manifest["confirmation"]["commitment"] == FROZEN_SEAL
    assert FROZEN_SEAL["fingerprint"] in DOC
    assert "OWNER-EV5-FREEZE-01" in manifest["authority"]
    # The contract and plans on disk are the manifest's.
    _, digest = ev.load(REPOSITORY / ev5.CONTRACT)
    assert digest == manifest["contract"]["digest"] == EV5_DIGEST
    files = manifest["plans"]["files"]
    # The optimizer's verification plans are added after selection
    # (manifest "optimizer_verification"); everything else is frozen.
    on_disk = sorted(
        p.name
        for p in (REPOSITORY / ev5.PLANS).iterdir()
        if not p.name.startswith("optimizer-")
    )
    assert on_disk == sorted(files)
    for name, entry in files.items():
        plan = json.loads((REPOSITORY / ev5.PLANS / name).read_text())
        assert plan == entry["plan"] and cr.digest(plan) == entry["digest"], name
    # The study sheet it pins is unchanged.
    assert manifest["study_sheet"]["sha256"] == ev5._file_digest(
        REPOSITORY, ev5.STUDY_SHEET
    )
    assert manifest["gate_cutoff"]["THRESHOLD_BANDS"] == 2.0
    assert manifest["hypotheses"]["H3"]["localized_measurement"]["cutoff"] is None
    assert not any(manifest["claims"].values())


def test_the_code_still_builds_what_was_frozen():
    # A change to any of these after the freeze is a new, reported version.
    manifest = _frozen_manifest()
    assert ev.digest(ev5.contract()) == manifest["contract"]["digest"]
    assert {name: cr.digest(plan) for name, plan in ev5.plans().items()} == {
        name: entry["digest"] for name, entry in manifest["plans"]["files"].items()
    }
    assert cr.digest(ev5.panel_record()) == cr.digest(manifest["panel"])
    assert cr.digest(ev5.optimizer_record()) == cr.digest(manifest["optimizer"])
    assert manifest["hypotheses"]["H3"]["localized_measurement"]["module_digest"] == (
        ev5._file_digest(REPOSITORY, ev5.H3_MEASUREMENT["module"])
    )


def test_a_second_freeze_is_refused_and_writes_nothing(capsys):
    evidence = REPOSITORY / ev5.EVIDENCE
    before = {p: p.read_bytes() for p in evidence.rglob("*") if p.is_file()}
    contract = (REPOSITORY / ev5.CONTRACT).read_bytes()
    argv = [
        "freeze",
        "--confirmation-fingerprint",
        FROZEN_SEAL["fingerprint"],
        "--confirmation-sequence",
        str(FROZEN_SEAL["journal_sequence"]),
    ]
    assert ev5.main(argv) == 2
    refused = json.loads(capsys.readouterr().out)
    assert refused["refused"] == "already_frozen"
    assert set(refused["blockers"]) == {ev5.CONTRACT, ev5.PLANS, ev5.FREEZE_MANIFEST}
    assert {p: p.read_bytes() for p in evidence.rglob("*") if p.is_file()} == before
    assert (REPOSITORY / ev5.CONTRACT).read_bytes() == contract


def test_the_freeze_writes_the_contract_plans_and_manifest_once(tmp_path):
    # A repository holding only what the manifest reads by path.
    for path in (
        ev5.SOURCE,
        ev5.STUDY_SHEET,
        ev5.EV4_FREEZE_MANIFEST,
        ev5.CANDIDATE_RECORD,
        ev5.H3_MEASUREMENT["module"],
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPOSITORY / path).read_bytes())
    with pytest.raises(cr.CombinedRunError) as refused:
        ev5.freeze(SEALED | {"journal_sequence": -1}, repository=tmp_path)
    assert "confirmation_not_sealed" in refused.value.blockers
    assert not (tmp_path / ev5.CONTRACT).exists()  # a refusal writes nothing
    result = ev5.freeze(SEALED, repository=tmp_path)
    assert result["written"] == sorted(
        [ev5.CONTRACT, ev5.FREEZE_MANIFEST]
        + [f"{ev5.PLANS}/{name}" for name in ev5.plans()]
    )
    manifest_bytes = (tmp_path / ev5.FREEZE_MANIFEST).read_bytes()
    assert b"\r" not in manifest_bytes
    assert result["manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    assert manifest == json.loads(json.dumps(ev5.freeze_manifest(SEALED, tmp_path)))
    _, digest = ev.load(tmp_path / ev5.CONTRACT)
    assert digest == result["contract_digest"] == manifest["contract"]["digest"]
    # The contract is laid out as EV4's is.
    text = (tmp_path / ev5.CONTRACT).read_text()
    assert text == json.dumps(ev5.contract(), indent=2) + "\n"
    with pytest.raises(cr.CombinedRunError) as again:
        ev5.freeze(SEALED, repository=tmp_path)
    assert again.value.code == "already_frozen"


def test_this_branch_never_sets_the_cutoff():
    for path in (
        "carbon/battery/value/ev5.py",
        "carbon/challenge_readiness/combined_run.py",
    ):
        assert "THRESHOLD_BANDS =" not in (REPOSITORY / path).read_text()


# --- H3: the localized measurement, descriptive (OWNER-EXEC-APPROVALS-01) ---------------


def test_h3_is_the_registered_false_acceptance_measurement_with_no_cutoff():
    measurement = ev5.H3_MEASUREMENT
    assert measurement["schema"] == fa.SCHEMA
    assert measurement["cutoff"] is None and measurement["state"] == "DESCRIPTIVE"
    module = REPOSITORY / measurement["module"]
    assert module.is_file() and module.name == Path(fa.__file__).name
    # The freeze pins exactly the module that computes it.
    pinned = ev5.hypotheses(None)["H3"]["localized_measurement"]
    assert pinned["module_digest"] == (
        "sha256:" + hashlib.sha256(module.read_bytes()).hexdigest()
    )


def test_h3_reports_every_member_and_control_and_never_calls_unmeasured_clean():
    from carbon.battery.value import scoring as sc
    from carbon.battery.value.near import near_cases

    store, case_ids, _ = sc.scoring_set(REPOSITORY)
    near = near_cases(store, case_ids)
    exact = {case: store.refs[case]["outputs"] for case in near}
    partial = dict(list(exact.items())[1:])
    contract, _ = ev.load(ev5.EV4_CONTRACT)  # EV5 carries EV4's bands over
    report = ev5.h3_report(
        contract,
        {"real-exact": exact, "attack-exact": exact, "real-partial": partial},
        {"attack-exact": "ATTACK_CONSTRUCTION"},
    )
    assert report["cutoff"] is None and report["state"] == "DESCRIPTIVE"
    assert report["important_cases"] == len(near) > 0
    members = report["members"]
    assert members["real-exact"]["kind"] == "RECONSTRUCTED"
    assert members["attack-exact"]["kind"] == "ATTACK_CONSTRUCTION"
    # A model that predicts the reference exactly never falsely accepts...
    exact_rate = members["real-exact"]["measurement"]["worst_false_acceptance_rate"]
    assert exact_rate in (None, 0.0)
    # ...and one missing a single important case is unmeasured, not clean.
    assert members["real-partial"]["measurement"] is None
    # The controls are exactly what the measurement's own module computes.
    assert report["controls"] == fa.controls(REPOSITORY)["controls"]
