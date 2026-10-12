import copy
import json
import sys

import pytest

from carbon.challenge_pipeline.onboarding import packet
from carbon.challenge_pipeline.onboarding import telemetry as t

STAGES = list(dict.fromkeys(t.MAPPING.values()))
DIGEST = "a" * 64


def event(kind, id_, at, **extra):
    return {
        "schema": t.SCHEMA,
        "id": id_,
        "challenge": "motor",
        "cycle": "motor-rehearsal",
        "stage": "S1_packet",
        "kind": kind,
        "at": at,
        "actor": "packets",
        "actor_kind": "AI_AGENT",
        "source": "docs/development/challenge_pipeline/toy.md",
        "source_sha256": DIGEST,
        "stage_map_sha256": DIGEST,
        **extra,
    }


def records():
    return [
        event("ENTRY", "entry", "2026-10-11T10:00:00Z"),
        event(
            "EXIT",
            "exit",
            "2026-10-11T12:00:00Z",
            entry_id="entry",
            disposition="PREPARED",
        ),
        event("EFFORT_START", "start", "2026-10-11T10:10:00Z", milestone="packet"),
        event("EFFORT_END", "end", "2026-10-11T10:20:00Z", start_id="start"),
    ]


def analyze(events):
    return t.analyze(events, "motor", STAGES, DIGEST)


def test_clock_stage_and_effort_are_separate_not_acceptance():
    report = analyze(records())
    row = next(r for r in report["stages"] if r["stage"] == "S1_packet")
    assert row["recorded_cycles"][0]["calendar_s"] == 7200
    assert row["active_hours_partial"]["AI_AGENT"] == pytest.approx(1 / 6)
    assert row["active_hours_partial"]["HUMAN"] is None
    assert not row["accepted_exit_verified"] and not report["authority_granted"]
    assert report["metrics_effort_events"] == []
    assert report["effort_exports_by_kind"]["AI_AGENT"][0]["duration_s"] == 600
    assert report["effort_exports_by_kind"]["AI_AGENT"][0]["stage"] == "packet"


def test_open_missing_and_subsecond_work_are_not_invented_hours():
    report = analyze(records()[:1])
    assert not report["metrics_effort_events"]
    assert all(
        all(v is None for v in r["active_hours_partial"].values())
        for r in report["stages"]
    )
    events = records()[2:]
    events[-1]["at"] = "2026-10-11T10:10:00.500000Z"
    report = analyze(events)
    assert not report["metrics_effort_events"]
    assert report["stages"][1]["active_hours_partial"]["AI_AGENT"] == pytest.approx(
        0.5 / 3600
    )


def test_duplicate_closures_reversed_context_and_overlaps_refused():
    events = records()
    with pytest.raises(packet.DraftError, match="duplicate"):
        analyze([*events, events[0]])
    bad = copy.deepcopy(events[-1])
    bad["id"] = "another"
    with pytest.raises(packet.DraftError, match="unique complete"):
        analyze([*events, bad])
    for change in (
        {"at": "2026-10-11T09:00:00Z"},
        {"cycle": "other"},
        {"actor": "other"},
    ):
        with pytest.raises(packet.DraftError):
            analyze([*events[:-1], {**events[-1], **change}])
    start = event(
        "EFFORT_START", "other-start", "2026-10-11T10:15:00Z", milestone="packet"
    )
    end = event(
        "EFFORT_END", "other-end", "2026-10-11T10:30:00Z", start_id="other-start"
    )
    with pytest.raises(packet.DraftError, match="overlapping"):
        analyze([*events, start, end])
    with pytest.raises(packet.DraftError, match="overlapping"):
        analyze([*events, start])


def test_global_cross_challenge_overlap_and_two_open_blocks_are_refused():
    events = records()
    start = {
        **event("EFFORT_START", "other", "2026-10-11T10:15:00Z", milestone="packet"),
        "challenge": "battery-v3",
    }
    end = {
        **event("EFFORT_END", "other-end", "2026-10-11T10:30:00Z", start_id="other"),
        "challenge": "battery-v3",
    }
    with pytest.raises(packet.DraftError, match="cross-Challenge"):
        analyze([*events, start, end])
    with pytest.raises(packet.DraftError, match="open"):
        analyze([events[2], {**start, "at": "2026-10-11T11:00:00Z"}])


