"""Graphite's per-pipeline-stage permission ledger (draft, Challenge Roadmap §02).

Which of Graphite's roles may act at which challenge-pipeline stage. A role
absent from a stage's row is refused there, and the frozen run admits none: it
is Carbon's own evaluation. The ledger is a DRAFT until the protocol is
locked. The campaign controller does not read it yet.

The ledger's key is `pipeline_stages` and the stage argument is
`pipeline_stage`. A research session's `stage` (`research_loop.run_epoch`)
namespaces a session inside its epoch and is a different thing
(OWNER-GRAPHITE-ATTACKER-01, slice AT-A). The ledger's roles are Graphite's
role names (`carbon.agent_campaign.graphite.roles.RoleName`).
"""

from __future__ import annotations

import json
from pathlib import Path

LEDGER = Path(__file__).with_name("graphite_ledger.json")
SCHEMA = "carbon.challenge-pipeline.graphite-ledger.v2"
PIPELINE_STAGES = ("prioritize", "design", "test_iterate", "frozen_run", "rank")


def load_ledger(path=LEDGER):
    ledger = json.loads(Path(path).read_text(encoding="utf-8"))
    if type(ledger) is not dict or ledger.get("schema") != SCHEMA:
        raise ValueError(f"the ledger's schema is {SCHEMA}")
    stages = ledger.get("pipeline_stages")
    if type(stages) is not dict or tuple(stages) != PIPELINE_STAGES:
        raise ValueError(f"the ledger's pipeline stages are {PIPELINE_STAGES}")
    for name, row in stages.items():
        roles = row.get("roles") if type(row) is dict else None
        if type(roles) is not list or not all(type(r) is str for r in roles):
            raise ValueError(f"pipeline stage {name} lists its roles")
    if stages["frozen_run"]["roles"]:
        raise ValueError("the frozen run admits no Graphite role")
    return ledger


def graphite_may(pipeline_stage, role, ledger=None):
    """True only when `role` is listed for `pipeline_stage`. An unknown stage
    refuses."""
    ledger = ledger or load_ledger()
    row = ledger["pipeline_stages"].get(pipeline_stage)
    return row is not None and getattr(role, "value", role) in row["roles"]
