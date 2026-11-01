"""The conservative score to beat (koth v2) and the launch board's crown changes (week-1 item 48 and crown_changes).

Claims: the v2 king document adds ``to_beat_rule`` and publishes ``floor(total, step) + step + margin`` rounded UP to three
places, from public values only, so beating the shown bar always beats the true bar (exact total + margin) and the bar
depends on nothing finer than the step-floored total; v1 is served byte-identical at its own path; the miners' reader
reads both and prefers v2; a v1 client of the old formula still reads the new receiver's v1 answer. The v2 launch board adds
at most five ``crown_changes`` (four keys, step-floored totals, nothing but incumbent events) under its own signing domain,
and the v1 board is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
from types import SimpleNamespace
from typing import ClassVar

import pytest

from carbon.challenge_validator import koth_public as kp
from carbon.challenge_validator import launch_board as lb
from carbon.registry.model import ChallengeKey
from carbon.scoring import grade_feedback as gf
from scripts.dev.miner_launchpad import king

HOTKEY = "5" + "F" * 47
OTHER = "5" + "G" * 47
THIRD = "5" + "H" * 47
KEY = ChallengeKey("electric-motor-magnetics", "1.5")


def _args(**changes):
    args = {
        "challenge_id": KEY.challenge_id,
        "challenge_version": "1.5",
        "exam_version_label": "motor-dual-sealed-batch-30-v2",
        "king": {"hotkey": HOTKEY, "total": 0.7123, "since_epoch": 12},
        "rebuild_noise": {"value": 0.0079, "measurement_digest": "sha256:" + "a" * 64},
        "baseline_total": None,
        **changes,
    }
    return args


# --- v2: the conservative bar -----------------------------------------------------------------------------


def test_v2_is_v1_plus_the_rule_and_a_bar_above_the_true_bar():
    one, two = kp.document(**_args()), kp.document_v2(**_args())
    assert set(two) == kp.FIELDS_V2 and two["schema"] == kp.SCHEMA_V2
    assert two["to_beat_rule"] == "floor_plus_step_plus_margin"
    assert {
        k: v for k, v in two.items() if k not in ("schema", "to_beat", "to_beat_rule")
    } == {k: v for k, v in one.items() if k not in ("schema", "to_beat")}
    # Motor: step 0.02 would apply for 0.02 noise; here noise 0.0079 -> step max(eta, 0.0079)
    step = gf.step(0.0079)
    exact_bar = 0.7123 + 0.0079
    assert two["to_beat"] > exact_bar
    assert two["to_beat"] == pytest.approx(
        math.ceil((two["king"]["total"] + step + 0.0079) * 1000 - 1e-9) / 1000
    )
    assert (
        two["to_beat"] - exact_bar < step + 0.0079 + 0.001
    )  # overstates by at most a step (+ the 3-place round-up)


def test_the_bar_is_always_above_the_true_bar_and_depends_only_on_the_floored_total():
    rng = random.Random(48)
    for _ in range(300):
        margin = rng.choice([0.0079, 0.02, 0.0473, 0.004, 0.05])
        step = gf.step(margin)
        total = rng.uniform(0.0, 0.9)
        doc = kp.document_v2(
            **_args(
                king={"hotkey": HOTKEY, "total": total, "since_epoch": 1},
                rebuild_noise={
                    "value": margin,
                    "measurement_digest": "sha256:" + "a" * 64,
                },
            )
        )
        assert (
            doc["to_beat"] > total + margin
        )  # beating the shown bar always beats the true bar
        # another total in the same step cell publishes the very same bar
        floored = doc["king"]["total"]
        twin = floored + rng.uniform(0.0, step * 0.999)
        other = kp.document_v2(
            **_args(
                king={"hotkey": HOTKEY, "total": twin, "since_epoch": 1},
                rebuild_noise={
                    "value": margin,
                    "measurement_digest": "sha256:" + "a" * 64,
                },
            )
        )
        if other["king"]["total"] == floored:
            assert other["to_beat"] == doc["to_beat"]


def test_with_no_king_the_baseline_gets_the_same_rule():
    doc = kp.document_v2(**_args(king=None, baseline_total=0.4))
    step = gf.step(0.0079)
    floored = doc["baseline_total"]
    assert doc["king"] is None and floored <= 0.4 < floored + step
    assert doc["to_beat"] > 0.4 + 0.0079
    assert doc["to_beat"] == pytest.approx(
        math.ceil((floored + step + 0.0079) * 1000 - 1e-9) / 1000
    )


def test_when_the_step_equals_the_margin_f02():
    noise = {"value": 0.0473, "measurement_digest": "sha256:" + "a" * 64}
    assert gf.step(0.0473) == 0.0473
    doc = kp.document_v2(
        **_args(
            rebuild_noise=noise, king={"hotkey": HOTKEY, "total": 0.6, "since_epoch": 3}
        )
    )
    floored = doc["king"]["total"]
    assert doc["to_beat"] == pytest.approx(
        math.ceil((floored + 2 * 0.0473) * 1000 - 1e-9) / 1000
    )
    assert doc["to_beat"] > 0.6 + 0.0473


def test_no_margin_no_bar_and_a_cap_at_one():
    none = kp.document_v2(**_args(rebuild_noise=None))
    assert (
        none["margin"] is None
        and none["to_beat"] is None
        and none["to_beat_rule"] == kp.TO_BEAT_RULE
    )
    top = kp.document_v2(
        **_args(king={"hotkey": HOTKEY, "total": 0.999, "since_epoch": 1})
    )
    assert top["to_beat"] == 1.0


def test_v1_is_unchanged_for_fixed_inputs():
    doc = kp.document(**_args())
    assert doc["to_beat"] == pytest.approx(doc["king"]["total"] + 0.0079)
    assert doc["schema"] == "carbon.koth.public.v1" and set(doc) == kp.FIELDS
    # the exact bytes for these inputs, pinned (as produced before v2 existed)
    body = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(body.encode()).hexdigest() == V1_PINNED


def _intake(view):
    from carbon.challenge_validator.direct_intake import DirectRecipeIntake

    intake = SimpleNamespace(challenge=KEY, koth_view=view)
    intake._koth = lambda path: DirectRecipeIntake._koth(intake, path)
    return intake


class _View:
    exam_version_label = "label-1"
    baseline_total = None
    rebuild_noise: ClassVar[dict] = {
        "value": 0.0079,
        "measurement_digest": "sha256:" + "a" * 64,
    }

    def king(self):
        return {"hotkey": HOTKEY, "total": 0.7123, "since_epoch": 12}


def test_the_receiver_serves_v1_at_the_old_path_and_v2_at_its_own():
    intake = _intake(_View())
    one = intake._koth(kp.PATH + KEY.challenge_id)
    two = intake._koth(kp.PATH + KEY.challenge_id + kp.V2_SUFFIX)
    assert one.status == two.status == 200
    assert one.body["schema"] == kp.SCHEMA and set(one.body) == kp.FIELDS
    assert two.body["schema"] == kp.SCHEMA_V2 and set(two.body) == kp.FIELDS_V2
    assert one.body == kp.document(**_args(exam_version_label="label-1"))
    assert intake._koth(kp.PATH + "other" + kp.V2_SUFFIX).status == 404
    assert intake._koth(kp.PATH + KEY.challenge_id + "/v3").status == 404
    intake.koth_view = None
    assert intake._koth(kp.PATH + KEY.challenge_id + kp.V2_SUFFIX).status == 404


# --- the miners' reader -------------------------------------------------------------------------------------


def _old_client_parse(document, challenge_id):
    """The reader as it was before v2: v1 only, a closed field set, to_beat within eta of (held + margin)."""
    assert (
        set(document) == king.FIELDS and document["schema"] == "carbon.koth.public.v1"
    )
    assert document["challenge_id"] == challenge_id
    held = document["king"]["total"] if document["king"] else document["baseline_total"]
    assert abs(document["to_beat"] - (held + document["margin"])) <= gf.ETA + 1e-9
    return True


def test_the_reader_reads_both_documents_and_an_old_client_still_reads_v1():
    one, two = kp.document(**_args()), kp.document_v2(**_args())
    old = king.parse(one, KEY.challenge_id)
    new = king.parse(two, KEY.challenge_id)
    assert "conservative" not in old and new["conservative"] is True
    assert new["to_beat"] > old["to_beat"]
    assert _old_client_parse(
        json.loads(json.dumps(one)), KEY.challenge_id
    )  # the new receiver's v1 bytes
    with pytest.raises(AssertionError):
        _old_client_parse(two, KEY.challenge_id)  # why v1 stays at its own path
    for tamper in (
        lambda d: d.update(to_beat=d["to_beat"] - 0.01),
        lambda d: d.update(to_beat_rule="ceil"),
        lambda d: d.pop("to_beat_rule"),
        lambda d: d.update(extra=1),
    ):
        broken = json.loads(json.dumps(two))
        tamper(broken)
        with pytest.raises(king.KingUnreadable):
            king.parse(broken, KEY.challenge_id)


def test_the_reader_asks_v2_first_and_falls_back_to_v1_on_a_404():
    import io
    import urllib.error

    asked = []
    served = {"v2": True}

    def opener(url, timeout):
        asked.append(url)
        if url.endswith(kp.V2_SUFFIX):
            if not served["v2"]:
                raise urllib.error.HTTPError(url, 404, "nf", {}, None)
            body = json.dumps(kp.document_v2(**_args())).encode()
        else:
            body = json.dumps(kp.document(**_args())).encode()
        return _Response(io.BytesIO(body))

    answer, why = king.read("http://127.0.0.1:9999", KEY.challenge_id, opener=opener)
    assert why is None and answer["conservative"] is True and len(asked) == 1
    assert asked[0].endswith(KEY.challenge_id + kp.V2_SUFFIX)
    served["v2"] = False
    asked.clear()
    answer, why = king.read("http://127.0.0.1:9999", KEY.challenge_id, opener=opener)
    assert why is None and "conservative" not in answer and len(asked) == 2
    assert asked[1].endswith(KEY.challenge_id)
    lines = king.words(king.parse(kp.document_v2(**_args()), KEY.challenge_id))
    assert any(
        "to be sure to take the crown" in line and "one Ladder step lower" in line
        for line in lines
    )


class _Response:
    def __init__(self, stream):
        self._stream = stream

    def __enter__(self):
        return self._stream

    def __exit__(self, *exc):
        return False


# --- crown changes -----------------------------------------------------------------------------------------


class _Store:
    def __init__(self, events, standings):
        self._events, self._standings = events, standings

    def events(self, kind=None):
        return [e for e in self._events if kind is None or e["kind"] == kind]

    def incumbent_standing(self, model_id):
        return self._standings.get(model_id)


def _event(sequence, model_id, previous):
    return {
        "sequence": sequence,
        "kind": "incumbent",
        "body": {"model_id": model_id, "reason": "r", "previous": previous},
    }


def _view(store, noise=0.02):
    return kp.PoolKingView(
        open_store=lambda: store,
        epoch_of=lambda sid: {"a": 5, "b": 6, "c": 7}.get(
            sid, 100 + int(sid[1:]) if sid[1:].isdigit() else None
        ),
        exam_version_label="exam-1",
        rebuild_noise_of=lambda: {
            "value": noise,
            "measurement_digest": "sha256:" + "a" * 64,
        },
    )


def test_crown_changes_are_the_incumbent_events_floored_newest_first_and_capped():
    exact = 0.8141579644010861
    standings = {
        "a": {"owner": HOTKEY, "total": exact},
        "b": {"owner": OTHER, "total": 0.9},
        "c": {"owner": HOTKEY, "total": 0.95},
    }
    events = [_event(1, "a", None), _event(2, "b", "a"), _event(3, "c", "b")]
    changes = _view(_Store(events, standings)).crown_changes()
    assert [c["to_hotkey"] for c in changes] == [HOTKEY, OTHER, HOTKEY]
    assert changes[-1] == {
        "from_hotkey": None,
        "to_hotkey": HOTKEY,
        "since_epoch": 5,
        "total": 0.8,
    }
    assert all(set(c) == lb.CROWN_CHANGE_FIELDS for c in changes)
    assert (
        changes[0]["from_hotkey"] == OTHER and changes[1]["from_hotkey"] == HOTKEY
    )  # a self-improvement is an entry too
    assert "0.8141579644010861" not in json.dumps(changes)
    # a cap of 5 with 7 changes keeps the 5 newest
    many = {
        f"m{i}": {"owner": HOTKEY if i % 2 else OTHER, "total": 0.5 + i / 100}
        for i in range(1, 8)
    }
    events = [_event(i, f"m{i}", None if i == 1 else f"m{i - 1}") for i in range(1, 8)]
    kept = _view(_Store(events, many)).crown_changes()
    assert len(kept) == 5 and [c["since_epoch"] for c in kept] == [
        107,
        106,
        105,
        104,
        103,
    ]


def test_changes_that_the_king_page_could_not_show_are_left_out():
    host = "carbon-crown-average-host"
    standings = {
        "a": {"owner": HOTKEY, "total": 0.7},
        "h": {"owner": host, "total": 0.9},  # a host-owned derived row is never a king
        "c": {"owner": OTHER, "total": 0.95},
    }
    events = [
        _event(1, "a", None),
        _event(2, "h", "a"),
        _event(3, None, "h"),  # a vacated crown is no change of king
        _event(4, "c", None),
        _event(5, "zz", "c"),  # no scored total: not shown
    ]
    changes = _view(_Store(events, standings)).crown_changes()
    assert [c["to_hotkey"] for c in changes] == [OTHER, HOTKEY]
    assert changes[0]["from_hotkey"] is None
    blob = json.dumps(changes)
    assert host not in blob and "rtsk_" not in blob


# --- the v2 board --------------------------------------------------------------------------------------------

_NOW = None


def _board(changes, *, v2=True, key=None):
    import datetime

    signer = key or lb.LaunchBoardKey(os.urandom(32))
    doc = (kp.document_v2 if v2 else kp.document)(**_args())
    board = lb.build(
        king_document=doc,
        rows=[],
        network="testnet",
        key=signer,
        version=3,
        now=datetime.datetime.fromtimestamp(1_800_000_000, datetime.UTC),
        crown_changes=changes if v2 else None,
    )
    return board, signer


CHANGES = [
    {"from_hotkey": OTHER, "to_hotkey": HOTKEY, "since_epoch": 9, "total": 0.8},
    {"from_hotkey": None, "to_hotkey": OTHER, "since_epoch": 4, "total": 0.6},
]


def test_the_v2_board_carries_crown_changes_and_the_rule_under_its_own_domain():
    board, signer = _board(CHANGES)
    assert board["schema"] == lb.SCHEMA_V2 and set(board) == lb.FIELDS_V2
    assert set(board["king"]) == set(lb.KING_SECTION_V2)
    assert board["king"]["to_beat_rule"] == kp.TO_BEAT_RULE
    assert board["crown_changes"] == CHANGES
    assert lb.verify(board, signer.public_key) == board
    # the v2 signature verifies under the v2 domain only: the v1 domain rejects it
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    body = {k: v for k, v in board.items() if k != "signature"}
    public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(signer.public_key))
    signature = bytes.fromhex(board["signature"])
    public.verify(signature, lb.BOARD_DOMAIN_V2 + lb._canonical(body).encode())
    with pytest.raises(InvalidSignature):
        public.verify(signature, lb.BOARD_DOMAIN + lb._canonical(body).encode())
    assert lb.BOARD_DOMAIN_V2 != lb.BOARD_DOMAIN


def test_the_v1_board_is_built_and_signed_exactly_as_before():
    board, signer = _board(None, v2=False)
    assert board["schema"] == lb.SCHEMA and set(board) == lb.FIELDS
    assert "crown_changes" not in board and "to_beat_rule" not in board["king"]
    assert lb.verify(board, signer.public_key) == board
    # a v1 document signed by the v1 domain; the same fixed key and time give the same bytes every time
    fixed = lb.LaunchBoardKey(bytes(range(32)))
    first, _ = _board(None, v2=False, key=fixed)
    second, _ = _board(None, v2=False, key=fixed)
    assert first == second
    body = {k: v for k, v in first.items() if k != "signature"}
    assert hashlib.sha256(lb._canonical(body).encode()).hexdigest() == V1_BOARD_PINNED
    # v1 never accepts a v2 koth document, nor v2 a v1 one
    with pytest.raises(lb.BoardRefused):
        lb.build(
            king_document=kp.document_v2(**_args()),
            rows=[],
            network="testnet",
            key=fixed,
            version=1,
        )
    with pytest.raises(lb.BoardRefused):
        lb.build(
            king_document=kp.document(**_args()),
            rows=[],
            network="testnet",
            key=fixed,
            version=1,
            crown_changes=[],
        )


def test_the_board_refuses_any_other_crown_change_shape():
    for bad in (
        [{**CHANGES[0], "extra": 1}],
        [{k: v for k, v in CHANGES[0].items() if k != "total"}],
        [{**CHANGES[0], "to_hotkey": "rtsk_" + "a" * 64}],
        [{**CHANGES[0], "since_epoch": -1}],
        [{**CHANGES[0], "total": 1.5}],
        [CHANGES[0]] * 6,
        "nope",
    ):
        with pytest.raises(lb.BoardRefused):
            _board(bad)
    board, _signer = _board(CHANGES)
    tampered = json.loads(json.dumps(board))
    tampered["crown_changes"][0]["total"] = 0.8000000001  # unrounded: refused whole
    with pytest.raises(lb.BoardRefused):
        lb.check(tampered)


def test_the_signed_body_leaks_nothing_beyond_the_page():
    exact = 0.8141579644010861
    standings = {
        "a": {"owner": HOTKEY, "total": exact},
        "h": {"owner": "carbon-crown-average-host", "total": 0.99},
    }
    events = [_event(1, "a", None), _event(2, "h", "a")]
    changes = _view(_Store(events, standings)).crown_changes()
    board, signer = _board(changes)
    raw = lb._canonical({k: v for k, v in board.items() if k != "signature"})
    assert "0.8141579644010861" not in raw and "carbon-crown-average-host" not in raw
    assert "rtsk_" not in raw
    allowed = {signer.public_key}
    assert set(re.findall(r"[0-9a-f]{64}", raw)) <= allowed
    assert all(set(c) == lb.CROWN_CHANGE_FIELDS for c in board["crown_changes"])
    assert board["crown_changes"] == [
        {"from_hotkey": None, "to_hotkey": HOTKEY, "since_epoch": 5, "total": 0.8}
    ]


V1_PINNED = "50c9448936dfbc594773ae7e374dff69147eed44c52a28c9e3bce3e4347437d6"
V1_BOARD_PINNED = "f2f33e8fccb4ac6ed43a9d4a4acf5d9508f050e4d6ed494f17cfe284c1bd98db"
