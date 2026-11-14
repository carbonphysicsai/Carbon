"""The crown hold of a menu-D version can be registered OFF for one exact version (the owner's ruling, 13 Nov).

Shipped with NO entry: Motor 1.8 stays held by default. Off only via an entry of
`scripts/validator_host_classes/crown_hold.json`; every other version is unchanged; a bad registry holds (fail closed);
the operator pause flag still stops every crown change. SYNTHETIC grades and registry files; no value is registered.
"""

from __future__ import annotations

import json
import os

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_hold, queue_view
from carbon.challenge_validator.interface import digest
from tests.cpu.test_crown_hold import release
from tests.cpu.test_operator_pause import CHANGES, consider, flag, never

posix = pytest.mark.skipif(
    not hasattr(os, "geteuid"), reason="owner-only file modes are POSIX"
)
MOTOR, COOLING = "electric-motor-magnetics", "chip-cold-plate"
AUTHORITY = digest("the typed owner line")


@pytest.fixture(autouse=True)
def _restore_hold():
    yield
    crown_hold.ACTIVE = False
    crown_hold.SERVED = None


def _registry(tmp_path, holds, **extra):
    path = tmp_path / "crown_hold.json"
    path.write_text(
        json.dumps({"schema": crown_hold.REGISTRY_SCHEMA, "holds": holds, **extra})
    )
    return path


def _off(challenge=MOTOR, version="1.8", **changes):
    return {
        "challenge": challenge,
        "version": version,
        "hold": "off",
        "authority": AUTHORITY,
        **changes,
    }


@pytest.fixture
def served_18(monkeypatch, tmp_path):
    """The receiver serves Motor 1.8 (a menu version in the real registration) with the registry file at tmp_path."""
    monkeypatch.setattr(crown_hold, "REGISTRY", tmp_path / "crown_hold.json")
    _registry(tmp_path, [])
    crown_hold.install(MOTOR, "1.8", log=lambda line: None)
    assert crown_hold.ACTIVE is True


# --- shipped held ------------------------------------------------------------------------------------------------------


def test_the_committed_registry_lists_nothing_so_motor_18_is_held_by_default():
    document = json.loads(crown_hold.REGISTRY.read_bytes())
    assert document["schema"] == crown_hold.REGISTRY_SCHEMA and document["holds"] == []
    assert crown_hold.registered_off(MOTOR, "1.8") is False
    crown_hold.install(MOTOR, "1.8", log=lambda line: None)
    assert crown_hold.ACTIVE is True and crown_hold.holding() is True
    assert crown_hold.held("/nowhere", "any-contender") is True


def test_the_registry_is_outside_the_worker_image_build_inputs():
    from carbon.reconstruction.worker import build_inputs

    root = crown_hold.REGISTRY.parents[2]
    relative = crown_hold.REGISTRY.resolve().relative_to(root).as_posix()
    assert not any(
        relative == item or relative.startswith(item + "/")
        for item in build_inputs.paths()
    )


# --- off only via a registry entry -----------------------------------------------------------------------------------------


def test_an_entry_turns_the_hold_off_for_exactly_that_version_and_needs_no_restart(
    served_18, tmp_path
):
    assert crown_hold.holding() is True
    _registry(tmp_path, [_off()])  # registered after install: read at call time
    assert crown_hold.registered_off(MOTOR, "1.8") is True
    assert crown_hold.holding() is False
    assert crown_hold.held(tmp_path, "any-contender") is False
    # the version is still a menu version: the menu re-check (`ACTIVE`) keeps running
    assert crown_hold.ACTIVE is True and crown_hold.menu_registered(MOTOR, "1.8")


def test_removing_the_entry_holds_again(served_18, tmp_path):
    _registry(tmp_path, [_off()])
    assert crown_hold.holding() is False
    _registry(tmp_path, [])
    assert crown_hold.holding() is True


def test_a_registered_off_install_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(crown_hold, "REGISTRY", _registry(tmp_path, [_off()]))
    lines = []
    crown_hold.install(MOTOR, "1.8", log=lines.append)
    assert lines[-1] == "crown_hold_active=true reason=menu"
    assert lines[0].startswith("crown_hold_registered_off=true")


# --- every other version unchanged ------------------------------------------------------------------------------------------


def test_an_entry_for_one_version_changes_no_other(monkeypatch, tmp_path):
    monkeypatch.setattr(crown_hold, "REGISTRY", _registry(tmp_path, [_off()]))
    # another menu version (Cooling 1.8) stays held
    crown_hold.install(COOLING, "1.8", log=lambda line: None)
    assert crown_hold.ACTIVE is True and crown_hold.holding() is True
    assert crown_hold.registered_off(COOLING, "1.8") is False
    # a version with no menu block: never held, exactly as before
    crown_hold.install(MOTOR, "1.5", log=lambda line: None)
    assert crown_hold.ACTIVE is False and crown_hold.holding() is False
    # and an entry for a non-menu version does not make it a menu version
    monkeypatch.setattr(
        crown_hold, "REGISTRY", _registry(tmp_path, [_off(version="1.5")])
    )
    crown_hold.install(MOTOR, "1.5", log=lambda line: None)
    assert crown_hold.ACTIVE is False and crown_hold.holding() is False


