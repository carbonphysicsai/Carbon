import json
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet
from scripts.dev.onboarding.automation_rehearsal import HEADS, summarize

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "docs/development/challenge_pipeline/automation-rehearsal"


def report():
    return json.loads((FOLDER / "report.json").read_text())


def test_retained_trial_has_same_outputs_and_honest_effort_basis():
    data = report()
    assert data["comparison"]["all_compared_outputs_equal"]
    assert data["comparison"]["baseline_invocations"] == 8
    assert data["comparison"]["batched_invocations"] == 3
    assert data["comparison"]["human_labour_speedup"] is None
    assert "NOT_DEMONSTRATED" in data["comparison"]["human_labour_basis"]
    assert data["candidate_tool_heads"] == HEADS
    assert (
        not data["solver_runs"] and not data["spend"] and not data["stage_acceptance"]
    )
    assert all(not p["full_checklist_claim"] for p in data["phases"])


def test_metrics_replay_does_not_convert_tool_timers_into_labour():
    data = report()
    assert data["process_view"]["metrics_effort_events"] == []
    assert data["process_view"]["effort_exports_by_kind"]["HUMAN"] == []
    assert all(
        r["human_team_effort_hours"] is None
        for r in data["metrics_replay"]["motor_rows"]
    )
    assert all(
        r["accepted_stage_elapsed_s"] is None
        for r in data["metrics_replay"]["motor_rows"]
    )
    assert data["process_view"]["events_examined"] == 24
    assert not data["process_view"]["authority_granted"]
    assert all(not s["accepted_exit_verified"] for s in data["process_view"]["stages"])


def test_every_record_retains_public_source_digest_and_no_acceptance():
    data = report()
    assert len(set(data["event_ids"])) == 24
    for id_ in data["event_ids"]:
        path = (
            ROOT / f"docs/development/challenge_pipeline/onboarding-events/{id_}.json"
        )
        event = json.loads(path.read_text())
        assert event["id"] == id_ and event["challenge"] == "motor"
        assert event["actor_kind"] == "TOOL"
        source = packet.source_path(ROOT, event["source"])
        assert packet.digest(source.read_bytes()) == event["source_sha256"]
        if event["kind"] == "EXIT":
            assert event["disposition"] == "PREPARED"


def test_timing_is_observation_not_guaranteed_speed_or_person_hours():
    data = report()
    assert data["comparison"] == summarize(data["phases"])
    for phase in data["phases"]:
        assert phase["per_clause_wall_s"] >= 0 and phase["batched_wall_s"] >= 0
    # A future slow batch is still a valid observation, never forced to pass.
    slow = summarize(
        [
            {
                "baseline_invocations": 1,
                "per_clause_wall_s": 1,
                "batched_wall_s": 2,
                "outputs_equal": True,
            }
        ]
    )
    assert slow["observed_command_consolidation_ratio"] == 0.5
    assert slow["human_labour_speedup"] is None
