import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import status
from carbon.challenge_pipeline.onboarding.__main__ import main

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "challenge",
    ["motor", "battery-v3", "cooling-cell", "f02", "f06", "f08", "f13", "f17"],
)
def test_all_eight_views_report_basis_not_artifact_success(challenge):
    view = status.generate(ROOT, challenge)
    assert view["binding_status"] == "CONFIGURED"
    assert len(view["stages"]) == 11
    assert view["observed_artifact_stages"]
    assert not view["tested_challenge_claim"]
    assert all(not s["exit_verified"] for s in view["stages"])
    assert view["basis"]["stage_map_sha256"]
    assert all(s["owner"] and s["next_required"] for s in view["stages"])


def test_motor_existing_law_blocks_and_stale_readiness_are_explicit():
    view = status.generate(ROOT, "electric-motor-magnetics")
    assert view["challenge"] == "motor"
    law = next(s for s in view["stages"] if s["id"] == "S4_question_law")
    gaps = law["artifacts"][0]["gaps"]
    assert any(g["state"] == "AWAITING_REEXPORT" for g in gaps)
    readiness = next(s for s in view["stages"] if s["id"] == "S6_readiness")
    assert readiness["progress"] == "HISTORICAL_READINESS_NOT_CURRENT"
    snapshot = readiness["artifacts"][0]["readiness_snapshot"]
    assert snapshot["report_verified"] and snapshot["items_checked"] == 41
    assert snapshot["counts"]["FAIL"] == 5
    assert "Historical counts" in status.render(view)


def test_new_challenge_returns_missing_bindings_not_absent_work():
    view = status.generate(ROOT, "new-brief")
    assert view["binding_status"] == "HUMAN_INPUT_ARTIFACT_BINDINGS"
    assert all(
        s["what_was_checked"] == {"configured": 0, "read": 0} for s in view["stages"]
    )
    assert not view["tested_challenge_claim"]


def test_missing_and_disallowed_paths_are_not_converted_to_pass():
    for relative in ("docs/development/missing.json", "../secret", ".git/config"):
        row = status.inspect(ROOT, relative)
        assert row["state"] == "UNAVAILABLE_OR_REFUSED"
        assert "cannot conclude" in row["basis"]


def test_cli_is_read_only_and_emits_no_solver_or_host_claim(capsys):
    assert (
        main(
            ["--root", str(ROOT), "status", "--challenge", "motor", "--format", "json"]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["tested_challenge_claim"] is False
    assert main(["--root", str(ROOT), "status", "--challenge", "../hidden"]) == 2
    assert "../hidden" not in capsys.readouterr().err


def test_status_reports_gap_fields_not_reference_rows_or_seeds():
    assert status.gaps(
        {"reference": [{"seed": "SECRET", "values": {"x": 10}}], "registered": None}
    ) == [{"field": "registered", "state": None}]
    result = status.generate(ROOT, "motor")
    assert "phase4" not in json.dumps(result)
