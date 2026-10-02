"""Graphite's per-stage permission ledger (draft, Challenge Roadmap §02).

Which of Graphite's roles may act at which pipeline stage. A role absent from
a stage's row is refused there, and the frozen run admits none: it is
Carbon's own evaluation. The ledger is a DRAFT until the protocol is locked.
The campaign controller does not read it yet (`PROTOCOL_DRAFT.md` §6).
"""

from __future__ import annotations

import json
from pathlib import Path

LEDGER = Path(__file__).with_name("graphite_ledger.json")
STAGES = ("prioritize", "design", "test_iterate", "frozen_run", "rank")


def load_ledger(path=LEDGER):
    ledger = json.loads(Path(path).read_text(encoding="utf-8"))
    if tuple(ledger["stages"]) != STAGES:
        raise ValueError(f"the ledger's stages are {STAGES}")
    return ledger


def graphite_may(stage, role, ledger=None):
    """True only when `role` is listed for `stage`. An unknown stage refuses."""
    ledger = ledger or load_ledger()
    row = ledger["stages"].get(stage)
    return row is not None and getattr(role, "value", role) in row["roles"]
