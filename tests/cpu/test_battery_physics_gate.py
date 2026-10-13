"""PLT-13: prospective B15 admission; public evidence and synthetic control flow.

No hidden packs, real keys, chain or truth solves. Probe pairs here are
explicitly synthetic registration fixtures, never a production probe plan.
"""

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.battery import deployment, exam
from carbon.battery.daemon import COVERAGE_IDENTITY, BatteryValidator, rule_digest
from carbon.battery.physics_gate import (
    CODE,
    CONTRACT,
    PROBE_SCHEMA,
    REFERENCE_IMAGE,
    BatteryPhysics,
    PhysicsRefused,
    verdict,
)
from carbon.battery.pool_store import PoolStore, StateError
from carbon.battery.worker import WorkerFailure
from carbon.challenge_validator.battery import BatteryAdapter, ScoreReplayMismatch

ROOT = Path(__file__).resolve().parents[2]
POOL = {"version": 1, "active": ["f"]}
POINT = {"c1": 1.0, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.2}


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _term(tmp_path, *, change=None, repository=ROOT):
    sha = _hash((repository / CONTRACT).read_bytes())
    pairs = []
    for axis, step in (("c1", 0.075), ("c2", 0.04)):
        pairs.append(
            {
                "axis": axis,
                "base": dict(POINT),
                "partner": {**POINT, axis: POINT[axis] + step},
            }
        )
    plan = {"schema": PROBE_SCHEMA, "contract_sha256": sha, "pairs": pairs}
    if change:
        change(plan)
    path = tmp_path / "synthetic-probes.json"
    raw = json.dumps(plan).encode()
    path.write_bytes(raw)
    return {
        "contract_sha256": sha,
        "probes_path": str(path),
        "probes_sha256": _hash(raw),
        "reference_image": REFERENCE_IMAGE,
    }


@pytest.fixture
def component(tmp_path):
    return BatteryPhysics(_term(tmp_path), ROOT, reference_image=REFERENCE_IMAGE)


def _outputs(temp=25.0, voltage=3.6):
    return {"temperature_c": [temp] * 121, "voltage_v": [voltage] * 121}


def _probes(component, gap=0.0, voltage_gap=0.0):
    return {
        key: _outputs(
            25.0 + (gap if key.endswith("partner") else 0),
            3.6 + (voltage_gap if key.endswith("partner") else 0),
        )
        for key in component.inputs()
    }


def _aggregate():
    return {
        "eligible": True,
        "score": 0.1,
        "important_score": 0.1,
        "gate_failures": {},
        "n_cases": 1,
        "n_scored": 1,
        "n_reference_invalid": 0,
        "n_failed_infra": 0,
        "components": {"temperature": 0.1},
    }


def _daemon(component, monkeypatch, *, probes=None):
    aggregate = _aggregate()
    monkeypatch.setattr(
        exam,
        "evaluate",
        lambda *a: (
            [{"case_id": "case", "state": "SCORABLE", "error": 0.1}],
            copy.deepcopy(aggregate),
        ),
    )
    inputs = {"case": dict(POINT)}
    preds = {"case": _outputs()}
    store = SimpleNamespace(
        active_case_ids=lambda p: ["case"], case_inputs=lambda f: inputs
    )
    target = SimpleNamespace(
        store=store,
        rule=exam.DEVELOPMENT_RULE,
        physics_contract=component,
        _case_store=lambda f: object(),
        _infer=lambda *a: preds,
        _rebuild=lambda m: {
            "schema": "carbon.battery.rebuild-identity.v1",
            "device_class": "synthetic",
        },
        _reference_identity=lambda f: {"f": "sha256:" + "0" * 64},
        _quiz_predictions=lambda *a, **k: (
            _probes(component) if probes is None else probes
        ),
    )
    target._physics = lambda *a: BatteryValidator._physics(target, *a)
    return target


def _score(target):
    return BatteryValidator._pool_records(target, POOL, "model", None, "test")


