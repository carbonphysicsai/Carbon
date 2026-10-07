"""Pre-solved hidden-case banks on the producer (VALIDATOR-23;
OWNER-BANK-ARCHITECTURE-01). Producer-only: no validator surface imports it.

Every rotation draws its batch from a bank the producer solved once, rather
than solving a fresh batch:

- **Banks.** A Challenge names its banks: `pool` (a faithful draw from P),
  and steered quiz banks (`q2`, `q3:<stratum>`). Each bank has a stratum
  function, which is a single stratum for an unsteered bank.
- **Tranches.** A bank grows in tranches. A tranche is drawn by the
  Challenge's `BankSource` from the producer root under its tranche role. It
  is committed to the bank journal before use, then solved, then sealed with
  a Merkle root (`bank_proof`) over its cases and terminal references.
- **Live set.** Sealed cases whose reference is `OK` and that are not
  retired. A case whose reference failed is counted, never drawn.
- **Windows.** Each window draws n live cases, uniformly and without
  replacement, seeded by `HMAC(bank key, window/<bank>/<slot>)`. It skips
  every case held by another window of the same bank still active, and
  draws each stratum's quota within that stratum. A window's draw is stored
  once.
- **Exposure.** Each draw adds one exposure to each drawn case. At E the
  case retires into the release queue. Releasing it stays HUMAN_INPUT
  (OWNER-BATTERY-3B-AND-EXPOSURE-01).
- **Top-up.** `deficit` is what the bank needs to return to B live cases,
  counting tranches not yet sealed. The caller draws, solves and seals a
  tranche of that size.

The bank key and every case, input and reference are private and
owner-only. The journal and `status` hold public values only: roots,
digests, counts, exposure histograms and coverage.
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import abc
import contextlib
import hashlib
import hmac
import json
import os
import random
import sqlite3
import stat
from pathlib import Path

from . import bank_proof
from .batch_source import ProducerRefused

JOURNAL_SCHEMA = "carbon.challenge-validator.bank-journal.v1"
STORE_SCHEMA = "carbon.challenge-validator.bank-store.v1"
LIVE_STATUS = "OK"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


class BankSource(abc.ABC):
    """What a Challenge supplies to bank its hidden cases."""

    challenge_id: str

    @abc.abstractmethod
    def draw_tranche(self, bank, role, count):
        """`count` fresh cases `[{case_id, inputs}]` for `bank`, drawn from
        the producer root under `role`: deterministic, with case ids unique
        across every role. Private."""

    @abc.abstractmethod
    def terminal(self):
        """The reference statuses that end a case."""

    def stratum(self, bank, inputs):
        """The stratum of `inputs` within `bank`; one stratum by default."""
        return "all"

    def cell(self, bank, inputs):
        """The coverage cell of `inputs` (public), or None: no coverage
        diagnostic for this bank."""
        return


class BankRefused(ProducerRefused):
    pass


def _owner_only_dir(path):
    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True, mode=0o700)
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise BankRefused("bank_dir_not_owner_only")
    return path


def _count(db, bank, sql):
    return db.execute(sql, (bank,)).fetchone()[0]


class BankLedger:
    """One Challenge's banks: tranches, cases, windows, exposures and the
    public journal, owner-only."""

    DDL = """
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS tranches(
        bank TEXT NOT NULL,
        number INTEGER NOT NULL,
        role TEXT NOT NULL UNIQUE,
        fingerprint TEXT NOT NULL,
        drawn_sequence INTEGER NOT NULL,
        state TEXT NOT NULL,
        root TEXT,
        references_digest TEXT,
        sealed_sequence INTEGER,
        PRIMARY KEY(bank, number)
    );
    CREATE TABLE IF NOT EXISTS cases(
        case_id TEXT PRIMARY KEY,
        bank TEXT NOT NULL,
        tranche TEXT NOT NULL,
        stratum TEXT NOT NULL,
        inputs TEXT NOT NULL,
        reference TEXT,
        status TEXT,
        exposures INTEGER NOT NULL DEFAULT 0,
        retired_slot INTEGER
    );
    CREATE TABLE IF NOT EXISTS windows(
        bank TEXT NOT NULL,
        slot INTEGER NOT NULL,
        cases TEXT NOT NULL,
        selection_digest TEXT NOT NULL,
        PRIMARY KEY(bank, slot)
    );
    CREATE TABLE IF NOT EXISTS release(
        case_id TEXT PRIMARY KEY,
        bank TEXT NOT NULL,
        slot INTEGER NOT NULL
    );
    """

    def __init__(self, directory, source):
        self.directory = _owner_only_dir(directory)
        self.source = source
        self.challenge_id = source.challenge_id
        self.path = self.directory / "bank.sqlite3"
        self.journal_path = self.directory / "bank-journal.jsonl"
        key = self.directory / "bank.key"
        if not key.exists():
            fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(os.urandom(32))
        for path in (key,):
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise BankRefused("bank_file_not_owner_only")
        self._key = key.read_bytes()
        if len(self._key) != 32:
            raise BankRefused("bank_key_malformed")
        if not self.path.exists():
            os.close(os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600))
        if not self.journal_path.exists():
            os.close(
                os.open(self.journal_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            )
        database = sqlite3.connect(self.path, isolation_level=None)
        try:
            database.executescript(self.DDL)
            database.execute(
                "INSERT OR IGNORE INTO meta VALUES('schema', ?)", (STORE_SCHEMA,)
            )
            database.execute(
                "INSERT OR IGNORE INTO meta VALUES('challenge', ?)",
                (self.challenge_id,),
            )
            found = dict(database.execute("SELECT key, value FROM meta").fetchall())
        finally:
            database.close()
        if found != {"schema": STORE_SCHEMA, "challenge": self.challenge_id}:
            raise BankRefused("bank_store_mismatch")

    def __repr__(self):
        return f"BankLedger({self.challenge_id}, <redacted>)"

    @contextlib.contextmanager
    def _db(self):
        database = sqlite3.connect(self.path, timeout=30)
        database.row_factory = sqlite3.Row
        try:
            yield database
            database.commit()
        except Exception:
            database.rollback()
            raise
        finally:
            database.close()

    # --- the public journal ---------------------------------------------------

    def entries(self):
        return [
            json.loads(line)
            for line in self.journal_path.read_text().splitlines()
            if line
        ]

    def _append(self, event, **fields):
        entry = {
            "schema": JOURNAL_SCHEMA,
            "sequence": len(self.entries()),
            "event": event,
            "challenge_id": self.challenge_id,
            **fields,
        }
        fd = os.open(self.journal_path, os.O_WRONLY | os.O_APPEND)
        with os.fdopen(fd, "a") as handle:
            handle.write(_canonical(entry) + "\n")
        return entry

    # --- tranches -------------------------------------------------------------

    def tranches(self, bank=None):
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM tranches"
                + (" WHERE bank = ?" if bank else "")
                + " ORDER BY bank, number",
                (bank,) if bank else (),
            ).fetchall()
        return [dict(row) for row in rows]

    def draw_tranche(self, bank, count):
        """Draw and journal-commit the bank's next tranche of `count` cases
        before any use. Returns `{tranche, fingerprint, cases}`."""
        if type(count) is not int or count < 1:
            raise BankRefused("bank_tranche_size_malformed")
        number = len(self.tranches(bank)) + 1
        role = f"bank-{bank}-T{number}"
        cases = self.source.draw_tranche(bank, role, count)
        ids = [case["case_id"] for case in cases]
        if len(cases) != count or len(set(ids)) != count:
            raise BankRefused("bank_tranche_malformed")
        fingerprint = _digest({"bank": bank, "role": role, "cases": cases})
        with self._db() as db:
            taken = db.execute(
                f"SELECT 1 FROM cases WHERE case_id IN ({','.join('?' * count)})",
                ids,
            ).fetchone()
            if taken is not None:
                raise BankRefused("bank_case_id_reused")
        entry = self._append(
            "tranche_drawn",
            bank=bank,
            tranche=role,
            fingerprint=fingerprint,
            cases=count,
        )
        with self._db() as db:
            db.execute(
                "INSERT INTO tranches VALUES (?, ?, ?, ?, ?, 'DRAWN', NULL, NULL, NULL)",
                (bank, number, role, fingerprint, entry["sequence"]),
            )
            for case in cases:
                db.execute(
                    "INSERT INTO cases(case_id, bank, tranche, stratum, inputs) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        case["case_id"],
                        bank,
                        role,
                        str(self.source.stratum(bank, case["inputs"])),
                        _canonical(case["inputs"]),
                    ),
                )
        return {"tranche": role, "fingerprint": fingerprint, "cases": count}

    def jobs(self, tranche):
        """The tranche's unsolved cases, as solve jobs. Private."""
        with self._db() as db:
            rows = db.execute(
                "SELECT case_id, inputs FROM cases WHERE tranche = ? "
                "AND reference IS NULL ORDER BY case_id",
                (tranche,),
            ).fetchall()
        return [
            {"case_id": row["case_id"], "inputs": json.loads(row["inputs"])}
            for row in rows
        ]

    def ingest(self, tranche, records):
        """Store each case's first terminal reference record; refuse a case
        outside the tranche or a record for other inputs. Returns how many
        cases are still unsolved."""
        terminal = set(self.source.terminal())
        with self._db() as db:
            state = db.execute(
                "SELECT state FROM tranches WHERE role = ?", (tranche,)
            ).fetchone()
            if state is None:
                raise BankRefused("bank_unknown_tranche")
            if state["state"] == "SEALED":
                raise BankRefused("bank_tranche_sealed")
            for record in records:
                case_id = record.get("case_id") if type(record) is dict else None
                row = db.execute(
                    "SELECT inputs, reference FROM cases WHERE case_id = ? "
                    "AND tranche = ?",
                    (case_id, tranche),
                ).fetchone()
                if row is None:
                    raise BankRefused("bank_reference_not_in_tranche")
                if record.get("status") not in terminal or row["reference"] is not None:
                    continue
                if "inputs" in record and record["inputs"] != json.loads(row["inputs"]):
                    raise BankRefused("bank_reference_inputs_mismatch")
                db.execute(
                    "UPDATE cases SET reference = ?, status = ? WHERE case_id = ?",
                    (_canonical(record), record["status"], case_id),
                )
            return db.execute(
                "SELECT COUNT(*) FROM cases WHERE tranche = ? AND reference IS NULL",
                (tranche,),
            ).fetchone()[0]

    def _leaves(self, tranche):
        with self._db() as db:
            rows = db.execute(
                "SELECT case_id, inputs, reference FROM cases WHERE tranche = ? "
                "ORDER BY case_id",
                (tranche,),
            ).fetchall()
        return [
            (
                row["case_id"],
                json.loads(row["inputs"]),
                None if row["reference"] is None else json.loads(row["reference"]),
            )
            for row in rows
        ]

    def seal(self, tranche):
        """Seal a fully solved tranche: its Merkle root and references digest,
        journaled. Idempotent; a sealed tranche whose cases changed is
        refused."""
        rows = self._leaves(tranche)
        if any(reference is None for _, _, reference in rows):
            raise BankRefused("bank_tranche_unsolved")
        leaves = [bank_proof.leaf(c, x, r) for c, x, r in rows]
        root = bank_proof.root(leaves)
        references = _digest([[c, r] for c, _, r in rows])
        with self._db() as db:
            found = dict(
                db.execute(
                    "SELECT * FROM tranches WHERE role = ?", (tranche,)
                ).fetchone()
            )
        if found["state"] == "SEALED":
            if (found["root"], found["references_digest"]) != (root, references):
                raise BankRefused("bank_tranche_changed")
            return self._commitment(found)
        live = sum(r["status"] == LIVE_STATUS for _, _, r in rows)
        entry = self._append(
            "tranche_sealed",
            bank=found["bank"],
            tranche=tranche,
            root=root,
            references_digest=references,
            cases=len(rows),
            live=live,
            reference_failed=len(rows) - live,
        )
        with self._db() as db:
            db.execute(
                "UPDATE tranches SET state = 'SEALED', root = ?, references_digest = ?, "
                "sealed_sequence = ? WHERE role = ?",
                (root, references, entry["sequence"], tranche),
            )
            found = dict(
                db.execute(
                    "SELECT * FROM tranches WHERE role = ?", (tranche,)
                ).fetchone()
            )
        return self._commitment(found)

    @staticmethod
    def _commitment(row):
        """A sealed tranche's public commitment."""
        return {
            "tranche": row["role"],
            "bank": row["bank"],
            "root": row["root"],
            "references_digest": row["references_digest"],
            "sealed_sequence": row["sealed_sequence"],
        }

    # --- the live set and windows ---------------------------------------------

    def _live(self, db, bank, exclude):
        rows = db.execute(
            "SELECT c.case_id, c.stratum FROM cases c JOIN tranches t "
            "ON t.role = c.tranche WHERE c.bank = ? AND t.state = 'SEALED' "
            "AND c.status = ? AND c.retired_slot IS NULL ORDER BY c.case_id",
            (bank, LIVE_STATUS),
        ).fetchall()
        return [
            (r["case_id"], r["stratum"]) for r in rows if r["case_id"] not in exclude
        ]

    def _rng(self, bank, slot):
        seed = hmac.new(
            self._key, f"window/{bank}/{slot}".encode(), hashlib.sha256
        ).digest()
        return random.Random(int.from_bytes(seed[:16], "big"))

    def draw_window(self, bank, slot, quotas, *, active_slots=(), retire_at):
        """Draw slot `slot`'s cases from `bank`: `quotas` maps stratum to a
        count (one entry, `{"all": n}`, for an unsteered bank). Without
        replacement, disjoint from the windows of `active_slots`. Stored once,
        exposures counted, cases at `retire_at` exposures retired into the
        release queue. Returns the drawn case ids, sorted."""
        if type(retire_at) is not int or retire_at < 1:
            raise BankRefused("bank_retirement_malformed")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            stored = db.execute(
                "SELECT cases FROM windows WHERE bank = ? AND slot = ?", (bank, slot)
            ).fetchone()
            if stored is not None:
                return json.loads(stored["cases"])
            held = set()
            for other in active_slots:
                row = db.execute(
                    "SELECT cases FROM windows WHERE bank = ? AND slot = ?",
                    (bank, other),
                ).fetchone()
                if row is not None:
                    held |= set(json.loads(row["cases"]))
            live = self._live(db, bank, held)
            rng = self._rng(bank, slot)
            drawn = []
            for stratum, count in sorted(quotas.items()):
                pool = [c for c, s in live if stratum == "all" or s == stratum]
                if len(pool) < count:
                    raise BankRefused("bank_short:" + bank)
                drawn += rng.sample(pool, count)
            drawn = sorted(drawn)
            db.execute(
                "INSERT INTO windows VALUES (?, ?, ?, ?)",
                (bank, slot, _canonical(drawn), _digest(drawn)),
            )
            retired = 0
            for case_id in drawn:
                db.execute(
                    "UPDATE cases SET exposures = exposures + 1 WHERE case_id = ?",
                    (case_id,),
                )
                exposures = db.execute(
                    "SELECT exposures FROM cases WHERE case_id = ?", (case_id,)
                ).fetchone()[0]
                if exposures >= retire_at:
                    db.execute(
                        "UPDATE cases SET retired_slot = ? WHERE case_id = ?",
                        (slot, case_id),
                    )
                    db.execute(
                        "INSERT INTO release VALUES (?, ?, ?)", (case_id, bank, slot)
                    )
                    retired += 1
        self._append(
            "window_drawn",
            bank=bank,
            slot=slot,
            cases=len(drawn),
            selection_digest=_digest(drawn),
            retired=retired,
        )
        return drawn

    def window_cases(self, bank, slot):
        """A drawn window's cases with their references and Merkle proofs,
        and its tranches' commitments. Private."""
        with self._db() as db:
            stored = db.execute(
                "SELECT cases, selection_digest FROM windows WHERE bank = ? AND slot = ?",
                (bank, slot),
            ).fetchone()
            if stored is None:
                raise BankRefused("bank_window_not_drawn")
            ids = json.loads(stored["cases"])
            rows = db.execute(
                f"SELECT case_id, tranche FROM cases WHERE case_id IN "
                f"({','.join('?' * len(ids))})",
                ids,
            ).fetchall()
            tranches = {
                r["role"]: dict(r)
                for r in db.execute("SELECT * FROM tranches").fetchall()
            }
        of = {row["case_id"]: row["tranche"] for row in rows}
        cases, used = {}, {}
        for tranche in sorted(set(of.values())):
            rows = self._leaves(tranche)
            leaves = [bank_proof.leaf(c, x, r) for c, x, r in rows]
            for index, (case_id, inputs, reference) in enumerate(rows):
                if case_id in of:
                    cases[case_id] = {
                        "inputs": inputs,
                        "reference": reference,
                        "tranche": tranche,
                        "proof": bank_proof.proof(leaves, index),
                    }
            used[tranche] = self._commitment(tranches[tranche])
        return {
            "cases": cases,
            "tranches": [used[t] for t in sorted(used)],
            "selection_digest": stored["selection_digest"],
        }

    def deficit(self, bank, size):
        """Cases the bank needs to return to `size` live cases, counting
        tranches drawn but not yet sealed."""
        with self._db() as db:
            live = len(self._live(db, bank, set()))
            pending = db.execute(
                "SELECT COUNT(*) FROM cases c JOIN tranches t ON t.role = c.tranche "
                "WHERE c.bank = ? AND t.state = 'DRAWN'",
                (bank,),
            ).fetchone()[0]
        return max(0, size - live - pending)

    def released(self):
        """The release queue's public counts by bank. Releasing stays
        HUMAN_INPUT."""
        with self._db() as db:
            rows = db.execute(
                "SELECT bank, COUNT(*) FROM release GROUP BY bank ORDER BY bank"
            ).fetchall()
        return {bank: count for bank, count in rows}

    # --- diagnostics (public) -------------------------------------------------

    def coverage(self, bank, cells):
        """Per stratum, the share of P-mass in `cells` (`{cell: mass}`, the
        registered stratum's cells) that the live bank occupies."""
        with self._db() as db:
            rows = db.execute(
                "SELECT c.inputs, c.stratum FROM cases c JOIN tranches t "
                "ON t.role = c.tranche WHERE c.bank = ? AND t.state = 'SEALED' "
                "AND c.status = ? AND c.retired_slot IS NULL",
                (bank, LIVE_STATUS),
            ).fetchall()
        occupied = {}
        for row in rows:
            cell = self.source.cell(bank, json.loads(row["inputs"]))
            if cell is not None:
                occupied.setdefault(row["stratum"], set()).add(cell)
        report = {}
        for stratum, masses in sorted(cells.items()):
            total = sum(masses.values())
            held = occupied.get(stratum, set())
            report[stratum] = (
                None
                if total <= 0
                else sum(m for c, m in masses.items() if c in held) / total
            )
        return report

    def status(self):
        """Public counts per bank: live, pending, failed references, retired,
        windows, and the exposure histogram of live cases."""
        report = {}
        with self._db() as db:
            banks = [
                r[0]
                for r in db.execute(
                    "SELECT DISTINCT bank FROM tranches ORDER BY bank"
                ).fetchall()
            ]
            for bank in banks:
                live = self._live(db, bank, set())
                histogram = {}
                for (count,) in db.execute(
                    "SELECT c.exposures FROM cases c JOIN tranches t ON t.role = "
                    "c.tranche WHERE c.bank = ? AND t.state = 'SEALED' AND c.status = ? "
                    "AND c.retired_slot IS NULL",
                    (bank, LIVE_STATUS),
                ).fetchall():
                    histogram[str(count)] = histogram.get(str(count), 0) + 1

                report[bank] = {
                    "live": len(live),
                    "pending": _count(
                        db,
                        bank,
                        "SELECT COUNT(*) FROM cases c JOIN tranches t ON t.role = "
                        "c.tranche WHERE c.bank = ? AND t.state = 'DRAWN'",
                    ),
                    "reference_failed": _count(
                        db,
                        bank,
                        "SELECT COUNT(*) FROM cases WHERE bank = ? AND status IS NOT "
                        f"NULL AND status != '{LIVE_STATUS}'",
                    ),
                    "retired": _count(
                        db,
                        bank,
                        "SELECT COUNT(*) FROM cases WHERE bank = ? AND retired_slot IS NOT NULL",
                    ),
                    "tranches": _count(
                        db, bank, "SELECT COUNT(*) FROM tranches WHERE bank = ?"
                    ),
                    "windows": _count(
                        db, bank, "SELECT COUNT(*) FROM windows WHERE bank = ?"
                    ),
                    "exposures": dict(sorted(histogram.items())),
                }
        return report


__all__ = ["BankLedger", "BankRefused", "BankSource"]
