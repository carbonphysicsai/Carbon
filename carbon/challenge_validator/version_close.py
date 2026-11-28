"""Closing the submissions still queued on a Challenge version a door leaves (owner decision #9, 8 Nov, Lead ledger:
"Yes, close them"; Validator-2B's recommendation).

At a version flip (Wed 11 Nov: Motor 1.5 -> 1.8, Cooling 1.6 -> 1.8, route-h (b), in place) the new root starts with a
clean queue, so a submission still queued on the old door is not carried. It is CLOSED, NOT GRADED, NOTHING CHARGED:

- `close_queued` runs on the OLD root once its receiver has STOPPED (the operator's runbook step, after the drain).
  Every submitted task of the old version's served contract that the grader never marked (`AutoGrader.pending`'s own
  rule) gets an auto-grade marker ``VERSION_CLOSED`` (code ``version_closed``). Nothing else is written there: no
  attempt row, no exam-cap slot (a slot is reserved only when a grade starts, `exam_cap.ExamCap.reserve`), no recipe
  copy row. A rollback to that root grades none of them (the marker stands) and answers v4 ``NOT_GRADED``. A task
  its owner WITHDREW while queued whose marker is not written yet is skipped: its own WITHDRAWN_BY_MINER marker follows.
- It also writes ``version-closed.json`` in the old root: the closed ids with their owners. The NEW door names that
  file in its configuration (``version_closed_files``); when the owner asks about one of its own closed submissions
  there, it answers the typed refusal ``version_closed`` (HTTP 410), never ``feedback_submission_unknown``. Any other
  hotkey asking gets the unknown answer, as for any id it does not own.
- When a submission-fee ledger is configured or armed on the host (`OWNER-SUBMISSION-FEE-01`, `B6`, `L1`), `close_queued`
  resolves the shared host ledger via `submission_fee.resolve_host_state_dir`, recovers any crashed old-door `RESERVED`
  rows first, and mints `VERSION_CLOSED` `RETRY_CREDIT`s idempotently, refusing (`fee_ledger_missing`) if an expected
  host fee ledger cannot be opened.

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
_LAST_MINTED_CREDITS = 0


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


def _withdrawn(root, ledger, contract, submission_id):
    """Whether its owner WITHDREW ``submission_id`` while it was queued (`LeanRecipeAdapter.withdraw`): the door's withdrawal
    row, or the owner's task store's durable cancellation id (read only), in case the door stopped before its row and marker
    were written. Such a task is never closed here: the withdrawal's own repair writes its WITHDRAWN_BY_MINER marker
    (`AutoGrader._settle_withdrawn`). Anything unreadable says no (the task is closed as before: not graded either way).
    """
    import hashlib
    import sqlite3

    from .lean_recipe import WITHDRAW_PREFIX

    if ledger.miner_withdrawal(contract, submission_id) is not None:
        return True
    owner = ledger.owned_outcome(contract, submission_id)
    if type(owner) is not str:
        return False
    store = (
        Path(root)
        / "owners"
        / hashlib.sha256(owner.encode()).hexdigest()
        / "tasks"
        / "direct-tasks.sqlite3"
    )
    if store.is_symlink() or not store.is_file():
        return False
    try:
        db = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
        try:
            row = db.execute(
                "SELECT cancellation FROM direct_tasks WHERE id=?", (submission_id,)
            ).fetchone()
        finally:
            db.close()
    except sqlite3.Error:
        return False
    return row is not None and row[0] == WITHDRAW_PREFIX + submission_id


def _discover_receiver_fee_hints(root: Path) -> tuple[str | None, int | None]:
    """Read optional `(submission_fee_state_dir, netuid)` from `receiver.json` if present."""
    for cand in (root / "receiver.json", root.parent / "receiver.json"):
        if cand.is_file() and not cand.is_symlink():
            try:
                cfg = json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if type(cfg) is dict:
                sdir = cfg.get("submission_fee_state_dir")
                net = cfg.get("netuid")
                if net is None and cfg.get("network") == "finney":
                    net = 116
                elif net is None and cfg.get("network") == "testnet":
                    net = 567
                return (
                    sdir if type(sdir) is str and sdir else None,
                    net if type(net) is int else None,
                )
    return None, None


def _resolve_version_close_ledgers(
    root: Path,
    *,
    fee_ledger_path: Path | str | None = None,
    fee_state_dir: Path | str | None = None,
    netuid: int | None = None,
) -> list[Path]:
    """Resolve host `FeeLedger` SQLite files via `resolve_host_state_dir` (`L1`),
    refusing (`VersionCloseRefused('fee_ledger_missing')`) if an explicit or armed
    fee state has no valid ledger file."""
    from .submission_fee import (
        ARMED_FLAG_NAME,
        FIXED_HOST_STATE_ROOT,
        POLICY_FILE_NAME,
        is_inside_repo,
        ledger_file_name,
        resolve_host_state_dir,
    )

    if fee_ledger_path is not None:
        target = Path(fee_ledger_path)
        if is_inside_repo(target) or target.is_symlink() or not target.is_file():
            raise VersionCloseRefused("fee_ledger_missing")
        return [target]

    cfg_dir, cfg_netuid = _discover_receiver_fee_hints(root)
    effective_dir = (
        fee_state_dir or cfg_dir or os.environ.get("CARBON_SUBMISSION_FEE_STATE_DIR")
    )
    effective_netuid = netuid if netuid is not None else cfg_netuid

    if effective_dir is not None:
        try:
            sdir = resolve_host_state_dir(
                netuid=effective_netuid or 116, configured_dir=effective_dir
            )
        except ValueError as exc:
            raise VersionCloseRefused("fee_ledger_missing") from exc
        if effective_netuid is not None:
            cand = sdir / ledger_file_name(effective_netuid)
            if cand.is_file() and not cand.is_symlink():
                return [cand]
            raise VersionCloseRefused("fee_ledger_missing")
        found = [
            p
            for p in sorted(sdir.glob("submission_fees_*.sqlite3"))
            if p.is_file() and not p.is_symlink() and not is_inside_repo(p)
        ]
        if not found:
            raise VersionCloseRefused("fee_ledger_missing")
        return found

    if effective_netuid is not None:
        sdir = resolve_host_state_dir(netuid=effective_netuid)
        cand = sdir / ledger_file_name(effective_netuid)
        armed = (sdir / ARMED_FLAG_NAME).exists() or (sdir / POLICY_FILE_NAME).exists()
        if cand.is_file() and not cand.is_symlink():
            return [cand]
        if armed:
            raise VersionCloseRefused("fee_ledger_missing")
        return []

    # Check fixed host root (`/var/lib/carbon/submission-fee-netuid-*`) when no netuid is given.
    found_all: list[Path] = []
    if FIXED_HOST_STATE_ROOT.is_dir():
        for sdir in sorted(FIXED_HOST_STATE_ROOT.glob("submission-fee-netuid-*")):
            armed = (sdir / ARMED_FLAG_NAME).exists()
            dbs = [
                p
                for p in sorted(sdir.glob("submission_fees_*.sqlite3"))
                if p.is_file() and not p.is_symlink() and not is_inside_repo(p)
            ]
            if armed and not dbs:
                raise VersionCloseRefused("fee_ledger_missing")
            found_all.extend(dbs)
    return found_all


def _recover_and_mint_shared_fee_credits(
    *,
    ledgers: list[Path],
    attempt_ledger,
    contract_digest: str,
    challenge_id: str,
    version: str,
    ledger_path: Path,
    closed: list[dict],
) -> list[str]:
    """Recover crashed old-door `RESERVED` rows, then mint `version_closed` credits (`B6`, `L1`)."""
    if not ledgers:
        return []
    from .submission_fee import FeeLedger, is_outcome_admitted_in_attempt_ledger

    door_id = f"{challenge_id}:{version}:{ledger_path}"
    closed_ids = [
        str(row["submission_id"]) for row in closed if row.get("submission_id")
    ]
    minted: list[str] = []
    for cand in ledgers:
        fee_ldg = FeeLedger(cand)
        fee_ldg.recover_door_reservations(
            door_id,
            lambda sub_id: is_outcome_admitted_in_attempt_ledger(
                attempt_ledger, contract_digest, sub_id
            ),
        )
        if closed_ids:
            minted.extend(fee_ldg.credit_version_closed(closed_ids))
    return minted


def close_queued(
    root,
    *,
    challenge_id,
    version,
    fee_ledger_path=None,
    fee_state_dir=None,
    netuid=None,
):
    """Close every never-graded task of ``challenge_id`` ``version`` on the STOPPED door root ``root``; returns the
    ``version-closed.json`` document (also written there, once) and mints any owed `RETRY_CREDIT`s in the shared host ledger.
    """
    global _LAST_MINTED_CREDITS
    from .auto_grade import _TASK
    from .ledger import AttemptLedger

    root = Path(root)
    ledger_path = root / "attempts.sqlite3"
    markers = root / "auto-grade" / "markers"
    if not ledger_path.is_file() or not markers.is_dir() or markers.is_symlink():
        raise VersionCloseRefused("not_a_grading_door_root")
    contract = _contract(challenge_id, version)
    # Validate fee ledger resolution BEFORE mutating markers so `fee_ledger_missing`
    # refuses cleanly without touching any task (`VersionCloseRefused` contract).
    fee_ledgers = _resolve_version_close_ledgers(
        root,
        fee_ledger_path=fee_ledger_path,
        fee_state_dir=fee_state_dir,
        netuid=netuid,
    )
    ledger = AttemptLedger(ledger_path)
    closed = []
    for submission_id in ledger.submitted_outcomes(contract):
        if not _TASK.fullmatch(submission_id):
            continue
        if not _marker_path(markers, submission_id).exists():
            if _withdrawn(root, ledger, contract, submission_id):
                continue  # withdrawn by its owner: its own marker, never VERSION_CLOSED
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
    minted = _recover_and_mint_shared_fee_credits(
        ledgers=fee_ledgers,
        attempt_ledger=ledger,
        contract_digest=contract,
        challenge_id=challenge_id,
        version=version,
        ledger_path=ledger_path,
        closed=closed,
    )
    _LAST_MINTED_CREDITS = len(minted)
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
    parser.add_argument(
        "--fee-ledger",
        default=None,
        help="optional shared host FeeLedger SQLite path",
    )
    parser.add_argument(
        "--fee-state-dir",
        default=None,
        help="optional host submission_fee_state_dir",
    )
    parser.add_argument(
        "--netuid",
        type=int,
        default=None,
        help="optional subnet netuid (e.g. 116 or 567)",
    )
    args = parser.parse_args(argv)
    try:
        document = close_queued(
            args.root,
            challenge_id=args.challenge_id,
            version=args.version,
            fee_ledger_path=args.fee_ledger,
            fee_state_dir=args.fee_state_dir,
            netuid=args.netuid,
        )
    except VersionCloseRefused as refused:
        print(json.dumps({"refused": str(refused)}))
        return 2
    print(
        json.dumps(
            {
                "closed": len(document["closed"]),
                "fee_credits_minted": _LAST_MINTED_CREDITS,
                "file": FILE,
                "file_sha256": hashlib.sha256(_canonical(document) + b"\n").hexdigest(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
