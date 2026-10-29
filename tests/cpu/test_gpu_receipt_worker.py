"""The GPU receipt worker's queue, lanes, yielding, restart and receipts. Stand-ins for Docker and the GPU: nothing is run."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path

import pytest

from carbon.backbone_catalog import gpu_receipt, listing
from carbon.backbone_catalog.receipt_store import ReceiptStore
from scripts.dev import gpu_receipt_worker as w

RT = "torch-cu130-py311"
HOST = "test-host-class"
IMAGE = "sha256:" + "a" * 64


def jobs(*ids, challenges=("c1",), runtime=RT):
    return [
        {
            "key": f"{i}|{runtime}",
            "catalog_id": i,
            "runtime": runtime,
            "bundle_digest": "sha256:" + "b" * 64,
            "challenges": list(challenges),
        }
        for i in ids
    ]


def ctx(tmp_path):
    return w.Context(
        checkout=tmp_path / "co",
        state_dir=tmp_path / "state",
        gpu_uuid="GPU-x",
        images={RT: IMAGE},
        wheels=tmp_path / "wheels",
        store=ReceiptStore(tmp_path / "store"),
        host_class=HOST,
        tested_on="RTX / 1",
        entry_timeout_s=60,
    )


def drive(
    queue, context, executor, *, max_attempts=2, lanes=1, busy=lambda: False, **extra
):
    lines = []
    counts = w.run_loop(
        queue,
        context,
        max_attempts=max_attempts,
        lanes_now=lambda: lanes,
        busy=busy,
        executor=executor,
        receipt_writer=extra.pop(
            "receipt_writer",
            lambda c, j, r: "sha256:" + "0" * 64,
        ),
        sleep=extra.pop("sleep", lambda s: None),
        nice=0,
        poll_s=0.01,
        out=lines.append,
        **extra,
    )
    return counts, lines


def ok(job_ctx, job):
    return {
        "verdict": "PASS",
        "reason": "bit_identical",
        "detail": "",
        "peak_gpu_bytes": 1,
    }


def test_a_passing_entry_ends_pass_and_progress_counts_per_challenge(tmp_path):
    q = w.Queue(":memory:")
    q.sync(jobs("a", "b", challenges=("c1", "c2")) + jobs("c"))
    counts, _ = drive(q, ctx(tmp_path), ok)
    assert counts["PASS"] == 3 and counts["QUEUED"] == 0
    assert w.progress_line(q).startswith("GPU receipts: c1 3 of 3; c2 2 of 2")


def test_a_failed_entry_is_retried_only_up_to_max_attempts_then_failed_with_its_reason(
    tmp_path,
):
    q = w.Queue(":memory:")
    q.sync(jobs("a"))
    calls = []

    def bad(c, j):
        calls.append(j["attempt"])
        return {"verdict": "FAILED", "reason": "worker_exit", "detail": "boom"}

    counts, _ = drive(q, ctx(tmp_path), bad, max_attempts=3)
    assert calls == [1, 2, 3]
    assert counts["FAILED"] == 1
    assert q.failures()[0]["reason"] == "worker_exit"


def test_a_pair_that_differs_is_unstable_with_no_receipt_and_no_retry(tmp_path):
    q = w.Queue(":memory:")
    q.sync(jobs("a"))
    calls = []

    def differ(c, j):
        calls.append(1)
        return w._classify("DIFFER", 5)

    written = []
    counts, _ = drive(
        q, ctx(tmp_path), differ, receipt_writer=lambda c, j, r: written.append(j)
    )
    assert counts["UNSTABLE"] == 1 and calls == [1] and not written
    assert q.failures()[0]["reason"] == "non_reproducible"


def test_a_crashing_attempt_is_a_result_not_a_stop(tmp_path):
    q = w.Queue(":memory:")
    q.sync(jobs("a", "b"))

    def crash(c, j):
        if j["catalog_id"] == "a":
            raise RuntimeError("x")
        return ok(c, j)

    counts, _ = drive(q, ctx(tmp_path), crash, max_attempts=1)
    assert counts["FAILED"] == 1 and counts["PASS"] == 1


def test_restart_puts_running_back_and_keeps_the_attempt_count(tmp_path):
    path = tmp_path / "q.sqlite3"
    q = w.Queue(path)
    q.sync(jobs("a"))
    assert q.claim()["attempt"] == 1  # the process dies here, job left RUNNING
    again = w.Queue(path)
    assert again.counts()["RUNNING"] == 1
    assert again.recover() == 1
    assert again.claim()["attempt"] == 2
    # a job that died on its last attempt is exhausted, not retried forever
    again.recover()
    again.exhaust(2)
    assert again.counts()["FAILED"] == 1


def test_no_lane_starts_while_official_grading_is_busy_and_work_resumes_after(tmp_path):
    q = w.Queue(":memory:")
    q.sync(jobs("a"))
    state = {"n": 0}

    def busy():
        state["n"] += 1
        return state["n"] <= 3

    started = []

    def exe(c, j):
        started.append(state["n"])
        return ok(c, j)

    counts, _ = drive(q, ctx(tmp_path), exe, busy=busy)
    assert counts["PASS"] == 1 and started[0] > 3


def test_lanes_run_concurrently_up_to_the_plan(tmp_path):
    q = w.Queue(":memory:")
    q.sync(jobs("a", "b", "c", "d"))
    lock, live, peak = threading.Lock(), [0], [0]
    gate = threading.Barrier(2, timeout=5)

    def exe(c, j):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        try:
            if j["catalog_id"] in ("a", "b"):
                gate.wait()
        finally:
            with lock:
                live[0] -= 1
        return ok(c, j)

    drive(q, ctx(tmp_path), exe, lanes=2)
    assert peak[0] == 2


def test_plan_lanes_takes_the_smallest_limit_and_demands_measured_figures():
    plan = {"lane_vram": 10, "lane_cpus": 2, "lane_memory": 100, "max_lanes": 9}
    assert w.plan_lanes(free_vram=95, cpus=64, memory_available=10**6, **plan) == 9
    assert w.plan_lanes(free_vram=35, cpus=64, memory_available=10**6, **plan) == 3
    assert w.plan_lanes(free_vram=95, cpus=5, memory_available=10**6, **plan) == 2
    assert w.plan_lanes(free_vram=95, cpus=64, memory_available=250, **plan) == 2
    assert w.plan_lanes(free_vram=5, cpus=64, memory_available=10**6, **plan) == 0
    with pytest.raises(ValueError):
        w.plan_lanes(
            free_vram=1,
            cpus=1,
            memory_available=1,
            lane_vram=0,
            lane_cpus=1,
            lane_memory=1,
            max_lanes=1,
        )


def test_the_yield_choice_must_be_explicit_and_exactly_one(tmp_path):
    with pytest.raises(ValueError):
        w.make_busy()
    with pytest.raises(ValueError):
        w.make_busy(yield_file=str(tmp_path / "f"), no_yield=True)
    flag = tmp_path / "grading"
    busy = w.make_busy(yield_file=str(flag))
    assert busy() is False
    flag.write_text("x")
    assert busy() is True
    assert w.make_busy(no_yield=True)() is False
    assert w.make_busy(busy_command="exit 0")() is True
    assert w.make_busy(busy_command="exit 1")() is False


def test_sync_skips_and_adopts_and_never_requeues_a_known_job():
    q = w.Queue(":memory:")
    js = jobs("a", "b", "c")
    q.sync(
        js,
        skipped={js[0]["key"]: "smoke_only_cpu_rebuild_lane"},
        adopted={js[1]["key"]: "receipt_already_on_disk"},
    )
    assert (
        q.counts()["SKIPPED"] == 1
        and q.counts()["PASS"] == 1
        and q.counts()["QUEUED"] == 1
    )
    q.sync(js)
    assert q.counts()["QUEUED"] == 1
    # skipped entries are not part of "M"
    assert q.per_challenge()["c1"]["total"] == 2


def test_the_docker_run_is_the_official_isolated_shape_and_moves_no_tag(tmp_path):
    c = ctx(tmp_path)
    argv = w.docker_argv(
        c, RT, "cat-1", "name1", tmp_path / "out", tmp_path / "scratch"
    )
    joined = " ".join(argv)
    for part in (
        "--gpus device=GPU-x",
        "--network none",
        "--read-only",
        "/work:ro",
        "/wheels:ro",
        IMAGE,
    ):
        assert part in joined, part
    assert argv[:2] == ["docker", "run"] and "tag" not in argv and "build" not in argv
    assert (
        "--framework torch" in joined
        and argv[argv.index("scripts/dev/gpu_repeat.py") + 2] == "/out/name1.json"
    )


def test_official_pair_passes_on_two_identical_runs_and_fails_on_a_dead_run(
    tmp_path, monkeypatch
):
    c = ctx(tmp_path)
    job = {
        "key": f"cat-1|{RT}",
        "catalog_id": "cat-1",
        "runtime": RT,
        "challenges": ["c1"],
        "attempt": 1,
    }
    state = {"rc": 0, "verdict": "PASS"}

    def fake(argv, **kw):
        if argv[:2] == ["docker", "run"]:
            name = argv[argv.index("--name") + 1]
            out = next(a for a in argv if a.endswith(":/out:rw")).rsplit(":/out:rw", 1)[
                0
            ]
            if state["rc"] == 0:
                Path(out, name + ".json").write_text(
                    json.dumps({"entries": {"cat-1": {"first": {"peak_gpu_bytes": 7}}}})
                )
            return subprocess.CompletedProcess(argv, state["rc"], "", "died")
        return subprocess.CompletedProcess(argv, 0, "", "")

    c.run = fake
    monkeypatch.setattr(w, "compare_runs", lambda a, b: state["verdict"])
    done = w.official_pair(c, job)
    assert done["verdict"] == "PASS" and done["peak_gpu_bytes"] == 7
    state["verdict"] = "DIFFER"
    assert w.official_pair(c, job)["verdict"] == "UNSTABLE"
    state["verdict"] = "NOT_OK: backend_not_gpu"
    assert w.official_pair(c, job)["verdict"] == "FAILED"
    state["rc"] = 1
    failed = w.official_pair(c, job)
    assert failed["verdict"] == "FAILED" and failed["reason"] == "worker_exit"


def test_a_timeout_removes_the_container_and_is_a_failure(tmp_path):
    c = ctx(tmp_path)
    job = {
        "key": f"cat-1|{RT}",
        "catalog_id": "cat-1",
        "runtime": RT,
        "challenges": ["c1"],
        "attempt": 1,
    }
    seen = []

    def fake(argv, **kw):
        seen.append(argv[:3])
        if argv[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(argv, 1)
        return subprocess.CompletedProcess(argv, 0, "", "")

    c.run = fake
    done = w.official_pair(c, job)
    assert done["reason"] == "timeout" and ["docker", "rm", "-f"] in seen


def test_a_pass_appends_the_store_record_the_official_route_reads(tmp_path):
    pytest.importorskip("fcntl")
    c = ctx(tmp_path)
    item = next(
        e
        for e in listing.entries()
        if RT in (e.get("bundle_refs") or {})
        and e["catalog_id"] not in gpu_receipt.SMOKE_ONLY
    )
    cid = item["catalog_id"]
    job = {
        "key": f"{cid}|{RT}",
        "catalog_id": cid,
        "runtime": RT,
        "bundle_digest": item["bundle_refs"][RT]["bundle_digest"],
        "challenges": ["c1"],
    }
    run = "sha256:" + "d" * 64
    assert not w.record_is_done(c.store, job, IMAGE, HOST)
    own = w.write_record(c, job, {"run_digests": [run, run]})
    record = c.store.current(job["bundle_digest"], RT)
    assert own.startswith("sha256:") and record["host_class"] == HOST
    assert record["determinism_flags_digest"] == (
        gpu_receipt.required_determinism_digest(RT)
    )
    assert record["result"] == {"kind": "bit_identical"}
    assert w.record_is_done(c.store, job, IMAGE, HOST)
    assert not w.record_is_done(c.store, job, IMAGE, "other-class")
    assert not w.record_is_done(c.store, job, "sha256:" + "e" * 64, HOST)
    # the official read serves it (official_grade_problem judges image pin and host class, not this worker)
    assert gpu_receipt.official_load(item, RT, c.store)["host_class"] == HOST
    # write-once: the same bundle again must name the record it replaces, so a blind second write is refused
    with pytest.raises(ValueError):
        w.write_record(c, job, {"run_digests": [run, run]})


def test_a_bad_pair_writes_no_record_and_a_typed_failure_line(tmp_path):
    pytest.importorskip("fcntl")
    q = w.Queue(":memory:")
    q.sync(jobs("a", "b"))
    c = ctx(tmp_path)

    def exe(cx, j):
        if j["catalog_id"] == "a":
            return w._classify("DIFFER", 1)
        return {"verdict": "FAILED", "reason": "timeout", "detail": "x"}

    drive(q, c, exe, max_attempts=1)
    lines = [
        json.loads(x) for x in (c.state_dir / w.FAILURE_LOG).read_text().splitlines()
    ]
    assert {(x["catalog_id"], x["reason"]) for x in lines} == {
        ("a", "non_reproducible"),
        ("b", "timeout"),
    }
    assert ((c.state_dir / w.FAILURE_LOG).stat().st_mode & 0o077) == 0
    assert c.store.records() == []


def test_the_operator_pause_and_the_grading_lock_hold_the_worker_back(tmp_path):
    pytest.importorskip("fcntl")
    import fcntl

    state = tmp_path / "validator"
    state.mkdir()
    busy = w.make_busy(grading_state_dir=state, operator_state_dir=state)
    assert busy() is False  # no flag, no lock file: nothing holds the worker
    (state / "official-grading.lock").write_text("")
    fd = os.open(state / "official-grading.lock", os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert busy() is True
    finally:
        os.close(fd)
    assert busy() is False
    flag = state / "operator-pause.json"

    def put(text, mode=0o600):
        flag.write_text(text)
        flag.chmod(mode)

    put('{"crowns_paused": false, "weights_paused": false}')
    assert busy() is False  # a flag that pauses nothing
    for held in ('{"crowns_paused": true}', '{"weights_paused": true}'):
        put(held)
        assert busy() is True  # any pause stops new lanes
    for bad, mode in (
        ("not json", 0o600),
        ('{"other": true}', 0o600),
        ('{"crowns_paused": "yes"}', 0o600),
        ('{"crowns_paused": false}', 0o644),  # group/world-readable: a bad flag
    ):
        put(bad, mode)
        assert busy() is True  # a bad flag stops everything
    flag.unlink()
    flag.symlink_to(state / "elsewhere")
    assert busy() is True  # a symlinked flag is bad too
    assert w.make_busy(no_yield=True, operator_state_dir=state)() is True


def test_busy_freezes_the_running_containers_and_thaws_them(tmp_path):
    q = w.Queue(":memory:")
    q.sync(jobs("a"))
    flags = iter([False, True, True, False, False, False, False])
    calls = []
    release = threading.Event()

    def exe(c, j):
        release.wait(5)
        return ok(c, j)

    def busy():
        return next(flags, False)

    def pauser(running, paused):
        calls.append((paused, [j["catalog_id"] for j in running]))
        if not paused:
            release.set()

    drive(
        q,
        ctx(tmp_path),
        exe,
        busy=busy,
        pauser=pauser,
    )
    assert calls[:2] == [(True, ["a"]), (False, ["a"])]


def test_the_docker_pauser_names_both_containers_of_a_pair():
    seen = []
    w.docker_pauser(run=lambda argv, **kw: seen.append(argv))(jobs("a"), True)
    assert [x[:2] for x in seen] == [["docker", "pause"]] * 2
    assert seen[0][2] != seen[1][2]


def w_entries():
    from carbon.backbone_catalog import listing

    return [e["catalog_id"] for e in listing.entries()]


def test_served_jobs_come_from_the_registry_and_only_the_gpu_twins():
    found = w.served_jobs()
    assert found and all(j["runtime"] in w.TWINS for j in found)
    assert len({j["key"] for j in found}) == len(found)


def test_the_cli_requires_every_limit_and_a_registered_host_class(tmp_path, capsys):
    assert w.main(["run", "--state-dir", str(tmp_path)]) == 2
    assert "missing" in capsys.readouterr().err
    flags = []
    for name, value in (
        ("checkout", tmp_path),
        ("gpu-uuid", "u"),
        ("host-class", "nope"),
        ("wheels", tmp_path),
        ("store-dir", tmp_path),
        ("operator-state-dir", tmp_path),
        ("max-attempts", 2),
        ("entry-timeout-s", 9),
        ("lane-vram-bytes", 1),
        ("lane-cpus", 1),
        ("lane-memory-bytes", 1),
        ("max-lanes", 1),
    ):
        flags += [f"--{name}", str(value)]
    assert w.main(["run", "--state-dir", str(tmp_path), *flags]) == 2  # no yield choice
    assert (
        w.main(["run", "--state-dir", str(tmp_path), "--no-yield", *flags]) == 2
    )  # unregistered host class
    assert "not registered" in capsys.readouterr().err


def test_units_write_a_user_service_that_is_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gpu_receipt,
        "REGISTERED_HOST_CLASSES",
        {HOST: {}}
        if isinstance(gpu_receipt.REGISTERED_HOST_CLASSES, dict)
        else (HOST,),
    )
    flags = []
    for name, value in (
        ("checkout", tmp_path),
        ("gpu-uuid", "u"),
        ("host-class", HOST),
        ("wheels", tmp_path),
        ("store-dir", tmp_path),
        ("operator-state-dir", tmp_path),
        ("max-attempts", 2),
        ("entry-timeout-s", 9),
        ("lane-vram-bytes", 1),
        ("lane-cpus", 1),
        ("lane-memory-bytes", 1),
        ("max-lanes", 1),
    ):
        flags += [f"--{name}", str(value)]
    out = tmp_path / "units"
    assert (
        w.main(
            [
                "units",
                "--state-dir",
                str(tmp_path / "s"),
                "--no-yield",
                "--out-dir",
                str(out),
                *flags,
            ]
        )
        == 0
    )
    text = (out / "carbon-gpu-receipt-worker.service").read_text()
    assert (
        "Restart=on-failure" in text
        and "gpu_receipt_worker.py" in text
        and "--no-yield" in text
    )


def test_a_wheelhouse_the_container_cannot_read_is_refused_before_any_run(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    wheel = wheels / "a-1-py3-none-any.whl"
    wheel.write_bytes(b"x")
    wheels.chmod(0o755)
    wheel.chmod(0o644)
    assert w.wheels_problem(wheels) is None
    if os.name == "posix":
        wheel.chmod(0o600)
        assert "wheels_not_world_readable" in w.wheels_problem(wheels)
        wheel.chmod(0o644)
        wheels.chmod(0o700)
        assert "wheels_not_world_readable" in w.wheels_problem(wheels)
    assert "wheels_dir_missing" in w.wheels_problem(tmp_path / "nope")


def test_the_worker_starts_no_lane_while_a_grade_holds_the_lock_then_starts_one(
    tmp_path,
):
    """The receiver holds official-grading.lock for a whole official rebuild + grade (receipt_job.official_grading);
    the worker's loop, with the real lock probe, must start nothing until it is released.
    """
    pytest.importorskip("fcntl")
    from carbon.backbone_catalog import receipt_job

    state = tmp_path / "validator-state"
    state.mkdir()
    q = w.Queue(":memory:")
    q.sync(jobs("a"))
    started = []
    probes = []
    real = w.make_busy(grading_state_dir=state)

    def busy():
        held = real()
        probes.append(held)
        return held

    def exe(c, j):
        started.append(len(probes))
        return ok(c, j)

    lock = receipt_job.official_grading(state)
    lock.__enter__()
    released = []

    def sleep(_):
        # the loop waited at least three probes under the held lock, and nothing started
        if len(probes) >= 3 and not released:
            assert started == [] and all(probes)
            lock.__exit__(None, None, None)
            released.append(True)

    try:
        counts, _ = drive(q, ctx(tmp_path), exe, busy=busy, sleep=sleep)
    finally:
        if not released:
            lock.__exit__(None, None, None)
    assert released and counts["PASS"] == 1
    assert len(started) == 1 and started[0] > 3  # started only after the release
