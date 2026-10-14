"""Finite synthetic controls; no model training, solver or protected inputs."""

import copy
import gzip
import json
import statistics
from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_measurement as study
from scripts.dev.score_lab import core
from scripts.dev.score_lab import measurement_run as driver


def panel():
    losses = ((0, 6, 2, 1), (2, 0, 4, 3), (4, 2, 0, 7), (3, 1, 5, 0))
    return {
        "schema": core.SCHEMA,
        "scope": study.SCOPE,
        "score_questions": {"S": {}},
        "value_questions": {f"V{i}": {} for i in range(4)},
        "value_strata": {
            f"V{i}": "extrapolated" if i == 3 else "in_range" for i in range(4)
        },
        "exact_oracle_losses": {f"V{i}": -1.0 for i in range(4)},
        "members": [
            {
                "id": f"m{j}",
                "recipe": f"m{j}",
                "kind": "MODEL",
                "score_predictions": {"S": {"a": j}},
                "score_row": {"E": j},
                "value_losses": {f"V{i}": float(v) for i, v in enumerate(row)},
            }
            for j, row in enumerate(losses)
        ],
    }


def score(predictions, references, metadata):
    assert set(predictions) == set(references) == {"S"}
    assert set(metadata) == {"score_row"}
    return {"score": -metadata["score_row"]["E"], "admissible": True}


def cell(**changes):
    return {**study.cells()[0], "N": 30, "B": 3, "seed": 11, **changes}


def test_prospective_matrix_is_full_and_unique():
    cells = study.cells()
    assert len(cells) == 126 == len({core.canonical_sha(c) for c in cells})
    assert sum(c["study"] == "sample_blocks" for c in cells) == 54
    assert sum(c["study"] == "proposal_outages" for c in cells) == 72


def test_sampling_deterministic_preserves_scores_and_changes_with_seed_dependence():
    p = panel()
    before = copy.deepcopy(p)
    law = study.finite_law(p, "half_extrapolated")
    args = {
        "n": 300,
        "blocks": 10,
        "dependence": "replicated",
        "seed": 11,
        "estimand": "P",
    }
    first, groups = study.sample(p, law, **args)
    assert study.sample(p, law, **args) == (first, groups)
    assert first != study.sample(p, law, **{**args, "seed": 22})[0]
    iid, _ = study.sample(p, law, **{**args, "dependence": "iid"})
    assert any(
        len({iid["value_questions"][q]["source"] for q in group}) > 1
        for group in groups.values()
    )
    assert all(
        len({first["value_questions"][q]["source"] for q in group}) == 1
        for group in groups.values()
    )
    assert p == before
    for view in (first, iid):
        assert view["score_questions"] == p["score_questions"]
        for a, b in zip(view["members"], p["members"]):
            assert a["score_predictions"] == b["score_predictions"]
            assert a["score_row"] == b["score_row"]


def test_ht_correction_exactly_targets_p_not_q_and_w_is_not_a_probability():
    p = panel()
    law = study.finite_law(p, "half_extrapolated")
    law["V3"]["w"] = 2.0
    truth_p = study.population_values(p, law, "P")
    truth_q = study.population_values(p, law, "Q")
    for m in p["members"]:
        # Exact expectation over the finite proposal, not a Monte Carlo assertion.
        ht = sum(
            law[q]["Q"] * law[q]["w"] * law[q]["P"] / law[q]["Q"] * x
            for q, x in m["value_losses"].items()
        )
        assert -ht == pytest.approx(truth_p[m["id"]])
    assert truth_p != truth_q
    assert truth_p["m0"] == -2.5
    assert truth_q["m0"] == pytest.approx(-7 / 3)


def test_repeated_rows_keep_block_information_but_naive_question_only_ci_shrinks():
    p = panel()
    law = study.finite_law(p, "uniform")
    rule = study.frozen_rule(p, score)
    a = study.compare(
        p, law, cell(N=30, dependence="replicated"), {"toy": rule}, bootstrap=100
    )
    b = study.compare(
        p, law, cell(N=3000, dependence="replicated"), {"toy": rule}, bootstrap=100
    )
    ra, rb = (r["rows"]["toy"] for r in (a, b))
    assert ra["block"]["tau_ci95"] == rb["block"]["tau_ci95"]
    assert (
        ra["block"]["tau_undefined_fraction"] == rb["block"]["tau_undefined_fraction"]
    )
    assert ra["block"]["tau"] == rb["block"]["tau"]
    assert ra["block"]["top1_regret"] == pytest.approx(rb["block"]["top1_regret"])
    assert ra["block"]["value_questions"] == rb["block"]["value_questions"] == 3
    # Joint intervals can remain wide because there are only four recipe clusters.
    # The existing question-only sensitivity isolates the false sample-size gain.
    sensitivities = []
    for n in (30, 3000):
        sampled, _ = study.sample(
            p, law, n=n, blocks=3, dependence="replicated", seed=11, estimand="P"
        )
        members = sampled["members"]
        sensitivities.append(
            core.score_proof.bootstrap(
                {m["id"]: -i for i, m in enumerate(members)},
                {},
                {m["id"]: list(m["value_losses"].values()) for m in members},
                {m["id"]: m["recipe"] for m in members},
                [m["id"] for m in members],
                n=100,
                seed=11,
            )["question_only"]
        )
    assert (
        sensitivities[0][1] - sensitivities[0][0]
        > sensitivities[1][1] - sensitivities[1][0]
    )


