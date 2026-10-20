#!/usr/bin/env python3
"""Relabel Motor reference cases whose mesher was stopped from outside.

`run_batch.py` reads torque straight after the solve script, so a mesher
killed before it wrote a mesh is recorded as `REFERENCE_SOLVER_FAILED` ("no
torque at step 0"). That is infrastructure, not the reference (invariant 7):
RR-PACKS-13 lost 14 of 40 cases this way (exit 120, `log.mesh` cut at the
first traceback line, three bursts while 16 fine meshes built at once).

`run_batch.py` itself is bound by the Motor decision study's construction
freeze, so it is not edited; this runs after it over a finished run:

    python3 scripts/dev/motor/reference/infra_relabel.py RUN_DIR

A `REFERENCE_SOLVER_FAILED` record becomes `FAILED_INFRA` (its reason
recorded) only when no `mesh.json` was written and the mesher was stopped: a
signal exit (>= 128 or negative), Python's exit 120 (it could not flush its
own streams, e.g. a full disk), or a `log.mesh` traceback cut off before its
exception line. A mesher that raised its own complete error, and any case that
wrote its mesh, keep their labels. The runner's own file is kept unchanged
as `records.runner.jsonl`; `records.jsonl` becomes the relabelled set. A
second run reads the kept original, so it is idempotent.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_EXIT = re.compile(r"exit (-?[0-9]+)\Z")
#: A complete traceback ends with its exception line ("ValueError: x",
#: "KeyboardInterrupt"); a cut-off one ends inside the frames.
_EXCEPTION_LINE = re.compile(r"[A-Za-z_][\w.]*(:.*)?\Z")
RAW = "records.runner.jsonl"


def interrupted_mesher(case_dir: Path, detail: str | None) -> str | None:
    """Why the mesher was stopped from outside, or None."""
    if (case_dir / "mesh.json").exists():
        return None
    match = _EXIT.fullmatch(detail or "")
    code = int(match.group(1)) if match else None
    if code is not None and (code >= 128 or code < 0 or code == 120):
        return f"mesher stopped from outside before writing a mesh ({detail})"
    try:
        text = (case_dir / "log.mesh").read_text(errors="replace")
    except OSError:
        return None
    lines = [line for line in text.splitlines() if line.strip()]
    if (
        "Traceback (most recent call last):" in text
        and lines
        and not _EXCEPTION_LINE.fullmatch(lines[-1])
    ):
        return f"mesher traceback cut off before its exception ({detail})"
    return None


def relabel(run_dir: Path) -> dict:
    """Relabel `run_dir`'s records in place (original kept); returns counts."""
    run_dir = Path(run_dir)
    raw_path = run_dir / RAW
    if not raw_path.exists():
        raw_path.write_bytes((run_dir / "records.jsonl").read_bytes())
    out, changed = [], []
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("status") == "REFERENCE_SOLVER_FAILED":
            why = interrupted_mesher(
                run_dir / "cases" / record["case_id"], record.get("run")
            )
            if why is not None:
                record = {
                    **record,
                    "status": "FAILED_INFRA",
                    "reasons": [why],
                    "relabelled_from": {
                        "status": "REFERENCE_SOLVER_FAILED",
                        "reasons": record.get("reasons"),
                        "by": "scripts/dev/motor/reference/infra_relabel.py",
                    },
                }
                changed.append(record["case_id"])
        out.append(json.dumps(record, sort_keys=True))
    (run_dir / "records.jsonl").write_text(
        "".join(line + "\n" for line in out), encoding="utf-8"
    )
    return {"records": len(out), "relabelled_failed_infra": sorted(changed)}


if __name__ == "__main__":
    print(json.dumps(relabel(Path(sys.argv[1]))))