def test_v2_only_adopts_b15_and_keeps_every_other_law_and_v1():
    v1 = json.loads((ROOT / "carbon/battery/physics_contract.v1.json").read_bytes())
    v2 = json.loads((ROOT / CONTRACT).read_bytes())
    assert [x for x in v2["laws"] if x["id"] != "B15"] == [
        x for x in v1["laws"] if x["id"] != "B15"
    ]
    old = next(x for x in v1["laws"] if x["id"] == "B15")
    new = next(x for x in v2["laws"] if x["id"] == "B15")
    assert old["adoption"] == "HUMAN_INPUT"
    assert new["adoption"] == "ADOPTED" and new["allowance_absolute_c"] == 1e-4
    assert (
        new["gate_max_violation_rate"] == 0
        and new["reference_image"] == REFERENCE_IMAGE
    )


def test_public_retained_members_pass_the_adopted_allowance_and_control_fails():
    path = (
        ROOT / "docs/development/evidence/physics-contract-01/physics-screen-pairs.json"
    )
    screen = json.loads(path.read_bytes())
    readings = screen["laws"]["B15"]["member_residuals"]
    assert screen["members"] == len(readings) == 142
    good = set(screen["good_members"])
    assert len(good) == 65
    for member in good:
        row = readings[member]
        assert row["points"] == 200 and row["missing_pairs"] == 0
        assert verdict([row["max"]], expected=1)["eligible"], member
    rebuilt = [m for m in readings if not m.startswith("control-")]
    assert len(rebuilt) == 137
    assert all(verdict([readings[m]["max"]], expected=1)["eligible"] for m in rebuilt)
    assert readings["control-boundary_optimist"]["max"] == pytest.approx(3.5)
    assert (
        verdict([readings["control-boundary_optimist"]["max"]], expected=1)["code"]
        == CODE
    )


@pytest.mark.parametrize(
    "values, expected, unresolved, passes",
    [
        ([0, 1e-4], 2, 0, True),
        ([0, 1.00001e-4], 2, 0, False),
        ([], 0, 0, False),
        ([0], 2, 1, False),
        ([float("nan")], 1, 0, False),
    ],
)
def test_allowance_is_inclusive_zero_rate_and_incomplete_never_passes(
    values, expected, unresolved, passes
):
    assert (
        verdict(values, expected=expected, unresolved=unresolved)["eligible"] is passes
    )


def test_checker_excludes_switch_and_card_metrics_cannot_fail_b15(component):
    probes = _probes(component, voltage_gap=0.016)
    for key in probes:
        if key.endswith("partner"):
            probes[key]["temperature_c"][4:] = [100.0] * 117
    measured = component.measure(
        probes,
        [(POINT, _outputs(23.5)), (POINT, _outputs(24.5)), (POINT, _outputs(25.0))],
    )
    assert measured["B15"]["eligible"]
    assert measured["model_card"]["B16"]["rest_voltage_leak_mv"] == pytest.approx(16)
    b9 = measured["model_card"]["B9"]
    assert b9["max_below_ambient_deficit_c"] == 1.5
    assert b9["share_cases_gt_0_1_c"] == 2 / 3
    assert b9["share_cases_gt_1_c"] == 1 / 3
    assert b9["n_checked"] == 3 and b9["n_unresolved"] == 0


def test_missing_measurements_report_no_information_and_do_not_become_zero(component):
    measured = component.measure({}, [(POINT, {})])
    assert measured["B15"]["code"] == CODE
    assert measured["model_card"]["B16"]["rest_voltage_leak_mv"] is None
    assert measured["model_card"]["B9"]["share_cases_gt_0_1_c"] is None
    assert measured["model_card"]["B9"]["n_unresolved"] == 1
    assert measured["B15"]["n_violations"] == 0
    assert measured["B15"]["n_unresolved"] == 2


