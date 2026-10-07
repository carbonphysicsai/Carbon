"""Battery's windows drawn from a pre-solved bank (VALIDATOR-23 slice 2;
OWNER-BANK-ARCHITECTURE-01). Producer-only: no validator surface imports it.

Under rule `v2-bank`, the producer no longer solves a fresh batch for every
rotation:
- **The pool bank** (`bank.BankLedger`, bank `pool`) holds battery cases
  drawn from the producer's own root (`seeds.make_batch` under the tranche
  role, with its duplicate dropped). Published campaign cases are refused.
  Cases are solved once in the pinned truth image, then sealed.
- **A window** (a producer slot, screening or finalist) draws the rule's
  `window_cases` live cases from the bank, without replacement and disjoint
  from every other active window. v2's two hidden duplicates are added with
  opaque ids derived from the root. The result is an ordinary `PrivateBatch`
  under the slot's role. It is imported into the producer's own battery
  deployment (journal-committed there), and its references come from the
  bank. Battery's seal, export, check and import paths are therefore
  unchanged.
- **The commitment** gains `bank`: the tranche commitments and the window's
  selection digest. The package carries each drawn case's Merkle proof, so
  every validator checks that each case and reference came from a sealed
  tranche (`BatteryAdapter.import_answer_key`).
- **Top-up.** Before a window is drawn, the bank is refilled to the rule's
  `size` live cases: a new tranche is drawn, journal-committed, solved and
  sealed. The first fill is the operator's `fill` command.

    python -m carbon.challenge_validator.battery_bank fill --config PRODUCER.json [--workers 7]

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import random
import re
import subprocess
import sys
from pathlib import Path

from .bank import BankLedger, BankRefused, BankSource
from .batch_source import ProducerRefused
from .battery import BatteryBatchSource

REPOSITORY = Path(__file__).resolve().parents[2]
BANK = "pool"
#: Battery truth outcomes that end a case; FAILED_INFRA is retried.
TERMINAL = ("OK", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")
#: The producer's slot roles (`Producer.tick`).
SLOT_ROLE = re.compile(r"(pscreen|pfinal)-S([0-9]+)")


def bank_rule(rule):
    """The rule's pool bank values, or refusal when the rule has no bank."""
    bank = rule.get("bank") if type(rule) is dict else None
    pool = bank.get("pool") if type(bank) is dict else None
    if type(pool) is not dict:
        raise ProducerRefused("producer_rule_has_no_bank")
    return pool


class BatteryBankSource(BankSource):
    """Battery's tranche draws, from the producer deployment's root."""

    def __init__(self, target):
        self.target = target
        self.challenge_id = target.identities()["challenge"]["id"]

    def draw_tranche(self, bank, role, count):
        from carbon.battery.daemon import PublishedCaseRefused
        from carbon.battery.seeds import make_batch

        batch = make_batch(self.target.root, self.target.pin, role, count + 1, 1)
        duplicate = {dup for dup, _ in batch.duplicates}
        try:
            self.target._refuse_published(batch)
        except PublishedCaseRefused:
            raise BankRefused("bank_published_case") from None
        return [
            {"case_id": case_id, "inputs": dict(inputs)}
            for case_id, inputs in batch.cases
            if case_id not in duplicate
        ]

    def terminal(self):
        return TERMINAL


