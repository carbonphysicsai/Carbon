"""The battery evaluation deployment fails closed, and never scores a failure."""

import json
from pathlib import Path

import pytest

from carbon.battery import evaluation, seeds, shadow
from carbon.battery.challenge import INPUTS
from carbon.reconstruction import capability_registry as registry

REPOSITORY = Path(__file__).resolve().parents[2]
EVIDENCE = REPOSITORY / "docs/development/evidence/exam-design-2026-09-24"
BATTERY = registry.BATTERY_CHALLENGE
KNN = {
    "schema_version": "1.0",
    "challenge_id": BATTERY,
    "backbone": "knn",
    "parameters": {"neighbours": 5},
}


@pytest.fixture(scope="module")
def refs():
    found = {}
    lines = (EVIDENCE / "refs-b/out/battery_refs/records.jsonl").read_text()
    for line in lines.splitlines():
        record = json.loads(line)
        if not record.get("refined") and record["case_id"].startswith("pscreen-"):
            found[record["case_id"]] = record
    return found


def _write(path, value):
    path.write_text(value if type(value) is str else json.dumps(value))
    path.chmod(0o600)


def _batch(refs, role):
    ids = sorted(c for c in refs if c.startswith(role + "-"))[:98]
    cases = [(c, tuple(sorted((k, refs[c]["inputs"][k]) for k in INPUTS))) for c in ids]
    repeats = [(f"{role}-r{j}", ids[j * 40]) for j in range(2)]
    inputs = dict(cases)
    cases += [(d, inputs[o]) for d, o in repeats]
    return seeds.PrivateBatch(role, tuple(cases), tuple(repeats))


def deployment(tmp_path, refs, *, commit=4, batches=4, drop_reference=None):
    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin("sha256:g", "sha256:s"))
    made = [_batch(refs, f"pscreen-B0{b}") for b in range(batches)]
    for batch in made[:commit]:
        journal.commit(batch, pool_version=0)
    _write(tmp_path / "batches.json", [b.document() for b in made])
    kept = {k: v for k, v in refs.items() if k != drop_reference}
    _write(
        tmp_path / "references.jsonl",
        "".join(json.dumps(r) + "\n" for r in kept.values()),
    )
    config = {
        "schema": evaluation.SCHEMA,
        "private_root": str(tmp_path / "root.bin"),
        "journal": str(tmp_path / "journal.jsonl"),
        "batches": str(tmp_path / "batches.json"),
        "references": str(tmp_path / "references.jsonl"),
        "results": str(tmp_path / "results.jsonl"),
    }
    _write(tmp_path / "deployment.json", config)
    return tmp_path / "deployment.json"


def load(path):
    return evaluation.EvaluationDeployment.load(path, repository=REPOSITORY)


def test_an_uncommitted_batch_is_never_scored(tmp_path, refs):
    path = deployment(tmp_path, refs, commit=3)
    with pytest.raises(evaluation.EvaluationUnavailable) as refused:
        load(path)
    assert refused.value.code == "evaluation_batch_uncommitted"


def test_a_missing_reference_stops_the_load(tmp_path, refs):
    missing = min(c for c in refs if c.startswith("pscreen-B01-"))
    path = deployment(tmp_path, refs, drop_reference=missing)
    with pytest.raises(evaluation.EvaluationUnavailable) as refused:
        load(path)
    assert refused.value.code == "evaluation_references_incomplete"


def test_inputs_must_be_owner_only(tmp_path, refs):
    path = deployment(tmp_path, refs)
    (tmp_path / "references.jsonl").chmod(0o644)
    with pytest.raises(evaluation.EvaluationUnavailable) as refused:
        load(path)
    assert refused.value.code == "evaluation_input_not_owner_only"


def test_outcomes_are_typed_and_only_a_score_is_scored(tmp_path, refs, monkeypatch):
    target = load(deployment(tmp_path, refs))
    refused = target.evaluate("s-refused", dict(KNN, backbone="fno"), None)
    assert refused["status"] == "REFUSED" and refused["scored"] is False
    assert refused["issues"][0]["code"] == "backbone.not_rebuildable"

    def broken(*args, **kwargs):
        raise RuntimeError("worker lost")

    with monkeypatch.context() as patch:
        patch.setattr(shadow, "rebuild", broken)
        failed = target.evaluate("s-infra", KNN, registry.contract_digest(BATTERY))
    assert failed == {
        "schema": evaluation.RESULT_SCHEMA,
        "challenge": {"id": BATTERY, "version": "1.0"},
        "submission_id": "s-infra",
        "status": "FAILED_INFRA",
        "scored": False,
        "retryable": True,
    }
    assert target.pool.pool.history == []  # neither outcome entered the pool
    scored = target.evaluate("s-ok", KNN, registry.contract_digest(BATTERY))
    assert scored["status"] == "SCORED"
    assert scored["result"]["reconstruction"]["validator_path"] is False
    log = [json.loads(x) for x in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert [x["status"] for x in log] == ["REFUSED", "FAILED_INFRA", "SCORED"]
    assert (tmp_path / "results.jsonl").stat().st_mode & 0o077 == 0


def test_retired_batches_stay_retired_after_a_restart(tmp_path, refs):
    path = deployment(tmp_path, refs)
    target = load(path)
    for i in range(3):  # OD-2: rotate after three admitted submissions
        target.evaluate(f"s{i}", KNN, registry.contract_digest(BATTERY))
    retired = seeds.SeedJournal(tmp_path / "journal.jsonl").retired()
    assert len(retired) == 1
    reloaded = load(path)
    assert not {c.fingerprint for c in reloaded.pool.committed} & retired
