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


@pytest.mark.parametrize("challenge", sorted(standard.offered()))
def test_every_provision_is_declared(challenge):
    assert set(standard.offered()[challenge]) == set(standard.PROVISIONS)


def _entries():
    for challenge, table in sorted(standard.offered().items()):
        for provision, status in sorted(table.items()):
            yield challenge, provision, status


def _retired_entries():
    for challenge, record in sorted(standard.retired().items()):
        for provision, status in sorted(record.provided.items()):
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


def test_retired_here_exactly_when_retired_in_the_registry():
    """The standard and the Challenge registry cannot disagree about which
    Challenges are retired."""
    from carbon.challenge_registry.registry import RETIRED, entries

    registry_retired = {
        entry.challenge_id
        for entry in entries()
        if entry.status == RETIRED and entry.challenge_id in standard.ENVIRONMENTS
    }
    assert set(standard.retired()) == registry_retired
    assert "burgers-dynamics-v1" in registry_retired  # specimen


@pytest.mark.parametrize(("challenge", "provision", "status"), list(_retired_entries()))
def test_a_retired_record_stays_readable(challenge, provision, status):
    """Retiring deletes nothing: what the Challenge provided, and the symbols
    it provided it through, still resolve, so recorded evidence keeps its
    meaning."""
    assert isinstance(status, standard.Provided)
    # The same check the offered Challenges' evidence passes.
    test_provided_evidence_imports_and_gaps_are_named(challenge, provision, status)


def test_retired_is_never_a_gap(monkeypatch):
    """A gap is work owed; retired is work no longer owed. The two cannot be
    confused: a retired Challenge is absent from gaps(), is not a
    per-provision status, and cannot be built holding a gap."""
    report = standard.gaps()
    assert "burgers-dynamics-v1" not in report
    # Specimen: gaps() does report an open gap on an offered Challenge.
    battery = standard.ENVIRONMENTS["battery-fastcharge-ageing-development-v1"]
    monkeypatch.setitem(
        standard.ENVIRONMENTS,
        "fixture-challenge",
        {**battery, "generate": standard.Gap("r", "n")},
    )
    assert "generate" in standard.gaps()["fixture-challenge"]
    monkeypatch.undo()
    burgers = standard.ENVIRONMENTS["burgers-dynamics-v1"]
    assert type(burgers) is standard.Retired
    assert standard.Retired not in standard.Status.__args__
    assert "burgers-dynamics-v1" not in standard.offered()
    with pytest.raises(TypeError, match="never a gap"):
        standard.Retired(
            decision="fixture", provided={"generate": standard.Gap("r", "n")}
        )
    with pytest.raises(ValueError, match="known provisions"):
        standard.Retired(
            decision="fixture", provided={"invent": burgers.provided["train"]}
        )
    with pytest.raises(ValueError, match="decision"):
        standard.Retired(decision=" ", provided={})
