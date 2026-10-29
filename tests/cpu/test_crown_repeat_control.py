"""V7 (OWNER-ATTACK-RISKS-V7-G4B-01, Validator V7 rulings, codex-queue/reports/VALIDATOR_V7_RULINGS_20261029.md): the control rebuild and the repeat-miss watch.

A crown-changing repeat beyond tolerance runs a Carbon control rebuild on the same host. The control reproduces:
`candidate_not_reproducible`, no crown, no host alert. The control misses, cannot run, is not registered, or the miss is
the incumbent's: FAILED_INFRA with the typed alert. One hotkey with three misses on a Challenge within a day: an operator
alert only.
"""

import json
import logging
import math

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import koth_registry, repeat_miss_watch
from carbon.challenge_validator import lean_recipe_retention as retention
from tests.cpu import test_crown_grade_repeat as base


def miss_by(again, who, by=0.2):
    """A repeat that moves ``who``'s total beyond the registered 0.1."""

    def repeat(model):
        row = again(model)
        return base.moved(row, by) if model in who else row

    return repeat


def consider(fixed, repeat, control=None, noise=base.NOISE):
    store = base.Store(fixed)
    promotion = bp.BankPromotion.__new__(bp.BankPromotion)
    promotion.store = store
    promotion.registered_source_receipt_sha256 = base.digest("pin")
    outcome = promotion.consider_private(
        fixed["candidate"]["submission_id"],
        base.KEY,
        base.comparator(noise),
        repeat=repeat,
        control=control,
    )
    return outcome, store


TAKEOVER = base.CASES["takeover"]


# --- the decision ------------------------------------------------------------------------------------------------------


def test_a_control_that_reproduces_makes_the_miss_the_candidates_not_the_hosts():
    outcome, store = consider(
        TAKEOVER, miss_by(base.same_again(TAKEOVER), {"c"}), control=lambda: True
    )
    assert (
        outcome["outcome"]
        == bp.CANDIDATE_NOT_REPRODUCIBLE
        == "candidate_not_reproducible"
    )
    assert outcome["reason"] == bp.CONTROL_REPRODUCED
    assert "alert" not in outcome  # no host alert
    assert store.moves == [] and store.marks == {}  # no crown, no repeat mark


@pytest.mark.parametrize(
    "control,state",
    [
        (lambda: False, "missed"),
        (lambda: "yes", "missed"),
        (lambda: None, "missed"),
        (lambda: (_ for _ in ()).throw(RuntimeError("cannot run")), "unavailable"),
        (None, "none_registered"),
    ],
)
def test_a_control_that_misses_cannot_run_or_is_absent_keeps_failed_infra_and_the_host_alert(
    control, state
):
    outcome, store = consider(
        TAKEOVER, miss_by(base.same_again(TAKEOVER), {"c"}), control=control
    )
    assert outcome["outcome"] == bp.FAILED_INFRA
    assert outcome["reason"] == bp.REPEAT_MISMATCH
    assert outcome["alert"]["control"] == state
    assert outcome["alert"]["action"] == "recheck_validator_host"
    assert store.moves == [] and store.marks == {}


def test_an_incumbents_miss_is_not_put_down_to_the_candidate():
    called = []
    outcome, _store = consider(
        TAKEOVER,
        miss_by(base.same_again(TAKEOVER), {"k"}),
        control=lambda: called.append(1) or True,
    )
    assert outcome["outcome"] == bp.FAILED_INFRA
    assert outcome["alert"]["control"] == "not_applicable" and called == []
    both, _ = consider(
        TAKEOVER,
        miss_by(base.same_again(TAKEOVER), {"c", "k"}),
        control=lambda: called.append(1) or True,
    )
    assert both["outcome"] == bp.FAILED_INFRA and called == []


def test_the_control_is_not_run_when_the_repeat_agrees():
    def never():
        raise AssertionError("no miss, no control")

    outcome, store = consider(TAKEOVER, base.same_again(TAKEOVER), control=never)
    assert outcome["outcome"] == bp.CHALLENGER and store.moves != []


def test_no_registered_tolerance_is_still_unavailable_before_any_control():
    def never():
        raise AssertionError("no tolerance, no control")

    outcome, _ = consider(
        TAKEOVER, miss_by(base.same_again(TAKEOVER), {"c"}), control=never, noise=None
    )
    assert outcome["outcome"] == bp.UNAVAILABLE


# --- the registered control ---------------------------------------------------------------------------------------------

CHALLENGE = "electric-motor-magnetics"
CONTROL = {
    "entry_id": base.digest("control entry"),
    "reference_total": 0.62,
    "reference_fingerprint": base.digest("control fingerprint"),
    "control_basis": "bit_identical",
}


def registry(tmp_path, noise):
    path = tmp_path / "noise.json"
    path.write_text(
        json.dumps({"schema": koth_registry.SCHEMA, "challenges": {CHALLENGE: noise}})
    )
    return path


NOISE = {"value": 0.01, "measurement_digest": base.digest("noise record")}


