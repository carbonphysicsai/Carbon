"""Reference solvers on RunPod CPU pods (OWNER-RUNPOD-SOLVER-READINESS-01).

No test reaches RunPod or the network. The pod side (pod_phase.py and its
docker shim) runs real processes in a temporary repository; the operator
side (pod_control's reference-solvers campaign) runs against the in-memory
RunPod (`carbon.agent_campaign.graphite.pods.InMemoryRunPod`).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.agent_campaign.graphite import pods as graphite_pods
from scripts.dev.reference_packages import docker_shim
from scripts.dev.reference_packages import pod_phase as pp

REPOSITORY = Path(__file__).resolve().parents[2]
SHIM = REPOSITORY / "scripts/dev/reference_packages/docker_shim.py"
PLANS = REPOSITORY / "docs/development/evidence/reference-solvers-2026-10-15/plans"


@pytest.mark.parametrize("exit_code", [0, 130])
def test_f13_container_bounds_library_threads_and_retains_exit_outcome(
    tmp_path, monkeypatch, exit_code
):
    from scripts.dev.reference_packages.elmer import f13_proof

    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(f13_proof.subprocess, "run", run)
    result = f13_proof._container(
        "pinned-mesher", tmp_path, "python3 make_mesh.py", 1, "3g", "mesher", 60
    )
    (argv,) = calls
    environment = dict(
        argv[i + 1].split("=", 1) for i, value in enumerate(argv) if value == "-e"
    )
    assert environment["OPENBLAS_NUM_THREADS"] == environment["OMP_NUM_THREADS"] == "1"
    assert argv[argv.index("--pids-limit") + 1] == "16"
    assert argv[argv.index("--cpus") + 1] == "1"
    assert argv[argv.index("--network") + 1] == "none"
    assert result["exit"] == exit_code
    assert result["outcome"] == ("COMPLETED" if exit_code == 0 else "FAILED")


def _load_pod_control(name):
    spec = importlib.util.spec_from_file_location(
        name, REPOSITORY / "scripts/dev/exam_design/runpod/pod_control.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_funded_operator_phase_keeps_historical_accounting_separate(
    tmp_path, monkeypatch
):
    pc = _load_pod_control("phase_accounting")
    monkeypatch.setattr(pc, "REPO", str(tmp_path / "repo"))
    monkeypatch.setattr(pc, "STATE_DIR", str(tmp_path / "operator"))
    config = tmp_path / "operator/campaigns.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps({"ceilings_usd": {"reference-solvers": 25}, "balance_floor_usd": 15})
    )
    monkeypatch.setattr(pc, "account", lambda: {"clientBalance": 50})
    pc.use_campaign("reference-solvers", "resume-fixture")
    phase_ledger = Path(pc.PRIVATE_LEDGER)
    assert "phases/resume-fixture" in Path(pc.LEDGER).as_posix()
    assert pc.ACTIVE.endswith("-resume-fixture")
    pc.cmd_start(SimpleNamespace(cap_usd=25))
    assert pc.campaign_cap() == 25 and pc.committed_spend() == 0
    with pytest.raises(SystemExit, match="already started"):
        pc.cmd_start(SimpleNamespace(cap_usd=25))
    pc.use_campaign("reference-solvers")
    assert Path(pc.PRIVATE_LEDGER) != phase_ledger
    assert pc.OPERATOR_PHASE is None
    historical = Path(pc.LEDGER)
    historical.parent.mkdir(parents=True, exist_ok=True)
    historical.write_text(
        json.dumps({"utc": "fixture", "event": "campaign_start"}) + "\n"
    )
    with pytest.raises(SystemExit, match="lacks"):
        pc.ledger_rows()
    assert phase_ledger.exists()


@pytest.mark.parametrize(
    "name,phase",
    [
        ("reference-solvers", "../escape"),
        ("reference-solvers", ""),
        ("reference-solvers", "a/b"),
        ("ev4", "resume-fixture"),
    ],
)
def test_operator_phase_rejects_path_escape_and_other_campaigns(name, phase):
    pc = _load_pod_control("invalid_phase")
    with pytest.raises(SystemExit, match="operator phase"):
        pc.use_campaign(name, phase)


# ------------------------------------------------------------ docker shim


def shim(args, tmp_path, images=(), cwd=None):
    env = dict(
        os.environ,
        CARBON_DOCKER_SHIM=json.dumps(
            {
                "images": list(images),
                "identity": "native:test",
                "log": str(tmp_path / "shim.jsonl"),
            }
        ),
    )
    return subprocess.run(
        [sys.executable, "-I", str(SHIM), *args],
        env=env,
        capture_output=True,
        text=True,
        cwd=cwd or tmp_path,
        check=False,
    )


def test_shim_runs_a_container_command_natively_with_paths_mapped(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "in.txt").write_text("deck\n")
    done = shim(
        ["run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp", "--cpus", "1",
         "--memory=3g", "--user", "0:0", "-e", "MARK=yes", "-v", f"{case}:/w", "-w", "/w",
         "mesh-image@sha256:" + "a" * 64, "sh", "-c",
         'pwd > where.txt; echo "$MARK" > mark.txt; cat "$0" > copy.txt', "/w/in.txt"],
        tmp_path,
        images=["mesh-image@sha256:" + "a" * 64],
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    assert (case / "where.txt").read_text().strip() == str(case)
    assert (case / "mark.txt").read_text().strip() == "yes"
    assert (case / "copy.txt").read_text() == "deck\n"
    (row,) = [json.loads(x) for x in (tmp_path / "shim.jsonl").read_text().splitlines()]
    assert row["event"] == "run" and "--network=none" in row["ignored"]
    # The pinned solver images' WORKDIR is /case: a run naming no -w uses it.
    done = shim(
        ["run", "--rm", "-v", f"{case}:/case", "native", "sh", "-c", "pwd"], tmp_path
    )
    assert done.stdout.strip() == str(case)


@pytest.mark.parametrize(
    "args",
    [
        ["run", "-v", "/x:/case", "someone/else@sha256:" + "b" * 64, "true"],
        ["run", "--privileged", "-v", "/x:/case", "native", "true"],
        ["run", "-v", "named-volume:/case", "native", "true"],
        ["run", "-v", "/x:/elsewhere", "native", "true"],
        ["run", "-v", "/x:/case", "native"],
        ["ps"],
        ["exec", "c", "true"],
    ],
)
def test_shim_refuses_what_it_cannot_provide(args, tmp_path):
    done = shim(args, tmp_path)
    assert done.returncode == 125 and "native shim" in done.stderr
    row = json.loads((tmp_path / "shim.jsonl").read_text().splitlines()[-1])
    assert row["event"] == "refused"


def test_shim_inspect_names_the_native_environment_not_an_image_id(tmp_path):
    done = shim(["image", "inspect", "native", "--format", "{{.Id}}"], tmp_path)
    assert done.returncode == 0 and done.stdout.strip() == "native:test"
    done = shim(["image", "inspect", "--format", "{{json .}}", "native"], tmp_path)
    assert json.loads(done.stdout)["Id"] == "native:test"
    assert shim(["image", "inspect", "other:1"], tmp_path).returncode == 1


def test_shim_parse_maps_entrypoint_and_env():
    run = docker_shim.plan_run(
        ["--entrypoint", "python3", "-v", "/h:/w", "-w", "/w/sub", "native", "make.py"],
        {},
    )
    assert run["argv"] == ["python3", "make.py"] and run["cwd"] == "/h/sub"


# -------------------------------------------------------------- pod phase


def _sha(data):
    return hashlib.sha256(data).hexdigest()


FREEZE = r"""
import hashlib, json, sys
from pathlib import Path
out = Path(sys.argv[1]); variant = sys.argv[2]
cases = []
for name, body in (("ok-a", "a"), ("ok-b", "b"), ("ctl", "c")):
    d = out / "fx" / name; d.mkdir(parents=True)
    text = body + ("-changed" if variant == "drift" and name == "ok-b" else "") + "\n"
    (d / "case.sif").write_text(text)
    cases.append({"family": "fx", "case": name,
                  "reservation": "controls" if name == "ctl" else "primary",
                  "command": "cat case.sif > out.txt; echo log > solver.log",
                  "files": {"case.sif": hashlib.sha256(text.encode()).hexdigest()}})
