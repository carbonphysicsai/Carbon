"""Closing the submissions still queued on a Challenge version a door leaves (owner decision #9, 8 Nov, Lead ledger:
"Yes, close them"; Validator-2B's recommendation).

At a version flip (Wed 11 Nov: Motor 1.5 -> 1.8, Cooling 1.6 -> 1.8, route-h (b), in place) the new root starts with a
clean queue, so a submission still queued on the old door is not carried. It is CLOSED, NOT GRADED, NOTHING CHARGED:

- `close_queued` runs on the OLD root once its receiver has STOPPED (the operator's runbook step, after the drain).
  Every submitted task of the old version's served contract that the grader never marked (`AutoGrader.pending`'s own
  rule) gets an auto-grade marker ``VERSION_CLOSED`` (code ``version_closed``). Nothing else is written there: no
  attempt row, no exam-cap slot (a slot is reserved only when a grade starts, `exam_cap.ExamCap.reserve`), no recipe
  copy row. A rollback to that root grades none of them (the marker stands) and answers v4 ``NOT_GRADED``.
- It also writes ``version-closed.json`` in the old root: the closed ids with their owners. The NEW door names that
  file in its configuration (``version_closed_files``); when the owner asks about one of its own closed submissions
  there, it answers the typed refusal ``version_closed`` (HTTP 410), never ``feedback_submission_unknown``. Any other
  hotkey asking gets the unknown answer, as for any id it does not own.

Re-running is idempotent: the list is rebuilt from the VERSION_CLOSED markers, and the file is written once (a re-run
whose list differs refuses). Counts are printed; ids and hotkeys stay in the operator's files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

STATE = "VERSION_CLOSED"
CODE = "version_closed"
SCHEMA = "carbon.receiver.version-closed.v1"
FILE = "version-closed.json"


class VersionCloseRefused(ValueError):
    """The closing step cannot run soundly on this root (no task is touched)."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _contract(challenge_id, version):
    from carbon.reconstruction.served_recipe_contract import registered

    try:
        return registered(challenge_id, version).digest
    except LookupError:
        raise VersionCloseRefused("version_has_no_served_contract") from None


def _marker_path(markers, submission_id):
    return markers / (submission_id + ".json")


def _write_marker(markers, submission_id):
    from .auto_grade import SCHEMA as MARKER_SCHEMA

    body = {
        "schema": MARKER_SCHEMA,
        "submission_id": submission_id,
        "state": STATE,
        "code": CODE,
        "entry_id": None,
    }
    fd = os.open(
        _marker_path(markers, submission_id),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(fd, "w") as handle:
        json.dump(body, handle, sort_keys=True)
        handle.write("\n")


def _closed(markers, submission_id):
    path = _marker_path(markers, submission_id)
    try:
        if path.is_symlink():
            return False
        body = json.loads(path.read_text())
    except (OSError, ValueError):
        return False
    return type(body) is dict and body.get("state") == STATE


def close_queued(root, *, challenge_id, version):
    """Close every never-graded task of ``challenge_id`` ``version`` on the STOPPED door root ``root``; returns the
    ``version-closed.json`` document (also written there, once)."""
    from .auto_grade import _TASK
    from .ledger import AttemptLedger

    root = Path(root)
    ledger_path = root / "attempts.sqlite3"
    markers = root / "auto-grade" / "markers"
    if not ledger_path.is_file() or not markers.is_dir() or markers.is_symlink():
        raise VersionCloseRefused("not_a_grading_door_root")
    contract = _contract(challenge_id, version)
    ledger = AttemptLedger(ledger_path)
    closed = []
    for submission_id in ledger.submitted_outcomes(contract):
        if not _TASK.fullmatch(submission_id):
            continue
        if not _marker_path(markers, submission_id).exists():
            _write_marker(markers, submission_id)
        if not _closed(markers, submission_id):
            continue  # the grader's own outcome stands
        owner = ledger.owned_outcome(contract, submission_id)
        closed.append({"submission_id": submission_id, "owner": owner})
    document = {
        "schema": SCHEMA,
        "challenge": {"id": challenge_id, "version": version},
        "contract_digest": contract,
        "code": CODE,
        "closed": closed,
    }
    path = root / FILE
    payload = _canonical(document) + b"\n"
    if path.exists():
        if path.is_symlink() or path.read_bytes() != payload:
            raise VersionCloseRefused("version_closed_file_differs")
    else:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
    return document


def load(paths, *, challenge_id, version):
    """The closed submissions of earlier versions a door was configured with: ``{submission_id: owner}``.

    Each file must be a `close_queued` document of THIS Challenge for a version other than the door's own; anything
    else refuses the start (a mistyped path never silently answers nothing)."""
    closed = {}
    for selected in paths or ():
        if type(selected) is not str or not Path(selected).is_absolute():
            raise ValueError("exact version-closed file path required")
        try:
            document = json.loads(Path(selected).read_bytes())
        except (OSError, ValueError):
            raise ValueError("version-closed file unreadable") from None
        if (
            type(document) is not dict
            or document.get("schema") != SCHEMA
            or document.get("code") != CODE
            or type(document.get("challenge")) is not dict
            or document["challenge"].get("id") != challenge_id
            or document["challenge"].get("version") == version
            or type(document.get("closed")) is not list
        ):
            raise ValueError("version-closed file is not an earlier version's")
        for row in document["closed"]:
            if (
                type(row) is not dict
                or set(row) != {"submission_id", "owner"}
                or type(row["submission_id"]) is not str
                or not (row["owner"] is None or type(row["owner"]) is str)
            ):
                raise ValueError("version-closed file row invalid")
            closed[row["submission_id"]] = row["owner"]
    return closed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, help="the STOPPED old door root")
    parser.add_argument("--challenge-id", required=True)
    parser.add_argument("--version", required=True, help="the version being closed")
    args = parser.parse_args(argv)
    try:
        document = close_queued(
            args.root, challenge_id=args.challenge_id, version=args.version
        )
    except VersionCloseRefused as refused:
        print(json.dumps({"refused": str(refused)}))
        return 2
    print(
        json.dumps(
            {
                "closed": len(document["closed"]),
                "file": FILE,
                "file_sha256": hashlib.sha256(_canonical(document) + b"\n").hexdigest(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
