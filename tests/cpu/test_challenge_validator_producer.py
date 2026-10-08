"""Carbon's pool-batch producer over battery (VALIDATOR-19 slice 1).

Synthetic roots in a temporary directory, battery rule v2, and a scripted
truth solve that writes synthetic terminal records: no container, network or
spend. The references are not physics; the checks are draw, commit, seal and
tamper refusal. Not a security audit (AGENTS.md §13).
"""

import json
import os
import pwd
import sqlite3
from pathlib import Path

import pytest

from carbon.battery import exam, seeds, worker
from carbon.battery.challenge import INPUTS
from carbon.battery.daemon import BatteryValidator, rule_digest
from carbon.battery.pool_store import PoolStore
from carbon.challenge_validator import producer as pr
from carbon.challenge_validator.battery import BatteryAdapter, BatteryBatchSource

REPOSITORY = Path(__file__).resolve().parents[2]
V2 = exam.DEVELOPMENT_RULE_V2
ME = pwd.getpwuid(os.geteuid()).pw_name
SIZE = 12


def scripted_solve(command, check):
    """The truth container's contract, scripted: every job in
    `/work/jobs.json` gets a synthetic terminal record."""
    mount = next(a for a in command if a.endswith(":/work:rw"))
    work = Path(mount.removesuffix(":/work:rw"))
    jobs = json.loads((work / "jobs.json").read_text())["jobs"]
    with (work / "records.jsonl").open("a") as handle:
        for job in jobs:
            record = {
                "case_id": job["case_id"],
                "inputs": {k: job[k] for k in INPUTS},
                "status": "OK",
            }
            handle.write(json.dumps(record) + "\n")

    class Done:
        returncode = 0

    return Done()


@pytest.fixture
def source(tmp_path):
    state = tmp_path / "hidden"
    state.mkdir(mode=0o700)
    root = seeds.PrivateRoot.create(state / "root.bin")
    journal = seeds.SeedJournal(state / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin("sha256:" + "0" * 64, rule_digest(V2)))
    target = BatteryValidator(
        store=PoolStore(state / "state.sqlite3", rule=V2),
        backend=worker.DirectBackend(REPOSITORY),
        root=root,
        journal=journal,
        repository=REPOSITORY,
        require_commitment=False,
    )
    target.start()
    target.lock_path = str(state / "state.sqlite3.lock")
    target.readonly = False
    return BatteryBatchSource(
        BatteryAdapter(target), overlay=tmp_path / "overlay", runner=scripted_solve
    )


@pytest.fixture
def producer(tmp_path, source):
    return pr.Producer(tmp_path / "producer", [source])


def drawn(producer, source, role="pscreen-P01"):
    return producer.draw(source.challenge_id, role, kind="screening", size=SIZE)


# -- draw, solve once, seal -----------------------------------------------------------------


def test_a_batch_is_drawn_solved_once_and_sealed(tmp_path, producer, source):
    challenge = source.challenge_id
    result = drawn(producer, source)
    fingerprint = result["fingerprint"]
    # Hidden duplicates reuse their original's solve.
    assert result["jobs"] == SIZE - 2
    assert producer.seal(challenge, fingerprint) == {
        "fingerprint": fingerprint,
        "state": "PENDING",
    }
    assert producer.solve(challenge, fingerprint) == {"returncode": 0}
    commitment = producer.seal(challenge, fingerprint)
    assert commitment["fingerprint"] == fingerprint
    assert commitment["cases"] == SIZE
    assert commitment["kind"] == "screening"
    assert commitment["references_digest"].startswith("sha256:")
    assert commitment["window"] is None
    assert commitment["rule_digest"] == rule_digest(V2)
    # Sealing again returns the same commitment and journals nothing new.
    assert producer.seal(challenge, fingerprint) == commitment
    events = [e["event"] for e in producer.journal.entries()]
    assert events == ["drawn", "sealed"]
    assert producer.status() == {
        "challenges": {challenge: {"drawn": 1, "sealed": 1, "published": 0}}
    }


def test_the_public_record_names_no_case(tmp_path, producer, source):
    fingerprint = drawn(producer, source)["fingerprint"]
    producer.solve(source.challenge_id, fingerprint)
    producer.seal(source.challenge_id, fingerprint)
    jobs = json.loads(
        next((tmp_path / "producer" / "work").rglob("jobs.json")).read_text()
    )
    case_ids = [job["case_id"] for job in jobs["jobs"]]
    public = [
        (tmp_path / "producer" / "journal.jsonl").read_text(),
        *(
            p.read_text()
            for p in (tmp_path / "producer" / "commitments").rglob("*.json")
        ),
    ]
    for text in public:
        assert "inputs" not in text
        assert not any(c in text for c in case_ids)
    for path in (tmp_path / "producer").rglob("*"):
        assert os.lstat(path).st_mode & 0o077 == 0, path


def test_a_draw_is_idempotent_by_role(producer, source):
    first = drawn(producer, source)
    assert drawn(producer, source) == first
    assert [e["event"] for e in producer.journal.entries()] == ["drawn"]


def test_only_a_served_kind_is_drawn(producer, source):
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.draw(source.challenge_id, "tuning-x", kind="tuning")
    assert refused.value.code == "producer_kind_refused"


def test_a_reserved_role_is_refused(producer, source):
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.draw(source.challenge_id, "graphite-tuning-v1", kind="screening")
    assert refused.value.code == "seed_role_reserved"


