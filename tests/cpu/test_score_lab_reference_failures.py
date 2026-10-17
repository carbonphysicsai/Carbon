"""Synthetic measurement controls only; no real reference or solver inputs."""

from __future__ import annotations

import copy
import json

import pytest

from scripts.dev.score_lab import campaign_reference as reference
from scripts.dev.score_lab.core import SCHEMA, LabRefused, analyze
from scripts.dev.score_lab.legacy_cli import main


def _spec(**updates):
    return {
        "schema": reference.SCHEMA,
        "label": "ASSUMPTION: synthetic fixture only",
        "fraction": 0.05,
        "seed": 42,
        "policy": "EXCLUDE_COMMON",
    } | updates


def _panel():
    question = {"actions": {"a": {"objective": 1.0, "status": "FEASIBLE"}}}
    value = {f"V-{i:02d}": copy.deepcopy(question) for i in range(20)}
    return {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "score_questions": {"S-0": question},
        "value_questions": value,
        "exact_oracle_losses": {q: 0.0 for q in value},
        "members": [
            {
                "id": name,
                "recipe": name,
                "kind": kind,
                "score_predictions": {"S-0": {"a": {"objective": 1.0 + loss}}},
                "score_row": {"E": loss},
                "value_losses": {q: loss for q in value},
            }
            for name, kind, loss in (
                ("good", "MODEL", 0.1),
                ("bad", "MODEL", 0.2),
                ("control", "PROBE", 0.3),
            )
        ],
    }


def _score(predictions, references, metadata):
    assert set(predictions) == set(references) == {"S-0"}
    assert set(metadata) == {"score_row"}
    return {"score": 1 / (1 + metadata["score_row"]["E"]), "admissible": True}


@pytest.mark.parametrize("policy", sorted(reference.POLICIES))
def test_zero_outages_reproduce_existing_analysis_exactly(policy):
    panel = _panel()
    before = copy.deepcopy(panel)
    expected = analyze(panel, _score, bootstrap=10)
    actual = reference.evaluate(
        panel, _score, _spec(fraction=0, policy=policy), bootstrap=10
    )
    receipt = actual.pop("value_reference_measurement")
    assert actual == expected
    assert panel == before
    assert receipt["injected_unresolved"] == 0
    assert receipt["scored_value_questions"] == 20


def test_outages_are_shared_deterministic_and_independent_of_model_losses():
    panel = _panel()
    before = copy.deepcopy(panel)
    masked, receipt = reference.prepare(panel, _spec())
    assert panel == before
    failed = {
        q for q, loss in masked["members"][0]["value_losses"].items() if loss is None
    }
    assert len(failed) == 1
    assert receipt["injected_unresolved"] == 1
    assert receipt["realized_injected_fraction"] == 0.05
    for member, original in zip(masked["members"], panel["members"], strict=True):
        assert {
            q for q, loss in member["value_losses"].items() if loss is None
        } == failed
        assert member["score_predictions"] == original["score_predictions"]
        assert member["score_row"] == original["score_row"]
    assert masked["score_questions"] == panel["score_questions"]
    assert masked["value_questions"] == panel["value_questions"]
    assert all(masked["exact_oracle_losses"][q] is None for q in failed)
    panel["members"].reverse()
    for member in panel["members"]:
        member["value_losses"] = {q: 999.0 for q in panel["value_questions"]}
        member["score_predictions"]["S-0"]["a"]["objective"] = 999.0
        member["score_row"]["E"] = 999.0
    changed, changed_receipt = reference.prepare(panel, _spec())
    assert {
        q for q, loss in changed["members"][0]["value_losses"].items() if loss is None
    } == failed
    assert (
        changed_receipt["common_resolved_mask_sha256"]
        == receipt["common_resolved_mask_sha256"]
    )


def test_require_complete_invokes_no_scorer_and_has_no_candidate_failure():
    def forbidden(*args):
        pytest.fail("incomplete reference measurement invoked the scorer")

    result = reference.evaluate(_panel(), forbidden, _spec(policy="REQUIRE_COMPLETE"))
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["reason"] == "value_reference_incomplete"
    assert "admissibility_failures" not in result
    assert "tau" not in result and "top1_regret" not in result
    receipt = result["value_reference_measurement"]
    assert receipt["common_resolved_available"] == 19
    assert receipt["scored_value_questions"] == 0


def test_exclusion_calls_real_scorer_but_does_not_expose_value_mask():
    calls = []

    def score(predictions, references, metadata):
        calls.append(set(references))
        return _score(predictions, references, metadata)

    result = reference.evaluate(_panel(), score, _spec(), bootstrap=10)
    assert calls == [{"S-0"}] * 3
    assert result["status"] == "MEASURED_DEVELOPMENT"
    assert result["value_questions"] == 19
    assert result["value_questions_offered"] == 20
    assert result["admissibility_failures"] == 0
    assert result["value_reference_measurement"]["scored_value_questions"] == 19
    assert (
        result["value_reference_measurement"]["estimand"]
        == "conditional_on_common_resolved_value_questions"
    )


def test_different_preexisting_gaps_share_one_mask_including_controls():
    panel = _panel()
    for index, member in enumerate(panel["members"]):
        member["value_losses"][f"V-{index:02d}"] = None
    result = reference.evaluate(panel, _score, _spec(fraction=0), bootstrap=10)
    assert result["value_questions"] == 17
    receipt = result["value_reference_measurement"]
    assert receipt["preexisting_unresolved"] == receipt["common_unresolved"] == 3
    assert receipt["scored_value_questions"] == 17
    expected = analyze(panel, _score, bootstrap=10)
    assert {
        k: v for k, v in result.items() if k != "value_reference_measurement"
    } == expected


