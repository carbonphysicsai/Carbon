import hashlib
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


def test_json_default_is_v1_and_v2_is_an_explicit_cli_choice(capsys):
    args = ["--root", str(ROOT), "readiness", "--challenge", "f08", "--format", "json"]
    assert main(args) == 0
    legacy = json.loads(capsys.readouterr().out)
    assert legacy["schema"] == "carbon.onboarding.evidence-readiness.v1"
    assert all(row["state"] != "PROPOSED" for row in legacy["items"])
    assert main(args + ["--report-version", "2"]) == 0
    modern = json.loads(capsys.readouterr().out)
    assert modern["schema"] == "carbon.onboarding.evidence-readiness.v2"
    assert modern["yes_count"] == legacy["yes_count"]


def test_v1_generated_contract_is_accepted_by_unchanged_campaign_reader(tmp_path):
    from carbon.development_comparison.evidence_campaign import _readiness

    # Fixture identity, no dispatch: exercise the real closed reader, including
    # labels and states, without touching the optimizer's implementation.
    report = er.generate(ROOT, "battery-v3", main_ref="HEAD")
    report["main"] = "a" * 40
    path = tmp_path / "synthetic-readiness.json"
    raw = json.dumps(report).encode()
    path.write_bytes(raw)
    assert (
        _readiness(
            path,
            "sha256:" + hashlib.sha256(raw).hexdigest(),
            "battery-v3",
            require_yes=False,
        )
        == report
    )
