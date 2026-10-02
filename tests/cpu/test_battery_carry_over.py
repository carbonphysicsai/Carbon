"""Carrying a battery deployment over a contract revision (OWNER-BATTERY-CARRYOVER-01).

During testing the owner revises recipes and the construction contract while a
deployment runs, and incumbents stay winners across a revision. These tests
hold that:
- `PoolStore.rebind` carries over only the contract, implementation, backend
  and envelope, keeps every earlier identity, and refuses a changed rule;
- a recipe admitted under a recorded earlier contract is recompiled under the
  current one, and each recompile is recorded;
- a digest that matches no recorded identity is still `artifact_mismatch`;
- a carried recipe the current contract refuses is closed as
  `contract_revised` without stalling the queue behind it;
- a final whose incumbent the current contract refuses keeps the incumbent;
- `operate upgrade` rebinds a deployment in place.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import (
    Counting,
    make,
    refs,  # noqa: F401 - fixture
    run,
    submission,
)

from carbon.battery import exam
from carbon.battery.pool_store import StateError

OLD_CONTRACT = "sha256:" + "a" * 64


@pytest.fixture(scope="module")
def backend():
    return Counting(REPOSITORY)


def carry(validator):
    """Record an earlier identity this deployment was carried over from."""
    store = validator.store
    current = store.identities()
    store.rebind({**current, "contract_digest": OLD_CONTRACT}, decision="specimen")
    store.rebind(current, decision="specimen")
    return current


def admitted_under(validator, submission_id, contract, *, strategy=None):
    """Rewrite one admission as if it had been made under `contract`."""
    with validator.store.transaction() as db:
        binding, stored = db.execute(
            "SELECT binding, strategy FROM submissions WHERE submission_id=?",
            (submission_id,),
        ).fetchone()
        binding = json.loads(binding)
        binding["contract_digest"] = contract
        binding["recipe_digest"] = "sha256:" + "0" * 64
        db.execute(
            "UPDATE submissions SET binding=?, strategy=? WHERE submission_id=?",
            (
                json.dumps(binding),
                stored if strategy is None else json.dumps(strategy),
                submission_id,
            ),
        )


def test_a_rebind_carries_only_what_testing_revises(
    tmp_path,
    refs,  # noqa: F811
    backend,
):
    validator = make(tmp_path, refs, backend)
    store = validator.store
    current = store.identities()
    assert store.rebind(current, decision="specimen") == {"changed": []}
    assert store.identity_history() == []
    changed = store.rebind(
        {
            **current,
            "contract_digest": OLD_CONTRACT,
            "implementation_digest": "sha256:" + "b" * 64,
        },
        decision="specimen",
    )
    assert changed == {"changed": ["contract_digest", "implementation_digest"]}
    assert store.identity_history() == [current]
    (event,) = store.events("rebound")
    assert event["body"]["from"] == current and event["body"]["decision"] == "specimen"
    for fixed in ("rule_digest", "train_v1_sha256", "seed_pin", "challenge"):
        with pytest.raises(StateError) as refused:
            store.rebind({**current, fixed: "changed"}, decision="specimen")
        assert refused.value.code == "identities_not_carryable"


def test_a_carried_recipe_is_recompiled_and_scored(
    tmp_path,
    refs,  # noqa: F811
    backend,
):
    validator = make(tmp_path, refs, backend)
    carry(validator)
    admitted = validator.admit(submission("hk1", neighbours=4))
    admitted_under(validator, admitted["submission_id"], OLD_CONTRACT)
    outcome = validator.process(admitted["submission_id"])
    assert outcome["state"] == "SCORED"
    (recompiled,) = validator.store.events("recompiled")
    assert recompiled["body"]["submission_id"] == admitted["submission_id"]
    assert recompiled["body"]["from"] == "sha256:" + "0" * 64


def test_an_unrecorded_digest_is_still_a_mismatch(
    tmp_path,
    refs,  # noqa: F811
    backend,
):
    validator = make(tmp_path, refs, backend)
    carry(validator)
    admitted = validator.admit(submission("hk1", neighbours=4))
    admitted_under(validator, admitted["submission_id"], "sha256:" + "c" * 64)
    with pytest.raises(StateError) as mismatch:
        validator.process(admitted["submission_id"])
    assert mismatch.value.code == "artifact_mismatch"
    assert validator.store.events("recompiled") == []


def test_a_carried_recipe_the_contract_refuses_does_not_stall_the_queue(
    tmp_path,
    refs,  # noqa: F811
    backend,
):
    validator = make(tmp_path, refs, backend)
    carry(validator)
    first = validator.admit(submission("hk1", neighbours=4))["submission_id"]
    second = validator.admit(submission("hk2", neighbours=6))["submission_id"]
    refused = {**submission("hk1").strategy, "parameters": {"no_such_field": 1}}
    admitted_under(validator, first, OLD_CONTRACT, strategy=refused)
    validator.run_pending()
    closed = validator.outcome(first)
    assert closed["state"] == "INVALID_CONSTRUCTION"
    assert closed["failure"]["code"] == "contract_revised"
    assert validator.outcome(second)["state"] == "SCORED"


def test_a_final_keeps_an_incumbent_the_current_contract_refuses(
    tmp_path,
    refs,  # noqa: F811
    backend,
):
    validator = make(tmp_path, refs, backend)
    incumbent = run(validator, submission("hk0", neighbours=8))["submission_id"]
    nominee = run(
        validator, submission("hk1", backbone="mlp", steps=3000, width=64, depth=3)
    )
    assert nominee["nominated"] is True
    (final_id,) = validator.store.open_finals()
    carry(validator)
    refused = {**submission("hk0").strategy, "parameters": {"no_such_field": 1}}
    admitted_under(validator, incumbent, OLD_CONTRACT, strategy=refused)
    decided = validator.process_final(final_id)
    assert decided["outcome"]["outcome"] == exam.INSUFFICIENT
    assert decided["outcome"]["reason"] == "incumbent contract_revised"
    assert decided["outcome"]["promotable"] is False
    assert validator.store.incumbent()["model_id"] == incumbent


def test_operate_upgrade_rebinds_a_deployment_in_place(tmp_path, monkeypatch):
    from test_battery_validator_deployment import config

    from carbon.battery import daemon, deployment, operate

    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    path = config(tmp_path)
    deployment.validator(path, repository=REPOSITORY)  # binds the identities
    real = daemon.BatteryValidator.identities

    def revised(self):
        return {**real(self), "implementation_digest": "sha256:" + "d" * 64}

    monkeypatch.setattr(daemon.BatteryValidator, "identities", revised)
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.validator(path, repository=REPOSITORY)
    assert refused.value.code == "evaluation_identities_changed"
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    result = operate.upgrade(path)
    assert result == {
        "changed": ["implementation_digest"],
        "decision": "OWNER-BATTERY-CARRYOVER-01",
    }
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    started = deployment.validator(path, repository=REPOSITORY)
    assert started.store.identities()["implementation_digest"] == "sha256:" + "d" * 64

    def other_rule(self):
        return {**real(self), "rule_digest": "sha256:" + "e" * 64}

    monkeypatch.setattr(daemon.BatteryValidator, "identities", other_rule)
    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    with pytest.raises(deployment.EvaluationUnavailable) as fixed:
        operate.upgrade(path)
    assert fixed.value.code == "upgrade_identities_not_carryable"
