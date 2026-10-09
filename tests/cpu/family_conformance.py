"""The reference family conformance kit (VALIDATOR-28 slice 4).

A family is reviewable when its conformance test passes: its own test module
calls `check_family` with its registration, its import-only validator, a
deployment writer and a scripted runner honouring the runner contract
(`RUNNER PLAN --out DIR ...`, one record per planned case). Motor's
(`test_challenge_validator_family_conformance.py`) is the reference.

What it proves, each on the family's own values:
1. a draw is deterministic by role, across processes on one custody, and
   another role draws another batch;
2. a case repeating a published case of the family is refused;
3. the solve resumes: a case whose first attempt is `FAILED_INFRA` is
   retried, never stored, and nothing solved is solved twice;
4. a reference record for other inputs, or for a case outside the batch, is
   refused;
5. a sealed, signed package is verified and imported by an import-only
   validator, and held on a second import;
6. a bank tranche is drawn by role, solved through the same runner, and
   sealed.

Scripted solves only: no container, chain, network or spend. Not a
scientific qualification of the family's population or references.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.batch_source import ProducerRefused
from carbon.challenge_validator.family_source import FamilySource


@dataclass(frozen=True)
class FamilyUnderTest:
    #: The family's registration (`ReferenceFamily`).
    family: Any
    #: `deployment(path, store=..., custody=None) -> path`: writes the family's
    #: owner-only deployment file.
    deployment: Callable[..., Any]
    #: `validator(tmp_path, name) -> adapter`: an import-only validator on its
    #: own store (`FamilyHiddenImport` mixed in).
    validator: Callable[..., Any]
    #: `runner(fail=()) -> callable`: a scripted runner; each case in `fail`
    #: answers `FAILED_INFRA` on its first attempt.
    runner: Callable[..., Any]
    #: The kind a screening draw uses.
    kind: str = "screening"


def _source(fut, tmp_path, runner=None):
    path = fut.deployment(
        tmp_path / "producer-etc" / "family.json",
        store=str(tmp_path / "producer-store"),
        custody=str(tmp_path / "producer-custody"),
    )
    if not (tmp_path / "producer-custody").exists():
        FamilySource.init_custody(fut.family, path)
    return FamilySource(
        fut.family, path, repository=pr.REPOSITORY, runner=runner or fut.runner()
    )


def check_determinism(fut, tmp_path):
    source = _source(fut, tmp_path)
    fingerprint = source.draw("pscreen-S1", kind=fut.kind)
    assert source.draw("pscreen-S1", kind=fut.kind) == fingerprint
    assert _source(fut, tmp_path).draw("pscreen-S1", kind=fut.kind) == fingerprint
    assert source.draw("pscreen-S2", kind=fut.kind) != fingerprint
    assert len(source.jobs(fingerprint)) == fut.family.batch_cases


def check_published_refusal(fut, tmp_path):
    source = _source(fut, tmp_path)
    document = source._document("pscreen-S1", fut.kind)
    source._published = {fut.family.overlap_key(document["cases"][0]["inputs"])}
    with pytest.raises(ProducerRefused) as refused:
        source.draw("pscreen-S1", kind=fut.kind)
    assert refused.value.code == "producer_published_case"
    assert source.custody.batches() == []


def check_resumable_solve(fut, tmp_path):
    first = _source(fut, tmp_path)
    fingerprint = first.draw("pscreen-S1", kind=fut.kind)
    flaky = sorted(job["case_id"] for job in first.jobs(fingerprint))[:1]
    source = _source(fut, tmp_path, fut.runner(fail=flaky))
    producer = pr.Producer(tmp_path / "producer", [source])
    producer.draw(fut.family.challenge_id, "pscreen-S1", kind=fut.kind)
    producer.solve(fut.family.challenge_id, fingerprint)
    assert producer.seal(fut.family.challenge_id, fingerprint)["state"] == "PENDING"
    assert source.store.pending(fingerprint) == flaky
    producer.solve(fut.family.challenge_id, fingerprint)
    sealed = producer.seal(fut.family.challenge_id, fingerprint)
    assert sealed["cases"] == fut.family.batch_cases
    assert producer.solve(fut.family.challenge_id, fingerprint) == {
        "returncode": 0,
        "solved": 0,
    }
    return source, fingerprint


def check_reference_refusals(fut, tmp_path):
    source = _source(fut, tmp_path)
    fingerprint = source.draw("pscreen-S1", kind=fut.kind)
    [job, *_] = source.jobs(fingerprint)
    record = {"case_id": job["case_id"], "status": fut.family.terminal[0]}
    foreign = {**record, "inputs": {**job["inputs"], "not_an_input": 1}}
    with pytest.raises(ProducerRefused) as refused:
        source.ingest(fingerprint, [foreign])
    assert refused.value.code == "producer_reference_malformed"
    with pytest.raises(ProducerRefused) as refused:
        source.ingest(fingerprint, [{**record, "case_id": "not-in-the-batch"}])
    assert refused.value.code == "producer_reference_case_not_in_batch"


def check_import(fut, tmp_path):
    source = _source(fut, tmp_path)
    key = ak.ProducerKey.create(tmp_path / "producer.key")
    producer = pr.Producer(tmp_path / "producer", [source], signing_key=key)
    challenge = fut.family.challenge_id
    drawn = producer.draw(challenge, "pscreen-S1", kind=fut.kind)
    producer.solve(challenge, drawn["fingerprint"])
    commitment = producer.seal(challenge, drawn["fingerprint"])
    producer.schedule(challenge, drawn["fingerprint"], 1, block=0)
    producer.publish(challenge, drawn["fingerprint"])
    outbox = tmp_path / "producer" / "outbox" / challenge
    adapter = fut.validator(tmp_path, "validator")
    result = ak.import_local(adapter, key.public_key, outbox)
    assert [p["state"] for p in result["packages"]] == ["IMPORTED"]
    again = ak.import_local(adapter, key.public_key, outbox)
    assert [p["state"] for p in again["packages"]] == ["HELD"]
    assert adapter.status()["evidence"] == adapter.hidden.evidence
    return commitment


def check_bank(fut, tmp_path):
    source = _source(fut, tmp_path)
    ledger = source.bank(tmp_path / "bank")
    drawn = ledger.draw_tranche("pool", 4)
    sealed = source.fill_tranche(ledger, drawn["tranche"], tmp_path / "bank-work")
    assert sealed["tranche"] == drawn["tranche"]
    assert [row["state"] for row in ledger.tranches("pool")] == ["SEALED"]


CHECKS = (
    check_determinism,
    check_published_refusal,
    check_resumable_solve,
    check_reference_refusals,
    check_import,
    check_bank,
)


def check_family(fut, tmp_path):
    """Every conformance check, each on its own directory."""
    for index, check in enumerate(CHECKS):
        directory = tmp_path / f"check-{index}"
        directory.mkdir()
        check(fut, directory)
