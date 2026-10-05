"""Cooling's registered candidate-fault classification and lifecycle record."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from carbon.challenge_validator import candidate_fault


def _policy_dir(tmp_path):
    target = tmp_path / "policies"
    shutil.copytree(candidate_fault.POLICY_DIR, target)
    return target


def _write(path, document):
    Path(path).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _register(directory, document, *, challenge="chip-cold-plate"):
    version = document["version"]
    _write(directory / f"{version}.json", document)
    registry = json.loads((directory / "registry.json").read_text(encoding="utf-8"))
    section = registry["candidate_faults"]
    section["versions"][version] = candidate_fault._digest(document)
    section["current_by_challenge"][challenge] = version
    _write(directory / "registry.json", registry)


def _v1():
    return json.loads(
        (
            candidate_fault.POLICY_DIR / "cooling-candidate-fault-v1.json"
        ).read_text(encoding="utf-8")
    )


def test_current_cooling_policy_is_registered_pinned_and_complete():
    policy = candidate_fault.load_policy("chip-cold-plate")
    assert policy.version == "cooling-candidate-fault-v1"
    assert policy.faults == candidate_fault.FAULTS
    assert policy.classification == {
        "kind": "FAILED_INFRA",
        "code": "adapter_failure",
        "scientific_result": False,
        "candidate_penalty": False,
    }
    record = policy.record("predict_exception")
    assert record["fault"] == "predict_exception"
    assert record["retry"] == {
        "owner": "registered_submission_lifecycle",
        "validator_performs": False,
        "eligibility": "subject_to_registered_attempt_budget",
        "new_charge": False,
        "retry_credit": False,
    }
    assert record["refund"] == {
        "owner": "registered_fee_service",
        "validator_performs": False,
        "charged_terminal": "full_remaining_balance_refund",
        "uncharged_terminal": "no_fee_event",
    }
    assert policy.digest.startswith("sha256:")


def test_altered_or_unregistered_policy_fails_closed(tmp_path):
    directory = _policy_dir(tmp_path)
    document = _v1()
    document["notes"].append("altered after registration")
    _write(directory / "cooling-candidate-fault-v1.json", document)
    with pytest.raises(candidate_fault.CandidateFaultPolicyRefused, match="altered"):
        candidate_fault.load_policy("chip-cold-plate", directory=directory)
    with pytest.raises(candidate_fault.CandidateFaultPolicyRefused, match="registered"):
        candidate_fault.load_policy(
            "chip-cold-plate", "cooling-candidate-fault-v9", directory=directory
        )


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["classification"].update(kind="SCORED"),
        lambda d: d["classification"].update(scientific_result=True),
        lambda d: d["classification"].update(candidate_penalty=True),
        lambda d: d["retry"].update(validator_performs=True),
        lambda d: d["retry"].update(new_charge=True),
        lambda d: d["refund"].update(validator_performs=True),
        lambda d: d["faults"].remove("non_finite_score"),
    ],
)
def test_a_digest_pinned_but_unsafe_policy_is_refused(tmp_path, change):
    directory = _policy_dir(tmp_path)
    document = _v1()
    document["version"] = "cooling-candidate-fault-unsafe"
    change(document)
    _register(directory, document)
    with pytest.raises(candidate_fault.CandidateFaultPolicyRefused):
        candidate_fault.load_policy("chip-cold-plate", directory=directory)


def test_cross_challenge_policy_is_refused_even_when_registered(tmp_path):
    directory = _policy_dir(tmp_path)
    document = _v1()
    document["version"] = "cooling-candidate-fault-wrong-challenge"
    _register(directory, document, challenge="electric-motor-magnetics")
    with pytest.raises(
        candidate_fault.CandidateFaultPolicyRefused, match="another challenge"
    ):
        candidate_fault.load_policy(
            "electric-motor-magnetics", directory=directory
        )


def test_a_safe_successor_is_selected_by_registry_data_without_code_edit(tmp_path):
    directory = _policy_dir(tmp_path)
    document = copy.deepcopy(_v1())
    document["version"] = "cooling-candidate-fault-test-v2"
    document["authority"] = "synthetic test authority"
    document["notes"].append("A test-only successor with unchanged safe semantics.")
    _register(directory, document)
    policy = candidate_fault.load_policy("chip-cold-plate", directory=directory)
    assert policy.version == "cooling-candidate-fault-test-v2"
    assert policy.digest == candidate_fault._digest(document)