(out / "manifest.json").write_text(json.dumps({"schema": "carbon.reference-triage.frozen-decks.v1",
                                               "image": "sha256:" + "a" * 64, "cases": cases}))
"""


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    (root / "tools/freeze.py").write_text(FREEZE)
    # The pinned manifest is the freeze's own output for the clean variant.
    pin_dir = tmp_path / "pin"
    subprocess.run(
        [sys.executable, root / "tools/freeze.py", pin_dir, "clean"], check=True
    )
    (root / "pins").mkdir()
    shutil.copyfile(pin_dir / "manifest.json", root / "pins/fx.json")
    monkeypatch.setattr(pp, "ROOT", root)
    monkeypatch.setitem(
        pp.KINDS,
        "fake",
        {
            "native": {
                "version_command": "echo FAKESOLVER 1.0",
                "version_expect": "FAKESOLVER 1.0",
            },
            "solvers": ["sh"],
            "images": [],
        },
    )
    return root


def bulk_step(name, variant, select=None):
    return {
        "name": name,
        "type": "bulk",
        "manifest": "pins/fx.json",
        "freeze": {"argv": ["python3", "tools/freeze.py", "{decks}", variant]},
        "select": select or {"families": ["fx"]},
        "families": {
            "fx": {
                "case_limits": {
                    "cpus": 1,
                    "memory_gib": 1,
                    "pids": 64,
                    "wall_timeout_s": 600,
                },
                "ceilings": {"launches": 10, "cpu_hours": 1},
            }
        },
    }


def write_plan(root, steps):
    plan = {
        "schema": pp.PLAN_SCHEMA,
        "plan_id": "fake-smoke",
        "kind": "fake",
        "authority": "unit test",
        "steps": steps,
    }
    (root / "plan.json").write_text(json.dumps(plan))
    return "plan.json"


def config(plan):
    now = time.time()
    return {
        "pod_plan": plan,
        "vcpu": 2,
        "memory_gib": 3,
        "deadline_epoch": now + 3600,
        "stop_admitting_epoch": now + 3000,
    }


def test_the_pod_phase_runs_scripts_and_verified_bulk_steps(fake_repo, tmp_path):
    script = (
        "mkdir -p {work}/c && docker run --rm --network none -v {work}/c:/case native"
        " sh -c 'echo ran > out.txt' && cp {work}/c/out.txt {out}/out.txt"
        ' && echo \'{{"test": "t1", "pass": true}}\''
    )
    plan = write_plan(
        fake_repo,
        [
            {"name": "smoke", "type": "script", "argv": ["sh", "-c", script],
             "timeout_s": 60, "jsonl_all": {"pass": True}},
            {**bulk_step("decks-ok", "clean", {"reservations": ["primary"]}),
             "observe": {"argv": ["sh", "-c", "cat {bulk}/cases/fx/*/work/out.txt > {out}/observed.txt"]}},
            bulk_step("decks-drift", "drift"),
            {"name": "fails", "type": "script", "argv": ["sh", "-c", "exit 4"]},
        ],
    )  # fmt: skip
    out = tmp_path / "out"
    code = pp.run("fake", out, config(plan), work_root=str(tmp_path / "work"))
    assert code == 1  # a refused and a failing step
    summary = json.loads((out / "pod-phase.json").read_text())
    status = {s["name"]: s["status"] for s in summary["steps"]}
    assert status == {
        "smoke": "PASS",
        "decks-ok": "PASS",
        "decks-drift": "REFUSED",
        "fails": "FAIL",
    }
    assert (out / "smoke/out.txt").read_text().strip() == "ran"
    shim_log = (out / "smoke/docker-shim.jsonl").read_text()
    assert '"image": "native"' in shim_log
    # The clean freeze reproduced every pinned file and ran natively.
    ok = json.loads((out / "decks-ok/deck-verification.json").read_text())
    assert (
        ok["selected"] == 2
        and ok["selected_refused"] == []
        and ok["all_cases_matching"] == 3
    )
    finished = [
        json.loads(x)
        for x in (out / "decks-ok/ledger.jsonl").read_text().splitlines()
        if '"FINISHED"' in x
    ]
    assert sorted(r["case"] for r in finished) == ["ok-a", "ok-b"]
    assert {r["outcome"] for r in finished} == {"COMPLETED"}
    assert {r["executor"] for r in finished} == {"native"}
    assert (out / "decks-ok/cases/fx/ok-a/work/out.txt").read_text() == "a\n"
    assert (out / "decks-ok/cases/fx/ok-a/meta/outputs.json").exists()
    # The observe command saw the full bulk output before the work dir went.
    assert (out / "decks-ok/observed.txt").read_text().split() == ["a", "b"]
    assert json.loads((out / "decks-ok/step.json").read_text())["observe_exit"] == 0
    plan_doc = json.loads((out / "decks-ok/bulk-plan.json").read_text())
    assert plan_doc["machine"]["cpus"] <= 2 and plan_doc["machine"]["memory_gib"] <= 3
    assert plan_doc["families"][0]["native"]["version_expect"] == "FAKESOLVER 1.0"
    # A drifted deck refuses the step before anything runs.
    drift = json.loads((out / "decks-drift/deck-verification.json").read_text())
    assert drift["selected_refused"] == ["fx/ok-b"]
    assert not (out / "decks-drift/ledger.jsonl").exists()
    step = json.loads((out / "decks-drift/step.json").read_text())
    assert "differ from the manifest" in step["why"]
    env = json.loads((out / "pod-environment.json").read_text())
    assert env["kind"] == "fake" and env["usable_cpus"] <= 2


def test_the_pod_phase_skips_steps_past_its_admission_deadline(fake_repo, tmp_path):
    plan = write_plan(fake_repo, [{"name": "late", "type": "script", "argv": ["true"]}])
    cfg = config(plan) | {"stop_admitting_epoch": time.time() + 30}
    assert pp.run("fake", tmp_path / "out", cfg, work_root=str(tmp_path / "w")) == 1
    summary = json.loads((tmp_path / "out/pod-phase.json").read_text())
    assert summary["steps"] == [
        {"name": "late", "status": "SKIPPED_DEADLINE", "wall_s": None}
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "elmer"},
        {"steps": [{"name": "x", "type": "bulk", "manifest": "docs/private/m.json",
                    "decks": "d", "families": {"f": {}}}]},
        {"steps": [{"name": "x", "type": "shell", "argv": ["true"]}]},
        {"steps": []},
    ],
)  # fmt: skip
def test_the_pod_phase_refuses_bad_or_non_public_plans(fake_repo, change):
    plan = {
        "schema": pp.PLAN_SCHEMA,
        "kind": "fake",
        "steps": [{"name": "a", "type": "script", "argv": ["true"]}],
    } | change
    (fake_repo / "p.json").write_text(json.dumps(plan))
    with pytest.raises(SystemExit, match="refusing"):
        pp.load_plan(fake_repo / "p.json", "fake")


# --------------------------------------- the committed plans and the kinds


def test_committed_pod_plans_are_valid_public_and_reference_tracked_files():
    plans = sorted(PLANS.glob("*.json"))
    assert {json.loads(p.read_text())["kind"] for p in plans} == {
        "elmer",
        "calculix",
        "openfoam2506",
    }
    for path in plans:
        doc = pp.load_plan(path, json.loads(path.read_text())["kind"])
        for step in doc["steps"]:
            if step["type"] == "bulk":
                manifest = json.loads((REPOSITORY / step["manifest"]).read_text())
                assert manifest["schema"] == "carbon.reference-triage.frozen-decks.v1"
                picked = [
                    c for c in manifest["cases"] if pp.selected(c, step.get("select"))
                ]
                assert picked, (path.name, step["name"])
                for fam, spec in step["families"].items():
                    assert {"cpus", "memory_gib", "pids", "wall_timeout_s"} <= set(
                        spec["case_limits"]
                    )
                    assert fam in {c["family"] for c in picked}


def test_each_solver_kind_replays_its_locked_dockerfile():
    pc = _load_pod_control("pod_control_kinds")
    assert set(pc.SOLVER_KINDS) == set(pp.KINDS)
    assert set(pc.CAMPAIGNS["reference-solvers"]["solver_kinds"]) == set(
        pc.SOLVER_KINDS
    )
    for name in ("elmer", "calculix"):
        base = REPOSITORY / "scripts/dev/reference_packages" / name
        lock = json.loads((base / "sources.lock.json").read_text())
        dockerfile = (base / "Dockerfile").read_text()
        kind = pc.SOLVER_KINDS[name]
        assert kind["image"].split("@")[1] == lock["base_image"].split("@")[1]
        assert kind["image"].startswith("debian:trixie-")  # tag beside the digest
        snapshot = re.search(r"ARG SNAPSHOT=(\S+)", dockerfile).group(1)
        assert f"deb [check-valid-until=no] {snapshot} trixie main" in kind["setup"]
        for source in lock["sources"]:
            assert source["url"] in kind["setup"] and source["sha256"] in kind["setup"]
        for package in lock["build_packages"]:
            assert f" {package}" in kind["setup"], (name, package)
        for line in re.findall(r"(sed -i .*?) \\?\n", dockerfile):
            line = line.split(" && ")[0]
            assert line.strip() in kind["setup"], line
        for option in lock.get("cmake_options", []):
            assert option in kind["setup"]
        assert "ENV_DIR" not in kind["setup"] and "$(nproc)" in kind["setup"]
    motor = (REPOSITORY / "scripts/dev/motor/reference/Dockerfile").read_text()
    arg = dict(re.findall(r"^ARG (\w+)=(\S+)$", motor, flags=re.MULTILINE))
    for name in ("elmer", "calculix"):
        assert arg["GMSH_URL"] in pc.SOLVER_KINDS[name]["setup"]
        assert arg["GMSH_SHA256"] in pc.SOLVER_KINDS[name]["setup"]
    assert (
        pp.MOTOR_MESH_IMAGE.split(":")[-1]
        in (REPOSITORY / "scripts/dev/reference_packages/elmer/f13_deck.py").read_text()
    )
    openfoam = pc.SOLVER_KINDS["openfoam2506"]
    assert openfoam["image"].startswith("opencfd/openfoam-default:2506@sha256:")
    assert "openfoam2506/etc/bashrc" in openfoam["setup"]


def test_what_a_solver_pod_ships_is_enough_to_start_its_tools(tmp_path):
    """A pod receives only SOLVER_SHIP and the plans' tracked paths."""
    pc = _load_pod_control("pod_control_ship2")
    for prefix in pc.SOLVER_SHIP:
        source = REPOSITORY / prefix
        files = (
            [source]
            if source.is_file()
            else sorted(
                p
                for p in source.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts
            )
        )
        for path in files:
            target = tmp_path / path.relative_to(REPOSITORY)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    for module in (
        "scripts.dev.reference_packages.pod_phase",
        "scripts.dev.reference_packages.bulk_run",
        "scripts.dev.reference_packages.elmer.triage_freeze",
        "scripts.dev.reference_packages.elmer.f02_controls",
    ):
        done = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                f"import sys; sys.path.insert(0, '.'); import {module}",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, (module, done.stderr[-1500:])
    done = subprocess.run(
        [
            sys.executable,
            "-I",
            "scripts/dev/reference_packages/calculix/f08_freeze.py",
            "--help",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-1500:]


# ------------------------------------- pod_control with the in-memory RunPod


class PricedRunPod(graphite_pods.InMemoryRunPod):
    """The in-memory RunPod, with a Secure price on each CPU stock answer."""

    def __init__(self, prices, **kw):
        super().__init__(**kw)
        self.prices = prices

    def _answer(self, method, url, body):
        status, payload = super()._answer(method, url, body)
        if "cpuFlavors" in str(body):
            instance = re.search(
                r'instanceId:"([A-Za-z0-9-]+)"', json.loads(body)["query"]
            ).group(1)
            flavor = instance.split("-")[0]
            price = self.prices.get(flavor)
            payload["data"]["cpuFlavors"][0]["specifics"] = {
                "stockStatus": "High" if price else None,
                "securePrice": price,
            }
        return status, payload


@pytest.fixture
def operator(tmp_path, monkeypatch):
    pc = _load_pod_control("pod_control_solvers")
    state = tmp_path / "state"
    state.mkdir()
    (state / "campaigns.json").write_text(
        json.dumps({"ceilings_usd": {"reference-solvers": 25}, "balance_floor_usd": 15})
    )
    monkeypatch.setattr(pc, "STATE_DIR", str(state))
    monkeypatch.setattr(pc, "REPO", str(tmp_path / "repo"))
    pc.use_campaign("reference-solvers")
    plan_dir = tmp_path / "repo/plans"
    plan_dir.mkdir(parents=True)
    (plan_dir / "smoke.json").write_text(
        json.dumps({"schema": pp.PLAN_SCHEMA, "kind": "elmer", "steps": []})
    )
    rp = PricedRunPod({"cpu3c": 0.24, "cpu5c": 0.28, "cpu3m": 0.44}, balance=43.0)

    def req(method, url, body=None, headers=None, timeout=60):
        data = json.dumps(body).encode() if body is not None else None
        return rp.transport(
            method,
            url,
            body=data,
            headers={"Authorization": "Bearer " + graphite_pods.CHECK_KEY},
            timeout=timeout,
        )

    monkeypatch.setattr(pc, "_req", req)
    monkeypatch.setattr(pc, "ref_is_pushed", lambda ref: True)
    monkeypatch.setattr(pc, "ship_paths", lambda ref, prefixes: ["scripts/a.py"])
    monkeypatch.setattr(
        pc, "code_manifest", lambda ref, paths: {p: "0" * 64 for p in paths}
    )
    monkeypatch.setattr(pc, "ca_bundle_gz_b64", lambda: "")
    watchdogs = []
    monkeypatch.setattr(
        pc.subprocess, "Popen", lambda argv, **kw: watchdogs.append(argv)
    )
    real_run = subprocess.run

    def git(argv, **kw):
        if argv[:1] == ["git"] and "ls-tree" in argv:
            return SimpleNamespace(
                stdout="plans/smoke.json\nscripts/a.py\n", returncode=0
            )
        if argv[:1] == ["git"]:
            return SimpleNamespace(stdout="a" * 40 + "\n", returncode=0)
        return real_run(argv, **kw)

    monkeypatch.setattr(pc.subprocess, "run", git)
    monkeypatch.setattr(pc.time, "sleep", lambda s: None)

    def proxy(path, timeout=60, pod=None):
        pod = pc.pick_pod(pod)
        return rp.http(
            f"https://{pod}-8000.proxy.runpod.net{path}", pc.token_for(pod), timeout
        )

    monkeypatch.setattr(pc, "_proxy", proxy)
    pc.main(["--campaign", "reference-solvers", "start", "--cap-usd", "25"])
    return SimpleNamespace(pc=pc, rp=rp, watchdogs=watchdogs, tmp=tmp_path)


def dispatch(op, *extra):
    op.pc.main(
        ["--campaign", "reference-solvers", "dispatch-solver", "elmer",
         "--pod-plan", "plans/smoke.json", "--vcpu", "16", *extra]
    )  # fmt: skip


def test_a_solver_pod_is_created_cheapest_first_with_a_deadline(operator):
    op = operator
    before = time.time()
    dispatch(op, "--minutes", "60")
    (pod_id,) = op.rp.pods
    pod = op.rp.pods[pod_id]
    env = pod["env"]
    # Memory-optimized flavors cost more and are listed last; cpu5g/cpu5m
    # have no stock in this account.
    request = json.loads(json.dumps(env))  # what was sent
    assert pod["cpuFlavorId"] == "cpu3c"
    cfg = json.loads(request["PHASE_CONFIG"])
    assert cfg["pod_plan"] == "plans/smoke.json" and cfg["vcpu"] == 16
    assert cfg["memory_gib"] == 32  # the smallest offered flavor's memory
    assert before + 3600 - 5 <= cfg["deadline_epoch"] <= time.time() + 3600
    assert cfg["stop_admitting_epoch"] == cfg["deadline_epoch"] - 600
    assert int(request["PROBE_DEADLINE"]) == int(cfg["deadline_epoch"] + 60)
    assert request["PHASE_MODULE"] == "scripts.dev.reference_packages.pod_phase"
    assert (
        request["CARBON_VCPU"] == "16"
        and "Elmer 26.2.1" in request["CARBON_REFERENCE_ENV"]
    )
    # The operator watchdog deletes it at the deadline.
    (argv,) = op.watchdogs
    assert argv[-3:] == ["watchdog", pod_id, str(int(cfg["deadline_epoch"]))]
    public = [json.loads(x) for x in Path(op.pc.LEDGER).read_text().splitlines()]
    assert all(
        "rate" not in r and "offers" not in r and "balance_usd" not in r for r in public
    )
    created = next(r for r in public if r["event"] == "created")
    assert created["cpu_flavor"] == "cpu3c"


def test_memory_need_selects_a_memory_flavor(operator):
    dispatch(operator, "--minutes", "30", "--memory-gib", "100")
    (pod,) = operator.rp.pods.values()
    assert pod["cpuFlavorId"] == "cpu3m"


def test_phase_watchdog_keeps_termination_in_its_funded_namespace(operator):
    pc = operator.pc
    args = ["--campaign", "reference-solvers", "--operator-phase", "resume-fixture"]
    pc.main([*args, "start", "--cap-usd", "25"])
    pc.main([*args, "dispatch-solver", "elmer", "--pod-plan", "plans/smoke.json",
             "--vcpu", "16", "--minutes", "60"])  # fmt: skip
    (watchdog,) = operator.watchdogs
    assert watchdog[watchdog.index("--operator-phase") + 1] == "resume-fixture"
    pc.main([*watchdog[3:-1], str(int(time.time()) - 1)])
    assert not operator.rp.pods and not pc.active_pods()
    rows = pc.ledger_rows()
    assert any(r["event"] == "terminated_verified" for r in rows)
    assert "resume-fixture" in pc.PRIVATE_LEDGER
    pc.use_campaign("reference-solvers")
    assert [r["event"] for r in pc.ledger_rows()] == ["campaign_start"]


def test_budget_refusal_counts_each_pod_at_its_worst_case(operator):
    # 16 vCPU at most 0.44/h (cpu3m) for 600 min is under the cap; a third
    # such pod is refused by the pod allowance before any budget question.
    with pytest.raises(SystemExit, match="exceed the cap"):
        # 0.44/h * 60 h is far above USD 25.
        operator.pc.SOLVER_MAX_MINUTES = 100_000
        dispatch(operator, "--minutes", "3600", "--flavors", "cpu3m")
    assert operator.rp.pods == {}


def test_balance_floor_refuses(operator):
    operator.rp.balance = 15.5
    with pytest.raises(SystemExit, match="floor"):
        dispatch(operator, "--minutes", "120")
    assert operator.rp.pods == {}


def test_at_most_four_pods_and_a_deadline_is_required(operator):
    for _ in range(4):
        dispatch(operator, "--minutes", "20", "--max-pods", "4")
    with pytest.raises(SystemExit, match="allowance 4"):
        dispatch(operator, "--minutes", "20", "--max-pods", "5")
    with pytest.raises(SystemExit, match="deadline"):
        dispatch(operator, "--minutes", "0")
    assert len(operator.rp.pods) == 4


def test_rate_guard_and_flavor_policy(operator):
    operator.rp.prices = {"cpu3c": 2.0}  # above the campaign's guard
    with pytest.raises(SystemExit, match="in stock"):
        dispatch(operator, "--minutes", "20")
    with pytest.raises(SystemExit, match="not all in"):
        dispatch(operator, "--minutes", "20", "--flavors", "cpu3c,gpu")
    with pytest.raises(SystemExit, match="runs no"):
        operator.pc.CAMPAIGNS["reference-solvers"]["solver_kinds"] = ["calculix"]
        dispatch(operator, "--minutes", "20")
    assert operator.rp.pods == {}


def test_a_non_public_or_mismatched_plan_is_refused(operator):
    plan = operator.tmp / "repo/plans/smoke.json"
    plan.write_text(
        json.dumps({"schema": pp.PLAN_SCHEMA, "kind": "calculix", "steps": []})
    )
    with pytest.raises(SystemExit, match="not elmer"):
        dispatch(operator, "--minutes", "20")
    plan.write_text(
        json.dumps(
            {
                "schema": pp.PLAN_SCHEMA,
                "kind": "elmer",
                "steps": [{"manifest": "x/eval/m.json"}],
            }
        )
    )
    with pytest.raises(SystemExit, match="non-public"):
        dispatch(operator, "--minutes", "20")
    assert operator.rp.pods == {}


def test_collect_fetches_then_deletes_and_the_watchdog_deletes_at_deadline(operator):
    op = operator
    dispatch(op, "--minutes", "20")
    (first,) = list(op.rp.pods)
    dest = op.tmp / "results"
    op.pc.main(
        [
            "--campaign",
            "reference-solvers",
            "collect",
            str(dest),
            "--wait",
            "--poll-s",
            "0",
        ]
    )
    assert first not in op.rp.pods and op.pc.active_pods() == []
    assert any((dest / "out").rglob("*"))
    events = [
        json.loads(x)["event"] for x in Path(op.pc.LEDGER).read_text().splitlines()
    ]
    assert events[-3:] == ["exported", "terminate_requested", "terminated_verified"]
    # A pod left alone is deleted by the operator watchdog at its deadline.
    dispatch(op, "--minutes", "20")
    (second,) = list(op.rp.pods)
    op.pc.main(
        [
            "--campaign",
            "reference-solvers",
            "watchdog",
            second,
            str(int(time.time()) - 1),
        ]
    )
    assert op.rp.pods == {} and op.pc.active_pods() == []
    events = [
        json.loads(x)["event"] for x in Path(op.pc.LEDGER).read_text().splitlines()
    ]
    assert events[-3:] == [
        "watchdog_deadline",
        "terminate_requested",
        "terminated_verified",
    ]
    # Spend so far is booked against the cap at the verified end times.
    assert op.pc.committed_spend() < 1.0
