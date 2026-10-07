"""OWNER-BATTERY-STUDY-SHEET-01: the battery study grant, its limits and the
sheet agree, and the arithmetic in the grant's README holds."""

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
GRANT = "TRAINING-BUDGET-GRANT-BATTERY-STUDY-01"


def load():
    grant = SpendingGrant.from_document(
        json.loads((GRANTS / f"{GRANT}.json").read_text())
    )
    limits = json.loads((GRANTS / f"{GRANT}.limits.json").read_text())
    return grant, limits


def cents(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def test_the_grant_loads_and_matches_the_sheets_ceiling():
    grant, limits = load()
    battery = sheet.load(capability_registry.BATTERY_CHALLENGE)
    assert grant.monetary_ceiling == Decimal(str(battery.get("spend_ceiling")))
    assert limits["grant_id"] == grant.grant_id == GRANT
    assert limits["challenge_id"] == battery.challenge_id
    assert limits["gpu_model"] == battery.get("gpu_model")


def test_the_ceiling_is_the_pod_hours_at_the_rate_cap_and_the_pause_is_80_percent():
    grant, limits = load()
    rate = Decimal(limits["rate_cap_usd_per_hour"])
    assert cents(limits["pod_hours"] * rate) == grant.monetary_ceiling
    assert cents(grant.monetary_ceiling * Decimal("0.8")) == Decimal(
        limits["pause_at_usd"]
    )
    assert limits["reestimate_after_phase"] == "A"


def test_the_runs_fit_the_grant():
    grant, limits = load()
    assert grant.permitted_runs == len(limits["runs"]) == grant.max_submissions
    assert grant.max_concurrency == 1
    # The largest run (Phase H) fits its time and cost bounds at the rate cap.
    rate = Decimal(limits["rate_cap_usd_per_hour"])
    assert (
        cents(Decimal(grant.max_runtime_s) / 3600 * rate) <= grant.worst_case_run_cost
    )
    assert grant.worst_case_run_cost + grant.cleanup_allowance <= grant.monetary_ceiling


def test_no_balance_or_account_identifier_is_recorded():
    for path in GRANTS.glob(f"{GRANT}*"):
        text = path.read_text().lower()
        assert "balance" not in text and "acct_" not in text and "api_key" not in text
