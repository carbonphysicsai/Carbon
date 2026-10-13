"""Run the five-item gate with actual pytest evidence in pinned CI."""

import json

import pytest

from carbon.challenge_pipeline.readiness import model, runner


@pytest.mark.parametrize("level", [2, 3, 4])
def test_batch1_gate_runs_the_recorded_level_assertions(tmp_path, level):
    items = {"P3", "R7", "A2", "A3", "S2"}
    report = runner.run_gate(
        "battery-fastcharge-ageing-development-v1",
        level,
        only=items,
    )
    (tmp_path / f"batch1-readiness-level-{level}.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    assert {row["id"] for row in report["items"]} == items
    assert all(row["status"] == model.PASS for row in report["items"]), report
    assert report["partial"] and not report["green"] and not report["launch_ready"]
    assert report["claims"] == {
        "authority_to_run": False,
        "live_run": False,
        "spend": False,
    }
    print(
        json.dumps(
            {
                "level": level,
                "items": {row["id"]: row["status"] for row in report["items"]},
            }
        )
    )
