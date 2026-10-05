"""The phase-4 grants are the owner's, validate, and match their recorded
derivation (grants/README.md). Money and time bind, never a call count. No
live run happens in this work.

- GRAPHITE-GRANT-PHASE4, battery's (OWNER-GRAPHITE-ATTACKER-01 §5; also
  recorded as OWNER-GRAPHITE-TEST-WAVE-01 §2, carbonphysicsai/Carbon#556);
- GRAPHITE-GRANT-PHASE4-COOLING, cooling's (OWNER-GRAPHITE-TEST-WAVE-05 §2,
  carbonphysicsai/Carbon#593): the same amounts, a new file, bound to
  `chip-cold-plate` by the runner's registry (`phase4.PHASE4_GRANTS`).
"""

from __future__ import annotations

import json
import math
from decimal import Decimal
from pathlib import Path

import pytest

from carbon.agent_campaign.grant import FIELDS, SpendingGrant
from carbon.agent_campaign.graphite import experiment, phase4
from carbon.challenge_validator import scoring as challenge_scoring
from carbon.reconstruction.capability_registry import (
    BATTERY_CHALLENGE,
    COLD_PLATE_CHALLENGE,
    MOTOR_CHALLENGE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
GRANTS = REPOSITORY / "docs/development/graphite/grants"
#: Challenge -> (grant id, file name), as the owner's records approve them.
APPROVED = {
    BATTERY_CHALLENGE: ("GRAPHITE-GRANT-PHASE4", "GRAPHITE-GRANT-PHASE4.json"),
    COLD_PLATE_CHALLENGE: (
        "GRAPHITE-GRANT-PHASE4-COOLING",
        "GRAPHITE-GRANT-PHASE4-COOLING.json",
    ),
}
CHALLENGES = sorted(APPROVED)


def _document(challenge):
    document = json.loads((GRANTS / APPROVED[challenge][1]).read_text())
    assert "HUMAN_INPUT" not in json.dumps(document)
    return document


def _grant(challenge):
    return SpendingGrant.from_document(_document(challenge))


def test_the_registry_is_exactly_the_approved_grants():
    """One grant per Challenge, each where the driver reads it; motor has
    none until its scorer exists (OWNER-GRAPHITE-TEST-WAVE-05 §2)."""
    assert {
        challenge: (entry.grant_id, entry.grant_file)
        for challenge, entry in phase4.PHASE4_GRANTS.items()
    } == {
        challenge: (grant_id, phase4.GRANTS_DIR + "/" + name)
        for challenge, (grant_id, name) in APPROVED.items()
    }
    assert MOTOR_CHALLENGE not in phase4.PHASE4_GRANTS
    for challenge, entry in phase4.PHASE4_GRANTS.items():
        assert entry.challenge == challenge
        assert (REPOSITORY / entry.grant_file).parent == GRANTS
        assert _grant(challenge).grant_id == entry.grant_id
    ids = [entry.grant_id for entry in phase4.PHASE4_GRANTS.values()]
    files = [entry.grant_file for entry in phase4.PHASE4_GRANTS.values()]
    assert len(set(ids)) == len(ids) and len(set(files)) == len(files)


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_the_phase4_grant_is_the_owners(challenge):
    grant = _grant(challenge)
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


def test_the_cooling_grant_is_battery_s_but_for_its_id():
    """WAVE-05 §2: "identical to GRAPHITE-GRANT-PHASE4"; only the id differs,
    so the two canonical digests differ and neither passes for the other."""
    battery, cooling = _document(BATTERY_CHALLENGE), _document(COLD_PLATE_CHALLENGE)
    assert set(cooling) == set(FIELDS)
    assert {key for key in FIELDS if battery[key] != cooling[key]} == {"grant_id"}
    assert phase4.grant_digest(battery) != phase4.grant_digest(cooling)


def test_the_cooling_grant_cites_its_authority():
    readme = (GRANTS / "README.md").read_text()
    section = readme[readme.index("## GRAPHITE-GRANT-PHASE4-COOLING") :]
    assert "OWNER-GRAPHITE-TEST-WAVE-05 §2" in section
    assert "carbonphysicsai/Carbon#593" in section
    assert "chip-cold-plate" in section
    assert "3 × 3.41 + 0.25 = 10.48 ≤ 10.50" in section


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_the_ceiling_covers_three_runs_and_cleanup(challenge):
    """A grant ceiling that no longer covers three runs plus cleanup turns this
    red (mutation: grant ceiling exceeded)."""
    grant = _grant(challenge)
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


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_the_run_cost_is_the_pod_and_token_split(challenge):
    """Six verify pods (USD 1.48) plus about 40 glm-5.2 calls (USD 1.93), under
    the Challenge's own scoring."""
    grant = _grant(challenge)
    budget = phase4.attacker_budget(grant, challenge_scoring.scoring_for(challenge))
    assert budget.challenge_id == challenge
    assert budget.max_pods == phase4.ATTACKER_VERIFY_PODS == 6
    assert budget.pod_allowance_usd == Decimal("1.48")
    assert budget.token_allowance_usd == Decimal("1.93")
    assert budget.pod_allowance_usd + budget.token_allowance_usd == (
        grant.worst_case_run_cost
    )


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_the_grant_also_satisfies_the_shared_pod_budget(challenge):
    """The grant validates for #504's budget machinery that the provider
    inherits, so `AttackerProvider` can be built from it."""
    budget = experiment.phase3_budget(
        _grant(challenge), challenge_scoring.scoring_for(challenge)
    )
    assert budget.max_pods >= 2 and budget.token_allowance_usd > 0


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_the_dry_run_grant_is_the_named_challenge_s_under_a_synthetic_identity(
    challenge,
):
    dry = phase4.dry_run_grant(challenge).document()
    real = _grant(challenge).document()
    changed = {key for key in real if dry[key] != real[key]}
    assert changed == {"grant_id", "account", "granted_by", "expires_at"}
    assert dry["grant_id"] == "graphite-phase4-attacker-dry-run-synthetic"
    # The amounts, runs and runtime are the named Challenge's grant's.
    for key in (
        "monetary_ceiling",
        "worst_case_run_cost",
        "max_runtime_s",
        "permitted_runs",
        "cleanup_allowance",
    ):
        assert dry[key] == real[key]


def test_the_dry_run_grant_reads_the_named_challenge_s_file(tmp_path, capsys):
    """Mutation: read one fixed file for every Challenge, and cooling's dry
    run copies battery's grant (or the reverse); a file naming another grant
    is refused, and motor has no grant to copy."""
    (tmp_path / phase4.GRANTS_DIR).mkdir(parents=True)
    for index, challenge in enumerate(CHALLENGES):
        document = _document(challenge)
        # Mark each file so the copy shows which one it was read from.
        document["max_runtime_s"] = 100 + index
        (tmp_path / phase4.GRANTS_DIR / APPROVED[challenge][1]).write_text(
            json.dumps(document)
        )
    for index, challenge in enumerate(CHALLENGES):
        assert phase4.dry_run_grant(challenge, tmp_path).max_runtime_s == 100 + index
    swapped = tmp_path / phase4.PHASE4_GRANTS[COLD_PLATE_CHALLENGE].grant_file
    swapped.write_text(json.dumps(_document(BATTERY_CHALLENGE)))
    with pytest.raises(SystemExit):
        phase4.dry_run_grant(COLD_PLATE_CHALLENGE, tmp_path)
    assert "phase4_grant_file_names_another_grant" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        phase4.dry_run_grant(MOTOR_CHALLENGE, tmp_path)
    assert "no_phase4_grant_for_challenge" in capsys.readouterr().out
