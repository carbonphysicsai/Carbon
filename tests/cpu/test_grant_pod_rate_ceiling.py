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
    assert grant.pod_rate_ceiling_usd_per_hr is None
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


def test_a_raised_ceiling_under_a_fixed_token_share_is_refused_not_silently_shrunk():
    """Stage A's Constructor keeps R4's 11.93 token share of a 14.91 run: at
    0.65 an hour its session's pods need more than the 2.98 left, so the run
    is refused before anything opens. A raised ceiling needs its grant's
    token share or per-run worst case re-set too (an owner figure)."""
    stage_a = SpendingGrant.from_document(_document(pod_rate_ceiling_usd_per_hr="0.65"))
    with pytest.raises(ex.BudgetRefused) as refused:
        ex.phase3_budget(stage_a, _battery())
    assert refused.value.code == "grant_token_share_leaves_too_little_for_pods"
