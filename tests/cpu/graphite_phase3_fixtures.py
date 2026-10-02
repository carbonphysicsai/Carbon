"""Shared fixtures for the Graphite phase-3 tests (GRAPHITE-01, Constructor Level 0).

A scripted model, a scripted pod account and a recording miner tool: no live
inference, no pod, no key, no network and no spend. Carbon's own reconstruction
gate, frozen-rule scoring, comparison, bundle and clean rebuild run for real on
the CPU; the pods' predictions are SYNTHETIC (`pods.synthetic_outputs`).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from graphite_fixtures import Clock, RecordingMinerTools

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import phase3
from carbon.agent_campaign.graphite.model import ScriptedModel, text, tool
from carbon.agent_campaign.graphite.pods import ScriptedPods, Step, synthetic_outputs
from carbon.agent_campaign.graphite.roles import PROPOSE
from carbon.battery.research import SCAFFOLD
from carbon.development_session.research_tools import PREFIX

REPOSITORY = Path(__file__).resolve().parents[2]
GRANT_FILE = REPOSITORY / "docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3.json"
LEDGER_NOW = 1000.0
BASELINE = SCAFFOLD


def grant_document(**changes):
    document = json.loads(GRANT_FILE.read_bytes())
    # The committed grant expires on 2026-12-31; tests run under a copy that
    # does not, with every other field the committed grant's.
    document["expires_at"] = "2099-01-01T00:00:00Z"
    document.update(changes)
    return document


def grant(**changes):
    return SpendingGrant.from_document(grant_document(**changes))


def variant(**parameters):
    strategy = copy.deepcopy(BASELINE)
    strategy["parameters"].update(parameters)
    return strategy


UNREBUILDABLE = {**BASELINE, "backbone": "transolver"}


def propose(strategy, why="a recipe that may fit better"):
    return tool(
        PROPOSE,
        {
            "strategy_json": json.dumps(strategy),
            "hypothesis": why,
            "expected_effect": "a lower frozen-rule score than the baseline",
        },
    )


def steps(*qualities, **extra):
    """One scripted pod per quality (lower is better; the baseline is first)."""
    return [
        Step(outputs=synthetic_outputs(q), charge="0.10", **extra) for q in qualities
    ]


def provider(root, script, pods, *, grant_changes=None, miner=None, **kw):
    # Staged as the runner stages it (PROTO4-D11); pass stage_profile=None
    # for an unstaged provider.
    if "stage_profile" not in kw:
        kw["stage_profile"] = phase3.staged_profile()
    return phase3.Phase3Provider(
        root=Path(root) / "graphite",
        grant=grant(**(grant_changes or {})),
        model=ScriptedModel(script),
        pods=pods,
        miner_tools=miner if miner is not None else RecordingMinerTools(),
        clock=lambda: LEDGER_NOW,
        randomness=lambda n: b"\x01" * n,
        **kw,
    )


def controller(root, graphite):
    return phase3.controller_for(root, graphite, graphite.grant, clock=Clock())


def brief(graphite):
    return phase3.session_brief(checkout_commit="1" * 40, budget=graphite.budget)


def session(root, script, pods, number=1, **kw):
    """Run one session behind the controller; returns (result, provider, control)."""
    graphite = provider(root, script, pods, **kw)
    control = controller(root, graphite)
    try:
        result = phase3.run_session(control, graphite, brief(graphite), number)
    finally:
        control.close()
    return result, graphite, control


def run_id(number=1):
    from carbon.agent_campaign.graphite.provider import GraphiteProvider

    return GraphiteProvider.run_id_for(phase3.session_key(number))


__all__ = [
    "BASELINE",
    "PREFIX",
    "UNREBUILDABLE",
    "ScriptedPods",
    "Step",
    "propose",
    "text",
    "tool",
]
