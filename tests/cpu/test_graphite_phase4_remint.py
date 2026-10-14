"""OPT-13: recover an existing breach from a toy campaign store only."""

from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest
from test_attack_analysis import StubAdapter, write_call
from test_attack_verify import ACCEPTED, COMPILE, GOOD, breaching, dry

from carbon.agent_campaign.attack import analysis, verify
from carbon.agent_campaign.graphite import phase4, phase4_remint
from carbon.development_session.profile import canonical


def _fixture(tmp_path, monkeypatch):
    root = tmp_path / "graphite-att-l2-root-E"
    store = root / "attacker"
    controller = store / "controller"
    evidence_dir = controller / "evidence"
    evidence_dir.mkdir(parents=True)
    run_id = phase4.GraphiteProvider.run_id_for(phase4.session_key(1))
    run_dir = store / "graphite" / "runs" / run_id
    attempt_id = write_call(run_dir, COMPILE, dry(GOOD), ACCEPTED, turn=7)
    (attempt,) = analysis.attempts(run_dir)
    adapter = StubAdapter(oracle=breaching())
    verdict = verify.verify(attempt, adapter)
    assert verdict.outcome == verify.BREACHED and verdict.rebuild == verify.REBUILT
    expected = verify.specimen_name(verdict.family, verdict.artifact)
    old = {
        **verdict.record(),
        "specimen": {
            "status": "SPECIMEN_CHECK_FAILED",
            "reason": "ValueError: specimen_record_without_recipe_digest",
            "folder": str(store / "specimens" / expected),
        },
    }
    body = canonical(
        {
            "schema": verify.FINDING_SCHEMA,
            "condition": verdict.condition,
            "verdict": old,
        }
    )
    sha = hashlib.sha256(body).hexdigest()
    evidence = evidence_dir / (sha + ".bin")
    evidence.write_bytes(body)
    database = controller / "campaign.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE runs (key TEXT, campaign TEXT, run_id TEXT)")
        db.execute("CREATE TABLE findings (id TEXT, body TEXT)")
        db.execute(
            "INSERT INTO runs VALUES (?,?,?)",
            (phase4.session_key(1), phase4.CAMPAIGN, run_id),
        )
        db.execute(
            "INSERT INTO findings VALUES (?,?)",
            (
                "attack-failing-trigger-toy-0",
                json.dumps(
                    {
                        "id": "attack-failing-trigger-toy-0",
                        "condition": verdict.condition,
                        "evidence": {
                            "path": "evidence/" + sha + ".bin",
                            "sha256": "sha256:" + sha,
                        },
                    }
                ),
            ),
        )
    log = store / "iteration-log.jsonl"
    log.write_bytes(
        canonical(
            {
                "schema": phase4.LOG_SCHEMA,
                "session": 1,
                "run_id": run_id,
                "challenge": adapter.challenge_id,
                "construction_level": adapter.level,
                "findings": ["attack-failing-trigger-toy-0"],
            }
        )
        + b"\n"
    )
    monkeypatch.setattr(phase4, "attack_modules", dict)
    monkeypatch.setattr(
        phase4, "adapter_for", lambda _atk, _challenge, _level: (adapter, None)
    )
    return root, store, attempt_id, expected, (database, log, evidence)


def test_remint_existing_breach_is_idempotent_and_keeps_raw_attempt(
    tmp_path, monkeypatch, capsys
):
    root, store, attempt, expected, source = _fixture(tmp_path, monkeypatch)
    source_bytes = {path: path.read_bytes() for path in source}
    argv = [
        "remint",
        "--root",
        str(root),
        "--attempt",
        attempt,
        "--specimen",
        expected,
    ]
    assert phase4.main(argv) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["status"] == "REBUILT" and first["reused"] is False
    assert first["excluded_non_session"] == []
    assert first["excluded_non_session_count"] == 0
    assert first["finding_records_seen"] == 1
    folder = store / "specimens" / expected
    assert folder.is_dir()
    assert (
        verify.clean_attack_specimen(folder, StubAdapter(oracle=breaching()))["status"]
        == "REBUILT"
    )
    assert phase4.main(argv) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["status"] == "REBUILT" and second["reused"] is True
    assert {path: path.read_bytes() for path in source} == source_bytes
    assert len(analysis.attempts(store / "graphite" / "runs" / first["run_id"])) == 1


