"""Cooling's research parts per version (OWNER-BACKBONE-CATALOG-01, as Motor's):
1.0 keeps its exact bytes; the catalog version 1.2 is keyed 1.2 throughout."""

from __future__ import annotations

import pytest
from cooling_catalog_stand_in import STAND_IN, inject

from carbon.cold_plate import contracts, research
from carbon.cold_plate.challenge import CHALLENGE
from carbon.reconstruction.capability_registry import public_registry


def test_version_1_0_is_unchanged_by_the_key():
    parts = research.challenge_parts("1.0")
    assert parts.key == CHALLENGE
    assert contracts.cold_plate_contracts() is contracts.cold_plate_contracts("1.0")
    assert contracts.research_key() == CHALLENGE
    assert parts.scaffold_strategy == research.SCAFFOLD
    assert parts.strategy_schema == public_registry("chip-cold-plate")


def test_there_is_no_default_version():
    with pytest.raises(TypeError):
        research.challenge_parts()
    with pytest.raises(ValueError, match="cooling version"):
        contracts.key_for(None)
    with pytest.raises(ValueError, match="no research parts"):
        research.challenge_parts("1.1")


def test_the_catalog_version_is_keyed_1_2_throughout():
    parts = research.challenge_parts("1.2")
    assert parts.key.version == "1.2"
    assert parts.measurements.challenge_key == parts.key
    for binding in parts.measurements.stratum_applicability:
        assert binding.stratum_ref.challenge_key == parts.key
    assert parts.scaffold_strategy["source"]["kind"] == "catalog"
    assert parts.strategy_schema["schema"] == "carbon.backbone-catalog.served.v1"
    assert parts.practice_scope["challenge"] == {
        "id": "chip-cold-plate",
        "version": "1.2",
    }
    assert contracts.cold_plate_contracts("1.2").key == parts.key
    # Built, the key returns to 1.0.
    assert contracts.research_key() == CHALLENGE
    # 1.2's refs are its own: no 1.0 ref is reused.
    assert (
        contracts.cold_plate_contracts("1.2").assembly.to_ref()
        != contracts.cold_plate_contracts("1.0").assembly.to_ref()
    )


def test_an_empty_catalog_scaffolds_an_unfilled_template():
    # As shipped, Cooling 1.2 offers no tested entry: the scaffold names none.
    parts = research.challenge_parts("1.2")
    assert parts.strategy_schema["entries"] == {}
    assert parts.scaffold_strategy["source"]["catalog_id"] is None
    assert parts.scaffold_strategy["output"]["format"] is None


def test_an_offered_entry_becomes_the_ready_recipe(monkeypatch):
    inject(monkeypatch)
    parts = research.challenge_parts("1.2")
    assert set(parts.strategy_schema["entries"]) == {STAND_IN}
    assert parts.scaffold_strategy["source"]["catalog_id"] == STAND_IN
    assert parts.scaffold_catalog["templates"] == [parts.scaffold_strategy]