def test_a_control_registered_beside_the_noise_is_read_and_the_noise_stays_two_keys(
    tmp_path,
):
    path = registry(tmp_path, {**NOISE, "control": CONTROL})
    assert koth_registry.control(CHALLENGE, path=path) == CONTROL
    assert koth_registry.rebuild_noise(CHALLENGE, path=path) == NOISE
    # The comparator, whose key set is exact, is unchanged by it.
    assert set(koth_registry.rebuild_noise(CHALLENGE, path=path)) == {
        "value",
        "measurement_digest",
    }


def test_without_a_control_there_is_none_and_the_noise_is_as_before(tmp_path):
    path = registry(tmp_path, dict(NOISE))
    assert koth_registry.control(CHALLENGE, path=path) is None
    assert koth_registry.rebuild_noise(CHALLENGE, path=path) == NOISE
    assert koth_registry.control("not-registered", path=path) is None


@pytest.mark.parametrize(
    "bad",
    [
        {**CONTROL, "control_basis": "close_enough"},
        {**CONTROL, "entry_id": "latest"},
        {**CONTROL, "reference_fingerprint": None},
        {**CONTROL, "reference_total": math.inf},
        {**CONTROL, "reference_total": "0.6"},
        {k: v for k, v in CONTROL.items() if k != "reference_total"},
        {**CONTROL, "extra": 1},
        "control",
    ],
)
def test_a_malformed_control_makes_the_registry_invalid(tmp_path, bad):
    path = registry(tmp_path, {**NOISE, "control": bad})
    with pytest.raises(koth_registry.RegistryInvalid):
        koth_registry.control(CHALLENGE, path=path)


def evidence(total, **model):
    return {
        "model_p": {"score_status": bp.SCORED, "total_score": total, **model},
        "score_compatibility": {"score_pack_digest": base.digest("pack")},
    }


def test_a_bit_identical_control_reproduces_only_on_its_exact_grade_fingerprint():
    grade = evidence(0.62)
    control = {
        **CONTROL,
        "reference_fingerprint": bp.grade_fingerprint({"evidence": grade}),
    }
    assert retention._control_reproduced(control, grade, {}) is True
    assert retention._control_reproduced(control, evidence(0.62 + 2**-52), {}) is False
    assert retention._control_reproduced(control, evidence(0.9), {}) is False


def test_a_within_noise_control_reproduces_on_its_total_within_the_registered_noise():
    control = {**CONTROL, "control_basis": "within_noise"}
    comparator = {"rebuild_noise": NOISE}
    assert retention._control_reproduced(control, evidence(0.62), comparator) is True
    assert retention._control_reproduced(control, evidence(0.629), comparator) is True
    assert retention._control_reproduced(control, evidence(0.64), comparator) is False
    # No registered noise: nothing can be said to reproduce.
    assert retention._control_reproduced(control, evidence(0.62), {}) is False
    assert (
        retention._control_reproduced(
            control, {"model_p": {"total_score": "x"}}, comparator
        )
        is False
    )


def test_the_control_check_rebuilds_the_registered_entry_through_the_uncounted_repeat_grade(
    monkeypatch,
):
    asked = []
    grade = evidence(0.62)
    monkeypatch.setattr(
        retention,
        "repeat_grade",
        lambda adapter, entry_id, **custody: asked.append((adapter, entry_id, custody))
        or grade,
    )
    control = {
        **CONTROL,
        "reference_fingerprint": bp.grade_fingerprint({"evidence": grade}),
    }

    def repeat(model):
        raise AssertionError("not run")

    repeat.adapter, repeat.custody = "ADAPTER", {"artifact_directory": "A"}
    check = retention._control_check(repeat, control, {})
    assert check() is True
    assert asked == [("ADAPTER", control["entry_id"], {"artifact_directory": "A"})]
    # With no registered control, or a repeat with nothing to rebuild with, there is no check.
    assert retention._control_check(repeat, None, {}) is None
    assert retention._control_check(lambda model: None, control, {}) is None


# --- the watch ------------------------------------------------------------------------------------------------------------


def store_in(tmp_path):
    from carbon.battery.pool_store import PoolStore

    return PoolStore(tmp_path / "pool.sqlite3")


def miss_outcome(kind=bp.FAILED_INFRA, key=None):
    return {
        "outcome": kind,
        "reason": (
            bp.REPEAT_MISMATCH if kind == bp.FAILED_INFRA else bp.CONTROL_REPRODUCED
        ),
        "evaluation_key": key or base.KEY,
    }


class Adapter:
    challenge_id = CHALLENGE
    contract_digest = "sha256:" + "c" * 64
    ledger = None

    def __init__(self, blocks, owners):
        self.blocks, self.owners = blocks, owners

    def owner(self, submission_id):
        return self.owners.get(submission_id)


@pytest.fixture
def watch_env(tmp_path, monkeypatch):
    blocks = {}
    monkeypatch.setattr(
        repeat_miss_watch.exam_cap,
        "submission_block",
        lambda ledger, contract, submission_id: blocks.get(submission_id),
    )
    return store_in(tmp_path), blocks


DAY = repeat_miss_watch.WINDOW_BLOCKS


