"""Cooling 1.2's card states its recorded limitation (Validator ruling
VALIDATOR_RULING_COOLING12_PEAK_GATE_20261022, finding G1): catalog recipes
fail the mandatory peak_bounds_profile gate until Cooling 1.3."""

from __future__ import annotations

from scripts.dev.miner_launchpad import capabilities


def test_the_1_2_card_states_the_peak_gate_limitation_and_others_none():
    cooling = {"challenge_id": "chip-cold-plate", "version": "1.2"}
    (line,) = capabilities._known_limitations(cooling)
    assert "peak_bounds_profile" in line and "Cooling 1.3" in line
    assert capabilities._known_limitations({**cooling, "version": "1.1"}) == []
    motor = {"challenge_id": "electric-motor-magnetics", "version": "1.3"}
    assert capabilities._known_limitations(motor) == []


def test_battery_cards_state_the_sealed_exam_gap():
    # Validator VALIDATOR_BATTERY_SEALED_RULINGS_20261022 §13, from the one
    # shared table every Challenge's card reads.
    battery = {"challenge_id": "battery-fastcharge-ageing-development-v1"}
    for version in ("1.0", "2.0", "2.1"):
        (line,) = capabilities._known_limitations({**battery, "version": version})
        assert "below 10 °C" in line and "above 0.42" in line


def test_a_catalog_versions_card_counts_its_installed_entries(tmp_path):
    # M1 E2E U30: setup read done while the catalog was not installed.
    from carbon.backbone_catalog import listing

    motor = {"challenge_id": "electric-motor-magnetics", "version": "1.3"}
    entries = listing.entries(motor["challenge_id"], motor["version"])
    cfg = {"campaigns_root": str(tmp_path)}
    assert capabilities._catalog_install(motor, cfg) == {
        "entries": len(entries),
        "installed": 0,
    }
    digest = entries[0]["bundle_ref"]["bundle_digest"][7:]
    staged = tmp_path / ".direct-development/library-cache/materials" / digest
    staged.mkdir(parents=True)
    assert capabilities._catalog_install(motor, cfg)["installed"] == 1
    assert capabilities._catalog_install({**motor, "version": "1.0"}, cfg) is None