def test_remint_refuses_changed_evidence_and_wrong_specimen(
    tmp_path, monkeypatch, capsys
):
    root, store, attempt, expected, (_db, _log, evidence) = _fixture(
        tmp_path, monkeypatch
    )
    wrong = "specimen-" + "0" * 16
    assert (
        phase4.main(
            ["remint", "--root", str(root), "--attempt", attempt, "--specimen", wrong]
        )
        == 4
    )
    assert (
        json.loads(capsys.readouterr().out)["code"]
        == "remint_source_missing_or_ambiguous"
    )
    evidence.write_bytes(b"{}")
    assert (
        phase4.main(
            [
                "remint",
                "--root",
                str(root),
                "--attempt",
                attempt,
                "--specimen",
                expected,
            ]
        )
        == 4
    )
    assert json.loads(capsys.readouterr().out)["code"] == (
        "finding_evidence_unreadable_or_changed"
    )
    assert not (store / "specimens").exists()


def _add_non_session_finding(
    database, log, evidence_dir, source, finding_id="attack-failing-trigger-toy-control"
):
    common = {"schema": verify.FINDING_SCHEMA, "condition": "FAILING_TRIGGER"}
    if source == "family_report":
        content = {
            "source": "family_report",
            "role": "held_out_control",
            "family": "l2_pool_sources_and_weights",
            "control": "honest_control",
            "control_identity": "sha256:" + "a" * 64,
            "outcome": "WRONGLY_REFUSED",
        }
    else:
        content = {
            "source": "deterministic_baseline",
            "role": "attack",
            "family": "l2_pool_sources_and_weights",
            "attempt": "pool_practice_stratum",
            "evidence_digest": "sha256:" + "a" * 64,
        }
    body = canonical({**common, **content})
    sha = hashlib.sha256(body).hexdigest()
    (evidence_dir / (sha + ".bin")).write_bytes(body)
    with sqlite3.connect(database) as db:
        db.execute(
            "INSERT INTO findings VALUES (?,?)",
            (
                finding_id,
                json.dumps(
                    {
                        "id": finding_id,
                        "condition": "FAILING_TRIGGER",
                        "evidence": {
                            "path": "evidence/" + sha + ".bin",
                            "sha256": "sha256:" + sha,
                        },
                    }
                ),
            ),
        )
    entry = json.loads(log.read_text())
    entry["findings"].insert(0, finding_id)
    log.write_bytes(canonical(entry) + b"\n")
    return finding_id


