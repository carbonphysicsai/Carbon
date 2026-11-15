"""The Motor 1.8 kit page (kits/motor/HOW_YOURE_TESTED.md) shows the registered in-range gate and the other
registered public values of the version's pool-constants row, as READ from `pool_constants.json`, never retyped.

A value is public once the row registers it (the row has no HUMAN_INPUT in these leaves); the page must then show it
and must not still say HUMAN_INPUT for it. A leaf the row still holds as HUMAN_INPUT is not asserted here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "kits" / "motor" / "HOW_YOURE_TESTED.md"
POOL = ROOT / "scripts" / "validator_host_classes" / "pool_constants.json"
ROW = "electric-motor-magnetics 1.8"

#: The page's wording of an output name, in the order the registered threshold lists them.
GATE_OUTPUT_WORDS = {
    "mean_torque_nm": "mean torque",
    "ripple_pk_pk_nm": "torque ripple",
    "back_emf_open_circuit": "open-circuit back-EMF",
}


def _row():
    return json.loads(POOL.read_text(encoding="utf-8"))["versions"][ROW]


def _page():
    return " ".join(PAGE.read_text(encoding="utf-8").split())


def _u(value):
    """The page's format of a limit in U: four significant figures at most (as the published exam text)."""
    return f"{value:.4g}"


def test_page_shows_the_registered_in_range_gate_read_from_the_pool_row():
    physics = _row()["physics"]
    statistic, limits = physics["gate_statistic"], physics["gate_threshold"]
    assert statistic == "p90"
    assert set(limits) == set(GATE_OUTPUT_WORDS)
    text = _page()
    gate = re.search(r"The threshold, as registered: (.*?) Design value", text)
    assert gate is not None, "the in-range gate bullet is missing"
    paragraph = gate.group(1)
    assert f"({statistic})" in paragraph
    for name, word in GATE_OUTPUT_WORDS.items():
        assert f"{_u(limits[name])} U for {word}" in paragraph, (name, paragraph)


def test_page_does_not_call_the_registered_in_range_threshold_human_input():
    text = _page()
    gate_at = text.index("In-range accuracy is a gate")
    nearby = text[gate_at : gate_at + 1400]
    assert "HUMAN_INPUT" not in nearby


def test_page_shows_the_registered_menu_rotation_and_tasks_and_no_query_budget():
    menu = _row()["menu"]
    for leaf in (menu["rotation_days"], menu["tasks_per_epoch"]):
        assert type(leaf) is int, "a leaf this test reads is still HUMAN_INPUT"
    text = _page()
    assert f"(every {menu['rotation_days']} days)" in text
    assert f"Carbon draws {menu['tasks_per_epoch']} design tasks per epoch." in text
    # Motor 1.8 is menu D with no search: the row's optimizer budget is a pick-D leftover and is not published
    assert "model-call budget" not in text


def _registry(name):
    return json.loads(
        (ROOT / "scripts" / "validator_host_classes" / name).read_text(encoding="utf-8")
    )


def _section(heading):
    text = PAGE.read_text(encoding="utf-8")
    start = text.index(heading)
    end = text.find("\n## ", start + 1)
    return " ".join(text[start : len(text) if end < 0 else end].split())


def test_page_crown_section_shows_the_registered_official_score_rule_and_floor():
    margin = _registry("crown_official_score.json")["versions"][ROW]["margin"]
    floor = next(
        row["value"]
        for row in _registry("crown_floor.json")["floors"]
        if (row["challenge"], row["version"]) == ("electric-motor-magnetics", "1.8")
    )
    crown = _section("## 5. The crown")
    assert f"registered margin, {margin:g};" in crown
    assert "a tie, or anything within the margin, keeps the king" in crown
    assert (
        f"When there is no king, a grade takes the crown only if its official total is above the floor, "
        f"currently {floor:g} (provisional, set by the owner), by more than the same margin."
    ) in crown
    assert "there are no crown rebuilds" in crown
    # the retired rebuild-average rule and the review hold are not described
    assert "10-rebuild" not in crown and "rebuilds that model" not in crown
    assert "crown_held_for_review" not in crown
    holds = _registry("crown_hold.json")["holds"]
    assert [h["hold"] for h in holds if h["version"] == "1.8"] == ["off"]


def test_page_states_the_registered_early_stop_and_the_overlay_wall():
    stop = _registry("early_wall_stop.json")["rows"][ROW]
    assert stop["enabled"] is True and stop["margin"] == 1.0
    wall = _registry("version_overlay.json")["versions"][ROW]["rebuild_wall_seconds"]
    page = _page()
    assert f"up to **{wall} seconds**" in page
    assert f"projected run time is past the {wall} s limit" in page
    assert "a stop counts as a try" in page


def test_page_no_longer_says_the_version_does_not_grade():
    assert "does not grade" not in _page()
