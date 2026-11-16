"""Owner 16 Nov: "Show scores to 3 decimals, so a lead smaller than the margin is visible. Make the posted bar match the
real rule." Display only, v2 documents only.

Claims: a v2 king page and a v2-v5 launch board show each total to 3 places, rounded HALF UP from the exact total (a
ladder row only when its exact total is its own; other rows keep the floored total); the v2 score to beat is the crown
rule's own bar (`bank_promotion.compare_private_pair`: crowned iff total > king + margin), the exact total + the margin
rounded UP to 3 places and capped at 1, named ``king_plus_margin``; with no king the same rule runs on Carbon's
baseline; the averaged bar is unchanged; every v1 document is byte-identical; the crown is decided on exact totals, so
nothing here changes who wins. Today's numbers: king 0.77951 -> 0.780, challenger 0.78701 -> 0.787, margin 0.0129 ->
to_beat 0.79241 rounded up -> 0.793.
"""

from __future__ import annotations

import datetime
import json

import pytest

from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import launch_board as lb
from carbon.scoring import grade_feedback as gf
from scripts.dev.miner_launchpad import king as card

KING = "5" + "K" * 47
CHALLENGER = "5" + "C" * 47
THIRD = "5" + "T" * 47
MARGIN = 0.0129
NOISE = {"value": MARGIN, "measurement_digest": "sha256:" + "a" * 64}
KING_EXACT = 0.77951
CHALLENGER_EXACT = 0.78701
NOW = datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC)
SIGNER = lb.LaunchBoardKey(bytes(range(32)))


def _args(**changes):
    return {
        "challenge_id": "electric-motor-magnetics",
        "challenge_version": "1.9",
        "exam_version_label": "motor-exam",
        "king": {"hotkey": KING, "total": KING_EXACT, "since_epoch": 12},
        "rebuild_noise": NOISE,
        "baseline_total": None,
        **changes,
    }


def _floored(exact):
    """What the Ladder publishes for ``exact``: floored to its step (max(eta, the noise)), then to 9 places."""
    return lb.floor9(gf.floor_to_step(exact, MARGIN))


def _rows(exact):
    scored = {"status": "IMPROVED", "gate_names": []}
    return [(hotkey, {"total": _floored(value)}, scored) for hotkey, value in exact]


def _build(document, exact_totals, rows, *, v2=True):
    return lb.build(
        king_document=document,
        rows=rows,
        network="testnet",
        key=SIGNER,
        version=7,
        now=NOW,
        crown_changes=[] if v2 else None,
        exact_totals=exact_totals if v2 else None,
        rebuild_noise=NOISE if v2 else lb._REQUIRED,
    )


# --- the king page ------------------------------------------------------------------------------------------------


def test_todays_numbers_on_the_v2_king_page():
    doc = kp.document_v2(**_args())
    assert doc["king"]["total"] == 0.78  # 0.77951 -> 0.780
    assert doc["margin"] == MARGIN
    assert doc["to_beat"] == 0.793  # 0.77951 + 0.0129 = 0.79241 -> 0.793
    assert doc["to_beat_rule"] == kp.TO_BEAT_RULE == "king_plus_margin"
    assert kp.shown_total(CHALLENGER_EXACT) == 0.787  # the challenger's row
    # the lead (0.787 vs 0.780) is now visible, and so is that it is short of the bar
    assert doc["king"]["total"] < kp.shown_total(CHALLENGER_EXACT) < doc["to_beat"]
    # the rule itself: the challenger is not crowned (0.78701 <= 0.79241)
    assert not CHALLENGER_EXACT > KING_EXACT + MARGIN


def test_totals_round_half_up_to_three_places():
    assert kp.TOTAL_DECIMALS == 3
    assert kp.shown_total(0.7795) == 0.78  # exactly half: up
    assert kp.shown_total(0.77949999) == 0.779  # just below half: down
    assert kp.shown_total(0.7785) == 0.779
    assert kp.shown_total(0.0005) == 0.001 and kp.shown_total(0.00049) == 0.0
    assert kp.shown_total(1.0) == 1.0 and kp.shown_total(0.0) == 0.0
    # a king total exactly on a half shows up on the page
    doc = kp.document_v2(
        **_args(king={"hotkey": KING, "total": 0.7795, "since_epoch": 1})
    )
    assert doc["king"]["total"] == 0.78


