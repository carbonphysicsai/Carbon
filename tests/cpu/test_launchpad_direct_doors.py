"""Direct campaign refusals through the real Launchpad HTTP and MCP doors.

The Battery worker serves direct graph recipes, so a legacy KNN strategy must
be refused before a task starts. The receiver remains unserved. The battery
harness uses development fixtures; no chain or model job runs.
"""

import json
import sys
from pathlib import Path

import pytest

from carbon.development_session.profile import canonical, digest
from scripts.dev.miner_launchpad import levels, supervisor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "service"))

from test_launchpad_production_journey import BATTERY, KNN

pytest_plugins = ("test_launchpad_extended_journey",)


def _launch(key, **extra):
    return {
        "agent": "none",
        "challenge": BATTERY,
        "challenge_version": "1.0",
        "idempotency_key": key,
        **extra,
    }


def test_new_direct_campaign_fails_closed_through_both_doors(
    battery, door, monkeypatch
):
    call = door(battery)
    launched = call("launch", _launch("direct-door-new-0001"))
    assert "error" not in launched, launched
    battery.join()
    identity = launched["id"]

    with battery.host.db() as db:
        row = dict(
            db.execute(
                "SELECT * FROM launchpad_campaigns WHERE id=?", (identity,)
            ).fetchone()
        )
    recorded = json.loads(row["launch_request"])
    assert row["construction_binding_version"] == 4
    assert not {"construction_level", "arm", "construction_variant_digest"} & set(
        recorded
    )
    manifest = json.loads(
        (battery.campaign_root(identity) / "campaign-manifest.json").read_bytes()
    )
    assert manifest["construction_mode"] == "direct"
    assert manifest["challenge"] == {"id": BATTERY, "version": "1.0"}

    practice = call(
        "practice",
        {
            "campaign": identity,
            "strategy": KNN,
            "hypothesis": "legacy recipe is not a direct construction recipe",
            "idempotency_key": "direct-door-practice-0001",
        },
    )
    assert practice["error"] == "construction_recipe_malformed"
    submit = call(
        "submit", {"campaign": identity, "idempotency_key": "direct-door-submit-0001"}
    )
    # A refused legacy recipe leaves no frozen candidate; the first truthful
    # submit refusal is the missing freeze, before receiver admission.
    assert submit["error"] == "freeze_a_candidate_first"
    # Isolate the receiver gate as though a future worker had supplied a
    # frozen candidate. The fixture never creates state or calls an intake.
    monkeypatch.setattr(
        type(battery.host), "_require_frozen", staticmethod(lambda _: None)
    )
    receiver = call(
        "submit", {"campaign": identity, "idempotency_key": "direct-door-submit-0002"}
    )
    # A direct campaign submits through its own evaluate to the construction
    # receiver (M1 E2E H9), so the gate is no longer a blanket refusal: here
    # the next truthful refusal is the frozen record itself, before anything
    # is signed or sent.
    assert receiver["error"] == "freeze_a_candidate_first"
    assert battery.view(identity)["in_flight"] is None
    assert battery.view(identity)["journey"]["submitted_epochs"] == []

    battery.restart()
    call = door(battery)
    assert call("observe", {"campaign": identity})["id"] == identity
    assert call("launch", _launch("direct-door-new-0001"))["id"] == identity
    for request in (
        _launch("direct-door-new-0001", construction_level=0),
        _launch("direct-door-new-0001", arm=None),
        _launch("direct-door-retired-0001", arm="signed"),
    ):
        refused = call("launch", request)
        assert refused["error"] == "construction_selector_retired"
        assert refused["next_step"] == supervisor.NEXT_ACTIONS[refused["error"]]


def test_wrong_train_binding_refused_before_practice_through_both_doors(battery, door):
    from test_battery_direct_practice import _recipe

    call = door(battery)
    launched = call("launch", _launch("direct-wrong-train-0001"))
    assert "error" not in launched, launched
    battery.join()
    identity = launched["id"]
    recipe = _recipe("sha256:" + "a" * 64)
    recipe["challenge"]["train_digest"] = "sha256:" + "f" * 64
    refused = call(
        "practice",
        {
            "campaign": identity,
            "strategy": recipe,
            "hypothesis": "wrong TRAIN binding must not dispatch",
            "idempotency_key": "direct-wrong-train-practice-0001",
        },
    )
    assert refused["error"] == "construction_recipe_binding_mismatch"
    view = call("observe", {"campaign": identity})
    assert view["attempted_experiments"] == 0
    assert view["completed_experiments"] == 0


@pytest.mark.parametrize(
    "changed",
    [
        {"construction_level": 2},
        {"arm": "inert_fields"},
        {"construction_level": None},
        {"construction_variant_digest": None},
        {"arm": None},
    ],
)
def test_archived_level_arm_key_replays_only_exactly_after_restart(
    battery, door, changed
):
    """Rehydrate one old row shape; new selector-bearing launches stay closed."""
    call = door(battery)
    key = "historical-level-arm-0001"
    created = call("launch", _launch(key))
    assert "error" not in created, created
    battery.join()
    identity = created["id"]
    historical = _launch(key, construction_level=1, arm="signed")
    challenge = {"id": BATTERY, "version": "1.0"}
    binding = levels.launch_binding(historical, challenge, "none", battery.cfg)
    captured = levels.capture_binding(binding)
    with battery.host.db() as db:
        row = dict(
            db.execute(
                "SELECT * FROM launchpad_campaigns WHERE id=?", (identity,)
            ).fetchone()
        )
        recorded = json.loads(row["launch_request"])
        recorded.update({"construction_level": 1, "arm": "signed"})
        recorded[levels.CONSTRUCTION_ADMISSION] = captured
        request_digest = battery.host._launch_identity(battery.cfg, historical)[1]
        db.execute(
            "UPDATE launchpad_campaigns SET request_digest=?, launch_request=?, "
            "construction_binding_version=?, construction_binding_digest=? WHERE id=?",
            (
                request_digest,
                canonical(recorded),
                levels.capture_version(captured),
                digest(canonical(captured)),
                identity,
            ),
        )
    # The prior writer also placed its level binding in the prepared manifest.
    manifest_path = battery.campaign_root(identity) / "campaign-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["construction_level"] = binding
    manifest.pop("construction_mode", None)
    manifest_path.write_bytes(canonical(manifest))

    battery.restart()
    call = door(battery)
    assert call("launch", historical)["id"] == identity
    assert call("launch", {**historical, **changed})["error"] == (
        "research_launch_replay_conflict"
    )
    assert (
        call("launch", _launch("historical-new-key-0001", construction_level=1))[
            "error"
        ]
        == "construction_selector_retired"
    )
