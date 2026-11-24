"""Build the public decision index the decision-id invariant reads once the records leave public main (v2 5878 (2)).

    python -I -B scripts/dev/build_decision_index.py [OUT]   # default tests/invariants/decision_index.json

For every id the tree CITES that resolves TODAY (a `.agent/decisions` record's filename or content, `.agent/DECISIONS.md`,
or a `.agent/tickets` file), the index keeps the id and the sha256 of the bytes of the file that declares it (the first
in path order); plus the record-family PREFIXES the id pattern is derived from. No record content: ids and shas only
(v2 5761: no hidden value in the records). The private copy of the records keeps every sha verifiable; while a record
is still on disk, the invariant checks its sha. Run it BEFORE the records are removed; afterwards the index only grows
(a new owner record's id + sha added by a head).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "carbon.decision-index.v1"


def _invariant():
    path = ROOT / "tests" / "invariants" / "test_decision_ids_resolve.py"
    spec = importlib.util.spec_from_file_location("decision_ids_resolve", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    inv = _invariant()
    prefixes, pattern = inv._pattern()
    cited = inv._cited(pattern)
    declaring = {}
    for path in inv._records():
        for found in [inv._stem(path), *inv._ids(pattern, inv._text(path))]:
            declaring.setdefault(found, path)
    if inv.HISTORY.is_file():
        for found in inv._ids(pattern, inv._text(inv.HISTORY)):
            declaring.setdefault(found, inv.HISTORY)
    if inv.TICKETS.is_dir():
        for path in sorted(inv.TICKETS.iterdir()):
            if path.is_file():
                declaring.setdefault(inv.re.split(r"[_.]", path.name)[0], path)
    ids = {
        found: {
            "file": path.relative_to(ROOT).as_posix(),
            "sha256": _sha(path),
        }
        for found, path in sorted(declaring.items())
        if found in cited
    }
    return {"schema": SCHEMA, "prefixes": sorted(prefixes), "ids": ids}


def main(argv):
    out = (
        Path(argv[0]) if argv else ROOT / "tests" / "invariants" / "decision_index.json"
    )
    document = build()
    out.write_bytes(
        (json.dumps(document, indent=1, sort_keys=True) + "\n").encode("utf-8")
    )
    print(f"prefixes {len(document['prefixes'])}, ids {len(document['ids'])} -> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
