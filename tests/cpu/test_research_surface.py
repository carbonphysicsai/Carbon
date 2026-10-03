"""The miner's research surface (OWNER-MINER-RESEARCH-SURFACE-01).

What these hold, without a browser:
- the campaign view is an allow-list: nothing private, no seed, no per-case
  evaluation detail, and the frozen feedback mode applies (RSURF-D1, D4);
- per-case curves are public practice only, from verified predictions, and
  fail closed to aggregates otherwise (RSURF-D2);
- every output kind is drawn, for battery and for a synthetic second
  Challenge, through the same code (RSURF-D8);
- `carbon_note` is bounded and its text is shown as text (RSURF-D5).

The page itself is held in test_research_surface_page.py, and the demo
fixture and the two doors' parity in test_research_surface_fixture.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_registry.research_view import (
    OUTPUT_KINDS,
    Axis,
    OutputSpec,
    PerCasePolicy,
    ResearchView,
    per_case_policy,
    validate_chart,
)
from scripts.dev.miner_launchpad import campaign_view as cv
from scripts.dev.miner_launchpad.controller import Rejected

ROOT = Path(__file__).resolve().parents[2]
LAUNCHPAD = ROOT / "scripts/dev/miner_launchpad"
BATTERY = {"id": "battery-fastcharge-ageing-development-v1", "version": "1.0"}
SENTINEL = "PRIVATE-SENTINEL"


def synthetic_view(*, allowed=True, modes=None):
    """A second Challenge that exists only here: one output of every kind."""
    time_axis = Axis("time", "s", tuple(range(11)))
    outputs = (
        OutputSpec("plate_t", "time_series", "degC", "Plate temperature", (time_axis,)),
        OutputSpec("peak_flux", "scalar", "W/m2", "Peak flux"),
        OutputSpec(
            "efficiency",
            "checkpoint_vector",
            None,
            "Efficiency at load",
            (Axis("load", "%", (25, 50, 100)),),
        ),
        OutputSpec(
            "field",
            "field_2d",
            "degC",
            "Temperature field",
            (Axis("y", "mm", tuple(range(6))), Axis("x", "mm", tuple(range(8)))),
        ),
    )
    cases = {
        f"synthetic-{i:03d}": {
            "inputs": {"load": 0.5 + i / 10},
            "outputs": {
                "plate_t": [20 + i + t for t in range(11)],
                "peak_flux": 1000.0 + i,
                "efficiency": [0.9, 0.85 - i / 100, 0.8],
                "field": [[float(r * c + i) for c in range(8)] for r in range(6)],
            },
        }
        for i in range(3)
    }
    fields = modes or {
        "FULL": (("state", "screening", "nominated"), ("eligible", "score"))
    }
    return (
        ResearchView(
            challenge_id="synthetic-heat-plate-v1",
            outputs=outputs,
            components=(("thermal", "Thermal"), ("flux", "Flux")),
            direction="lower_is_better",
            per_case=PerCasePolicy(allowed, "synthetic disclosure"),
            learning_curve={"recorded": False, "basis": "synthetic"},
            case_ids=lambda: list(cases),
            reference=lambda case: cases.get(case),
            feedback_fields=lambda mode: fields.get(mode),
            inputs=("load",),
        ),
        cases,
    )


def own_projection(n=2, **extra):
    experiments = [
        {
            "id": f"run-{i}",
            "recipe": {"backbone": "mlp", "parameters": {"width": 32 * i}},
            "summary": {
                "score": 0.5 / i,
                "eligible": True,
                "components": {"thermal": 0.4 / i, "flux": 0.6 / i},
                "n_cases": 3,
                "n_scored": 3,
                "gate_failures": {},
            },
            "fit": {"final_loss": 0.01 / i, "n_params": 100, "train_s": 1.0},
            "backend": {"kind": "ISOLATED_CARRIER"},
        }
        for i in range(1, n + 1)
    ]
    value = {
        "id": "c0ffee",
        "state": "READY",
        "selects": "miner",
        "challenge": {"id": "synthetic-heat-plate-v1", "version": "1.0"},
        "started_unix": 1000.0,
        "experiments": experiments,
        "hypotheses": [],
        "decisions": [],
        "candidate_freezes": [],
        "final_results": [],
        "journey": {
            "submitted_epochs": [],
            "final_exams_remaining": 2,
            "frozen_awaiting_submission": False,
        },
    }
    value.update(extra)
    return value


def predicted(cases, scale):
    return {
        case: {
            "plate_t": [v * scale for v in ref["outputs"]["plate_t"]],
            "peak_flux": ref["outputs"]["peak_flux"] * scale,
            "efficiency": [v * scale for v in ref["outputs"]["efficiency"]],
            "field": [[v * scale for v in row] for row in ref["outputs"]["field"]],
        }
        for case, ref in cases.items()
    }


def view_of(own, view, predictions, **kwargs):
    return cv.build(
        own,
        view=view,
        contract=None,
        notes=kwargs.pop("notes", []),
        feedback_mode=kwargs.pop("feedback_mode", "FULL"),
        predictions=predictions,
        now=2000.0,
        **kwargs,
    )


# ---- Every output kind, for battery and for a synthetic second Challenge.


def test_battery_declares_its_outputs_from_its_io_description():
    from carbon.challenge_registry.campaigns import campaign_for

    view = campaign_for(BATTERY).research_view()
    kinds = {o.name: (o.kind, o.unit, o.shape) for o in view.outputs}
    assert kinds == {
        "voltage_v": ("time_series", "V", (121,)),
        "temperature_c": ("time_series", "degC", (121,)),
        "plating_margin_v": ("scalar", "V", ()),
        "capacity_ah": ("checkpoint_vector", "Ah", (4,)),
    }
    time_axis = view.outputs[0].axes[0]
    assert (time_axis.name, time_axis.values[0], time_axis.values[-1]) == (
        "time",
        0,
        3600,
    )
    assert view.outputs[3].axes[0].values == (1, 10, 20, 30)
    assert [k for k, _ in view.components] == [
        "voltage",
        "temperature",
        "plating",
        "capacity",
    ]
    # Battery's own disclosure contract allows its public practice detail.
    assert view.per_case.allowed
    assert len(view.case_ids()) == 200
    # Trainer v2 records a TRAIN-loss history in practice (RSURF-D3).
    assert view.learning_curve["recorded"] is True


def test_a_synthetic_second_challenge_draws_every_kind_through_the_same_code():
    view, cases = synthetic_view()
    doc = view_of(
        own_projection(),
        view,
        lambda task: (predicted(cases, 1.1 if task == "run-2" else 1.3), None),
    )
    case_charts = doc["per_case"]["selected"]["charts"]
    assert doc["per_case"]["status"] == "AVAILABLE"
    assert {c["kind"] for c in case_charts} == set(OUTPUT_KINDS)
    for chart in case_charts + doc["charts"]:
        validate_chart(chart)
    # Reference, this run and the run before it, each in the output's shape.
    field = next(c for c in case_charts if c["kind"] == "field_2d")
    assert [s["role"] for s in field["series"]] == ["reference", "current", "previous"]
    assert len(field["series"][1]["values"]) == 6
    assert len(field["series"][1]["values"][0]) == 8
    assert {c["id"] for c in doc["charts"]} == {
        "components",
        "trend_score",
        "trend_components",
    }


@pytest.mark.parametrize(
    "chart",
    [
        {"kind": "pie", "id": "x", "title": "x", "axes": [], "series": []},
        {
            "kind": "time_series",
            "id": "x",
            "title": "x",
            "axes": [{"name": "t", "values": [0, 1]}],
            "series": [{"label": "a", "role": "current", "values": [1.0]}],
        },
        {
            "kind": "scalar",
            "id": "x",
            "title": "x",
            "axes": [],
            "series": [{"label": "a", "role": "current", "values": float("nan")}],
        },
        {
            "kind": "time_series",
            "id": "x",
            "title": "x",
            "axes": [{"name": "t", "values": [0]}],
            "series": [{"label": "a", "role": "rank-1", "values": [1.0]}],
        },
    ],
)
def test_a_malformed_chart_is_refused(chart):
    with pytest.raises(ValueError):
        validate_chart(chart)


def test_non_finite_predictions_are_drawn_as_missing_not_invented():
    view, cases = synthetic_view()
    bad = predicted(cases, 1.0)
    first = next(iter(bad))
    bad[first]["peak_flux"] = float("inf")
    bad[first]["plate_t"][3] = float("nan")
    bad[first]["efficiency"] = [1.0]  # the wrong shape
    doc = view_of(own_projection(1), view, lambda task: (bad, None))
    charts = {c["id"]: c for c in doc["per_case"]["selected"]["charts"]}
    current = lambda name: charts["case_" + name]["series"][1]["values"]
    assert current("peak_flux") is None
    assert current("plate_t")[3] is None
    assert current("efficiency") is None
    json.dumps(doc, allow_nan=False)


# ---- Per-case detail: public practice only, and fail closed.


def test_the_per_case_rule_reads_the_disclosure_contract():
    from carbon.battery.research import population_and_sampling

    population, _ = population_and_sampling()
    assert per_case_policy(population.disclosure_contract).allowed
    aggregate = SimpleNamespace(object_id="detailed_own_public_practice")
    for contract in (
        SimpleNamespace(public_field_ids=("laws",), aggregation_policy_ref=aggregate),
        SimpleNamespace(
            public_field_ids=("public_practice_labels",),
            aggregation_policy_ref=SimpleNamespace(object_id="aggregate_only"),
        ),
        SimpleNamespace(),
    ):
        assert not per_case_policy(contract).allowed


def test_per_case_detail_fails_closed_when_not_disclosed():
    view, cases = synthetic_view(allowed=False)
    calls = []

    def predictions(task):
        calls.append(task)
        return predicted(cases, 1.0), None

    doc = view_of(own_projection(), view, predictions)
    assert doc["per_case"] == {
        "status": "WITHHELD",
        "reason": "not_disclosed",
        "basis": "synthetic disclosure",
    }
    assert calls == [], "predictions are not even read when withheld"
    assert "synthetic-000" not in json.dumps(doc)


def test_per_case_detail_fails_closed_without_verified_predictions():
    view, _ = synthetic_view()
    doc = view_of(
        own_projection(), view, lambda task: (None, "predictions_digest_differs")
    )
    assert doc["per_case"]["status"] == "UNAVAILABLE"
    assert doc["per_case"]["reason"] == "predictions_digest_differs"
    assert "selected" not in doc["per_case"]
    doc = view_of(own_projection(), None, lambda task: (None, None))
    assert doc["per_case"] == {
        "status": "UNAVAILABLE",
        "reason": "no_research_view_for_this_challenge",
    }


def test_only_a_public_practice_case_or_a_known_run_can_be_asked_for():
    view, cases = synthetic_view()
    with pytest.raises(Rejected) as refused:
        view_of(
            own_projection(),
            view,
            lambda task: (predicted(cases, 1.0), None),
            practice_case="private-eval-007",
        )
    assert refused.value.code == "unknown_practice_case"
    with pytest.raises(Rejected) as refused:
        view_of(
            own_projection(),
            view,
            lambda task: (predicted(cases, 1.0), None),
            experiment="someone-elses-run",
        )
    assert refused.value.code == "unknown_experiment"


def test_predictions_are_read_only_when_their_digest_matches_the_ledger(tmp_path):
    from carbon.development_session.profile import digest

    view, cases = synthetic_view()
    snapshot = tmp_path / "op-1" / "snapshot"
    snapshot.mkdir(parents=True)
    body = json.dumps(predicted(cases, 1.0)).encode()
    (snapshot / "predictions.json").write_bytes(body)
    facts = {
        "practice": {"run-1": "op-1", "run-2": "../op-1", "run-3": "op-3"},
        "workers": {
            "op-1": {"predictions.json": digest(body)},
            "../op-1": {"predictions.json": digest(body)},
            "op-3": {"predictions.json": digest(body)},
        },
    }
    value, reason = cv.verified_predictions(tmp_path, view, facts, "run-1")
    assert reason is None and set(value) == set(cases)
    # A path outside the campaign, a missing file and an unknown run.
    assert cv.verified_predictions(tmp_path, view, facts, "run-2") == (
        None,
        "no_worker_record",
    )
    assert cv.verified_predictions(tmp_path, view, facts, "run-3") == (
        None,
        "predictions_missing",
    )
    assert cv.verified_predictions(tmp_path, view, facts, "run-9") == (
        None,
        "no_worker_record",
    )
    # Changed bytes are not read, even when the size is the same.
    (snapshot / "predictions.json").write_bytes(body.replace(b"1", b"2", 1))
    os.utime(snapshot / "predictions.json", ns=(1, 1))
    assert cv.verified_predictions(tmp_path, view, facts, "run-1") == (
        None,
        "predictions_digest_differs",
    )
    # A symlinked file is never followed.
    (snapshot / "predictions.json").unlink()
    (snapshot / "predictions.json").symlink_to(tmp_path / "elsewhere.json")
    assert cv.verified_predictions(tmp_path, view, facts, "run-1") == (
        None,
        "predictions_missing",
    )


# ---- The view is an allow-list.


def test_nothing_outside_the_allow_list_reaches_the_view():
    view, cases = synthetic_view()
    own = own_projection(
        seed=SENTINEL,
        research_guidance={"text": SENTINEL},
        effective_research_inputs=SENTINEL,
        images=SENTINEL,
        agent_policy={"prompt_digest": SENTINEL},
        operations=[
            {"id": "op-1", "phase": "trial", "state": "SUCCEEDED", "result": SENTINEL}
        ],
        usage={
            "budget": {},
            "reported": {"provider_nanodollars": 5},
            "reserved": {},
            "uncertain": {},
            "carbon_service_limits": SENTINEL,
            "cost_basis": "basis",
        },
        final_results=[
            {
                "epoch": 1,
                "status": "VALIDATOR_OUTCOME",
                "result": {
                    "state": "SCORED",
                    "submission_id": "s-1",
                    "nominated": False,
                    "screening": {
                        "eligible": True,
                        "score": 0.2,
                        "per_case_errors": SENTINEL,
                        "seed": SENTINEL,
                    },
                    "seed": SENTINEL,
                    "private_pool": SENTINEL,
                },
            }
        ],
    )
    own["experiments"][0]["worker"] = {"operation": SENTINEL}
    own["experiments"][0]["summary"]["rows"] = [{"case": SENTINEL}]
    own["experiments"][0]["backend"]["device"] = SENTINEL
    doc = view_of(own, view, lambda task: (predicted(cases, 1.0), None))
    text = json.dumps(doc)
    assert SENTINEL not in text
    assert doc["outcomes"][0]["result"]["screening"] == {"eligible": True, "score": 0.2}
    assert doc["official_eligible"] is False and doc["qualification"] is False
    assert doc["labels"]["statement"] == "Practice evidence ≠ qualification"
    assert (doc["labels"]["mode"], doc["labels"]["netuid"]) == ("DEVELOPMENT", 567)


def test_the_frozen_feedback_mode_applies_to_the_outcome_shown():
    modes = {
        "FULL": (
            ("state", "submission_id", "nominated", "finals"),
            ("eligible", "gates_failed", "score", "pool_version"),
        ),
        "SCORE_WITHHELD": (("state", "submission_id"), ("eligible", "gates_failed")),
    }
    view, _ = synthetic_view(modes=modes)
    result = {
        "state": "SCORED",
        "submission_id": "s-1",
        "nominated": True,
        "finals": [{"state": "DONE", "promoted": False}],
        "screening": {
            "eligible": True,
            "gates_failed": [],
            "score": 0.2,
            "pool_version": 3,
        },
    }
    own = own_projection(
        final_results=[{"epoch": 1, "status": "VALIDATOR_OUTCOME", "result": result}]
    )
    shown = lambda mode: view_of(
        own, view, lambda task: (None, "none"), feedback_mode=mode
    )["outcomes"][0]["result"]
    full = shown("FULL")
    assert full["screening"]["score"] == 0.2 and full["nominated"] is True
    withheld = shown("SCORE_WITHHELD")
    assert withheld["screening"] == {"eligible": True, "gates_failed": []}
    assert "nominated" not in withheld and "finals" not in withheld
    unknown = shown("SOME_NEW_MODE")
    assert set(unknown) == {
        "state",
        "feedback_mode",
        "withheld",
        "qualification",
        "reward",
    }


def test_battery_feedback_modes_come_from_its_own_ladder():
    from carbon.battery import campaign
    from carbon.challenge_registry.campaigns import campaign_for

    view = campaign_for(BATTERY).research_view()
    for mode in campaign.FEEDBACK_MODES:
        outcome, screening = view.feedback_fields(mode)
        if mode != "FULL":
            assert screening == campaign._SCREENING_FIELDS[mode]
            assert "nominated" not in outcome
    assert view.feedback_fields("NOT_A_MODE") is None


# ---- The lifecycle and the journal.


@pytest.mark.parametrize(
    "extra, expected",
    [
        (
            {"experiments": [], "started_unix": None},
            ["current", "waiting", "waiting", "waiting"],
        ),
        ({}, ["done", "current", "waiting", "waiting"]),
        (
            {
                "candidate_freezes": [{"epoch": 1}],
                "journey": {
                    "frozen_awaiting_submission": True,
                    "final_exams_remaining": 2,
                },
            },
            ["done", "done", "done", "current"],
        ),
        ({"state": "PAUSED"}, ["done", "halted", "waiting", "waiting"]),
        ({"state": "STOPPED"}, ["done", "done", "not_reached", "not_reached"]),
    ],
)
def test_the_stage_tracker_reads_the_real_lifecycle(extra, expected):
    assert [s["state"] for s in cv.stages(own_projection(**extra))] == expected


def test_controls_are_the_real_halt_and_resume_operations():
    own = own_projection(state="PAUSED")
    by = {c["action"]: c for c in cv.controls(own, fixture=False)}
    assert by["resume"]["available"] and by["resume"]["operation"] == "resume"
    assert by["stop"]["operation"] == "halt" and not by["pause"]["available"]
    stopped = cv.controls(own_projection(state="STOPPED"), fixture=False)
    assert not any(c["available"] for c in stopped)
    assert not any(c["available"] for c in cv.controls(own, fixture=True))


def test_journal_text_is_bounded_plain_text():
    notes = [
        {
            "sequence": 5,
            "body": {
                "schema": cv.NOTE_SCHEMA,
                "note_kind": "plan",
                "text": "<script>x</script>\u202e",
            },
        },
        {"sequence": 6, "body": {"anything": ["structured"]}},
        {"sequence": 7, "body": "x" * 5000},
    ]
    doc = view_of(own_projection(), None, lambda task: (None, None), notes=notes)
    entries = {e["sequence"]: e for e in doc["journal"]["entries"]}
    # Kept as the characters typed (the page sets it as text), minus the
    # bidirectional override, which could disguise what is shown.
    assert entries[5]["text"] == "<script>x</script>"
    assert entries[5]["kind"] == "plan" and entries[5]["via"] == "carbon_note"
    assert entries[6]["text"].startswith("A structured notebook entry")
    assert len(entries[7]["text"]) == cv.NOTE_MAX
    assert all(e["untrusted"] for e in doc["journal"]["entries"])


def _ledger(root):
    from carbon.development_session.research_ledger import CampaignLedger

    ledger = CampaignLedger(root)
    with ledger.db() as db:
        db.execute(
            "INSERT INTO campaign(id,manifest,digest,started) VALUES(1,?,?,NULL)",
            (json.dumps({"owner": "owner-1"}).encode(), "sha256:" + "0" * 64),
        )
    return ledger


def _admitted(root, kind="product"):
    return SimpleNamespace(campaign={"id": "c", "root": str(root), "kind": kind})


def test_a_note_goes_through_the_existing_journal_path(tmp_path):
    ledger = _ledger(tmp_path)
    answer = cv.post_note(
        None, _admitted(tmp_path), {"note_kind": "observation", "note": "x" * 2000}
    )
    assert answer == {
        "posted": True,
        "note_kind": "observation",
        "characters": 2000,
        "shown_as": "untrusted text",
    }
    (note,) = ledger.status(owner="owner-1")["notes"]
    assert note["kind"] == "notebook"
    assert note["body"] == {
        "schema": cv.NOTE_SCHEMA,
        "note_kind": "observation",
        "text": "x" * 2000,
    }


@pytest.mark.parametrize(
    "request_, code",
    [
        ({"note_kind": "plan", "note": "x" * 2001}, "bounded_note_required"),
        ({"note_kind": "plan", "note": "   "}, "bounded_note_required"),
        ({"note_kind": "plan", "note": "a\x00b"}, "bounded_note_required"),
        ({"note_kind": "plan", "note": "a\x1b[31mb"}, "bounded_note_required"),
        ({"note_kind": "plan", "note": "safe\u202etxt.exe"}, "bounded_note_required"),
        ({"note_kind": "plan", "note": 7}, "bounded_note_required"),
        ({"note_kind": "command", "note": "run this"}, "note_kind_unknown"),
    ],
)
def test_a_note_outside_its_bounds_is_refused(tmp_path, request_, code):
    ledger = _ledger(tmp_path)
    with pytest.raises(Rejected) as refused:
        cv.post_note(None, _admitted(tmp_path), request_)
    assert refused.value.code == code
    assert ledger.status(owner="owner-1")["notes"] == []


def test_a_note_needs_a_product_campaign_with_a_journal(tmp_path):
    with pytest.raises(Rejected) as refused:
        cv.post_note(None, _admitted(tmp_path), {"note_kind": "plan", "note": "x"})
    assert refused.value.code == "campaign_journal_not_ready"
    _ledger(tmp_path)
    with pytest.raises(Rejected) as refused:
        cv.post_note(
            None,
            _admitted(tmp_path, "retired_grant"),
            {"note_kind": "plan", "note": "x"},
        )
    assert refused.value.code == "retired_grant_campaign"
