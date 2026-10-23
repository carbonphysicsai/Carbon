"""The public king document (GET /carbon/v1/koth/<challenge>): the closed v1 contract
Launchpad's reader enforces, Ladder-stepped totals, and 404 until a grader publishes."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import koth_public as kp
from carbon.registry.model import ChallengeKey

HOTKEY = "5" + "F" * 47
KEY = ChallengeKey("electric-motor-magnetics", "1.3")
NOISE = {"value": 0.03, "measurement_digest": "sha256:" + "a" * 64}


def _doc(**changes):
    args = {
        "challenge_id": KEY.challenge_id,
        "challenge_version": "1.3",
        "exam_version_label": "motor-dual-sealed-batch-30-v2",
        "king": {"hotkey": HOTKEY, "total": 0.7123, "since_epoch": 12},
        "rebuild_noise": NOISE,
        "baseline_total": None,
        **changes,
    }
    return kp.document(**args)


def test_a_king_is_shown_at_the_ladder_step_with_the_score_to_beat():
    doc = _doc()
    assert set(doc) == kp.FIELDS and set(doc["king"]) == kp.KING_FIELDS
    assert doc["schema"] == kp.SCHEMA
    # stepped down to the Ladder grid (noise 0.03 > eta), never finer
    assert doc["king"]["total"] == pytest.approx(0.69)
    assert doc["margin"] == 0.03
    assert doc["to_beat"] == pytest.approx(0.69 + 0.03)
    assert doc["baseline_total"] is None


def test_without_a_king_the_baseline_is_the_starting_bar():
    doc = _doc(king=None, baseline_total=0.4)
    assert doc["king"] is None and doc["baseline_total"] == 0.4
    assert doc["to_beat"] == pytest.approx(0.43)


def test_no_registered_noise_means_no_margin_and_no_to_beat():
    doc = _doc(rebuild_noise=None)
    assert doc["margin"] is None and doc["to_beat"] is None
    # the step falls back to eta
    assert doc["king"]["total"] == pytest.approx(0.7)
    none = _doc(king=None, baseline_total=None)
    assert none["king"] is None and none["baseline_total"] is None
    assert none["to_beat"] is None and none["margin"] is None


def test_margin_with_nothing_to_measure_from_is_dropped_not_invented():
    doc = _doc(king=None, baseline_total=None)
    assert doc["margin"] is None and doc["to_beat"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"challenge_version": "BAD VERSION"},
        {"exam_version_label": ""},
        {"king": {"hotkey": "not-ss58", "total": 0.5, "since_epoch": 1}},
        {"king": {"hotkey": HOTKEY, "total": 1.5, "since_epoch": 1}},
        {"king": {"hotkey": HOTKEY, "total": float("nan"), "since_epoch": 1}},
        {"king": {"hotkey": HOTKEY, "total": 0.5, "since_epoch": -1}},
        {"king": {"hotkey": HOTKEY, "total": True, "since_epoch": 1}},
    ],
)
def test_malformed_inputs_refuse(changes):
    with pytest.raises(kp.KothPublicRefused):
        _doc(**changes)


def test_the_document_fits_the_reader_bound_and_carries_nothing_else():
    text = json.dumps(_doc())
    assert len(text.encode()) < kp.MAX_BYTES
    for word in ("case", "leg", "score_pack", "submission", "recipe", "probe"):
        assert word not in text


class _View:
    exam_version_label = "label-1"
    baseline_total = None
    rebuild_noise = NOISE

    def __init__(self, king, fail=False):
        self._king, self._fail = king, fail

    def king(self):
        if self._fail:
            raise OSError("down")
        return self._king


def test_serve_is_404_until_published_503_on_failure_200_otherwise():
    assert kp.serve(None, KEY)[0] == 404
    status, body = kp.serve(_View(None, fail=True), KEY)
    assert status == 503 and body == {"refused": "koth_unavailable"}
    status, body = kp.serve(
        _View({"hotkey": HOTKEY, "total": 0.5, "since_epoch": 0}), KEY
    )
    assert status == 200 and body["challenge_id"] == KEY.challenge_id
    status, body = kp.serve(_View({"hotkey": "x", "total": 0.5, "since_epoch": 0}), KEY)
    assert status == 503 and body == {"refused": "koth_king"}


def test_the_intake_serves_only_its_own_challenge_and_the_route_is_read_only():
    from carbon.challenge_validator.direct_intake import DirectRecipeIntake

    intake = SimpleNamespace(
        challenge=KEY,
        koth_view=_View({"hotkey": HOTKEY, "total": 0.5, "since_epoch": 3}),
    )
    intake._koth = lambda path: DirectRecipeIntake._koth(intake, path)
    answer = intake._koth(kp.PATH + KEY.challenge_id)
    assert answer.status == 200 and answer.body["king"]["since_epoch"] == 3
    assert intake._koth(kp.PATH + "other-challenge").status == 404
    intake.koth_view = None
    assert intake._koth(kp.PATH + KEY.challenge_id).status == 404
