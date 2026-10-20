"""The sealed plating reference battery-plating-ref-v2, as a per-case label.

VALIDATOR-PLATING-REF-V2-02 (sealed on #1316) labels a case from its mesh-20
plating margin and, where re-solved, its mesh-160 margin. The labels come from
the reference's own reader, `scripts/dev/battery/plating_rereference.py:
v2_label`, executed from the exact bytes whose sha256 is pinned here, never
reimplemented. A case inside the v2 window without a mesh-160 re-solve is
`pending-m160-r1` UNRESOLVED and is never usable as FEASIBLE; `None` is v2's
own "no claim" (|m20| >= 15 mV).

Trusted-host only: it reads a repository script, so it never runs on a miner.
"""

from __future__ import annotations

import hashlib
import types
from functools import lru_cache
from pathlib import Path

VERSION = "battery-plating-ref-v2"
READER = (
    "scripts/dev/battery/plating_rereference.py",
    "dc8fe7f3f2cadb1993a9fce125ed44d292583e81576de10863e99bd5137351bc",
)
_REPOSITORY = Path(__file__).resolve().parents[2]


class ReaderUnavailable(ValueError):
    """The pinned reader is missing or differs from its pin."""


@lru_cache(maxsize=4)
def reader(root: str = str(_REPOSITORY)):
    """`v2_label`, executed from the verified bytes (never a second read)."""
    path = Path(root) / READER[0]
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ReaderUnavailable(f"{READER[0]} is missing") from exc
    if hashlib.sha256(raw).hexdigest() != READER[1]:
        raise ReaderUnavailable(f"pinned {READER[0]} differs")
    module = types.ModuleType("carbon_plating_rereference")
    module.__file__ = str(path)
    exec(compile(raw, module.__file__, "exec"), module.__dict__)
    return module.v2_label


def labels(records, root: str = str(_REPOSITORY)) -> list:
    """Each record's v2 label from its mesh-20 margin (no mesh-160 re-solve)."""
    v2_label = reader(root)
    return [v2_label(float(r["outputs"]["plating_margin_v"])) for r in records]
