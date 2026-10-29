"""The on-box store of official GPU receipts and its standing job (OWNER-GPU-OPEN-WITH-READY-01)."""

import json
import os
import stat

import pytest

from carbon.backbone_catalog import (
    gpu_receipt,
    pipeline,
    receipt_job,
    receipt_store,
    served,
)
from carbon.backbone_catalog.receipt_store import ReceiptRefused, ReceiptStore

pytestmark = pytest.mark.skipif(
    not hasattr(os, "geteuid"), reason="owner-only modes and flock are POSIX"
)

RUNTIME = "torch-cu130-py311"
IMAGE = "sha256:" + "a" * 64
RUN_A, RUN_B = "sha256:" + "1" * 64, "sha256:" + "2" * 64
NOISE = 0.01


def registered(challenge_id):
    return NOISE if challenge_id == "electric-motor-magnetics" else None


def torch_item():
    for item in pipeline.load()["entries"]:
        if RUNTIME in (item.get("bundle_refs") or {}):
            return item
    raise AssertionError("no torch twin in the catalog")


def record(item=None, *, supersedes=None, runs=(RUN_A, RUN_A), result=None, **change):
    item = item or torch_item()
    body = {
        "schema": receipt_store.SCHEMA,
        "catalog_id": item["catalog_id"],
        "runtime_profile_id": RUNTIME,
        "bundle_digest": item["bundle_refs"][RUNTIME]["bundle_digest"],
        "image_id": IMAGE,
        "host_class": "VALIDATOR-HOST-CLASS-FIXTURE",
        "determinism_flags_digest": gpu_receipt.required_determinism_digest(RUNTIME),
        "result": result or {"kind": receipt_store.BIT_IDENTICAL},
        "run_digests": list(runs),
        "supersedes": supersedes,
    }
    body.update(change)
    return body


def within(diff=0.004, noise=NOISE, challenge="electric-motor-magnetics"):
    return {
        "kind": receipt_store.WITHIN_NOISE,
        "challenge_id": challenge,
        "noise_value": noise,
        "max_abs_diff": diff,
    }


@pytest.fixture
def store(tmp_path):
    return ReceiptStore(tmp_path / "gpu-receipts", registered_noise=registered)


# --- the store is owner-only, write-once and append-only ----------------------------------------------------------


def test_a_record_is_stored_owner_only_named_by_its_digest_and_logged(store):
    own = store.append(record())
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE((store.root / "records").stat().st_mode) == 0o700
    path = store.root / "records" / (own.removeprefix("sha256:") + ".json")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((store.root / "receipts.log").stat().st_mode) == 0o600
    assert receipt_store.digest(path.read_bytes()) == own
    assert [
        json.loads(l)["record"]
        for l in (store.root / "receipts.log").read_bytes().splitlines()
    ] == [own]
    assert store.current(record()["bundle_digest"], RUNTIME) == record()


def test_a_second_record_for_the_same_bundle_must_name_the_one_it_replaces(store):
    first = store.append(record())
    with pytest.raises(ReceiptRefused, match="must_name_the_old"):
        store.append(record(image_id="sha256:" + "b" * 64))
    with pytest.raises(ReceiptRefused, match="must_name_the_old"):
        store.append(record(image_id="sha256:" + "b" * 64, supersedes=RUN_A))
    new = record(image_id="sha256:" + "b" * 64, supersedes=first)
    second = store.append(new)
    assert store.current(new["bundle_digest"], RUNTIME) == new
    # Append-only: the replaced record and its file are still there and still logged.
    assert [r["image_id"] for r in store.records()] == [IMAGE, "sha256:" + "b" * 64]
    assert (store.root / "records" / (first.removeprefix("sha256:") + ".json")).exists()
    with pytest.raises(ReceiptRefused, match="must_name_the_old"):
        store.append(record(image_id="sha256:" + "c" * 64, supersedes=first))
    assert second != first


def test_a_first_record_cannot_claim_to_replace_something(store):
    with pytest.raises(ReceiptRefused, match="record_supersedes"):
        store.append(record(supersedes=RUN_A))
    assert store.records() == []