def test_human_agent_and_tool_timers_never_collapse_to_person_hours():
    events = records()
    for kind, hour in (("HUMAN", 11), ("TOOL", 12)):
        start = event(
            "EFFORT_START",
            "start-" + kind,
            f"2026-10-11T{hour}:00:00Z",
            milestone="packet",
        )
        end = event(
            "EFFORT_END",
            "end-" + kind,
            f"2026-10-11T{hour}:30:00Z",
            start_id=start["id"],
        )
        start.update(actor=kind.lower(), actor_kind=kind)
        end.update(actor=kind.lower(), actor_kind=kind)
        events.extend([start, end])
    row = analyze(events)["stages"][1]
    assert row["active_hours_partial"] == {
        "HUMAN": 0.5,
        "AI_AGENT": pytest.approx(1 / 6),
        "TOOL": 0.5,
    }


@pytest.mark.parametrize(
    "value", ["2026-10-11T10:00:00", "2026-10-11T10:00:00+01:00", "bad"]
)
def test_non_utc_or_invalid_clocks_refused(value):
    with pytest.raises(packet.DraftError):
        t.moment(value)


def test_stage_or_milestone_mismatch_refused_and_stage_drift_is_visible():
    with pytest.raises(packet.DraftError, match="milestone"):
        analyze(
            [
                event(
                    "EFFORT_START",
                    "x",
                    "2026-10-11T10:00:00Z",
                    milestone="verification_spec",
                )
            ]
        )
    report = t.analyze(records(), "motor", STAGES, "b" * 64)
    assert not report["stages"][1]["recorded_cycles"][0]["current_stage_definition"]


def test_no_events_view_has_unknowns_and_source_changes_do_not_erase_clock(tmp_path):
    stage = tmp_path / t.STAGE_MAP
    stage.parent.mkdir(parents=True)
    stage.write_text(json.dumps({"stages": [{"id": s} for s in STAGES]}))
    assert "UNKNOWN" in t.render(t.view(tmp_path, "motor"))
    source = tmp_path / records()[0]["source"]
    source.write_text("source revised since record")
    folder = tmp_path / t.FOLDER
    folder.mkdir()
    for row in records():
        (folder / (row["id"] + ".json")).write_text(json.dumps(row))
    report = t.view(tmp_path, "motor")
    assert all(
        v["state"] == "SOURCE_CHANGED" for v in report["source_observations"].values()
    )
    assert report["effort_exports_by_kind"]["AI_AGENT"][0]["duration_s"] == 600


def test_cli_timer_creates_unique_immutable_public_records(
    tmp_path, monkeypatch, capsys
):
    stage = tmp_path / t.STAGE_MAP
    stage.parent.mkdir(parents=True)
    stage.write_text(json.dumps({"stages": [{"id": s} for s in STAGES]}))
    source = tmp_path / "docs/development/challenge_pipeline/toy.md"
    source.write_text("public")
    args = [
        "telemetry",
        "--root",
        str(tmp_path),
        "start",
        "--challenge",
        "motor",
        "--cycle",
        "rehearsal",
        "--stage",
        "S1_packet",
        "--actor",
        "packets",
        "--actor-kind",
        "AI_AGENT",
        "--source",
        source.relative_to(tmp_path).as_posix(),
        "--milestone",
        "packet",
    ]
    monkeypatch.setattr(sys, "argv", args)
    assert t.main() == 0
    start = json.loads(capsys.readouterr().out)
    original = (tmp_path / t.FOLDER / (start["id"] + ".json")).read_bytes()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "telemetry",
            "--root",
            str(tmp_path),
            "finish",
            "--challenge",
            "motor",
            "--ref-id",
            start["id"],
        ],
    )
    assert t.main() == 0
    end = json.loads(capsys.readouterr().out)
    assert end["id"] != start["id"]
    assert (tmp_path / t.FOLDER / (start["id"] + ".json")).read_bytes() == original
    assert t.view(tmp_path, "motor")["events_examined"] == 2


def test_status_command_includes_process_without_promoting_stage(
    tmp_path, monkeypatch, capsys
):
    from carbon.challenge_pipeline.onboarding import __main__ as cli
    from carbon.challenge_pipeline.onboarding import evidence_readiness, status

    stage = tmp_path / t.STAGE_MAP
    stage.parent.mkdir(parents=True)
    stage.write_text(json.dumps({"stages": [{"id": s} for s in STAGES]}))
    monkeypatch.setattr(
        status,
        "generate",
        lambda *args, **kw: {"challenge": "motor", "tested_challenge_claim": False},
    )
    monkeypatch.setattr(
        evidence_readiness, "generate", lambda *args, **kw: {"qualified": False}
    )
    assert (
        cli.main(
            [
                "--root",
                str(tmp_path),
                "status",
                "--challenge",
                "motor",
                "--format",
                "json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["recorded_process"]["events_examined"] == 0
    assert not report["tested_challenge_claim"]
