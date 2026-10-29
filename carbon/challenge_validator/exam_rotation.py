"""The weekly fresh-draw check and the overfit rotation signal (OWNER-CADENCE-AND-ROTATION-02).

An exam rotates at 90 days (``exam_cap``) or earlier on a measured overfit signal: once a
week the king is also graded on a fresh QA-passed draw from the backlog (his regrade on a
backlog pack, in a receiver started with that pack, never switching the active version).
If his sealed-exam total beats his fresh-draw total by more than the registered margin plus
two standard errors of the difference of the two totals, the exam rotates::

    sealed - fresh  >  margin + 2 * sqrt(SE_sealed^2 + SE_fresh^2)

Each SE is a case bootstrap of the king's total on that exam (200 resamples, seeded by the
exam key; see ``physical_dual_pack.bootstrap_total_se``). Where an adapter cannot measure a
resample the check is UNAVAILABLE for that Challenge and only the 90-day limit rotates it.
An SE is never typed by an operator: it is read from the evaluation's own sidecar.

Both totals, both SEs and the decision are logged in an operator-only table of the receiver's
attempt ledger; nothing here is reachable from a miner surface.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

from carbon.challenge_validator.exam_cap import DAY_BLOCKS

#: The king is checked on a fresh draw once a week.
FRESH_DRAW_PERIOD_BLOCKS = 7 * DAY_BLOCKS
SE_SIDECAR = "exam-total-se.json"
SE_SCHEMA = "carbon.exam.total-se.v1"
ROTATE, KEEP, UNAVAILABLE = "ROTATE", "KEEP", "UNAVAILABLE"

_DDL = """
CREATE TABLE IF NOT EXISTS fresh_draw_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    king_submission_id TEXT NOT NULL,
    sealed_key TEXT NOT NULL,
    fresh_key TEXT NOT NULL,
    block INTEGER NOT NULL,
    sealed_total REAL,
    fresh_total REAL,
    margin REAL,
    se_sealed REAL,
    se_fresh REAL,
    threshold REAL,
    outcome TEXT NOT NULL CHECK(outcome IN ('ROTATE','KEEP','UNAVAILABLE')),
    reason TEXT NOT NULL,
    at_ns INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS fresh_draw_log_sealed
    ON fresh_draw_log(challenge_id, sealed_key, block);
"""


def threshold(margin, se_sealed, se_fresh) -> float:
    """margin + 2 SE of the difference of two independent exams' totals."""
    return margin + 2.0 * math.sqrt(se_sealed**2 + se_fresh**2)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def decide(*, sealed_total, fresh_total, margin, se_sealed, se_fresh) -> dict:
    """ROTATE, KEEP, or UNAVAILABLE with the reason; nothing is ever defaulted."""

    def result(outcome, reason, limit=None):
        return {"outcome": outcome, "reason": reason, "threshold": limit}

    if not (_number(sealed_total) and _number(fresh_total)):
        return result(UNAVAILABLE, "total_unavailable")
    if not _number(margin):
        return result(UNAVAILABLE, "rebuild_noise_unregistered")
    if not (_number(se_sealed) and _number(se_fresh)):
        return result(UNAVAILABLE, "standard_error_unavailable")
    limit = threshold(margin, se_sealed, se_fresh)
    if sealed_total - fresh_total > limit:
        return result(ROTATE, "sealed_exceeds_fresh_beyond_margin_and_2se", limit)
    return result(KEEP, "within_margin_and_2se", limit)