class BankedBatterySource(BatteryBatchSource):
    """Battery's producer source under rule `v2-bank`."""

    def __init__(
        self, adapter, bank_dir, *, overlay=None, repository=None, runner=None
    ):
        super().__init__(adapter, overlay=overlay, repository=repository, runner=runner)
        self.pool = bank_rule(adapter.target.rule)
        self.ledger = BankLedger(bank_dir, BatteryBankSource(adapter.target))
        self.bank_dir = Path(bank_dir)

    @classmethod
    def from_deployment(cls, config_path, bank_dir, *, overlay=None, repository):
        from .battery import BatteryAdapter

        return cls(
            BatteryAdapter.from_deployment(config_path, repository=repository),
            bank_dir,
            overlay=overlay,
            repository=repository,
        )

    # --- the bank's tranches ----------------------------------------------------

    def _solve_tranche(self, tranche, *, workers=7, timeout_s=1200.0):
        from carbon.battery import truth_env

        if self.overlay is None:
            raise ProducerRefused("producer_no_truth_overlay")
        work = self.bank_dir / "work" / tranche
        work.mkdir(parents=True, mode=0o700, exist_ok=True)
        records = work / "records.jsonl"
        for _attempt in range(3):
            jobs = [
                {"case_id": job["case_id"], **job["inputs"]}
                for job in self.ledger.jobs(tranche)
            ]
            if not jobs:
                break
            (work / "jobs.json").write_text(
                json.dumps({"fingerprint": tranche, "jobs": jobs})
            )
            if not records.exists():
                records.touch(mode=0o600)
            command = truth_env.solve_command(
                self.overlay,
                work,
                repository=self.repository,
                workers=workers,
                timeout_s=timeout_s,
            )
            (self.runner or subprocess.run)(command, check=False)
            # Records are re-read whole: the ledger keeps each case's first
            # terminal record and skips the rest.
            rows = [
                json.loads(line) for line in records.read_text().splitlines() if line
            ]
            self.ledger.ingest(tranche, rows)
        if self.ledger.jobs(tranche):
            raise ProducerRefused("producer_bank_tranche_unsolved")
        return self.ledger.seal(tranche)

    def top_up(self, *, workers=7):
        """Refill the pool bank to the rule's size: draw, solve and seal one
        tranche of the deficit, and finish any tranche left unsealed."""
        sealed = []
        for row in self.ledger.tranches(BANK):
            if row["state"] == "DRAWN":
                sealed.append(self._solve_tranche(row["role"], workers=workers))
        deficit = self.ledger.deficit(BANK, self.pool["size"])
        if deficit:
            drawn = self.ledger.draw_tranche(BANK, deficit)
            sealed.append(self._solve_tranche(drawn["tranche"], workers=workers))
        return sealed

    # --- windows -----------------------------------------------------------------

    def _window(self, role):
        """`(key, active keys)` for a slot role: screening and finalist
        windows of one slot get distinct keys, and the active ones are every
        window of the slots still live alongside it."""
        found = SLOT_ROLE.fullmatch(role)
        if found is None:
            raise ProducerRefused("producer_bank_role_not_a_slot")
        kind = 1 if found.group(1) == "pfinal" else 0
        slot = int(found.group(2))
        active = self.adapter.target.rule["active_batches"]
        earlier = range(max(0, slot - active + 1), slot + 1)
        keys = {2 * s + k for s in earlier for k in (0, 1)}
        return 2 * slot + kind, sorted(keys - {2 * slot + kind})

    def _batch(self, role, drawn):
        """The window's `PrivateBatch`: the drawn cases plus the rule's hidden
        duplicates, ids and order derived from the producer root."""
        from carbon.battery.seeds import PrivateBatch

        window = self.ledger.window_cases(BANK, self._window(role)[0])
        key = hmac.new(
            self.adapter.target.root._bytes,
            b"bank-window/" + role.encode(),
            hashlib.sha256,
        ).digest()
        rng = random.Random(int.from_bytes(key[:16], "big"))
        originals = rng.sample(sorted(drawn), self.pool["hidden_duplicates"])
        cases = [(c, window["cases"][c]["inputs"]) for c in sorted(drawn)]
        twins = []
        for j, original in enumerate(originals):
            tag = hmac.new(key, f"repeat/{j}".encode(), hashlib.sha256).hexdigest()[:16]
            twins.append((f"{role}-{tag}", original))
        inputs = dict(cases)
        cases += [(dup, inputs[original]) for dup, original in twins]
        rng.shuffle(cases)
        return (
            PrivateBatch(
                role,
                tuple((c, tuple(sorted(x.items()))) for c, x in cases),
                tuple(twins),
            ),
            window,
        )

    def draw(self, role, *, kind, size=None):
        from carbon.battery.pool_store import StateError

        if size not in (
            None,
            self.pool["window_cases"] + self.pool["hidden_duplicates"],
        ):
            raise ProducerRefused("producer_size_not_registered")
        key, active = self._window(role)
        if (kind == "finalist") != (key % 2 == 1):
            raise ProducerRefused("producer_kind_refused")
        try:
            drawn = self.ledger.draw_window(
                BANK,
                key,
                {"all": self.pool["window_cases"]},
                active_slots=active,
                retire_at=self.pool["retire_at"],
            )
        except BankRefused as refused:
            if not refused.code.startswith("bank_short"):
                raise ProducerRefused("producer_" + refused.code) from None
            self.top_up()
            drawn = self.ledger.draw_window(
                BANK,
                key,
                {"all": self.pool["window_cases"]},
                active_slots=active,
                retire_at=self.pool["retire_at"],
            )
        batch, window = self._batch(role, drawn)
        target = self.adapter.target
        try:
            fingerprint = target.import_batch(batch, kind=kind)
            target.ingest_references(
                fingerprint, [window["cases"][c]["reference"] for c in sorted(drawn)]
            )
        except StateError as refused:
            raise ProducerRefused(refused.code) from None
        return fingerprint

    def solve(self, work, **options):
        """Nothing to solve: a window's references come from the bank."""
        return {"returncode": 0, "solved": 0}

    # --- the v2 commitment and the package -------------------------------------

    def _drawn(self, fingerprint):
        row = self._row(fingerprint)
        key, _ = self._window(row["role"])
        return key, self.ledger.window_cases(BANK, key)

    def bank_commitment(self, fingerprint):
        """The commitment's `bank` field: public."""
        _key, window = self._drawn(fingerprint)
        return {
            "bank": BANK,
            "rule": dict(self.pool),
            "tranches": window["tranches"],
            "selection_digest": window["selection_digest"],
        }

    def export(self, fingerprint):
        payload = super().export(fingerprint)
        _key, window = self._drawn(fingerprint)
        payload["bank"] = {
            "proofs": {
                case_id: {"tranche": case["tranche"], "proof": case["proof"]}
                for case_id, case in sorted(window["cases"].items())
            }
        }
        return payload


def main(argv=None):
    from .producer import Producer

    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.battery_bank")
    sub = parser.add_subparsers(dest="command", required=True)
    fill = sub.add_parser("fill")
    fill.add_argument("--config", required=True)
    fill.add_argument("--workers", type=int, default=7)
    status = sub.add_parser("status")
    status.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    try:
        producer = Producer.from_config(args.config)
        banked = [
            s for s in producer.sources.values() if isinstance(s, BankedBatterySource)
        ]
        if not banked:
            raise ProducerRefused("producer_no_bank")
        [source] = banked
        if args.command == "fill":
            result = {"sealed": source.top_up(workers=args.workers)}
        else:
            result = {}
        result["status"] = source.ledger.status()
    except ProducerRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["BankedBatterySource", "BatteryBankSource", "bank_rule"]