def test_overflowing_voltage_metric_stays_unresolved_without_changing_gate(component):
    probes = _probes(component)
    for key, output in probes.items():
        output["voltage_v"] = [1e308 if key.endswith("partner") else -1e308] * 121
    measured = component.measure(probes, [])
    assert measured["B15"]["eligible"]
    assert measured["model_card"]["B16"]["rest_voltage_leak_mv"] is None
    json.dumps(measured, allow_nan=False)


def test_component_data_is_immutable_and_views_do_not_change_it(component):
    identity = component.identity
    identity["reference_image"] = "changed"
    inputs = component.inputs()
    inputs["p0-base"]["c1"] = 2.0
    assert component.identity["reference_image"] == REFERENCE_IMAGE
    assert component.inputs()["p0-base"] == POINT
    with pytest.raises(AttributeError):
        component._plan = b"changed"


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(pairs=[]),
        lambda p: p["pairs"].pop(),
        lambda p: p["pairs"][0]["partner"].update(soc0=0.3),
        lambda p: p["pairs"][0]["partner"].update(c1=2.1),
        lambda p: p["pairs"].append(p["pairs"][0]),
        lambda p: p.update(extra=1),
    ],
)
def test_unregistered_incomplete_or_wrong_geometry_is_refused(tmp_path, change):
    with pytest.raises(PhysicsRefused):
        BatteryPhysics(
            _term(tmp_path, change=change), ROOT, reference_image=REFERENCE_IMAGE
        )


def test_digest_image_and_adoption_changes_are_refused(tmp_path):
    term = _term(tmp_path)
    with pytest.raises(PhysicsRefused, match="image_mismatch"):
        BatteryPhysics(term, ROOT, reference_image="sha256:" + "0" * 64)
    with pytest.raises(PhysicsRefused, match="digest"):
        BatteryPhysics(
            {**term, "probes_sha256": "0" * 64}, ROOT, reference_image=REFERENCE_IMAGE
        )
    repo = tmp_path / "repository"
    (repo / "carbon/battery").mkdir(parents=True)
    v2 = json.loads((ROOT / CONTRACT).read_bytes())
    next(x for x in v2["laws"] if x["id"] == "B15")["allowance_absolute_c"] = 0.01
    (repo / CONTRACT).write_text(json.dumps(v2))
    with pytest.raises(PhysicsRefused, match="adoption"):
        BatteryPhysics(
            _term(tmp_path, repository=repo), repo, reference_image=REFERENCE_IMAGE
        )
    (repo / CONTRACT).write_bytes((ROOT / CONTRACT).read_bytes())
    with pytest.raises(PhysicsRefused, match="legacy_unavailable"):
        BatteryPhysics(
            _term(tmp_path, repository=repo), repo, reference_image=REFERENCE_IMAGE
        )


def test_legacy_deployment_score_is_exact_golden_and_requests_no_probes(monkeypatch):
    target = _daemon(None, monkeypatch)
    target._quiz_predictions = lambda *a, **k: pytest.fail("legacy called probes")
    expected = {
        "model_id": "model",
        "pool_version": 1,
        "rebuild": {
            "schema": "carbon.battery.rebuild-identity.v1",
            "device_class": "synthetic",
        },
        "active_batches": ["f"],
        "references": {"f": "sha256:" + "0" * 64},
        "rule_digest": rule_digest(exam.DEVELOPMENT_RULE),
        "coverage_rule": dict(COVERAGE_IDENTITY),
        **_aggregate(),
        "screening_noise": {"errors": [0.1]},
        "nomination": {
            "nominated": True,
            "reason": "no incumbent",
            "incumbent": None,
            "incumbent_score": None,
        },
    }
    assert json.dumps(_score(target), sort_keys=True) == json.dumps(
        expected, sort_keys=True
    )


