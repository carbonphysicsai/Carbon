"""OWNER-GRAPHITE-STAGE-B-01: the Graphite ladder wave's stage B grants
(battery Levels 2 and 3, kimi-k3, up to 4 runs at once).

Claims tested:
- the owner's figures: 6 Constructor runs at 14.91 and 4 Attacker runs at
  13.41, cleanup 0.25 split as in stage A, ceilings summing to USD 143.35,
  `max_concurrency` 4;
- the Constructor grant admits Levels 2 and 3 only, on kimi-k3 with R4's
  token share; stage A's and R4's level rules are unchanged;
- the Attacker grant starts the Attacker on kimi-k3, is refused by phase 3,
  and phase 4 accepts it for battery at Levels 2 and 3 only.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import grant_binding, phase4
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.development_session.model_provider import ENGY_LADDER
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
CONSTRUCTOR = "GRAPHITE-GRANT-STAGE-B-CONSTRUCTOR"
ATTACKER = "GRAPHITE-GRANT-STAGE-B-ATTACKER"


def _grant(grant_id):
    document = json.loads((GRANTS / (grant_id + ".json")).read_bytes())
    return SpendingGrant.from_document(
        {**document, "expires_at": "2099-01-01T00:00:00Z"}
    )


def _refusal(capsys, call):
    with pytest.raises(SystemExit):
        call()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]


def test_the_grants_are_the_owners_figures():
    constructor, attacker = _grant(CONSTRUCTOR), _grant(ATTACKER)
    for grant, runs, worst in ((constructor, 6, "14.91"), (attacker, 4, "13.41")):
        assert grant.worst_case_run_cost == Decimal(worst)
        assert grant.permitted_runs == runs == grant.max_submissions
        assert grant.max_concurrency == 4
        assert (
            grant.worst_case_run_cost * runs + grant.cleanup_allowance
            == grant.monetary_ceiling
        )
    assert constructor.monetary_ceiling + attacker.monetary_ceiling == Decimal("143.35")


def test_the_constructor_grant_admits_levels_2_and_3_only():
    grant = _grant(CONSTRUCTOR)
    entry = grant_binding.entry_of(grant)
    assert (entry.min_level, entry.max_level) == (2, 3)
    assert entry.token_share_usd == grant_binding.STAGE_TOKEN_SHARE == Decimal("10.99")
    for level in (2, 3):
        assert grant_binding.level_refusal(grant, level) is None
    for level in (0, 1, 4, None, "2"):
        assert grant_binding.level_refusal(grant, level) == (
            grant_binding.LEVEL_RANGE_REFUSED
        )
    top = len(ENGY_LADDER) - 1
    assert grant_binding.start_rungs(grant) == {
        RoleName.CONSTRUCTOR: top,
        RoleName.PLANNER: top,
    }
    assert grant_binding.run_conditions(grant)["authority"] == (
        grant_binding.STAGE_B_AUTHORITY
    )


def test_earlier_level_rules_are_unchanged():
    r4 = grant_binding.PHASE3_GRANTS["GRAPHITE-GRANT-PHASE3-R4"]
    stage_a = grant_binding.PHASE3_GRANTS["GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR"]
    assert (r4.min_level, r4.max_level) == (1, None)
    assert (stage_a.min_level, stage_a.max_level) == (0, None)
    named = type("G", (), {"grant_id": "GRAPHITE-GRANT-PHASE3-R4"})()
    assert grant_binding.level_refusal(named, 0) == grant_binding.LEVEL_REFUSED


def test_phase_3_refuses_the_attacker_grant(capsys):
    code = _refusal(
        capsys,
        lambda: grant_binding.check_phase3_grant(
            GRANTS / (ATTACKER + ".json"), _grant(ATTACKER), challenge=BATTERY_CHALLENGE
        ),
    )
    assert code == "grant_is_not_a_phase3_grant"
    assert grant_binding.start_rungs(_grant(ATTACKER)) == {
        RoleName.ATTACKER: len(ENGY_LADDER) - 1
    }


@pytest.mark.parametrize("level", [2, 3])
def test_phase_4_accepts_the_attacker_grant_at_levels_2_and_3(tmp_path, capsys, level):
    code = _refusal(
        capsys,
        lambda: phase4.check_committed_grant(
            GRANTS / (ATTACKER + ".json"),
            tmp_path,
            challenge=BATTERY_CHALLENGE,
            level=level,
        ),
    )
    assert code == "phase4_grant_not_committed"  # bound; then the blob check


@pytest.mark.parametrize(
    ("challenge", "level", "code"),
    [
        (BATTERY_CHALLENGE, 0, grant_binding.LEVEL_RANGE_REFUSED),
        (BATTERY_CHALLENGE, 1, grant_binding.LEVEL_RANGE_REFUSED),
        (BATTERY_CHALLENGE, 4, grant_binding.LEVEL_RANGE_REFUSED),
        (COLD_PLATE_CHALLENGE, 2, "grant_is_for_another_challenge"),
    ],
)
def test_phase_4_refuses_the_attacker_grant_elsewhere(
    tmp_path, capsys, challenge, level, code
):
    assert (
        _refusal(
            capsys,
            lambda: phase4.check_committed_grant(
                GRANTS / (ATTACKER + ".json"),
                tmp_path,
                challenge=challenge,
                level=level,
            ),
        )
        == code
    )
