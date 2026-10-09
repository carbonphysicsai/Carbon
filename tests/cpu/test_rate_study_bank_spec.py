"""SUBMISSION-RATE-STUDY-01 study bank spec (run sheet C.1): the arithmetic holds
and agrees with the battery bank rule."""

import json
from pathlib import Path

from carbon.battery import exam

REPOSITORY = Path(__file__).resolve().parents[2]
SPEC = json.loads(
    (
        REPOSITORY
        / "docs/development/evidence/submission-rate-study-01/bank-spec-v1.json"
    ).read_text(encoding="utf-8")
)


def test_draws_exposures_and_solves_add_up():
    runs, bank, fresh, e = SPEC["runs"], SPEC["bank"], SPEC["fresh"], SPEC["exposure"]
    submissions = len(runs["rates"]) * runs["replicates_per_rate"]
    draws = submissions * runs["windows_per_run"] * e["window_cases"]
    arithmetic = SPEC["arithmetic"]
    assert draws == arithmetic["draws"] == 14112
    assert bank["cases"] * e["E"] == arithmetic["exposures_available"] == 15000
    assert arithmetic["exposures_available"] - draws == arithmetic["spare_exposures"]
    assert fresh["windows"] * fresh["cases_per_window"] == fresh["total"] == 1176
    assert bank["cases"] + fresh["total"] == arithmetic["reference_solves"]
    assert bank["cases"] >= -(-draws // e["E"]), "the bank must supply every draw"


def test_the_spec_agrees_with_the_battery_bank_rule():
    pool = exam.DEVELOPMENT_RULE_V2_BANK["bank"]["pool"]
    assert SPEC["exposure"]["window_cases"] == pool["window_cases"]
    assert SPEC["exposure"]["hidden_duplicates"] == pool["hidden_duplicates"]
    assert SPEC["exposure"]["E"] == pool["retire_at"]


def test_the_study_bank_is_sacrificial_and_the_fresh_bank_is_never_drawable():
    assert SPEC["bank"]["sacrificial"] is True
    assert SPEC["bank"]["serves_real_window"] is False
    assert SPEC["bank"]["top_up"] == "off"
    assert SPEC["fresh"]["drawable_by_a_window"] is False
    assert not any(SPEC["claims"].values())