def test_screening_gate_cannot_be_compensated_by_score_and_keeps_old_gates(
    component, monkeypatch
):
    target = _daemon(component, monkeypatch, probes=_probes(component, gap=3.5))
    record = _score(target)
    assert record["score"] == 0.1
    assert not record["eligible"] and not record["nomination"]["nominated"]
    assert record["gate_failures"] == {CODE: 1}
    public = BatteryValidator._public_score(target, record)
    assert public["gates_failed"] == [CODE]
    assert "physics" not in public and "model_card" not in public
    aggregate = _aggregate()
    aggregate.update(eligible=False, gate_failures={"voltage_ceiling": 1})
    monkeypatch.setattr(exam, "evaluate", lambda *a: ([], copy.deepcopy(aggregate)))
    target._quiz_predictions = lambda *a, **k: _probes(component)
    record = _score(target)
    assert not record["eligible"] and record["gate_failures"] == {"voltage_ceiling": 1}


def test_component_is_new_state_and_cannot_be_carried_over(component, tmp_path):
    store = PoolStore(tmp_path / "state.sqlite3")
    old = {"schema": "synthetic", "rule_digest": "same"}
    store.bind(old)
    new = {**old, "physics_contract": component.identity}
    with pytest.raises(StateError, match="identities_changed"):
        store.bind(new)
    with pytest.raises(StateError):
        store.rebind(new, decision="OWNER-PHYSICS-GATES-01")
    fresh = PoolStore(tmp_path / "new-state.sqlite3")
    fresh.bind(new)
    with pytest.raises(StateError):
        fresh.bind(old)


def test_daemon_identity_adds_only_the_optional_component(
    component, tmp_path, monkeypatch
):
    monkeypatch.setattr("carbon.battery.daemon.PublicMaterial.load", lambda r: object())
    monkeypatch.setattr("carbon.battery.daemon.frozen_calibration", lambda r: ({}, {}))

    def validator(physics=None):
        return BatteryValidator(
            store=PoolStore(tmp_path / ("new.sqlite3" if physics else "old.sqlite3")),
            backend=SimpleNamespace(identity={"backend": "SYNTHETIC"}),
            root=object(),
            journal=SimpleNamespace(
                root_pin=lambda r: {"scoring_digest": rule_digest()}
            ),
            repository=ROOT,
            physics_contract=physics,
        )

    legacy, adopted = validator(), validator(component)
    old = legacy.identities()
    new = adopted.identities()
    assert "physics_contract" not in old
    assert new.pop("physics_contract") == component.identity
    assert old == new
    with pytest.raises(TypeError, match="validated BatteryPhysics"):
        validator({"adopted": True})


def test_process_routes_probe_infrastructure_to_retry_never_a_gate(
    component, monkeypatch
):
    target = _daemon(component, monkeypatch)
    row = {"state": "RECONSTRUCTED", "binding": {"attempt": 0}}
    marks, retries = [], []
    target.store.submission = lambda s: row
    target.store.pool = lambda: {**POOL, "status": "OPEN"}
    target.store.model_state = lambda s: {"state": "synthetic"}
    target.store.mark = lambda *a: marks.append(a)
    target._bump_attempt = lambda *a: retries.append(a)
    target._settle = lambda: None
    target._recipe = lambda r: object()
    target.outcome = lambda s: {"state": marks[-1][1], "failure": marks[-1][2]}
    target._screen = lambda *a: _score(target)

    def fail(*a, **k):
        raise WorkerFailure("synthetic_infrastructure", candidate=False)

    target._quiz_predictions = fail
    outcome = BatteryValidator.process(target, "model")
    assert outcome == {
        "state": "FAILED_INFRA",
        "failure": {"code": "synthetic_infrastructure", "attempt": 0},
    }
    assert retries == [("model", 1)] and CODE not in json.dumps(outcome)

    def candidate_fail(*a, **k):
        raise WorkerFailure("prediction_cases_differ", candidate=True)

    target._quiz_predictions = candidate_fail
    assert _score(target)["physics"]["B15"]["code"] == CODE


