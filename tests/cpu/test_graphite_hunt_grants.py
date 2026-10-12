"""OWNER-GRAPHITE-OPEN-SAFE-01-GRANTS: the Level 5 hunt's per-run grants (H1 to H3, A1 and A2).

Claims tested:
- each file loads through the grant loader, is one run, and stays under the USD 50 per-run cap;
- the figures are the existing stage grants' worst cases (14.91 and 13.41) with no new assumption, and the five
  ceilings total no more than the owner's USD 86.71 for the hunt (H4's share is left unallocated);
- the binding registers each: Constructors at their own level only, Attackers through phase 4 at their own level only,
  all on kimi-k3, citing the owner's record.
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
RECORD = (
    REPOSITORY / ".agent/decisions/2026-10-12-OWNER-GRAPHITE-OPEN-SAFE-01-GRANTS.md"
)
HUNT_TOTAL = Decimal("86.71")  # the owner's record: USD 86.71 all in
PER_RUN_CAP = Decimal(
    50
)  # OWNER-TESTNET-WEEKLY-BUDGET-01, amended by OWNER-TEST-GRANT-01
CONSTRUCTORS = {
    "GRAPHITE-GRANT-HUNT-H1-CONSTRUCTOR": 1,
    "GRAPHITE-GRANT-HUNT-H2-CONSTRUCTOR": 2,
    "GRAPHITE-GRANT-HUNT-H3-CONSTRUCTOR": 3,
}
ATTACKERS = {"GRAPHITE-GRANT-HUNT-A1-ATTACKER": 1, "GRAPHITE-GRANT-HUNT-A2-ATTACKER": 3}


def _document(grant_id):
    return json.loads((GRANTS / (grant_id + ".json")).read_bytes())


def _grant(grant_id):
    return SpendingGrant.from_document(
        {**_document(grant_id), "expires_at": "2099-01-01T00:00:00Z"}
    )


def _refusal(capsys, call):
    with pytest.raises(SystemExit):
        call()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]


def test_the_record_states_the_hunt_figure_the_files_are_held_to():
    text = RECORD.read_text(encoding="utf-8")
    assert "L5 hunt: USD 86.71" in text and "86.71" in str(HUNT_TOTAL)


def test_each_file_loads_is_one_run_and_is_under_the_per_run_cap():
    for grant_id in (*CONSTRUCTORS, *ATTACKERS):
        grant = _grant(grant_id)
        assert grant.permitted_runs == 1 == grant.max_submissions
        assert grant.max_concurrency == 1
        assert grant.worst_case_run_cost <= PER_RUN_CAP
        assert grant.monetary_ceiling <= PER_RUN_CAP
        assert (
            grant.worst_case_run_cost + grant.cleanup_allowance
            == grant.monetary_ceiling
        )
        assert str(grant.pod_rate_ceiling_usd_per_hr) == "0.65"
        assert grant.currency == "USD"


def test_the_worst_cases_are_the_existing_stage_figures_not_new_assumptions():
    stage_constructor = _grant("GRAPHITE-GRANT-STAGE-B-CONSTRUCTOR")
    stage_attacker = _grant("GRAPHITE-GRANT-STAGE-B-ATTACKER")
    for grant_id in CONSTRUCTORS:
        grant = _grant(grant_id)
        assert grant.worst_case_run_cost == stage_constructor.worst_case_run_cost
        assert grant.max_runtime_s == stage_constructor.max_runtime_s
    for grant_id in ATTACKERS:
        grant = _grant(grant_id)
        assert grant.worst_case_run_cost == stage_attacker.worst_case_run_cost
        assert grant.max_runtime_s == stage_attacker.max_runtime_s


def test_the_ceilings_total_no_more_than_the_owners_hunt_figure():
    total = sum(
        (_grant(g).monetary_ceiling for g in (*CONSTRUCTORS, *ATTACKERS)), Decimal(0)
    )
    assert total == Decimal("71.76")
    assert total <= HUNT_TOTAL
    # The unallocated remainder is H4's share (one more Constructor run).
    assert (
        HUNT_TOTAL - total
        >= _grant("GRAPHITE-GRANT-HUNT-H1-CONSTRUCTOR").monetary_ceiling
    )
    constructors = sum((_grant(g).cleanup_allowance for g in CONSTRUCTORS), Decimal(0))
    attackers = sum((_grant(g).cleanup_allowance for g in ATTACKERS), Decimal(0))
    assert constructors <= Decimal("0.12") and attackers <= Decimal("0.13")


@pytest.mark.parametrize(("grant_id", "level"), CONSTRUCTORS.items())
def test_a_constructor_grant_admits_its_own_level_only(grant_id, level):
    grant = _grant(grant_id)
    entry = grant_binding.entry_of(grant)
    assert (entry.min_level, entry.max_level) == (level, level)
    assert entry.authority == grant_binding.HUNT_AUTHORITY
    assert entry.token_share_usd == grant_binding.STAGE_TOKEN_SHARE
    assert entry.main_blob is True and entry.runner == "phase3"
    assert grant_binding.level_refusal(grant, level) is None
    for other in (0, 1, 2, 3, 4):
        if other != level:
            assert grant_binding.level_refusal(grant, other) == (
                grant_binding.LEVEL_RANGE_REFUSED
            )
    top = len(ENGY_LADDER) - 1
    assert grant_binding.start_rungs(grant) == {
        RoleName.CONSTRUCTOR: top,
        RoleName.PLANNER: top,
    }
    assert (
        grant_binding.run_conditions(grant)["authority"] == grant_binding.HUNT_AUTHORITY
    )


@pytest.mark.parametrize(("grant_id", "level"), ATTACKERS.items())
def test_an_attacker_grant_runs_only_through_phase_4_at_its_own_level(
    tmp_path, capsys, grant_id, level
):
    grant = _grant(grant_id)
    assert grant_binding.entry_of(grant).runner == "phase4"
    assert grant_binding.start_rungs(grant) == {RoleName.ATTACKER: len(ENGY_LADDER) - 1}
    code = _refusal(
        capsys,
        lambda: grant_binding.check_phase3_grant(
            GRANTS / (grant_id + ".json"), grant, challenge=BATTERY_CHALLENGE
        ),
    )
    assert code == "grant_is_not_a_phase3_grant"
    code = _refusal(
        capsys,
        lambda: phase4.check_committed_grant(
            GRANTS / (grant_id + ".json"),
            tmp_path,
            challenge=BATTERY_CHALLENGE,
            level=level,
        ),
    )
    assert code == "phase4_grant_not_committed"  # bound; then the blob check
    for other in (0, 1, 2, 3, 4):
        if other != level:
            code = _refusal(
                capsys,
                lambda other=other: phase4.check_committed_grant(
                    GRANTS / (grant_id + ".json"),
                    tmp_path,
                    challenge=BATTERY_CHALLENGE,
                    level=other,
                ),
            )
            assert code == grant_binding.LEVEL_RANGE_REFUSED
    code = _refusal(
        capsys,
        lambda: phase4.check_committed_grant(
            GRANTS / (grant_id + ".json"),
            tmp_path,
            challenge=COLD_PLATE_CHALLENGE,
            level=level,
        ),
    )
    assert code == "grant_is_for_another_challenge"


def test_a_constructor_grant_is_for_battery_only(capsys):
    grant_id = "GRAPHITE-GRANT-HUNT-H1-CONSTRUCTOR"
    code = _refusal(
        capsys,
        lambda: grant_binding.check_phase3_grant(
            GRANTS / (grant_id + ".json"),
            _grant(grant_id),
            challenge=COLD_PLATE_CHALLENGE,
            level=1,
        ),
    )
    assert code == "grant_is_for_another_challenge"


def test_the_earlier_stage_grants_are_unchanged():
    for grant_id, ceiling in (
        ("GRAPHITE-GRANT-STAGE-B-CONSTRUCTOR", "89.58"),
        ("GRAPHITE-GRANT-STAGE-B-ATTACKER", "53.77"),
        ("GRAPHITE-GRANT-STAGE-C-CONSTRUCTOR", "44.85"),
        ("GRAPHITE-GRANT-STAGE-C-ATTACKER", "26.95"),
    ):
        assert _grant(grant_id).monetary_ceiling == Decimal(ceiling)
