"""GRANT-POD-CEILING-01: a grant may carry its own pod rate ceiling; every
existing grant keeps its document, digest and behaviour."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import GrantError, SpendingGrant
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import pods as podlib

REPOSITORY = Path(__file__).resolve().parents[2]
GRANT_FILES = sorted(
    p
    for folder in (
        "docs/development/graphite/grants",
        "docs/development/training_budget_study/grants",
    )
    for p in (REPOSITORY / folder).glob("*.json")
    if "limits" not in p.name
)


def _document(**changes):
    document = json.loads(
        (
            REPOSITORY
            / "docs/development/graphite/grants/GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR.json"
        ).read_text()
    )
    return {**document, "expires_at": "2099-01-01T00:00:00Z", **changes}


@pytest.mark.parametrize("path", GRANT_FILES, ids=lambda p: p.name)
def test_every_committed_grant_is_unchanged(path):
    document = json.loads(path.read_text())
    grant = SpendingGrant.from_document(document)
    # The standing 0.65/h ceiling is on the stage grants only (owner-confirmed).
    expected = (
        Decimal("0.65") if path.name.startswith("GRAPHITE-GRANT-STAGE-") else None
    )
    assert grant.pod_rate_ceiling_usd_per_hr == expected
    assert grant.document() == document


def test_a_grant_may_name_its_pod_rate_ceiling():
    grant = SpendingGrant.from_document(_document(pod_rate_ceiling_usd_per_hr="0.65"))
    assert grant.pod_rate_ceiling_usd_per_hr == Decimal("0.65")
    assert grant.document()["pod_rate_ceiling_usd_per_hr"] == "0.65"


@pytest.mark.parametrize("value", ["0", "0.00", "-1", "x", 0.65, None])
def test_a_bad_pod_rate_ceiling_is_refused(value):
    with pytest.raises(GrantError):
        SpendingGrant.from_document(_document(pod_rate_ceiling_usd_per_hr=value))


def test_an_unknown_field_is_still_refused():
    with pytest.raises(GrantError):
        SpendingGrant.from_document(_document(pod_rate=1))


def _r3(**changes):
    document = json.loads(
        (
            REPOSITORY
            / "docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3-R3.json"
        ).read_text()
    )
    return SpendingGrant.from_document(
        {**document, "expires_at": "2099-01-01T00:00:00Z", **changes}
    )


def _battery():
    from carbon.challenge_validator.scoring import scoring_for
    from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

    return scoring_for(BATTERY_CHALLENGE)


def test_the_ceiling_reaches_pod_prices_and_the_run_budget():
    base = podlib.prices()
    raised = podlib.prices(Decimal("0.65"))
    assert raised["rate_ceiling_usd_per_hr"] == Decimal("0.65")
    assert raised["hourly_usd"] - base["hourly_usd"] == (
        Decimal("0.65") - base["rate_ceiling_usd_per_hr"]
    )
    assert ex.phase3_budget(_r3(), _battery()).hourly_usd == base["hourly_usd"]
    named = _r3(pod_rate_ceiling_usd_per_hr="0.65")
    assert ex.phase3_budget(named, _battery()).hourly_usd == raised["hourly_usd"]


#: kimi-k3's full-window reservation in USD (GRAPHITE-D35).
KIMI_FULL_CALL = Decimal("2.0646912")
STAGES = ("A", "B", "C")


def _stage(name):
    document = json.loads(
        (
            REPOSITORY
            / "docs/development/graphite/grants"
            / f"GRAPHITE-GRANT-STAGE-{name}.json"
        ).read_text()
    )
    return SpendingGrant.from_document(
        {**document, "expires_at": "2099-01-01T00:00:00Z"}
    )


def test_a_raised_ceiling_under_r4s_token_share_is_refused_not_silently_shrunk():
    """R4's 11.93 token share of a 14.91 run at 0.65 an hour leaves the
    session's pods too little: the run is refused before anything opens."""
    r4 = json.loads(
        (
            REPOSITORY
            / "docs/development/graphite/grants/GRAPHITE-GRANT-PHASE3-R4.json"
        ).read_text()
    )
    raised = SpendingGrant.from_document(
        {
            **r4,
            "expires_at": "2099-01-01T00:00:00Z",
            "pod_rate_ceiling_usd_per_hr": "0.65",
        }
    )
    with pytest.raises(ex.BudgetRefused) as refused:
        ex.phase3_budget(raised, _battery())
    assert refused.value.code == "grant_token_share_leaves_too_little_for_pods"


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_constructor_runs_at_the_standing_ceiling(stage):
    budget = ex.phase3_budget(_stage(f"{stage}-CONSTRUCTOR"), _battery())
    assert budget.hourly_usd == podlib.prices(Decimal("0.65"))["hourly_usd"]
    assert budget.pod_allowance_usd >= budget.pods_need_usd
    assert budget.token_allowance_usd == Decimal("10.99") >= 5 * KIMI_FULL_CALL
    # 10.99 is the largest share that fits: the pods need exactly 3.92.
    assert budget.pods_need_usd == Decimal("3.92") == budget.pod_allowance_usd


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_attacker_holds_four_kimi_k3_calls_at_the_standing_ceiling(stage):
    from carbon.agent_campaign.graphite import phase4

    budget = phase4.attacker_budget(_stage(f"{stage}-ATTACKER"), _battery())
    assert budget.token_allowance_usd >= 4 * KIMI_FULL_CALL
