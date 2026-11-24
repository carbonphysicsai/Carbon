"""A version ranked by its accuracy result shows it at two decimals, rounded down, in the true order (owner G-LEAD-91).

Claims: the decimals follow the number the crown row names, never a Challenge; the king page v3, its bar, the changes of king
decided on that number and the board rows show two decimals, the number down and the bar up; the signed board carries them
whatever the door's page shows; the order stays the exact one; every version ranked by its total is byte for byte as before.

Synthetic values only.
"""

from __future__ import annotations

import pytest

from carbon.challenge_validator import crown_official, koth_public
from scripts.dev import launch_board_operator as operator
from scripts.dev.miner_launchpad import king as card
from tests.cpu.test_koth_display_three_decimals import _args
from tests.cpu.test_ranked_number import (
    CHALLENGE,
    EXAM,
    HOTKEYS,
    TASKS,
    VERSION,
    _install,
    _Kept,
    _kept,
)

KING = "5" + "K" * 47


def test_the_decimals_follow_the_ranked_number(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, {"margin": 0.0129, "score": "A"})
    assert crown_official.shown_decimals(CHALLENGE, VERSION) == 2
    assert crown_official.shown_decimals(CHALLENGE, "1.7") is None
    _install(tmp_path, monkeypatch, {"margin": 0.0129})
    assert crown_official.shown_decimals(CHALLENGE, VERSION) is None


@pytest.mark.parametrize(
    ("value", "shown"),
    [(0.97038, 0.97), (0.9799999, 0.97), (0.98, 0.98), (0.969999, 0.96), (1.0, 1.0)],
)
def test_the_number_is_rounded_down(value, shown):
    assert koth_public.shown_total(value, 2) == shown <= value


def test_the_bar_is_rounded_up_to_the_same_decimals():
    assert koth_public.to_beat_exact(0.97038, 0.0129, 2) == 0.99
    assert koth_public.to_beat_exact(0.97, 0.01, 2) == 0.98
    assert koth_public.to_beat_exact(0.995, 0.0129, 2) == 1.0
    assert koth_public.to_beat_exact(0.7, 0.0121) == 0.713


def test_the_king_page_shows_two_and_one_without_decimals_is_as_before():
    args = _args()
    exact = args["king"]["total"]
    plain = koth_public.document_v3(**args)
    two = koth_public.document_v3(**args, decimals=2)
    assert two["king"]["total"] == koth_public.shown_total(exact, 2)
    assert set(two) == set(plain)
    assert koth_public.document_v3(**args, decimals=None) == plain
    for name in ("total", "since_epoch", "hotkey"):
        if name != "total":
            assert two["king"][name] == plain["king"][name]
    # the Launchpad's reader takes both
    assert card.parse(plain, args["challenge_id"])["exact_bar"] is True
    assert card.parse(two, args["challenge_id"])["exact_bar"] is True
    with pytest.raises(card.KingUnreadable):
        card.parse({**two, "to_beat": two["king"]["total"]}, args["challenge_id"])


def test_only_a_change_decided_on_the_number_is_shown_at_its_decimals(
    tmp_path, monkeypatch
):
    _install(tmp_path, monkeypatch, {"margin": 0.0129, "score": "A"})
    store = _Kept(
        [_kept("a", 0.5129, 0.7567), _kept("b", 0.7567, 0.5129)],
        king=TASKS["a"],
        journal=[(TASKS["b"], None), (TASKS["a"], TASKS["b"])],
        decided=[TASKS["a"]],
    )
    view = koth_public.PoolKingView(
        open_store=lambda: store,
        epoch_of=lambda model: 7,
        exam_version_label="exam",
        rebuild_noise_of=lambda: None,
        value=crown_official.reader(CHALLENGE, VERSION),
        decimals=2,
    )
    assert [c["total"] for c in view.crown_changes(v3=True)] == [0.75, 0.757]


def test_the_signed_board_never_carries_a_finer_number_than_the_rule():
    door = {
        "king": {"hotkey": KING, "total": 0.97, "since_epoch": 3},
        "margin": 0.0129,
        "to_beat": 0.984,
    }
    shown = operator.shown_king(door, {KING: 0.97038}, 2)
    assert (shown["king"]["total"], shown["to_beat"]) == (0.97, 0.99)
    assert (
        operator.shown_king(
            {**door, "king": {**door["king"], "total": 0.9704}}, {KING: 0.97038}, 2
        )
        == shown
    )
    assert operator.shown_king(door, {KING: 0.97038}, None) is door
    assert operator.shown_king({**door, "king": None}, {}, 2)["king"] is None
    with pytest.raises(operator.OperatorRefused):
        operator.shown_king(door, {}, 2)


def test_the_board_rows_are_two_decimals_in_the_exact_order():
    from carbon.challenge_validator import launch_board

    latest = {"status": "IMPROVED", "gate_names": []}
    a, b, k = HOTKEYS["a"], HOTKEYS["b"], HOTKEYS["k"]
    rows = [
        (a, {"total": 0.96}, latest),
        (b, {"total": 0.96}, latest),
        (k, {"total": 0.96}, latest),
    ]
    exact = {a: 0.96512, b: 0.96909, k: 0.97038}
    board = launch_board.ladder_rows(
        rows,
        exact=exact,
        king_hotkey=k,
        king_total=0.96,
        king_shown=0.97,
        three=True,
        decimals=2,
    )
    assert [(r["hotkey"], r["total"], r["rank"]) for r in board] == [
        (k, 0.97, 1),
        (b, 0.96, 2),
        (a, 0.96, 3),
    ]
    before = launch_board.ladder_rows(
        rows, exact=exact, king_hotkey=k, king_total=0.96, king_shown=0.97, three=True
    )
    assert [r["total"] for r in before] == [0.97, 0.969, 0.965]


def test_the_exam_key_fixture_is_a_digest():
    assert EXAM.startswith("sha256:")
