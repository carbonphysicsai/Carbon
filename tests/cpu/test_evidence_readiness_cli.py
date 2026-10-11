import json
from pathlib import Path

from carbon.challenge_pipeline.onboarding import evidence_readiness as er
from carbon.challenge_pipeline.onboarding.__main__ import main

ROOT = Path(__file__).resolve().parents[2]


def test_status_appends_readiness_and_keeps_existing_fields(capsys):
    assert (
        main(["--root", str(ROOT), "status", "--challenge", "f02", "--format", "json"])
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["tested_challenge_claim"] is False
    assert len(result["evidence_readiness"]["items"]) == 7
    assert not result["evidence_readiness"]["spend_authorized"]


def test_unknown_family_remains_compatible_with_status_custom_bindings():
    report = er.generate(ROOT, "future-brief")
    assert all(row["state"] == "UNKNOWN" for row in report["items"])
    assert not report["spend_authorized"]


def test_unmerged_head_cannot_be_used_as_main_evidence():
    report = er.generate(ROOT, "f02", main_ref="HEAD")
    assert report["main"] is None
    assert not report["all_prerequisites_yes"]
