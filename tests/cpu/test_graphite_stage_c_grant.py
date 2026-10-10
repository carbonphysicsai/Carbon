"""OWNER-GRAPHITE-STAGE-C-01: stage C's grants, battery Level 4 only."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import grant_binding, phase4
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

GRANTS = Path(__file__).resolve().parents[2] / grant_binding.GRANTS_DIR
CONSTRUCTOR = "GRAPHITE-GRANT-STAGE-C-CONSTRUCTOR"
ATTACKER = "GRAPHITE-GRANT-STAGE-C-ATTACKER"


def _grant(grant_id):
    document = json.loads((GRANTS / (grant_id + ".json")).read_bytes())
    return SpendingGrant.from_document(
        {**document, "expires_at": "2099-01-01T00:00:00Z"}
    )


def test_the_grants_are_the_owners_figures():
    constructor, attacker = _grant(CONSTRUCTOR), _grant(ATTACKER)
    for grant, runs, worst in ((constructor, 3, "14.91"), (attacker, 2, "13.41")):
        assert grant.worst_case_run_cost == Decimal(worst)
        assert grant.permitted_runs == runs == grant.max_submissions
        assert grant.max_concurrency == 4
        assert (
            grant.worst_case_run_cost * runs + grant.cleanup_allowance
            == grant.monetary_ceiling
        )
    assert constructor.monetary_ceiling + attacker.monetary_ceiling == Decimal("71.80")


def test_the_constructor_grant_admits_level_4_only():
    grant = _grant(CONSTRUCTOR)
    assert grant_binding.level_refusal(grant, 4) is None
    for level in (0, 1, 2, 3, 5, None):
        assert (
            grant_binding.level_refusal(grant, level)
            == grant_binding.LEVEL_RANGE_REFUSED
        )
    assert (
        grant_binding.run_conditions(grant)["authority"]
        == grant_binding.STAGE_C_AUTHORITY
    )


@pytest.mark.parametrize(
    ("level", "code"),
    [(4, "phase4_grant_not_committed"), (3, grant_binding.LEVEL_RANGE_REFUSED)],
)
def test_phase_4_takes_the_attacker_grant_at_level_4_only(
    tmp_path, capsys, level, code
):
    with pytest.raises(SystemExit):
        phase4.check_committed_grant(
            GRANTS / (ATTACKER + ".json"),
            tmp_path,
            challenge=BATTERY_CHALLENGE,
            level=level,
        )
    assert (
        json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]
        == code
    )