@pytest.mark.parametrize(
    "source,code",
    [
        ("family_report", "finding_non_session_control_v1"),
        ("deterministic_baseline", "finding_non_session_engine_v1"),
    ],
)
def test_remint_skips_named_older_finding_without_claiming_redaction(
    tmp_path, monkeypatch, capsys, source, code
):
    root, store, attempt, expected, (database, log, _evidence) = _fixture(
        tmp_path, monkeypatch
    )
    older_id = _add_non_session_finding(
        database, log, database.parent / "evidence", source
    )
    with sqlite3.connect(database) as db:
        older = phase4_remint._finding_verdict(database.parent, db, older_id)
    assert older == phase4_remint.NonSessionFinding(code)
    assert older.outcome == "EXCLUDED_NON_SESSION_FINDING"
    assert (
        phase4.main(
            [
                "remint",
                "--root",
                str(root),
                "--attempt",
                attempt,
                "--specimen",
                expected,
                "--session",
                "1",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "REBUILT"
    assert result["excluded_non_session_count"] == 1
    assert result["finding_records_seen"] == 2
    assert result["excluded_non_session"] == [
        {"session": 1, "finding_id": older_id, "code": code}
    ]
    assert (store / "specimens" / expected).is_dir()


def test_all_excluded_finding_occurrences_are_accounted_for(
    tmp_path, monkeypatch, capsys
):
    root, _store, attempt, expected, (database, log, _evidence) = _fixture(
        tmp_path, monkeypatch
    )
    first = _add_non_session_finding(
        database, log, database.parent / "evidence", "family_report", "older-control"
    )
    second = _add_non_session_finding(
        database,
        log,
        database.parent / "evidence",
        "deterministic_baseline",
        "older-baseline",
    )
    assert (
        phase4.main(
            [
                "remint",
                "--root",
                str(root),
                "--attempt",
                attempt,
                "--specimen",
                expected,
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["excluded_non_session_count"] == 2
    assert result["finding_records_seen"] == 3
    assert {row["finding_id"] for row in result["excluded_non_session"]} == {
        first,
        second,
    }
    assert {row["code"] for row in result["excluded_non_session"]} == {
        "finding_non_session_control_v1",
        "finding_non_session_engine_v1",
    }


def test_current_verdict_with_older_looking_fields_remains_session_verdict(
    tmp_path, monkeypatch
):
    _root, _store, _attempt, _expected, (database, _log, evidence) = _fixture(
        tmp_path, monkeypatch
    )
    body = json.loads(evidence.read_bytes())
    body.update(
        source="family_report",
        role="trained_control",
        outcome="WRONGLY_REFUSED",
        family="l2_pool_sources_and_weights",
        control="honest_control",
        control_identity="sha256:" + "a" * 64,
    )
    raw = canonical(body)
    sha = hashlib.sha256(raw).hexdigest()
    (evidence.parent / (sha + ".bin")).write_bytes(raw)
    with sqlite3.connect(database) as db:
        finding_id, old = db.execute("SELECT id, body FROM findings").fetchone()
        row = json.loads(old)
        row["evidence"] = {
            "path": "evidence/" + sha + ".bin",
            "sha256": "sha256:" + sha,
        }
        db.execute(
            "UPDATE findings SET body=? WHERE id=?", (json.dumps(row), finding_id)
        )
        verdict = phase4_remint._finding_verdict(database.parent, db, finding_id)
    assert isinstance(verdict, dict)
    assert verdict["outcome"] == verify.BREACHED


@pytest.mark.parametrize(
    "failure", ["schema", "condition", "coverage", "unknown_older"]
)
def test_remint_keeps_session_verdict_integrity_checks(tmp_path, monkeypatch, failure):
    _root, _store, _attempt, _expected, (database, _log, evidence) = _fixture(
        tmp_path, monkeypatch
    )
    body = json.loads(evidence.read_bytes())
    if failure == "schema":
        body["schema"] = "wrong.schema"
    elif failure == "condition":
        body["condition"] = "OTHER_SIGNAL"
    elif failure == "coverage":
        body["verdict"]["conditions"] = []
    else:
        body.pop("verdict")
        body["source"] = "unregistered_source"
    raw = canonical(body)
    sha = hashlib.sha256(raw).hexdigest()
    updated = evidence.parent / (sha + ".bin")
    updated.write_bytes(raw)
    with sqlite3.connect(database) as db:
        finding_id, old = db.execute("SELECT id, body FROM findings").fetchone()
        row = json.loads(old)
        row["evidence"] = {
            "path": "evidence/" + sha + ".bin",
            "sha256": "sha256:" + sha,
        }
        db.execute(
            "UPDATE findings SET body=? WHERE id=?", (json.dumps(row), finding_id)
        )
        with pytest.raises(phase4_remint.RemintRefused) as error:
            phase4_remint._finding_verdict(database.parent, db, finding_id)
    assert error.value.code == "finding_verdict_malformed"
