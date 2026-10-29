"""The operator pause switch: crown changes and the weights run (one flag file, read at decision time)."""

import argparse
import asyncio
import json
import os
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import operator_pause
from carbon.validator_setup import weights
from carbon.validator_setup.bundle import SetupRefused
from tests.cpu import test_crown_grade_repeat as base

pytestmark = pytest.mark.skipif(
    not hasattr(os, "geteuid"), reason="owner-only file modes are POSIX"
)


def flag(directory, body, mode=0o600):
    path = operator_pause.flag_path(directory)
    path.write_text(json.dumps(body), encoding="utf-8")
    path.chmod(mode)
    return path


class Store(base.Store):
    def __init__(self, fixed, directory):
        super().__init__(fixed)
        self.path = directory / "pool.sqlite3"


def consider(fixed, directory, repeat=None):
    store = Store(fixed, directory)
    promotion = bp.BankPromotion.__new__(bp.BankPromotion)
    promotion.store = store
    promotion.registered_source_receipt_sha256 = base.digest("pin")
    outcome = promotion.consider_private(
        fixed["candidate"]["submission_id"],
        base.KEY,
        base.comparator(),
        repeat=repeat or base.same_again(fixed),
    )
    return outcome, store


def never(model):
    raise AssertionError("a paused crown change spends no repeat grade")


CHANGES = dict(base.CASES)
CHANGES["dethrone_without_successor"] = base.pair(
    base.body("c", "FAILED_INFRA"), base.body("k", "MANDATORY_GATE_FAILED", 0.0)
)


@pytest.mark.parametrize("name", sorted(CHANGES))
def test_paused_crowns_change_nothing_for_every_crown_changing_outcome(name, tmp_path):
    flag(tmp_path, {"crowns_paused": True})
    outcome, store = consider(CHANGES[name], tmp_path, repeat=never)
    assert outcome["outcome"] == bp.UNAVAILABLE
    assert outcome["reason"] == "crowns_paused"
    assert outcome["candidate"] == "c"
    assert store.moves == [] and store.marks == {}


@pytest.mark.parametrize("name", sorted(CHANGES))
def test_removing_the_flag_lets_the_same_contender_be_considered_again(name, tmp_path):
    path = flag(tmp_path, {"crowns_paused": True})
    paused, store = consider(CHANGES[name], tmp_path, repeat=never)
    assert paused["reason"] == "crowns_paused" and store.moves == []
    path.unlink()
    resumed, store = consider(CHANGES[name], tmp_path)
    assert resumed["outcome"] in bp.CROWN_CHANGING
    assert store.moves != []
    # The contender's repeat ran as normal and was marked.
    assert store.marks


def test_an_outcome_that_changes_no_crown_is_not_touched_by_the_pause(tmp_path):
    flag(tmp_path, {"crowns_paused": True})
    fixed = base.pair(base.body("c", total=0.55), base.body("k", total=0.5))
    outcome, store = consider(fixed, tmp_path, repeat=never)
    assert outcome["outcome"] == bp.INCUMBENT_KEEPS and store.moves == []


def test_the_weights_flag_alone_does_not_pause_crowns(tmp_path):
    flag(tmp_path, {"weights_paused": True})
    outcome, store = consider(CHANGES["takeover"], tmp_path)
    assert outcome["outcome"] == bp.CHALLENGER and store.moves != []


@pytest.mark.parametrize(
    "bad",
    ["not json", "[]", '{"crowns_paused": "yes"}', '{"crowns": true}', "{}x"],
)
def test_an_unreadable_flag_pauses_both(tmp_path, bad):
    path = operator_pause.flag_path(tmp_path)
    path.write_text(bad, encoding="utf-8")
    path.chmod(0o600)
    assert operator_pause.read(tmp_path) == {
        "crowns_paused": True,
        "weights_paused": True,
    }


def test_a_flag_others_can_write_or_a_symlink_pauses_both(tmp_path):
    flag(tmp_path, {"crowns_paused": False}, mode=0o644)
    assert operator_pause.crowns_paused(tmp_path) is True
    operator_pause.flag_path(tmp_path).unlink()
    target = tmp_path / "elsewhere"
    target.write_text("{}", encoding="utf-8")
    target.chmod(0o600)
    operator_pause.flag_path(tmp_path).symlink_to(target)
    assert operator_pause.weights_paused(tmp_path) is True


def test_no_flag_means_running(tmp_path):
    running = {"crowns_paused": False, "weights_paused": False}
    assert operator_pause.read(tmp_path) == running
    flag(tmp_path, running)
    assert operator_pause.read(tmp_path) == running


def operator_config(tmp_path):
    from tests.cpu.test_validator_setup_weights import config

    return config(tmp_path)[0]


