"""One run count per grant, and one rolling weekly spend cap, across every controller root.

A controller counts the runs in its own root. A grant of N runs is therefore N per
root: stage A's Constructor grant (5 runs) ran a sixth from a new root. For a LIVE
controller (`CampaignController(..., shared_runs=True)`) this module keeps, outside the
repository:

* one ledger per grant id, and a launch is refused when the grant's `permitted_runs`
  entries are already claimed, whichever root claimed them;
* one host-wide spend ledger for the standing testnet testing budget
  (OWNER-TESTNET-WEEKLY-BUDGET-01: USD 150 per rolling seven days, pods plus model
  charges): a launch whose worst-case run cost would take the last seven days over the
  cap is refused. A run is reserved at its grant's worst-case run cost and later settled
  at its reported cost, so the window counts reservations until they settle.

Both are enforced together under both locks, so a launch the weekly cap refuses never
takes a run slot.

* Host-level and outside the repository: `CARBON_GRANT_RUNS_DIR`, else
  `~/.local/state/carbon/grant-runs`. A directory inside the repository is refused.
  Never committed.
* Ids, digests, timestamps and cost totals per run only: no balance, account or key.
* Locked: an exclusive `flock` covers read, check and append, so two concurrent claims
  cannot both take the last slot or the last of the budget.
* Fail closed: an unusable directory, an unreadable or corrupt ledger, a grant id that
  cannot name a file, a currency that is not USD, or a cost that cannot be read refuses
  the launch (`grant_runs_unavailable`). There is no fallback to the per-root count alone.
* Migration: the first claim from a root seeds the per-grant ledger with that root's
  existing runs (so they are never under-counted from then on). Runs in OTHER roots that
  predate the ledger are not known until each root claims or is seeded:
  `python -m carbon.agent_campaign.grant_runs seed --grant G.json --root DIR ...`. The
  weekly window starts with this ledger: spend before it is not known to it.

Not covered here, and still the owner's: server runs (CCX63), mainnet, anything over the
cap. Dry runs, prelive and tests build controllers without `shared_runs`, so they never
consume a real grant's runs or the weekly budget.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
ENV = "CARBON_GRANT_RUNS_DIR"
DEFAULT = Path("~/.local/state/carbon/grant-runs")
LIMIT = "run_limit_reached"
WEEKLY_LIMIT = "weekly_budget_reached"
UNAVAILABLE = "grant_runs_unavailable"
#: OWNER-TESTNET-WEEKLY-BUDGET-01: one hundred fifty US dollars per rolling seven days.
WEEKLY_CAP_USD = Decimal(150)
WEEK_SECONDS = 7 * 24 * 3600
WEEKLY_FILE = "weekly-spend.jsonl"
_SAFE = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_STORE_ID = re.compile(r"[0-9a-f]{32}")
_ENTRY = re.compile(r"[0-9a-f]{64}")


class SharedRunsError(Exception):
    """A launch the shared ledger refuses; `code` is `run_limit_reached`,
    `weekly_budget_reached` or `grant_runs_unavailable`."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def ledger_dir(repository=REPOSITORY):
    """The host-level directory, created owner-only, or `SharedRunsError`."""
    configured = os.environ.get(ENV)
    base = Path(configured) if configured else DEFAULT.expanduser()
    if not base.is_absolute():
        raise SharedRunsError(UNAVAILABLE, "ledger directory is not absolute")
    base = Path(os.path.abspath(base))
    root = Path(repository).resolve()
    if base == root or root in base.parents:
        raise SharedRunsError(UNAVAILABLE, "ledger directory is inside the repository")
    try:
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        if base.is_symlink() or not base.is_dir():
            raise SharedRunsError(UNAVAILABLE, "ledger directory is not a directory")
        if not os.access(base, os.R_OK | os.W_OK | os.X_OK):
            raise SharedRunsError(UNAVAILABLE, "ledger directory is not accessible")
    except OSError as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    return base


def _file(grant_id, repository):
    if type(grant_id) is not str or not _SAFE.fullmatch(grant_id):
        raise SharedRunsError(UNAVAILABLE, "grant id cannot name a ledger")
    tag = hashlib.sha256(grant_id.encode()).hexdigest()[:12]
    safe = grant_id.replace(":", "_")
    return ledger_dir(repository) / f"{safe}.{tag}.jsonl"


def entry_id(store_id, key):
    return hashlib.sha256(f"{store_id}\0{key}".encode()).hexdigest()


