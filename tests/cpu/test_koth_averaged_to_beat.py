"""The miner card's score to beat on a door with crown averaging on (Lead 5 Nov, the Validator's kings trace).

With averaging on, a single screening grade must beat the king's N-rebuild MEAN by more than margin_N
(`crown_average.Active.screening`); the card still showed the king's single grade plus the rebuild noise, which can
overstate or understate that bar. Claims: the v2 king document then states the averaged bar under its own rule,
``floor(mean, step) + step + margin_N`` rounded up (a KING_UNSTABLE king: his single total; no king: the baseline), never
below the true bar; it publishes only that sum (the closed v2 field set: no mean, no margin_N, no seed), keeps the king's
graded total and the rebuild-noise margin; with averaging off, or no registered margin_N, or an unmeasured king, the
document is byte-for-byte the single-grade one; v1 is untouched; the board builder, the dashboard reader, the Worker
projection and the Launchpad reader accept the new rule, and each words it as an average. Synthetic values only.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_launch_board_feed import CHALLENGE, KING, NOW, _rows, _signer

from carbon.challenge_validator import crown_average, koth_registry
from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import launch_board as lb
from carbon.registry.model import ChallengeKey
from carbon.scoring import grade_feedback as gf
from scripts.dev.miner_launchpad import king as card

HOTKEY = "5" + "F" * 47
KEY = ChallengeKey("electric-motor-magnetics", "1.3")
NOISE = {"value": 0.03, "measurement_digest": "sha256:" + "a" * 64}
MARGIN_N = 0.02


def _args(**changes):
    return {
        "challenge_id": KEY.challenge_id,
        "challenge_version": "1.3",
        "exam_version_label": "motor-exam",
        "king": {"hotkey": HOTKEY, "total": 0.7123, "since_epoch": 12},
        "rebuild_noise": NOISE,
        "baseline_total": None,
        **changes,
    }


def _expected(base, noise=0.03, margin=MARGIN_N):
    floored = gf.floor_to_step(base, noise)
    return min(1.0, math.ceil((floored + gf.step(noise) + margin) * 1000 - 1e-9) / 1000)


def test_the_averaged_bar_is_the_kings_mean_plus_margin_n_rounded_up_under_its_own_rule():
    single = kp.document_v2(**_args())
    doc = kp.document_v2(**_args(), crown_bar={"base": 0.6512, "margin": MARGIN_N})
    assert (
        doc["to_beat_rule"]
        == kp.TO_BEAT_RULE_AVERAGED
        == "mean_floor_plus_step_plus_margin_n"
    )
    assert doc["to_beat"] == pytest.approx(_expected(0.6512))
    # a mean below the single grade gives the LOWER bar the owner asked about; the single-grade bar would overstate it
    assert doc["to_beat"] < single["to_beat"]
    # everything else is the single-grade document: the king's graded total, the rebuild-noise margin, the closed fields
    assert {k: v for k, v in doc.items() if k not in ("to_beat", "to_beat_rule")} == {
        k: v for k, v in single.items() if k not in ("to_beat", "to_beat_rule")
    }
    assert set(doc) == kp.FIELDS_V2
    shown = json.dumps(doc)
    assert (
        "0.6512" not in shown and "0.02" not in shown
    )  # neither the mean nor margin_N on its own


@pytest.mark.parametrize(
    "mean", [0.0, 0.1234567, 0.33, 0.5, 0.6999999, 0.87, 0.97, 0.999]
)
@pytest.mark.parametrize("margin", [0.0, 0.00606, 0.02, 0.05])
def test_the_published_bar_is_never_below_the_true_bar(mean, margin):
    doc = kp.document_v2(**_args(), crown_bar={"base": mean, "margin": margin})
    assert doc["to_beat"] >= min(1.0, mean + margin) - 1e-12


def test_an_unstable_king_or_no_king_uses_the_total_that_stands_for_the_mean():
    no_king = kp.document_v2(
        **_args(king=None, baseline_total=0.4),
        crown_bar={"base": 0.4, "margin": MARGIN_N},
    )
    assert no_king["to_beat"] == pytest.approx(_expected(0.4))
    assert no_king["to_beat_rule"] == kp.TO_BEAT_RULE_AVERAGED


def test_without_a_crown_bar_or_a_rebuild_noise_nothing_changes():
    assert kp.document_v2(**_args(), crown_bar=None) == kp.document_v2(**_args())
    unmeasured = kp.document_v2(
        **_args(rebuild_noise=None), crown_bar={"base": 0.6, "margin": MARGIN_N}
    )
    assert unmeasured == kp.document_v2(**_args(rebuild_noise=None))
    assert (
        unmeasured["to_beat"] is None and unmeasured["to_beat_rule"] == kp.TO_BEAT_RULE
    )


@pytest.mark.parametrize(
    "bar",
    [
        {"base": 0.6},
        {"base": 1.2, "margin": 0.02},
        {"base": 0.6, "margin": float("nan")},
        [0.6, 0.02],
    ],
)
def test_a_malformed_crown_bar_refuses(bar):
    with pytest.raises(kp.KothPublicRefused, match="koth_crown_bar"):
        kp.document_v2(**_args(), crown_bar=bar)


CURRENT = "sha256:" + "c" * 64
OLD_KEY = "sha256:" + "0" * 64


class _Store:
    """A king whose latest grade is on CURRENT; his mean / unstable flag were filed on ``measured_on``."""

    def __init__(
        self,
        incumbent,
        standing,
        *,
        mean=None,
        unstable=False,
        baseline=None,
        measured_on=CURRENT,
    ):
        self._incumbent, self._standing = incumbent, standing
        self._mean, self._unstable, self._baseline = mean, unstable, baseline
        self._measured_on = measured_on

    def incumbent(self):
        return self._incumbent

    def incumbent_standing(self, model_id):
        return self._standing

    def incumbent_evaluation_key(self, model_id):
        return CURRENT

    def crown_mean(self, model_id, evaluation_key=None):
        return self._mean if evaluation_key in (None, self._measured_on) else None

    def crown_average_unstable(self, model_id, evaluation_key=None):
        if evaluation_key in (None, self._measured_on):
            return self._unstable
        return False

    def latest_baseline(self, challenge_id):
        return self._baseline


KING_ROW = {"model_id": "sub-1", "reason": "r"}
STANDING = {"owner": HOTKEY, "total": 0.8}


@pytest.fixture
def receiver(monkeypatch):
    """The receiver's `_crown_bar` over a stand-in store, with the averaging rule on (margin_N registered) or off."""
    from carbon.challenge_validator import direct_receiver

    def bar(store, *, on=True, margin=MARGIN_N):
        rule = SimpleNamespace(margin_for=lambda challenge_id: margin)
        monkeypatch.setattr(
            crown_average, "ACTIVE", SimpleNamespace(rule=rule) if on else None
        )
        monkeypatch.setattr(direct_receiver, "_open_pool_store", lambda path: store)
        return direct_receiver._crown_bar("pool.sqlite3", KEY.challenge_id)

    return bar


