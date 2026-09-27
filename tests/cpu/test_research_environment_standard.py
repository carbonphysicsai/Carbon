"""OWNER-RESEARCH-ENVIRONMENT-01: every Challenge declares a complete research
environment, or names each gap.

The claims tested: no Challenge with a construction contract is missing from
the standard; every provision is declared; provided evidence really imports;
gaps are explicit, never silent.
"""

from importlib import import_module

import pytest

from carbon.challenge_kit import standard
from carbon.reconstruction.capability_registry import CONTRACTS


def test_every_contracted_challenge_declares_its_research_environment():
    assert set(CONTRACTS) <= set(standard.ENVIRONMENTS)


def test_no_declaration_for_a_challenge_without_a_contract():
    assert set(standard.ENVIRONMENTS) <= set(CONTRACTS)


@pytest.mark.parametrize("challenge", sorted(standard.ENVIRONMENTS))
def test_every_provision_is_declared(challenge):
    assert set(standard.ENVIRONMENTS[challenge]) == set(standard.PROVISIONS)


def _entries():
    for challenge, table in sorted(standard.ENVIRONMENTS.items()):
        for provision, status in sorted(table.items()):
            yield challenge, provision, status


@pytest.mark.parametrize(("challenge", "provision", "status"), list(_entries()))
def test_provided_evidence_imports_and_gaps_are_named(challenge, provision, status):
    if isinstance(status, standard.Provided):
        assert status.evidence, (challenge, provision)
        for ref in status.evidence:
            module, _, symbol = ref.partition(":")
            assert symbol, ref
            assert callable(getattr(import_module(module), symbol)), ref
    else:
        assert isinstance(status, standard.Gap), (challenge, provision)
        assert status.reason.strip() and status.next_step.strip()


def test_open_gaps_are_reported():
    report = standard.gaps()
    declared = {
        (challenge, provision)
        for challenge, provision, status in _entries()
        if isinstance(status, standard.Gap)
    }
    reported = {
        (challenge, provision)
        for challenge, table in report.items()
        for provision in table
    }
    assert reported == declared
    assert all(table for table in report.values())


def test_the_standard_stays_out_of_the_miner_image():
    """The standard is validator-side policy, not kit code: it must never
    enter the challenge kit's import closure shipped to miners."""
    from pathlib import Path

    from carbon.development_session.research_image import challenge_kit_files

    repo = Path(__file__).resolve().parents[2]
    assert "carbon/challenge_kit/standard.py" not in set(challenge_kit_files(repo))
