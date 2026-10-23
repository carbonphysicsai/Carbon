"""What each run took and what the model calls that chose it cost (M1 E2E U45).

The agent view's runs table and per-run detail show, for every run, its wall
and worker seconds and the model cost behind it, from the campaign's ledger
alone - the same record for Graphite, a manual campaign and an external MCP
agent. These tests hold:
- the ledger records when each operation settled, beside it, without
  changing the operations table's columns;
- a run's wall seconds run from its reservation to its settlement, and its
  worker seconds are the worker's own settled time;
- a run's model cost is the settled charge of the model calls reserved after
  the previous run started, up to its own start; a call still reserved is
  counted apart, never at a figure;
- a campaign whose agent calls no model through Carbon has no model cost,
  with why; a run settled before settlement times were recorded has no wall
  time, with why;
- the campaign view carries each figure allow-listed.
"""

from __future__ import annotations

import json
import sqlite3

from test_battery_observation import _battery_campaign
from test_cw1_research_ledger import ledger, reserve

from carbon.development_session.profile import canonical, digest
from scripts.dev.miner_launchpad import campaign_view, projection

CALL = {"provider_attempts": 1, "provider_nanodollars": 5000}


def finish(value, identity, actual):
    value.finish(
        identity, owner="alice", state="SUCCEEDED", actual=actual, result={"ok": 1}
    )


def test_each_run_has_its_duration_and_the_cost_of_the_calls_that_chose_it(
    tmp_path,
):
    now = {"t": 1000.0}
    value = ledger(tmp_path, clock=lambda: now["t"], ceilings=None)
    # A model call, settled below its reservation, then the run it chose.
    reserve(value, "call-1", resources=CALL)
    now["t"] = 1004.0
    finish(value, "call-1", {"provider_attempts": 1, "provider_nanodollars": 3000})
    now["t"] = 1010.0
    reserve(value, "trial-1")
    now["t"] = 1100.5
    finish(value, "trial-1", {"research_trials": 1, "numerical_milliseconds": 80000})
    # A call whose outcome is still open, then a second run.
    now["t"] = 1110.0
    reserve(value, "call-2", resources=CALL)
    now["t"] = 1120.0
    reserve(value, "trial-2")
    now["t"] = 1130.0
    finish(value, "trial-2", {"research_trials": 1, "numerical_milliseconds": 9000})
    # A call after the last run chose nothing yet: no run carries it.
    now["t"] = 1140.0
    reserve(value, "call-3", resources=CALL)
    # A run still reserved has no settlement yet.
    reserve(value, "trial-3")

    times = value.operation_times(owner="alice")
    assert times["trial-1"] == (1010.0, 1100.5)
    assert times["trial-3"] == (1140.0, None)
    operations = value.status(owner="alice")["operations"]
    costs = projection.run_costs(operations, times, calls_models=True)
    assert set(costs) == {"trial-1", "trial-2", "trial-3"}
    assert costs["trial-1"] == {
        "duration": {"wall_seconds": 90.5, "worker_seconds": 80.0, "wall_reason": None},
        "model_cost": {
            "nanodollars": 3000,
            "calls": 1,
            "unsettled_calls": 0,
            "basis": projection.MODEL_COST_BASIS,
        },
        "model_cost_reason": None,
    }
    assert costs["trial-2"]["duration"]["wall_seconds"] == 10.0
    assert costs["trial-2"]["model_cost"] == {
        "nanodollars": 0,
        "calls": 0,
        "unsettled_calls": 1,
        "basis": projection.MODEL_COST_BASIS,
    }
    assert costs["trial-3"]["duration"] == {
        "wall_seconds": None,
        "worker_seconds": None,
        "wall_reason": "not_settled",
    }
    # The miner's own agent, or none, calls no model through Carbon.
    manual = projection.run_costs(operations, times, calls_models=False)
    assert manual["trial-1"]["model_cost"] is None
    assert manual["trial-1"]["model_cost_reason"] == "no_model_calls_through_carbon"
    # A run settled before settlement times were recorded keeps its worker
    # time and says why it has no wall time.
    with value.db() as db:
        db.execute("DELETE FROM operation_finished WHERE id='trial-1'")
    older = projection.run_costs(
        operations, value.operation_times(owner="alice"), calls_models=True
    )
    assert older["trial-1"]["duration"] == {
        "wall_seconds": None,
        "worker_seconds": 80.0,
        "wall_reason": "settled_before_times_were_recorded",
    }


