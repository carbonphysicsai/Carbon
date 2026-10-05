"""Shared fixtures for the Graphite harness tests (GRAPHITE-01 phase 1).

A scripted model, synthetic charges and an in-process controller: no live
inference, no API key, no network and no spend.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from carbon.agent_campaign import boundaries
from carbon.agent_campaign import controller as ctl
from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite.model import ScriptedModel, text, tool
from carbon.agent_campaign.graphite.provider import GraphiteProvider, SessionBrief
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.agent_campaign.provider import TaskSpec

REPOSITORY = Path(__file__).resolve().parents[2]
PROFILE = "sha256:" + "a" * 64
#: A synthetic commit id: the record binds whatever commit the checkout was
#: built from; the tests need only its shape.
FIXTURE_COMMIT = "1" * 40
CHECKOUT = boundaries.manifest_digest(
    boundaries.checkout_manifest(REPOSITORY, boundaries.Role.CONSTRUCTION)
)
#: The time the research ledger sees (unix seconds) and the controller's.
LEDGER_NOW = 1000.0


def grant_document(**changes):
    document = {
        "schema": "carbon.agent-campaign.spending-grant.v1",
        "grant_id": "graphite-test-grant",
        "provider": "graphite",
        "account": "test-account",
        "granted_by": "test-owner",
        "expires_at": "2099-01-01T00:00:00Z",
        "currency": "USD",
        "monetary_ceiling": "10.00",
        "cleanup_allowance": "1.00",
        "worst_case_run_cost": "0.50",
        "permitted_runs": 10,
        "max_concurrency": 2,
        "max_runtime_s": 3600,
        "max_submissions": 10,
    }
    document.update(changes)
    return document


def grant(**changes):
    return SpendingGrant.from_document(grant_document(**changes))


class Clock:
    def __init__(self):
        self.now = datetime.datetime(2026, 10, 2, 12, 0, 0, tzinfo=datetime.UTC)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += datetime.timedelta(seconds=seconds)


def reader_script():
    """A Reader session: search, read a card, then a written report."""
    return [
        tool("lit_search", {"query": "operator surrogate"}),
        tool("lit_card", {"card_id": "fixture-operator-0001"}),
        text("Report: one synthetic fixture card; no claim is made."),
    ]


def provider(root, model=None, *, grant_changes=None, **kw):
    return GraphiteProvider(
        root=Path(root),
        grant=grant(**(grant_changes or {})),
        model=model if model is not None else ScriptedModel(reader_script()),
        clock=lambda: LEDGER_NOW,
        **kw,
    )


def brief(role=RoleName.READER, observation=None):
    return SessionBrief(
        role=role,
        initial_observation=observation
        or {"objective": "synthetic harness fixture", "challenge": "fixture"},
        checkout_commit=FIXTURE_COMMIT,
        checkout_manifest_digest=CHECKOUT,
    )


def spec(graphite, session_brief=None, campaign="c1", max_runtime_s=3600):
    session_brief = session_brief or brief()
    return TaskSpec(
        campaign_id=campaign,
        role=ROLES[session_brief.role].boundary.value,
        workspace_id="ws-" + campaign,
        credential_ref="cred-" + campaign,
        profile_digest=PROFILE,
        instructions_digest=graphite.register_brief(session_brief),
        max_runtime_s=max_runtime_s,
    )


def controller(root, graphite, clock=None, crash_at=None):
    return ctl.CampaignController(
        root=Path(root) / "controller",
        provider=graphite,
        grant=graphite.grant,
        operator="carbon-operator",
        clock=clock or Clock(),
        crash_at=crash_at,
    )


def register(control, campaign="c1", role=RoleName.READER, ceiling="5.00"):
    control.register_campaign(
        campaign,
        role=ROLES[role].boundary,
        workspace_id="ws-" + campaign,
        credential_ref="cred-" + campaign,
        checkout_digest=CHECKOUT,
        profile_digest=PROFILE,
        ceiling=ceiling,
    )


def started(root, model=None, role=RoleName.READER, key="k1", observation=None, **kw):
    """A provider with one opened session; returns (provider, run_id)."""
    graphite = provider(root, model, **kw)
    session_brief = brief(role, observation=observation)
    handle = graphite.start(spec(graphite, session_brief), key)
    return graphite, handle.provider_run_id


class RecordingMinerTools:
    """A stand-in for the closed miner SDK: records each delegated call and
    answers from a table. It runs nothing."""

    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or {}

    async def call(self, name, arguments, identity):
        self.calls.append((name, arguments, identity))
        return self.answers.get(name, {"status": "OK", "fixture": True})
