"""OPT-13: recover an existing breach from a toy campaign store only."""

from __future__ import annotations

import hashlib
import json
import sqlite3

from test_attack_analysis import StubAdapter, write_call
from test_attack_verify import ACCEPTED, COMPILE, GOOD, breaching, dry

from carbon.agent_campaign.attack import analysis, verify
from carbon.agent_campaign.graphite import phase4
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
