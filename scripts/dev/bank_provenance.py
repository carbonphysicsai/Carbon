"""Motor Specialist Bank: PROVENANCE record of which miner recipes feed each Carbon artifact (reward lane).

Owner G-LEAD-36 ("We can use any recipe to create better models and products. We will work on a reward program for
any miners who's work we use"); design reports/BANK/REWARD_PROGRAM_DRAFT_20261121.md s2.

ONE append-only SQLite file, separate from the bank file (which is rebuilt on every catalog refresh), owner-only, on
GPUYard or a custody host (class C: it holds owner pseudonyms). Each row says: Carbon artifact X used miner recipe R
in role ROLE, justified by experiments-register row E, while X was at maturity state S. Rows are written WHEN the
artifact is built and never changed afterwards: SQLite triggers abort any UPDATE or DELETE.

Attribution: the owner of the recipe's non-copy SUCCEEDED submissions (``copy_of`` NULL), read from the bank file
(public-signal tables only); the door marks later identical submissions as copies, which earn nothing. Several distinct
owners for one recipe = refused for a human to decide. The owner
appears only as the catalog's HMAC pseudonym; it resolves to a hotkey only on the host, at payout time, never here.
No amount, weight or reward value lives in this file: those are the owner's (HUMAN_INPUT).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import stat
import sys
import time
from pathlib import Path

SCHEMA = "carbon.bank-provenance.v0"
ROLES = ("STRUCTURE_SEED", "CONSTANTS_COPIED", "SETTINGS", "EVIDENCE_ONLY")
#: PRA s4 maturity states, actual only.
STATES = (
    "CANDIDATE",
    "INTERNAL_PILOT",
    "PAID_PILOT",
    "REPEATABLE_SERVICE",
    "PRODUCTIZED",
    "ENTERPRISE_QUALIFIED",
    "SCALE_READY",
)
DDL = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS provenance(
    seq INTEGER PRIMARY KEY AUTOINCREMENT, artifact_id TEXT NOT NULL, source_recipe_digest TEXT NOT NULL,
    source_owner TEXT, source_submitted_ns INTEGER, role TEXT NOT NULL, evidence_ref TEXT NOT NULL,
    artifact_status TEXT NOT NULL, recorded_ns INTEGER NOT NULL);
CREATE TRIGGER IF NOT EXISTS provenance_no_update BEFORE UPDATE ON provenance
    BEGIN SELECT RAISE(ABORT, 'provenance is append-only'); END;
CREATE TRIGGER IF NOT EXISTS provenance_no_delete BEFORE DELETE ON provenance
    BEGIN SELECT RAISE(ABORT, 'provenance is append-only'); END;
"""


class BankRefused(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _owner_only(path):
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        return False
    if os.name != "posix":
        return True
    return info.st_uid == os.getuid() and not stat.S_IMODE(info.st_mode) & 0o077


def attribution(bank_file, recipe_digest):
    """(owner pseudonym, recipe first-seen ns) for a recipe, or a typed refusal.

    The door marks a later identical submission as a copy (``copy_of``), so a recipe's non-copy SUCCEEDED submissions
    should come from ONE owner. None -> refused (nothing to attribute); more than one distinct owner -> refused
    (a human decides; never guessed)."""
    db = sqlite3.connect("file:" + str(bank_file) + "?mode=ro", uri=True, timeout=5)
    db.execute("PRAGMA query_only=1")
    try:
        owners = {
            r[0]
            for r in db.execute(
                "SELECT l.owner FROM outcomes s JOIN lineage l ON l.submission_id = s.submission_id"
                " WHERE s.recipe_digest=? AND s.task_state='SUCCEEDED' AND s.copy_of IS NULL",
                (recipe_digest,),
            )
        }
        seen = db.execute(
            "SELECT first_seen_s FROM recipe_features WHERE recipe_digest=?",
            (recipe_digest,),
        ).fetchone()
    finally:
        db.close()
    if not owners:
        raise BankRefused("source_not_attributable")
    if len(owners) > 1:
        raise BankRefused("attribution_ambiguous")
    first_ns = None if seen is None or seen[0] is None else int(seen[0] * 1e9)
    return owners.pop(), first_ns


def record(
    provenance_file,
    bank_file,
    artifact_id,
    sources,
    evidence_ref,
    artifact_status,
    *,
    now=time.time_ns,
):
    """Append one row per (artifact, source recipe). ``sources`` = [(recipe_digest, role)]. Returns rows written."""
    if artifact_status not in STATES:
        raise BankRefused("artifact_status_unknown")
    if (
        not isinstance(artifact_id, str)
        or not artifact_id
        or not isinstance(evidence_ref, str)
        or not evidence_ref
    ):
        raise BankRefused("artifact_or_evidence_missing")
    if not sources:
        raise BankRefused("no_sources")
    rows = []
    for digest, role in sources:
        if role not in ROLES:
            raise BankRefused("role_unknown")
        owner, first_ns = attribution(bank_file, digest)
        rows.append(
            (
                artifact_id,
                digest,
                owner,
                first_ns,
                role,
                evidence_ref,
                artifact_status,
                now(),
            )
        )
    path = Path(provenance_file)
    fresh = not path.exists()
    if fresh:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    elif not _owner_only(path):
        raise BankRefused("provenance_not_owner_only")
    db = sqlite3.connect(path)
    try:
        db.executescript(DDL)
        db.execute("INSERT OR IGNORE INTO meta VALUES('schema', ?)", (SCHEMA,))
        if dict(db.execute("SELECT k, v FROM meta")).get("schema") != SCHEMA:
            raise BankRefused("provenance_schema_unknown")
        db.executemany(
            "INSERT INTO provenance(artifact_id, source_recipe_digest, source_owner, source_submitted_ns, role,"
            " evidence_ref, artifact_status, recorded_ns) VALUES(?,?,?,?,?,?,?,?)",
            rows,
        )
        db.commit()
    finally:
        db.close()
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--bank", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        help="RECIPE_DIGEST:ROLE (repeatable)",
    )
    parser.add_argument(
        "--evidence", required=True, help="experiments-register id, e.g. E008"
    )
    parser.add_argument("--status", required=True, choices=STATES)
    args = parser.parse_args(argv)
    try:
        sources = []
        for item in args.source:
            digest, _, role = item.rpartition(":")
            sources.append((digest, role))
        n = record(
            args.provenance,
            args.bank,
            args.artifact,
            sources,
            args.evidence,
            args.status,
        )
    except BankRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps({"rows_written": n}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