def test_an_undrawn_batch_is_neither_solved_nor_sealed(producer, source):
    for step in (producer.solve, producer.seal):
        with pytest.raises(pr.ProducerRefused) as refused:
            step(source.challenge_id, "sha256:" + "1" * 64)
        assert refused.value.code == "producer_not_drawn"


def test_an_unconfigured_challenge_is_refused(producer):
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.draw("no-such-challenge", "r", kind="screening")
    assert refused.value.code == "producer_no_source"


# -- tampering after the draw ---------------------------------------------------------------


def sealed(producer, source):
    fingerprint = drawn(producer, source)["fingerprint"]
    producer.solve(source.challenge_id, fingerprint)
    producer.seal(source.challenge_id, fingerprint)
    return fingerprint


def tamper(source, sql, *args):
    with sqlite3.connect(source.adapter.target.store.path) as db:
        db.execute(sql, args)


def test_a_changed_reference_is_refused(producer, source):
    fingerprint = sealed(producer, source)
    tamper(
        source,
        "UPDATE reference_records SET body=json_set(body,'$.status','REFERENCE_TIMEOUT')"
        " WHERE fingerprint=?",
        fingerprint,
    )
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.seal(source.challenge_id, fingerprint)
    assert refused.value.code == "producer_references_changed"


@pytest.mark.parametrize("duplicated", [False, True])
def test_a_changed_case_is_refused(producer, source, duplicated):
    """Either way: a changed fresh case changes the fingerprint; a changed
    case that has a hidden duplicate also breaks the batch's invariants."""
    fingerprint = sealed(producer, source)
    document = source.adapter.target.store.batch(fingerprint)["document"]
    twins = set(document["duplicates"]) | set(document["duplicates"].values())
    index = next(
        i
        for i, case in enumerate(document["cases"])
        if (case["case_id"] in twins) == duplicated
    )
    tamper(
        source,
        f"UPDATE batches SET document=json_set(document,'$.cases[{index}].inputs.c1',"
        "9.0) WHERE fingerprint=?",
        fingerprint,
    )
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.seal(source.challenge_id, fingerprint)
    assert refused.value.code == "producer_fingerprint_mismatch"


def test_solving_needs_the_truth_overlay(tmp_path, source):
    source.overlay = None
    producer = pr.Producer(tmp_path / "p2", [source])
    fingerprint = drawn(producer, source)["fingerprint"]
    with pytest.raises(pr.ProducerRefused) as refused:
        producer.solve(source.challenge_id, fingerprint)
    assert refused.value.code == "producer_no_truth_overlay"


# -- configuration --------------------------------------------------------------------------


def config(tmp_path, **changes):
    value = {
        "schema": pr.CONFIG_SCHEMA,
        "service_account": ME,
        "producer_dir": str(tmp_path / "producer"),
        "sources": {
            "battery": {
                "deployment": "/x/hidden.json",
                "approval": {"record": "OWNER-X-01", "file": "x.md", "sha256": "0"},
            }
        },
        **changes,
    }
    path = tmp_path / "producer.json"
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path


def test_the_config_loads_only_under_its_service_account(tmp_path):
    assert pr.load_config(config(tmp_path))["service_account"] == ME
    with pytest.raises(pr.ProducerRefused) as refused:
        pr.load_config(config(tmp_path, service_account="carbon-producer"))
    assert refused.value.code == "producer_wrong_account"


def test_the_config_is_owner_only_and_exact(tmp_path):
    path = config(tmp_path)
    path.chmod(0o644)
    with pytest.raises(pr.ProducerRefused) as refused:
        pr.load_config(path)
    assert refused.value.code == "producer_file_not_owner_only"
    with pytest.raises(pr.ProducerRefused) as refused:
        pr.load_config(config(tmp_path, extra=1))
    assert refused.value.code == "producer_config_malformed"


def test_the_producer_dir_stays_outside_the_repository():
    with pytest.raises(pr.ProducerRefused) as refused:
        pr.Producer(REPOSITORY / "tmp" / "producer", [])
    assert refused.value.code == "producer_dir_inside_repository"


def test_a_directory_others_can_read_is_refused_by_path(tmp_path, capsys, monkeypatch):
    """3a at r2: `carbon-push` had made the outbox 0755 under the default
    umask. The refusal is right; it now names the directory to fix."""
    from carbon.challenge_validator.batch_source import ProducerRefused

    outbox = tmp_path / "producer" / "outbox"
    outbox.mkdir(parents=True)
    outbox.chmod(0o755)
    with pytest.raises(ProducerRefused) as refused:
        pr._owner_only_dir(outbox)
    assert refused.value.code == "producer_dir_not_owner_only"
    assert refused.value.record() == {
        "refused": "producer_dir_not_owner_only",
        "path": str(outbox),
    }
    assert ProducerRefused("producer_slot_started").record() == {
        "refused": "producer_slot_started"
    }

    def refuse(*args, **kwargs):
        raise ProducerRefused("producer_dir_not_owner_only", path=outbox)

    monkeypatch.setattr(pr.Producer, "from_config", staticmethod(refuse))
    assert pr.main(["status", "--config", str(tmp_path / "producer.json")]) == 2
    printed = json.loads(capsys.readouterr().out)
    assert printed == {"refused": "producer_dir_not_owner_only", "path": str(outbox)}
