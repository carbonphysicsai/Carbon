"""EV5 before its freeze: fixture checks only (no PyBaMM, no network, no pod).

- the fresh conditions are the draft's, inside the published box, never
  repeated, fresh against every EV1, EV2 and EV4 decision condition, and
  protected from research agents as EV4's are;
- the optimizer keeps EV4's maxima, and a plan above them is refused;
- the panel keeps EV4's 100 members, seeds and 5 controls byte for byte, and
  adds the Track A harness's admitted constructions as ATTACK_CONSTRUCTION
  members, rebuilt, scored and value-tested like real ones; participant code
  and GRAPHITE constructions are refused by name;
- the contract, plans and campaign are built as EV4's were, and nothing
  dispatches;
- the freeze manifest refuses while the gate cutoff is unset, and builds once
  it is set (here monkeypatched; this file never sets it).
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
from carbon.battery import track_a
from carbon.battery.compile import compile_recipe
from carbon.battery.value import admissibility, ev5
from carbon.battery.value import contract as ev
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
        (float(t), s) for t in (10, 20, 30, 39) for s in (0.07, 0.20, 0.38)
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


def test_three_verification_conditions_sit_on_ev4s_protected_model_grid():
    # An open question, not a pass: `ev4_protected_conditions` counts EV4's
    # optimizer model-query grid as EV4 material, and three proposed
    # verification conditions are on it. The freeze refuses until it is
    # answered (see the freeze tests).
    found = cr.repeats(
        ev5.conditions(), {"ev4_protected": ev5.prior_conditions()["ev4_protected"]}
    )
    assert [(r["split"], tuple(r["condition"])) for r in found] == [
        ("verification", (10.0, 0.2)),
        ("verification", (20.0, 0.2)),
        ("verification", (30.0, 0.2)),
    ]
    assert all(tuple(r["condition"]) in EV4_MODEL for r in found)


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
    }
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
    tmp_path, scoring_refs, small_ev5  # noqa: F811
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
    # Written only at the freeze; then this becomes a digest pin, as EV4's is.
    assert not (REPOSITORY / ev5.CONTRACT).exists()


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
    assert not (REPOSITORY / ev5.EVIDENCE / "accounting").exists()


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
    assert skeleton["solved_on"] is None  # open: where the private cases run
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
    assert blockers[0] == "gate_cutoff_unset"
    assert blockers[1].startswith("conditions_not_fresh: [10.0, 0.2] in ev4_protected")
    assert blockers[2:] == ("confirmation_not_sealed",)


def test_the_freeze_manifest_builds_once_the_cutoff_is_set(monkeypatch):
    # Synthetic stand-ins for three answers this branch does not give: the
    # cutoff (#528), whether EV4's protected optimizer grid counts as EV4
    # conditions, and the sealed batch's public commitment.
    monkeypatch.setattr(admissibility, "THRESHOLD_BANDS", 1.2345)
    with pytest.raises(cr.CombinedRunError) as refused:
        ev5.freeze_manifest(SEALED)
    assert [x.split(":")[0] for x in refused.value.blockers] == ["conditions_not_fresh"]
    monkeypatch.setattr(ev5, "FRESH_AGAINST", ev5.PRIOR_STUDIES)
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
    assert hypotheses["H3"]["localized_measurement"] is None  # TODO(EV5-H3)
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
    assert not any(manifest["claims"].values())
    assert not (REPOSITORY / ev5.EVIDENCE).exists()  # nothing written


def test_this_branch_never_sets_the_cutoff():
    for path in (
        "carbon/battery/value/ev5.py",
        "carbon/challenge_readiness/combined_run.py",
    ):
        assert "THRESHOLD_BANDS =" not in (REPOSITORY / path).read_text()
