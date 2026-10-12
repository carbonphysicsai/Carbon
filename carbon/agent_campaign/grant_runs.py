"""One run count per grant, and one rolling weekly spend cap, across every controller root.

A controller counts the runs in its own root. A grant of N runs is therefore N per
root: stage A's Constructor grant (5 runs) ran a sixth from a new root. For a LIVE
controller (`CampaignController(..., shared_runs=True)`) this module keeps, outside the
repository:

* one ledger per grant id, and a launch is refused when the grant's `permitted_runs`
  entries are already claimed, whichever root claimed them;
* one host-wide spend ledger for the standing testnet testing budget
  (OWNER-TESTNET-WEEKLY-BUDGET-01, amended by OWNER-TEST-GRANT-01: USD 300 per rolling
  seven days, pods plus model charges, and USD 50 per run): a launch whose worst-case run cost would take the last seven days over the
  cap is refused. A run is reserved at its grant's worst-case run cost and later settled
  at its reported cost, so the window counts reservations until they settle.
* The cost basis is pod RESERVATION plus the provider-reported model charge. A pod's
  charge is usually unresolved at the provider (`pod_charge_unresolved`), and an
  unresolved pod stays counted at its full reservation: the settled cost a controller
  reports is `settled + pending`, where `pending` is exactly those reservations, and the
  ledger keeps `pending` beside it. Only a provider-reported charge or a zero-cost
  refusal lowers a run's count; the ledger holds no settled pod charge of its own.

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
* Refund: a run that failed as infrastructure before any pod was created may release its
  run SLOT (`settle(..., refund_reason=REFUND_FAILED_INFRA)`), and only the slot: the
  weekly window keeps its reported model charge and any pod reservation. A refund is
  written once per claim under both locks, with a reason code and the claim id; it is
  refused for a seeded claim, a run already settled, or a claim already refunded, and a
  refunded claim cannot be claimed again under the same key. The caller must prove the
  failure and the empty pod record (the controller refuses on anything it cannot read).
* Migration: the first claim from a root seeds the per-grant ledger with that root's
  existing runs (so they are never under-counted from then on), and so is their cost
  basis: each seeded run enters the rolling window at its own start time and at the
  controller's committed cost (settled where the store knows it, else the reservation).
  Runs in OTHER roots that predate the ledger are not known until each root claims or is
  seeded: `python -m carbon.agent_campaign.grant_runs seed --grant G.json --root DIR ...`
  (re-running it also imports the cost basis of a root counted by an earlier seed). A
  root whose store cannot be read, or holds a run whose cost cannot be read, refuses the
  seed (`grant_runs_unavailable`); it is never skipped. Spend from before a root's first
  run is not in any store, so it is not known to the window.

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
#: The one committed source of both figures: `.agent/decisions/2026-10-11-OWNER-TESTNET-WEEKLY-BUDGET-01.md`,
#: as amended 2026-10-12 by OWNER-TEST-GRANT-01 (#1167): "The figure is USD 300 per
#: rolling seven days" and "Per-run safety cap: USD 50". A test parses that record and
#: pins both constants to its text, so a figure here cannot drift from it.
CAP_DECISION = "OWNER-TESTNET-WEEKLY-BUDGET-01, amended by OWNER-TEST-GRANT-01 (#1167)"
CAP_RECORD = ".agent/decisions/2026-10-11-OWNER-TESTNET-WEEKLY-BUDGET-01.md"
WEEKLY_CAP_USD = Decimal(300)
#: A run whose worst-case reservation is above this is refused (fail closed); a larger
#: run needs its own owner record.
PER_RUN_CAP_USD = Decimal(50)
PER_RUN_LIMIT = "per_run_cap_exceeded"
WEEK_SECONDS = 7 * 24 * 3600
WEEKLY_FILE = "weekly-spend.jsonl"
NL = "\n"
#: The one reason a claim's run slot is refunded: the run failed as infrastructure
#: before any pod was created. The slot only: its cost stays in the weekly window.
REFUND_FAILED_INFRA = "failed_infra_before_any_pod"
REFUND_REASONS = (REFUND_FAILED_INFRA,)
BASIS = (
    "pod reservation plus provider-reported model charge; pod charges are unresolved "
    "at the provider and stay at their reservation"
)
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


def _read_all(stream):
    """`(active claims, refunded claims)` from a per-grant ledger. A refund line must
    follow its own claim and appear once; anything else is corrupt."""
    stream.seek(0)
    entries, refunded = {}, {}
    for number, line in enumerate(stream.read().decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if "refund" in entry:
                identifier = entry["refund"]
                if (
                    type(identifier) is not str
                    or not _ENTRY.fullmatch(identifier)
                    or identifier not in entries
                    or entry.get("reason") not in REFUND_REASONS
                ):
                    raise ValueError
                refunded[identifier] = entries.pop(identifier)
                continue
            identifier = entry["entry"]
        except (ValueError, KeyError, TypeError, AttributeError):
            raise SharedRunsError(
                UNAVAILABLE, f"ledger line {number} is corrupt"
            ) from None
        if type(identifier) is not str or not _ENTRY.fullmatch(identifier):
            raise SharedRunsError(UNAVAILABLE, f"ledger line {number} is corrupt")
        if identifier in refunded:
            raise SharedRunsError(UNAVAILABLE, f"ledger line {number} is corrupt")
        entries[identifier] = entry
    return entries, refunded


def _read(stream):
    """The active claims (a refunded claim no longer holds a run slot)."""
    return _read_all(stream)[0]


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
                runs[identifier]["pending"] = _cost(row.get("pending_usd", 0))
                if runs[identifier]["pending"] > cost:
                    raise ValueError
                runs[identifier]["settled"] = True
                continue
            identifier = row["entry"]
            if not _ENTRY.fullmatch(identifier):
                raise ValueError
            runs[identifier] = {
                "at": float(row["at"]),
                "cost": _cost(row["cost_usd"]),
                "grant": str(row["grant"]),
                "pending": Decimal(0),
                "settled": False,
                "seeded": row.get("seeded") is True,
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


def run_cost(open_phase, reserved, settled, usage_known):
    """A controller run's committed cost on the ledger's basis. A closed run whose usage
    is known counts at its settled amount (settled plus pending, so an unresolved pod
    stays at its reservation); an open run counts at the larger of that and its
    reservation; a run whose settled amount is missing or not known counts at its
    reservation. Anything unreadable raises."""
    reserved = _cost(reserved)
    if settled is None or not usage_known:
        return reserved
    settled = _cost(settled)
    return max(settled, reserved) if open_phase else settled


def run_start(text):
    """A run's `started_at` (UTC, whole seconds) as epoch seconds, or `SharedRunsError`."""
    import datetime

    try:
        if not text.endswith("Z"):
            raise ValueError
        moment = datetime.datetime.strptime(text[:-1] + "+0000", "%Y-%m-%dT%H:%M:%S%z")
    except (ValueError, AttributeError):
        raise SharedRunsError(UNAVAILABLE, "a run start time cannot be read") from None
    return moment.timestamp()


