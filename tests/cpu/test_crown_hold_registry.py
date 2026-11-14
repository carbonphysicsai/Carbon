"""The crown hold of a menu-D version can be registered OFF for one exact exam of one version (the owner's ruling, 13 Nov;
V2C's must-fixes M1 and M2).

Shipped with NO entry: Motor 1.8 stays held by default. Off only via an entry of
`scripts/validator_host_classes/crown_hold.json` that pins the sealed evaluation pack digest AND the menu epoch, and only
WHILE both equal the served pack and the registered menu epoch (a re-pack or a rotation re-engages the hold). The registry
is read once, at install. Every other version is unchanged; a bad registry holds (fail closed); the operator's pause flag
still stops every crown change. SYNTHETIC grades, digests and registry files; no value is registered.
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
PACK = digest("the sealed evaluation pack the door serves")
EPOCH = "E1"


@pytest.fixture(autouse=True)
def _restore_hold():
    yield
    crown_hold.ACTIVE = False
    for name in ("SERVED", "OFF", "PACK", "EPOCH"):
        setattr(crown_hold, name, None)


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
        "menu_epoch": EPOCH,
        "evaluation_pack_digest": PACK,
        "hold": "off",
        "authority": AUTHORITY,
        **changes,
    }


@pytest.fixture
def serve(monkeypatch, tmp_path):
    """Start a receiver serving Motor 1.8: the registry file at tmp_path, the registered menu epoch, the served pack."""

    def start(holds, *, pack=PACK, epoch=EPOCH, challenge=MOTOR, version="1.8"):
        monkeypatch.setattr(crown_hold, "REGISTRY", _registry(tmp_path, holds))
        monkeypatch.setattr(
            crown_hold, "_registered_epoch", lambda challenge_id, version_id: epoch
        )
        lines = []
        crown_hold.install(challenge, version, log=lines.append)
        if pack is not None:
            crown_hold.bind_pack(pack, log=lines.append)
        return lines

    return start


# --- shipped held ------------------------------------------------------------------------------------------------------


def test_the_committed_registry_holds_motor_18_unless_an_owner_record_registers_it_off():
    """Shipped EMPTY: Motor 1.8 is held by default. Once the owner registers the hold OFF, the committed entry is
    exactly the tracked owner-provisional record's (its pack, epoch and the digest of his words).
    """
    document = json.loads(crown_hold.REGISTRY.read_bytes())
    assert document["schema"] == crown_hold.REGISTRY_SCHEMA
    record_path = (
        crown_hold.REGISTRY.parent / "records" / "crown_provisional_motor18.json"
    )
    off = crown_hold.registered_off(MOTOR, "1.8")
    if not document["holds"]:
        assert off is None
    else:
        record = json.loads(record_path.read_bytes())
        assert record["crown_hold"] == "OFF_REGISTERED"
        assert off == {
            "menu_epoch": record["menu_epoch"],
            "evaluation_pack_digest": record["evaluation_pack_digest"],
        }
    crown_hold.install(MOTOR, "1.8", log=lambda line: None)
    crown_hold.bind_pack(
        PACK, log=lambda line: None
    )  # a pack that is not the registered one
    assert crown_hold.ACTIVE is True
    # held for any other pack, whatever the registry says; off only for the exact registered exam
    assert crown_hold.holding() is True
    assert crown_hold.held("/nowhere", "any-contender") is True


def test_the_registry_is_outside_the_worker_image_build_inputs():
    from carbon.reconstruction.worker import build_inputs

    root = crown_hold.REGISTRY.parents[2]
    relative = crown_hold.REGISTRY.resolve().relative_to(root).as_posix()
    assert not any(
        relative == item or relative.startswith(item + "/")
        for item in build_inputs.paths()
    )


# --- off only via an entry, and only for that exact pack and epoch -----------------------------------------------------


def test_an_entry_turns_the_hold_off_while_the_pack_and_the_epoch_match(
    serve, tmp_path
):
    serve([_off()])
    assert crown_hold.off_in_force() is True
    assert crown_hold.holding() is False
    assert crown_hold.held(tmp_path, "any-contender") is False
    # the version is still a menu version: the menu re-check (`ACTIVE`) keeps running
    assert crown_hold.ACTIVE is True and crown_hold.menu_registered(MOTOR, "1.8")


def test_before_the_pack_is_bound_the_hold_stays_on(serve):
    serve([_off()], pack=None)
    assert crown_hold.holding() is True
    crown_hold.bind_pack(None)  # a receiver with no sealed pack
    assert crown_hold.holding() is True


def test_a_re_pack_re_engages_the_hold(serve):
    """V2C M1: the entry pins the pack digest; a receiver serving another pack is held."""
    serve([_off()], pack=digest("a re-packed exam"))
    assert crown_hold.holding() is True
    # and binding the pinned pack afterwards is what turns it off
    assert crown_hold.bind_pack(PACK, log=lambda line: None) is True
    assert crown_hold.holding() is False


def test_an_epoch_change_re_engages_the_hold(serve):
    """V2C M1: the entry pins the menu epoch; a version registered at another epoch is held."""
    serve([_off()], epoch="E2")
    assert crown_hold.holding() is True
    serve(
        [_off(menu_epoch="E2")], epoch="E1"
    )  # the entry names an epoch that is not the registered one
    assert crown_hold.holding() is True
    serve([_off(menu_epoch="E2")], epoch="E2")  # both at E2: in force again
    assert crown_hold.holding() is False
    serve([_off()], epoch=None)  # the registered epoch cannot be read
    assert crown_hold.holding() is True


# --- read once, at install (V2C M2) ---------------------------------------------------------------------------------------


def test_the_registry_is_read_once_at_install_and_the_result_is_logged(serve, tmp_path):
    lines = serve([_off()])
    assert any(
        line.startswith("crown_hold_registry_off=true") and PACK[:23] in line
        for line in lines
    )
    assert lines[-1] == "crown_hold_off_in_force=true"
    assert "crown_hold_active=true reason=menu" in lines
    # a later edit of the file changes nothing in this process (a change is commit + push + roll)
    _registry(tmp_path, [])
    assert crown_hold.holding() is False
    # and the other direction: an entry added after install does not turn the hold off
    serve([])
    _registry(tmp_path, [_off()])
    assert crown_hold.holding() is True


def test_an_install_without_an_entry_says_so(serve):
    lines = serve([])
    assert lines[0].startswith("crown_hold_registry_off=false")
    assert (
        lines[-1] == "crown_hold_active=true reason=menu"
    )  # no bind_pack line without an entry


def test_a_mismatched_pack_is_logged_as_not_in_force(serve):
    lines = serve([_off()], pack=digest("another pack"))
    assert lines[-1] == "crown_hold_off_in_force=false"


# --- every other version unchanged ------------------------------------------------------------------------------------------


def test_an_entry_for_one_version_changes_no_other(serve):
    # another menu version (Cooling 1.8) stays held
    serve([_off()], challenge=COOLING, version="1.8")
    assert crown_hold.ACTIVE is True and crown_hold.holding() is True
    assert crown_hold.registered_off(COOLING, "1.8", path=crown_hold.REGISTRY) is None
    # a version with no menu block: never held, exactly as before
    serve([_off()], challenge=MOTOR, version="1.5")
    assert crown_hold.ACTIVE is False and crown_hold.holding() is False
    # and an entry for a non-menu version does not make it a menu version
    serve([_off(version="1.5")], challenge=MOTOR, version="1.5")
    assert crown_hold.ACTIVE is False and crown_hold.holding() is False


def test_the_hold_of_every_registered_version_is_what_it_was(monkeypatch, tmp_path):
    from pathlib import Path

    from carbon.scoring import pool_version

    monkeypatch.setattr(crown_hold, "REGISTRY", _registry(tmp_path, []))
    document = json.loads(Path(pool_version.CONSTANTS).read_bytes())
    for key in document["versions"]:
        challenge_id, version = key.rsplit(" ", 1)
        crown_hold.install(challenge_id, version, log=lambda line: None)
        crown_hold.bind_pack(PACK, log=lambda line: None)
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
        [_off(evaluation_pack_digest="not a digest")],
        [_off(evaluation_pack_digest=None)],
        [_off(menu_epoch="")],
        [_off(menu_epoch=None)],
        [_off(version="1.08")],  # a version the Challenge does not register
        [_off(version="9.9")],
        [_off(challenge="not-a-challenge")],
        [{**_off(), "extra": 1}],
        [{k: v for k, v in _off().items() if k != "authority"}],
        [{k: v for k, v in _off().items() if k != "menu_epoch"}],
        [{k: v for k, v in _off().items() if k != "evaluation_pack_digest"}],
        [_off(), _off()],  # a duplicate
        [_off(), _off(version="1.08")],  # one bad entry voids the whole registry
        "not a list",
    ],
)
def test_a_malformed_registry_leaves_the_hold_on(serve, holds):
    serve(holds)
    assert crown_hold.OFF is None
    assert crown_hold.holding() is True


def test_an_unreadable_or_foreign_registry_leaves_the_hold_on(
    serve, monkeypatch, tmp_path
):
    serve([_off()])
    path = crown_hold.REGISTRY
    for body in (
        "not json",
        json.dumps({"schema": "x", "holds": [_off()]}),
        json.dumps({"schema": crown_hold.REGISTRY_SCHEMA, "holds": [_off()], "x": 1}),
    ):
        path.write_text(body)
        assert crown_hold.registered_off(MOTOR, "1.8") is None
        crown_hold.install(MOTOR, "1.8", log=lambda line: None)
        crown_hold.bind_pack(PACK, log=lambda line: None)
        assert crown_hold.holding() is True
    path.unlink()
    crown_hold.install(MOTOR, "1.8", log=lambda line: None)
    crown_hold.bind_pack(PACK, log=lambda line: None)
    assert crown_hold.holding() is True


# --- the coded decision and the pause flag ---------------------------------------------------------------------------------------


@posix
@pytest.mark.parametrize("name", sorted(CHANGES))
def test_with_the_hold_off_the_coded_rule_decides(serve, tmp_path, name):
    """Held (no entry): UNAVAILABLE / crown_held_for_review. Off: the coded comparison decides as for any version."""
    serve([])
    held, store = consider(CHANGES[name], tmp_path, repeat=never)
    assert held["reason"] == crown_hold.CROWN_HELD and store.moves == []
    serve([_off()])
    decided, store = consider(CHANGES[name], tmp_path)
    assert decided["reason"] != crown_hold.CROWN_HELD
    assert decided["outcome"] in bp.CROWN_CHANGING and store.moves != []


@posix
@pytest.mark.parametrize("name", sorted(CHANGES))
def test_the_pause_flag_still_stops_every_crown_change_with_the_hold_off(
    serve, tmp_path, name
):
    serve([_off()])
    flag(tmp_path, {"crowns_paused": True})
    outcome, store = consider(CHANGES[name], tmp_path, repeat=never)
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert outcome["reason"] == "crowns_paused"
    assert store.moves == [] and store.marks == {}


@posix
def test_the_operators_release_still_works_while_the_hold_is_on(serve, tmp_path):
    serve([])
    release(tmp_path, ["c"])
    decided, store = consider(CHANGES["takeover"], tmp_path)
    assert decided["outcome"] == bp.CHALLENGER and store.moves != []


# --- what the queue shows -----------------------------------------------------------------------------------------------------------


def test_the_queue_shows_held_contenders_only_while_the_hold_is_on(serve):
    class Pool:
        def paused_crowns(self):
            return [{"submission_id": "c"}]

    class Grader:
        _pool = staticmethod(lambda: Pool())

    view = queue_view.QueueView.__new__(queue_view.QueueView)
    view.grader = Grader()
    serve([])
    assert view.held() == ["c"]
    serve([_off()])
    assert view.held() is None  # a door that holds no crown shows None, never 0
    serve([_off()], pack=digest("a re-packed exam"))
    assert view.held() == ["c"]  # a re-pack re-engages it


# --- the receiver ---------------------------------------------------------------------------------------------------------------


def test_the_receiver_names_its_sealed_pack_right_after_attaching_it():
    import inspect

    from carbon.challenge_validator import direct_receiver

    source = inspect.getsource(direct_receiver.serve)
    attach = source.index("_sealed_pack(")
    bind = source.index("crown_hold.bind_pack(pack_digest)")
    discovery = source.index("DirectFixtureDiscovery(")
    assert source.index("crown_hold.install(") < attach < bind < discovery


def test_the_hold_code_is_a_grading_path():
    from carbon.challenge_validator import direct_receiver

    assert "carbon/challenge_validator/crown_hold.py" in direct_receiver.GRADING_PATHS
