"""Battery exam rule v2 (OWNER-BATTERY-SCORING-WINDOW-01).

v2 replaces v1's global "rotate after 3 admitted" with one scored submission
per hotkey per 360-block tempo and block-based rotation that never stalls
miners. Everything else is v1's. The fixtures are the daemon's (real PyBaMM
references, `DirectBackend` in process); these check control flow and the
rule's semantics, not isolation or truth solves.
"""

import dataclasses
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    PIN_G,
    backend,  # noqa: F401 - fixture
    make,
    refs,  # noqa: F401 - fixture
    submission,
)

from carbon.battery import deployment, exam, seeds
from carbon.battery.daemon import BatteryValidator, rule_digest
from carbon.battery.pool_store import (
    HotkeyWindowUsed,
    PoolStore,
    StateError,
)

V2 = exam.DEVELOPMENT_RULE_V2
TEMPO = V2["per_hotkey"]["window_blocks"]
EVERY = V2["rotation"]["every_blocks"]


def at(block, hotkey="hk1", neighbours=8):
    base = submission(hotkey, neighbours=neighbours)
    return dataclasses.replace(base, receipt={**base.receipt, "block": block})


def test_v2_changes_only_the_rotation_and_adds_the_hotkey_window():
    v1 = exam.DEVELOPMENT_RULE
    assert "rotate_after_admitted" not in V2
    assert V2["per_hotkey"] == {"scored_per_window": 1, "window_blocks": 360}
    assert V2["rotation"] == {"basis": "finalized_block", "every_blocks": 1080}
    unchanged = set(v1) - {"rotate_after_admitted", "authority"}
    assert {k: V2[k] for k in unchanged} == {k: v1[k] for k in unchanged}
    assert rule_digest(V2) != rule_digest(v1)
    assert exam.hotkey_window(V2, 361) == (360, 720)
    assert exam.hotkey_window(v1, 361) is None


def test_one_submission_per_hotkey_per_tempo(tmp_path, refs, backend):  # noqa: F811
    validator = make(tmp_path, refs, backend, rule=V2)
    first = validator.admit(at(TEMPO + 5))
    assert first["state"] == "ADMITTED"
    with pytest.raises(HotkeyWindowUsed) as used:
        validator.admit(at(TEMPO + 100, neighbours=9))
    assert used.value.next_block == 2 * TEMPO
    # Nothing was recorded for the refused one; another hotkey is unaffected,
    # and the same hotkey is admissible in the next tempo.
    assert validator.store.pending_submissions() == [first["submission_id"]]
    assert validator.admit(at(TEMPO + 100, hotkey="hk2"))["state"] == "ADMITTED"
    assert validator.admit(at(2 * TEMPO, neighbours=9))["state"] == "ADMITTED"


def test_a_resend_of_the_admitted_submission_is_not_a_second_one(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    validator = make(tmp_path, refs, backend, rule=V2)
    sid = validator.admit(at(TEMPO + 5))["submission_id"]
    assert validator.admit(at(TEMPO + 50))["submission_id"] == sid


def test_an_invalid_construction_does_not_use_the_window(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    from carbon.reconstruction import capability_registry as registry

    validator = make(tmp_path, refs, backend, rule=V2)
    wrong = registry.contract_digest(registry.BURGERS_CHALLENGE)
    bad = dataclasses.replace(at(TEMPO + 1), contract_digest=wrong)
    assert validator.admit(bad)["state"] == "INVALID_CONSTRUCTION"
    assert validator.admit(at(TEMPO + 2))["state"] == "ADMITTED"


def test_a_receipt_without_a_block_is_not_admitted_under_v2(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    validator = make(tmp_path, refs, backend, rule=V2)
    with pytest.raises(HotkeyWindowUsed) as used:
        validator.admit(submission("hk1"))
    assert used.value.next_block is None
    assert validator.store.pending_submissions() == []


def test_rotation_follows_blocks_not_submission_counts(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    validator = make(tmp_path, refs, backend, rule=V2)
    start = 10 * TEMPO
    for n in range(5):  # five hotkeys in one tempo: v1 would have rotated
        validator.process(validator.admit(at(start, hotkey=f"hk{n}"))["submission_id"])
    assert validator.store.pool()["version"] == 0
    late = validator.admit(at(start + EVERY, hotkey="hk9"))
    validator.process(late["submission_id"])
    pool = validator.store.pool()
    assert (pool["version"], pool["status"]) == (1, "OPEN")


def test_a_due_rotation_without_a_batch_keeps_scoring(
    tmp_path,
    refs,  # noqa: F811
    backend,  # noqa: F811
):
    validator = make(tmp_path, refs, backend, rule=V2, screening=3)
    start = 10 * TEMPO
    validator.process(validator.admit(at(start))["submission_id"])
    for n in range(2):
        late = validator.admit(at(start + EVERY + n * TEMPO, hotkey=f"late{n}"))
        assert validator.process(late["submission_id"])["state"] == "SCORED"
    assert validator.store.pool()["status"] == "OPEN"
    overdue = [e for e in validator.store.events() if e["kind"] == "rotation_overdue"]
    assert len(overdue) == 1


def test_a_root_committed_for_one_rule_never_runs_another(tmp_path):
    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin(PIN_G, rule_digest()))
    with pytest.raises(StateError) as refused:
        BatteryValidator(
            store=PoolStore(tmp_path / "state.sqlite3", rule=V2),
            backend=None,
            root=root,
            journal=journal,
            repository=REPOSITORY,
            require_commitment=False,
        )
    assert refused.value.code == "rule_mismatch"


def test_a_deployment_names_a_known_rule(tmp_path):
    from test_battery_validator_deployment import config

    path = config(tmp_path, rule="v3")
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == "evaluation_config_rule"
