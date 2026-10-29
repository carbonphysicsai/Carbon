"""Per-part feedback never discloses more than the Validator set
(PART_FEEDBACK_GRANULARITY_20261029 sections 1 and 4): a merge that widens it fails
this gate.

- the part step is never finer than twice the total's step (p >= 2 * s) and never
  below 0.05;
- the v4 document's fields are exactly the set below;
- the never-shown list is exactly the closed list below;
- the store refuses a document with any field outside the allow-list.
"""

import json

import pytest

from carbon.challenge_validator.ladder_store import LadderStoreRefused, checked
from carbon.scoring import grade_feedback as gf

pytestmark = pytest.mark.invariant

EXPECTED_FIELDS_V4 = {
    "schema",
    "exam_version",
    "status",
    "total",
    "gate_names",
    "recipe_digest",
    "epoch",
    "parts",
    "gates",
    "minimums_missed",
}
EXPECTED_NEVER_SHOWN = (
    "per_case_values",
    "case_ids",
    "target_ids",
    "draw_ids",
    "positions_or_conditions",
    "which_cases_failed",
    "picked_design",
    "reference_values",
    "pool",
    "set_level_split",
    "feasible_target_counts",
    "unrounded_values",
    "another_hotkeys_anything",
)


def test_the_part_step_is_pinned_at_twice_the_total_step_and_at_least_005():
    assert gf.PART_FLOOR >= 0.05 and gf.PART_FACTOR >= 2
    assert gf.ETA == 0.02
    for noise in (None, 0, 0.005, 0.01, 0.02, 0.0251, 0.04, 0.1, 0.5, 1):
        assert gf.part_step(noise) >= 2 * gf.step(noise)
        assert gf.part_step(noise) >= 0.05


def test_the_v4_fields_and_the_never_shown_list_are_the_closed_ones():
    assert gf.FIELDS_V4 == EXPECTED_FIELDS_V4
    assert gf.FIELDS_V4_NOT_SCORED == EXPECTED_FIELDS_V4 | {"reason", "leg"}
    assert gf.PARTS_FIELDS == {"A", "D", "components"}
    assert gf.NEVER_SHOWN == EXPECTED_NEVER_SHOWN
    assert set(gf.GATE_VERDICTS) == {"pass", "fail"}


def test_no_extra_field_survives_the_store_check():
    document = gf.ladder_feedback(
        {
            "status": "SCORED_DEVELOPMENT_CANDIDATE",
            "score": 0.5,
            "legs": {"A": 0.5, "D": 0.5},
            "gates": {"g": "PASS"},
            "components": {"m": 0.5},
        },
        best=None,
        exam_version="x",
        gate_registry=["g"],
        rebuild_noise=None,
        recipe_digest="sha256:" + "1" * 64,
        epoch=1,
        parts_registry={"A": ["m"], "D": []},
    )
    assert set(document) == gf.FIELDS_V4
    assert set(checked(document)) == gf.FIELDS_V4
    for name in EXPECTED_NEVER_SHOWN:
        with pytest.raises(LadderStoreRefused):
            checked({**json.loads(json.dumps(document)), name: 1})
