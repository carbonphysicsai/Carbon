"""Motor's hidden pool end to end (VALIDATOR-21; OWNER-MOTOR-HIDDEN-POOL-01).

Carbon's producer draws a hidden motor batch from its own synthetic root and
solves it with a scripted solver standing in for the pinned GetDP image. It
seals, schedules and publishes the batch, and an import-only validator
verifies, imports and scores on it. There is no container, chain, network
or spend. Not a security audit (AGENTS.md §13).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.batch_source import ProducerRefused
from carbon.challenge_validator.interface import (
    MOTOR_CONFIRMATION_ROLE,
    Admitted,
    Unavailable,
)
from carbon.challenge_validator.motor import MotorAdapterError
from carbon.challenge_validator.motor_hidden import (
    BATCH_CASES,
    DEPLOYMENT_SCHEMA,
    SOLVER_IMAGE,
    MotorHiddenAdapter,
    open_store,
    overlap_key,
)
from carbon.challenge_validator.motor_source import MotorBatchSource
from carbon.motor.domain import ANGLE_STEPS
from carbon.motor.research import SCAFFOLD
from carbon.reconstruction import capability_registry as registry

REPOSITORY = Path(__file__).resolve().parents[2]
CHALLENGE = registry.MOTOR_CHALLENGE
CONTRACT = registry.contract(CHALLENGE)


def write_deployment(path, **fields):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.write_text(json.dumps({"schema": DEPLOYMENT_SCHEMA, **fields}))
    path.chmod(0o600)
    return path


class Solver:
    """`run_batch.py`'s contract, scripted: each planned case gets one record
    from the pinned image. `fail` names cases whose first attempt is
    `FAILED_INFRA`; `invalid` names cases that end `REFERENCE_INVALID`."""

    def __init__(self, fail=(), invalid=()):
        self.fail, self.invalid = set(fail), set(invalid)
        self.planned = []

    def __call__(self, command, check, cwd, env):
        assert env["CARBON_MOTOR_IMAGE"] == SOLVER_IMAGE
        plan = json.loads(Path(command[2]).read_text())
        out = Path(command[command.index("--out") + 1])
        self.planned.append(sorted(c["case_id"] for c in plan["cases"]))
        with (out / "records.jsonl").open("a") as handle:
            for case in plan["cases"]:
                record = {
                    "case_id": case["case_id"],
                    "inputs": case["inputs"],
                    "image": SOLVER_IMAGE,
                    "status": "OK",
                }
                if case["case_id"] in self.fail:
                    self.fail.discard(case["case_id"])
                    record["status"] = "FAILED_INFRA"
                elif case["case_id"] in self.invalid:
                    record["status"] = "REFERENCE_INVALID"
                else:
                    j = case["inputs"]["current_density_a_mm2"]
                    record["outputs"] = {
                        "torque_nm": [
                            0.4 * j + 0.2 * math.sin(2 * math.pi * k / ANGLE_STEPS)
                            for k in range(ANGLE_STEPS)
                        ]
                    }
                handle.write(json.dumps(record) + "\n")

        class Done:
            returncode = 0

        return Done()


def make_source(tmp_path, solver=None):
    deployment = write_deployment(
        tmp_path / "producer-etc" / "motor.json",
        store=str(tmp_path / "producer-store"),
        custody=str(tmp_path / "producer-custody"),
    )
    if not (tmp_path / "producer-custody").exists():
        MotorBatchSource.init(deployment)
    return MotorBatchSource(
        deployment, repository=REPOSITORY, runner=solver or Solver()
    )


def validator(tmp_path, name="validator"):
    deployment = write_deployment(
        tmp_path / f"{name}-etc" / "motor.json", store=str(tmp_path / f"{name}-store")
    )
    return MotorHiddenAdapter.from_deployment(deployment, repository=REPOSITORY)


def admitted(block, hotkey="hk-motor", strategy=None):
    return Admitted(
        hotkey=hotkey,
        receipt={"sequence": 1, "digest": "d" * 64, "block": block},
        challenge_id=CHALLENGE,
        challenge_version=CONTRACT.version,
        strategy=SCAFFOLD if strategy is None else strategy,
        contract_digest=CONTRACT.digest,
    )


@pytest.fixture
def published(tmp_path):
    """One sealed, scheduled and published motor screening batch."""
    solver = Solver(invalid=())
    source = make_source(tmp_path, solver)
    key = ak.ProducerKey.create(tmp_path / "producer.key")
    producer = pr.Producer(tmp_path / "producer", [source], signing_key=key)
    drawn = producer.draw(CHALLENGE, "pscreen-S1", kind="screening")
    producer.solve(CHALLENGE, drawn["fingerprint"])
    commitment = producer.seal(CHALLENGE, drawn["fingerprint"])
    # The owner's cadence: slot 1 is blocks [1080, 4320).
    producer.schedule(CHALLENGE, drawn["fingerprint"], 1, block=0)
    producer.publish(CHALLENGE, drawn["fingerprint"])
    outbox = tmp_path / "producer" / "outbox" / CHALLENGE
    [path] = outbox.glob("*.json")
    return {
        "key": key,
        "commitment": commitment,
        "outbox": outbox,
        "value": ak.read_private(path),
        "source": source,
    }


# --- the producer -----------------------------------------------------------------------


def test_a_draw_is_deterministic_committed_and_sized_by_the_rule(tmp_path):
    source = make_source(tmp_path)
    fingerprint = source.draw("pscreen-S1", kind="screening")
    assert source.draw("pscreen-S1", kind="screening") == fingerprint
    [entry] = source.custody.batches()
    assert entry["fingerprint"] == fingerprint and entry["cases"] == BATCH_CASES
    assert len(source.jobs(fingerprint)) == BATCH_CASES
    # Another process on the same custody draws the same batch.
    assert make_source(tmp_path).draw("pscreen-S1", kind="screening") == fingerprint
    assert source.draw("pscreen-S2", kind="screening") != fingerprint
    for kwargs, code in (
        ({"kind": "screening", "size": 15}, "producer_size_not_registered"),
        ({"kind": "tuning"}, "producer_kind_refused"),
    ):
        with pytest.raises(ProducerRefused) as refused:
            source.draw("pscreen-S3", **kwargs)
        assert refused.value.code == code
    with pytest.raises(ProducerRefused) as refused:
        source.draw(MOTOR_CONFIRMATION_ROLE, kind="screening")
    assert refused.value.code == "seed_role_reserved"
    with pytest.raises(ProducerRefused) as refused:
        source.draw("pfinal-S1", kind="finalist")
    assert refused.value.code == "producer_kind_refused"


def test_a_tick_rotates_screening_batches_only(tmp_path):
    source = make_source(tmp_path)
    key = ak.ProducerKey.create(tmp_path / "producer.key")
    producer = pr.Producer(tmp_path / "producer", [source], signing_key=key)
    report = producer.tick(100)[CHALLENGE]
    assert report["filled"] == [1]
    assert report["finalist"] == {"filled": [], "unfilled": []}
    assert len(list((tmp_path / "producer" / "outbox" / CHALLENGE).glob("*.json"))) == 1


def test_a_published_case_is_never_drawn(tmp_path):
    source = make_source(tmp_path)
    document = source._document("pscreen-S1", "screening")
    source._published = {overlap_key(document["cases"][0]["inputs"])}
    with pytest.raises(ProducerRefused) as refused:
        source.draw("pscreen-S1", kind="screening")
    assert refused.value.code == "producer_published_case"
    assert source.custody.batches() == []


def test_solve_resumes_and_infrastructure_failures_are_retried(tmp_path):
    first = make_source(tmp_path)
    fingerprint = first.draw("pscreen-S1", kind="screening")
    flaky = sorted(job["case_id"] for job in first.jobs(fingerprint))[:2]
    solver = Solver(fail=flaky)
    source = make_source(tmp_path, solver)
    producer = pr.Producer(tmp_path / "producer", [source])
    producer.draw(CHALLENGE, "pscreen-S1", kind="screening")
    producer.solve(CHALLENGE, fingerprint)
    assert producer.seal(CHALLENGE, fingerprint)["state"] == "PENDING"
    assert source.store.pending(fingerprint) == flaky
    producer.solve(CHALLENGE, fingerprint)
    assert solver.planned[1] == flaky
    commitment = producer.seal(CHALLENGE, fingerprint)
    assert commitment["cases"] == BATCH_CASES
    assert commitment["seed_pin"].startswith("sha256:")
    # Nothing is left to solve, and no record is ever stored twice.
    assert producer.solve(CHALLENGE, fingerprint) == {"returncode": 0, "solved": 0}
    assert len(solver.planned) == 2


def test_the_cadence_and_identities_come_from_the_hidden_rule(tmp_path):
    source = make_source(tmp_path)
    assert source.cadence() == {"every_blocks": 1080, "active": 3}
    identities = source.identities()
    assert identities["contract_digest"] == CONTRACT.digest
    assert identities["rule_digest"] == validator(tmp_path).identities()["rule_digest"]


def test_a_changed_reference_is_refused(tmp_path):
    store = open_store(tmp_path / "store")
    document = {"cases": [{"case_id": "a"}, {"case_id": "b"}]}
    fingerprint = store.add(document, role="r", kind="screening", sequence=1)
    terminal = ("OK",)
    assert not store.ingest(
        fingerprint, [{"case_id": "a", "status": "OK"}], terminal=terminal
    )
    assert store.ingest(
        fingerprint, [{"case_id": "b", "status": "OK"}], terminal=terminal
    )
    with pytest.raises(MotorAdapterError) as refused:
        store.ingest(
            fingerprint, [{"case_id": "a", "status": "OK", "x": 1}], terminal=terminal
        )
    assert refused.value.code == "motor_references_changed"


# --- the validator ----------------------------------------------------------------------


def test_an_import_only_validator_imports_and_scores_the_shared_batch(
    tmp_path, published
):
    adapter = validator(tmp_path)
    result = ak.import_local(adapter, published["key"].public_key, published["outbox"])
    assert [p["state"] for p in result["packages"]] == ["IMPORTED"]
    again = ak.import_local(adapter, published["key"].public_key, published["outbox"])
    assert [p["state"] for p in again["packages"]] == ["HELD"]

    with pytest.raises(Unavailable) as early:
        adapter.evaluate(admitted(1079))
    assert early.value.code == "motor_hidden_pool_not_open"

    outcome = adapter.evaluate(admitted(1200))
    assert outcome["state"] == "SCORED"
    assert outcome["n_cases"] == BATCH_CASES and outcome["n_scored"] == BATCH_CASES
    assert set(outcome) - {"failure"} == {
        "schema",
        "submission_id",
        "challenge",
        "state",
        "evidence",
        "qualification",
        "reward",
        "score",
        "eligible",
        "n_cases",
        "n_scored",
        "n_gate_failed",
    }
    hidden = published["value"]["payload"]["document"]["cases"]
    text = json.dumps(outcome)
    assert not any(case["case_id"] in text for case in hidden)
    record = adapter.score_record(outcome["submission_id"])
    assert record["batches"] == [published["commitment"]["fingerprint"]]

    # One scored submission per hotkey per 360 blocks; another hotkey scores.
    other = dict(SCAFFOLD, parameters=dict(SCAFFOLD["parameters"], length="length_8"))
    with pytest.raises(Unavailable) as used:
        adapter.evaluate(admitted(1201, strategy=other))
    assert used.value.code == "hotkey_window_used"
    assert used.value.retry == {"next_block": 1440}
    assert adapter.evaluate(admitted(1201, hotkey="hk-other"))["state"] == "SCORED"
    assert adapter.evaluate(admitted(1440, strategy=other))["state"] == "SCORED"
    # After its window the batch keeps scoring until a new one activates.
    assert adapter.evaluate(admitted(5000, hotkey="hk-late"))["state"] == "SCORED"


def test_a_reference_failure_is_counted_never_charged(tmp_path):
    first = make_source(tmp_path)
    fingerprint = first.draw("pscreen-S1", kind="screening")
    bad = min(job["case_id"] for job in first.jobs(fingerprint))
    source = make_source(tmp_path, Solver(invalid=[bad]))
    key = ak.ProducerKey.create(tmp_path / "producer.key")
    producer = pr.Producer(tmp_path / "producer", [source], signing_key=key)
    producer.draw(CHALLENGE, "pscreen-S1", kind="screening")
    producer.solve(CHALLENGE, fingerprint)
    producer.seal(CHALLENGE, fingerprint)
    producer.schedule(CHALLENGE, fingerprint, 1, block=0)
    producer.publish(CHALLENGE, fingerprint)
    adapter = validator(tmp_path)
    ak.import_local(
        adapter, key.public_key, tmp_path / "producer" / "outbox" / CHALLENGE
    )
    outcome = adapter.evaluate(admitted(1200))
    assert outcome["n_cases"] == BATCH_CASES
    assert outcome["n_scored"] == BATCH_CASES - 1
    aggregate = adapter.score_record(outcome["submission_id"])["aggregate"]
    assert aggregate["n_reference_invalid"] == 1


def resigned(published, commitment, payload):
    return ak.verify(
        ak.package(published["key"], commitment, payload), published["key"].public_key
    )


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ("rule", "answer_key_identity_mismatch"),
        ("window", "answer_key_no_window"),
        ("case", "answer_key_fingerprint_mismatch"),
        ("drop_reference", "answer_key_references_mismatch"),
        ("change_reference", "answer_key_references_mismatch"),
        ("other_image", "answer_key_references_mismatch"),
        ("references_digest", "answer_key_references_mismatch"),
    ],
)
def test_a_correctly_signed_but_wrong_package_imports_nothing(
    tmp_path, published, change, code
):
    value = json.loads(json.dumps(published["value"]))
    commitment, payload = value["manifest"]["commitment"], value["payload"]
    references = payload["references"]
    first = min(references)
    if change == "rule":
        commitment["rule_digest"] = "sha256:" + "1" * 64
    elif change == "window":
        commitment["window"] = None
    elif change == "case":
        payload["document"]["cases"][0]["inputs"]["airgap_mm"] += 1e-3
    elif change == "drop_reference":
        references.pop(first)
    elif change == "change_reference":
        references[first]["outputs"]["torque_nm"][0] += 1.0
    elif change == "other_image":
        references[first]["image"] = "carbon-motor-reference:dev"
    else:
        commitment["references_digest"] = "sha256:" + "2" * 64
    commitment, payload = resigned(published, commitment, payload)
    adapter = validator(tmp_path)
    with pytest.raises(ak.AnswerKeyRefused) as refused:
        adapter.import_answer_key(commitment, payload)
    assert refused.value.code == code
    assert adapter.store.fingerprints() == []


def test_the_validator_never_draws_or_solves(tmp_path):
    adapter = validator(tmp_path)
    for call in (
        lambda: adapter.prepare_batch("pscreen-S1", kind="screening"),
        lambda: adapter.reference_jobs("sha256:" + "0" * 64),
        lambda: adapter.ingest_references("sha256:" + "0" * 64, []),
        adapter.open_pool,
    ):
        with pytest.raises(MotorAdapterError) as refused:
            call()
        assert refused.value.code == "motor_hidden_import_only"


def test_the_producer_serves_motor_only_under_its_approval(tmp_path):
    source = make_source(tmp_path)
    deployment = tmp_path / "producer-etc" / "motor.json"
    with pytest.raises(ProducerRefused) as refused:
        pr.source_for(CHALLENGE, {"deployment": str(deployment), "approval": None})
    assert refused.value.code == "producer_challenge_not_approved"
    import hashlib

    name = "2026-10-07-OWNER-MOTOR-HIDDEN-POOL-01.md"
    body = (REPOSITORY / ".agent" / "decisions" / name).read_bytes()
    approval = {
        "record": "OWNER-MOTOR-HIDDEN-POOL-01",
        "file": name,
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    served = pr.source_for(
        CHALLENGE, {"deployment": str(deployment), "approval": approval}
    )
    assert served.identities() == source.identities()
