"""Motor's research parts per version (OWNER-BACKBONE-CATALOG-01): 1.0 keeps
its exact bytes; the catalog version 1.2 is keyed 1.2 throughout."""

from __future__ import annotations

from carbon.motor import contracts, research
from carbon.motor.challenge import CHALLENGE


def test_version_1_0_is_unchanged_by_the_key():
    default = research.challenge_parts()
    explicit = research.challenge_parts("1.0")
    assert default.key == explicit.key == CHALLENGE
    assert contracts.motor_contracts() is contracts.motor_contracts("1.0")
    assert contracts.research_key() == CHALLENGE


def test_the_catalog_version_is_keyed_1_2_throughout():
    parts = research.challenge_parts("1.2")
    assert parts.key.version == "1.2"
    assert parts.measurements.challenge_key == parts.key
    for binding in parts.measurements.stratum_applicability:
        assert binding.stratum_ref.challenge_key == parts.key
    assert parts.scaffold_strategy["source"]["kind"] == "catalog"
    assert parts.strategy_schema["schema"] == "carbon.backbone-catalog.served.v1"
    assert contracts.motor_contracts("1.2").key == parts.key
    # Built, the key returns to 1.0.
    assert contracts.research_key() == CHALLENGE
    # 1.2's refs are its own: no 1.0 ref is reused.
    assert (
        contracts.motor_contracts("1.2").assembly.to_ref()
        != contracts.motor_contracts("1.0").assembly.to_ref()
    )
