"""Expand documentary intake inheritance, never execute a physical job."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads(
    (
        ROOT / "docs/development/challenge_pipeline/intake-instances/instances.json"
    ).read_text(encoding="utf-8")
)
IDS = {f"I{i:02d}" for i in range(1, 18)}
PHYSICS_IDS = {"I02", *[f"I{i:02d}" for i in range(4, 12)]}


def test_every_intake_category_applies_to_each_candidate():
    assert set(DATA["common_inputs"]) == IDS
    assert {p["challenge"] for p in DATA["profiles"]} == {
        "battery-v3",
        "motor",
        "f02",
        "f17",
        "f13",
        "f06",
        "cooling",
        "f08",
    }
    count = 0
    for profile in DATA["profiles"]:
        assert set(profile["overrides"]) == PHYSICS_IDS
        for item_id, common in DATA["common_inputs"].items():
            row = {**common, **profile["overrides"].get(item_id, {})}
            assert set(row) == {
                "needed",
                "owner",
                "customer",
                "source",
                "test",
                "missing",
            }
            assert all(isinstance(v, str) and v for v in row.values())
            assert "HOLD" in row["missing"]
            sources = {**DATA["common_sources"], **profile["sources"]}
            assert (ROOT / sources[row["source"]]).is_file(), sources[row["source"]]
            count += 1
        assert (ROOT / profile["packet"]).is_file()
        assert profile["rehearsal_status"]
    assert count == 136


def test_audit_is_not_customer_rights_or_a_measured_ledger():
    assert DATA["maturity"] == "SPECIFIED"
    assert DATA["real_customer_intakes"] == 0
    assert DATA["source_role"] == "SPECIFICATION_REHEARSAL_NOT_CUSTOMER_RECEIPT"
    assert DATA["ledger_namespace"] == "INPUTS_PLANNING_ONLY"
    for key in ("solver_runs", "spend", "hidden_data", "customer_rights_accepted"):
        assert DATA[key] is False
    assert DATA["total_cost"] is None and DATA["elapsed_delivery"] is None


def test_customer_problem_scope_and_observers_are_not_replaced():
    profiles = {p["challenge"]: p for p in DATA["profiles"]}
    for challenge, phrase in {
        "battery-v3": "Session-start-to80",
        "motor": "unpowered absolute cogging",
        "f02": "Top-die spatial peak",
        "f17": "flux-weighted variance",
        "f13": "sparse points never fill p10",
        "f06": "fiber-mode coupling",
        "cooling": "lid-side TIM2",
        "f08": "full-band tip motion",
    }.items():
        assert phrase in profiles[challenge]["overrides"]["I10"]["needed"]