def file_miss(
    store, blocks, owners, submission, block, hotkey="hk", kind=bp.FAILED_INFRA
):
    blocks[submission] = block
    owners[submission] = hotkey
    return repeat_miss_watch.watch(
        store,
        Adapter(blocks, owners),
        submission,
        miss_outcome(kind, base.digest(submission)),
    )


def test_three_misses_by_one_hotkey_on_one_challenge_in_a_day_raise_one_operator_alert(
    watch_env, caplog
):
    store, blocks = watch_env
    owners = {}
    caplog.set_level(logging.WARNING, logger="carbon.repeat_miss_watch")
    assert file_miss(store, blocks, owners, "a", 1000) is None
    assert (
        file_miss(store, blocks, owners, "b", 1100, kind=bp.CANDIDATE_NOT_REPRODUCIBLE)
        is None
    )
    alert = file_miss(store, blocks, owners, "c", 1200)
    assert alert == {
        "alert": "repeat_miss_watch",
        "status": "PROVISIONAL",
        "hotkey": "hk",
        "challenge_id": CHALLENGE,
        "misses_in_window": 3,
        "window_blocks": DAY,
    }
    assert [r.getMessage() for r in caplog.records] == [
        "repeat_miss_alert " + json.dumps(alert, sort_keys=True)
    ]
    # One alert per hotkey, Challenge and window, however many misses follow.
    assert file_miss(store, blocks, owners, "d", 1300) is None
    assert [a["count"] for a in store.repeat_miss_alerts()] == [3]


def test_misses_of_another_hotkey_challenge_or_day_are_not_counted(watch_env):
    store, blocks = watch_env
    owners = {}
    assert file_miss(store, blocks, owners, "a", 1000) is None
    assert file_miss(store, blocks, owners, "b", 1100, hotkey="other") is None
    assert file_miss(store, blocks, owners, "c", 1200, hotkey="other") is None
    # A hotkey's misses more than a day apart do not add up.
    assert file_miss(store, blocks, owners, "d", 1000 + 2 * DAY) is None
    assert file_miss(store, blocks, owners, "e", 1000 + 4 * DAY) is None
    assert store.repeat_miss_alerts() == []
    other = Adapter(blocks, owners)
    other.challenge_id = "chip-cold-plate"
    results = []
    for submission, block in (("f", 5000), ("g", 5100), ("h", 5200)):
        blocks[submission], owners[submission] = block, "hk"
        results.append(
            repeat_miss_watch.watch(
                store, other, submission, miss_outcome(key=base.digest(submission))
            )
        )
    assert (
        results[:2] == [None, None] and results[2]["challenge_id"] == "chip-cold-plate"
    )
    assert [a["challenge_id"] for a in store.repeat_miss_alerts()] == [
        "chip-cold-plate"
    ]


def test_an_outcome_that_is_not_a_repeat_miss_records_nothing(watch_env):
    store, blocks = watch_env
    owners = {"a": "hk"}
    blocks["a"] = 1000
    for outcome in (
        {"outcome": bp.CHALLENGER, "reason": "x", "evaluation_key": base.KEY},
        {
            "outcome": bp.FAILED_INFRA,
            "reason": "crowns_paused",
            "evaluation_key": base.KEY,
        },
        {
            "outcome": bp.UNAVAILABLE,
            "reason": bp.REPEAT_MISMATCH,
            "evaluation_key": base.KEY,
        },
        {"error": "boom"},
        None,
    ):
        assert (
            repeat_miss_watch.watch(store, Adapter(blocks, owners), "a", outcome)
            is None
        )
    assert store.repeat_miss_blocks("hk", CHALLENGE) == []


def test_the_watch_never_raises_and_never_alters_an_outcome(watch_env):
    store, blocks = watch_env

    class Broken:
        challenge_id = CHALLENGE

        def owner(self, submission_id):
            raise RuntimeError("ledger gone")

    outcome = miss_outcome()
    snapshot = dict(outcome)
    assert repeat_miss_watch.watch(store, Broken(), "a", outcome) is None
    assert outcome == snapshot
    # An unknown hotkey or block files nothing.
    assert repeat_miss_watch.watch(store, Adapter(blocks, {}), "a", outcome) is None
    assert (
        repeat_miss_watch.watch(store, Adapter(blocks, {"a": "hk"}), "a", outcome)
        is None
    )
    assert store.repeat_miss_blocks("hk", CHALLENGE) == []


def test_recording_a_miss_twice_counts_it_once(watch_env):
    store, blocks = watch_env
    owners = {}
    file_miss(store, blocks, owners, "a", 1000)
    file_miss(store, blocks, owners, "a", 1000)
    assert store.repeat_miss_blocks("hk", CHALLENGE) == [1000]


def test_the_alert_values_are_the_validators_provisional_ones():
    from carbon.challenge_validator import exam_cap

    assert repeat_miss_watch.STATUS == "PROVISIONAL"
    assert repeat_miss_watch.COUNT == 3
    assert repeat_miss_watch.WINDOW_BLOCKS == exam_cap.DAY_BLOCKS
