"""OWNER-BATTERY-STUDY-4090-01: the battery study grant (-02), its limits and
the sheet agree, the arithmetic in the grant's README holds, and the
superseded A40 grant (-01) no longer matches the sheet."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from carbon.agent_campaign.grant import SpendingGrant
from carbon.reconstruction import capability_registry
from carbon.training_budget import sheet

GRANTS = (
    Path(__file__).resolve().parents[2]
    / "docs/development/training_budget_study/grants"
)
GRANT = "TRAINING-BUDGET-GRANT-BATTERY-STUDY-02"
SUPERSEDED = "TRAINING-BUDGET-GRANT-BATTERY-STUDY-01"


def load(grant_id=GRANT):
    grant = SpendingGrant.from_document(
        json.loads((GRANTS / f"{grant_id}.json").read_text())
    )
    limits = json.loads((GRANTS / f"{grant_id}.limits.json").read_text())
    return grant, limits


def cents(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def battery():
    return sheet.load(capability_registry.BATTERY_CHALLENGE)


def test_the_grant_loads_and_matches_the_sheets_ceiling():
    grant, limits = load()
    assert grant.provider == "runpod"
    assert grant.monetary_ceiling == cents(str(battery().get("spend_ceiling")))
    assert limits["grant_id"] == grant.grant_id == GRANT
    assert limits["challenge_id"] == battery().challenge_id
    assert limits["gpu_model"] == battery().get("gpu_model") == "nvidia-rtx-4090"
    assert limits["legs"][0]["gpu_model"] == limits["gpu_model"]
    assert limits["supersedes"] == SUPERSEDED
    assert limits["cloud_type"] == "COMMUNITY"


def test_the_ceiling_is_each_legs_pod_hours_at_its_rate_cap_and_the_pause_is_80():
    grant, limits = load()
    total = sum(
        Decimal(leg["rate_cap_usd_per_hour"]) * leg["pod_hours"]
        for leg in limits["legs"]
    )
    assert cents(total) == grant.monetary_ceiling == Decimal("34.80")
    assert cents(grant.monetary_ceiling * Decimal("0.8")) == Decimal(
        limits["pause_at_usd"]
    )
    assert limits["reestimate_after_phase"] == "A"


def test_the_runs_fit_the_grant():
    grant, limits = load()
    runs = [run for leg in limits["legs"] for run in leg["runs"]]
    assert len(set(runs)) == len(runs)
    assert grant.permitted_runs == len(runs) == grant.max_submissions
    assert grant.max_concurrency == 1
    # The largest run (Phase H, on the 4090 leg) fits its time and cost bounds.
    main = limits["legs"][0]
    assert "H" in main["runs"]
    rate = Decimal(main["rate_cap_usd_per_hour"])
    assert (
        cents(Decimal(grant.max_runtime_s) / 3600 * rate) <= grant.worst_case_run_cost
    )
    # The A100 leg's whole allowance is below one worst-case run.
    for leg in limits["legs"][1:]:
        cost = Decimal(leg["rate_cap_usd_per_hour"]) * leg["pod_hours"]
        assert cost <= grant.worst_case_run_cost
    assert grant.worst_case_run_cost + grant.cleanup_allowance <= grant.monetary_ceiling


def test_the_sheets_memory_ceiling_leaves_the_4090_headroom():
    ceiling = battery().get("memory_ceiling")
    assert ceiling == 20 * 2**30 < limits_memory_bytes("nvidia-rtx-4090")


def limits_memory_bytes(gpu_model):
    (leg,) = (leg for leg in load()[1]["legs"] if leg["gpu_model"] == gpu_model)
    return leg["memory_gb"] * 10**9


def test_the_a40_grant_is_superseded_and_no_longer_matches_the_sheet():
    grant, limits = load(SUPERSEDED)
    assert grant.monetary_ceiling != cents(str(battery().get("spend_ceiling")))
    assert limits["gpu_model"] != battery().get("gpu_model")


def test_no_balance_or_account_identifier_is_recorded():
    for path in GRANTS.glob("TRAINING-BUDGET-GRANT-BATTERY-STUDY-*"):
        text = path.read_text().lower()
        assert "balance" not in text and "acct_" not in text and "api_key" not in text