def _view(store, crown_bar=None):
    return kp.PoolKingView(
        open_store=lambda: store,
        epoch_of=lambda submission_id: 7,
        exam_version_label="exam-1",
        rebuild_noise_of=lambda: NOISE,
        crown_bar_of=None if crown_bar is None else (lambda challenge_id: crown_bar),
    )


def test_the_receiver_reads_the_kings_mean_and_margin_n_only_with_averaging_on(
    receiver,
):
    store = _Store(KING_ROW, STANDING, mean=0.74)
    assert receiver(store, on=False) is None
    assert receiver(store) == {"base": 0.74, "margin": MARGIN_N}
    assert receiver(_Store(KING_ROW, STANDING, unstable=True)) == {
        "base": 0.8,
        "margin": MARGIN_N,
    }
    assert (
        receiver(_Store(KING_ROW, STANDING)) is None
    )  # KING_UNMEASURED: crowns wait, no averaged bar stated
    assert receiver(_Store(None, None, baseline=0.4)) == {
        "base": 0.4,
        "margin": MARGIN_N,
    }
    assert receiver(_Store(None, None)) is None
    assert (
        receiver(store, margin=None) is None
    )  # no margin_N registered at the configured N
    assert receiver(None) is None  # no pool store yet
    # a mean (or flag) filed on the king's PREVIOUS key is no measure of this exam (NO CARRY): no averaged bar
    assert receiver(_Store(KING_ROW, STANDING, mean=0.74, measured_on=OLD_KEY)) is None
    assert (
        receiver(_Store(KING_ROW, STANDING, unstable=True, measured_on=OLD_KEY)) is None
    )


