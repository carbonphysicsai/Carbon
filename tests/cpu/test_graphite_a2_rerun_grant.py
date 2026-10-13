"""GRAPHITE-GRANT-HUNT-A2-RERUN-ATTACKER: one Level 3 Attacker re-run of the interrupted hunt run A2.

The first A2 was interrupted by a host crash; its resume ended `reconciliation_required`, a terminal state (the
unsettled model call keeps its reservation and phase 4 has no way to settle it), so its one run is spent. This grant
is the same attack, one run, under the standing weekly test grant (OWNER-TEST-GRANT-01).

Claims tested:
- the file loads, is one run, under the USD 50 per-run cap, and is a copy of A2's figures with only the id changed;
- the binding registers it for battery through phase 4 at Level 3 only, on kimi-k3, citing the standing grant;
- the earlier hunt grants (including the original A2) are unchanged;
- it fits the weekly cap beside the owner's other open grants and the Level 4 Constructor grant.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.grant_runs import PER_RUN_CAP_USD, WEEKLY_CAP_USD
from carbon.agent_campaign.graphite import grant_binding, phase4
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.development_session.model_provider import ENGY_LADDER
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
GRANT_ID = "GRAPHITE-GRANT-HUNT-A2-RERUN-ATTACKER"
ORIGINAL = "GRAPHITE-GRANT-HUNT-A2-ATTACKER"
#: The weekly-budget record's four grants with CONFIRM-02 at its amended 37: 86.71 + 44.85 + 37 + 16.
OTHER_OPEN_GRANTS = Decimal("184.56")
LEVEL_FOUR_CONSTRUCTOR = Decimal("14.94")


def _document(grant_id):
    return json.loads((GRANTS / (grant_id + ".json")).read_bytes())


def _grant(grant_id=GRANT_ID):
    return SpendingGrant.from_document(
        {**_document(grant_id), "expires_at": "2099-01-01T00:00:00Z"}
    )


def _refusal(capsys, call):
    with pytest.raises(SystemExit):
        call()
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]


def test_the_file_is_one_run_a_copy_of_a2s_figures_under_the_per_run_cap():
    grant = _grant()
    assert grant.permitted_runs == 1 == grant.max_submissions
    assert grant.max_concurrency == 1
    assert grant.monetary_ceiling <= PER_RUN_CAP_USD
    assert grant.worst_case_run_cost + grant.cleanup_allowance == grant.monetary_ceiling
    rerun, original = _document(GRANT_ID), _document(ORIGINAL)
    assert {k: v for k, v in rerun.items() if k != "grant_id"} == {
        k: v for k, v in original.items() if k != "grant_id"
    }
    assert grant.monetary_ceiling == Decimal("13.47")
    assert grant.worst_case_run_cost == Decimal("13.41")


def test_the_original_hunt_grants_are_unchanged():
    assert _grant(ORIGINAL).monetary_ceiling == Decimal("13.47")
    assert (
        grant_binding.PHASE3_GRANTS[ORIGINAL].authority == grant_binding.HUNT_AUTHORITY
    )
    assert phase4.PHASE4_STAGE_GRANTS[ORIGINAL].levels == (3,)


def test_the_binding_registers_it_through_phase_4_on_kimi_at_the_standing_grant():
    grant = _grant()
    entry = grant_binding.entry_of(grant)
    assert entry.challenge == BATTERY_CHALLENGE and entry.main_blob is True
    assert entry.runner == "phase4" and entry.start_roles == ("attacker",)
    assert entry.start_model == "kimi-k3" == ENGY_LADDER[-1]
    assert entry.authority == grant_binding.STANDING_TEST_GRANT_AUTHORITY
    assert grant_binding.start_rungs(grant) == {RoleName.ATTACKER: len(ENGY_LADDER) - 1}
    assert phase4.PHASE4_STAGE_GRANTS[GRANT_ID].levels == (3,)


def test_a_phase_3_run_refuses_it_and_phase_4_binds_it_to_level_3_battery_only(
    tmp_path, capsys
):
    path = GRANTS / (GRANT_ID + ".json")
    grant = _grant()
    code = _refusal(
        capsys,
        lambda: grant_binding.check_phase3_grant(
            path, grant, challenge=BATTERY_CHALLENGE
        ),
    )
    assert code == "grant_is_not_a_phase3_grant"
    code = _refusal(
        capsys,
        lambda: phase4.check_committed_grant(
            path, tmp_path, challenge=BATTERY_CHALLENGE, level=3
        ),
    )
    assert code == "phase4_grant_not_committed"  # bound; then the blob check
    for other in (0, 1, 2, 4):
        code = _refusal(
            capsys,
            lambda other=other: phase4.check_committed_grant(
                path, tmp_path, challenge=BATTERY_CHALLENGE, level=other
            ),
        )
        assert code == grant_binding.LEVEL_RANGE_REFUSED
    code = _refusal(
        capsys,
        lambda: phase4.check_committed_grant(
            path, tmp_path, challenge=COLD_PLATE_CHALLENGE, level=3
        ),
    )
    assert code == "grant_is_for_another_challenge"


def test_it_fits_the_weekly_cap_beside_the_other_open_grants_and_the_level_4_grant():
    ceiling = _grant().monetary_ceiling
    total = OTHER_OPEN_GRANTS + LEVEL_FOUR_CONSTRUCTOR + ceiling
    assert total == Decimal("212.97") and total <= WEEKLY_CAP_USD
