"""Bulk reference-data runner (scripts/dev/reference_packages/bulk_run.py).

A fake docker stands in for the daemon: it records every launch, the CPUs and
memory in use at once, and returns scripted results.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import Counter
from pathlib import Path

import pytest

from scripts.dev.reference_packages import bulk_run as br
from scripts.dev.reference_packages import triage_run

IMG = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
MIB = 1024**2


class FakeDocker:
    def __init__(self, identities=None, behaviour=None, config=None, stale=()):
        self.ids = {IMG: {IMG}} if identities is None else identities
        self.config = config or {}
        self.behaviour = behaviour or {}
        self.stale = list(stale)
        self.calls, self.stale_calls = [], 0
        self.lock = threading.Lock()
        self.cpus = self.mem = self.max_cpus = self.max_mem = 0
        self.fam_now, self.fam_max = Counter(), Counter()

    def info(self):
        return {}

    def image_identities(self, ref):
        return self.ids.get(ref)

    def config_digests(self, ref):
        return self.config.get(ref, set())

    def kill_stale(self, plan_id):
        self.stale_calls += 1
        return self.stale

    def run(self, spec, timeout_s, cancel):
        b = self.behaviour.get(spec["case"], {})
        with self.lock:
            self.calls.append((spec["family"], spec["case"], timeout_s))
            self.cpus += spec["cpus"]
            self.mem += spec["memory_bytes"]
            self.fam_now[spec["family"]] += 1
            self.max_cpus = max(self.max_cpus, self.cpus)
            self.max_mem = max(self.max_mem, self.mem)
            self.fam_max[spec["family"]] = max(
                self.fam_max[spec["family"]], self.fam_now[spec["family"]]
            )
        try:
            if "on_start" in b:
                b["on_start"]()
            if b.get("raise"):
                raise RuntimeError("daemon went away")
            if b.get("wait_cancel"):
                cancel.wait(5)
                reason = "cancel" if cancel.is_set() else "exit"
                return {"exit": 143, "stop_reason": reason, "wall_s": 1.0}
            time.sleep(b.get("sleep", 0.02))
            return {
                "exit": b.get("exit", 0),
                "stop_reason": b.get("stop_reason", "exit"),
                "wall_s": b.get("wall_s", 2.0),
                "cgroup_cpu_s": b.get("cpu_s", 1.5),
                "cgroup_memory_peak_bytes": b.get("peak", 100 * MIB),
                "cgroup_version": 2,
            }
        finally:
            with self.lock:
                self.cpus -= spec["cpus"]
                self.mem -= spec["memory_bytes"]
                self.fam_now[spec["family"]] -= 1


def make_family(root, family, cases, image=IMG):
    """cases: list of (name, reservation, extra-entry-fields)."""
    fdir = root / family
    entries = []
    for name, reservation, extra in cases:
        cdir = fdir / family / name
        cdir.mkdir(parents=True)
        body = f"deck {family}/{name}\n".encode()
        (cdir / "case.sif").write_bytes(body)
        entries.append(
            {
                "family": family,
                "case": name,
                "reservation": reservation,
                "command": "solver case.sif > solver.log 2>&1",
                "files": {"case.sif": hashlib.sha256(body).hexdigest()},
                **extra,
            }
        )
    manifest = {"schema": br.MANIFEST_SCHEMA, "image": image, "cases": entries}
    (fdir / "manifest.json").write_text(json.dumps(manifest))
    return fdir


def family_entry(family, **over):
    entry = {
        "family": family,
        "manifest_dir": family,
        "image": IMG,
        "priority": 10,
        "case_limits": {"cpus": 1, "memory_gib": 1, "pids": 64, "wall_timeout_s": 3600},
        "ceilings": {"launches": 100, "cpu_hours": 100},
    }
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(entry.get(key), dict):
            entry[key] = {**entry[key], **value}
        else:
            entry[key] = value
    return entry


def write_plan(root, families, **machine):
    plan = {
        "schema": br.PLAN_SCHEMA,
        "plan_id": "test-plan",
        "authority": "unit test",
        "host_profile": "fake",
        "machine": {"cpus": 8, "memory_gib": 16, "node_hours": 10, **machine},
        "families": families,
    }
    path = root / "plan.json"
    path.write_text(json.dumps(plan))
    return path


def cases(n, reservation="primary", prefix="c", **extra):
    return [(f"{prefix}{i}", reservation, dict(extra)) for i in range(n)]


def run(root, docker, host=None, **kw):
    plan = br.load_plan(root / "plan.json")
    br.preflight(plan, docker)
    host = host or {
        "nproc": 64,
        "mem_total_bytes": 512 * 1024**3,
        "boot_unix": time.time() - 60,
    }
    runner = br.BulkRun(
        plan, root / "out", docker, host=host, poll_s=0.01, log=lambda m: None
    )
    (root / "out").mkdir(exist_ok=True)
    total = runner.execute(**kw)
    return runner, total


def rows(root, event=None):
    lines = (root / "out" / "ledger.jsonl").read_text().splitlines()
    out = [json.loads(x) for x in lines if x.strip().endswith("}")]
    return [r for r in out if event is None or r["event"] == event]


def summary(root, family):
    return json.loads((root / "out" / "summary" / f"{family}.json").read_text())


# ------------------------------------------------------------------ plan


def test_plan_validation_names_every_problem(tmp_path):
    make_family(tmp_path, "f02", cases(1))
    bad = family_entry(
        "f02",
        image="carbon-ref-elmer:26.2.1",
        case_limits={"cpus": 99},
        ceilings={"cpu_hour": 3},
    )
    write_plan(tmp_path, [bad], eur_cap=5)
    with pytest.raises(br.PlanError) as err:
        br.load_plan(tmp_path / "plan.json")
    text = str(err.value)
    assert "image must be an image id" in text
    assert "unknown keys ['cpu_hour']" in text
    assert "eur_cap and machine.eur_per_hour go together" in text
    assert "exceed the machine's usable CPUs or memory" in text


def test_manifest_paths_must_stay_inside_the_case(tmp_path):
    fdir = make_family(tmp_path, "f02", cases(1))
    manifest = json.loads((fdir / "manifest.json").read_text())
    manifest["cases"][0]["files"] = {"../escape": "0" * 64}
    (fdir / "manifest.json").write_text(json.dumps(manifest))
    write_plan(tmp_path, [family_entry("f02")])
    with pytest.raises(br.PlanError, match="safe relative paths"):
        br.load_plan(tmp_path / "plan.json")


def test_priority_matches_triage_runner():
    assert br.PRIORITY == triage_run.PRIORITY


# ------------------------------------------------------------ scheduling


def test_bin_packing_never_oversubscribes_and_runs_families_together(tmp_path):
    make_family(tmp_path, "fa", cases(6))
    make_family(tmp_path, "fb", cases(4))
    write_plan(
        tmp_path,
        [
            family_entry("fa", case_limits={"cpus": 2, "memory_gib": 2}),
            family_entry("fb", case_limits={"cpus": 1, "memory_gib": 3}),
        ],
        cpus=5,
        memory_gib=9,
        reserve_cpus=1,
        reserve_memory_gib=1,
    )
    docker = FakeDocker(behaviour={f"c{i}": {"sleep": 0.1} for i in range(6)})
    run(tmp_path, docker)
    assert len(docker.calls) == 10
    assert docker.max_cpus <= 4 and docker.max_mem <= 8 * 1024**3
    assert docker.fam_max["fa"] >= 1 and docker.fam_max["fb"] >= 1
    assert docker.max_cpus >= 3  # packed, not one at a time
    assert {r["outcome"] for r in rows(tmp_path, "FINISHED")} == {"COMPLETED"}


def test_priority_and_reservation_order(tmp_path):
    make_family(tmp_path, "lo", cases(2))
    make_family(tmp_path, "hi", cases(1, "controls", prefix="k") + cases(2))
    write_plan(
        tmp_path,
        [family_entry("lo", priority=2), family_entry("hi", priority=1)],
        cpus=1,
    )
    docker = FakeDocker()
    run(tmp_path, docker)
    order = [(f, c) for f, c, _ in docker.calls]
    assert order == [
        ("hi", "c0"),
        ("hi", "c1"),
        ("hi", "k0"),
        ("lo", "c0"),
        ("lo", "c1"),
    ]


def test_cpu_ceiling_reservation_holds_under_concurrency(tmp_path):
    make_family(tmp_path, "f02", cases(5))
    write_plan(tmp_path, [family_entry("f02", ceilings={"cpu_hours": 2.5})])
    docker = FakeDocker(behaviour={f"c{i}": {"sleep": 0.05} for i in range(5)})
    run(tmp_path, docker)
    assert docker.fam_max["f02"] == 2  # two 1-CPU x 3600 s reservations fit 2.5 h
    assert len(rows(tmp_path, "FINISHED")) == 5
    # Replaying the ledger, booked + outstanding reservations never exceed it.
    booked, outstanding = 0.0, {}
    for row in rows(tmp_path):
        if row["event"] == "STARTED":
            outstanding[row["case"]] = row["reserved_cpu_s"]
        elif row["event"] == "FINISHED":
            outstanding.pop(row["case"])
            booked += row["allocated_cpu_s"]
        assert booked + sum(outstanding.values()) <= 2.5 * 3600


def test_launch_ceiling_counts_at_start(tmp_path):
    make_family(tmp_path, "f02", cases(5))
    write_plan(tmp_path, [family_entry("f02", ceilings={"launches": 3})])
    docker = FakeDocker(behaviour={f"c{i}": {"sleep": 0.1} for i in range(5)})
    run(tmp_path, docker)
    assert len(docker.calls) == 3
    s = summary(tmp_path, "f02")
    assert s["launches"] == 3 and s["not_launched"] == {"FAMILY_LAUNCH_CEILING": 2}


def test_last_budget_runs_clipped_and_is_censored(tmp_path):
    make_family(tmp_path, "f02", cases(3))
    write_plan(tmp_path, [family_entry("f02", ceilings={"cpu_hours": 0.4})])
    docker = FakeDocker(behaviour={"c0": {"stop_reason": "timeout", "wall_s": 1440.0}})
    run(tmp_path, docker)
    assert docker.calls == [("f02", "c0", pytest.approx(1440.0))]
    (started,) = rows(tmp_path, "STARTED")
    assert started["timeout_clip"] == "FAMILY"
    (done,) = rows(tmp_path, "FINISHED")
    assert done["outcome"] == "CENSORED_FAMILY_CAP"
    assert summary(tmp_path, "f02")["not_launched"] == {"FAMILY_CPU_CEILING": 2}


def test_case_timeout_and_failures_are_classified(tmp_path):
    make_family(tmp_path, "f02", cases(4))
    write_plan(tmp_path, [family_entry("f02")])
    docker = FakeDocker(
        behaviour={
            "c0": {"stop_reason": "timeout", "wall_s": 3600.0},
            "c1": {"exit": 1},
            "c2": {"raise": True},
            "c3": {"exit": 137},
        }
    )
    run(tmp_path, docker)
    got = {r["case"]: r for r in rows(tmp_path, "FINISHED")}
    assert got["c0"]["outcome"] == "CENSORED_CASE_TIMEOUT"
    assert got["c1"]["outcome"] == "FAILED"
    assert (
        got["c2"]["outcome"] == "FAILED_INFRA" and "daemon" in got["c2"]["infra_error"]
    )
    assert got["c3"]["outcome"] == "FAILED" and got["c3"]["oom_suspected"]


# ------------------------------------------------------- resume, refusal


def test_resume_abandons_started_case_and_never_retries(tmp_path):
    make_family(tmp_path, "f02", cases(4))
    write_plan(tmp_path, [family_entry("f02")])
    plan = br.load_plan(tmp_path / "plan.json")
    (tmp_path / "out").mkdir()
    ledger = br.Ledger(tmp_path / "out" / "ledger.jsonl")
    ledger.append(
        {"event": "RUN_START", "plan_digest": plan.digest, "started_unix": 1.0}
    )
    base = {"family": "f02", "reservation": "primary", "started_unix": 2.0}
    ledger.append({**base, "event": "STARTED", "case": "c0", "reserved_cpu_s": 3600.0})
    ledger.append({**base, "event": "STARTED", "case": "c1", "reserved_cpu_s": 3600.0})
    ledger.append(
        {
            **base,
            "event": "FINISHED",
            "case": "c1",
            "allocated_cpu_s": 5.0,
            "outcome": "FAILED",
        }
    )
    with open(tmp_path / "out" / "ledger.jsonl", "a") as handle:
        handle.write('{"event": "STAR')  # a crash mid-write
    docker = FakeDocker(stale=["deadbeef"])
    run(tmp_path, docker)
    assert sorted(c for _, c, _ in docker.calls) == ["c2", "c3"]
    assert docker.stale_calls == 1
    (abandoned,) = rows(tmp_path, "ABANDONED_ON_RESUME")
    assert abandoned["case"] == "c0" and abandoned["allocated_cpu_s"] == 3600.0
    s = summary(tmp_path, "f02")
    assert s["outcomes"] == {"COMPLETED": 2, "FAILED": 1, "ABANDONED_ON_RESUME": 1}
    assert s["allocated_cpu_hours"] == pytest.approx((3600 + 5 + 4) / 3600, abs=1e-4)
    total = json.loads((tmp_path / "out" / "summary" / "all.json").read_text())
    assert total["ledger_corrupt_lines"] == 1


def test_resume_under_another_plan_is_refused(tmp_path):
    make_family(tmp_path, "f02", cases(1))
    write_plan(tmp_path, [family_entry("f02")])
    (tmp_path / "out").mkdir()
    br.Ledger(tmp_path / "out" / "ledger.jsonl").append(
        {"event": "RUN_START", "plan_digest": "sha256:old", "started_unix": 1.0}
    )
    with pytest.raises(br.PlanError, match="another plan"):
        run(tmp_path, FakeDocker())


def test_hash_mismatch_refuses_the_run_before_any_launch(tmp_path):
    fdir = make_family(tmp_path, "f02", cases(2))
    write_plan(tmp_path, [family_entry("f02")])
    (fdir / "f02" / "c1" / "case.sif").write_text("tampered\n")
    docker = FakeDocker()
    code = br.main(
        ["--plan", str(tmp_path / "plan.json"), "--out", str(tmp_path / "out")], docker
    )
    assert code == 2 and docker.calls == []
    assert not (tmp_path / "out" / "ledger.jsonl").exists()


def test_tamper_after_preflight_is_refused_at_launch(tmp_path):
    fdir = make_family(tmp_path, "f02", cases(3))
    write_plan(tmp_path, [family_entry("f02")], cpus=1)

    def tamper():
        (fdir / "f02" / "c1" / "case.sif").write_text("tampered\n")

    docker = FakeDocker(behaviour={"c0": {"on_start": tamper}})
    run(tmp_path, docker)
    assert [c for _, c, _ in docker.calls] == ["c0"]
    (refused,) = rows(tmp_path, "REFUSED")
    assert refused["case"] == "c1" and refused["files"] == ["case.sif"]
    s = summary(tmp_path, "f02")
    assert s["refused"] == 1 and s["not_launched"] == {"REFUSED_HASH_MISMATCH": 1}


@pytest.mark.parametrize(
    ("identities", "config", "ok"),
    [
        ({IMG: {IMG}}, {}, True),
        ({IMG: {OTHER}}, {}, False),
        ({}, {}, False),
        ({IMG: {OTHER}}, {IMG: {"sha256:" + "c" * 64}}, False),
    ],
)
def test_image_must_carry_the_manifest_pin(tmp_path, identities, config, ok):
    make_family(tmp_path, "f02", cases(1))
    write_plan(tmp_path, [family_entry("f02")])
    plan = br.load_plan(tmp_path / "plan.json")
    docker = FakeDocker(identities=identities, config=config)
    if ok:
        br.preflight(plan, docker)
    else:
        with pytest.raises(br.PlanError, match="image"):
            br.preflight(plan, docker)


def test_config_digest_pin_is_found_through_image_save(tmp_path):
    ref = "ghcr.io/carbon/elmer@sha256:" + "d" * 64
    make_family(tmp_path, "f02", cases(1), image=IMG)
    write_plan(tmp_path, [family_entry("f02", image=ref)])
    plan = br.load_plan(tmp_path / "plan.json")
    docker = FakeDocker(identities={ref: {"sha256:" + "d" * 64}}, config={ref: {IMG}})
    assert IMG in br.preflight(plan, docker)["f02"]


# ----------------------------------------------------------------- stops


def test_stop_file_drains(tmp_path):
    make_family(tmp_path, "f02", cases(3))
    write_plan(tmp_path, [family_entry("f02")], cpus=1)
    stop = tmp_path / "out" / "STOP"
    docker = FakeDocker(behaviour={"c0": {"on_start": stop.touch}})
    _, total = run(tmp_path, docker)
    assert [c for _, c, _ in docker.calls] == ["c0"]
    assert rows(tmp_path, "FINISHED")[0]["outcome"] == "COMPLETED"
    assert total["stop_reason"] == "STOP"
    assert summary(tmp_path, "f02")["not_launched"] == {"STOP": 2}


def test_stop_now_cancels_running_cases(tmp_path):
    make_family(tmp_path, "f02", cases(2))
    write_plan(tmp_path, [family_entry("f02")], cpus=1)
    stop = tmp_path / "out" / "STOP_NOW"
    docker = FakeDocker(behaviour={"c0": {"on_start": stop.touch, "wait_cancel": True}})
    run(tmp_path, docker)
    (done,) = rows(tmp_path, "FINISHED")
    assert done["outcome"] == "CENSORED_OPERATOR_STOP"


def test_node_hour_cap_launches_nothing_after_the_deadline(tmp_path):
    make_family(tmp_path, "f02", cases(2))
    write_plan(tmp_path, [family_entry("f02")], node_hours=2)
    host = {"nproc": 64, "boot_unix": time.time() - 2 * 3600}
    docker = FakeDocker()
    _, total = run(tmp_path, docker, host=host)
    assert docker.calls == [] and total["stop_reason"] == "MACHINE_CAP"
    assert summary(tmp_path, "f02")["not_launched"] == {"MACHINE_CAP": 2}


def test_eur_cap_clips_cases_to_the_deadline(tmp_path):
    make_family(tmp_path, "f02", cases(1))
    write_plan(
        tmp_path,
        [family_entry("f02", case_limits={"wall_timeout_s": 7200})],
        eur_cap=3.5,
        eur_per_hour=1.0,
        margin_minutes=15,
    )
    host = {"nproc": 64, "boot_unix": time.time() - 2 * 3600}
    docker = FakeDocker()
    run(tmp_path, docker, host=host)
    # 3.5 EUR at 1 EUR per started hour = 3 billed hours; minus 2 h used, 15 min margin.
    ((_, _, timeout),) = docker.calls
    assert 2690 < timeout <= 2700
    assert rows(tmp_path, "STARTED")[0]["timeout_clip"] == "MACHINE"


def test_plan_bigger_than_host_is_refused(tmp_path):
    make_family(tmp_path, "f02", cases(1))
    write_plan(tmp_path, [family_entry("f02")], cpus=8)
    with pytest.raises(br.PlanError, match="host has 4"):
        run(tmp_path, FakeDocker(), host={"nproc": 4, "boot_unix": time.time()})


# ------------------------------------------------------------ acceptance


def test_failed_acceptance_blocks_only_its_family_and_is_not_retried(tmp_path):
    make_family(tmp_path, "fa", cases(2))
    make_family(tmp_path, "fb", cases(2))
    write_plan(
        tmp_path,
        [
            family_entry("fa", acceptance={"command": "solver -v", "timeout_s": 60}),
            family_entry("fb", acceptance={"command": "other -v"}),
        ],
    )
    docker = FakeDocker(behaviour={"_acceptance": {"exit": 0}})
    original = docker.run

    def run_with_failing_fa(spec, timeout_s, cancel):
        if spec["family"] == "fa" and spec["case"] == "_acceptance":
            return {"exit": 1, "stop_reason": "exit", "wall_s": 1.0}
        return original(spec, timeout_s, cancel)

    docker.run = run_with_failing_fa
    run(tmp_path, docker)
    launched = {(f, c) for f, c, _ in docker.calls}
    assert ("fb", "c0") in launched and not any(f == "fa" for f, _ in launched)
    assert summary(tmp_path, "fa")["not_launched"] == {"BLOCKED_ACCEPTANCE": 2}
    assert summary(tmp_path, "fa")["acceptance"] == {"passed": False, "exit": 1}
    before = len(rows(tmp_path, "ACCEPTANCE"))
    run(tmp_path, docker)  # resume: acceptance recorded, not re-run
    assert len(rows(tmp_path, "ACCEPTANCE")) == before == 2


# ---------------------------------------------------------- summary, dry


def test_summary_counts_cost_and_memory_percentiles(tmp_path):
    make_family(tmp_path, "f02", cases(10))
    write_plan(tmp_path, [family_entry("f02", case_limits={"cpus": 2})])
    behaviour = {
        f"c{i}": {"peak": (i + 1) * 100 * MIB, "wall_s": 10.0} for i in range(10)
    }
    behaviour["c9"]["exit"] = 3
    run(tmp_path, FakeDocker(behaviour=behaviour))
    s = summary(tmp_path, "f02")
    assert s["outcomes"] == {"COMPLETED": 9, "FAILED": 1}
    assert s["memory_peak_mib"]["p50"] == 500.0
    assert s["memory_peak_mib"]["p95"] == 1000.0
    assert s["allocated_cpu_hours"] == pytest.approx(10 * 10 * 2 / 3600, abs=1e-4)
    assert s["cgroup_cpu_hours"] == pytest.approx(15 / 3600, abs=1e-4)
    assert s["wall_s"]["total"] == 100.0
    assert "DEVELOPMENT" in s["maturity"]


def test_dry_run_validates_and_estimates_without_launching(tmp_path):
    make_family(tmp_path, "fa", cases(4, estimate_wall_s=100))
    make_family(tmp_path, "fb", cases(2, estimate_cpu_s=400))
    write_plan(
        tmp_path,
        [
            family_entry("fa"),
            family_entry("fb", case_limits={"cpus": 2, "wall_timeout_s": 600}),
        ],
        cpus=4,
    )
    plan = br.load_plan(tmp_path / "plan.json")
    docker = FakeDocker()
    host = {"boot_unix": time.time()}
    report = br.dry_run(plan, tmp_path / "out", docker, host)
    assert docker.calls == [] and not (tmp_path / "out").exists()
    est = report["estimate"]
    # Same priority and reservation: the families interleave in manifest
    # order (fa c0, fb c0, fa c1 fill 4 CPUs). At 100 s first-fit backfills
    # fa c2, fa c3 into the freed single CPUs, so fb c1 (2 CPUs) waits for
    # fb c0 and runs 200-400 s: the runner's own packing, starvation aside.
    assert est["makespan_s"] == 400.0
    assert est["families"]["fb"]["allocated_cpu_hours"] == pytest.approx(
        800 / 3600, abs=1e-3
    )
    assert est["fits_machine_cap"]


def test_cli_dry_run_skip_image_check(tmp_path, capsys):
    make_family(tmp_path, "f02", cases(1))
    write_plan(tmp_path, [family_entry("f02")])
    args = ["--plan", str(tmp_path / "plan.json"), "--out", str(tmp_path / "out")]
    assert (
        br.main([*args, "--dry-run", "--skip-image-check"], FakeDocker(identities={}))
        == 0
    )
    assert json.loads(capsys.readouterr().out)["images_checked"] is False


# ----------------------------------------------------------- docker real


def test_docker_command_enforces_isolation_and_caps(tmp_path):
    spec = {
        "plan_id": "p", "family": "f17", "case": "c0", "name": "cb-p-f17-c0",
        "image": IMG, "command": "./Allrun", "shell": "bash", "entrypoint": "image",
        "env": {"OMP_NUM_THREADS": "1"}, "cpus": 4, "memory_bytes": 8 * 1024**3,
        "pids": 256, "work_dir": "/w", "meta_dir": "/m",
    }  # fmt: skip
    cmd = br.DockerCli.command(spec)
    joined = " ".join(cmd)
    for flag in (
        "--network none",
        "--read-only",
        "--cpus 4",
        f"--memory {8 * 1024**3}",
        f"--memory-swap {8 * 1024**3}",
        "--pids-limit 256",
        "--cap-drop ALL",
        "-v /w:/case",
        "-e OMP_NUM_THREADS=1",
        "-e CARBON_SHELL=bash",
    ):
        assert flag in joined
    assert cmd[-4:-2] == [IMG, "sh"] and "--entrypoint" not in cmd
    spec["entrypoint"] = "override"
    assert br.DockerCli.command(spec)[-5:-2] == ["--entrypoint", "sh", IMG]


def test_cgroup_stats_parse_v1_and_v2(tmp_path):
    v2 = tmp_path / "v2.txt"
    v2.write_text(
        "memory_peak_bytes 1048576\ncgroup_version 2\ncpu_usage_usec 2500000\n"
    )
    v1 = tmp_path / "v1.txt"
    v1.write_text(
        "memory_peak_bytes 2097152\ncgroup_version 1\ncpu_usage_nsec 1500000000\n"
    )
    assert br._parse_cgroup(v2) == {
        "cgroup_cpu_s": 2.5,
        "cgroup_memory_peak_bytes": 1048576,
        "cgroup_version": 2,
    }
    assert br._parse_cgroup(v1)["cgroup_cpu_s"] == 1.5
    assert br._parse_cgroup(tmp_path / "absent")["cgroup_cpu_s"] is None


# ------------------------------------------------- triage_run unchanged


def test_triage_run_dry_run_keeps_its_caps(tmp_path, capsys):
    fdir = make_family(tmp_path, "f02", cases(1))
    manifest = json.loads((fdir / "manifest.json").read_text())
    ledger = tmp_path / "ledger.jsonl"
    triage_run.run(fdir, "f02", ledger, manifest["image"], dry_run=True)
    printed = capsys.readouterr().out
    assert "--cpus 8 --memory 24g --memory-swap 24g --pids-limit 16" in printed
    assert "--network none --read-only" in printed and not ledger.exists()
    with pytest.raises(SystemExit, match="image differs"):
        triage_run.run(fdir, "f02", ledger, OTHER, dry_run=True)


def test_ledger_rows_are_versioned(tmp_path):
    ledger = br.Ledger(tmp_path / "l.jsonl")
    ledger.append({"event": "X"})
    assert (
        json.loads(Path(tmp_path / "l.jsonl").read_text())["schema"] == br.LEDGER_SCHEMA
    )


def test_template_plan_has_the_schema_shape_and_fails_closed(tmp_path):
    root = Path(__file__).resolve().parents[2]
    path = root / "docs/development/challenge_pipeline/bulk-run/run-plan.template.json"
    template = json.loads(path.read_text())
    with pytest.raises(br.PlanError) as err:  # placeholders never validate
        br.load_plan(path)
    assert any("node_hours" in p for p in err.value.problems)
    # With every placeholder filled, the template's keys all validate.
    for fam in template["families"]:
        make_family(tmp_path / "decks", fam["family"], cases(1))
        fam["image"] = IMG
        fam["ceilings"] = {"launches": 10, "cpu_hours": 10}
        for key, value in fam["case_limits"].items():
            if isinstance(value, str):
                fam["case_limits"][key] = 2
    template["machine"].update(node_hours=4, eur_cap=10, eur_per_hour=1.5)
    (tmp_path / "plan.json").write_text(json.dumps(template))
    plan = br.load_plan(tmp_path / "plan.json")
    assert [f.name for f in plan.families] == ["f02", "f08", "f13", "f17", "f06"]