def test_finalist_gate_runs_on_fresh_models_and_infra_never_decides(
    component, monkeypatch
):
    target = _daemon(component, monkeypatch)
    frozen = {
        "seed": 0,
        "incumbent_recipe": "r",
        "challenger_recipe": "r",
        "rule": exam.RULES["v1"]["comparison"]
        | {"equivalence_margin": exam.RULES["v1"]["equivalence_margin_rel"]},
    }
    final = {
        "state": "FROZEN",
        "incumbent": "inc",
        "challenger": "chal",
        "frozen": frozen,
    }
    attempts = []
    target.store.final = lambda f: final
    target.store.final_attempt = lambda f: 0
    target.store.incumbent = lambda: {"model_id": "inc"}
    target.store.claim_finalist_set = lambda f: "f"
    target.store.batch = lambda f: {"document": {"cases": [{"case_id": "case"}]}}
    target.store.submission = lambda s: {"binding": {}}
    target.store.model_state = lambda s: {"state": "synthetic"}
    target.store.bump_final_attempt = lambda *a: attempts.append(a)
    target._recipe = lambda r: SimpleNamespace(recipe_digest="r")
    target._decide = lambda f, out, fp: out
    target._case_store = lambda f: SimpleNamespace(
        refs={"case": {"status": "OK"}}, important=lambda c: True
    )
    monkeypatch.setattr(
        exam,
        "final_compare",
        lambda *a, **k: {"outcome": "IMPROVEMENT", "promotable": k["chal_eligible"]},
    )
    monkeypatch.setattr("carbon.battery.rebuild_identity.comparable", lambda *a: True)
    measured = []

    def probes(model, inputs, tag, **kwargs):
        measured.append(model)
        return _probes(component, gap=3.5 if model.endswith("challenger") else 0)

    target._quiz_predictions = probes
    result = BatteryValidator.process_final(target, "final")
    assert measured == ["final-incumbent", "final-challenger"]
    assert result["physics_gate"] == CODE and not result["promotable"]

    def fail(*a, **k):
        raise WorkerFailure("probe_node_unavailable", candidate=False)

    target._quiz_predictions = fail
    result = BatteryValidator.process_final(target, "final")
    assert result["status"] == "FAILED_INFRA" and "physics_gate" not in result
    assert attempts == [("final", 1)]


def test_operator_replay_rechecks_card_and_gate_without_inference(
    component, monkeypatch
):
    target = _daemon(component, monkeypatch, probes=_probes(component, gap=3.5))
    record = _score(target)
    preds = {"case": _outputs()}
    target.store.score = lambda s: {"record": record}
    target.store.batch = lambda f: {"document": {"cases": [{"case_id": "case"}]}}
    target.store.predictions = lambda model, ids: (
        _probes(component, gap=3.5) if model.startswith(component.namespace) else preds
    )
    target.store.quiz_report = lambda s: None
    target._quiz_predictions = lambda *a, **k: pytest.fail("read-only replay inferred")
    adapter = SimpleNamespace(target=target)
    result = BatteryAdapter.score_record(adapter, "model")
    assert result["physics"]["B15"]["code"] == CODE
    assert result["aggregate"]["eligible"] is False
    record["physics"]["model_card"]["B9"]["max_below_ambient_deficit_c"] = 42
    with pytest.raises(ScoreReplayMismatch):
        BatteryAdapter.score_record(adapter, "model")


def test_deployment_accepts_only_complete_pinned_term(tmp_path):
    from carbon.battery.physics_gate import check_term

    term = _term(tmp_path)
    assert check_term(term) == term
    with pytest.raises(PhysicsRefused):
        check_term({**term, "adopted": True})
    # Build rejects before reading any private root or dispatching work.
    with pytest.raises(deployment.EvaluationUnavailable, match="digest"):
        deployment.build(
            {"physics_contract": {**term, "contract_sha256": "0" * 64}}, repository=ROOT
        )
    with pytest.raises(deployment.EvaluationUnavailable, match="testnet_only"):
        deployment.build(
            {"physics_contract": term, "commitment_reader": {"network": "mainnet"}},
            repository=ROOT,
        )