def test_complete_block_mask_is_identical_for_case_and_block_and_strict_is_unscored():
    p = panel()
    law = study.finite_law(p, "uniform")
    c = cell(N=300, B=30, outage=0.05, policy="EXCLUDE_COMPLETE_BLOCKS")
    r = study.compare(p, law, c, {"toy": score}, bootstrap=12)
    receipt = r["block_mask"]
    assert receipt["unresolved_questions"] == 15
    assert receipt["resolved_questions_in_incomplete_blocks"] > 0
    result = r["rows"]["toy"]
    assert result["case"]["value_questions"] == 10 * result["block"]["value_questions"]
    assert result["case"]["tau"] == result["block"]["tau"]
    assert result["case"]["top1_regret"] == pytest.approx(
        result["block"]["top1_regret"]
    )
    assert result["case"]["covers_population_tau"] is None
    assert r["estimand"].startswith("conditional_retained_draw_")

    def forbidden(*args):
        pytest.fail("strict missing measurement called scorer")

    r = study.compare(
        p, law, {**c, "policy": "REQUIRE_COMPLETE"}, {"toy": forbidden}, bootstrap=12
    )
    assert r["rows"]["toy"]["status"] == "INSUFFICIENT_EVIDENCE"


def test_frozen_score_calls_once_and_refuses_scoring_drift():
    p = panel()
    calls = []

    def observed(*args):
        calls.append(copy.deepcopy(args))
        return score(*args)

    frozen = study.frozen_rule(p, observed)
    assert len(calls) == frozen.scorer_calls == 4
    law = study.finite_law(p, "uniform")
    study.compare(p, law, cell(), {"toy": frozen}, bootstrap=3)
    assert len(calls) == 4
    p["members"][0]["score_predictions"]["S"]["a"] = 123
    with pytest.raises(core.LabRefused, match="score_input_changed"):
        study.compare(p, law, cell(), {"toy": frozen}, bootstrap=3)


@pytest.mark.parametrize(
    "mutation", ["scope", "missing", "oracle", "strata", "nonfinite"]
)
def test_incomplete_or_public_population_refused(mutation):
    p = panel()
    if mutation == "scope":
        p["scope"] = "PUBLIC_DEVELOPMENT"
    elif mutation == "missing":
        p["members"][0]["value_losses"]["V0"] = None
    elif mutation == "nonfinite":
        p["members"][0]["value_losses"]["V0"] = float("inf")
    elif mutation == "oracle":
        p["exact_oracle_losses"].pop("V0")
    else:
        p["value_strata"].pop("V0")
    with pytest.raises(core.LabRefused):
        study.finite_law(p, "uniform")


@pytest.mark.parametrize(
    "mutation", ["zero_q", "negative_p", "nan_w", "unknown", "sum", "support"]
)
def test_invalid_law_refused(mutation):
    p = panel()
    law = study.finite_law(p, "uniform")
    if mutation == "support":
        law.pop("V0")
    else:
        key, value = {
            "zero_q": ("Q", 0),
            "negative_p": ("P", -1),
            "nan_w": ("w", float("nan")),
            "unknown": ("magic", 1),
            "sum": ("P", 0.9),
        }[mutation]
        law["V0"][key] = value
    with pytest.raises(core.LabRefused):
        study.sample(p, law, n=30, blocks=3, dependence="iid", seed=11, estimand="P")


def test_draw_values_preserve_recorded_ht_correction():
    p = panel()
    law = study.finite_law(p, "half_extrapolated")
    view, _ = study.sample(
        p, law, n=300, blocks=10, dependence="iid", seed=11, estimand="P"
    )
    member = view["members"][0]
    expected = [
        p["members"][0]["value_losses"][r["source"]] * r["P"] / r["Q"] * r["w"]
        for r in view["value_questions"].values()
    ]
    assert statistics.fmean(member["value_losses"].values()) == pytest.approx(
        statistics.fmean(expected)
    )