def test_the_log_is_a_digest_chain_and_its_digest_moves_with_every_record(store):
    assert store.log_digest() is None
    store.append(record())
    first = store.log_digest()
    other = next(
        i
        for i in pipeline.load()["entries"]
        if RUNTIME in (i.get("bundle_refs") or {})
        and i["catalog_id"] != torch_item()["catalog_id"]
    )
    store.append(record(other))
    assert store.log_digest() != first
    lines = [
        json.loads(l) for l in (store.root / "receipts.log").read_bytes().splitlines()
    ]
    assert [l["sequence"] for l in lines] == [0, 1]
    assert lines[0]["previous"] is None
    assert lines[1]["previous"] == receipt_store.digest(
        (store.root / "receipts.log").read_bytes().splitlines()[0]
    )


# --- a defective store or record is refused, never served ---------------------------------------------------------


def test_a_tampered_record_is_refused(store):
    own = store.append(record())
    path = store.root / "records" / (own.removeprefix("sha256:") + ".json")
    path.write_bytes(path.read_bytes().replace(b"FIXTURE", b"FORGED"))
    with pytest.raises(ReceiptRefused, match="record_digest"):
        store.records()


def test_a_removed_record_or_an_altered_log_is_refused(store):
    own = store.append(record())
    log = store.root / "receipts.log"
    original = log.read_bytes()
    log.write_bytes(original.replace(b'"sequence":0', b'"sequence":5'))
    with pytest.raises(ReceiptRefused, match="log_chain"):
        store.records()
    log.write_bytes(original)
    (store.root / "records" / (own.removeprefix("sha256:") + ".json")).unlink()
    with pytest.raises(ReceiptRefused, match="store_unreadable"):
        store.records()


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"schema": "other"}, "record_schema"),
        ({"image_id": "latest"}, "record_image_id"),
        ({"bundle_digest": "sha256:short"}, "record_bundle_digest"),
        ({"determinism_flags_digest": None}, "record_determinism_flags_digest"),
        ({"host_class": ""}, "record_host_class"),
        ({"run_digests": [RUN_A]}, "record_run_digests"),
        ({"supersedes": "x"}, "record_supersedes"),
    ],
)
def test_a_malformed_record_is_refused_on_write(store, change, reason):
    with pytest.raises(ReceiptRefused, match=reason):
        store.append(record(**change))
    assert store.records() == []


def test_an_extra_or_missing_field_is_refused(store):
    extra = record()
    extra["note"] = "x"
    with pytest.raises(ReceiptRefused, match="record_shape"):
        store.append(extra)
    short = record()
    del short["host_class"]
    with pytest.raises(ReceiptRefused, match="record_shape"):
        store.append(short)


def test_a_malformed_record_in_the_store_is_refused_on_read(store):
    own = store.append(record())
    path = store.root / "records" / (own.removeprefix("sha256:") + ".json")
    forged = json.loads(path.read_bytes())
    forged["image_id"] = "latest"
    raw = receipt_store.canonical(forged)
    forged_name = receipt_store.digest(raw)
    (
        store.root / "records" / (forged_name.removeprefix("sha256:") + ".json")
    ).write_bytes(raw)
    os.chmod(
        store.root / "records" / (forged_name.removeprefix("sha256:") + ".json"), 0o600
    )
    line = receipt_store.canonical(
        {
            "schema": receipt_store.LOG_SCHEMA,
            "sequence": 0,
            "record": forged_name,
            "previous": None,
        }
    )
    (store.root / "receipts.log").write_bytes(line + b"\n")
    with pytest.raises(ReceiptRefused, match="record_image_id"):
        store.records()


def test_a_loosely_permissioned_store_is_refused(store):
    own = store.append(record())
    path = store.root / "records" / (own.removeprefix("sha256:") + ".json")
    os.chmod(path, 0o644)
    with pytest.raises(ReceiptRefused, match="store_not_owner_only"):
        store.records()
    os.chmod(path, 0o600)
    os.chmod(store.root, 0o755)
    with pytest.raises(ReceiptRefused, match="store_not_owner_only"):
        store.records()


def test_a_foreign_owned_store_is_refused(store, monkeypatch):
    store.append(record())
    monkeypatch.setattr(os, "geteuid", lambda: os.stat(store.root).st_uid + 1)
    with pytest.raises(ReceiptRefused, match="store_not_owner_only"):
        store.records()


def test_a_symlinked_record_is_refused(store, tmp_path):
    own = store.append(record())
    path = store.root / "records" / (own.removeprefix("sha256:") + ".json")
    target = tmp_path / "elsewhere"
    target.write_bytes(path.read_bytes())
    os.chmod(target, 0o600)
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(ReceiptRefused, match="store_not_owner_only"):
        store.records()


