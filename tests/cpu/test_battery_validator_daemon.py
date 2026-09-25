"""The battery validator daemon (M3): durable, replay-safe, and exact to OD-2.

The fixtures use real PyBaMM references retained by the exam-design campaign:
- the private screening batches `pscreen-B00` to `pscreen-B04`;
- the fresh finalist set `pfinal`.

Those cases are published development examples. A deployed validator refuses
them (`PublishedCaseRefused`), so these fixtures opt in explicitly.

The backend here is `DirectBackend`, which runs in this process. It exercises
control flow, durability and the exam semantics. It does not establish
container isolation (see `tests/service/test_battery_validator_containers.py`),
truth solves or GPU execution.
"""

import json
from pathlib import Path
from typing import ClassVar

import pytest

from carbon.battery import exam, seeds, signing
from carbon.battery.challenge import INPUTS
from carbon.battery.daemon import (
    AuthenticatedSubmission,
    BatteryValidator,
    CommitmentRequired,
    PublishedCaseRefused,
    commitment_digest,
    rule_digest,
)
from carbon.battery.pool_store import PoolStore, StateError
from carbon.battery.worker import DirectBackend, WorkerFailure
from carbon.reconstruction import capability_registry as registry

REPOSITORY = Path(__file__).resolve().parents[2]
EVIDENCE = REPOSITORY / "docs/development/evidence/exam-design-2026-09-24"
BATTERY = registry.BATTERY_CHALLENGE
DIGEST = registry.contract_digest(BATTERY)
#: Tagged digests standing in for the truth-image and exam identities.
PIN_G, PIN_S = "sha256:" + "1" * 64, "sha256:" + "2" * 64


@pytest.fixture(scope="module")
def refs():
    found = {}
    lines = (EVIDENCE / "refs-b/out/battery_refs/records.jsonl").read_text()
    for line in lines.splitlines():
        record = json.loads(line)
        if not record.get("refined"):
            found[record["case_id"]] = record
    return found


def batch(refs, role, n=98, prefix=None):
    ids = sorted(c for c in refs if c.startswith((prefix or role) + "-"))[:n]
    cases = [(c, tuple(sorted((k, refs[c]["inputs"][k]) for k in INPUTS))) for c in ids]
    repeats = [(f"{role}-r{j}", ids[j * 40]) for j in range(2)]
    inputs = dict(cases)
    cases += [(d, inputs[o]) for d, o in repeats]
    return seeds.PrivateBatch(role, tuple(cases), tuple(repeats))


class Counting(DirectBackend):
    """DirectBackend that counts calls and can be told to fail."""

    fail = None  # (kind, candidate) to raise once

    def reconstruct(self, identity, recipe, seed):
        if self.fail and self.fail[0] == "reconstruct":
            _, candidate = self.fail
            self.fail = None
            raise WorkerFailure("injected", candidate=candidate)
        return super().reconstruct(identity, recipe, seed)

    def infer(self, identity, state, inputs):
        if self.fail and self.fail[0] == "infer":
            _, candidate = self.fail
            self.fail = None
            raise WorkerFailure("injected", candidate=candidate)
        return super().infer(identity, state, inputs)


@pytest.fixture(scope="module")
def backend():
    return Counting(REPOSITORY)


def make(
    tmp_path, refs, backend, *, screening=4, finalist=True, open_pool=True, **kwargs
):
    tmp_path.chmod(0o700)
    root_path = tmp_path / "root.bin"
    root = (
        seeds.PrivateRoot.load(root_path)
        if root_path.exists()
        else seeds.PrivateRoot.create(root_path)
    )
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    if not journal.path.exists():
        journal.commit_root(root, seeds.seed_pin(PIN_G, PIN_S))
    validator = BatteryValidator(
        store=PoolStore(tmp_path / "state.sqlite3"),
        backend=backend,
        root=root,
        journal=journal,
        repository=REPOSITORY,
        require_commitment=kwargs.pop("require_commitment", False),
        allow_published_cases=True,
        **kwargs,
    )
    validator.start()
    if validator.store.pool() is None:
        for b in range(screening):
            fp = validator.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
            validator.ingest_references(fp, list(refs.values()))
        if finalist:
            fp = validator.import_batch(batch(refs, "pfinal", 198), kind="finalist")
            validator.ingest_references(fp, list(refs.values()))
        if open_pool:
            validator.open_pool()
    return validator


