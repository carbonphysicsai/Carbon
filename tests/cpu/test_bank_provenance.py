"""Bank provenance record (`scripts/dev/bank_provenance.py`; owner G-LEAD-36 reward lane): append-only (UPDATE and
DELETE abort), attribution to the one owner of a recipe's non-copy submissions (copies earn nothing; several owners
refused), closed roles and maturity states, and no amount / reward field anywhere. Synthetic bank file only.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))

import bank_features
import bank_provenance as prov

R1, R2, R3, R4 = ("sha256:" + c * 64 for c in "1234")


@pytest.fixture
def bank(tmp_path):
    path = tmp_path / "bank.sqlite3"
    db = sqlite3.connect(path)
    db.executescript(bank_features.DDL)
    rows = [
        # submission, recipe, state, copy_of, owner
        ("t1", R1, "SUCCEEDED", None, "ownerA"),
        ("t2", R1, "SUCCEEDED", "t1", "ownerB"),  # a door copy of R1: earns nothing
        ("t3", R2, "FAILED", None, "ownerC"),  # never succeeded: not attributable
        ("t4", R3, "SUCCEEDED", None, "ownerD"),
        ("t5", R3, "SUCCEEDED", None, "ownerE"),  # two owners, no copy link: ambiguous
    ]
    for i, (sid, digest, state, copy, owner) in enumerate(rows):
        db.execute(
            "INSERT INTO outcomes(submission_id, recipe_digest, task_state, copy_of) VALUES(?,?,?,?)",
            (sid, digest, state, copy),
        )
        db.execute(
            "INSERT INTO lineage(submission_id, owner, seq) VALUES(?,?,?)",
            (sid, owner, i),
        )
    db.execute(
        "INSERT INTO recipe_features(recipe_digest, first_seen_s) VALUES(?, 100.5)",
        (R1,),
    )
    db.commit()
    db.close()
    return path


def test_attribution_names_the_one_non_copy_owner_and_refuses_otherwise(bank):
    assert prov.attribution(bank, R1) == ("ownerA", 100_500_000_000)
    with pytest.raises(prov.BankRefused, match="source_not_attributable"):
        prov.attribution(bank, R2)
    with pytest.raises(prov.BankRefused, match="attribution_ambiguous"):
        prov.attribution(bank, R3)
    with pytest.raises(prov.BankRefused, match="source_not_attributable"):
        prov.attribution(bank, R4)


def test_record_appends_and_the_file_refuses_update_and_delete(bank, tmp_path):
    out = tmp_path / "prov.sqlite3"
    n = prov.record(
        out,
        bank,
        "cand-001",
        [(R1, "STRUCTURE_SEED")],
        "E008",
        "CANDIDATE",
        now=lambda: 7,
    )
    assert n == 1
    if os.name == "posix":
        assert os.stat(out).st_mode & 0o077 == 0
    prov.record(
        out,
        bank,
        "cand-001",
        [(R1, "CONSTANTS_COPIED")],
        "E009",
        "CANDIDATE",
        now=lambda: 8,
    )
    db = sqlite3.connect(out)
    rows = db.execute(
        "SELECT artifact_id, source_recipe_digest, source_owner, source_submitted_ns, role, evidence_ref,"
        " artifact_status, recorded_ns FROM provenance ORDER BY seq"
    ).fetchall()
    assert rows == [
        (
            "cand-001",
            R1,
            "ownerA",
            100_500_000_000,
            "STRUCTURE_SEED",
            "E008",
            "CANDIDATE",
            7,
        ),
        (
            "cand-001",
            R1,
            "ownerA",
            100_500_000_000,
            "CONSTANTS_COPIED",
            "E009",
            "CANDIDATE",
            8,
        ),
    ]
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        db.execute("UPDATE provenance SET role='SETTINGS'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        db.execute("DELETE FROM provenance")
    db.close()


@pytest.mark.parametrize(
    "kwargs,code",
    [
        (dict(sources=[(R1, "PAYOUT")]), "role_unknown"),
        (dict(status="SOLD"), "artifact_status_unknown"),
        (dict(sources=[]), "no_sources"),
        (dict(evidence=""), "artifact_or_evidence_missing"),
        (dict(sources=[(R3, "SETTINGS")]), "attribution_ambiguous"),
    ],
)
def test_typed_refusals_write_nothing(bank, tmp_path, kwargs, code):
    out = tmp_path / "prov.sqlite3"
    args = dict(sources=[(R1, "SETTINGS")], evidence="E010", status="CANDIDATE")
    args.update(kwargs)
    with pytest.raises(prov.BankRefused, match=code):
        prov.record(
            out, bank, "cand-002", args["sources"], args["evidence"], args["status"]
        )
    assert not out.exists()


def test_no_amount_or_reward_value_is_stored():
    cols = " ".join(prov.DDL.lower().split())
    for word in ("amount", "reward", "share", "payout", "price", "hotkey"):
        assert word not in cols