def test_the_v2_route_states_the_averaged_bar_and_v1_keeps_the_single_grade_one():
    store = _Store(KING_ROW, STANDING)
    off = kp.serve_v2(_view(store), KEY)[1]
    status, on = kp.serve_v2(_view(store, {"base": 0.74, "margin": MARGIN_N}), KEY)
    assert status == 200 and on["to_beat_rule"] == kp.TO_BEAT_RULE_AVERAGED
    assert off["to_beat_rule"] == kp.TO_BEAT_RULE
    assert (
        on["to_beat"] == pytest.approx(_expected(0.74))
        and on["to_beat"] < off["to_beat"]
    )
    assert on["king"] == off["king"] and on["margin"] == off["margin"]
    v1 = kp.serve(_view(store, {"base": 0.74, "margin": MARGIN_N}), KEY)[1]
    assert v1 == kp.serve(_view(store), KEY)[1] and v1["to_beat"] == pytest.approx(
        0.78 + 0.03
    )


def test_the_receivers_king_view_is_wired_to_its_crown_bar():
    from carbon.challenge_validator import direct_receiver

    source = Path(direct_receiver.__file__).read_text(encoding="utf-8")
    assert (
        "crown_bar_of=lambda challenge_id: _crown_bar(pool_store, challenge_id)"
        in source
    )


def _averaged_board():
    king = kp.document_v2(
        challenge_id=CHALLENGE.challenge_id,
        challenge_version=CHALLENGE.version,
        exam_version_label="motor-exam-1",
        king={"hotkey": KING, "total": 0.64, "since_epoch": 7},
        rebuild_noise=koth_registry.rebuild_noise(CHALLENGE.challenge_id),
        baseline_total=None,
        crown_bar={"base": 0.61, "margin": MARGIN_N},
    )
    assert king["to_beat_rule"] == kp.TO_BEAT_RULE_AVERAGED
    signer = _signer()
    board = lb.build(
        king_document=king,
        rows=_rows(),
        network="testnet",
        key=signer,
        version=4,
        now=NOW,
        crown_changes=[],
        exact_totals={KING: 0.64},
        rebuild_noise=koth_registry.rebuild_noise(CHALLENGE.challenge_id),
    )
    return board, signer, king


def test_the_board_builder_and_the_dashboard_reader_carry_the_averaged_rule():
    from carbon.dashboard import board_v2
    from carbon.dashboard import feed as dashboard_feed

    board, signer, king = _averaged_board()
    assert board["king"]["to_beat_rule"] == kp.TO_BEAT_RULE_AVERAGED
    lb.verify(board, signer.public_key)
    trust = dashboard_feed.Trust(keys=frozenset({signer.public_key}))
    projected = dashboard_feed.project(board, trust)
    assert projected["launch"]["to_beat_rule"] == kp.TO_BEAT_RULE_AVERAGED
    assert projected["launch"]["to_beat"] == pytest.approx(king["to_beat"])
    page = board_v2._launch(projected)["launch"]
    assert page["to_beat_rule"] == kp.TO_BEAT_RULE_AVERAGED


def test_the_page_data_of_a_single_grade_board_is_unchanged():
    from carbon.dashboard import board_v2

    single = {
        "launch": {
            "counts": {},
            "margin": 0.01,
            "to_beat": 0.5,
            "baseline_total": None,
            "king_since_epoch": 3,
            "exam_version_label": "x",
            "network": "testnet",
            "gate_names": {},
            "to_beat_rule": kp.TO_BEAT_RULE,
        }
    }
    assert "to_beat_rule" not in board_v2._launch(single)["launch"]


def test_an_unknown_rule_is_still_refused_by_the_builder():
    board_king = kp.document_v2(**_args())
    board_king["to_beat_rule"] = "anything_else"
    with pytest.raises(lb.BoardRefused, match="board_king"):
        lb._king(board_king, v2=True)


def _card(**changes):
    document = {
        "schema": card.SCHEMA_V2,
        "challenge_id": KEY.challenge_id,
        "challenge_version": "1.3",
        "exam_version_label": "motor-exam",
        "king": {"hotkey": HOTKEY, "total": 0.69, "since_epoch": 12},
        "margin": 0.03,
        "to_beat": 0.68,
        "baseline_total": None,
        "to_beat_rule": card.TO_BEAT_RULE_AVERAGED,
    }
    document.update(changes)
    return document


