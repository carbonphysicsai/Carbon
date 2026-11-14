"""Which output failed a gate-failed grade, and why: the miner's own feedback (owner, 14 Nov: "yes tell them").

A grade that fails the in-range accuracy gate says which registered OUTPUT failed and ONE of two closed reasons:

- ``over_limit``: the output's accuracy statistic is over the registered bar on a hidden in-range class;
- ``invalid_answer``: a hidden in-range class holding that output got an invalid answer from the model. The gate is checked per hidden
  in-range class and per output, and ONE invalid answer fails the whole class (every output of that class).

Published, prospective, for every miner. NEVER shown: the p90 or any ratio, the class, a count, the cases, a threshold. Only the
registered output NAME (already public: it is in the exam's published interface) and the reason leave this module.

ONE entry per output: when the same output fails for different reasons in different hidden classes, ``invalid_answer`` takes precedence, so
the list never reveals how many hidden classes there are (V2C 14 Nov: two entries for one output would say there are at least two classes).
The failures are derived by an allow-list from the grade's custody accuracy record (the `pool_exam` measurement), at grade time, and
kept per submission in a table of their own beside the Ladder (`gate_failures_v1`), so no stored Ladder document changes shape and a rollback to
code without this module leaves the table unread. They are served only on the v6 feedback reply (`direct_intake`): older clients never ask for it.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3

REASONS = ("over_limit", "invalid_answer")
KEYS = ("output", "reason")
#: A registered output name: lower-case words with underscores or digits (a bound on what may be shown, not a policy value).
_OUTPUT = re.compile(r"[a-z][a-z0-9_]{0,63}")
#: A bound on how many outputs a reply may name.
MAX_OUTPUTS = 64
_SUBMISSION = re.compile(r"rtsk_[0-9a-f]{64}")
_EXAM = re.compile(r"sha256:[0-9a-f]{64}")

DDL = """
CREATE TABLE IF NOT EXISTS gate_failures_v1(
    submission_id TEXT NOT NULL,
    exam_key TEXT NOT NULL,
    failures TEXT NOT NULL,
    PRIMARY KEY(submission_id, exam_key)
);
"""


def _number(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def derive(accuracy):
    """The allow-listed ``[{"output", "reason"}, ...]`` (sorted, distinct) of a gate-failed grade, or None.

    ``accuracy`` is the custody accuracy record. A row counts only when its verdict is FAIL (an in-range class and output). The reason
    is ``invalid_answer`` when the row's class holds an invalid answer (``n_invalid`` > 0), else ``over_limit`` when the row has a
    numeric gate statistic and no exact-row case; a failing row that is neither (no value, or an exact-row case) is left out, never
    guessed. One entry per OUTPUT: an output that fails as an invalid answer in one class and over the limit in another is listed once, as
    ``invalid_answer``, so the list says nothing about how many classes there are. With no identifiable failing row the answer is None:
    nothing is claimed.
    """
    if type(accuracy) is not dict:
        return None
    rows = accuracy.get("rows")
    gate = accuracy.get("gate")
    statistic = gate.get("statistic") if type(gate) is dict else None
    if type(rows) is not list or type(statistic) is not str:
        return None
    found = {}
    for row in rows:
        if type(row) is not dict or row.get("verdict") != "FAIL":
            continue
        output = row.get("output")
        if type(output) is not str or not _OUTPUT.fullmatch(output):
            continue
        invalid, exact = row.get("n_invalid"), row.get("n_exact")
        if type(invalid) is int and not isinstance(invalid, bool) and invalid > 0:
            found[output] = (
                "invalid_answer"  # takes precedence over any other reason for the same output
            )
        elif (
            _number(row.get(statistic))
            and type(exact) is int
            and not isinstance(exact, bool)
            and exact == 0
        ):
            found.setdefault(output, "over_limit")
    if not found:
        return None
    return [{"output": o, "reason": r} for o, r in sorted(found.items())][:MAX_OUTPUTS]


def valid(failures):
    """Whether ``failures`` is exactly what `derive` emits (a closed shape): a non-empty list of ``{"output", "reason"}``,
    sorted by output with ONE entry per output, a registered-shaped output name and one of `REASONS`, nothing else.
    """
    if type(failures) is not list or not 1 <= len(failures) <= MAX_OUTPUTS:
        return False
    keys = []
    for item in failures:
        if (
            type(item) is not dict
            or set(item) != set(KEYS)
            or type(item["output"]) is not str
            or not _OUTPUT.fullmatch(item["output"])
            or item["reason"] not in REASONS
        ):
            return False
        keys.append((item["output"], item["reason"]))
    outputs = [output for output, _reason in keys]
    return outputs == sorted(set(outputs))


def _canonical(failures):
    return json.dumps(failures, sort_keys=True, separators=(",", ":"))


def ensure(ledger):
    """Create the table beside the Ladder's in the receiver's ledger file (a no-op when it exists)."""
    db = sqlite3.connect(ledger.path, isolation_level=None)
    try:
        db.executescript(DDL)
    finally:
        db.close()


def record(ledger, submission_id, exam_key, failures):
    """Store a gate-failed grade's ``failures`` once per (submission, exam); the same list again is a no-op, another refuses."""
    if (
        type(submission_id) is not str
        or not _SUBMISSION.fullmatch(submission_id)
        or type(exam_key) is not str
        or not _EXAM.fullmatch(exam_key)
        or not valid(failures)
    ):
        raise ValueError("gate_failures_invalid")
    ensure(ledger)
    body = _canonical(failures)
    with ledger._db() as db:
        row = db.execute(
            "SELECT failures FROM gate_failures_v1 WHERE submission_id=? AND exam_key=?",
            (submission_id, exam_key),
        ).fetchone()
        if row is None:
            db.execute(
                "INSERT INTO gate_failures_v1(submission_id, exam_key, failures) VALUES(?,?,?)",
                (submission_id, exam_key, body),
            )
        elif row[0] != body:
            raise ValueError("gate_failures_changed")


def read(ledger, submission_id, exam_key):
    """The stored failures of this submission on this exam, or None (not gate-failed, an older grade, no table yet)."""
    try:
        with ledger._db() as db:
            row = db.execute(
                "SELECT failures FROM gate_failures_v1 WHERE submission_id=? AND exam_key=?",
                (submission_id, exam_key),
            ).fetchone()
    except sqlite3.OperationalError:
        return None  # the table is created at the first gate-failed grade
    if row is None:
        return None
    found = json.loads(row[0])
    return found if valid(found) else None