def test_reference_exclusion_does_not_erase_measured_candidate_gate_failures():
    def gate_score(predictions, references, metadata):
        result = _score(predictions, references, metadata)
        result["admissible"] = metadata["score_row"]["E"] == 0.1
        return result

    expected = analyze(_panel(), gate_score, bootstrap=10)
    actual = reference.evaluate(_panel(), gate_score, _spec(), bootstrap=10)
    assert actual["admissibility_failures"] == expected["admissibility_failures"] == 2
    assert actual["admissibility"] == expected["admissibility"]
    assert actual["value_reference_measurement"]["scored_value_questions"] == 19


def test_existing_and_injected_outages_do_not_double_count():
    panel = _panel()
    masked, _ = reference.prepare(panel, _spec())
    failed = next(
        q for q, v in masked["members"][0]["value_losses"].items() if v is None
    )
    panel["members"][0]["value_losses"][failed] = None
    _, receipt = reference.prepare(panel, _spec())
    assert receipt["injected_unresolved"] == receipt["preexisting_unresolved"] == 1
    assert receipt["overlap_unresolved"] == receipt["common_unresolved"] == 1
    assert receipt["common_resolved_available"] == 19


@pytest.mark.parametrize("policy", sorted(reference.POLICIES))
def test_empty_common_mask_never_invokes_scorer(policy):
    panel = _panel()
    panel["members"][0]["value_losses"] = {q: None for q in panel["value_questions"]}

    def forbidden(*args):
        pytest.fail("no common reference outcomes but scorer was invoked")

    result = reference.evaluate(panel, forbidden, _spec(policy=policy))
    assert result["reason"] == "no_common_resolved_value_questions"
    assert result["value_reference_measurement"]["scored_value_questions"] == 0


def test_small_fraction_rounding_is_disclosed_not_forced_to_one_outage():
    _, receipt = reference.prepare(_panel(), _spec(fraction=0.01))
    assert receipt["spec"]["fraction"] == 0.01
    assert receipt["injected_unresolved"] == 0
    assert receipt["realized_injected_fraction"] == 0


def test_absent_optional_oracle_remains_best_member_regret_not_zero_imputation():
    panel = _panel()
    panel["exact_oracle_losses"] = None
    result = reference.evaluate(panel, _score, _spec(), bootstrap=10)
    assert result["status"] == "MEASURED_DEVELOPMENT"
    assert result["top1_regret_reference"] == "BEST_MEMBER_IN_POOL"
    assert panel["exact_oracle_losses"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"fraction": -0.01},
        {"fraction": 0.051},
        {"fraction": True},
        {"fraction": float("nan")},
        {"fraction": float("inf")},
        {"seed": True},
        {"seed": -1},
        {"policy": []},
        {"policy": "PENALIZE"},
        {"label": "adopted"},
        {"extra": 1},
        {"schema": "production"},
    ],
)
def test_malformed_or_unregistered_options_refuse(change):
    with pytest.raises(LabRefused, match="value_reference_failure_spec"):
        reference.prepare(_panel(), _spec(**change))


@pytest.mark.parametrize("key", ["fraction", "seed", "policy"])
def test_required_options_have_no_adopted_defaults(key):
    spec = _spec()
    del spec[key]
    with pytest.raises(LabRefused, match="value_reference_failure_spec"):
        reference.prepare(_panel(), spec)


def test_public_panels_refuse_and_nonfinite_loss_is_not_silently_dropped():
    panel = _panel()
    panel["scope"] = "PUBLIC_DEVELOPMENT"
    with pytest.raises(LabRefused, match="requires_synthetic"):
        reference.evaluate(panel, _score, _spec())
    panel["scope"] = "SYNTHETIC_DEVELOPMENT"
    panel["members"][0]["value_losses"]["V-00"] = float("nan")
    with pytest.raises(LabRefused, match="nonfinite_loss"):
        reference.evaluate(panel, _score, _spec())


def test_actual_cli_records_policy_and_public_replay_parser_refuses_option(tmp_path):
    source = tmp_path / "rule.py"
    source.write_text(
        "def score(p, r, m):\n    raise AssertionError('strict policy called scorer')\n",
        encoding="utf-8",
    )
    spec = tmp_path / "failures.json"
    spec.write_text(json.dumps(_spec(policy="REQUIRE_COMPLETE")), encoding="utf-8")
    out = tmp_path / "result.json"
    assert (
        main(
            [
                "synthetic",
                "--quick",
                "--function",
                f"{source}:score",
                "--questions-per-side",
                "20",
                "--value-reference-failures",
                str(spec),
                "--bootstrap",
                "5",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    result = json.loads(out.read_text(encoding="utf-8"))
    assert len(result["rows"]) == 4
    for row in result["rows"]:
        assert row["status"] == "INSUFFICIENT_EVIDENCE"
        assert row["value_reference_measurement"]["injected_unresolved"] == 1
    with pytest.raises(SystemExit) as error:
        main(
            [
                "replay",
                "--cache",
                str(tmp_path / "not-read-public.json"),
                "--function",
                f"{source}:score",
                "--value-reference-failures",
                str(spec),
            ]
        )
    assert error.value.code == 2
