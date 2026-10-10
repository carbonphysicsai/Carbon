import json
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import packet, panel

ROOT = Path(__file__).resolve().parents[2]


def draft():
    return packet.generate(
        packet.read_json(
            ROOT
            / "docs/development/challenge_pipeline/onboarding-automation/motor-brief.json"
        ),
        ROOT,
    )


def seed():
    return {
        "schema": panel.SCHEMA,
        "challenge": "motor",
        "designs": [
            {"id": "a", "coordinates": {"gap_mm": 0.4}},
            {"id": "b", "coordinates": {"gap_mm": 0.8}},
        ],
        "strata": [
            {"id": "holding", "inputs": {"J": 10}},
            {"id": "peak", "inputs": {"J": 15}},
        ],
        "rungs": [
            {"id": "standard", "settings": {"angles": 60}},
            {"id": "rung2", "settings": {"angles": 120}},
        ],
        "pins": {key: "toy-pinned-v1" for key in panel.PIN_KEYS},
        "cost_cpu_seconds": {
            "standard": {
                "seconds": 4320,
                "basis": "supplied planning 1.2 CPU-h, not billed wall",
            },
            "rung2": {
                "seconds": 28800,
                "basis": "supplied planning 8 CPU-h, not billed wall",
            },
        },
    }


def test_case_crossproduct_cost_and_scheduled_reuse():
    s = seed()
    first = panel.generate(draft(), seed=s)
    assert first["case_count"] == 8
    assert first["cost"]["cpu_hours_without_reuse"] == pytest.approx(36.8)
    assert first["cost"]["eur"] is None
    identities = [row["physical_identity"] for row in first["cases"]]
    reuse = [
        {
            "identity": identities[0],
            "state": "COMPLETED",
            "receipt": "retained development receipt A",
        },
        {
            "identity": identities[1],
            "state": "SCHEDULED",
            "receipt": "precommitted development plan B",
        },
    ]
    next_ = panel.generate(draft(), seed=s, reuse=reuse)
    assert next_["reuse_check"]["completed_matches"] == 1
    assert next_["reuse_check"]["scheduled_matches"] == 1
    assert next_["cost"]["cpu_hours_if_reuse_accepted"] == pytest.approx(27.6)
    s["pins"]["observer"] = "changed-v2"
    changed = panel.generate(draft(), seed=s, reuse=reuse)
    assert changed["reuse_check"]["completed_matches"] == 0


def test_unknown_pins_never_match_and_duplicates_do_not_create_solves():
    s = seed()
    s["designs"].append({"id": "same-physics", "coordinates": {"gap_mm": 0.4}})
    assert panel.generate(draft(), seed=s)["case_count"] == 8
    s["pins"]["materials"] = None
    generated = panel.generate(draft(), seed=s, reuse=[])
    assert all(
        r["physical_identity"] is None and r["reuse_recommendation"] == "UNKNOWN"
        for r in generated["cases"]
    )
    s["cost_cpu_seconds"].pop("rung2")
    assert panel.generate(draft(), seed=s)["cost"]["cpu_hours_without_reuse"] is None


def test_no_numeric_packet_inputs_does_not_register_fiction():
    generated = panel.generate(draft())
    assert generated["case_count"] is None
    assert generated["designs"] is None
    assert "TWO" in generated["boundary_designs"]["recommendation"]
    assert (
        generated["boundary_designs"]["intervals_and_frontier_results"]
        == "NOT_DEMONSTRATED"
    )


def test_refuse_unbounded_or_nonfinite_seed():
    s = seed()
    s["cost_cpu_seconds"]["standard"]["seconds"] = float("nan")
    with pytest.raises(packet.DraftError):
        panel.generate(draft(), seed=s)
    s = seed()
    s["designs"][0]["coordinates"]["gap_mm"] = True
    with pytest.raises(packet.DraftError):
        panel.generate(draft(), seed=s)


def test_existing_panel_contracts_supply_the_same_registration_discipline():
    battery = packet.read_json(
        ROOT
        / "docs/development/challenge_pipeline/question-laws/battery-v3-middle-bands-panel.json"
    )
    assert battery["near"]["bands_both_sides"] == 2
    assert battery["stage_A"]["check_scheduled_before_start"]
    assert battery["accepted_manifest_digest"] is None
    magnetics = packet.read_json(
        ROOT / "docs/development/challenge_pipeline/magnetics-first-panels/panels.json"
    )
    assert "HUMAN_INPUT" in json.dumps(magnetics)
    assert panel.generate(draft())["registration_status"] == "PROPOSED_NOT_DISPATCHABLE"