# --- the result rules ---------------------------------------------------------------------------------------------


def test_bit_identical_needs_identical_run_digests(store):
    with pytest.raises(ReceiptRefused, match="not_bit_identical"):
        store.append(record(runs=(RUN_A, RUN_B)))
    store.append(record(runs=(RUN_A, RUN_A, RUN_A)))


def test_a_within_noise_result_needs_the_registered_noise_and_a_difference_within_it(
    store,
):
    store.append(record(result=within(), runs=(RUN_A, RUN_B)))


@pytest.mark.parametrize(
    "result,reason",
    [
        (within(diff=0.02), "beyond_noise"),
        (within(noise=0.5), "noise_not_registered"),
        (within(challenge="chip-cold-plate"), "noise_not_registered"),
        (within(challenge="unregistered"), "noise_not_registered"),
        (within(noise=0), "record_result"),
        (within(diff=-1), "record_result"),
        ({"kind": "within_noise"}, "record_result"),
        ({"kind": "sort_of_close"}, "record_result"),
    ],
)
def test_a_within_noise_result_that_does_not_hold_is_refused(store, result, reason):
    with pytest.raises(ReceiptRefused, match=reason):
        store.append(record(result=result, runs=(RUN_A, RUN_B)))


def test_without_a_registered_noise_source_a_within_noise_record_is_refused(tmp_path):
    bare = ReceiptStore(tmp_path / "bare")
    with pytest.raises(ReceiptRefused, match="noise_not_registered"):
        bare.append(record(result=within(), runs=(RUN_A, RUN_B)))


# --- gpu_receipt reads the store for the official route -------------------------------------------------------------


def test_the_official_route_reads_the_stores_record_and_judges_it_unchanged(
    store, monkeypatch
):
    item = torch_item()
    assert gpu_receipt.official_receipt(item, RUNTIME, store) is None
    store.append(record(item))
    receipt = gpu_receipt.official_receipt(item, RUNTIME, store)
    assert receipt["image_digest"] == IMAGE and receipt["kind"] == "repeat"
    assert receipt["determinism"] == gpu_receipt.required_determinism(RUNTIME)
    # Not yet an official-grade receipt: the image is not pinned and the host class is not registered.
    assert "pinned" in gpu_receipt.official_grade_problem(receipt, RUNTIME)
    monkeypatch.setattr(gpu_receipt, "PINNED_GPU_IMAGES", {RUNTIME: {IMAGE}})
    assert "host class" in gpu_receipt.official_grade_problem(receipt, RUNTIME)
    monkeypatch.setattr(
        gpu_receipt,
        "REGISTERED_HOST_CLASSES",
        frozenset({"VALIDATOR-HOST-CLASS-FIXTURE"}),
    )
    assert gpu_receipt.official_grade_problem(receipt, RUNTIME) is None


def test_a_record_with_another_determinism_digest_is_not_official_grade(
    store, monkeypatch
):
    item = torch_item()
    store.append(record(item, determinism_flags_digest="sha256:" + "d" * 64))
    receipt = gpu_receipt.official_receipt(item, RUNTIME, store)
    assert receipt["determinism"] is None
    monkeypatch.setattr(gpu_receipt, "PINNED_GPU_IMAGES", {RUNTIME: {IMAGE}})
    monkeypatch.setattr(
        gpu_receipt,
        "REGISTERED_HOST_CLASSES",
        frozenset({"VALIDATOR-HOST-CLASS-FIXTURE"}),
    )
    assert "determinism" in gpu_receipt.official_grade_problem(receipt, RUNTIME)


def test_a_record_of_another_entry_or_a_defective_store_is_never_served(store):
    item = torch_item()
    store.append(record(item, catalog_id="someone.else"))
    with pytest.raises(gpu_receipt.GpuReceiptBroken, match="another entry"):
        gpu_receipt.official_receipt(item, RUNTIME, store)
    broken = ReceiptStore(store.root.parent / "none")
    os.makedirs(broken.root, mode=0o755)
    os.chmod(broken.root, 0o755)
    with pytest.raises(gpu_receipt.GpuReceiptBroken, match="owner_only"):
        gpu_receipt.official_receipt(item, RUNTIME, broken)
    # The record of a replaced bundle is not the record of this one.
    other = dict(
        item,
        bundle_refs={
            RUNTIME: dict(
                item["bundle_refs"][RUNTIME], bundle_digest="sha256:" + "e" * 64
            )
        },
    )
    assert gpu_receipt.official_receipt(other, RUNTIME, store) is None