def test_the_launchpad_card_reads_the_averaged_bar_and_says_it_is_an_average():
    doc = kp.document_v2(**_args(), crown_bar={"base": 0.6512, "margin": MARGIN_N})
    shown = card.parse(doc, KEY.challenge_id)
    assert shown["averaged"] is True and shown["to_beat"] == doc["to_beat"]
    lines = card.words(shown)
    assert lines[1].startswith(
        f"Score above {doc['to_beat']:.4f} to be sure to start a crown check"
    )
    assert "average" in lines[1] and "margin 0.0300" not in lines[1]
    no_king = card.words(
        card.parse(_card(king=None, baseline_total=0.39), KEY.challenge_id)
    )
    assert (
        no_king[0].startswith("No king yet: score above 0.6800")
        and "average" in no_king[0]
    )
    # the single-grade v2 rule is still checked by its arithmetic
    with pytest.raises(card.KingUnreadable):
        card.parse(_card(to_beat_rule=card.TO_BEAT_RULE), KEY.challenge_id)
    with pytest.raises(card.KingUnreadable):
        card.parse(_card(to_beat_rule="anything_else"), KEY.challenge_id)


def test_the_worker_and_the_page_name_the_averaged_rule():
    root = Path(__file__).resolve().parents[2] / "carbon" / "dashboard"
    worker = (root / "worker" / "feed.mjs").read_text(encoding="utf-8")
    page = (root / "web" / "dashboard.js").read_text(encoding="utf-8")
    assert f'LAUNCH_TO_BEAT_RULE_AVERAGED = "{kp.TO_BEAT_RULE_AVERAGED}"' in worker
    # the page reads the rule only where the projection passed it, which is the averaged bar alone
    assert (
        "const a = l.to_beat_rule;" in page
        and "Crowns compare rebuild averages" in page
    )


# ---------------------------------------------------------------- a king rebuilt through a krb_ link (Lead 5 Nov 19:3x)


def _real_store(tmp_path, *, linked):
    """A real pool store: the king graded on OLD_KEY (crowned there), then rebuilt on the current exam as krb_k whose
    evaluation is on CURRENT; ``linked`` files the king_rebuild.v1 link king -> krb_k.
    """
    from carbon.battery.pool_store import PoolStore

    store = PoolStore(tmp_path / "pool.sqlite3")

    def evaluation(op, sid, key, total):
        body = {
            "submission_id": sid,
            "evaluation_key": key,
            "owner": {"hotkey": HOTKEY, "request_digest": "r"},
            "evidence": {
                "model_p": {
                    "score_status": "SCORED_DEVELOPMENT_CANDIDATE",
                    "total_score": total,
                }
            },
        }
        with store.transaction() as db:
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?)",
                (
                    op,
                    "private_evaluation.v1",
                    "BOUND_DEVELOPMENT_ONLY",
                    json.dumps(body),
                ),
            )

    evaluation("e-old", "king", OLD_KEY, 0.80)
    store.set_incumbent("king", "crowned")
    evaluation("e-new", "krb_k", CURRENT, 0.78)
    if linked:
        with store.transaction() as db:
            db.execute(
                "INSERT INTO operations VALUES(?,?,?,?)",
                (
                    "l1",
                    "king_rebuild.v1",
                    "RECORDED",
                    json.dumps(
                        {"king_submission_id": "king", "derived_submission_id": "krb_k"}
                    ),
                ),
            )
    return store


def test_a_linked_kings_key_is_his_rebuilt_rows_and_his_new_mean_shows(
    receiver, tmp_path
):
    """Every door's king was rebuilt through a krb_ link: his re-measure files the mean on the derived row's key
    (`king_upkeep._king_key_on`), so the king page must read the mean there."""
    store = _real_store(tmp_path, linked=True)
    assert store.incumbent_evaluation_key("king") == CURRENT
    store.record_crown_average("king", CURRENT, {"mean": 0.76})
    assert receiver(store) == {"base": 0.76, "margin": MARGIN_N}


def test_an_old_key_mean_no_longer_shows_once_the_king_is_linked(receiver, tmp_path):
    """A mean filed on the king's PRE-rebuild key is no measure of the exam he now stands on (NO CARRY): once linked,
    the page states the single-grade rule until his new mean files."""
    store = _real_store(tmp_path, linked=True)
    store.record_crown_average("king", OLD_KEY, {"mean": 0.79})
    assert receiver(store) is None
    # ... and states the averaged bar again as soon as the mean on his current key is filed
    store.record_crown_average("king", CURRENT, {"mean": 0.76})
    assert receiver(store) == {"base": 0.76, "margin": MARGIN_N}


def test_an_unlinked_king_keeps_his_own_key_and_an_unlinked_derived_row_is_not_his(
    receiver, tmp_path
):
    store = _real_store(tmp_path, linked=False)
    assert (
        store.incumbent_evaluation_key("king") == OLD_KEY
    )  # krb_k without a link is not his
    store.record_crown_average("king", OLD_KEY, {"mean": 0.79})
    assert receiver(store) == {"base": 0.79, "margin": MARGIN_N}