def test_a_replayed_settlement_keeps_its_first_time(tmp_path):
    now = {"t": 1000.0}
    value = ledger(tmp_path, clock=lambda: now["t"], ceilings=None)
    reserve(value, "trial-1")
    now["t"] = 1050.0
    actual = {"research_trials": 1, "numerical_milliseconds": 2000}
    finish(value, "trial-1", actual)
    now["t"] = 2000.0
    finish(value, "trial-1", actual)  # the same terminal outcome, replayed
    assert value.operation_times(owner="alice")["trial-1"] == (1000.0, 1050.0)


def test_the_projection_and_campaign_view_carry_each_run_figure(tmp_path):
    row = _battery_campaign(tmp_path)
    # Its practice ran as ledger operation task-1, as every practice does.
    with sqlite3.connect(tmp_path / "campaign.sqlite3") as db:
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "task-1",
                "miner-requester",
                "research",
                digest(b"request"),
                "SUCCEEDED",
                canonical({"research_trials": 1, "numerical_milliseconds": 600000}),
                canonical({"research_trials": 1, "numerical_milliseconds": 41250}),
                canonical({"ok": 1}),
                5000.0,
            ),
        )
        db.execute("INSERT INTO operation_finished VALUES('task-1', 5062.5)")
    value = projection.project(row, tmp_path)
    (experiment,) = value["experiments"]
    assert experiment["duration"] == {
        "wall_seconds": 62.5,
        "worker_seconds": 41.25,
        "wall_reason": None,
    }
    # A campaign with no agent: no model cost, with why.
    assert experiment["model_cost"] is None
    assert experiment["model_cost_reason"] == "no_model_calls_through_carbon"
    json.dumps(value, allow_nan=False)
    (shown,) = campaign_view.experiment_rows(value, None)
    assert shown["duration"] == experiment["duration"]
    assert shown["model_cost"] is None
    assert shown["model_cost_reason"] == "no_model_calls_through_carbon"


def test_the_campaign_view_allow_lists_run_figures():
    cost = {
        "nanodollars": 3000,
        "calls": 1,
        "unsettled_calls": 0,
        "basis": projection.MODEL_COST_BASIS,
    }
    shown = campaign_view.run_cost(
        {
            "duration": {"wall_seconds": 9.5, "worker_seconds": 8.0, "extra": "x"},
            "model_cost": {**cost, "provider_payload": "private"},
        }
    )
    assert shown == {
        "duration": {"wall_seconds": 9.5, "worker_seconds": 8.0, "wall_reason": None},
        "model_cost": cost,
        "model_cost_reason": None,
    }
    junk = campaign_view.run_cost(
        {
            "duration": {"wall_seconds": float("nan"), "worker_seconds": "8"},
            "model_cost": {"nanodollars": -1, "calls": 1.5, "unsettled_calls": True},
        }
    )
    assert junk["duration"] == {
        "wall_seconds": None,
        "worker_seconds": None,
        "wall_reason": None,
    }
    assert junk["model_cost"]["nanodollars"] is None
    assert junk["model_cost"]["calls"] is None
    # A record from before U45 carries neither.
    assert campaign_view.run_cost({}) == {
        "duration": None,
        "model_cost": None,
        "model_cost_reason": "not_recorded",
    }


def test_the_baseline_is_null_with_why_until_one_is_registered(monkeypatch):
    challenge = {"id": "electric-motor-magnetics", "version": "1.3"}
    assert campaign_view.baseline(challenge) == {
        "score": None,
        "label": "practice baseline on the public bank",
        "reason": "baseline_unregistered",
        "record": None,
    }
    assert campaign_view.baseline(None)["reason"] == "baseline_unregistered"
    monkeypatch.setitem(
        campaign_view.PRACTICE_BASELINES,
        ("electric-motor-magnetics", "1.3"),
        {
            "score": 0.41,
            "strategy_digest": "sha256:" + "a" * 64,
            "dual_schema": campaign_view.DUAL_FEEDBACK_SCHEMA_V2,
        },
    )
    shown = campaign_view.baseline(challenge)
    assert shown["score"] == 0.41 and shown["reason"] is None
    assert shown["record"]["strategy_digest"] == "sha256:" + "a" * 64
