"""The step 4 grant (CHALLENGE-PROTOCOL-04) is complete and matches its
derivation from listed Engy prices."""

from __future__ import annotations

import json
import math
from decimal import Decimal
from pathlib import Path

from carbon.agent_campaign.grant import SpendingGrant
from carbon.development_session.model_provider import DEFAULT_SETTINGS, ENGY_MODELS
from carbon.development_session.research_agent_policy import (
    MAX_PROVIDER_CALLS,
    MAX_RESEARCH_TRIALS,
)

GRANT = (
    Path(__file__).resolve().parents[2]
    / "docs/development/graphite/grants/GRAPHITE-GRANT-STEP4.json"
)
#: The per-role call cap the Attacker is held to (ticket slice 2).
ATTACKER_CALLS = 16
#: The battery construction contract envelope's wall-clock per trial.
TRIAL_SECONDS = 600
PROVIDER_TIMEOUT_S = 120


def _call_usd(model):
    price = ENGY_MODELS[model]
    nano = (
        DEFAULT_SETTINGS.max_input_tokens * price.input_nano
        + DEFAULT_SETTINGS.max_output_tokens * price.output_nano
    )
    return Decimal(nano) / Decimal(10) ** 9


def test_the_step4_grant_is_complete_and_matches_its_derivation():
    document = json.loads(GRANT.read_text())
    grant = SpendingGrant.from_document(document)
    assert grant.provider == "graphite" and grant.currency == "USD"
    assert grant.monetary_ceiling == Decimal("5.00") and grant.cleanup_allowance == 0
    constructor = MAX_PROVIDER_CALLS * _call_usd("deepseek-v4-flash-0731")
    attacker = ATTACKER_CALLS * _call_usd("glm-5.2")
    worst = Decimal(math.ceil(max(constructor, attacker) * 100)) / 100
    assert grant.worst_case_run_cost == worst == Decimal("0.77")
    assert grant.permitted_runs == int(grant.monetary_ceiling // worst) == 6
    assert grant.max_submissions >= grant.permitted_runs
    assert grant.max_runtime_s == MAX_PROVIDER_CALLS * PROVIDER_TIMEOUT_S + (
        MAX_RESEARCH_TRIALS * TRIAL_SECONDS
    )
    assert "HUMAN_INPUT" not in json.dumps(document)
