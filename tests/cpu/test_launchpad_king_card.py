"""The "Current king" card (owner via the Lead, Validator OWNER-INTAKE-EXPOSURE-03K).

Per Challenge from its grader's closed `carbon.koth.public.v1` answer, and the
subnet's paid hotkeys from the miner's own chain read: shares only, never a
score, and never a default where the margin is unmeasured.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from scripts.dev.miner_launchpad import king

HOTKEY = "5" + "F" * 47
COOLING = "chip-cold-plate"


def answer(**changes):
    document = {
        "schema": king.SCHEMA,
        "challenge_id": COOLING,
        "challenge_version": "1.3",
        "exam_version_label": "cooling-1.3-exam",
        "king": {"hotkey": HOTKEY, "total": 0.62, "since_epoch": 14},
        "margin": 0.04,
        "to_beat": 0.66,
        "baseline_total": None,
    }
    document.update(changes)
    return document


def test_a_king_with_a_margin_reads_its_score_to_beat():
    lines = king.words(king.parse(answer(), COOLING))
    assert lines[0].startswith("Current king: " + HOTKEY + ", score 0.6200")
    assert "since round 14" in lines[0] and "cooling-1.3-exam" in lines[0]
    assert lines[1] == (
        "Score to beat: 0.6600 (the king's score plus the margin 0.0400)."
    )
    assert king.PAUSED not in lines


def test_an_unmeasured_margin_pauses_takeovers_and_names_no_score_to_beat():
    lines = king.words(king.parse(answer(margin=None, to_beat=None), COOLING))
    assert lines[-1] == king.PAUSED
    assert not any(line.startswith("Score to beat") for line in lines)


def test_no_king_reads_carbons_baseline():
    shown = king.parse(
        answer(king=None, baseline_total=0.5, margin=None, to_beat=None), COOLING
    )
    lines = king.words(shown)
    assert (
        lines[0]
        == "No king yet: beat Carbon's baseline (0.5000, exam cooling-1.3-exam)."
    )
    assert lines[-1] == king.PAUSED
    with_margin = king.words(
        king.parse(answer(king=None, baseline_total=0.5, to_beat=0.54), COOLING)
    )
    assert with_margin[0].endswith("by the margin 0.0400, so score above 0.5400.")


@pytest.mark.parametrize(
    "changes",
    [
        {"recipe_digest": "sha256:" + "a" * 64},  # a key outside the set
        {"schema": "carbon.koth.public.v2"},
        {"challenge_id": "f02"},  # another Challenge's answer
        {"king": {"hotkey": "not-an-address", "total": 0.5, "since_epoch": 1}},
        {"king": {"hotkey": HOTKEY, "total": 0.5, "since_epoch": 1, "legs": {}}},
        {"king": {"hotkey": HOTKEY, "total": 1.5, "since_epoch": 1}},
        {"king": {"hotkey": HOTKEY, "total": True, "since_epoch": 1}},
        {"margin": None},  # a score to beat with no margin
        {"to_beat": None},  # a margin with no score to beat
        {"baseline_total": 0.5},  # a baseline beside a king
        {"exam_version_label": "x" * 65},
        {"to_beat": 0.75},  # not the king's total plus the margin
        {"king": None, "baseline_total": None},  # a score to beat with nothing to beat
    ],
)
def test_anything_outside_the_closed_shape_is_unreadable(changes):
    with pytest.raises(king.KingUnreadable):
        king.parse(answer(**changes), COOLING)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_reader_asks_the_graders_route_and_says_why_when_it_cannot():
    asked = []

    def opener(url, timeout):
        asked.append(url)
        return _Response(json.dumps(answer()).encode())

    shown, why = king.read("https://grader.example/", COOLING, opener=opener)
    assert why is None and shown["king"]["hotkey"] == HOTKEY
    assert asked == ["https://grader.example/carbon/v1/koth/chip-cold-plate"]

    def missing(url, timeout):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))

    assert king.read("https://grader.example", COOLING, opener=missing) == (
        None,
        king.NO_ROUTE,
    )

    def down(url, timeout):
        raise urllib.error.URLError("refused")

    assert king.read("https://grader.example", COOLING, opener=down) == (
        None,
        king.UNREACHABLE,
    )

    def huge(url, timeout):
        return _Response(b" " * (king.MAX_BYTES + 1))

    assert king.read("https://grader.example", COOLING, opener=huge) == (
        None,
        king.UNREADABLE,
    )
    assert king.read("ftp://grader.example", COOLING, opener=opener) == (
        None,
        king.NO_GRADER,
    )


def test_the_card_lists_each_challenge_with_a_grader_and_no_subnet_line_yet():
    shown = king.card(
        {COOLING: "https://grader.example"},
        read_one=lambda url, cid: (king.parse(answer(), cid), None),
    )
    assert shown["subnet"] is None
    assert shown["challenges"][0]["challenge_id"] == COOLING
    assert shown["challenges"][0]["lines"][0].startswith("Current king")
    unreachable = king.card(
        {COOLING: "https://grader.example"},
        read_one=lambda url, cid: (None, king.UNREACHABLE),
    )
    assert unreachable["challenges"][0]["lines"] == [king.UNREACHABLE]
    assert king.for_profile(None)["challenges"] == []


def test_the_page_reads_the_card_from_the_controller():
    root = Path(king.__file__).parent
    assert '"/api/v1/page/king"' in (root / "app.js").read_text(encoding="utf-8")
    assert 'id="overview-kings"' in (root / "index.html").read_text(encoding="utf-8")
    from scripts.dev.miner_launchpad import controller

    assert controller.KING_ROUTE == "/api/v1/page/king"


def test_a_score_to_beat_within_one_grid_step_of_total_plus_margin_is_read():
    # One Ladder grid step (eta) of stepping is tolerated; the margin is not.
    assert king.parse(answer(to_beat=0.68), COOLING)["to_beat"] == pytest.approx(0.68)
    for off in (0.66 + 0.04 / 2 + 0.001, 0.66 + 0.04, 0.66 - 0.03):
        with pytest.raises(king.KingUnreadable):
            king.parse(answer(to_beat=off), COOLING)
    baseline = {"king": None, "baseline_total": 0.5}
    king.parse(answer(**baseline, to_beat=0.54), COOLING)
    with pytest.raises(king.KingUnreadable):
        king.parse(answer(**baseline, to_beat=0.58), COOLING)
