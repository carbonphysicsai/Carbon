"""A battery campaign's measured practice reaches `observe` on both doors.

The projection read `manifest["provider"]["model"]`, which a battery campaign
with no agent does not have (its frozen plan is {"agent": "none",
"model_calls": 0}), so observing it raised KeyError; and it dropped every
battery practice result because it knew only the Burgers provenance.
"""

from __future__ import annotations

import json

from test_miner_launchpad_runner import RUNTIME, registered

from carbon.battery.campaign import provider_plan
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import PRODUCT, CampaignLedger
from scripts.dev.miner_launchpad.projection import project

# Shaped as carbon.battery.practice.feedback() records it: the exam's own
# aggregate on public PRACTICE, fit statistics and the backend that ran.
PRACTICE = {
    "schema": "carbon.battery.practice-feedback.v1",
    "provenance": "BATTERY_PUBLIC_PRACTICE",
    "challenge": {"id": "battery-fastcharge-ageing-development", "version": "1.0"},
    "recipe_digest": "sha256:" + "a" * 64,
    "backbone": "mlp",
    "summary": {"score": 0.42, "eligible": True, "gate_failures": [], "n_scored": 12},
    "fit": {"final_loss": 0.0137, "train_s": 41.5, "n_params": 1234},
    "backend": {"kind": "ISOLATED_CARRIER"},
    "recipe": {"schema_version": "1.0", "backbone": "mlp"},
    "adaptively_seen": True,
    "final_exam": False,
}


def _battery_campaign(root):
    ledger = CampaignLedger(root, clock=lambda: 1000)
    ledger.generation = CampaignControl(ledger).acquire()
    manifest = {
        "schema": PRODUCT,
        "authority": "C-MLP-02-D11",
        "campaign_id": "cmp-battery",
        "principal": "alice",
        "owner": "miner-requester",
        "agent": "none",
        "runtime": RUNTIME,
        "admission": registered().record(),
        "implementation": RUNTIME["implementation"],
        "images": RUNTIME["images"],
        "objective": "battery",
        "sampling": "battery",
        "control": "battery",
        "selection": "battery",
        "replica_policy": "battery",
        "provider": provider_plan("none", {}),
    }
    ledger.freeze(manifest)
    body = canonical(PRACTICE)
    with ledger.db() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_results "
            "(owner TEXT, task TEXT, body BLOB, digest TEXT)"
        )
        db.execute(
            "INSERT INTO research_results VALUES (?,?,?,?)",
            ("miner-requester", "task-1", body, digest(body)),
        )
    return {
        "id": "run-battery",
        "campaign": "cmp-battery",
        "profile": "p",
        "state": "READY",
        "principal": "alice",
    }


def test_a_battery_campaign_with_no_agent_projects(tmp_path):
    assert "model" not in provider_plan("none", {})
    row = _battery_campaign(tmp_path)
    value = project(row, tmp_path)
    assert value["selects"] == "miner"
    assert value["agent"] == "manual"
    assert value["reasoning"] is None


def test_battery_practice_is_projected_as_measured(tmp_path):
    value = project(_battery_campaign(tmp_path), tmp_path)
    assert value["completed_experiments"] == 1
    (experiment,) = value["experiments"]
    assert experiment["provenance"] == "BATTERY_PUBLIC_PRACTICE"
    assert experiment["summary"] == PRACTICE["summary"]
    assert experiment["fit"] == PRACTICE["fit"]
    assert experiment["backend"] == {"kind": "ISOLATED_CARRIER"}
    # Recorded values only: nothing the practice did not report appears.
    assert "completed_steps" not in experiment
    json.dumps(value, allow_nan=False)