class FreshDrawLog:
    """The operator-only record of the weekly check, in the receiver's attempt ledger."""

    def __init__(self, ledger, *, clock=None):
        self.ledger = ledger
        self.clock = clock or time.time_ns
        with ledger._db() as db:
            for statement in _DDL.strip().split(";"):
                if statement.strip():
                    db.execute(statement)

    def due(self, *, challenge_id: str, sealed_key: str, block: int) -> bool:
        """True when this sealed exam has had no fresh-draw check in the last week."""
        with self.ledger._db() as db:
            last = db.execute(
                "SELECT MAX(block) FROM fresh_draw_log WHERE challenge_id=? AND "
                "sealed_key=?",
                (challenge_id, sealed_key),
            ).fetchone()[0]
        return last is None or block - last >= FRESH_DRAW_PERIOD_BLOCKS

    def record(
        self,
        *,
        challenge_id,
        challenge_version,
        king,
        sealed_key,
        fresh_key,
        block,
        inputs,
        decision,
    ):
        with self.ledger._db() as db:
            db.execute(
                "INSERT INTO fresh_draw_log(challenge_id, challenge_version, "
                "king_submission_id, sealed_key, fresh_key, block, sealed_total, "
                "fresh_total, margin, se_sealed, se_fresh, threshold, outcome, reason, "
                "at_ns) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    challenge_id,
                    challenge_version,
                    king,
                    sealed_key,
                    fresh_key,
                    block,
                    inputs["sealed_total"],
                    inputs["fresh_total"],
                    inputs["margin"],
                    inputs["se_sealed"],
                    inputs["se_fresh"],
                    decision["threshold"],
                    decision["outcome"],
                    decision["reason"],
                    int(self.clock()),
                ),
            )

    def rows(self):
        with self.ledger._db() as db:
            cursor = db.execute("SELECT * FROM fresh_draw_log ORDER BY id")
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def read_se(sidecar_path) -> tuple:
    """(standard error, total) from an evaluation's SE sidecar; (None, total) if unmeasured."""
    document = json.loads(Path(sidecar_path).read_bytes())
    if type(document) is not dict or document.get("schema") != SE_SCHEMA:
        raise ValueError("exam total SE sidecar malformed")
    se = (
        document.get("standard_error") if document.get("status") == "MEASURED" else None
    )
    return (se if _number(se) else None), document.get("total")


def _total(body):
    model = (body or {}).get("evidence", {}).get("model_p")
    if (
        type(model) is not dict
        or model.get("score_status") != "SCORED_DEVELOPMENT_CANDIDATE"
    ):
        return None
    total = model.get("total_score")
    return total if _number(total) else None


def check_king(
    *,
    log,
    store,
    challenge_id,
    challenge_version,
    king,
    sealed,
    fresh,
    block,
    margin=None,
):
    """Compare the king's sealed and fresh-draw totals and log both.

    ``sealed`` and ``fresh`` are ``{"key", "pin", "se"}``: the evaluation key the king was
    graded on, the registered source-receipt pin it was filed under in the pool store, and
    the exam-total SE from that evaluation's sidecar (None when unmeasured). ``margin`` is the
    registered rebuild noise (koth_registry) unless given.
    """
    if margin is None:
        from carbon.challenge_validator import koth_registry

        noise = koth_registry.rebuild_noise(challenge_id)
        margin = None if noise is None else noise["value"]
    totals = {}
    for name, side in (("sealed", sealed), ("fresh", fresh)):
        body = store.private_evaluation_body(
            king, side["key"], registered_source_receipt_sha256=side["pin"]
        )
        totals[name] = _total(body)
    inputs = {
        "sealed_total": totals["sealed"],
        "fresh_total": totals["fresh"],
        "margin": margin,
        "se_sealed": sealed["se"],
        "se_fresh": fresh["se"],
    }
    decision = decide(**inputs)
    log.record(
        challenge_id=challenge_id,
        challenge_version=challenge_version,
        king=king,
        sealed_key=sealed["key"],
        fresh_key=fresh["key"],
        block=block,
        inputs=inputs,
        decision=decision,
    )
    if decision["outcome"] == ROTATE:
        # Loud on purpose: the operator rotates this Challenge's exam.
        print(
            json.dumps(
                {
                    "event": "exam_overfit_rotate",
                    "challenge": challenge_id,
                    "version": challenge_version,
                    "action": "rotate the exam key to the next backlog draw",
                }
            ),
            file=sys.stderr,
            flush=True,
        )
    return {**decision, **inputs}


#: A weekly run that could not read the chain has no block to log; the row carries this sentinel (and its
#: reason), which never counts as the last check's block.
NO_BLOCK = 0
UNIT_NAME = "carbon-exam-fresh-draw"


