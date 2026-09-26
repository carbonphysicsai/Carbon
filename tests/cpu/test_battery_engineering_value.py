"""EV1: the fixed-candidate engineering-value experiment.

The decision logic is tested on hand-built cases. The end-to-end run uses:
- a deterministic fixture solver (an analytic stand-in for PyBaMM,
  labelled so), through the real truth service;
- a fixture backend, through the real panel path.

Neither is numerical evidence. The authentic run uses pinned PyBaMM and
real reconstructions.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from carbon.battery.value import contract as ev
from carbon.battery.value import decision as d
from carbon.battery.value import panel as pn
from carbon.battery.value.experiment import Experiment, ExperimentError, _decide
from carbon.scoring import weight_profile as wp

REPOSITORY = Path(__file__).resolve().parents[2]
CONTRACT, _ = ev.load()


# --- a small analytic world (fixture only) ----------------------------------------------


def outputs_for(c1, c2, t_amb, soc0, *, plating_shift=0.0, temp_shift=0.0):
    """Faster charging reaches CV sooner, plates more when cold, runs hotter."""
    grid = [30.0 * i for i in range(121)]
    rate = 0.55 * c1 + 0.45 * c2
    reach = 120.0 + (1.0 - soc0) * 2400.0 / rate
    voltage = []
    for t in grid:
        if t <= 120.0:
            voltage.append(3.6)
        else:
            voltage.append(min(4.2, 3.6 + 0.6 * (t - 120.0) / (reach - 120.0)))
    peak = t_amb + 7.0 * c1 + 3.0 * c2 + temp_shift
    temperature = [t_amb + (peak - t_amb) * min(1.0, t / 1800.0) for t in grid]
    margin = 0.02 - 0.02 * c1 + 0.0012 * (t_amb - 15.0) + plating_shift
    return {
        "voltage_v": voltage,
        "temperature_c": temperature,
        "plating_margin_v": margin,
        "capacity_ah": [5.0, 4.95, 4.9, 4.85],
    }


def fixture_solver(job):
    return {
        "status": "OK",
        "outputs": outputs_for(job["c1"], job["c2"], job["t_amb_c"], job["soc0"]),
    }


def scenario(conditions, sid="T"):
    return {"id": sid, "split": "development", "conditions": conditions}


def reference_for(sc, candidates, **shift):
    refs = {}
    for c in candidates:
        for i, (t, s) in enumerate(sc["conditions"]):
            refs[(c["id"], i)] = {
                "status": "OK",
                "outputs": outputs_for(c["c1"], c["c2"], t, s, **shift),
            }
    return refs


def predictions_for(sc, candidates, transform=lambda o, c, i: o):
    preds = {}
    for c in candidates:
        for i, (t, s) in enumerate(sc["conditions"]):
            outputs = outputs_for(c["c1"], c["c2"], t, s)
            preds[f"ev1:{sc['id']}:{c['id']}:{i}"] = transform(outputs, c, i)
    return preds


CANDIDATES = ev.candidates(CONTRACT)
BASELINE = ev.candidate_id(CONTRACT["baseline"]["protocol"])


def verified(sc, **shift):
    return d.assess_reference(
        CONTRACT, sc, CANDIDATES, reference_for(sc, CANDIDATES, **shift)
    )


# --- the contract --------------------------------------------------------------------------


def test_the_contract_is_versioned_valid_and_public_synthetic():
    assert CONTRACT["schema"] == ev.SCHEMA
    assert ev.load()[1] == ev.digest(CONTRACT)
    assert len(CANDIDATES) == 16
    assert len(ev.decision_cases(CONTRACT)) == 16 * 4 * 6
    assert CONTRACT["data_scope"]["classification"] == "PUBLIC_SYNTHETIC"
    assert CONTRACT["authority"] == {
        "record": CONTRACT["authority"]["record"],
        "chain": False,
        "reward": False,
        "changes_testnet_rule": False,
        "qualification": False,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["data_scope"].update(classification="CLIENT_CONFIDENTIAL"),
        lambda c: c["scenarios"]["development"][0]["conditions"].append([60.0, 0.1]),
        lambda c: c["baseline"]["protocol"].update(c1=1.1),
        lambda c: c["design_variables"]["c1"]["allowed"].append(3.0),
        lambda c: c["scoring_candidates"]["weight_profiles"].append(
            {
                "id": "bad",
                "weights": {"physics": 0.5, "robustness": 0.5, "accuracy": 0.5},
            }
        ),
        lambda c: c["authority"].update(reward=True),
    ],
)
def test_the_contract_refuses_by_name(mutate):
    document = copy.deepcopy(CONTRACT)
    mutate(document)
    with pytest.raises((ev.ContractError, wp.WeightProfileError)):
        ev.validate(document)


# --- measurement -------------------------------------------------------------------------------


def test_time_to_cv_onset_is_interpolated_and_unreached_is_not_the_window():
    fast = ev.candidates(CONTRACT)[-1]
    q = d.measure(CONTRACT, outputs_for(fast["c1"], fast["c2"], 25.0, 0.3))
    assert 0 < q["time_to_cv_onset_s"] < 3480
    slow = outputs_for(0.75, 0.4, 25.0, 0.05)
    slow["voltage_v"] = [min(v, 4.1) for v in slow["voltage_v"]]
    assert d.measure(CONTRACT, slow)["time_to_cv_onset_s"] is None


# --- the decision ------------------------------------------------------------------------------


WARM = scenario([[25.0, 0.1], [25.0, 0.3]], "warm")
COLD = scenario([[5.0, 0.1], [5.0, 0.3]], "cold")


def decide(sc, reference, transform=lambda o, c, i: o):
    outcome, agreement = _decide(
        CONTRACT,
        sc,
        CANDIDATES,
        predictions_for(sc, CANDIDATES, transform),
        reference,
        BASELINE,
    )
    return outcome, agreement


def test_a_known_best_feasible_candidate_is_selected_by_an_accurate_model():
    reference = verified(WARM)
    best = d.best_in_set(CANDIDATES, reference)
    assert best is not None
    outcome, agreement = decide(WARM, reference)
    assert outcome["kind"] == "SELECTED_FEASIBLE" and outcome["selected"] == best
    assert outcome["gap_to_best_in_set_s"] == 0.0 and outcome["decision_loss"] == 0.0
    assert agreement["false_acceptances"] == agreement["false_rejections"] == 0


def test_the_fastest_candidate_is_not_best_when_it_is_infeasible():
    reference = verified(WARM)
    fastest = min(
        (c for c in CANDIDATES if reference[c["id"]]["objective"] is not None),
        key=lambda c: reference[c["id"]]["objective"],
    )
    assert reference[fastest["id"]]["status"] == d.INFEASIBLE
    assert d.best_in_set(CANDIDATES, reference) != fastest["id"]


def test_no_feasible_candidate_means_correct_abstention():
    reference = verified(COLD)
    assert d.best_in_set(CANDIDATES, reference) is None
    outcome, _ = decide(COLD, reference)
    assert outcome["kind"] == "CORRECT_ABSTENTION" and outcome["decision_loss"] == 0.0


def test_incorrect_abstention_is_a_missed_opportunity():
    reference = verified(WARM)

    def pessimist(outputs, c, i):
        return {**outputs, "plating_margin_v": -1.0}

    outcome, agreement = decide(WARM, reference, pessimist)
    assert outcome["kind"] == "MISSED_OPPORTUNITY"
    assert outcome["decision_loss"] == CONTRACT["mistake_costs"]["missed_opportunity"]
    assert agreement["false_rejections"] > 0


def test_a_localized_error_changes_the_selected_design_and_costs_a_false_acceptance():
    reference = verified(WARM)
    fastest = min(
        (c for c in CANDIDATES if reference[c["id"]]["objective"] is not None),
        key=lambda c: reference[c["id"]]["objective"],
    )

    def optimistic_there(outputs, c, i):
        if c["id"] == fastest["id"]:
            return {
                **outputs,
                "plating_margin_v": 0.05,
                "temperature_c": [20.0] * len(outputs["temperature_c"]),
            }
        return outputs

    outcome, agreement = decide(WARM, reference, optimistic_there)
    assert outcome["selected"] == fastest["id"]
    assert outcome["kind"] == "SELECTED_INFEASIBLE"
    assert outcome["decision_loss"] == CONTRACT["mistake_costs"]["false_acceptance"]
    assert agreement["false_acceptances"] == 1
    assert outcome["violations"]


def test_predicting_an_unacceptable_outcome_correctly_is_not_a_model_failure():
    reference = verified(COLD)
    outcome, agreement = decide(COLD, reference)
    # Every protocol plates in the cold: the model says so, and that is right.
    assert agreement["false_acceptances"] == 0 and agreement["false_rejections"] == 0
    assert outcome["kind"] == "CORRECT_ABSTENTION"


def test_reference_uncertainty_at_a_constraint_boundary_stays_unresolved():
    band = CONTRACT["reference"]["uncertainty"]["bands"]["plating_margin_v"]
    candidate = CANDIDATES[0]
    sc = scenario([[25.0, 0.3]], "edge")
    refs = reference_for(sc, CANDIDATES)
    edge = copy.deepcopy(refs[(candidate["id"], 0)])
    edge["outputs"]["plating_margin_v"] = band / 2  # inside the band
    refs[(candidate["id"], 0)] = edge
    reference = d.assess_reference(CONTRACT, sc, CANDIDATES, refs)
    assert reference[candidate["id"]]["status"] == d.UNRESOLVED
    outcome = d.outcome(CONTRACT, CANDIDATES, candidate["id"], reference, BASELINE)
    assert outcome["kind"] == "SELECTED_UNRESOLVED" and outcome["decision_loss"] is None


def test_missing_references_and_missing_outputs_are_not_candidate_failures():
    refs = reference_for(WARM, CANDIDATES)
    del refs[(CANDIDATES[3]["id"], 1)]
    refs[(CANDIDATES[4]["id"], 0)] = {"status": "REFERENCE_SOLVER_FAILED"}
    reference = d.assess_reference(CONTRACT, WARM, CANDIDATES, refs)
    assert reference[CANDIDATES[3]["id"]]["status"] == d.UNAVAILABLE
    assert reference[CANDIDATES[4]["id"]]["status"] == d.UNAVAILABLE
    preds = predictions_for(WARM, CANDIDATES)
    preds.pop(next(iter(preds)))
    outcome, agreement = _decide(CONTRACT, WARM, CANDIDATES, preds, reference, BASELINE)
    assert outcome["kind"] == "MODEL_OUTPUT_MISSING" and agreement is None


def test_selection_never_sees_reference_answers():
    """The selector's inputs are a model's predictions only: changing every
    reference answer changes the verification, never the selection."""
    a = decide(WARM, verified(WARM))[0]
    b = decide(WARM, verified(WARM, plating_shift=-1.0, temp_shift=40.0))[0]
    assert a["selected"] == b["selected"]
    assert a["kind"] != b["kind"]


def test_ties_are_broken_deterministically():
    predicted = {c["id"]: {"feasible": True, "objective": 100.0} for c in CANDIDATES}
    assert d.select(CANDIDATES, predicted) == CANDIDATES[0]["id"]
    assert d.select(list(reversed(CANDIDATES)), predicted) == CANDIDATES[0]["id"]


# --- zero-weight scoring semantics --------------------------------------------------------------


def test_zero_weight_profiles_omit_the_leg_but_never_the_evidence():
    profile = wp.parse(
        {"id": "z", "weights": {"physics": 0, "robustness": 0.3, "accuracy": 0.7}}
    )
    assert profile.positive == ("robustness", "accuracy")
    value = wp.combine(profile, {"physics": None, "robustness": 0.5, "accuracy": 0.8})
    assert math.isclose(value, math.exp(0.3 * math.log(0.5) + 0.7 * math.log(0.8)))
    assert wp.combine(profile, {"robustness": 0.0, "accuracy": 0.8}) == 0.0
    with pytest.raises(wp.WeightProfileError) as missing:
        wp.combine(profile, {"robustness": None, "accuracy": 0.8})
    assert missing.value.code == "missing_component"
    full = wp.parse(
        {"id": "f", "weights": {"physics": 0.45, "robustness": 0.3, "accuracy": 0.25}}
    )
    with pytest.raises(wp.WeightProfileError) as unmeasurable:
        wp.combine(full, {"physics": None, "robustness": 0.5, "accuracy": 0.8})
    assert unmeasurable.value.code == "missing_component"


@pytest.mark.parametrize(
    ("weights", "code"),
    [
        ({"physics": 0, "robustness": 0, "accuracy": 0}, "all_zero"),
        ({"physics": 0, "robustness": 0.3, "accuracy": 0.6}, "weight_sum"),
        ({"physics": -0.1, "robustness": 0.4, "accuracy": 0.7}, "weight_range"),
        ({"robustness": 0.3, "accuracy": 0.7}, "weight_legs"),
    ],
)
def test_bad_profiles_are_refused(weights, code):
    with pytest.raises(wp.WeightProfileError) as refused:
        wp.parse({"id": "x", "weights": weights})
    assert refused.value.code == code


def test_the_core_score_pack_still_requires_three_positive_weights():
    import inspect

    from carbon.scoring import pack

    source = inspect.getsource(pack._validate_number)
    assert "decimal_value <= zero" in source


# --- end to end ------------------------------------------------------------------------------


class FixtureBackend:
    """Reconstruct/infer stand-in: accurate on the scoring set's references,
    analytic on decision inputs, with a per-family perturbation. Test only."""

    def __init__(self, scoring_refs, fail_on=None):
        self.identity = {"backend": "FIXTURE_TEST_ONLY", "validator_path": False}
        self.scoring_refs = scoring_refs
        self.fail_on = fail_on
        self.calls = {"reconstruct": 0, "infer": 0}

    def reconstruct(self, identity, recipe, seed):
        if self.fail_on and self.fail_on in identity:
            raise RuntimeError("interrupted")
        self.calls["reconstruct"] += 1
        return json.dumps({"id": identity, "seed": seed}).encode(), {"fixture": True}

    def infer(self, identity, state, inputs):
        self.calls["infer"] += 1
        member = json.loads(state)["id"]
        shift = {"knn": 0.02, "mlp_half": 0.006, "mlp_raw": 0.0}.get(
            member.split("-", 2)[-1].rsplit("-s", 1)[0], 0.001
        )
        out = {}
        for case_id, x in inputs.items():
            if case_id in self.scoring_refs:
                o = copy.deepcopy(self.scoring_refs[case_id]["outputs"])
                o["plating_margin_v"] += shift
            else:
                o = outputs_for(
                    x["c1"], x["c2"], x["t_amb_c"], x["soc0"], plating_shift=shift
                )
            out[case_id] = o
        return out


@pytest.fixture(scope="module")
def scoring_refs():
    from carbon.battery.value import scoring as sc

    store, _, _ = sc.scoring_set(REPOSITORY)
    return store.refs


def test_the_experiment_runs_end_to_end_and_resumes_without_rework(
    tmp_path, scoring_refs
):
    root = tmp_path / "ev1"
    experiment = Experiment(root, repository=REPOSITORY)
    backend = FixtureBackend(scoring_refs, fail_on="mlp_ens3")
    # Interrupted: the last member fails; everything before it is kept.
    with pytest.raises(RuntimeError):
        experiment.run(solver=fixture_solver, backend=backend, workers=2)
    status = experiment.status()
    assert status["references"]["terminal"] == 384
    assert status["panel"]["missing"] == ["mlp_ens3-s0"]
    solved = len(experiment._reference_records())
    # Resume: nothing solved or reconstructed twice.
    backend.fail_on = None
    before = backend.calls["reconstruct"]
    result = experiment.run(solver=fixture_solver, backend=backend, workers=2)
    assert result["status"] == "EVALUATED"
    assert len(experiment._reference_records()) == solved
    assert backend.calls["reconstruct"] - before == 1
    status = experiment.status()
    assert status["status"] == "EVALUATED" and status["paid_resources"].startswith(
        "none"
    )
    results = json.loads((root / "results" / "results.json").read_text())
    assert results["claims"]["best_in_tested_set_is_global_optimum"] is False
    assert results["comparison"]["p45-r30-a25"]["measurable"] is False
    assert results["summary"]["chosen_rule_on_development"] is not None
    kinds = {v["kind"] for v in results["summary"]["members"].values()}
    assert kinds == {"RECONSTRUCTED", "SYNTHETIC_CONTROL"}
    report = (root / "results" / "report.md").read_text()
    assert "best in the tested candidate set" in report
    out = experiment.export(tmp_path / "export")
    assert sorted(out["files"]) == ["manifest.json", "report.md", "results.json"]


def test_a_different_contract_or_artifact_is_refused(tmp_path, scoring_refs):
    root = tmp_path / "ev1"
    experiment = Experiment(root, repository=REPOSITORY)
    experiment.freeze()
    other = copy.deepcopy(CONTRACT)
    other["minimum_useful_improvement_s"] = 60.0
    path = tmp_path / "other.json"
    path.write_text(json.dumps(other))
    with pytest.raises(ExperimentError) as mismatch:
        experiment.freeze(path)
    assert mismatch.value.code == "contract_mismatch"
    # A retained prediction from another recipe is never reinterpreted.
    experiment.references(solver=fixture_solver, workers=2)
    experiment.panel(backend=FixtureBackend(scoring_refs))
    member = pn.members()[0][0]
    import gzip

    bundle_path = experiment._prediction_path(member)
    bundle = json.loads(gzip.decompress(bundle_path.read_bytes()))
    bundle["recipe_digest"] = "sha256:" + "0" * 64
    bundle_path.chmod(0o600)
    bundle_path.write_bytes(gzip.compress(json.dumps(bundle).encode()))
    with pytest.raises(ExperimentError) as artifact:
        experiment.evaluate()
    assert artifact.value.code == "artifact_mismatch"


def test_references_from_elsewhere_must_match_the_frozen_inputs(tmp_path):
    experiment = Experiment(tmp_path / "ev1", repository=REPOSITORY)
    experiment.freeze()
    job = ev.decision_cases(CONTRACT)[0]
    records = tmp_path / "records.jsonl"
    records.write_text(
        json.dumps(
            {
                "case_id": job["case_id"],
                "status": "OK",
                "inputs": {
                    **{k: job[k] for k in ("c1", "c2", "t_amb_c", "soc0")},
                    "c1": 9.9,
                },
                "outputs": {},
            }
        )
        + "\n"
    )
    with pytest.raises(ExperimentError) as refused:
        experiment.import_references(records)
    assert refused.value.code == "reference_inputs_mismatch"


def test_one_runner_per_root(tmp_path):
    experiment = Experiment(tmp_path / "ev1", repository=REPOSITORY)
    other = Experiment(tmp_path / "ev1", repository=REPOSITORY)
    with experiment.lock(), pytest.raises(ExperimentError) as busy, other.lock():
        pass
    assert busy.value.code == "experiment_busy"


def test_missing_prerequisites_are_reported_not_faked(tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "pybamm", None)
    experiment = Experiment(tmp_path / "ev1", repository=REPOSITORY)
    experiment.freeze()
    result = experiment.references()
    assert result["status"] == "MISSING_PREREQUISITE"
    assert result["code"] == "truth_runtime_unavailable"
    assert "--network" in result["solve_command"]
    with pytest.raises(ExperimentError) as missing:
        experiment.evaluate()
    assert missing.value.code == "prerequisites_missing"


# --- the Workbench adapter ---------------------------------------------------------------------


def test_the_workbench_imports_only_public_synthetic_contracts():
    from carbon.scientific_tasks import workbench_value as wb

    view = wb.contract_view(copy.deepcopy(CONTRACT))
    assert view["schema"] == wb.CONTRACT_VIEW
    assert view["contract"]["digest"] == ev.digest(CONTRACT)
    assert view["qualification"] == "NOT_QUALIFIED"
    client = copy.deepcopy(CONTRACT)
    client["data_scope"]["classification"] = "CLIENT_CONFIDENTIAL"
    with pytest.raises(wb.StudyRefused) as refused:
        wb.contract_view(client)
    assert refused.value.code == "client_material_requires_private_route"
    broken = copy.deepcopy(CONTRACT)
    broken["baseline"]["protocol"]["c1"] = 1.1
    with pytest.raises(wb.StudyRefused):
        wb.contract_view(broken)


def test_the_workbench_reads_retained_results_without_rerunning(tmp_path, scoring_refs):
    from carbon.scientific_tasks import workbench_value as wb

    experiment = Experiment(tmp_path / "ev1", repository=REPOSITORY)
    experiment.run(
        solver=fixture_solver, backend=FixtureBackend(scoring_refs), workers=2
    )
    results = json.loads((tmp_path / "ev1" / "results" / "results.json").read_text())
    view = wb.results_view(results)
    assert view["schema"] == wb.RESULTS_VIEW
    assert set(view["scenarios"]) == {s["id"] for s in ev.scenarios(CONTRACT)}
    assert view["rules"]["p45-r30-a25"]["measurable"] is False
    with pytest.raises(wb.StudyRefused):
        wb.results_view({**results, "claims": {"evidence_class": "CLIENT"}})