def submission(hotkey, backbone="knn", challenge=BATTERY, digest=DIGEST, **parameters):
    return AuthenticatedSubmission(
        hotkey,
        {"sequence": 1, "digest": "0" * 64},
        challenge,
        "1.0",
        {
            "schema_version": "1.0",
            "challenge_id": challenge,
            "backbone": backbone,
            "parameters": parameters or {"neighbours": 8},
        },
        digest,
    )


def run(validator, sub):
    admitted = validator.admit(sub)
    return validator.process(admitted["submission_id"])


def test_screening_covers_the_whole_active_pool_and_binds_identities(
    tmp_path, refs, backend
):
    validator = make(tmp_path, refs, backend)
    outcome = run(validator, submission("hk1"))
    assert outcome["state"] == "SCORED"
    score = validator.store.score(outcome["submission_id"])
    record = score["record"]
    # Three active batches of 100: gates and score over all 300 cases.
    assert record["n_cases"] == 300 == 3 * exam.DEVELOPMENT_RULE["screening_batch_size"]
    assert len(record["active_batches"]) == exam.DEVELOPMENT_RULE["active_batches"]
    assert set(record["references"]) == set(record["active_batches"])
    assert all(v.startswith("sha256:") for v in record["references"].values())
    assert record["rule_digest"] == rule_digest()
    binding = validator.store.submission(outcome["submission_id"])["binding"]
    for key in (
        "train_v1_sha256",
        "ocv_table_sha256",
        "contract_digest",
        "implementation_digest",
        "recipe_digest",
        "calibration_sha256",
    ):
        assert binding[key]
    assert binding["backend"] == {
        "backend": "DIRECT_TRUSTED_PROCESS",
        "validator_path": False,
    }


def test_duplicate_admission_and_replay_count_once(tmp_path, refs, backend):
    validator = make(tmp_path, refs, backend)
    first = run(validator, submission("hk1"))
    again = validator.admit(
        AuthenticatedSubmission(
            "hk1",
            {"sequence": 99, "digest": "f" * 64},
            BATTERY,
            "1.0",
            submission("hk1").strategy,
            DIGEST,
        )
    )
    assert again["submission_id"] == first["submission_id"]
    before = dict(backend.calls)
    validator.process(first["submission_id"])
    validator.run_pending()
    assert backend.calls == before  # nothing rebuilt or re-inferred
    assert validator.store.pool()["admitted"] == 1
    assert len(validator.store.events("scored")) == 1


def test_restart_between_reconstruction_and_score(tmp_path, refs, backend, monkeypatch):
    validator = make(tmp_path, refs, backend)
    admitted = validator.admit(submission("hk1"))
    sid = admitted["submission_id"]

    def crash(*args, **kwargs):
        raise RuntimeError("process killed")

    with monkeypatch.context() as patch:
        patch.setattr(validator.store, "record_score", crash)
        with pytest.raises(RuntimeError):
            validator.process(sid)
    assert validator.store.submission(sid)["state"] == "RECONSTRUCTED"
    rebuilt = backend.calls["reconstruct"]
    restarted = make(tmp_path, refs, backend)
    assert restarted.process(sid)["state"] == "SCORED"
    assert backend.calls["reconstruct"] == rebuilt  # the retained model is reused
    assert restarted.store.pool()["admitted"] == 1


def test_rotation_is_durable_across_restart(tmp_path, refs, backend):
    validator = make(tmp_path, refs, backend)
    for i, k in enumerate((8, 6, 4)):
        run(validator, submission(f"hk{i}", neighbours=k))
    pool = validator.store.pool()
    assert (pool["version"], pool["admitted"]) == (1, 0)
    retired = validator.store.batches(kind="screening", state="RETIRED")
    assert len(retired) == 1
    assert retired[0]["fingerprint"] in validator.journal.retired()
    restarted = make(tmp_path, refs, backend)
    restarted.recover()
    retire_entries = [e for e in restarted.journal.public() if e["kind"] == "retire"]
    assert len(retire_entries) == 1  # never retired twice
    outcome = run(restarted, submission("hk9", neighbours=3))
    assert outcome["screening"]["pool_version"] == 1