def test_weights_run_is_refused_before_any_wallet_issuer_or_reader(
    tmp_path, monkeypatch
):
    from carbon.chain import sdk, sdk_weights
    from carbon.rewards import testnet_winner_publication as publication

    def forbidden(*args, **kwargs):
        raise AssertionError("a paused run must not reach these")

    monkeypatch.setattr(sdk, "BittensorReader", forbidden)
    monkeypatch.setattr(sdk_weights, "open_operator_wallet", forbidden)
    monkeypatch.setattr(publication, "_issuer", forbidden)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    flag(state, {"weights_paused": True})
    args = argparse.Namespace(
        config=operator_config(tmp_path),
        action="run",
        journal=state / "journal.sqlite3",
    )
    with pytest.raises(SetupRefused, match="weights_paused"):
        asyncio.run(weights.execute(args))
    assert list(state.iterdir()) == [operator_pause.flag_path(state)]


def test_preview_still_works_while_weights_are_paused(tmp_path, monkeypatch):
    from carbon.chain import sdk
    from carbon.rewards import testnet_winner_publication as publication

    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    flag(state, {"crowns_paused": True, "weights_paused": True})

    class Reader:
        async def capture(self, _context):
            return "snapshot"

    monkeypatch.setattr(publication, "_issuer", lambda *a: "issuer")
    monkeypatch.setattr(sdk, "BittensorReader", Reader)
    monkeypatch.setattr(publication, "preview", lambda issuer, snap: (issuer, snap))
    args = SimpleNamespace(
        config=operator_config(tmp_path),
        action="preview",
        journal=state / "journal.sqlite3",
    )
    assert asyncio.run(weights.execute(args)) == ("issuer", "snapshot")


def test_the_crowns_flag_alone_does_not_refuse_the_weights_run(tmp_path, monkeypatch):
    from carbon.rewards import testnet_winner_publication as publication

    class Reached(Exception):
        pass

    def issuer(*args, **kwargs):
        raise Reached

    monkeypatch.setattr(publication, "_issuer", issuer)
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    flag(state, {"crowns_paused": True})
    args = SimpleNamespace(
        config=operator_config(tmp_path),
        action="run",
        journal=state / "journal.sqlite3",
    )
    with pytest.raises(Reached):
        asyncio.run(weights.execute(args))


TASK = "rtsk_" + "a" * 64


class FakeIntake:
    """Stands for the receiver: retains a task and reports its crown decision, which the operator's pause withholds."""

    def __init__(self, directory):
        self.directory = directory
        self.calls = 0
        self.adapter = SimpleNamespace(
            contract_digest="c",
            ledger=SimpleNamespace(submitted_outcomes=lambda digest: [TASK]),
        )

    def retain_result(self, submission_id, **kwargs):
        self.calls += 1
        paused = operator_pause.crowns_paused(self.directory)
        outcome = (
            {"outcome": bp.UNAVAILABLE, "reason": "crowns_paused"}
            if paused
            else {"outcome": bp.CHALLENGER, "reason": "bank_comparison_development"}
        )
        return {"entry_id": "sha256:" + "b" * 64, "koth_comparison": outcome}


def grader(tmp_path):
    from carbon.challenge_validator.auto_grade import AutoGrader

    state = tmp_path / "state"
    state.mkdir(mode=0o700, exist_ok=True)
    intake = FakeIntake(state)
    auto = AutoGrader(intake, tmp_path)
    auto._pool = lambda: SimpleNamespace(path=state / "pool.sqlite3")
    return auto, intake, state


def marker_state(tmp_path):
    return json.loads((tmp_path / "auto-grade/markers" / (TASK + ".json")).read_text())[
        "state"
    ]


def test_a_paused_crown_is_marked_paused_not_graded(tmp_path):
    auto, _intake, state = grader(tmp_path)
    flag(state, {"crowns_paused": True})
    assert auto.run_once() == (TASK, "GRADED")
    assert marker_state(tmp_path) == "PAUSED"


def test_nothing_is_retried_while_the_flag_stands(tmp_path):
    auto, intake, state = grader(tmp_path)
    flag(state, {"crowns_paused": True})
    auto.run_once()
    for _ in range(3):
        assert auto.run_once() is None
    assert intake.calls == 1 and marker_state(tmp_path) == "PAUSED"


def test_clearing_the_flag_considers_the_contender_again_without_manual_action(
    tmp_path,
):
    auto, intake, state = grader(tmp_path)
    path = flag(state, {"crowns_paused": True})
    auto.run_once()
    path.unlink()
    assert auto.run_once() == (TASK, "GRADED")
    assert intake.calls == 2
    assert marker_state(tmp_path) == "GRADED"
    # Once graded it is not retained again.
    assert auto.run_once() is None and intake.calls == 2


def test_a_graded_task_is_never_retried_by_the_resume(tmp_path):
    auto, intake, state = grader(tmp_path)
    assert auto.run_once() == (TASK, "GRADED") and marker_state(tmp_path) == "GRADED"
    flag(state, {"crowns_paused": True})
    assert auto.run_once() is None
    operator_pause.flag_path(state).unlink()
    assert auto.run_once() is None and intake.calls == 1