def _read(stream):
    stream.seek(0)
    entries = {}
    for number, line in enumerate(stream.read().decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            identifier = entry["entry"]
        except (ValueError, KeyError, TypeError):
            raise SharedRunsError(
                UNAVAILABLE, f"ledger line {number} is corrupt"
            ) from None
        if type(identifier) is not str or not _ENTRY.fullmatch(identifier):
            raise SharedRunsError(UNAVAILABLE, f"ledger line {number} is corrupt")
        entries[identifier] = entry
    return entries


def _line(store_id, key, seeded):
    return (
        json.dumps(
            {"entry": entry_id(store_id, key), "store": store_id, "seeded": seeded},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _cost(value):
    """A non-negative finite cost, or `SharedRunsError`: an unknown cost refuses."""
    try:
        cost = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise SharedRunsError(UNAVAILABLE, "a cost cannot be read") from None
    if not cost.is_finite() or cost < 0:
        raise SharedRunsError(UNAVAILABLE, "a cost cannot be read")
    return cost


def _read_weekly(stream):
    """`{entry id: {"at", "cost", "grant"}}` with each run's latest settled cost."""
    stream.seek(0)
    runs = {}
    for number, line in enumerate(stream.read().decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if "settle" in row:
                identifier = row["settle"]
                cost = _cost(row["cost_usd"])
                if identifier not in runs:
                    raise ValueError
                runs[identifier]["cost"] = cost
                continue
            identifier = row["entry"]
            if not _ENTRY.fullmatch(identifier):
                raise ValueError
            runs[identifier] = {
                "at": float(row["at"]),
                "cost": _cost(row["cost_usd"]),
                "grant": str(row["grant"]),
            }
        except SharedRunsError:
            raise
        except (ValueError, KeyError, TypeError):
            raise SharedRunsError(
                UNAVAILABLE, f"weekly line {number} is corrupt"
            ) from None
    return runs


def _window(runs, now):
    return {k: v for k, v in runs.items() if v["at"] > now - WEEK_SECONDS}


def _open(path):
    try:
        return os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None


def claim(
    grant,
    store_id,
    key,
    seed_keys=(),
    repository=REPOSITORY,
    *,
    clock=time.time,
    weekly_cap=WEEKLY_CAP_USD,
):
    """Claim one run of `grant` for launch `key` in the store `store_id`: against the
    grant's run cap and the host-wide rolling weekly spend cap. Idempotent for a key
    already claimed. `seed_keys` are this store's existing launch keys, added first so
    they are counted. Raises `SharedRunsError`; returns the grant's count after."""
    if type(store_id) is not str or not _STORE_ID.fullmatch(store_id):
        raise SharedRunsError(UNAVAILABLE, "store id is invalid")
    if grant.currency != "USD":
        raise SharedRunsError(UNAVAILABLE, "the grant's currency is not USD")
    cost = _cost(grant.worst_case_run_cost)
    path = _file(grant.grant_id, repository)
    weekly_path = ledger_dir(repository) / WEEKLY_FILE
    now = float(clock())
    with (
        os.fdopen(_open(path), "r+b") as stream,
        os.fdopen(_open(weekly_path), "r+b") as weekly,
    ):
        try:
            fcntl.flock(stream, fcntl.LOCK_EX)
            fcntl.flock(weekly, fcntl.LOCK_EX)
            entries = _read(stream)
            spent = _read_weekly(weekly)
            stream.seek(0, os.SEEK_END)
            # This store's existing runs are facts: record them before deciding.
            for seed in seed_keys:
                identifier = entry_id(store_id, seed)
                if identifier not in entries:
                    entries[identifier] = {}
                    stream.write(_line(store_id, seed, True))
            stream.flush()
            os.fsync(stream.fileno())
            identifier = entry_id(store_id, key)
            if identifier in entries:
                return len(entries)
            if len(entries) >= grant.permitted_runs:
                raise SharedRunsError(
                    LIMIT, f"{len(entries)} of {grant.permitted_runs} runs claimed"
                )
            used = sum((v["cost"] for v in _window(spent, now).values()), Decimal(0))
            if used + cost > weekly_cap:
                raise SharedRunsError(
                    WEEKLY_LIMIT, f"{used} of {weekly_cap} USD used in the last 7 days"
                )
            entries[identifier] = {}
            stream.write(_line(store_id, key, False))
            stream.flush()
            os.fsync(stream.fileno())
            weekly.seek(0, os.SEEK_END)
            weekly.write(
                (
                    json.dumps(
                        {
                            "entry": identifier,
                            "grant": grant.grant_id,
                            "at": now,
                            "cost_usd": str(cost),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
            weekly.flush()
            os.fsync(weekly.fileno())
        except SharedRunsError:
            raise
        except OSError as error:
            raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    return len(entries)


def settle(grant, store_id, key, cost_usd, repository=REPOSITORY):
    """Record a run's reported cost in place of its worst-case reservation. An unknown
    or unreadable cost raises (the reservation stays, which is the conservative side).
    """
    cost = _cost(cost_usd)
    weekly_path = ledger_dir(repository) / WEEKLY_FILE
    identifier = entry_id(store_id, key)
    with os.fdopen(_open(weekly_path), "r+b") as weekly:
        try:
            fcntl.flock(weekly, fcntl.LOCK_EX)
            runs = _read_weekly(weekly)
            if identifier not in runs:
                return False
            weekly.seek(0, os.SEEK_END)
            weekly.write(
                (
                    json.dumps(
                        {"settle": identifier, "cost_usd": str(cost)},
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode()
            )
            weekly.flush()
            os.fsync(weekly.fileno())
        except SharedRunsError:
            raise
        except OSError as error:
            raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    return True


def weekly_report(repository=REPOSITORY, *, clock=time.time, weekly_cap=WEEKLY_CAP_USD):
    """The rolling seven days from the ledger: spent, cap, remaining, runs, per grant.
    Totals only; fails closed if the ledger is unreadable."""
    path = ledger_dir(repository) / WEEKLY_FILE
    now = float(clock())
    if not path.exists():
        runs = {}
    else:
        try:
            with open(path, "rb") as stream:
                fcntl.flock(stream, fcntl.LOCK_SH)
                runs = _read_weekly(stream)
        except OSError as error:
            raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    inside = _window(runs, now)
    by_grant = {}
    for row in inside.values():
        by_grant[row["grant"]] = by_grant.get(row["grant"], Decimal(0)) + row["cost"]
    spent = sum(by_grant.values(), Decimal(0))
    cents = Decimal("0.01")
    return {
        "window_days": 7,
        "spent_usd": str(spent.quantize(cents)),
        "cap_usd": str(Decimal(weekly_cap).quantize(cents)),
        "remaining_usd": str(max(Decimal(0), weekly_cap - spent).quantize(cents)),
        "runs": len(inside),
        "by_grant": {k: str(v.quantize(cents)) for k, v in sorted(by_grant.items())},
    }


def weekly_line(report):
    """One line for the Test Lead."""
    return (
        f"Testnet testing budget, rolling {report['window_days']} days: "
        f"USD {report['spent_usd']} of {report['cap_usd']} used, "
        f"USD {report['remaining_usd']} remaining, {report['runs']} runs."
    )


def count(grant_id, repository=REPOSITORY):
    """Runs claimed against `grant_id` on this host (fails closed if unreadable)."""
    path = _file(grant_id, repository)
    if not path.exists():
        return 0
    try:
        with open(path, "rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            return len(_read(stream))
    except OSError as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None


def seed_root(grant, root, repository=REPOSITORY):
    """Count every run an existing controller root already holds, read-only from its
    store. Returns the ledger count after seeding."""
    from .controller import STORE_ID_FILE

    root = Path(root)
    try:
        store_id = (root / STORE_ID_FILE).read_text().strip()
    except OSError:
        raise SharedRunsError(UNAVAILABLE, "no store id in the root") from None
    database = root / "campaign.sqlite3"
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            keys = [
                r[0] for r in connection.execute("SELECT key FROM runs ORDER BY key")
            ]
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    if not keys:
        return count(grant.grant_id, repository)
    return claim_seeds(grant, store_id, keys, repository)


def claim_seeds(grant, store_id, keys, repository=REPOSITORY):
    """Seed `keys` (no new launch, no spend)."""
    path = _file(grant.grant_id, repository)
    with os.fdopen(_open(path), "r+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX)
            entries = _read(stream)
            stream.seek(0, os.SEEK_END)
            for key in keys:
                identifier = entry_id(store_id, key)
                if identifier not in entries:
                    entries[identifier] = {}
                    stream.write(_line(store_id, key, True))
            stream.flush()
            os.fsync(stream.fileno())
        except OSError as error:
            raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    return len(entries)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.agent_campaign.grant_runs")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="runs claimed against a grant id")
    status.add_argument("--grant-id", required=True)
    sub.add_parser("weekly", help="the rolling seven-day testnet budget, one line")
    seed = sub.add_parser("seed", help="count the runs existing controller roots hold")
    seed.add_argument(
        "--grant", required=True, type=Path, help="the grant document (JSON file)"
    )
    seed.add_argument("--root", action="append", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print(
                json.dumps({"grant_id": args.grant_id, "claimed": count(args.grant_id)})
            )
            return 0
        if args.command == "weekly":
            print(weekly_line(weekly_report()))
            return 0
        from .grant import SpendingGrant

        grant = SpendingGrant.from_document(json.loads(args.grant.read_text()))
        for root in args.root:
            total = seed_root(grant, root)
            print(
                json.dumps(
                    {"grant_id": grant.grant_id, "root": root.name, "claimed": total}
                )
            )
        return 0
    except SharedRunsError as error:
        print(error.code, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