def test_retained_models_are_inferred_not_retrained_after_rotation(
    tmp_path, refs, backend
):
    validator = make(tmp_path, refs, backend)
    run(validator, submission("hk0", neighbours=8))  # becomes the incumbent
    incumbent = validator.store.incumbent()["model_id"]
    for i, k in enumerate((6, 4)):
        run(validator, submission(f"hk{i + 1}", neighbours=k))
    assert validator.store.pool()["version"] == 1
    rebuilt = backend.calls["reconstruct"]
    run(validator, submission("hk5", neighbours=3))
    # One rebuild, for the new submission; the incumbent is only inferred.
    assert backend.calls["reconstruct"] == rebuilt + 1
    ids = validator.store.active_case_ids()
    assert len(validator.store.predictions(incumbent, ids)) == 300


def test_exhausted_pool_waits_instead_of_scoring(tmp_path, refs, backend):
    validator = make(tmp_path, refs, backend, screening=3)
    for i, k in enumerate((8, 6, 4)):
        run(validator, submission(f"hk{i}", neighbours=k))
    assert validator.store.pool()["status"] == "ROTATION_PENDING"
    waiting = run(validator, submission("hk7", neighbours=5))
    assert waiting["state"] == "ADMITTED" and waiting["waiting"] == "ROTATION_PENDING"
    assert "screening" not in waiting
    fp = validator.import_batch(batch(refs, "pscreen-B04"), kind="screening")
    validator.ingest_references(fp, list(refs.values()))
    validator.store.rotate_if_ready()
    scored = validator.process(waiting["submission_id"])
    assert scored["screening"]["pool_version"] == 1


def test_incomplete_references_never_open_a_pool(tmp_path, refs, backend):
    validator = make(
        tmp_path, refs, backend, open_pool=False, screening=0, finalist=False
    )
    fps = [
        validator.import_batch(batch(refs, f"pscreen-B0{b}"), kind="screening")
        for b in range(3)
    ]
    partial = [r for r in refs.values() if not r["case_id"].startswith("pscreen-B02")]
    infra = [
        dict(r, status="FAILED_INFRA")
        for r in refs.values()
        if r["case_id"].startswith("pscreen-B02")
    ]
    for fp in fps:
        validator.ingest_references(fp, partial + infra)
    with pytest.raises(StateError) as refused:
        validator.open_pool()
    assert refused.value.code == "pool_incomplete"
    # FAILED_INFRA is never stored as a reference: the batch stays pending.
    assert validator.store.batch(fps[2])["references_state"] == "PENDING"


def test_a_reference_failure_is_withdrawn_for_every_model(tmp_path, refs, backend):
    failed = next(c for c in sorted(refs) if c.startswith("pscreen-B01-"))
    altered = {**refs, failed: dict(refs[failed], status="REFERENCE_SOLVER_FAILED")}
    validator = make(tmp_path, altered, backend)
    a = validator.store.score(run(validator, submission("hk1"))["submission_id"])
    b = validator.store.score(
        run(validator, submission("hk2", neighbours=3))["submission_id"]
    )
    for score in (a, b):
        assert score["record"]["n_reference_invalid"] >= 1
        assert "schema_finite" not in score["record"]["gate_failures"]
    assert a["record"]["n_reference_invalid"] == b["record"]["n_reference_invalid"]


def test_infrastructure_failure_is_retried_never_scored(tmp_path, refs, backend):
    validator = make(tmp_path, refs, backend)
    backend.fail = ("reconstruct", False)
    outcome = run(validator, submission("hk1"))
    assert outcome["state"] == "FAILED_INFRA" and "screening" not in outcome
    assert validator.store.pool()["admitted"] == 0
    retried = validator.process(outcome["submission_id"])
    assert retried["state"] == "SCORED"
    assert (
        validator.store.submission(outcome["submission_id"])["binding"]["attempt"] == 1
    )


