"""The weekly fresh-draw check's watchdog: overdue, failed run, failed unit; read-only, operator only."""

import sqlite3
import subprocess
from pathlib import Path

import pytest
from test_exam_health import NS, SECRET_KEY, _ledger

from carbon.challenge_validator import exam_watchdog as wd

DAY_NS = wd._DAY_NS
KEYS = [("motor", "1.1", 10), ("f02", "2.5", 10)]


def _alerts(ledger, now, unit=None):
    return {
        (a["challenge"], a["kind"]) for a in wd.alerts(ledger, now_ns=now, unit=unit)
    }


def test_a_recent_decision_for_every_active_exam_is_silent(tmp_path):
    ledger = _ledger(
        tmp_path,
        keys=KEYS,
        checks=[("motor", "1.1", "KEEP", "x"), ("f02", "2.5", "ROTATE", "y")],
    )
    assert wd.alerts(ledger, now_ns=NS + 7 * DAY_NS) == []
    assert wd.main(["--ledger", str(ledger), "--no-unit-check"], clock=lambda: NS) == 0


def test_an_exam_with_no_row_newer_than_eight_days_is_overdue(tmp_path):
    ledger = _ledger(
        tmp_path,
        keys=KEYS,
        checks=[("motor", "1.1", "KEEP", "x")],  # f02 has never been checked
    )
    assert _alerts(ledger, NS + 7 * DAY_NS) == {("f02", "weekly_check_overdue")}
    assert _alerts(ledger, NS + 9 * DAY_NS) == {
        ("motor", "weekly_check_overdue"),
        ("f02", "weekly_check_overdue"),
    }


def test_a_week_the_check_could_not_run_alerts_or_warns_by_reason(tmp_path, capsys):
    for reason in wd.RUN_MISSES:
        ledger = _ledger(
            tmp_path, keys=[KEYS[0]], checks=[("motor", "1.1", "UNAVAILABLE", reason)]
        )
        assert _alerts(ledger, NS) == {("motor", "weekly_check_failed")}
        severity = {a["severity"] for a in wd.alerts(ledger, now_ns=NS)}
        assert severity == {"WARN" if reason in wd.WARN_MISSES else "ALERT"}
        rc = wd.main(["--ledger", str(ledger), "--no-unit-check"], clock=lambda: NS)
        out = capsys.readouterr().out
        assert (rc, out.split()[0]) == (
            (0, "WARN") if reason in wd.WARN_MISSES else (1, "ALERT")
        )
        Path(ledger).unlink()
    assert wd.WARN_MISSES == ("no_incumbent", "fresh_draw_set_unavailable")
    ledger = _ledger(
        tmp_path,
        keys=[KEYS[0]],
        checks=[("motor", "1.1", "UNAVAILABLE", "total_unavailable")],
    )
    assert _alerts(ledger, NS) == set()  # a decision about the totals, not a run miss


def test_only_the_newest_row_counts_for_a_failed_run(tmp_path):
    ledger = _ledger(
        tmp_path,
        keys=[KEYS[0]],
        checks=[
            ("motor", "1.1", "UNAVAILABLE", "chain_unavailable"),
            ("motor", "1.1", "KEEP", "within_margin_and_2se"),
        ],
    )
    assert _alerts(ledger, NS) == set()


def test_the_weekly_service_result_is_read_and_anything_but_success_alerts(tmp_path):
    ledger = _ledger(tmp_path, keys=[KEYS[0]], checks=[("motor", "1.1", "KEEP", "x")])
    assert _alerts(ledger, NS, unit=lambda: "success") == set()
    assert _alerts(ledger, NS, unit=lambda: None) == set()  # unreadable is not an alert
    assert _alerts(ledger, NS, unit=lambda: "exit-code") == {
        (None, "weekly_unit_failed")
    }
    seen = []

    def fake(argv, **kw):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, "failed\n", "")

    assert wd.unit_result(run=fake) == "failed"
    assert seen[0][:3] == ["systemctl", "--user", "show"]
    assert seen[0][3].startswith("carbon-exam-fresh-draw")


def test_it_reads_the_ledger_read_only_and_prints_no_key_or_total(tmp_path, capsys):
    ledger = _ledger(
        tmp_path,
        keys=[KEYS[0]],
        checks=[("motor", "1.1", "UNAVAILABLE", "no_incumbent")],
    )
    before = Path(ledger).read_bytes()
    rc = wd.main(["--ledger", str(ledger), "--no-unit-check"], clock=lambda: NS)
    out = capsys.readouterr().out
    assert rc == 0 and "WARN motor: weekly_check_failed" in out
    assert SECRET_KEY not in out and "king-sub-77" not in out and "0.8123" not in out
    assert Path(ledger).read_bytes() == before
    with pytest.raises(
        sqlite3.OperationalError
    ):  # the report's connection cannot write
        db = sqlite3.connect(Path(ledger).resolve().as_uri() + "?mode=ro", uri=True)
        db.execute("DELETE FROM fresh_draw_log")


def test_nothing_imports_the_watchdog_and_it_schedules_nothing():
    import re

    root = Path(__file__).resolve().parents[2]
    text = (root / "carbon/challenge_validator/exam_watchdog.py").read_text()
    assert "OnCalendar" not in text and "[Timer]" not in text
    for path in (root / "carbon").rglob("*.py"):
        if path.name == "exam_watchdog.py":
            continue
        assert not re.search(r"exam_watchdog", path.read_text(encoding="utf-8")), path