def test_the_bar_is_rounded_up_and_capped_at_one():
    assert kp.to_beat_exact(0.7, 0.0121) == 0.713  # 0.7121 -> up
    assert kp.to_beat_exact(0.7, 0.013) == 0.713  # already on 3 places: unchanged
    assert kp.to_beat_exact(0.99, MARGIN) == 1.0  # 1.0029 -> capped
    top = kp.document_v2(
        **_args(king={"hotkey": KING, "total": 0.995, "since_epoch": 1})
    )
    assert top["to_beat"] == 1.0 and top["king"]["total"] == 0.995
    for total in (0.1, 0.33333, 0.5, 0.66, 0.77951, 0.8765, 0.9871):
        bar = kp.to_beat_exact(total, MARGIN)
        assert total + MARGIN - 1e-12 <= bar < total + MARGIN + 0.001
        assert bar == round(bar, 3)


def test_with_no_king_the_bar_is_the_exact_baseline_plus_the_margin():
    doc = kp.document_v2(**_args(king=None, baseline_total=0.65437))
    assert doc["king"] is None
    assert doc["baseline_total"] == 0.654  # half up
    assert doc["to_beat"] == 0.668  # 0.65437 + 0.0129 = 0.66727 -> up
    assert doc["to_beat_rule"] == kp.TO_BEAT_RULE
    none = kp.document_v2(**_args(king=None, baseline_total=None))
    assert none["baseline_total"] is None and none["to_beat"] is None
    assert none["margin"] is None  # nothing to measure a margin from (v1's rule)


def test_no_margin_registered_means_no_bar():
    doc = kp.document_v2(**_args(rebuild_noise=None))
    assert doc["margin"] is None and doc["to_beat"] is None
    assert doc["king"]["total"] == 0.78


def test_the_averaged_bar_is_unchanged():
    bar = {"base": 0.7512, "margin": 0.021}
    doc = kp.document_v2(**_args(), crown_bar=bar)
    assert (
        doc["to_beat_rule"]
        == kp.TO_BEAT_RULE_AVERAGED
        == "mean_floor_plus_step_plus_margin_n"
    )
    assert doc["to_beat"] == kp.to_beat_averaged(bar, MARGIN)
    assert (
        doc["king"]["total"] == 0.78
    )  # the king's total is shown to 3 places here too


def test_every_v1_king_page_is_byte_identical():
    for args in (
        _args(),
        _args(king=None, baseline_total=0.65437),
        _args(rebuild_noise=None),
        _args(king={"hotkey": KING, "total": 0.995, "since_epoch": 1}),
    ):
        before = json.dumps(kp.document(**args), sort_keys=True)
        kp.document_v2(**args)
        after = json.dumps(kp.document(**args), sort_keys=True)
        assert before == after
    one = kp.document(**_args())
    # v1 still floors to the Ladder step (max(eta, noise) = 0.02) and adds the margin
    assert one["king"]["total"] == gf.floor_to_step(KING_EXACT, MARGIN) == 0.76
    assert one["to_beat"] == pytest.approx(0.76 + MARGIN)
    assert set(one) == kp.FIELDS and "to_beat_rule" not in one


def test_the_launchpad_card_reads_the_new_bar():
    answer = card.parse(kp.document_v2(**_args()), "electric-motor-magnetics")
    assert answer["exact_bar"] is True and "conservative" not in answer
    lines = card.words(answer)
    assert any("Score above 0.7930 to take the crown" in line for line in lines)
    assert any("score 0.7800" in line for line in lines)
    broken = {**kp.document_v2(**_args()), "to_beat": 0.79}
    with pytest.raises(card.KingUnreadable):
        card.parse(broken, "electric-motor-magnetics")
    # a grader before 16 Nov (the floored rule) is still read, with its own words
    old = {
        **kp.document_v2(**_args()),
        "king": {"hotkey": KING, "total": 0.76, "since_epoch": 12},
        "to_beat": kp.to_beat_v2(0.76, MARGIN),
        "to_beat_rule": kp.TO_BEAT_RULE_FLOOR,
    }
    assert card.parse(old, "electric-motor-magnetics")["conservative"] is True


def test_the_dashboard_readers_accept_the_new_rule_id():
    from pathlib import Path

    from carbon.dashboard import launch

    assert launch.TO_BEAT_RULE == kp.TO_BEAT_RULE
    assert set(launch.TO_BEAT_RULES) == set(kp.TO_BEAT_RULES)
    worker = (
        Path(__file__).resolve().parents[2] / "carbon/dashboard/worker/feed.mjs"
    ).read_text(encoding="utf-8")
    assert f'const LAUNCH_TO_BEAT_RULE = "{kp.TO_BEAT_RULE}";' in worker
    assert f'const LAUNCH_TO_BEAT_RULE_FLOOR = "{kp.TO_BEAT_RULE_FLOOR}";' in worker