def test_candidate_failures_are_distinct_and_terminal(tmp_path, refs, backend):
    validator = make(tmp_path, refs, backend)
    backend.fail = ("reconstruct", True)
    built = run(validator, submission("hk1"))
    assert built["state"] == "RECONSTRUCTION_FAILED"
    backend.fail = ("infer", True)
    predicted = run(validator, submission("hk2", neighbours=3))
    assert predicted["state"] == "RECONSTRUCTION_FAILED"
    assert validator.store.pool()["admitted"] == 0
    assert validator.process(built["submission_id"])["state"] == "RECONSTRUCTION_FAILED"


def test_incumbent_inference_failure_is_not_charged_to_the_challenger(
    tmp_path, refs, backend
):
    validator = make(tmp_path, refs, backend)
    for i, k in enumerate((8, 6, 4)):
        run(validator, submission(f"hk{i}", neighbours=k))  # rotates to version 1
    admitted = validator.admit(submission("hk5", neighbours=3))

    real = backend.infer
    calls = {"n": 0}

    def fail_second(identity, state, inputs):
        calls["n"] += 1
        if identity.startswith("inf-" + validator.store.incumbent()["model_id"]):
            raise WorkerFailure("injected", candidate=True)
        return real(identity, state, inputs)

    backend.infer = fail_second
    try:
        outcome = validator.process(admitted["submission_id"])
    finally:
        del backend.infer
    assert outcome["state"] == "FAILED_INFRA"
    assert outcome["failure"]["code"].startswith("incumbent_inference")


def test_contract_artifact_and_cross_challenge_mismatches_are_refused(
    tmp_path, refs, backend
):
    validator = make(tmp_path, refs, backend)
    wrong_digest = run(
        validator,
        submission("hk1", digest=registry.contract_digest(registry.BURGERS_CHALLENGE)),
    )
    assert wrong_digest["state"] == "INVALID_CONSTRUCTION"
    assert wrong_digest["failure"]["code"] == "contract_refused"
    burgers = run(
        validator,
        submission(
            "hk2", backbone="fno", challenge=registry.BURGERS_CHALLENGE, steps=64
        ),
    )
    assert burgers["state"] == "INVALID_CONSTRUCTION"
    reserved = validator.admit(
        AuthenticatedSubmission("hk3", {}, "photonic-coupler", None, {}, DIGEST)
    )
    assert reserved["failure"]["code"] == "challenge_not_implemented"
    foreign = validator.admit(
        AuthenticatedSubmission(
            "hk4",
            {},
            BATTERY,
            "1.0",
            {**submission("hk4").strategy, "challenge_id": registry.BURGERS_CHALLENGE},
            DIGEST,
        )
    )
    assert foreign["failure"]["code"] == "cross_challenge_submission"
    assert validator.store.pool()["admitted"] == 0
    # An admitted recipe whose rebuild would differ is never built silently.
    admitted = validator.admit(submission("hk5", neighbours=4))
    with validator.store.transaction() as db:
        row = db.execute(
            "SELECT binding FROM submissions WHERE submission_id=?",
            (admitted["submission_id"],),
        ).fetchone()
        binding = json.loads(row[0])
        binding["recipe_digest"] = "sha256:" + "0" * 64
        db.execute(
            "UPDATE submissions SET binding=? WHERE submission_id=?",
            (json.dumps(binding), admitted["submission_id"]),
        )
    with pytest.raises(StateError) as mismatch:
        validator.process(admitted["submission_id"])
    assert mismatch.value.code == "artifact_mismatch"


def test_changed_identities_are_refused_on_restart(tmp_path, refs, backend):
    make(tmp_path, refs, backend)

    class Other(Counting):
        identity: ClassVar[dict] = {
            "backend": "ISOLATED_CARRIER",
            "validator_path": True,
        }

    with pytest.raises(StateError) as refused:
        make(tmp_path, refs, Other(REPOSITORY))
    assert refused.value.code == "identities_changed"


