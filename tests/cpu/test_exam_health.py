"""The operator's exam-health report (EXAM_REFRESH_TRACKING_AUDIT_20261029, gap 5)."""

import json
import re
import sqlite3
from pathlib import Path

from carbon.challenge_validator import exam_cap, exam_health, exam_rotation

DAY = exam_cap.DAY_BLOCKS
SECRET_KEY = "sealed-key-0123456789abcdef"
NS = 1_700_000_000 * 10**9


def _ledger(tmp_path, keys=(), checks=()):
    path = tmp_path / "ledger.sqlite"
    db = sqlite3.connect(path)
    db.executescript(exam_cap._DDL)
    db.executescript(exam_rotation._DDL)
    for challenge, version, first_block in keys:
        db.execute(
            "INSERT INTO exam_keys VALUES(?,?,?,?)",
            (challenge, version, SECRET_KEY, first_block),
        )
    for challenge, version, outcome, reason in checks:
        db.execute(
            "INSERT INTO fresh_draw_log(challenge_id, challenge_version, king_submission_id, "
            "sealed_key, fresh_key, block, sealed_total, fresh_total, margin, se_sealed, "
            "se_fresh, threshold, outcome, reason, at_ns) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                challenge,
                version,
                "king-sub-77",
                SECRET_KEY,
                "fresh-key-xyz",
                5,
                0.8123,
                0.7777,
                0.01,
                0.02,
                0.02,
                0.07,
                outcome,
                reason,
                NS,
            ),
        )
    db.commit()
    db.close()
    return path


def _by(rows):
    return {row["challenge"]: row for row in rows}


def test_age_days_left_and_the_75_and_90_day_limits(tmp_path):
    now = 1000 * DAY
    ledger = _ledger(
        tmp_path,
        keys=[
            ("f02", "2.5", now - 10 * DAY),
            ("f08-ribbed-bracket", "1.7", now - 75 * DAY),
            ("chip-cold-plate", "1.6", now - 90 * DAY),
        ],
    )
    rows = _by(exam_health.report(ledger, block=now))
    assert (
        rows["f02"]["state"],
        rows["f02"]["age_days"],
        rows["f02"]["days_left"],
    ) == ("OK", 10, 80)
    assert rows["f08-ribbed-bracket"]["state"] == "WARNING"
    assert rows["chip-cold-plate"]["state"] == "EXPIRED"
    assert rows["chip-cold-plate"]["days_left"] == 0
    assert rows["electric-motor-magnetics"]["state"] == "NO_EXAM_GRADED"
    text = exam_health.render(list(rows.values()))
    assert (
        text.index("chip-cold-plate")
        < text.index("f08-ribbed-bracket")
        < text.index("f02 ")
    )
    assert "GRADING HAS STOPPED" in text and "WARNING: replace it before day 90" in text


def test_the_active_exam_is_the_newest_key(tmp_path):
    now = 500 * DAY
    ledger = _ledger(
        tmp_path, keys=[("f02", "2.4", now - 80 * DAY), ("f02", "2.5", now - 3 * DAY)]
    )
    row = _by(exam_health.report(ledger, block=now))["f02"]
    assert (row["version"], row["age_days"], row["state"]) == ("2.5", 3, "OK")


def test_last_weekly_check_outcome_reason_and_date(tmp_path):
    now = 500 * DAY
    ledger = _ledger(
        tmp_path,
        keys=[("f02", "2.5", now - DAY)],
        checks=[
            ("f02", "2.5", "UNAVAILABLE", "standard_error_unavailable"),
            ("f02", "2.5", "ROTATE", "sealed_exceeds_fresh_beyond_margin_and_2se"),
        ],
    )
    row = _by(exam_health.report(ledger, block=now, backlog={"f02": 2}))["f02"]
    assert row["last_check"] == {
        "outcome": "ROTATE",
        "reason": "sealed_exceeds_fresh_beyond_margin_and_2se",
        "date": "2023-11-14",
    }
    assert row["backlog"] == 2
    text = exam_health.render([row])
    assert "ROTATE: replace the exam now" in text and "2023-11-14" in text
    assert "Held-back fresh sets on hand: 2." in text


def test_no_check_and_no_backlog_say_so(tmp_path):
    ledger = _ledger(tmp_path, keys=[("f02", "2.5", 0)])
    text = exam_health.render([_by(exam_health.report(ledger, block=DAY))["f02"]])
    assert "No weekly check has run yet." in text
    assert "Held-back fresh sets on hand: not recorded." in text


def test_an_empty_or_new_ledger_reads_without_error(tmp_path):
    empty = tmp_path / "new.sqlite"
    sqlite3.connect(empty).close()
    rows = exam_health.report(empty, block=DAY)
    assert {row["state"] for row in rows} == {"NO_EXAM_GRADED"}


def test_the_report_discloses_no_key_total_or_threshold(tmp_path):
    now = 500 * DAY
    ledger = _ledger(
        tmp_path,
        keys=[("f02", "2.5", now - DAY)],
        checks=[("f02", "2.5", "KEEP", "within_margin_and_2se")],
    )
    rows = exam_health.report(ledger, block=now)
    shown = json.dumps(rows) + exam_health.render(rows)
    for secret in (
        SECRET_KEY,
        "fresh-key-xyz",
        "0.8123",
        "0.7777",
        "0.07",
        "king-sub-77",
    ):
        assert secret not in shown, secret
    assert set(rows[0]) <= {"challenge", "backlog", "state"}
    for row in rows:
        if row.get("last_check"):
            assert set(row["last_check"]) == {"outcome", "reason", "date"}


def test_the_ledger_is_opened_read_only(tmp_path):
    ledger = _ledger(tmp_path, keys=[("f02", "2.5", 0)])
    before = ledger.read_bytes()
    exam_health.report(ledger, block=DAY)
    assert ledger.read_bytes() == before


def test_the_command_exits_nonzero_only_when_an_exam_has_expired(tmp_path, capsys):
    ledger = _ledger(tmp_path, keys=[("f02", "2.5", 0)])
    assert exam_health.main(["--ledger", str(ledger), "--block", str(10 * DAY)]) == 0
    assert exam_health.main(["--ledger", str(ledger), "--block", str(95 * DAY)]) == 1
    assert "GRADING HAS STOPPED" in capsys.readouterr().out


def test_nothing_imports_the_operator_report():
    root = Path(__file__).resolve().parents[2]
    pattern = re.compile(r"\bexam_health\b")
    importers = [
        str(path.relative_to(root))
        for folder in ("carbon", "scripts")
        for path in (root / folder).rglob("*.py")
        if path.name != "exam_health.py"
        and pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert importers == []
