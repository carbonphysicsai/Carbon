"""READINESS-GAPS-01: producer evidence checks on toy inputs only."""

import json
from pathlib import Path

from carbon.challenge_pipeline import __main__ as pipeline_cli
from carbon.challenge_pipeline.readiness import checks, evidence_checks, runner
from carbon.challenge_validator.interface import digest as registry_digest

CHALLENGE = "example-challenge"


def _write(path: Path, document: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as out:
        json.dump(document, out, sort_keys=True)
    return path


def _registration(repo: Path, name: str, document: dict) -> Path:
    return _write(
        repo / "carbon/challenge_pipeline/readiness" / CHALLENGE / name, document
    )


def _context(repo: Path, **evidence_paths) -> checks.Context:
    return checks.Context(CHALLENGE, 0, repository=repo, evidence_paths=evidence_paths)


def _margin(tmp_path):
    repo = tmp_path / "repo"
    panel = _write(
        tmp_path / "margin-panel.json",
        {
            "schema": evidence_checks.MARGIN_PANEL_SCHEMA,
            "challenge": CHALLENGE,
            "margins": {"gate-a": [0.1, 0.3, 0.4], "gate-b": [2.0, 3.0, 4.0]},
        },
    )
    _registration(
        repo,
        "gate-margin-registration.json",
        {
            "schema": evidence_checks.MARGIN_REGISTRATION_SCHEMA,
            "challenge": CHALLENGE,
            "panel_digest": evidence_checks._digest(panel),
            "gates": [
                {"name": "gate-a", "unit": "toy", "fragile_below": 0.15},
                {"name": "gate-b", "unit": "toy", "fragile_below": 1.0},
            ],
        },
    )
    return repo, panel


def _overlap(tmp_path):
    repo = tmp_path / "repo"
    directory = repo / "carbon/challenge_validator/confirmation_sets"
    roles = {}
    for role in ("tuning", "sealed-a", "unsealed-b"):
        document = {"role": role, "challenge_id": CHALLENGE}
        _write(directory / f"{role}.json", document)
        roles[role] = registry_digest(document)
    _write(directory / "registry.json", {"sets": roles})
    panel = _write(
        tmp_path / "overlap-panel.json",
        {
            "schema": evidence_checks.OVERLAP_PANEL_SCHEMA,
            "challenge": CHALLENGE,
            "groups": {
                role: [{"toy_input": index}]
                for index, role in enumerate(
                    (
                        "tuning",
                        "sealed-a",
                        "rotating_pool",
                        "TRAIN",
                        "PRACTICE",
                        "practice_decision",
                    )
                )
            },
        },
    )
    registration = {
        "schema": evidence_checks.OVERLAP_REGISTRATION_SCHEMA,
        "challenge": CHALLENGE,
        "panel_digest": evidence_checks._digest(panel),
        "tuning_role": "tuning",
        "sealed_roles": ["sealed-a"],
        "unsealed_roles": ["unsealed-b"],
    }
    _registration(repo, "tuning-overlap-registration.json", registration)
    return repo, panel, registration


def test_s3_computes_per_gate_minimum_p01_and_fragility(tmp_path):
    repo, panel = _margin(tmp_path)
    report = runner.run_gate(
        CHALLENGE,
        0,
        only=["S3"],
        repository=repo,
        root=repo,
        evidence_paths={"S3": panel},
    )
    (row,) = report["items"]
    assert row["status"] == "PASS"
    assert any(
        "gate-a: min=0.1 p01=0.104" in e and "fragile=True" in e
        for e in row["evidence"]
    )
    assert any("gate-b: min=2.0" in e and "fragile=False" in e for e in row["evidence"])
    assert report["partial"] and not report["green"]


def test_s3_missing_malformed_and_unregistered_evidence_never_pass(tmp_path):
    repo, panel = _margin(tmp_path)
    item = {"id": "S3"}
    assert evidence_checks.gate_margin_study(item, _context(repo)).status == "NOT_BUILT"
    registration = (
        repo
        / "carbon/challenge_pipeline/readiness"
        / CHALLENGE
        / "gate-margin-registration.json"
    )
    registration.unlink()
    assert (
        evidence_checks.gate_margin_study(item, _context(repo, S3=panel)).status
        == "NOT_BUILT"
    )
    _margin(tmp_path)
    _write(
        panel,
        {
            "schema": evidence_checks.MARGIN_PANEL_SCHEMA,
            "challenge": CHALLENGE,
            "margins": {"gate-a": [0.1]},
        },
    )
    assert (
        evidence_checks.gate_margin_study(item, _context(repo, S3=panel)).status
        == "FAIL"
    )
    registered = json.loads(registration.read_text())
    registered["panel_digest"] = evidence_checks._digest(panel)
    _write(registration, registered)
    result = evidence_checks.gate_margin_study(item, _context(repo, S3=panel))
    assert result.status == "FAIL" and "coverage_incomplete" in result.detail


def test_h2_checks_every_registered_role_and_public_prior_without_leaking_cases(
    tmp_path,
):
    repo, panel, registration = _overlap(tmp_path)
    result = evidence_checks.tuning_overlap({"id": "H2"}, _context(repo, H2=panel))
    assert result.status == "PASS"
    assert "groups:6" in result.evidence
    assert "cases:6" in result.evidence
    assert "toy_input" not in repr(result)
    registration["unsealed_roles"] = []
    _registration(repo, "tuning-overlap-registration.json", registration)
    assert (
        evidence_checks.tuning_overlap({"id": "H2"}, _context(repo, H2=panel)).status
        == "FAIL"
    )


def test_h2_overlap_and_missing_public_group_fail(tmp_path):
    repo, panel, registration = _overlap(tmp_path)
    document = json.loads(panel.read_text())
    document["groups"]["PRACTICE"] = [{"toy_input": 0}]
    _write(panel, document)
    registration["panel_digest"] = evidence_checks._digest(panel)
    _registration(repo, "tuning-overlap-registration.json", registration)
    result = evidence_checks.tuning_overlap({"id": "H2"}, _context(repo, H2=panel))
    assert result.status == "FAIL" and "overlap_between_groups" in result.detail
    document["groups"].pop("practice_decision")
    _write(panel, document)
    registration["panel_digest"] = evidence_checks._digest(panel)
    _registration(repo, "tuning-overlap-registration.json", registration)
    result = evidence_checks.tuning_overlap({"id": "H2"}, _context(repo, H2=panel))
    assert result.status == "FAIL" and "coverage" in result.detail


def test_v3_remains_human_review_item():
    from carbon.challenge_pipeline.readiness.model import load_items

    (item,) = [row for row in load_items() if row["id"] == "V3"]
    assert item["kind"] == "review" and item["check"] == "review_only"


def test_cli_refuses_to_write_producer_panel_evidence_into_history(capsys):
    status = pipeline_cli.main(
        ["readiness", "--challenge", CHALLENGE, "--margin-panel", "private.json"]
    )
    assert status == 2
    assert "requires --no-history" in capsys.readouterr().out


def test_cli_refuses_private_aggregate_json_inside_repository(capsys):
    from carbon.challenge_pipeline.readiness.model import REPOSITORY

    status = pipeline_cli.main(
        [
            "readiness",
            "--challenge",
            CHALLENGE,
            "--margin-panel",
            "private.json",
            "--no-history",
            "--json",
            str(REPOSITORY / "would-leak.json"),
        ]
    )
    assert status == 2
    assert "must be outside repository" in capsys.readouterr().out