def test_registration_does_not_import_candidate_and_refuses_changed_inputs(tmp_path):
    root = Path(__file__).resolve().parents[2]
    candidate = tmp_path / "candidate.py"
    candidate.write_text(
        "raise RuntimeError('must not import during registration')\n", encoding="utf-8"
    )
    plan = driver.register(root, candidate)
    driver.verify(root, plan, candidate)
    changed = copy.deepcopy(plan)
    changed["cells"] = changed["cells"][:-1]
    with pytest.raises(core.LabRefused, match="registration_or_source_changed"):
        driver.verify(root, changed, candidate)
    candidate.write_text("changed\n", encoding="utf-8")
    with pytest.raises(core.LabRefused, match="registration_or_source_changed"):
        driver.verify(root, plan, candidate)


def _readout_fixture(tmp_path):
    """Receipt transport fixture only: all candidate outcomes explicitly unscored."""
    root = Path(__file__).resolve().parents[2]
    candidate = tmp_path / "candidate.py"
    candidate.write_text("# fixture, never imported\n", encoding="utf-8")
    plan = driver.register(root, candidate)
    planpath = tmp_path / "plan.json"
    study.write(planpath, plan)
    out = tmp_path / "out"
    out.mkdir()
    start = {
        "schema": study.SCHEMA,
        "scope": study.SCOPE,
        "source_commit": "fixture-not-a-run",
        "plan_sha256": core.canonical_sha(plan),
        "candidate_sha256": plan["candidate_sha256"],
        "sources": plan["sources"],
        "execution": "fixture receipt transport; no evaluator execution",
    }
    study.write(out / "START.json", start)
    study.write(out / "REGISTERED_PLAN.json", plan)
    study.write(out / "CONTROLS.json", {"status": "CONTROL_PASS", "fixture": True})
    study.write(out / "RUN.json", {"status": "COMPLETED", "complete_cells": 126})
    for index, c in enumerate(plan["cells"]):
        result = {
            "cell": c,
            "block_mask": {
                "complete_blocks_available": 0,
                "unresolved_questions": c["N"],
                "resolved_questions_in_incomplete_blocks": 0,
            },
            "estimand": "fixture_unscored",
            "rows": {
                n: {"status": "INSUFFICIENT_EVIDENCE"} for n in driver.CANDIDATE_IDS
            },
        }
        (out / f"CELL_{index:03d}.json.gz").write_bytes(
            gzip.compress(json.dumps(result).encode(), mtime=0)
        )
    _seal_fixture(out, start)
    return planpath, out, start


def _seal_fixture(out, start):
    study.write(
        out / "IDENTITY.json",
        {
            **start,
            "artifacts_sha256": {
                p.name: study.file_sha(p)
                for p in sorted(out.iterdir())
                if p.name != "IDENTITY.json"
            },
        },
    )


def test_readout_requires_identity_inventory_and_complete_outcomes(tmp_path):
    planpath, out, start = _readout_fixture(tmp_path)
    report = driver.readout(planpath, out)
    assert len(report["rows"]) == 1260
    assert all(r["status"] == "INSUFFICIENT_EVIDENCE" for r in report["rows"])
    assert all(
        r["measured_sampling_seeds"] == 0 for r in report["descriptive_seed_summary"]
    )
    cellpath = out / "CELL_000.json.gz"
    result = json.loads(gzip.decompress(cellpath.read_bytes()))
    result["rows"].pop(driver.CANDIDATE_IDS[0])
    cellpath.write_bytes(gzip.compress(json.dumps(result).encode(), mtime=0))
    with pytest.raises(core.LabRefused, match="artifact_binding"):
        driver.readout(planpath, out)
    _seal_fixture(out, start)
    with pytest.raises(core.LabRefused, match="candidate_inventory"):
        driver.readout(planpath, out)


def test_readout_rejects_stopped_run_and_rebound_start(tmp_path):
    planpath, out, start = _readout_fixture(tmp_path)
    study.write(out / "RUN.json", {"status": "STOPPED", "complete_cells": 125})
    _seal_fixture(out, start)
    with pytest.raises(core.LabRefused, match="incomplete_run"):
        driver.readout(planpath, out)
    study.write(out / "START.json", {**start, "source_commit": "changed"})
    _seal_fixture(out, start)
    with pytest.raises(core.LabRefused, match="identity_binding"):
        driver.readout(planpath, out)
