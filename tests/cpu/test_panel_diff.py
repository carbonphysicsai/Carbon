import copy
from pathlib import Path

import pytest

from carbon.challenge_pipeline.onboarding import packet, panel
from carbon.challenge_pipeline.onboarding import panel_diff as diff
from carbon.design_search import tasks

ROOT = Path(__file__).resolve().parents[2]


def draft(family="motor"):
    folder = (
        "onboarding-automation"
        if family == "motor"
        else "onboarding-runs/generated/f02"
    )
    filename = "motor-brief.json" if family == "motor" else "brief.json"
    return packet.generate(
        packet.read_json(
            ROOT / f"docs/development/challenge_pipeline/{folder}/{filename}"
        ),
        ROOT,
    )


def seed(family="motor"):
    return {
        "schema": panel.SCHEMA,
        "challenge": family,
        "designs": [
            {"id": "a", "coordinates": {"gap_mm": 0.4}},
            {"id": "alias", "coordinates": {"gap_mm": 0.4}},
        ],
        "strata": [
            {"id": "holding", "inputs": {"J": 10}},
            {"id": "peak", "inputs": {"J": 15}},
        ],
        "rungs": [
            {"id": "r1", "settings": {"angles": 60}},
            {"id": "r2", "settings": {"angles": 120}},
        ],
        "pins": {
            k: "sha256:" + str(i) * 64 for i, k in enumerate(sorted(panel.PIN_KEYS))
        },
        "cost_cpu_seconds": {
            "r1": {"seconds": 4320, "basis": "synthetic planning"},
            "r2": {"seconds": 28800, "basis": "synthetic planning"},
        },
    }


def inventory(family="motor", records=None):
    return {
        "schema": diff.SCHEMA,
        "challenge": family,
        "scope": "PUBLIC_DEVELOPMENT",
        "coverage": "COMPLETE_FOR_REQUESTED_PINS",
        "basis": "SYNTHETIC_FIXTURE_ONLY; not actual DC inventory",
        "records": records or [],
    }


def test_full_tuples_identity_aliases_cost_and_no_authority():
    d, s = draft(), seed()
    out = diff.generate(d, seed=s, inventory=inventory())
    assert len(out["tuples"]) == 4 and out["basis"]["requested_aliases"] == 8
    assert all(len(t["aliases"]) == 2 for t in out["tuples"])
    assert all(
        t["physical_identity"] == tasks.digest(t["tuple"]) for t in out["tuples"]
    )
    assert out["cost"]["cpu_hours_new_only"] == pytest.approx(18.4)
    assert out["registration_input_ready"]
    assert not out["execution_authorized"] and not out["registration_adopted"]


def test_completed_and_scheduled_are_reused_not_recounted():
    d, s = draft(), seed()
    initial = diff.generate(d, seed=s, inventory=inventory())
    records = [
        {
            "tuple": initial["tuples"][i]["tuple"],
            "state": state,
            "receipt": "public declared " + state,
        }
        for i, state in enumerate(("COMPLETED", "SCHEDULED"))
    ]
    out = diff.generate(d, seed=s, inventory=inventory(records=records))
    assert len(out["new"]) == 2 and len(out["completed"]) == len(out["scheduled"]) == 1
    assert out["cost"]["cpu_hours_new_only"] == pytest.approx(9.2)
    assert not out["reuse_verified_by_tool"]
    s["pins"]["observer"] = "sha256:" + "f" * 64
    changed = diff.generate(d, seed=s, inventory=inventory(records=records))
    assert len(changed["new"]) == 4 and changed["unused_inventory_identities"] == 2


def test_partial_or_missing_index_does_not_prove_new():
    for index in (None, {**inventory(), "coverage": "PARTIAL"}):
        out = diff.generate(draft(), seed=seed(), inventory=index)
        assert not out["new"] and len(out["unseen"]) == 4
        assert (
            not out["registration_input_ready"]
            and out["cost"]["cpu_hours_new_only"] is None
        )


def test_schedule_conflict_is_visible_not_silently_cancelled():
    t = diff.generate(draft(), seed=seed())["tuples"][0]["tuple"]
    index = inventory(
        records=[
            {"tuple": t, "state": s, "receipt": s} for s in ("COMPLETED", "SCHEDULED")
        ]
    )
    out = diff.generate(draft(), seed=seed(), inventory=index)
    assert len(out["conflicts"]) == 1 and not out["registration_input_ready"]
    assert len(out["tuples"][0]["receipts"]) == 2


def test_missing_pin_and_cost_are_unknown_not_zero():
    s = seed()
    s["pins"]["materials"] = None
    out = diff.generate(draft(), seed=s, inventory=inventory())
    assert out["missing_pins"] == ["materials"]
    assert all(t["physical_identity"] is None for t in out["tuples"])
    s = seed()
    s["cost_cpu_seconds"].pop("r2")
    assert (
        diff.generate(draft(), seed=s, inventory=inventory())["cost"][
            "cpu_hours_new_only"
        ]
        is None
    )


def test_real_f02_draft_with_no_physical_seed_is_explicitly_blocked():
    out = diff.generate(draft("f02"))
    assert out["challenge"] == "f02" and out["basis"]["case_count"] is None
    assert not out["registration_input_ready"] and not out["tuples"]


@pytest.mark.parametrize(
    "change",
    [{"scope": "HIDDEN"}, {"challenge": "battery-v3"}, {"coverage": "ASSUME_EMPTY"}],
)
def test_bad_inventory_refused(change):
    with pytest.raises(packet.DraftError):
        diff.generate(draft(), seed=seed(), inventory={**inventory(), **change})


def test_inventory_cannot_fake_identity_or_duplicate_receipt():
    t = diff.generate(draft(), seed=seed())["tuples"][0]["tuple"]
    row = {"tuple": t, "state": "COMPLETED", "receipt": "fixture"}
    with pytest.raises(packet.DraftError):
        diff.generate(
            draft(), seed=seed(), inventory=inventory(records=[row, copy.deepcopy(row)])
        )
    row["identity"] = "sha256:" + "0" * 64
    with pytest.raises(packet.DraftError):
        diff.generate(draft(), seed=seed(), inventory=inventory(records=[row]))


def test_existing_public_f02_cases_are_not_crossed_into_fictional_panel():
    from scripts.dev.onboarding.panel_diff_example import build

    report = build()
    assert report["existing_public_tuples"] == 8
    assert all(r["basis"]["case_count"] == 1 for r in report["results"])
    assert all(not r["registration_input_ready"] for r in report["results"])
    assert all(len(r["unseen"]) == 1 for r in report["results"])
    assert not report["solver_runs"] and not report["registration_adopted"]