# --- the launch board ----------------------------------------------------------------------------------------------


def test_todays_numbers_on_the_v2_board():
    exact = {KING: KING_EXACT, CHALLENGER: CHALLENGER_EXACT, THIRD: 0.70049}
    board = _build(
        kp.document_v2(**_args()),
        exact,
        _rows([(KING, KING_EXACT), (CHALLENGER, CHALLENGER_EXACT), (THIRD, 0.70049)]),
    )
    rows = {r["hotkey"]: (r["rank"], r["total"]) for r in board["ladder"]}
    assert rows == {KING: (1, 0.78), CHALLENGER: (2, 0.787), THIRD: (3, 0.7)}
    assert board["king"]["king"]["total"] == 0.78 and board["king"]["to_beat"] == 0.793
    assert board["king"]["to_beat_rule"] == "king_plus_margin"
    raw = lb._canonical({k: v for k, v in board.items() if k != "signature"})
    for value in (KING_EXACT, CHALLENGER_EXACT, 0.70049, KING_EXACT + MARGIN):
        assert repr(value) not in raw  # no exact total, no exact bar
    assert lb.verify(board, SIGNER.public_key) == board


def test_a_row_without_its_own_exact_total_keeps_its_floored_total():
    # THIRD holds an exact total of another exam (it does not floor to his row's total); FOURTH holds none
    fourth = "5" + "F" * 47
    rows = _rows([(KING, KING_EXACT), (CHALLENGER, CHALLENGER_EXACT), (THIRD, 0.70049)])
    rows.append(
        (fourth, {"total": _floored(0.6512)}, {"status": "IMPROVED", "gate_names": []})
    )
    exact = {KING: KING_EXACT, CHALLENGER: CHALLENGER_EXACT, THIRD: 0.61}
    board = _build(kp.document_v2(**_args()), exact, rows)
    shown = {r["hotkey"]: r["total"] for r in board["ladder"]}
    assert shown[THIRD] == _floored(0.70049) == 0.7
    assert shown[fourth] == _floored(0.6512) == 0.64
    assert shown[CHALLENGER] == 0.787


def test_the_true_order_is_unchanged_by_the_display():
    # two challengers in one step cell: ordered by exact total, shown to 3 places
    a, b = "5" + "A" * 47, "5" + "B" * 47
    exact = {KING: KING_EXACT, a: 0.70049, b: 0.71101}
    board = _build(
        kp.document_v2(**_args()),
        exact,
        _rows([(KING, KING_EXACT), (a, 0.70049), (b, 0.71101)]),
    )
    assert [(r["hotkey"], r["rank"], r["total"]) for r in board["ladder"]] == [
        (KING, 1, 0.78),
        (b, 2, 0.711),
        (a, 3, 0.7),
    ]


def test_every_v1_board_is_byte_identical():
    rows = _rows([(KING, KING_EXACT), (CHALLENGER, CHALLENGER_EXACT)])
    document = kp.document(**_args())
    before = json.dumps(_build(document, None, rows, v2=False), sort_keys=True)
    _build(kp.document_v2(**_args()), {KING: KING_EXACT}, rows)
    after = json.dumps(_build(document, None, rows, v2=False), sort_keys=True)
    assert before == after
    v1 = json.loads(after)
    assert v1["schema"] == lb.SCHEMA
    assert {r["hotkey"]: r["total"] for r in v1["ladder"]} == {
        KING: 0.76,
        CHALLENGER: 0.78,
    }


def test_the_door_serves_a_three_place_v2_board_and_still_checks_v1(monkeypatch):
    from carbon.challenge_validator import koth_registry
    from carbon.challenge_validator import launch_board_file as lbf

    monkeypatch.setattr(koth_registry, "rebuild_noise", lambda *_a, **_k: NOISE)
    rows = _rows([(KING, KING_EXACT), (CHALLENGER, CHALLENGER_EXACT)])
    exact = {KING: KING_EXACT, CHALLENGER: CHALLENGER_EXACT}
    two = _build(kp.document_v2(**_args()), exact, rows)
    assert lbf._on_the_ladder_step(two)
    one = _build(kp.document(**_args()), None, rows, v2=False)
    assert lbf._on_the_ladder_step(one)
    # v1 never accepts a 3-place total that is off the Ladder step
    off = json.loads(json.dumps(one))
    off["ladder"][0]["total"] = 0.787
    assert not lbf._on_the_ladder_step(off)
    # and a v2 board never accepts a total finer than 3 places that is off the step
    finer = json.loads(json.dumps(two))
    finer["ladder"][1]["total"] = 0.7871
    assert not lbf._on_the_ladder_step(finer)