def _weekly_line(identifier, grant_id, at, cost):
    return (
        json.dumps(
            {
                "entry": identifier,
                "grant": grant_id,
                "at": at,
                "cost_usd": str(cost),
                "seeded": True,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


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
    seed_runs=(),
):
    """Claim one run of `grant` for launch `key` in the store `store_id`: against the
    grant's run cap and the host-wide rolling weekly spend cap. Idempotent for a key
    already claimed. `seed_keys` are this store's existing launch keys, added first so
    they are counted; `seed_runs` are `(key, started_at epoch, cost)` for runs whose
    cost basis also enters the rolling window at their own start time. Raises
    `SharedRunsError`; returns the grant's count after."""
    if type(store_id) is not str or not _STORE_ID.fullmatch(store_id):
        raise SharedRunsError(UNAVAILABLE, "store id is invalid")
    if grant.currency != "USD":
        raise SharedRunsError(UNAVAILABLE, "the grant's currency is not USD")
    cost = _cost(grant.worst_case_run_cost)
    if cost > PER_RUN_CAP_USD:
        raise SharedRunsError(
            PER_RUN_LIMIT,
            f"worst case {cost} is above the {PER_RUN_CAP_USD} USD per-run cap",
        )
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
            entries, refunded = _read_all(stream)
            spent = _read_weekly(weekly)
            stream.seek(0, os.SEEK_END)
            # This store's existing runs are facts: record them before deciding.
            for seed in seed_keys:
                identifier = entry_id(store_id, seed)
                if identifier not in entries and identifier not in refunded:
                    entries[identifier] = {}
                    stream.write(_line(store_id, seed, True))
            stream.flush()
            os.fsync(stream.fileno())
            _seed_costs(weekly, spent, grant.grant_id, store_id, seed_runs)
            identifier = entry_id(store_id, key)
            if identifier in refunded:
                raise SharedRunsError(
                    UNAVAILABLE, "this claim was refunded; launch under a new key"
                )
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


def settle(grant, store_id, key, cost_usd, repository=REPOSITORY, *, pending_usd=0):
    """Record a run's reported cost in place of its worst-case reservation. `cost_usd`
    is the total (settled plus pending) and `pending_usd` the part that is still a pod
    reservation because the provider reported no charge; it is part of the cost, never
    taken off it. An unknown or unreadable cost raises (the reservation stays, which is
    the conservative side)."""
    cost = _cost(cost_usd)
    pending = _cost(pending_usd)
    if pending > cost:
        raise SharedRunsError(UNAVAILABLE, "pending exceeds the reported cost")
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
                        {
                            "settle": identifier,
                            "cost_usd": str(cost),
                            "pending_usd": str(pending),
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
    return True


def refund(
    grant,
    store_id,
    key,
    cost_usd,
    repository=REPOSITORY,
    *,
    pending_usd=0,
    reason=REFUND_FAILED_INFRA,
    clock=time.time,
):
    """Release one claim's run SLOT and settle its weekly cost, together, under both
    locks. Only the slot is released: `cost_usd` (the reported model charge plus any pod
    reservation, `pending_usd` of it) stays in the rolling window. The caller proves the
    run failed as infrastructure before any pod was created; this function refuses what
    it can check itself: an unknown reason, a claim that is missing, seeded (a run that
    predates the ledger) or already refunded, and a run already settled. A refusal
    raises `SharedRunsError`; the slot then stays consumed (the conservative side).
    Returns the number of active claims after."""
    if reason not in REFUND_REASONS:
        raise SharedRunsError(UNAVAILABLE, "unknown refund reason")
    cost = _cost(cost_usd)
    pending = _cost(pending_usd)
    if pending > cost:
        raise SharedRunsError(UNAVAILABLE, "pending exceeds the reported cost")
    if grant.currency != "USD":
        raise SharedRunsError(UNAVAILABLE, "the grant's currency is not USD")
    path = _file(grant.grant_id, repository)
    weekly_path = ledger_dir(repository) / WEEKLY_FILE
    identifier = entry_id(store_id, key)
    with (
        os.fdopen(_open(path), "r+b") as stream,
        os.fdopen(_open(weekly_path), "r+b") as weekly,
    ):
        try:
            fcntl.flock(stream, fcntl.LOCK_EX)
            fcntl.flock(weekly, fcntl.LOCK_EX)
            entries, refunded = _read_all(stream)
            runs = _read_weekly(weekly)
            if identifier in refunded:
                raise SharedRunsError(UNAVAILABLE, "refund refused: already refunded")
            claim_line = entries.get(identifier)
            if claim_line is None or claim_line.get("seeded") is not False:
                raise SharedRunsError(
                    UNAVAILABLE, "refund refused: not a launch claimed here"
                )
            row = runs.get(identifier)
            if row is None or row["settled"] or row["seeded"]:
                raise SharedRunsError(
                    UNAVAILABLE, "refund refused: the run is already settled"
                )
            weekly.seek(0, os.SEEK_END)
            weekly.write(
                (
                    json.dumps(
                        {
                            "settle": identifier,
                            "cost_usd": str(cost),
                            "pending_usd": str(pending),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + NL
                ).encode()
            )
            weekly.flush()
            os.fsync(weekly.fileno())
            stream.seek(0, os.SEEK_END)
            stream.write(
                (
                    json.dumps(
                        {
                            "refund": identifier,
                            "reason": reason,
                            "store": store_id,
                            "at": float(clock()),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + NL
                ).encode()
            )
            stream.flush()
            os.fsync(stream.fileno())
        except SharedRunsError:
            raise
        except OSError as error:
            raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    return len(entries) - 1


def _seed_costs(weekly, spent, grant_id, store_id, seed_runs):
    """Enter each seeded run's cost basis in the rolling window at its own start time,
    once (a run already in the window is left alone). Writes under the weekly lock the
    caller holds; a cost or time that cannot be read refuses."""
    wrote = 0
    weekly.seek(0, os.SEEK_END)
    for key, at, cost in seed_runs:
        identifier = entry_id(store_id, key)
        if identifier in spent:
            continue
        cost = _cost(cost)
        at = float(at)
        weekly.write(_weekly_line(identifier, grant_id, at, cost))
        spent[identifier] = {
            "at": at,
            "cost": cost,
            "grant": grant_id,
            "pending": Decimal(0),
            "settled": True,
            "seeded": True,
        }
        wrote += 1
    weekly.flush()
    os.fsync(weekly.fileno())
    return wrote


def weekly_report(repository=REPOSITORY, *, clock=time.time, weekly_cap=WEEKLY_CAP_USD):
    """The rolling seven days from the ledger: spent, cap, headroom, runs, per grant,
    and how much of the spend is a pod reservation the provider never settled, a worst
    case not yet settled, or seeded from an earlier root. Totals only; fails closed if
    the ledger is unreadable."""
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

    def total(rows):
        return str(sum((r["cost"] for r in rows), Decimal(0)).quantize(cents))

    return {
        "window_days": 7,
        "basis": BASIS,
        "spent_usd": str(spent.quantize(cents)),
        "cap_usd": str(Decimal(weekly_cap).quantize(cents)),
        "per_run_cap_usd": str(PER_RUN_CAP_USD.quantize(cents)),
        "cap_decision": CAP_DECISION,
        "remaining_usd": str(max(Decimal(0), weekly_cap - spent).quantize(cents)),
        "runs": len(inside),
        "pod_reservation_unresolved_usd": str(
            sum((r["pending"] for r in inside.values()), Decimal(0)).quantize(cents)
        ),
        "worst_case_not_yet_settled_usd": total(
            r for r in inside.values() if not r["settled"]
        ),
        "seeded_runs": sum(r["seeded"] for r in inside.values()),
        "seeded_usd": total(r for r in inside.values() if r["seeded"]),
        "by_grant": {k: str(v.quantize(cents)) for k, v in sorted(by_grant.items())},
    }


def weekly_line(report):
    """One line for the Test Lead: the usage, the basis and the headroom."""
    return (
        f"Testnet testing budget, rolling {report['window_days']} days: "
        f"USD {report['spent_usd']} of {report['cap_usd']} used, "
        f"USD {report['remaining_usd']} headroom, {report['runs']} runs "
        f"({report['seeded_runs']} seeded from earlier roots). "
        f"Cap: USD {report['cap_usd']} per rolling 7 days and USD "
        f"{report['per_run_cap_usd']} per run ({report['cap_decision']}). "
        f"Basis: {report['basis']}."
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


def read_store(root):
    """`(store id, [(key, started_at epoch, cost)])` from a controller root, read-only.
    The cost is the controller's committed cost (`run_cost`). A root whose store cannot
    be read, or a run whose cost or time cannot be read, raises `SharedRunsError`: the
    root is refused, never skipped."""
    from .controller import OPEN, STORE_ID_FILE

    root = Path(root)
    try:
        store_id = (root / STORE_ID_FILE).read_text().strip()
    except OSError:
        raise SharedRunsError(UNAVAILABLE, "no store id in the root") from None
    if not _STORE_ID.fullmatch(store_id):
        raise SharedRunsError(UNAVAILABLE, "store id is invalid")
    database = root / "campaign.sqlite3"
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            rows = connection.execute(
                "SELECT key, phase, reserved, settled, usage_known, started_at "
                "FROM runs ORDER BY started_at, key"
            ).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    open_phases = {phase.value for phase in OPEN}
    runs = [
        (
            key,
            run_start(started),
            run_cost(phase in open_phases, reserved, settled, usage_known),
        )
        for key, phase, reserved, settled, usage_known, started in rows
    ]
    return store_id, runs


def seed_root(grant, root, repository=REPOSITORY):
    """Count every run an existing controller root already holds, and enter each run's
    cost basis in the rolling window at its own start time. Read-only on the store.
    Returns the ledger count after seeding."""
    store_id, runs = read_store(root)
    if not runs:
        return count(grant.grant_id, repository)
    return claim_seeds(grant, store_id, [r[0] for r in runs], repository, runs=runs)


def claim_seeds(grant, store_id, keys, repository=REPOSITORY, runs=()):
    """Seed `keys` (no new launch) and the cost basis of `runs` (`(key, started_at,
    cost)`) into the rolling window. Re-seeding a counted root imports any cost basis
    it lacks."""
    path = _file(grant.grant_id, repository)
    weekly_path = ledger_dir(repository) / WEEKLY_FILE
    with (
        os.fdopen(_open(path), "r+b") as stream,
        os.fdopen(_open(weekly_path), "r+b") as weekly,
    ):
        try:
            fcntl.flock(stream, fcntl.LOCK_EX)
            fcntl.flock(weekly, fcntl.LOCK_EX)
            entries, refunded = _read_all(stream)
            spent = _read_weekly(weekly)
            stream.seek(0, os.SEEK_END)
            for key in keys:
                identifier = entry_id(store_id, key)
                if identifier not in entries and identifier not in refunded:
                    entries[identifier] = {}
                    stream.write(_line(store_id, key, True))
            stream.flush()
            os.fsync(stream.fileno())
            _seed_costs(weekly, spent, grant.grant_id, store_id, runs)
        except SharedRunsError:
            raise
        except OSError as error:
            raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    return len(entries)


# --- pod jobs (CLOUD-FIRST-COMPUTE-01, build item 2) ---------------------------------
#
# The shared pod launcher's runs (Data Collection's `pod_jobs`) are claimed here under
# the standing weekly test grant (OWNER-TEST-GRANT-01), with no per-run owner ask: each
# job's cost cap is its worst case, at most the USD 50 per-run cap; all of them count in
# the same rolling-week ledger; and they may not use the reserves held for named runs.

#: The ledger the pod jobs share. The weekly spend cap is their limit, not a run count.
POD_JOB_GRANT_ID = "OWNER-TEST-GRANT-01:pod-jobs"
POD_JOB_STORE = hashlib.sha256(b"carbon.grant-runs.pod-jobs.v1").hexdigest()[:32]
POD_JOB_RUNS = 10**9
#: Weekly budget held back from pod jobs for named runs (CLOUD-FIRST-COMPUTE-01): the
#: sealed confirmation run's USD 40. Released by removing its entry, in a reviewed
#: change, once that run has settled.
HELD_RESERVES = {"OWNER-SCORE-PROOF-CONFIRM-02-GRANT": Decimal(40)}


class PodJobGrant:
    """A pod job's grant: OWNER-TEST-GRANT-01, worst case = the job's cost cap."""

    grant_id = POD_JOB_GRANT_ID
    currency = "USD"
    permitted_runs = POD_JOB_RUNS

    def __init__(self, cost_cap_usd):
        cost = _cost(cost_cap_usd)
        if cost <= 0:
            raise SharedRunsError(UNAVAILABLE, "a pod job needs a positive cost cap")
        if cost > PER_RUN_CAP_USD:
            raise SharedRunsError(
                PER_RUN_LIMIT,
                f"cost cap {cost} is above the {PER_RUN_CAP_USD} USD per-run cap",
            )
        self.worst_case_run_cost = cost


def pod_job_weekly_cap(reserves=None):
    """The weekly cap a pod job sees: the standing cap less the held reserves."""
    held = HELD_RESERVES if reserves is None else reserves
    return WEEKLY_CAP_USD - sum((_cost(v) for v in held.values()), Decimal(0))


def claim_pod_job(
    job_id, cost_cap_usd, repository=REPOSITORY, *, clock=time.time, reserves=None
):
    """Claim one pod job before any provider call: refused above the per-run cap, or
    when its cost cap would take the rolling week past the cap less the held reserves.
    Idempotent for a job id already claimed. Returns the job's grant."""
    if type(job_id) is not str or not _SAFE.fullmatch(job_id):
        raise SharedRunsError(UNAVAILABLE, "a pod job id is 1-128 of [A-Za-z0-9._:-]")
    grant = PodJobGrant(cost_cap_usd)
    claim(
        grant,
        POD_JOB_STORE,
        job_id,
        repository=repository,
        clock=clock,
        weekly_cap=pod_job_weekly_cap(reserves),
    )
    return grant


def settle_pod_job(job_id, cost_usd, repository=REPOSITORY, *, pending_usd=0):
    """Settle a pod job after teardown: its reported cost (settled plus any pod
    reservation still unresolved, `pending_usd`) replaces its cost cap."""
    return settle(
        None, POD_JOB_STORE, job_id, cost_usd, repository, pending_usd=pending_usd
    )


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
