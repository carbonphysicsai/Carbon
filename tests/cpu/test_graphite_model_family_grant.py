"""GRAPHITE-GRANT-MODEL-QWEN-CONSTRUCTOR-1: one short Constructor session on an open-weight model, standing test grant.

Claims tested:
- the file loads through the grant loader, is one run, at most USD 15 and under the per-run cap, with the figures of the
  existing Level 4 Constructor grants (no new assumption);
- the binding registers it for battery at Levels 0 to 3 only, under the standing test grant, on the Engy provider, with
  qwen3.8-27b as the start model (a floor: a session may not open below it);
- qwen3.8-27b is on the Engy ladder with a recorded rate and context, so no new key or provider registration is needed;
- the README index lists it with a distinct purpose, and every grant the binding registers under the standing test grant
  still fits the effective weekly cap beside the owner's other open grants, without touching the ledger.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from carbon.agent_campaign import grant_runs
from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.grant_runs import PER_RUN_CAP_USD, WEEKLY_CAP_USD
from carbon.agent_campaign.graphite import grant_binding, model_providers
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.development_session.model_provider import (
    ENGY_CONTEXT_TOKENS,
    ENGY_LADDER,
    ENGY_MODELS,
)
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
GRANT_ID = "GRAPHITE-GRANT-MODEL-QWEN-CONSTRUCTOR-1"
MODEL = "qwen3.8-27b"
#: The weekly-budget record's other open grants (CONFIRM-02 at its amended 37), as in the Level 4 grant tests.
OTHER_OPEN_GRANTS = Decimal("184.56")


def _grant(grant_id=GRANT_ID):
    document = json.loads((GRANTS / (grant_id + ".json")).read_bytes())
    return SpendingGrant.from_document(
        {**document, "expires_at": "2099-01-01T00:00:00Z"}
    )


def test_the_file_is_one_run_at_most_fifteen_dollars_with_the_existing_figures():
    grant, level_four = _grant(), _grant("GRAPHITE-GRANT-L4-G-CONSTRUCTOR-3")
    assert grant.permitted_runs == 1 == grant.max_submissions
    assert grant.max_concurrency == 1 and grant.currency == "USD"
    assert grant.monetary_ceiling <= Decimal("14.94")
    assert grant.monetary_ceiling <= PER_RUN_CAP_USD
    assert grant.worst_case_run_cost + grant.cleanup_allowance == grant.monetary_ceiling
    for name in (
        "monetary_ceiling",
        "worst_case_run_cost",
        "cleanup_allowance",
        "max_runtime_s",
        "pod_rate_ceiling_usd_per_hr",
        "provider",
    ):
        assert getattr(grant, name) == getattr(level_four, name), name


def test_the_binding_registers_it_for_levels_zero_to_three_on_the_engy_ladder():
    grant = _grant()
    entry = grant_binding.entry_of(grant)
    assert entry.challenge == BATTERY_CHALLENGE and entry.main_blob is True
    assert (entry.min_level, entry.max_level) == (0, 3)
    assert entry.authority == grant_binding.STANDING_TEST_GRANT_AUTHORITY
    assert entry.start_model == MODEL and entry.runner == "phase3"
    for level in (0, 1, 2, 3):
        assert grant_binding.level_refusal(grant, level) is None
    assert grant_binding.level_refusal(grant, 4) == grant_binding.LEVEL_RANGE_REFUSED
    assert grant_binding.run_conditions(grant)["authority"] == "OWNER-TEST-GRANT-01"
    # No new provider or key: the default (Engy) provider, whose ladder holds the model with a recorded rate and context.
    assert (
        grant_binding.model_provider_of(grant) == grant_binding.DEFAULT_MODEL_PROVIDER
    )
    assert (
        MODEL in ENGY_LADDER and MODEL in ENGY_MODELS and MODEL in ENGY_CONTEXT_TOKENS
    )
    assert (
        model_providers.resolve("engy").context_tokens[MODEL]
        == ENGY_CONTEXT_TOKENS[MODEL]
    )


def test_the_start_model_is_a_floor_a_session_may_not_open_below():
    grant = _grant()
    rung = ENGY_LADDER.index(MODEL)
    assert grant_binding.start_rungs(grant) == {
        RoleName.CONSTRUCTOR: rung,
        RoleName.PLANNER: rung,
    }
    below = ENGY_LADDER[rung - 1]
    assert (
        grant_binding.start_model_refusal(grant, RoleName.CONSTRUCTOR, below)
        == grant_binding.START_MODEL_REFUSED
    )
    assert grant_binding.start_model_refusal(grant, RoleName.CONSTRUCTOR, MODEL) is None


def test_the_readme_index_lists_it_with_a_distinct_purpose():
    text = (GRANTS / "README.md").read_text(encoding="utf-8")
    section = text[text.index("## Model-family test grants (index)") :]
    section = section[: section.index("\n## ", 5)]
    rows = [
        [c.strip() for c in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("| GRAPHITE-GRANT-")
    ]
    row = next(r for r in rows if r[0] == GRANT_ID)
    assert row[4] == grant_binding.STANDING_TEST_GRANT_AUTHORITY
    assert Decimal(row[5]) == _grant().monetary_ceiling and row[3]


def test_every_standing_grant_still_fits_the_effective_weekly_cap():
    standing = [
        _grant(grant_id)
        for grant_id, registered in grant_binding.PHASE3_GRANTS.items()
        if registered.authority == grant_binding.STANDING_TEST_GRANT_AUTHORITY
    ]
    assert GRANT_ID in {g.grant_id for g in standing}
    effective = WEEKLY_CAP_USD - sum(grant_runs.HELD_RESERVES.values())
    assert grant_runs.effective_weekly_cap() == effective
    assert OTHER_OPEN_GRANTS + sum(g.monetary_ceiling for g in standing) <= effective