def test_the_repository_receipts_stay_the_practice_and_legacy_source(store):
    item = torch_item()
    # No store record: the official route falls back to the repository receipt, exactly as before.
    assert gpu_receipt.official_load(item, RUNTIME, store) == gpu_receipt.load(
        item["catalog_id"], RUNTIME
    )


def test_the_official_route_accepts_a_store_receipt_and_refuses_without_one(
    store, monkeypatch
):
    item = torch_item()
    ref = item["bundle_refs"][RUNTIME]
    monkeypatch.setattr(gpu_receipt, "PINNED_GPU_IMAGES", {RUNTIME: {IMAGE}})
    monkeypatch.setattr(
        gpu_receipt,
        "REGISTERED_HOST_CLASSES",
        frozenset({"VALIDATOR-HOST-CLASS-FIXTURE"}),
    )
    monkeypatch.setattr(gpu_receipt, "OFFICIAL_STORE", store)
    monkeypatch.setattr(gpu_receipt, "load", lambda catalog_id, runtime: None)
    with pytest.raises(served.CatalogRefused) as refused:
        served.refuse_unreproducible_runtime(ref)
    assert refused.value.code == "catalog_runtime_not_reproducible"
    store.append(record(item))
    served.refuse_unreproducible_runtime(ref)
    assert served.runtime_bundle_ref(item, RUNTIME, official=True) == ref


# --- the standing job yields to official grading --------------------------------------------------------------------


def test_the_grading_probe_sees_the_lock_and_never_holds_it(tmp_path):
    import fcntl

    assert receipt_job.grading_busy(tmp_path) is False
    path = tmp_path / receipt_job.GRADING_LOCK
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert receipt_job.grading_busy(tmp_path) is True
        fcntl.flock(fd, fcntl.LOCK_UN)
        assert receipt_job.grading_busy(tmp_path) is False
        # The probe left nothing held: a grader can take the exclusive lock at once.
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)


def entries_with_twins(count):
    return [
        e for e in pipeline.load()["entries"] if RUNTIME in (e.get("bundle_refs") or {})
    ][:count]


def test_the_job_waits_while_grading_runs_and_receipts_every_entry_in_order(store):
    items = entries_with_twins(3)
    state = {"busy_for": 3, "waits": 0, "produced": []}

    def busy():
        if state["busy_for"] > 0:
            state["busy_for"] -= 1
            return True
        return False

    def produce(entry, should_yield):
        state["produced"].append(entry["catalog_id"])
        return record(entry)

    def sleep(seconds):
        state["waits"] += 1

    done = receipt_job.run_standing(
        store, items, produce, busy=busy, nice=0, sleep=sleep
    )
    assert state["waits"] == 3
    assert state["produced"] == [e["catalog_id"] for e in items]
    assert len(done) == 3 and len(store.records()) == 3


def test_an_entry_abandoned_for_grading_is_redone_afterwards_not_recorded(store):
    (item,) = entries_with_twins(1)
    calls = []
    busy_now = [False]

    def busy():
        return busy_now[0]

    def produce(entry, should_yield):
        calls.append(should_yield())
        if len(calls) == 1:
            busy_now[0] = True  # official grading starts mid-entry
            assert should_yield() is True
            raise receipt_job.Yielded
        return record(entry)

    def sleep(seconds):
        busy_now[0] = False  # grading ends

    done = receipt_job.run_standing(
        store, [item], produce, busy=busy, nice=0, sleep=sleep
    )
    assert len(calls) == 2 and len(done) == 1
    assert len(store.records()) == 1


def test_the_job_lowers_its_priority_and_stops_cleanly(store, monkeypatch):
    niced = []
    monkeypatch.setattr(os, "nice", lambda value: niced.append(value) or 0)

    def never(entry, should_yield):
        raise AssertionError("stopped before any work")

    done = receipt_job.run_standing(
        store,
        entries_with_twins(2),
        never,
        busy=lambda: False,
        stop=lambda: True,
    )
    assert niced == [19] and done == []