def _unavailable(log, check, *, reason, block, king="", sealed_key="", fresh_key=""):
    """Log a week the check could not run, so a miss is a row and never a silence."""
    inputs = {
        "sealed_total": None,
        "fresh_total": None,
        "margin": None,
        "se_sealed": None,
        "se_fresh": None,
    }
    log.record(
        challenge_id=check["challenge"],
        challenge_version=check["version"],
        king=king,
        sealed_key=sealed_key,
        fresh_key=fresh_key,
        block=block,
        inputs=inputs,
        decision={"outcome": UNAVAILABLE, "reason": reason, "threshold": None},
    )
    return {"outcome": UNAVAILABLE, "reason": reason, "challenge": check["challenge"]}


def run_weekly(config, *, head_reader=None, clock=None):
    """One weekly pass over the configured Challenges (operator only; the timer's command).

    ``config`` is ``{"checks": [{"ledger", "challenge", "version", "sealed_binding", "pool_store",
    "deployment", "fresh_binding"?}]}``. For each: the chain's finalized block is read through the validator
    deployment's own reader (never the ledger's last block, which goes stale when nothing is graded); when the
    check is due, the king is the pool store's incumbent (never an operator file) and the fresh binding is the
    king's regrade on a held-back fresh set. Every miss is a ``fresh_draw_log`` row with its reason:
    ``chain_unavailable``, ``no_incumbent``, ``fresh_draw_set_unavailable``. Returns one outcome per check.
    """
    from carbon.battery.pool_store import PoolStore
    from carbon.challenge_validator import answer_key
    from carbon.challenge_validator.bank_promotion import private_evaluation_key
    from carbon.challenge_validator.ledger import AttemptLedger

    head_reader = head_reader or answer_key.finalized_head
    outcomes = []
    for check in config["checks"]:
        log = FreshDrawLog(AttemptLedger(Path(check["ledger"])), clock=clock)
        sealed_path = Path(check["sealed_binding"])
        sealed_binding = json.loads(sealed_path.read_bytes())
        sealed_key = private_evaluation_key(sealed_binding)
        block = head_reader(check["deployment"])
        if type(block) is not int or block < 0:
            outcomes.append(
                _unavailable(
                    log,
                    check,
                    reason="chain_unavailable",
                    block=NO_BLOCK,
                    sealed_key=sealed_key,
                )
            )
            continue
        if not log.due(
            challenge_id=check["challenge"], sealed_key=sealed_key, block=block
        ):
            outcomes.append(
                {"outcome": "NOT_DUE", "challenge": check["challenge"], "block": block}
            )
            continue
        store = PoolStore(Path(check["pool_store"]))
        incumbent = store.incumbent()
        if incumbent is None:
            outcomes.append(
                _unavailable(
                    log,
                    check,
                    reason="no_incumbent",
                    block=block,
                    sealed_key=sealed_key,
                )
            )
            continue
        king = incumbent["model_id"]
        fresh_path = (
            Path(check["fresh_binding"]) if check.get("fresh_binding") else None
        )
        if fresh_path is None or not fresh_path.is_file():
            outcomes.append(
                _unavailable(
                    log,
                    check,
                    reason="fresh_draw_set_unavailable",
                    block=block,
                    king=king,
                    sealed_key=sealed_key,
                )
            )
            continue
        fresh_binding = json.loads(fresh_path.read_bytes())
        sides = []
        for binding, path in (
            (sealed_binding, sealed_path),
            (fresh_binding, fresh_path),
        ):
            sidecar = path.with_name(SE_SIDECAR)
            sides.append(
                {
                    "key": private_evaluation_key(binding),
                    "pin": binding["source_receipt_sha256"],
                    "se": read_se(sidecar)[0] if sidecar.is_file() else None,
                }
            )
        outcomes.append(
            {
                **check_king(
                    log=log,
                    store=store,
                    challenge_id=check["challenge"],
                    challenge_version=check["version"],
                    king=king,
                    sealed=sides[0],
                    fresh=sides[1],
                    block=block,
                ),
                "challenge": check["challenge"],
            }
        )
    return outcomes