def test_commitments_are_required_when_configured(tmp_path, refs, backend):
    class Chain:
        def __init__(self):
            self.values = {}

        def read(self, hotkey):
            return self.values.get(hotkey)

    chain = Chain()
    validator = make(
        tmp_path, refs, backend, require_commitment=True, commitments=chain
    )
    sub = submission("hk1")
    with pytest.raises(CommitmentRequired):
        validator.admit(sub)
    from carbon.battery.compile import compile_recipe

    _, recipe = compile_recipe(sub.strategy)
    chain.values["hk1"] = {
        "digest": commitment_digest(BATTERY, DIGEST, recipe.strategy_hash),
        "block": 123,
    }
    admitted = validator.admit(sub)
    binding = validator.store.submission(admitted["submission_id"])["binding"]
    assert binding["commitment"]["block"] == 123


def test_outcomes_disclose_no_private_case_label_or_seed(tmp_path, refs, backend):
    validator = make(tmp_path, refs, backend)
    outcomes = [
        run(validator, submission(f"hk{i}", neighbours=k)) for i, k in enumerate((8, 2))
    ]
    text = json.dumps(outcomes)
    for fingerprint in [b["fingerprint"] for b in validator.store.batches()]:
        for case in validator.store.batch(fingerprint)["document"]["cases"]:
            assert case["case_id"] not in text
        assert fingerprint not in text
    for forbidden in (
        "seed",
        "duplicate",
        "voltage_v",
        "references",
        "pscreen",
        "pfinal",
        "root",
    ):
        assert forbidden not in text
    key = signing.ServiceKey.create(tmp_path / "service.key")
    validator.service_key = key
    signed = validator.signed_outcome(outcomes[0]["submission_id"])
    assert signing.verify(signed)
    signed["payload"]["state"] = "tampered"
    assert not signing.verify(signed)
    assert "<redacted>" in repr(key)
    with pytest.raises(PermissionError):
        signing.winner_intent()
    intent = key.sign(
        "weight_intent", signing.all_burn_intent(pool_version=0, reason="phase A")
    )
    assert intent["payload"]["mode"] == "ALL_BURN" and signing.verify(intent)


def test_published_campaign_cases_cannot_be_hidden_cases(tmp_path, refs, backend):
    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin(PIN_G, PIN_S))
    deployed = BatteryValidator(
        store=PoolStore(tmp_path / "state.sqlite3"),
        backend=backend,
        root=root,
        journal=journal,
        repository=REPOSITORY,
    )
    with pytest.raises(PublishedCaseRefused):
        deployed.import_batch(batch(refs, "pscreen-B00"), kind="screening")
    fresh = deployed.prepare_batch("screen-000", kind="screening")
    assert deployed.store.batch(fresh)["state"] == "PREPARED"
    assert len(deployed.reference_jobs(fresh)) == 98  # duplicates reuse a solve
    assert deployed.prepare_batch("screen-000", kind="screening") == fresh


def test_finalist_comparison_is_frozen_fresh_and_honest(tmp_path, refs, backend):
    validator = make(tmp_path, refs, backend)
    run(validator, submission("hk0", neighbours=8))  # incumbent
    nominee = run(
        validator, submission("hk1", backbone="mlp", steps=3000, width=64, depth=3)
    )
    assert nominee["nominated"] is True
    (final_id,) = validator.store.open_finals()
    frozen = validator.store.final(final_id)["frozen"]
    assert (
        frozen["rule"]["equivalence_margin"]
        == exam.DEVELOPMENT_RULE["equivalence_margin_rel"]
    )
    decided = validator.process_final(final_id)
    events = [e["kind"] for e in validator.store.events()]
    assert events.index("final_frozen") < events.index("finalist_assigned")
    assert decided["outcome"]["outcome"] in {
        exam.IMPROVEMENT,
        exam.REGRESSION,
        exam.TRADE_OFF,
        exam.NO_IMPROVEMENT,
        exam.INSUFFICIENT,
    }
    assert (validator.store.incumbent()["model_id"] == nominee["submission_id"]) == (
        decided["outcome"]["promotable"]
    )
    finalist = validator.store.batch(decided["finalist"])
    assert finalist["state"] == "CONSUMED"
    validator.recover()
    assert decided["finalist"] in validator.journal.retired()
    # The fresh cases never reach a miner-visible outcome.
    shown = json.dumps(validator.outcome(nominee["submission_id"]))
    for case in finalist["document"]["cases"]:
        assert case["case_id"] not in shown
    # Replaying the decided final changes nothing.
    assert validator.process_final(final_id)["outcome"] == decided["outcome"]


