"""bulk_run.py --executor native: cases run directly on the host (a RunPod CPU
pod has no Docker). Real processes, seconds of CPU, no network."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_bulk_run import cases, family_entry, make_family, rows, write_plan

from scripts.dev.reference_packages import bulk_run as br

MIB = 1024**2
PY = sys.executable
NATIVE = {
    "version_command": "echo SOLVER v 9.9 ready",
    "version_expect": "SOLVER v 9.9",
}


def _run(argv, tmp_path, timeout=10.0, cancel=None, **kw):
    return br.run_native(
        argv, tmp_path, dict(os.environ), timeout, cancel or threading.Event(), **kw
    )


# ------------------------------------------------------------- run_native


def test_exit_code_cpu_and_peak_memory_are_measured(tmp_path):
    burn = "import time\nt=time.process_time()\nwhile time.process_time()-t<0.4: pass\nb=bytearray(150*2**20)\nb[::4096]=b'x'*len(b[::4096])"
    r = _run([PY, "-c", burn + "\nraise SystemExit(3)"], tmp_path)
    assert r["exit"] == 3 and r["stop_reason"] == "exit" and r["signal"] is None
    assert r["rusage_cpu_s"] >= 0.3
    assert r["rusage_maxrss_bytes"] >= 150 * MIB
    assert r["wall_s"] < 10


def test_timeout_kills_the_whole_group_and_is_reported(tmp_path):
    marker = tmp_path / "survived"
    start = time.monotonic()
    r = _run(["sh", "-c", f"(sleep 3; touch {marker}) & sleep 60"], tmp_path, 2.0)
    assert r["stop_reason"] == "timeout" and time.monotonic() - start < 8
    time.sleep(3.5)
    assert not marker.exists()  # the background child died with its group


def test_cancel_stops_the_case(tmp_path):
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    r = _run(["sleep", "60"], tmp_path, 60.0, cancel)
    assert r["stop_reason"] == "cancel" and r["wall_s"] < 30


def test_address_space_limit_is_enforced(tmp_path):
    grab = "b=bytearray(600*2**20)"
    r = _run([PY, "-c", grab], tmp_path, memory_bytes=300 * MIB)
    assert r["exit"] != 0 and r["rlimit_as_bytes"] == 300 * MIB
    ok = _run([PY, "-c", grab], tmp_path)
    assert ok["exit"] == 0


def test_rss_watchdog_kills_a_group_past_its_limit(tmp_path):
    hold = (
        "import time\nb=bytearray(400*2**20)\nb[::4096]=b'x'*len(b[::4096])\n"
        "time.sleep(30)"
    )
    r = _run([PY, "-c", hold], tmp_path, 60.0, rss_limit_bytes=100 * MIB)
    assert r["stop_reason"] == "memory" and r["exit"] == 128 + signal.SIGKILL
    assert r["sampled_group_rss_peak_bytes"] > 100 * MIB


def test_cases_are_pinned_to_their_cores(tmp_path):
    core = min(os.sched_getaffinity(0))
    out = tmp_path / "n"
    _run(
        [
            PY,
            "-c",
            f"import os;open({str(out)!r},'w').write(str(sorted(os.sched_getaffinity(0))))",
        ],
        tmp_path,
        cpus={core},
    )
    assert out.read_text() == str([core])


# ------------------------------------------------------- through BulkRun


def native_plan(tmp_path, native=NATIVE, families=("fx",), **case_kw):
    entries = []
    for fam in families:
        make_family(tmp_path, fam, case_kw.get("cases") or cases(3))
        entries.append(family_entry(fam, native=native))
    return write_plan(tmp_path, entries, cpus=2, memory_gib=2)


def test_native_run_keeps_ledger_semantics_and_drops_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "must-not-leak")
    monkeypatch.setenv("PROBE_TOKEN", "must-not-leak")
    spec = [
        ("ok", "primary", {}),
        ("bad", "controls", {}),
    ]
    make_family(tmp_path, "fx", spec)
    manifest = json.loads((tmp_path / "fx/manifest.json").read_text())
    manifest["cases"][0]["command"] = "cat case.sif > out.txt; env > env.txt"
    manifest["cases"][1]["command"] = "echo broken > solver.log; exit 125"
    (tmp_path / "fx/manifest.json").write_text(json.dumps(manifest))
    write_plan(tmp_path, [family_entry("fx", native=NATIVE)], cpus=2, memory_gib=2)
    out = tmp_path / "out"
    code = br.main(
        ["--plan", str(tmp_path / "plan.json"), "--out", str(out), "--executor", "native",
         "--poll-s", "0.05"]
    )  # fmt: skip
    assert code == 0
    work = out / "cases/fx/ok/work"
    assert (work / "out.txt").read_text() == "deck fx/ok\n"
    env = (work / "env.txt").read_text()
    assert "must-not-leak" not in env and "CARBON_BULK_PLAN=test-plan" in env
    assert not (out / "cases/fx/ok/tmp").exists()  # scratch HOME removed
    finished = {r["case"]: r for r in rows(tmp_path, "FINISHED")}
    assert finished["ok"]["outcome"] == "COMPLETED"
    # Exit 125 is the case's own exit natively, not a Docker create failure.
    assert finished["bad"]["outcome"] == "FAILED"
    for r in finished.values():
        assert r["executor"] == "native" and r["cgroup_cpu_s"] is None
        assert r["rusage_cpu_s"] is not None and r["rusage_maxrss_bytes"] > 0
    started = rows(tmp_path, "STARTED")
    assert {r["executor"] for r in started} == {"native"}
    run_start = rows(tmp_path, "RUN_START")[0]
    assert (
        run_start["docker"]["environment_checks"]["fx"]["line"] == "SOLVER v 9.9 ready"
    )
    summary = json.loads((out / "summary/fx.json").read_text())
    assert summary["executors"] == ["native"]
    assert summary["memory_peak_mib"]["cases_with_peak"] == 2
    # No retry: a second run launches nothing.
    assert (
        br.main(
            [
                "--plan",
                str(tmp_path / "plan.json"),
                "--out",
                str(out),
                "--executor",
                "native",
            ]
        )
        == 0
    )
    assert len(rows(tmp_path, "STARTED")) == 2


def test_environment_check_refuses_before_any_launch(tmp_path, capsys):
    native_plan(
        tmp_path, native={"version_command": "echo v1.0", "version_expect": "v2.0"}
    )
    out = tmp_path / "out"
    code = br.main(
        [
            "--plan",
            str(tmp_path / "plan.json"),
            "--out",
            str(out),
            "--executor",
            "native",
        ]
    )
    assert code == 2 and "environment check failed" in capsys.readouterr().err
    assert not (out / "ledger.jsonl").exists()


def test_native_mode_needs_a_native_block_per_family(tmp_path, capsys):
    make_family(tmp_path, "fx", cases(1))
    write_plan(tmp_path, [family_entry("fx")], cpus=2, memory_gib=2)
    code = br.main(
        ["--plan", str(tmp_path / "plan.json"), "--out", str(tmp_path / "o"),
         "--executor", "native"]
    )  # fmt: skip
    assert code == 2 and "no native block" in capsys.readouterr().err


def test_native_block_is_validated(tmp_path):
    make_family(tmp_path, "fx", cases(1))
    write_plan(
        tmp_path,
        [
            family_entry(
                "fx", native={"version_command": "x", "memory_cap": "cgroup", "y": 1}
            )
        ],
    )
    with pytest.raises(br.PlanError) as err:
        br.load_plan(tmp_path / "plan.json")
    text = " ".join(err.value.problems)
    assert "version_expect is required" in text
    assert "memory_cap" in text and "unknown keys ['y']" in text


def test_native_case_timeout_is_censored_and_measured(tmp_path):
    make_family(tmp_path, "fx", [("slow", "primary", {})])
    manifest = json.loads((tmp_path / "fx/manifest.json").read_text())
    manifest["cases"][0]["command"] = "sleep 60"
    (tmp_path / "fx/manifest.json").write_text(json.dumps(manifest))
    entry = family_entry("fx", native=NATIVE, case_limits={"wall_timeout_s": 2})
    write_plan(tmp_path, [entry], cpus=2, memory_gib=2, min_case_window_s=1)
    plan = br.load_plan(tmp_path / "plan.json")
    executor = br.NativeExecutor(out=tmp_path / "out")
    br.check_native(plan, executor)
    (tmp_path / "out").mkdir()
    host = {"nproc": 2, "mem_total_bytes": 4 * 1024**3, "boot_unix": time.time()}
    runner = br.BulkRun(
        plan, tmp_path / "out", executor, host=host, poll_s=0.05, log=lambda m: None
    )
    runner.execute()
    (row,) = rows(tmp_path, "FINISHED")
    assert row["outcome"] == "CENSORED_CASE_TIMEOUT" and row["wall_s"] < 10


def test_kill_stale_kills_only_this_plans_groups(tmp_path):
    def start(plan_id, case):
        meta = tmp_path / "cases/fx" / case / "meta"
        meta.mkdir(parents=True)
        env = dict(os.environ, CARBON_BULK_PLAN=plan_id)
        proc = subprocess.Popen(["sleep", "60"], env=env, start_new_session=True)
        (meta / "native.pgid").write_text(f"{proc.pid}\n")
        return proc

    mine, other = start("p1", "a"), start("p2", "b")
    try:
        killed = br.NativeExecutor(out=tmp_path).kill_stale("p1")
        assert killed == [mine.pid]
        assert mine.wait(timeout=5) == -signal.SIGKILL
        assert other.poll() is None
    finally:
        other.kill()
        other.wait()


def test_docker_stays_the_default_executor(tmp_path, monkeypatch, capsys):
    made = []

    class Spy:
        def __init__(self):
            made.append(self)

    monkeypatch.setattr(br, "DockerCli", Spy)
    make_family(tmp_path, "fx", cases(1))
    write_plan(tmp_path, [family_entry("fx")])
    code = br.main(
        ["--plan", str(tmp_path / "plan.json"), "--out", str(tmp_path / "o"),
         "--dry-run", "--skip-image-check"]
    )  # fmt: skip
    assert code == 0 and len(made) == 1
    assert json.loads(capsys.readouterr().out)["executor"] == "docker"
