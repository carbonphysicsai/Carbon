"""GRAPHITE-GRANT-PHASE4 (OWNER-GRAPHITE-ATTACKER-01 §5; also recorded as
OWNER-GRAPHITE-TEST-WAVE-01 §2, carbonphysicsai/Carbon#556) is the owner's,
validates, and matches its recorded derivation. Money and time bind, never a
call count. No live run happens in this work."""

from __future__ import annotations

import json
import math
from decimal import Decimal
from pathlib import Path

from carbon.agent_campaign.grant import SpendingGrant
from carbon.agent_campaign.graphite import experiment, phase4
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

REPOSITORY = Path(__file__).resolve().parents[2]
GRANT = REPOSITORY / "docs/development/graphite/grants/GRAPHITE-GRANT-PHASE4.json"
SCORING = challenge_scoring.scoring_for(BATTERY_CHALLENGE)


def _grant():
    document = json.loads(GRANT.read_text())
    assert "HUMAN_INPUT" not in json.dumps(document)
    return SpendingGrant.from_document(document)


def test_the_grant_file_is_where_the_driver_reads_it():
    assert GRANT == REPOSITORY / phase4.GRANT_FILE
    assert _grant().grant_id == phase4.GRANT_ID == "GRAPHITE-GRANT-PHASE4"


def test_the_phase4_grant_is_the_owners():
    grant = _grant()
    assert grant.provider == "graphite" and grant.currency == "USD"
    assert grant.account == "Carbon-Account" and grant.granted_by == "owner"
    assert grant.expires_at.isoformat() == "2026-12-31T23:59:59+00:00"
    assert grant.monetary_ceiling == Decimal("10.50")
    assert grant.cleanup_allowance == Decimal("0.25")
    assert grant.worst_case_run_cost == Decimal("3.41")
    assert grant.permitted_runs == 3
    assert grant.max_concurrency == 1
    assert grant.max_runtime_s == 15600
    assert grant.max_submissions == 3


def test_the_ceiling_covers_three_runs_and_cleanup():
    """A grant ceiling that no longer covers three runs plus cleanup turns this
    red (mutation: grant ceiling exceeded)."""
    grant = _grant()
    assert (
        grant.permitted_runs * grant.worst_case_run_cost + grant.cleanup_allowance
        == (Decimal("10.48"))
    )
    assert (
        grant.permitted_runs * grant.worst_case_run_cost + grant.cleanup_allowance
        <= grant.monetary_ceiling
    )
    headroom = grant.monetary_ceiling - grant.cleanup_allowance
    assert math.floor(headroom / grant.worst_case_run_cost) == grant.permitted_runs


def test_the_run_cost_is_the_pod_and_token_split():
    """Six verify pods (USD 1.48) plus about 40 glm-5.2 calls (USD 1.93)."""
    grant = _grant()
    budget = phase4.attacker_budget(grant, SCORING)
    assert budget.max_pods == phase4.ATTACKER_VERIFY_PODS == 6
    assert budget.pod_allowance_usd == Decimal("1.48")
    assert budget.token_allowance_usd == Decimal("1.93")
    assert budget.pod_allowance_usd + budget.token_allowance_usd == (
        grant.worst_case_run_cost
    )


def test_the_grant_also_satisfies_the_shared_pod_budget():
    """The grant validates for #504's budget machinery that the provider
    inherits, so `AttackerProvider` can be built from it."""
    budget = experiment.phase3_budget(_grant(), SCORING)
    assert budget.max_pods >= 2 and budget.token_allowance_usd > 0


def test_the_dry_run_grant_is_the_phase4_grant_under_a_synthetic_identity():
    dry = phase4.dry_run_grant().document()
    real = _grant().document()
    changed = {key for key in real if dry[key] != real[key]}
    assert changed == {"grant_id", "account", "granted_by", "expires_at"}
    assert dry["grant_id"] == "graphite-phase4-attacker-dry-run-synthetic"
    # The amounts, runs and runtime are the real grant's.
    for key in (
        "monetary_ceiling",
        "worst_case_run_cost",
        "max_runtime_s",
        "permitted_runs",
        "cleanup_allowance",
    ):
        assert dry[key] == real[key]
