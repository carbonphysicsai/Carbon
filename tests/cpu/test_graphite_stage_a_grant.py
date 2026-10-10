"""OWNER-GRAPHITE-STAGE-A-01: the Graphite ladder wave's stage A grants.

Claims tested:
- the two grants are the owner's figures: 5 Constructor runs at 14.91 and 4
  Attacker runs at 13.41, cleanup 0.25 split between them, ceilings summing
  to USD 128.44; `max_concurrency` 2; R4 is untouched;
- the Constructor grant admits Level 0 and above, starts the Constructor and
  Planner on kimi-k3 with R4's token share, and records its run conditions
  under stage A's authority;
- the Attacker grant starts the Attacker on kimi-k3, is refused by phase 3,
  is accepted by phase 4 for battery only, and its model money holds at
  least four full kimi-k3 reservations; battery's default phase-4 grant is
  unchanged.

No live run, key, network or spend.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import grant_binding, phase4
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.development_session.model_provider import ENGY_LADDER
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
CONSTRUCTOR = "GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR"
ATTACKER = "GRAPHITE-GRANT-STAGE-A-ATTACKER"
#: kimi-k3's full-window reservation in USD (GRAPHITE-D35).
KIMI_FULL_CALL = Decimal("2.0646912")


def _document(grant_id):
    return json.loads((GRANTS / (grant_id + ".json")).read_bytes())


def _grant(grant_id, **changes):
    return SpendingGrant.from_document(
        {**_document(grant_id), "expires_at": "2099-01-01T00:00:00Z", **changes}
    )


def _refusal(capsys, call):
    with pytest.raises(SystemExit):
        call()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]


# -- the figures -------------------------------------------------------------------------
def test_the_grants_are_the_owners_figures():
    constructor, attacker = _grant(CONSTRUCTOR), _grant(ATTACKER)
    for grant, runs, worst in ((constructor, 5, "14.91"), (attacker, 4, "13.41")):
        assert grant.worst_case_run_cost == Decimal(worst)
        assert grant.permitted_runs == runs == grant.max_submissions
        assert grant.max_concurrency == 2
        assert (
            grant.worst_case_run_cost * runs + grant.cleanup_allowance
            == grant.monetary_ceiling
        )
    assert constructor.cleanup_allowance + attacker.cleanup_allowance == Decimal("0.25")
    assert constructor.monetary_ceiling + attacker.monetary_ceiling == Decimal("128.44")
    assert _document("GRAPHITE-GRANT-PHASE3-R4")["monetary_ceiling"] == "45.00"


# -- the Constructor ---------------------------------------------------------------------
def test_the_constructor_grant_admits_level_0_on_kimi_k3():
    grant = _grant(CONSTRUCTOR)
    entry = grant_binding.entry_of(grant)
    assert entry.min_level == 0 and entry.runner == "phase3"
    assert entry.token_share_usd == grant_binding.STAGE_TOKEN_SHARE == Decimal("10.90")
    for level in (0, 1, 3):
        assert grant_binding.level_refusal(grant, level) is None
    top = len(ENGY_LADDER) - 1
    assert grant_binding.start_rungs(grant) == {
        RoleName.CONSTRUCTOR: top,
        RoleName.PLANNER: top,
    }
    conditions = grant_binding.run_conditions(grant)
    assert conditions["authority"] == grant_binding.STAGE_A_AUTHORITY
    assert conditions["min_construction_level"] == 0
    assert conditions["start_roles"] == ["constructor", "planner"]


def test_the_constructor_grant_binds_battery_and_mains_blob(tmp_path, capsys):
    grant = _grant(CONSTRUCTOR)
    path = GRANTS / (CONSTRUCTOR + ".json")
    code = _refusal(
        capsys,
        lambda: grant_binding.check_phase3_grant(
            path, grant, challenge=BATTERY_CHALLENGE, level=0, repository=tmp_path
        ),
    )
    assert code == "phase3_grant_not_committed"
    code = _refusal(
        capsys,
        lambda: grant_binding.check_phase3_grant(
            path, grant, challenge=COLD_PLATE_CHALLENGE
        ),
    )
    assert code == "grant_is_for_another_challenge"


def test_r4_keeps_its_own_conditions():
    entry = grant_binding.PHASE3_GRANTS["GRAPHITE-GRANT-PHASE3-R4"]
    assert entry.min_level == 1
    assert entry.authority == "OWNER-GRAPHITE-PHASE3-R4-01"
    assert entry.start_roles == ("constructor", "planner")


# -- the Attacker ------------------------------------------------------------------------
def test_the_attacker_grant_starts_the_attacker_on_kimi_k3_only():
    grant = _grant(ATTACKER)
    assert grant_binding.entry_of(grant).runner == "phase4"
    assert grant_binding.start_rungs(grant) == {RoleName.ATTACKER: len(ENGY_LADDER) - 1}
    below = ENGY_LADDER[0]
    assert (
        grant_binding.start_model_refusal(grant, RoleName.ATTACKER, below)
        == grant_binding.START_MODEL_REFUSED
    )
    assert grant_binding.start_model_refusal(grant, RoleName.CONSTRUCTOR, below) is None


def test_phase_3_refuses_the_attacker_grant(capsys):
    grant = _grant(ATTACKER)
    code = _refusal(
        capsys,
        lambda: grant_binding.check_phase3_grant(
            GRANTS / (ATTACKER + ".json"), grant, challenge=BATTERY_CHALLENGE
        ),
    )
    assert code == "grant_is_not_a_phase3_grant"


def test_phase_4_accepts_the_attacker_grant_for_battery_only(tmp_path, capsys):
    path = GRANTS / (ATTACKER + ".json")
    code = _refusal(
        capsys,
        lambda: phase4.check_committed_grant(
            path, tmp_path, challenge=BATTERY_CHALLENGE
        ),
    )
    assert code == "phase4_grant_not_committed"  # bound; then the blob check
    code = _refusal(
        capsys,
        lambda: phase4.check_committed_grant(
            path, tmp_path, challenge=COLD_PLATE_CHALLENGE
        ),
    )
    assert code == "grant_is_for_another_challenge"
    assert phase4.phase4_grant(BATTERY_CHALLENGE).grant_id == "GRAPHITE-GRANT-PHASE4"


def test_the_attacker_model_money_holds_four_full_kimi_k3_calls():
    scoring = challenge_scoring.scoring_for(BATTERY_CHALLENGE)
    staged = phase4.attacker_budget(_grant(ATTACKER), scoring)
    base = phase4.attacker_budget(_grant("GRAPHITE-GRANT-PHASE4"), scoring)
    assert staged.token_allowance_usd >= 4 * KIMI_FULL_CALL
    # At the standing 0.65/h ceiling the verify pods reserve more, so the model
    # money is above PHASE4's by less than 10.00, and still holds four calls.
    assert staged.token_allowance_usd > base.token_allowance_usd