def test_a_final_without_a_prepared_set_waits(tmp_path, refs, backend):
    validator = make(tmp_path, refs, backend, finalist=False)
    run(validator, submission("hk0", neighbours=8))
    run(validator, submission("hk1", backbone="mlp", steps=3000, width=64, depth=3))
    (final_id,) = validator.store.open_finals()
    assert validator.process_final(final_id)["status"] == "WAITING_FOR_FINALIST_SET"
    assert validator.store.incumbent()["model_id"] != final_id


def test_restart_after_admission_before_any_work(tmp_path, refs, backend):
    validator = make(tmp_path, refs, backend)
    sid = validator.admit(submission("hk1"))["submission_id"]
    # The process dies here: admitted, nothing built.
    restarted = make(tmp_path, refs, backend)
    assert restarted.store.submission(sid)["state"] == "ADMITTED"
    assert [r["state"] for r in restarted.run_pending()] == ["SCORED"]
    assert restarted.store.pool()["admitted"] == 1


def test_restart_between_rotation_and_journal_retirement(
    tmp_path, refs, backend, monkeypatch
):
    validator = make(tmp_path, refs, backend)
    run(validator, submission("hk0", neighbours=8))
    run(validator, submission("hk1", neighbours=6))

    def crash(*args, **kwargs):
        raise RuntimeError("process killed")

    with monkeypatch.context() as patch:
        # The third admission rotates the pool; the process dies before the
        # journal records the retirement.
        patch.setattr(validator.store, "settle_retirements", crash)
        with pytest.raises(RuntimeError):
            run(validator, submission("hk2", neighbours=4))
    assert validator.store.pool()["version"] == 1
    assert not validator.journal.retired()
    restarted = make(tmp_path, refs, backend)  # start() settles it
    retired = restarted.store.batches(kind="screening", state="RETIRED")
    assert [b["fingerprint"] for b in retired] == list(restarted.journal.retired())
    restarted.recover()
    entries = [e for e in restarted.journal.public() if e["kind"] == "retire"]
    assert len(entries) == 1  # never retired twice


def test_a_final_retries_infrastructure_under_a_new_attempt(
    tmp_path, refs, backend, monkeypatch
):
    validator = make(tmp_path, refs, backend)
    run(validator, submission("hk0", neighbours=8))
    nominee = run(
        validator, submission("hk1", backbone="mlp", steps=3000, width=64, depth=3)
    )
    assert nominee["nominated"] is True
    (final_id,) = validator.store.open_finals()
    backend.fail = ("reconstruct", False)
    failed = validator.process_final(final_id)
    assert failed["status"] == "FAILED_INFRA"
    assert validator.store.final(final_id)["state"] == "FROZEN"  # never a result
    assert validator.store.final_attempt(final_id) == 1
    claimed = validator.store.final(final_id)["finalist"]
    # A restart resumes the same final on the same fresh set, attempt 1.
    restarted = make(tmp_path, refs, backend)
    decided = restarted.process_final(final_id)
    assert decided["state"] == "DECIDED"
    assert decided["finalist"] == claimed
    assert restarted.store.batches(kind="finalist", state="PREPARED") == []
    assert len(restarted.store.batches(kind="finalist", state="CONSUMED")) == 1


def test_an_unavailable_worker_host_is_infrastructure(tmp_path, refs):
    from carbon.battery.worker import CarrierBackend, WorkLedger

    def no_docker(ledger, **kwargs):
        raise FileNotFoundError("docker")

    store_path = tmp_path / "state.sqlite3"
    validator = make(tmp_path, refs, DirectBackend(REPOSITORY))
    validator.backend = CarrierBackend(
        WorkLedger(validator.store, tmp_path / "work"),
        None,
        root=REPOSITORY,
        runner=no_docker,
        identity=validator.backend.identity,
    )
    assert store_path.exists()
    outcome = run(validator, submission("hk1"))
    assert outcome["state"] == "FAILED_INFRA"
    assert outcome["failure"]["code"] == "worker_infrastructure:FileNotFoundError"
    assert "screening" not in outcome
    assert validator.store.pool()["admitted"] == 0
