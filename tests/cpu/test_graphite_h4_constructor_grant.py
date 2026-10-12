"""GRAPHITE-GRANT-HUNT-H4-CONSTRUCTOR: the Level 5 hunt's Level 4 Constructor run, funded from the standing grant.

The A2 re-run consumed the unallocated H4 share of the hunt's USD 86.71 (#1163), so H4 is funded from the standing
weekly test grant (OWNER-TEST-GRANT-01), not from the hunt's record. The theme (`causal-structure`) is in the plan; the
grant binds spend, and a money grant is not a licence to run (the Level 4 gate, R1 and R8, must pass first).

Claims tested:
- the file loads, is one run, at most USD 15 and under the USD 50 per-run cap, with H3's Constructor figures;
- the binding registers it for battery at Level 4 only, on kimi-k3, citing the standing grant, beside the unchanged hunt;
- the theme the plan names is registered for Level 4;
- the weekly arithmetic of the pending grants stays within the cap.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign import grant_runs
from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import grant_binding, hunt_themes
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.development_session.model_provider import ENGY_LADDER
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
GRANT_ID = "GRAPHITE-GRANT-HUNT-H4-CONSTRUCTOR"
SIBLING = "GRAPHITE-GRANT-HUNT-H3-CONSTRUCTOR"
#: Pending grants against the weekly cap: the weekly-budget record's four (CONFIRM-02 at its amended 37) plus the Level 4
#: Constructor, the A2 re-run and this one.
OTHER_OPEN_GRANTS = Decimal("184.56")
LEVEL_FOUR_CONSTRUCTOR = Decimal("14.94")
A2_RERUN = Decimal("13.47")


def _document(grant_id):
    return json.loads((GRANTS / (grant_id + ".json")).read_bytes())


def _grant(grant_id=GRANT_ID):
    return SpendingGrant.from_document(
        {**_document(grant_id), "expires_at": "2099-01-01T00:00:00Z"}
    )


def test_the_file_is_one_run_a_copy_of_h3s_figures_under_fifteen_dollars():
    grant = _grant()
    assert grant.permitted_runs == 1 == grant.max_submissions
    assert grant.max_concurrency == 1
    assert grant.worst_case_run_cost == Decimal("14.91")
    assert grant.monetary_ceiling == Decimal("14.94") <= Decimal(15)
    assert grant.monetary_ceiling <= grant_runs.PER_RUN_CAP_USD
    assert grant.worst_case_run_cost + grant.cleanup_allowance == grant.monetary_ceiling
    rerun, sibling = _document(GRANT_ID), _document(SIBLING)
    assert {k: v for k, v in rerun.items() if k != "grant_id"} == {
        k: v for k, v in sibling.items() if k != "grant_id"
    }


def test_the_binding_registers_it_at_level_four_only_under_the_standing_grant():
    grant = _grant()
    entry = grant_binding.entry_of(grant)
    assert entry.challenge == BATTERY_CHALLENGE and entry.main_blob is True
    assert (entry.min_level, entry.max_level) == (4, 4) and entry.runner == "phase3"
    assert entry.start_model == "kimi-k3" == ENGY_LADDER[-1]
    assert entry.authority == grant_binding.STANDING_TEST_GRANT_AUTHORITY
    assert entry.token_share_usd == grant_binding.STAGE_TOKEN_SHARE
    assert grant_binding.level_refusal(grant, 4) is None
    for other in (0, 1, 2, 3):
        assert grant_binding.level_refusal(grant, other) == (
            grant_binding.LEVEL_RANGE_REFUSED
        )
    top = len(ENGY_LADDER) - 1
    assert grant_binding.start_rungs(grant) == {
        RoleName.CONSTRUCTOR: top,
        RoleName.PLANNER: top,
    }


def test_the_hunt_grants_are_unchanged_and_h4_is_not_one_of_them():
    for n, level in ((1, 1), (2, 2), (3, 3)):
        entry = grant_binding.PHASE3_GRANTS[f"GRAPHITE-GRANT-HUNT-H{n}-CONSTRUCTOR"]
        assert (entry.min_level, entry.max_level) == (level, level)
        assert entry.authority == grant_binding.HUNT_AUTHORITY
    assert (
        grant_binding.PHASE3_GRANTS[GRANT_ID].authority != grant_binding.HUNT_AUTHORITY
    )


def test_it_is_for_battery_only(capsys):
    with pytest.raises(SystemExit):
        grant_binding.check_phase3_grant(
            GRANTS / (GRANT_ID + ".json"),
            _grant(),
            challenge=COLD_PLATE_CHALLENGE,
            level=4,
        )
    reason = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]
    assert reason == "grant_is_for_another_challenge"


def test_the_plans_theme_is_registered_for_level_four():
    theme = hunt_themes.THEMES["causal-structure"]
    assert 4 in theme["levels"]


def test_the_pending_grants_stay_within_the_weekly_cap():
    total = (
        OTHER_OPEN_GRANTS
        + LEVEL_FOUR_CONSTRUCTOR
        + A2_RERUN
        + _grant().monetary_ceiling
    )
    assert total == Decimal("227.91") and total <= grant_runs.WEEKLY_CAP_USD