def render_units(config_path, *, repository, python):
    """The weekly check as a ``systemd --user`` service and timer (weekly, Persistent): ``{filename: text}``.
    The service runs ``exam_rotation weekly`` from the repository checkout; it holds no key and reads only the
    validator's own ledger, pool store and deployment named in the config."""
    import shlex

    config_path, repository, python = (
        Path(config_path),
        Path(repository),
        Path(python),
    )
    for path in (config_path, repository, python):
        if not path.is_absolute() and not str(path).startswith("/"):
            raise ValueError("unit paths must be absolute")
    command = " ".join(
        shlex.quote(part)
        for part in (
            python.as_posix(),
            "-B",
            "-m",
            "carbon.challenge_validator.exam_rotation",
            "weekly",
            "--config",
            config_path.as_posix(),
        )
    )
    return {
        f"{UNIT_NAME}.service": (
            "[Unit]\nDescription=Carbon weekly fresh-draw check (operator only)\n\n"
            f"[Service]\nType=oneshot\nWorkingDirectory={repository.as_posix()}\n"
            "Environment=PYTHONDONTWRITEBYTECODE=1\n"
            f"ExecStart={command}\n"
        ),
        f"{UNIT_NAME}.timer": (
            "[Unit]\nDescription=Carbon weekly fresh-draw check, once a week\n\n"
            "[Timer]\nOnCalendar=weekly\nPersistent=true\n"
            f"Unit={UNIT_NAME}.service\n\n[Install]\nWantedBy=timers.target\n"
        ),
    }


def main(argv=None):
    import argparse

    from carbon.battery.pool_store import PoolStore
    from carbon.challenge_validator.bank_promotion import private_evaluation_key
    from carbon.challenge_validator.ledger import AttemptLedger

    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_validator.exam_rotation",
        description="The weekly fresh-draw check of the king (operator only).",
    )
    parser.add_argument("action", choices=("due", "check", "weekly", "units"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--challenge")
    parser.add_argument("--version")
    parser.add_argument("--block", type=int)
    parser.add_argument("--sealed-binding", type=Path)
    parser.add_argument("--fresh-binding", type=Path)
    parser.add_argument("--pool-store", type=Path)
    parser.add_argument("--king")
    args = parser.parse_args(argv)
    if args.action == "weekly":
        if not args.config:
            parser.error("weekly needs --config")
        outcomes = run_weekly(json.loads(args.config.read_bytes()))
        print(json.dumps(outcomes, sort_keys=True))
        return 0
    if args.action == "units":
        if not (args.config and args.repository and args.python and args.out_dir):
            parser.error("units needs --config, --repository, --python and --out-dir")
        units = render_units(
            args.config, repository=args.repository, python=args.python
        )
        args.out_dir.mkdir(mode=0o700)
        for name, text in units.items():
            target = args.out_dir / name
            target.write_text(text, encoding="utf-8", newline="\n")
            target.chmod(0o600)
        print(json.dumps({"written": sorted(units), "installed": False}))
        return 0
    for required in ("ledger", "challenge", "version", "block", "sealed_binding"):
        if getattr(args, required) is None:
            parser.error(f"{args.action} needs --{required.replace('_', '-')}")
    log = FreshDrawLog(AttemptLedger(args.ledger))
    sealed_binding = json.loads(args.sealed_binding.read_bytes())
    sealed_key = private_evaluation_key(sealed_binding)
    if args.action == "due":
        print(
            json.dumps(
                {
                    "due": log.due(
                        challenge_id=args.challenge,
                        sealed_key=sealed_key,
                        block=args.block,
                    )
                }
            )
        )
        return 0
    if not (args.fresh_binding and args.pool_store and args.king):
        parser.error("check needs --fresh-binding, --pool-store and --king")
    fresh_binding = json.loads(args.fresh_binding.read_bytes())
    sides = []
    for binding, path in (
        (sealed_binding, args.sealed_binding),
        (fresh_binding, args.fresh_binding),
    ):
        sidecar = path.with_name(SE_SIDECAR)
        sides.append(
            {
                "key": private_evaluation_key(binding),
                "pin": binding["source_receipt_sha256"],
                "se": read_se(sidecar)[0] if sidecar.is_file() else None,
            }
        )
    outcome = check_king(
        log=log,
        store=PoolStore(args.pool_store),
        challenge_id=args.challenge,
        challenge_version=args.version,
        king=args.king,
        sealed=sides[0],
        fresh=sides[1],
        block=args.block,
    )
    print(json.dumps(outcome, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
