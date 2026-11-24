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
    gate = re.search(
        r"The threshold, as registered: (.*?) \*\*One answer per design", text
    )
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


def test_page_states_the_number_that_ranks_and_no_design_menu():
    """The crown row ranks Motor 1.8 by its accuracy result, so the page states no design value rule: no menu, draw, task
    count or schedule. The row check still counts, and its pass name is still described.
    """
    assert _registry("crown_official_score.json")["versions"][ROW]["score"] == "A"
    text = _page()
    assert "`TOTAL = A`, the physics part below, 0 to 1, higher is better." in text
    assert "Design value is not counted." in text
    for gone in (
        "0.5 x physics",
        "design tasks per epoch",
        "top five picks",
        "from a menu",
        "design menus",
        "the hidden sample rotates",
        "(every 7 days)",
    ):
        assert gone not in text, gone
    assert "A grade is ranked only when its result shows" in text
    assert "`menu_rowcheck`: " in text
    # the row's optimizer budget is a pick-D leftover and is not published
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


def test_page_crown_section_shows_the_registered_official_score_rule():
    margin = _registry("crown_official_score.json")["versions"][ROW]["margin"]
    crown = _section("## 5. The crown")
    assert f"registered margin, {margin:g};" in crown
    assert "a tie, or anything within the margin, keeps the king" in crown
    # the registered floor is a floor on the total: on the number that ranks now none is registered, and a first crown waits
    assert (
        "When there is no king, the first crown waits until a floor on this score is registered."
        in crown
    )
    assert "official total" not in crown
    assert "there are no crown rebuilds" in crown
    # the retired rebuild-average rule and the review hold are not described
    assert "10-rebuild" not in crown and "rebuilds that model" not in crown
    assert "crown_held_for_review" not in crown
    holds = _registry("crown_hold.json")["holds"]
    assert [h["hold"] for h in holds if h["version"] == "1.8"] == ["off"]


def test_page_states_the_registered_early_stop_and_the_overlay_wall():
    """The early stop is OFF for Motor 1.8 (owner, 15 Nov 07:02 CST, at the compiled-forward switch): the page says so
    and no longer describes a projection stop."""
    stop = _registry("early_wall_stop.json")["rows"][ROW]
    assert stop["enabled"] is False
    wall = _registry("version_overlay.json")["versions"][ROW]["rebuild_wall_seconds"]
    page = _page()
    assert f"up to **{wall} seconds**" in page
    assert "Early stop: off for Motor 1.8 for now." in page
    assert f"an inference that reaches the {wall} s limit is a normal timeout" in page
    assert "projected run time" not in page
    assert "stopped early, and a stop counts as a try" not in page


def test_page_no_longer_says_the_version_does_not_grade():
    assert "does not grade" not in _page()
