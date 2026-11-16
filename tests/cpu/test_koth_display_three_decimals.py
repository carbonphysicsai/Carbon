"""Owner 16 Nov: "Show scores to 3 decimals, so a lead smaller than the margin is visible. Make the posted bar match the
real rule." Display only, served as NEW versions so every deployed reader keeps working (Validator-2: the Launchpad kit
on main 8b20c190 refuses any v2 rule id but its own, with no v1 fallback).

Claims: the v3 king page (``/carbon/v1/koth/<id>/v3``) and the v6 launch board show each total to 3 places, rounded
HALF UP from the exact total (a ladder row only when its exact total is its own; other rows keep the floored total);
the v3 score to beat is the crown rule's own bar (`bank_promotion.compare_private_pair`: crowned iff total > king +
margin), the exact total + the margin rounded UP to 3 places and capped at 1, named ``king_plus_margin``; with no king
the same rule runs on Carbon's baseline; the averaged bar is unchanged. Every v1/v2 king page and every v1-v5 board is
byte-identical to main 8b20c190 (pinned digests over a fixed grid), and the main kit's own reader still parses all that
the door serves at the paths it reads. Today's numbers: king 0.77951 -> 0.780, challenger 0.78701 -> 0.787, margin
0.0129 -> to_beat 0.79241 rounded up -> 0.793.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import io
import json
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import launch_board as lb
from carbon.registry.model import ChallengeKey
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
CHALLENGE = "electric-motor-magnetics"
#: The kit's king card exactly as on main 8b20c190 (git blob below): what every miner on the old kit runs.
OLD_KIT = Path(__file__).with_name("koth_old_kit_king_fixture.py")
OLD_KIT_BLOB = "ba449a53c69bc868d8bacaf666e6f7f70fd95b0c"
#: sha256 of main 8b20c190's v1 + v2 king pages over `_page_grid` (computed with that commit's koth_public).
PAGES_MAIN_8B20C190 = "c9c8a712c5a3c7a9828c3847b98999083f42e06f9ad65541ecb59cb4cfecf7f6"
#: sha256 of main 8b20c190's v1-v5 boards over `_board_grid` (computed with that commit's launch_board + koth_public).
BOARDS_MAIN_8B20C190 = (
    "25fc8199b379aa1d069ecf437b900f8a27bdc12faecc68b197b8adad85b14651"
)


def _args(**changes):
    return {
        "challenge_id": CHALLENGE,
        "challenge_version": "1.9",
        "exam_version_label": "motor-exam",
        "king": {"hotkey": KING, "total": KING_EXACT, "since_epoch": 12},
        "rebuild_noise": NOISE,
        "baseline_total": None,
        **changes,
    }


def _floored(exact, margin=MARGIN):
    """What the Ladder publishes for ``exact``: floored to its step (max(eta, the noise)), then to 9 places."""
    return lb.floor9(gf.floor_to_step(exact, margin))


def _rows(exact):
    scored = {"status": "IMPROVED", "gate_names": []}
    return [(hotkey, {"total": _floored(value)}, scored) for hotkey, value in exact]


def _v6(document, exact_totals, rows, *, crown_changes=()):
    return lb.build(
        king_document=document,
        rows=rows,
        network="testnet",
        key=SIGNER,
        version=7,
        now=NOW,
        crown_changes=list(crown_changes),
        exact_totals=exact_totals,
        rebuild_noise=NOISE,
        stability=None if document["king"] is None else "STABLE",
        crowned_utc=None,
        v6=True,
    )


def _old_kit():
    """The main 8b20c190 king card, loaded from its committed copy, after checking that copy IS that blob."""
    data = OLD_KIT.read_bytes()
    assert b"\r" not in data
    assert hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() == OLD_KIT_BLOB
    spec = importlib.util.spec_from_file_location("old_kit_king_8b20c190", OLD_KIT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- v1 / v2 / v1-v5 boards are main's, byte for byte ---------------------------------------------------------------


def _page_grid():
    for margin in (None, 0.0129, 0.0079, 0.0473):
        noise = (
            None
            if margin is None
            else {"value": margin, "measurement_digest": "sha256:" + "a" * 64}
        )
        for total in (0.0, 0.33333, 0.66, 0.6655, 0.7123, 0.77951, 0.7795, 0.995, 1.0):
            yield {
                "king": {"hotkey": KING, "total": total, "since_epoch": 12},
                "rebuild_noise": noise,
                "baseline_total": None,
            }
        for base in (None, 0.5, 0.65437):
            yield {"king": None, "rebuild_noise": noise, "baseline_total": base}


def test_every_v1_and_v2_king_page_is_mains():
    out = []
    for grid in _page_grid():
        args = {
            "challenge_id": CHALLENGE,
            "challenge_version": "1.9",
            "exam_version_label": "motor-exam",
            **grid,
        }
        out.append(kp.document(**args))
        out.append(kp.document_v2(**args))
        if grid["rebuild_noise"] is not None:
            out.append(
                kp.document_v2(crown_bar={"base": 0.7512, "margin": 0.021}, **args)
            )
    text = json.dumps(out, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(text.encode()).hexdigest() == PAGES_MAIN_8B20C190
    assert kp.TO_BEAT_RULE == "floor_plus_step_plus_margin"
    assert kp.TO_BEAT_RULES == (kp.TO_BEAT_RULE, kp.TO_BEAT_RULE_AVERAGED)


def _board_grid():
    out = []
    for margin in (0.0129, 0.0079):
        noise = {"value": margin, "measurement_digest": "sha256:" + "a" * 64}
        for king_total in (0.77951, 0.7123, None):
            a, b, c = ("5" + x * 47 for x in "ABC")
            exact = {KING: king_total} if king_total is not None else {}
            exact.update({a: 0.78701, b: 0.70049, c: 0.71101})
            king = (
                None
                if king_total is None
                else {"hotkey": KING, "total": king_total, "since_epoch": 12}
            )
            args = _args(
                king=king,
                rebuild_noise=noise,
                baseline_total=None if king else 0.65437,
            )
            scored = {"status": "IMPROVED", "gate_names": []}
            rows = [
                (h, {"total": _floored(v, margin)}, scored) for h, v in exact.items()
            ]
            rows.append(
                (
                    "5" + "N" * 47,
                    None,
                    {"status": "NOT_SCORED", "gate_names": [], "reason": "TIMED_OUT"},
                )
            )
            common = {
                "rows": rows,
                "network": "testnet",
                "key": SIGNER,
                "version": 7,
                "now": NOW,
            }
            out.append(lb.build(king_document=kp.document(**args), **common))
            two = kp.document_v2(**args)
            v2 = {
                "crown_changes": [
                    {
                        "from_hotkey": None,
                        "to_hotkey": KING,
                        "since_epoch": 12,
                        "total": 0.76,
                    }
                ],
                "exact_totals": dict(exact),
                "rebuild_noise": noise,
            }
            out.append(lb.build(king_document=two, **common, **v2))
            stable = None if king is None else "STABLE"
            out.append(lb.build(king_document=two, **common, **v2, stability=stable))
            measure = None if king is None else {"state": "MEASURED", "kept": 3, "n": 3}
            out.append(
                lb.build(
                    king_document=two,
                    **common,
                    **v2,
                    stability=stable,
                    measure=measure,
                    crown_checks=[],
                )
            )
            out.append(
                lb.build(
                    king_document=two,
                    **common,
                    **v2,
                    stability=stable,
                    crowned_utc=None if king is None else "2026-11-16T12:00:00Z",
                )
            )
    return out


def test_every_v1_to_v5_board_is_mains():
    boards = _board_grid()
    assert [b["schema"] for b in boards[:5]] == [
        lb.SCHEMA,
        lb.SCHEMA_V2,
        lb.SCHEMA_V3,
        lb.SCHEMA_V4,
        lb.SCHEMA_V5,
    ]
    text = json.dumps(boards, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(text.encode()).hexdigest() == BOARDS_MAIN_8B20C190


# --- the v3 king page --------------------------------------------------------------------------------------------


def test_todays_numbers_on_the_v3_king_page():
    doc = kp.document_v3(**_args())
    assert doc["schema"] == kp.SCHEMA_V3 == "carbon.koth.public.v3"
    assert set(doc) == kp.FIELDS_V3 == kp.FIELDS_V2
    assert doc["king"]["total"] == 0.78  # 0.77951 -> 0.780
    assert doc["margin"] == MARGIN
    assert doc["to_beat"] == 0.793  # 0.77951 + 0.0129 = 0.79241 -> 0.793
    assert doc["to_beat_rule"] == kp.TO_BEAT_RULE_EXACT == "king_plus_margin"
    assert kp.shown_total(CHALLENGER_EXACT) == 0.787  # the challenger's row
    # the lead (0.787 vs 0.780) is now visible, and so is that it is short of the bar
    assert doc["king"]["total"] < kp.shown_total(CHALLENGER_EXACT) < doc["to_beat"]
    # the rule itself: the challenger is not crowned (0.78701 <= 0.79241)
    assert not CHALLENGER_EXACT > KING_EXACT + MARGIN
    # the v2 page for the same king is main's: the floored total and the conservative bar
    two = kp.document_v2(**_args())
    assert two["king"]["total"] == 0.76
    assert two["to_beat"] == kp.to_beat_v2(0.76, MARGIN)
    assert two["to_beat_rule"] == "floor_plus_step_plus_margin"


def test_totals_round_half_up_to_three_places():
    assert kp.TOTAL_DECIMALS == 3
    assert kp.shown_total(0.7795) == 0.78  # exactly half: up
    assert kp.shown_total(0.77949999) == 0.779  # just below half: down
    assert kp.shown_total(0.7785) == 0.779
    assert kp.shown_total(0.0005) == 0.001 and kp.shown_total(0.00049) == 0.0
    assert kp.shown_total(1.0) == 1.0 and kp.shown_total(0.0) == 0.0
    doc = kp.document_v3(
        **_args(king={"hotkey": KING, "total": 0.7795, "since_epoch": 1})
    )
    assert doc["king"]["total"] == 0.78


def test_the_bar_is_rounded_up_and_capped_at_one():
    assert kp.to_beat_exact(0.7, 0.0121) == 0.713  # 0.7121 -> up
    assert kp.to_beat_exact(0.7, 0.013) == 0.713  # already on 3 places: unchanged
    assert kp.to_beat_exact(0.99, MARGIN) == 1.0  # 1.0029 -> capped
    top = kp.document_v3(
        **_args(king={"hotkey": KING, "total": 0.995, "since_epoch": 1})
    )
    assert top["to_beat"] == 1.0 and top["king"]["total"] == 0.995
    for total in (0.1, 0.33333, 0.5, 0.66, 0.77951, 0.8765, 0.9871):
        bar = kp.to_beat_exact(total, MARGIN)
        assert total + MARGIN - 1e-12 <= bar < total + MARGIN + 0.001
        assert bar == round(bar, 3)


def test_with_no_king_the_bar_is_the_exact_baseline_plus_the_margin():
    doc = kp.document_v3(**_args(king=None, baseline_total=0.65437))
    assert doc["king"] is None
    assert doc["baseline_total"] == 0.654  # half up
    assert doc["to_beat"] == 0.668  # 0.65437 + 0.0129 = 0.66727 -> up
    assert doc["to_beat_rule"] == kp.TO_BEAT_RULE_EXACT
    none = kp.document_v3(**_args(king=None, baseline_total=None))
    assert none["baseline_total"] is None and none["to_beat"] is None
    assert none["margin"] is None  # nothing to measure a margin from (v1's rule)


def test_no_margin_registered_means_no_bar():
    doc = kp.document_v3(**_args(rebuild_noise=None))
    assert doc["margin"] is None and doc["to_beat"] is None
    assert doc["king"]["total"] == 0.78


def test_the_averaged_bar_is_unchanged():
    bar = {"base": 0.7512, "margin": 0.021}
    doc = kp.document_v3(**_args(), crown_bar=bar)
    assert doc["to_beat_rule"] == kp.TO_BEAT_RULE_AVERAGED
    assert doc["to_beat"] == kp.to_beat_averaged(bar, MARGIN)
    assert doc["to_beat"] == kp.document_v2(**_args(), crown_bar=bar)["to_beat"]
    assert doc["king"]["total"] == 0.78


class _View:
    exam_version_label = "motor-exam"
    baseline_total = None
    rebuild_noise = NOISE

    def __init__(self, king=KING_EXACT, crown_bar=None):
        self._king, self._bar = king, crown_bar

    def king(self):
        if self._king is None:
            return None
        return {"hotkey": KING, "total": self._king, "since_epoch": 12}

    def crown_bar(self, _challenge_id):
        return self._bar


def _door(view):
    from carbon.challenge_validator.direct_intake import DirectRecipeIntake

    intake = SimpleNamespace(challenge=ChallengeKey(CHALLENGE, "1.9"), koth_view=view)
    return lambda path: DirectRecipeIntake._koth(intake, kp.PATH + path)


def test_the_door_serves_v3_at_its_own_path_and_v1_v2_unchanged():
    door = _door(_View())
    three = door(CHALLENGE + kp.V3_SUFFIX)
    assert three.status == 200 and three.body == kp.document_v3(**_args())
    assert door(CHALLENGE + kp.V2_SUFFIX).body == kp.document_v2(**_args())
    assert door(CHALLENGE).body == kp.document(**_args())
    assert door("other" + kp.V3_SUFFIX).status == 404
    averaged = _door(_View(crown_bar={"base": 0.7512, "margin": 0.021}))
    assert averaged(CHALLENGE + kp.V3_SUFFIX).body["to_beat_rule"] == (
        kp.TO_BEAT_RULE_AVERAGED
    )
    assert _door(None)(CHALLENGE + kp.V3_SUFFIX).status == 404


# --- readers: the old kit, the new kit -------------------------------------------------------------------------


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _opener(door, asked):
    def opener(url, timeout):
        asked.append(url)
        answer = door(url.split(kp.PATH, 1)[1])
        if answer.status != 200:
            raise urllib.error.HTTPError(url, answer.status, "x", {}, None)
        return _Response(json.dumps(answer.body).encode())

    return opener


def test_the_old_kit_still_reads_everything_the_door_serves_where_it_reads():
    old = _old_kit()
    assert old.TO_BEAT_RULE == "floor_plus_step_plus_margin"
    views = [
        _View(),
        _View(king=0.7795),
        _View(king=0.995),
        _View(king=None),
        _View(crown_bar={"base": 0.7512, "margin": 0.021}),
    ]
    for view in views:
        door = _door(view)
        # the paths the old kit reads: v2, then v1
        for path in (CHALLENGE + kp.V2_SUFFIX, CHALLENGE):
            answer = door(path)
            if answer.status == 200:
                assert old.parse(answer.body, CHALLENGE)["challenge_id"] == CHALLENGE
        asked = []
        shown, why = old.read(
            "https://door.example", CHALLENGE, opener=_opener(door, asked)
        )
        assert asked == [f"https://door.example{kp.PATH}{CHALLENGE}{kp.V2_SUFFIX}"]
        assert why is None
        assert (shown["king"] is None) == (view.king() is None)
    # why v3 is its own path: the old kit refuses its rule id (it never asks for it)
    with pytest.raises(old.KingUnreadable):
        old.parse(kp.document_v3(**_args()), CHALLENGE)


def test_the_new_kit_reads_v3_first_and_falls_back():
    asked = []
    shown, why = card.read(
        "https://door.example", CHALLENGE, opener=_opener(_door(_View()), asked)
    )
    assert why is None and shown["exact_bar"] is True and "conservative" not in shown
    assert asked == [f"https://door.example{kp.PATH}{CHALLENGE}{kp.V3_SUFFIX}"]
    lines = card.words(shown)
    assert any("Score above 0.7930 to take the crown" in line for line in lines)
    assert any("score 0.7800" in line for line in lines)
    broken = {**kp.document_v3(**_args()), "to_beat": 0.79}
    with pytest.raises(card.KingUnreadable):
        card.parse(broken, CHALLENGE)

    # a door before 16 Nov: no v3 route, so v2 (its floored rule, still read with its own words), then v1
    def older(path):
        if path.endswith(kp.V3_SUFFIX):
            return SimpleNamespace(status=404, body={"refused": "not_found"})
        return _door(_View())(path)

    asked = []
    shown, why = card.read(
        "https://door.example", CHALLENGE, opener=_opener(older, asked)
    )
    assert why is None and shown["conservative"] is True
    assert [u.rsplit("/", 1)[1] for u in asked] == ["v3", "v2"]
    assert card.parse(kp.document(**_args()), CHALLENGE)["to_beat"] == pytest.approx(
        0.76 + MARGIN
    )


# --- the v6 launch board ------------------------------------------------------------------------------------------


def test_todays_numbers_on_the_v6_board():
    exact = {KING: KING_EXACT, CHALLENGER: CHALLENGER_EXACT, THIRD: 0.70049}
    board = _v6(
        kp.document_v3(**_args()),
        exact,
        _rows([(KING, KING_EXACT), (CHALLENGER, CHALLENGER_EXACT), (THIRD, 0.70049)]),
        crown_changes=[
            {
                "from_hotkey": None,
                "to_hotkey": KING,
                "since_epoch": 12,
                "total": kp.shown_total(KING_EXACT),
            }
        ],
    )
    assert board["schema"] == lb.SCHEMA_V6 == "carbon.validator.launch-board.v6"
    rows = {r["hotkey"]: (r["rank"], r["total"]) for r in board["ladder"]}
    assert rows == {KING: (1, 0.78), CHALLENGER: (2, 0.787), THIRD: (3, 0.7)}
    assert board["king"]["king"]["total"] == 0.78 and board["king"]["to_beat"] == 0.793
    assert board["king"]["to_beat_rule"] == "king_plus_margin"
    assert board["crown_changes"][0]["total"] == 0.78
    raw = lb._canonical({k: v for k, v in board.items() if k != "signature"})
    for value in (KING_EXACT, CHALLENGER_EXACT, 0.70049, KING_EXACT + MARGIN):
        assert repr(value) not in raw  # no exact total, no exact bar
    assert lb.verify(board, SIGNER.public_key) == board
    # the v6 signature is its own: it never verifies as a v5 board
    as_v5 = {**board, "schema": lb.SCHEMA_V5}
    with pytest.raises(lb.BoardRefused):
        lb.verify(as_v5, SIGNER.public_key)


def test_a_v6_board_takes_only_a_v3_king_page_and_the_kings_exact_total():
    rows = _rows([(KING, KING_EXACT)])
    with pytest.raises(lb.BoardRefused):
        _v6(kp.document_v2(**_args()), {KING: KING_EXACT}, rows)  # the floored rule
    averaged_v2 = kp.document_v2(**_args(), crown_bar={"base": 0.7512, "margin": 0.021})
    with pytest.raises(lb.BoardRefused):
        _v6(averaged_v2, {KING: KING_EXACT}, rows)  # a v2 page, even with a v3 rule id
    with pytest.raises(lb.BoardRefused):
        _v6(kp.document_v3(**_args()), {}, rows)  # no exact total for the king
    with pytest.raises(lb.BoardRefused):
        lb.build(
            king_document=kp.document_v3(**_args()),
            rows=rows,
            network="testnet",
            key=SIGNER,
            version=7,
            crown_changes=[],
            exact_totals={KING: KING_EXACT},
            rebuild_noise=NOISE,
            stability="STABLE",
            v6=True,
        )  # v6 is v5's shape: it needs crowned_utc
    # a v2-v5 board never takes the v3 page's rule
    with pytest.raises(lb.BoardRefused):
        lb.build(
            king_document=kp.document_v3(**_args()),
            rows=rows,
            network="testnet",
            key=SIGNER,
            version=7,
            crown_changes=[],
            exact_totals={KING: KING_EXACT},
            rebuild_noise=NOISE,
        )


def test_a_row_without_its_own_exact_total_keeps_its_floored_total():
    # THIRD holds an exact total of another exam (it does not floor to his row's total); FOURTH holds none
    fourth = "5" + "F" * 47
    rows = _rows([(KING, KING_EXACT), (CHALLENGER, CHALLENGER_EXACT), (THIRD, 0.70049)])
    rows.append(
        (fourth, {"total": _floored(0.6512)}, {"status": "IMPROVED", "gate_names": []})
    )
    exact = {KING: KING_EXACT, CHALLENGER: CHALLENGER_EXACT, THIRD: 0.61}
    board = _v6(kp.document_v3(**_args()), exact, rows)
    shown = {r["hotkey"]: r["total"] for r in board["ladder"]}
    assert shown[THIRD] == _floored(0.70049) == 0.7
    assert shown[fourth] == _floored(0.6512) == 0.64
    assert shown[CHALLENGER] == 0.787


def test_the_true_order_is_unchanged_by_the_display():
    a, b = "5" + "A" * 47, "5" + "B" * 47
    exact = {KING: KING_EXACT, a: 0.70049, b: 0.71101}
    rows = _rows([(KING, KING_EXACT), (a, 0.70049), (b, 0.71101)])
    six = _v6(kp.document_v3(**_args()), exact, rows)
    assert [(r["hotkey"], r["rank"], r["total"]) for r in six["ladder"]] == [
        (KING, 1, 0.78),
        (b, 2, 0.711),
        (a, 3, 0.7),
    ]
    five = lb.build(
        king_document=kp.document_v2(**_args()),
        rows=rows,
        network="testnet",
        key=SIGNER,
        version=7,
        now=NOW,
        crown_changes=[],
        exact_totals=exact,
        rebuild_noise=NOISE,
        stability="STABLE",
        crowned_utc=None,
    )
    assert [(r["hotkey"], r["rank"]) for r in five["ladder"]] == [
        (r["hotkey"], r["rank"]) for r in six["ladder"]
    ]
    assert {r["total"] for r in five["ladder"][1:]} == {_floored(0.71)}  # v5: floored


def test_the_door_serves_a_three_place_v6_board_and_never_a_three_place_v5(
    monkeypatch,
):
    from carbon.challenge_validator import koth_registry
    from carbon.challenge_validator import launch_board_file as lbf

    monkeypatch.setattr(koth_registry, "rebuild_noise", lambda *_a, **_k: NOISE)
    rows = _rows([(KING, KING_EXACT), (CHALLENGER, CHALLENGER_EXACT)])
    exact = {KING: KING_EXACT, CHALLENGER: CHALLENGER_EXACT}
    six = _v6(kp.document_v3(**_args()), exact, rows)
    assert lbf._on_the_ladder_step(six)
    off = json.loads(json.dumps(six))
    off["schema"] = (
        lb.SCHEMA_V5
    )  # the same 3-place totals on a v5 board: off the Ladder step
    assert not lbf._on_the_ladder_step(off)
    finer = json.loads(json.dumps(six))
    finer["ladder"][1]["total"] = 0.7871  # finer than 3 places and off the step
    assert not lbf._on_the_ladder_step(finer)


def test_the_dashboard_reads_a_v6_board_and_still_every_old_rule():
    from carbon.dashboard import feed, launch

    assert launch.SCHEMA_V6 == lb.SCHEMA_V6 and launch.DOMAIN_V6 == lb.BOARD_DOMAIN_V6
    assert set(launch.TO_BEAT_RULES) == {
        kp.TO_BEAT_RULE,
        kp.TO_BEAT_RULE_AVERAGED,
        kp.TO_BEAT_RULE_EXACT,
    }
    exact = {KING: KING_EXACT, CHALLENGER: CHALLENGER_EXACT}
    six = _v6(
        kp.document_v3(**_args()),
        exact,
        _rows([(KING, KING_EXACT), (CHALLENGER, CHALLENGER_EXACT)]),
    )
    trust = feed.Trust(keys=frozenset({SIGNER.public_key}))
    shown = feed.project(json.loads(json.dumps(six)), trust)
    assert shown["source_schema"] == lb.SCHEMA_V6
    assert shown["launch"]["to_beat"] == 0.793
    assert shown["launch"]["to_beat_rule"] == kp.TO_BEAT_RULE_EXACT
    worker = (
        Path(__file__).resolve().parents[2] / "carbon/dashboard/worker/feed.mjs"
    ).read_text(encoding="utf-8")
    assert f'const LAUNCH_TO_BEAT_RULE = "{kp.TO_BEAT_RULE}";' in worker
    assert f'const LAUNCH_TO_BEAT_RULE_EXACT = "{kp.TO_BEAT_RULE_EXACT}";' in worker
    assert f'export const LAUNCH_SCHEMA_V6 = "{lb.SCHEMA_V6}";' in worker
