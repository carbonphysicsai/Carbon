"""SUBMISSION-RATE-STUDY-01 content disjointness, operator-side, counts only
(run sheet C.3; plan O6: it stands in for H2's missing overlap check for
this study).

    python scripts/dev/rate_study/disjointness.py \\
        --study pool=/var/lib/carbon-producer/rate-study/battery/bank/bank.sqlite3#pool \\
        --study fresh=/var/lib/carbon-producer/rate-study/battery/bank/bank.sqlite3#fresh \\
        --against live=/var/lib/carbon-producer/.../bank.sqlite3 \\
        --against ev5=PATH.json --against train=PATH.jsonl ... \\
        --out /var/lib/carbon-producer/rate-study/disjointness.json

A case is its canonical battery inputs (`c1, c2, t_amb_c, soc0`, each
rounded to the draw's 4 decimals); ids, seeds and roles are ignored. Two
cases match when those inputs are identical. A near-duplicate tolerance
would be a scientific choice and stays HUMAN_INPUT, so only exact matches
are counted, and the record says so.

Sources: a bank ledger (`bank.sqlite3`, every case, or one bank with
`#name`), or a JSON / JSONL file in which every object carrying all four
inputs (at its top level or under `inputs`, as a mapping or a list of
pairs) is a case. The output holds counts, the study sets' digest-set
digests and this script's digest. It holds no case, input, id or per-case
digest, and it is written owner-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

INPUTS = ("c1", "c2", "t_amb_c", "soc0")  # carbon/battery/domain.py
DECIMALS = 4  # carbon/battery/seeds.draw_inputs


def canonical(inputs):
    """Digest of one case's inputs, or None when it is not a battery case."""
    if isinstance(inputs, list) and all(
        isinstance(p, list | tuple) and len(p) == 2 for p in inputs
    ):
        inputs = dict(inputs)
    if not isinstance(inputs, dict) or not all(k in inputs for k in INPUTS):
        return None
    try:
        values = [round(float(inputs[k]), DECIMALS) for k in INPUTS]
    except (TypeError, ValueError):
        return None
    text = json.dumps(dict(zip(INPUTS, values)), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def _walk(obj, out):
    if isinstance(obj, dict):
        digest = canonical(obj) or canonical(obj.get("inputs"))
        if digest:
            out.append(digest)
            return
        for value in obj.values():
            _walk(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _walk(value, out)


def read(spec):
    """[digest, ...] for one source (duplicates kept for counting)."""
    path, _, bank = spec.partition("#")
    path = Path(path)
    if path.suffix in (".sqlite3", ".sqlite", ".db"):
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            sql, args = (
                ("SELECT inputs FROM cases WHERE bank = ?", (bank,))
                if bank
                else ("SELECT inputs FROM cases", ())
            )
            rows = [canonical(json.loads(r[0])) for r in db.execute(sql, args)]
        finally:
            db.close()
        return [d for d in rows if d]
    text = path.read_text()
    out = []
    if path.suffix == ".jsonl":
        for line in text.splitlines():
            if line.strip():
                _walk(json.loads(line), out)
    else:
        _walk(json.loads(text), out)
    return out


def check(study, against):
    """Counts only. `study` and `against` map a set name to its source spec."""
    studies = {name: read(spec) for name, spec in study.items()}
    others = {name: set(read(spec)) for name, spec in against.items()}
    result = {"rule": "exact match of canonical inputs (c1, c2, t_amb_c, soc0 at 4 decimals); near-duplicate tolerance HUMAN_INPUT, not checked",
              "study": {}, "against_sizes": {name: len(s) for name, s in others.items()}}  # fmt: skip
    names = sorted(studies)
    for name in names:
        digests = studies[name]
        unique = set(digests)
        row = {
            "cases": len(digests),
            "repeated_within_set": len(digests) - len(unique),
            "set_digest": hashlib.sha256(
                "\n".join(sorted(unique)).encode()
            ).hexdigest(),
            "matches": {other: len(unique & s) for other, s in others.items()},
            "matches_other_study_sets": {
                o: len(unique & set(studies[o])) for o in names if o != name
            },
        }
        row["disjoint"] = not any(row["matches"].values()) and not any(
            row["matches_other_study_sets"].values()
        )
        result["study"][name] = row
    result["all_disjoint"] = all(r["disjoint"] for r in result["study"].values())
    result["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def _pairs(values):
    out = {}
    for v in values or ():
        name, sep, spec = v.partition("=")
        if not sep or not name or not spec:
            raise SystemExit(f"expected NAME=PATH, got {v!r}")
        out[name] = spec
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rate_study.disjointness")
    parser.add_argument(
        "--study", action="append", required=True, help="NAME=PATH[#bank]"
    )
    parser.add_argument(
        "--against", action="append", required=True, help="NAME=PATH[#bank]"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = check(_pairs(args.study), _pairs(args.against))
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"all_disjoint": result["all_disjoint"],
                      "matches": {n: r["matches"] for n, r in result["study"].items()}}))  # fmt: skip
    return 0 if result["all_disjoint"] else 1


if __name__ == "__main__":
    sys.exit(main())