def test_the_hold_of_every_registered_version_is_what_it_was(monkeypatch, tmp_path):
    from pathlib import Path

    from carbon.scoring import pool_version

    monkeypatch.setattr(crown_hold, "REGISTRY", _registry(tmp_path, []))
    document = json.loads(Path(pool_version.CONSTANTS).read_bytes())
    for key in document["versions"]:
        challenge_id, version = key.rsplit(" ", 1)
        crown_hold.install(challenge_id, version, log=lambda line: None)
        assert crown_hold.holding() is crown_hold.menu_registered(
            challenge_id, version
        ), key


# --- fail closed ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "holds",
    [
        [_off(hold="on")],
        [_off(hold=True)],
        [_off(authority="not a digest")],
        [_off(authority=None)],
        [_off(version="1.08")],  # a version the Challenge does not register
        [_off(version="9.9")],
        [_off(challenge="not-a-challenge")],
        [{**_off(), "extra": 1}],
        [{k: v for k, v in _off().items() if k != "authority"}],
        [_off(), _off()],  # a duplicate
        [_off(), _off(version="1.08")],  # one bad entry voids the whole registry
        "not a list",
    ],
)
def test_a_malformed_registry_leaves_the_hold_on(served_18, tmp_path, holds):
    _registry(tmp_path, holds)
    assert crown_hold.registered_off(MOTOR, "1.8") is False
    assert crown_hold.holding() is True


def test_an_unreadable_or_foreign_registry_leaves_the_hold_on(served_18, tmp_path):
    path = tmp_path / "crown_hold.json"
    path.write_text("not json")
    assert crown_hold.holding() is True
    path.write_text(json.dumps({"schema": "x", "holds": [_off()]}))
    assert crown_hold.holding() is True
    path.write_text(
        json.dumps({"schema": crown_hold.REGISTRY_SCHEMA, "holds": [_off()], "x": 1})
    )
    assert crown_hold.holding() is True
    path.unlink()
    assert crown_hold.holding() is True


# --- the coded decision and the pause flag ---------------------------------------------------------------------------------------


@posix
@pytest.mark.parametrize("name", sorted(CHANGES))
def test_with_the_hold_off_the_coded_rule_decides(served_18, tmp_path, name):
    """Held (no entry): UNAVAILABLE / crown_held_for_review. Off: the coded comparison decides as for any version."""
    held, store = consider(CHANGES[name], tmp_path, repeat=never)
    assert held["reason"] == crown_hold.CROWN_HELD and store.moves == []
    _registry(tmp_path, [_off()])
    decided, store = consider(CHANGES[name], tmp_path)
    assert decided["reason"] != crown_hold.CROWN_HELD
    assert decided["outcome"] in bp.CROWN_CHANGING and store.moves != []


@posix
@pytest.mark.parametrize("name", sorted(CHANGES))
def test_the_pause_flag_still_stops_every_crown_change_with_the_hold_off(
    served_18, tmp_path, name
):
    _registry(tmp_path, [_off()])
    flag(tmp_path, {"crowns_paused": True})
    outcome, store = consider(CHANGES[name], tmp_path, repeat=never)
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert outcome["reason"] == "crowns_paused"
    assert store.moves == [] and store.marks == {}


@posix
def test_the_operators_release_still_works_while_the_hold_is_on(served_18, tmp_path):
    release(tmp_path, ["c"])
    decided, store = consider(CHANGES["takeover"], tmp_path)
    assert decided["outcome"] == bp.CHALLENGER and store.moves != []


# --- what the queue shows -----------------------------------------------------------------------------------------------------------


def test_the_queue_shows_held_contenders_only_while_the_hold_is_on(served_18, tmp_path):
    class Pool:
        def paused_crowns(self):
            return [{"submission_id": "c"}]

    class Grader:
        _pool = staticmethod(lambda: Pool())

    view = queue_view.QueueView.__new__(queue_view.QueueView)
    view.grader = Grader()
    assert view.held() == ["c"]
    _registry(tmp_path, [_off()])
    assert view.held() is None  # a door that holds no crown shows None, never 0


def test_the_hold_code_is_a_grading_path():
    from carbon.challenge_validator import direct_receiver

    assert "carbon/challenge_validator/crown_hold.py" in direct_receiver.GRADING_PATHS
