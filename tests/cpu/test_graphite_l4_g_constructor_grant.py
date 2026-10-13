"""GRAPHITE-GRANT-L4-G-CONSTRUCTOR-2: one lane G Level 4 Constructor run under the standing weekly test grant.

Claims tested:
- the file loads through the grant loader, is one run, kimi-k3 binding, at most USD 15 and under the USD 50 per-run cap;
- its figures are the existing Constructor grant's (14.91 worst case plus the 0.03 cleanup, the same run time): no new
  assumption, and it is its own grant, not the Level 5 hunt's H4 share (the hunt grants are unchanged);
- the binding registers it for battery at Level 4 only, citing the standing test grant's committed record;
- it fits the weekly cap logic beside the owner's other open grants, without touching the ledger.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign import grant_runs
from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.grant_runs import PER_RUN_CAP_USD, WEEKLY_CAP_USD
from carbon.agent_campaign.graphite import grant_binding, score_lab_research
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.development_session.model_provider import ENGY_LADDER
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / grant_binding.GRANTS_DIR
GRANT_ID = "GRAPHITE-GRANT-L4-G-CONSTRUCTOR-2"
RECORD = REPOSITORY / ".agent/decisions/2026-10-11-OWNER-TESTNET-WEEKLY-BUDGET-01.md"
RUN_LIMIT = Decimal(
    15
)  # the Test Lead's decision: worst case and ceiling at most USD 15
#: The weekly-budget record lists 86.71 + 44.85 + 25 + 16 = 172.56; the owner then amended CONFIRM-02 from 25 to 37
#: (`.agent/decisions/2026-10-12-OWNER-SCORE-PROOF-CONFIRM-02-GRANT.md`): 86.71 + 44.85 + 37 + 16 = 184.56.
OTHER_OPEN_GRANTS = Decimal("184.56")


def _grant(grant_id=GRANT_ID):
    document = json.loads((GRANTS / (grant_id + ".json")).read_bytes())
    return SpendingGrant.from_document(
        {**document, "expires_at": "2099-01-01T00:00:00Z"}
    )


def test_the_standing_grants_record_states_the_terms_the_file_is_held_to():
    text = RECORD.read_text(encoding="utf-8")
    assert "OWNER-TEST-GRANT-01" in text
    assert (
        "USD 300 per rolling seven days" in text
        and "Per-run safety cap: USD 50" in text
    )
    assert "172.56" in text
    assert PER_RUN_CAP_USD == Decimal(50) and WEEKLY_CAP_USD == Decimal(300)


def test_the_file_is_one_run_at_most_fifteen_dollars_and_under_the_per_run_cap():
    grant = _grant()
    assert grant.permitted_runs == 1 == grant.max_submissions
    assert grant.max_concurrency == 1
    assert grant.worst_case_run_cost <= RUN_LIMIT
    assert grant.monetary_ceiling <= RUN_LIMIT
    assert grant.monetary_ceiling <= PER_RUN_CAP_USD
    assert grant.worst_case_run_cost + grant.cleanup_allowance == grant.monetary_ceiling
    assert str(grant.pod_rate_ceiling_usd_per_hr) == "0.65" and grant.currency == "USD"


def test_the_figures_are_the_existing_constructor_grants_not_new_assumptions():
    grant, stage = _grant(), _grant("GRAPHITE-GRANT-STAGE-C-CONSTRUCTOR")
    assert grant.worst_case_run_cost == stage.worst_case_run_cost == Decimal("14.91")
    assert grant.max_runtime_s == stage.max_runtime_s
    assert grant.pod_rate_ceiling_usd_per_hr == stage.pod_rate_ceiling_usd_per_hr
    assert grant.cleanup_allowance == Decimal(
        "0.03"
    ) and grant.monetary_ceiling == Decimal("14.94")


def test_it_is_its_own_grant_and_the_hunt_grants_are_unchanged():
    hunt_h3 = _grant("GRAPHITE-GRANT-HUNT-H3-CONSTRUCTOR")
    assert hunt_h3.monetary_ceiling == Decimal("14.94")
    assert grant_binding.PHASE3_GRANTS[
        "GRAPHITE-GRANT-HUNT-H3-CONSTRUCTOR"
    ].authority == (grant_binding.HUNT_AUTHORITY)
    assert GRANT_ID not in {g for g in grant_binding.PHASE3_GRANTS if "HUNT" in g}


def test_the_binding_registers_it_for_battery_at_level_four_only():
    grant = _grant()
    entry = grant_binding.entry_of(grant)
    assert entry.challenge == BATTERY_CHALLENGE and entry.main_blob is True
    assert (entry.min_level, entry.max_level) == (4, 4)
    assert (
        entry.authority
        == grant_binding.STANDING_TEST_GRANT_AUTHORITY
        == "OWNER-TEST-GRANT-01"
    )
    assert entry.token_share_usd == grant_binding.STAGE_TOKEN_SHARE
    assert (
        entry.start_model == "kimi-k3" == ENGY_LADDER[-1] and entry.runner == "phase3"
    )
    assert grant_binding.level_refusal(grant, 4) is None
    for other in (0, 1, 2, 3):
        assert (
            grant_binding.level_refusal(grant, other)
            == grant_binding.LEVEL_RANGE_REFUSED
        )
    top = len(ENGY_LADDER) - 1
    assert grant_binding.start_rungs(grant) == {
        RoleName.CONSTRUCTOR: top,
        RoleName.PLANNER: top,
    }
    assert grant_binding.run_conditions(grant)["authority"] == "OWNER-TEST-GRANT-01"


def test_the_grant_is_for_battery_only(capsys):
    with pytest.raises(SystemExit):
        grant_binding.check_phase3_grant(
            GRANTS / (GRANT_ID + ".json"),
            _grant(),
            challenge=COLD_PLATE_CHALLENGE,
            level=4,
        )
    reason = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]
    assert reason == "grant_is_for_another_challenge"


def test_it_fits_the_weekly_cap_beside_the_owners_other_open_grants():
    grant = _grant()
    # The other open grants total 184.56 of the 300 per rolling week (CONFIRM-02 at 37); this one adds its ceiling.
    assert OTHER_OPEN_GRANTS + grant.monetary_ceiling <= WEEKLY_CAP_USD


@pytest.mark.parametrize(
    "rerun_id",
    ["GRAPHITE-GRANT-L4-G-CONSTRUCTOR-3", "GRAPHITE-GRANT-L4-G-CONSTRUCTOR-4"],
)
def test_the_rerun_grant_is_the_same_grant_again_and_fits_the_effective_weekly_cap(
    rerun_id,
):
    """-3 is -2 again (the run under -2 was spent without staging): every figure equal, nothing above the 14.94 ceiling.
    The owner's other open grants plus every grant the binding registers under the standing test grant (-2, -3 and the
    A2 re-run) stay under the effective cap (300 less the held reserves).
    """
    first, again = _grant(), _grant(rerun_id)
    for name in (
        "monetary_ceiling",
        "worst_case_run_cost",
        "cleanup_allowance",
        "permitted_runs",
        "max_concurrency",
        "max_runtime_s",
        "max_submissions",
        "pod_rate_ceiling_usd_per_hr",
        "currency",
        "provider",
    ):
        assert getattr(again, name) == getattr(first, name), name
    assert (
        again.monetary_ceiling == Decimal("14.94") and again.grant_id != first.grant_id
    )
    entry, other = (
        grant_binding.PHASE3_GRANTS[again.grant_id],
        grant_binding.PHASE3_GRANTS[first.grant_id],
    )
    assert (entry.min_level, entry.max_level) == (4, 4)
    assert (
        entry.authority
        == other.authority
        == grant_binding.STANDING_TEST_GRANT_AUTHORITY
    )
    assert entry.start_model == other.start_model == "kimi-k3"
    held = sum(grant_runs.HELD_RESERVES.values())
    effective = WEEKLY_CAP_USD - held
    assert grant_runs.effective_weekly_cap() == effective
    standing = [
        _grant(grant_id)
        for grant_id, registered in grant_binding.PHASE3_GRANTS.items()
        if registered.authority == grant_binding.STANDING_TEST_GRANT_AUTHORITY
    ]
    assert {g.grant_id for g in standing} >= {
        first.grant_id,
        again.grant_id,
        "GRAPHITE-GRANT-HUNT-A2-RERUN-ATTACKER",
    }
    # The Score Lab research grant is a closed-task grant under the same standing authority; it is not in the
    # phase 3 binding, so its ceiling is added from the module's own whitelist.
    research = [
        _grant(grant_id) for grant_id in sorted(score_lab_research.RESEARCH_GRANTS)
    ]
    assert research and all(g.monetary_ceiling <= Decimal("14.94") for g in research)
    total = sum(g.monetary_ceiling for g in standing) + sum(
        g.monetary_ceiling for g in research
    )
    assert OTHER_OPEN_GRANTS + total <= effective


def _index_rows():
    text = (GRANTS / "README.md").read_text(encoding="utf-8")
    section = text[text.index("## Level 4 Constructor grants (index)") :]
    section = section[: section.index("\n## ", 5)]
    rows = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 7 and cells[0].startswith("GRAPHITE-GRANT-"):
            rows[cells[0]] = {
                "level": cells[1],
                "lane": cells[2],
                "purpose": cells[3],
                "authority": cells[4],
                "ceiling": Decimal(cells[5]),
            }
    return rows


def test_the_grants_index_lists_every_level_4_constructor_grant_with_its_pool():
    rows = _index_rows()
    level_four = {
        grant_id: entry
        for grant_id, entry in grant_binding.PHASE3_GRANTS.items()
        if entry.runner == "phase3" and entry.min_level == entry.max_level == 4
    }
    assert set(rows) == set(level_four)
    purposes = [row["purpose"] for row in rows.values()]
    assert len(set(purposes)) == len(purposes) and all(purposes)
    for grant_id, entry in level_four.items():
        assert rows[grant_id]["authority"] == entry.authority
        assert rows[grant_id]["level"] == "4"
        assert rows[grant_id]["ceiling"] == _grant(grant_id).monetary_ceiling
    pools = {}
    for row in rows.values():
        pools[row["authority"]] = (
            pools.get(row["authority"], Decimal(0)) + row["ceiling"]
        )
    assert pools[grant_binding.STANDING_TEST_GRANT_AUTHORITY] == Decimal("44.82")
    assert pools[grant_binding.HUNT_AUTHORITY] == Decimal("14.94")
