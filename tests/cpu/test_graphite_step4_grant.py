"""The step 4 grant (CHALLENGE-PROTOCOL-04, PROTO4-D4) is complete, funds the
Attacker block only, and matches its derivation from listed Engy prices."""

from __future__ import annotations

import json
import math
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import challenge as challenges
from carbon.agent_campaign.graphite import experiment, phase4
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.battery.research import PRACTICE_SECONDS
from carbon.development_session.model_provider import DEFAULT_SETTINGS, ENGY_MODELS
from carbon.development_session.research_agent_policy import (
    MAX_PROVIDER_CALLS,
    MAX_RESEARCH_TRIALS,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANT = REPOSITORY / "docs/development/graphite/grants/GRAPHITE-GRANT-STEP4.json"
#: Battery's Attacker campaign record names the step 4 grant.
BATTERY = challenges.get("battery-fastcharge-ageing-development-v1")
CAMPAIGN = BATTERY.campaign
LIMITS = phase4.limits(BATTERY)


def _call_usd(model):
    price = ENGY_MODELS[model]
    nano = (
        DEFAULT_SETTINGS.max_input_tokens * price.input_nano
        + DEFAULT_SETTINGS.max_output_tokens * price.output_nano
    )
    return Decimal(nano) / Decimal(10) ** 9


def _grant():
    document = json.loads(GRANT.read_text())
    assert "HUMAN_INPUT" not in json.dumps(document)
    return SpendingGrant.from_document(document)


def test_the_step4_grant_is_the_owners():
    grant = _grant()
    assert grant.grant_id == CAMPAIGN["grant"]["id"] == "GRAPHITE-GRANT-STEP4"
    assert REPOSITORY / CAMPAIGN["grant"]["file"] == GRANT
    assert grant.provider == "graphite" and grant.currency == "USD"
    assert grant.account == "Carbon-Account" and grant.granted_by == "owner"
    assert grant.expires_at.isoformat() == "2026-12-31T23:59:59+00:00"
    assert grant.monetary_ceiling == Decimal("5.00")


def test_the_step4_grant_matches_its_derivation():
    grant = _grant()
    assert grant.cleanup_allowance == 0 and grant.permitted_runs == 3
    shared = (grant.monetary_ceiling - grant.cleanup_allowance) / grant.permitted_runs
    worst = Decimal(math.floor(shared * 100)) / 100
    assert grant.worst_case_run_cost == worst == Decimal("1.66")
    assert (grant.monetary_ceiling - grant.cleanup_allowance) // worst == 3
    assert ROLES[RoleName.ATTACKER].start_model == "glm-5.2"
    call = _call_usd("glm-5.2")
    turns = CAMPAIGN["session_turns"]
    assert turns == LIMITS["model_calls"] == int(worst // call) == 34
    assert turns * call <= worst
    assert MAX_PROVIDER_CALLS == 48  # the shared cap stays unchanged
    assert LIMITS["code_runs"] == phase4.MAX_CODE_RUNS == MAX_RESEARCH_TRIALS
    seconds = LIMITS["code_run_seconds_at_most"]
    assert seconds == PRACTICE_SECONDS
    assert grant.max_runtime_s == (
        turns * DEFAULT_SETTINGS.timeout_seconds + phase4.MAX_CODE_RUNS * seconds
    )
    assert grant.max_runtime_s == 8880
    assert grant.max_concurrency == 1
    assert grant.max_submissions == grant.permitted_runs
    assert Decimal(CAMPAIGN["ceiling_usd"]) + grant.cleanup_allowance <= (
        grant.monetary_ceiling
    )


def test_the_dry_run_grant_is_the_step4_grant_under_a_synthetic_identity():
    """Before the generalization the dry run carried its own copy of these
    amounts; it now copies the record's grant and changes only its names."""
    dry = phase4.dry_run_grant(BATTERY).document()
    real = _grant().document()
    changed = {key for key in real if dry[key] != real[key]}
    assert changed == {"grant_id", "account", "granted_by", "expires_at"}
    assert dry["grant_id"] == "graphite-step4-attacker-dry-run-synthetic"


def test_the_step4_grant_cannot_fund_a_constructor_session():
    """The Constructor block runs under GRAPHITE-GRANT-PHASE3; #504's runner
    refuses this grant because its run cost cannot cover a session's pods."""
    with pytest.raises(experiment.BudgetRefused):
        experiment.phase3_budget(_grant())
