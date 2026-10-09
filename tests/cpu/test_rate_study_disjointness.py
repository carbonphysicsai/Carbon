"""The rate study's counts-only disjointness check on synthetic sets."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "disjointness", ROOT / "scripts/dev/rate_study/disjointness.py"
)
dj = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dj)


def case(i, **extra):
    return {"c1": 1.0 + i / 1000, "c2": 0.5, "t_amb_c": 25.0, "soc0": 0.1, **extra}


def ledger(path, banks):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE cases(case_id TEXT, bank TEXT, inputs TEXT)")
    for bank, cases in banks.items():
        for i, c in enumerate(cases):
            db.execute(
                "INSERT INTO cases VALUES (?, ?, ?)",
                (f"{bank}-{i}", bank, json.dumps(sorted(c.items()))),
            )
    db.commit()
    db.close()


def test_counts_matches_and_never_writes_cases(tmp_path):
    study = tmp_path / "bank.sqlite3"
    ledger(
        study,
        {
            "pool": [case(i) for i in range(10)],
            "fresh": [case(100 + i) for i in range(5)],
        },
    )
    ev5 = tmp_path / "ev5.json"
    ev5.write_text(
        json.dumps(
            {"cases": [{"case_id": "x", "inputs": case(3)}, {"inputs": case(500)}]}
        )
    )
    train = tmp_path / "train.jsonl"
    train.write_text("\n".join(json.dumps(case(900 + i, id=i)) for i in range(4)))
    out = tmp_path / "out.json"
    code = dj.main([
        "--study", f"pool={study}#pool", "--study", f"fresh={study}#fresh",
        "--against", f"ev5={ev5}", "--against", f"train={train}", "--out", str(out),
    ])  # fmt: skip
    doc = json.loads(out.read_text())
    assert code == 1 and doc["all_disjoint"] is False
    assert doc["study"]["pool"]["matches"] == {"ev5": 1, "train": 0}
    assert doc["study"]["fresh"]["disjoint"] is True
    assert doc["study"]["pool"]["cases"] == 10 and doc["against_sizes"]["ev5"] == 2
    text = out.read_text()
    assert "1.003" not in text and "pool-3" not in text  # no inputs or ids
    assert oct(out.stat().st_mode & 0o777) == "0o600"


def test_study_sets_overlapping_each_other_are_not_disjoint(tmp_path):
    study = tmp_path / "bank.sqlite3"
    ledger(study, {"pool": [case(1), case(2)], "fresh": [case(2)]})
    other = tmp_path / "none.json"
    other.write_text("[]")
    doc = dj.check(
        {"pool": f"{study}#pool", "fresh": f"{study}#fresh"}, {"none": str(other)}
    )
    assert doc["study"]["fresh"]["matches_other_study_sets"] == {"pool": 1}
    assert doc["all_disjoint"] is False


def test_canonical_ignores_ids_and_rounds_to_draw_precision():
    assert dj.canonical(case(1, case_id="a")) == dj.canonical(case(1, case_id="b"))
    assert dj.canonical({**case(1), "c2": 0.50000001}) == dj.canonical(case(1))
    assert dj.canonical({"c1": 1.0}) is None
