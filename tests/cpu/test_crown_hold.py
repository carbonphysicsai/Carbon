"""The coded crown HOLD of a menu-D version (Validator-2B 7 Nov): a challenger who beats the king on a version that
registers a pool ``menu`` block gets UNAVAILABLE / crown_held_for_review, the crown is unchanged and no repeat is spent;
only the operator's private release file lets that one contender be decided. Every other version is untouched.
SYNTHETIC grades (the crown-repeat fixtures)."""

import json
import os

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_hold, crown_pause_sweep
from tests.cpu import test_crown_grade_repeat as base
from tests.cpu.test_operator_pause import CHANGES, Store, consider, never

posix = pytest.mark.skipif(
    not hasattr(os, "geteuid"), reason="owner-only file modes are POSIX"
)


@pytest.fixture
def hold_on(monkeypatch):
    monkeypatch.setattr(crown_hold, "ACTIVE", True)


def release(directory, ids, mode=0o600):
    path = directory / crown_hold.RELEASE_NAME
    path.write_text(json.dumps({"released": ids}), encoding="utf-8")
    path.chmod(mode)
    return path


@pytest.mark.parametrize("name", sorted(CHANGES))
def test_a_challenger_who_beats_the_king_on_a_menu_version_is_held(
    name, tmp_path, hold_on
):
    outcome, store = consider(CHANGES[name], tmp_path, repeat=never)
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert outcome["reason"] == crown_hold.CROWN_HELD == bp.CROWN_HELD
    assert outcome["candidate"] == "c"
    assert (
        store.moves == [] and store.marks == {}
    )  # the crown is unchanged, no repeat spent


def test_an_outcome_that_changes_no_crown_is_not_held(tmp_path, hold_on):
    fixed = base.pair(base.body("c", total=0.55), base.body("k", total=0.5))
    outcome, store = consider(fixed, tmp_path, repeat=never)
    assert outcome["outcome"] == bp.INCUMBENT_KEEPS and store.moves == []


def test_without_a_menu_version_nothing_is_held(tmp_path, monkeypatch):
    monkeypatch.setattr(crown_hold, "ACTIVE", False)
    outcome, store = consider(CHANGES["takeover"], tmp_path)
    assert outcome["outcome"] == bp.CHALLENGER and store.moves != []


@posix
def test_only_the_operators_private_release_lets_that_contender_be_decided(
    tmp_path, hold_on
):
    release(tmp_path, ["someone-else"])
    held, store = consider(CHANGES["takeover"], tmp_path, repeat=never)
    assert held["reason"] == crown_hold.CROWN_HELD and store.moves == []
    release(tmp_path, ["c"])
    decided, store = consider(CHANGES["takeover"], tmp_path)
    assert decided["outcome"] == bp.CHALLENGER and store.moves != []


@posix
@pytest.mark.parametrize(
    "body", ["not json", "[]", '{"released": "c"}', '{"released": ["c"], "x": 1}']
)
def test_a_malformed_or_open_release_file_releases_nothing(tmp_path, hold_on, body):
    path = tmp_path / crown_hold.RELEASE_NAME
    path.write_text(body, encoding="utf-8")
    path.chmod(0o600)
    assert crown_hold.held(tmp_path, "c")
    release(
        tmp_path, ["c"], mode=0o644
    )  # others can write it: not the operator's record
    assert crown_hold.held(tmp_path, "c")


def test_install_holds_exactly_the_versions_whose_registration_carries_a_menu(
    tmp_path, monkeypatch
):
    constants = tmp_path / "pool_constants.json"
    constants.write_text(
        json.dumps(
            {
                "schema": "x",
                "versions": {
                    "electric-motor-magnetics 1.8": {"menu": "HUMAN_INPUT"},
                    "electric-motor-magnetics 1.5": {"optimizer": {}},
                },
            }
        ),
        encoding="utf-8",
    )
    from carbon.scoring import pool_version

    monkeypatch.setattr(pool_version, "CONSTANTS", constants)
    try:
        for version, expected in (("1.8", True), ("1.5", False), ("9.9", False)):
            crown_hold.install(
                {"challenge": {"id": "electric-motor-magnetics", "version": version}}
            )
            assert crown_hold.ACTIVE is expected
        crown_hold.install({})
        assert crown_hold.ACTIVE is False
    finally:
        crown_hold.install({})


def test_every_version_registered_today_is_not_held():
    from pathlib import Path

    from carbon.scoring import pool_version

    document = json.loads(Path(pool_version.CONSTANTS).read_bytes())
    for key in document["versions"]:
        challenge_id, version = key.rsplit(" ", 1)
        assert crown_hold.menu_registered(challenge_id, version) is False


def test_the_sweep_stops_at_a_held_contender_with_no_attempt(tmp_path, hold_on):
    class Filed:
        path = tmp_path / "pool.sqlite3"

        def __init__(self):
            self.attempts = []

        def paused_crowns(self, kind):
            return [{"submission_id": "c", "evaluation_key": base.KEY, "exam": "e"}]

        def incumbent(self):
            return {"model_id": "k"}

        def crown_pause_attempts(self, *a):
            return 0, None

        def resolve_crown_pause(self, *a):
            raise AssertionError("a held contender is never resolved")

    def reconsider(record):
        raise AssertionError("a held contender is never reconsidered")

    assert (
        crown_pause_sweep.sweep(Filed(), reconsider, kind="pack", current_exam="e")
        == []
    )


def test_the_store_double_is_the_operator_pause_one():
    assert issubclass(Store, base.Store)
