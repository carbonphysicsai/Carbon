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
    # stepped to the Ladder grid (noise 0.03), like every total on this page
    assert doc["king"] is None and doc["baseline_total"] == pytest.approx(0.39)
    assert doc["to_beat"] == pytest.approx(0.42)


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


class _Store:
    def __init__(self, incumbent, standing):
        self._incumbent, self._standing = incumbent, standing

    def incumbent(self):
        return self._incumbent

    def incumbent_standing(self, model_id):
        assert model_id == self._incumbent["model_id"]
        return self._standing


def _pool_view(store, epoch=7, noise=NOISE):
    return kp.PoolKingView(
        open_store=lambda: store,
        epoch_of=lambda submission_id: epoch,
        exam_version_label="exam-1",
        rebuild_noise_of=lambda: noise,
    )


def test_the_pool_view_names_the_incumbent_its_owner_total_and_epoch():
    store = _Store(
        {"model_id": "sub-1", "reason": "r"}, {"owner": HOTKEY, "total": 0.8}
    )
    status, body = kp.serve(_pool_view(store), KEY)
    assert status == 200
    assert body["king"] == {
        "hotkey": HOTKEY,
        "total": pytest.approx(0.78),
        "since_epoch": 7,
    }
    assert body["to_beat"] == pytest.approx(0.81)


def test_the_pool_view_has_no_king_without_an_incumbent_a_scored_total_or_an_epoch():
    assert kp.serve(_pool_view(_Store(None, None)), KEY)[1]["king"] is None
    held = {"model_id": "sub-1", "reason": "r"}
    assert kp.serve(_pool_view(_Store(held, None)), KEY)[1]["king"] is None
    standing = {"owner": HOTKEY, "total": 0.8}
    assert (
        kp.serve(_pool_view(_Store(held, standing), epoch=None), KEY)[1]["king"] is None
    )


def test_an_unregistered_margin_gives_a_null_to_beat_with_a_king():
    store = _Store(
        {"model_id": "sub-1", "reason": "r"}, {"owner": HOTKEY, "total": 0.8}
    )
    body = kp.serve(_pool_view(store, noise=None), KEY)[1]
    assert body["margin"] is None and body["to_beat"] is None
    assert body["king"]["total"] == pytest.approx(0.8)


def test_an_unopened_pool_store_is_unavailable_not_a_crash():
    view = _pool_view(None)
    assert kp.serve(view, KEY) == (503, {"refused": "koth_unavailable"})


def test_the_real_pool_store_reports_the_incumbents_latest_scored_evaluation(tmp_path):
    from carbon.battery.pool_store import PoolStore
    from carbon.challenge_validator.interface import digest

    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: 0.0)
    store.admit(
        "a",
        request_digest=digest(["request", "a"]),
        hotkey="fixture-a",
        challenge="electric-motor-magnetics",
        strategy={},
        binding={"challenge": {"id": "electric-motor-magnetics"}},
    )
    assert store.incumbent_standing("a") is None

    def file(op, status, total, submission="a"):
        body = {
            "submission_id": submission,
            "owner": HOTKEY,
            "evidence": {"model_p": {"score_status": status, "total_score": total}},
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

    file("1", "SCORED_DEVELOPMENT_CANDIDATE", 0.4)
    file("2", "SCORED_DEVELOPMENT_CANDIDATE", 0.6, submission="other")
    assert store.incumbent_standing("a") == {"owner": HOTKEY, "total": 0.4}
    file("3", "SCORED_DEVELOPMENT_CANDIDATE", 0.7)
    assert store.incumbent_standing("a")["total"] == 0.7
    file("4", "FAILED_INFRA", None)  # the latest says nothing: no total shown
    assert store.incumbent_standing("a") is None


def test_the_baseline_is_the_registered_comparators_and_only_without_a_king(tmp_path):
    """The king route's baseline is the aggregate registered when the KOTH comparator was
    built for the exam set (`PoolStore.record_baseline`, by `BankPromotion.consider_private`),
    shown only while there is no king; the intake never reads the private score pack."""
    from carbon.battery.pool_store import PoolStore, StateError

    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: 0.0)
    assert store.latest_baseline("c") is None
    store.record_baseline("c", "sha256:" + "1" * 64, 0.5)
    store.record_baseline("c", "sha256:" + "1" * 64, 0.5)  # idempotent
    with pytest.raises(StateError):
        store.record_baseline(
            "c", "sha256:" + "1" * 64, 0.6
        )  # a pack's baseline is fixed
    store.record_baseline("other", "sha256:" + "2" * 64, 0.2)
    assert store.latest_baseline("c") == 0.5
    store.record_baseline("c", "sha256:" + "3" * 64, 0.45)  # the current exam set
    assert store.latest_baseline("c") == 0.45

    class View:
        exam_version_label = "exam-1"
        rebuild_noise = NOISE
        baseline_total = store.latest_baseline("c")

        def __init__(self, king):
            self._king = king

        def king(self):
            return self._king

    none = kp.serve(View(None), KEY)[1]
    assert none["king"] is None and none["baseline_total"] == pytest.approx(0.45)
    assert none["to_beat"] == pytest.approx(0.48)
    held = kp.serve(View({"hotkey": HOTKEY, "total": 0.8, "since_epoch": 1}), KEY)[1]
    assert held["baseline_total"] is None and held["king"] is not None


def test_consider_private_registers_the_comparators_baseline(tmp_path):
    from carbon.battery.pool_store import PoolStore
    from carbon.challenge_validator import bank_promotion as bp
    from carbon.challenge_validator.interface import digest

    store = PoolStore(tmp_path / "pool.sqlite", clock=lambda: 0.0)
    flow = bp.BankPromotion(store, registered_source_receipt_sha256=digest("pin"))
    comparator = {
        "schema": bp.COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": "electric-motor-magnetics",
        "score_pack_digest": digest("pack"),
        "rebuild_noise": None,
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": [],
        "baseline_total": 0.37,
    }
    try:
        flow.consider_private("missing", digest("key"), comparator)
    except Exception:  # noqa: BLE001 - the pair is not filed; registration comes first
        pass
    assert store.latest_baseline("electric-motor-magnetics") == 0.37


def test_the_intake_side_reads_no_score_pack():
    """The king view and the route import and call nothing that reads the private
    score pack: the baseline comes from the registered aggregate."""
    import ast
    from pathlib import Path

    for module in ("koth_public.py",):
        path = Path(kp.__file__).with_name(module)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            getattr(n, "module", None) or ""
            for n in ast.walk(tree)
            if isinstance(n, ast.Import | ast.ImportFrom)
        } | {
            alias.name
            for n in ast.walk(tree)
            if isinstance(n, ast.Import | ast.ImportFrom)
            for alias in n.names
        }
        assert not [m for m in names if "koth_registry" in m or "score_pack" in m]
        calls = {
            getattr(n.func, "attr", getattr(n.func, "id", ""))
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
        }
        assert "baseline_total" not in calls
    from carbon.challenge_validator import direct_receiver

    source = __import__("inspect").getsource(direct_receiver._king_view)
    assert "baseline_total(" not in source and "read_json_role" not in source
    assert "latest_baseline" in source
