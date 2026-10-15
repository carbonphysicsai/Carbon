"""Run a reference-solvers pod plan inside a RunPod CPU pod.

    python -m scripts.dev.reference_packages.pod_phase KIND --out OUT

The pod bootstrap (``scripts/dev/exam_design/runpod/bootstrap.py``) fetches
the hash-pinned code at a pushed commit and runs this as its phase, after the
pod's start command built KIND's solver natively as its locked Dockerfile
does (``pod_control.SOLVER_KINDS``). PHASE_CONFIG (JSON) names the pod plan
and the pod's size and deadline::

    {"pod_plan": "<repo path>", "vcpu": 16, "memory_gib": 32,
     "deadline_epoch": T, "stop_admitting_epoch": T - 600}

A pod plan (schema ``carbon.reference-solvers.pod-plan.v1``) is public
material only and lists steps, run in order until the admission deadline:

- ``script``: ``argv`` run from the repository root with a ``docker`` shim on
  PATH (``docker_shim.py``) that runs the family tools' ``docker run IMAGE``
  natively for the images the step names; ``{out}`` is the step's served
  results dir, ``{work}`` a scratch dir whose ``keep`` files are copied to
  ``{out}/work``, ``{src}`` the checked source archives, ``{root}`` the
  repository; passes on exit 0 and, when ``jsonl_all`` is given, when every
  JSON line it prints carries those field values;
- ``bulk``: a frozen manifest pinned at the ref (``manifest``). Its decks are
  regenerated on the pod by the ``freeze`` command (``{decks}``) or taken
  from a tracked ``decks`` dir; every selected case's every file must match
  the manifest's sha256 and its command the manifest's command, else the
  step is refused before anything runs (``deck-verification.json`` lists
  every case either way). The selected cases then run through
  ``bulk_run.py --executor native`` on a plan sized to the pod (its vCPUs,
  its memory less a reserve, its admission deadline); the ledger, summaries,
  each case's meta and the ``keep`` files of its work dir are served.

Writes ``OUT/pod-environment.json`` first and ``OUT/pod-phase.json`` last.
Exits non-zero when any step did not pass. DEVELOPMENT engineering only: it
measures and runs public decks; it decides no adequacy or qualification.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import platform
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.reference_packages import bulk_run as br

PLAN_SCHEMA = "carbon.reference-solvers.pod-plan.v1"
PHASE_SCHEMA = "carbon.reference-solvers.pod-phase.v1"
GIB = 1024**3
#: Each kind's solver version check (bulk_run's environment check) and the
#: images whose tools it provides natively to the docker shim: the solver's
#: own pinned images and the motor reference image (Gmsh 4.15.2) the f08 and
#: f13 decks are meshed with.
MOTOR_MESH_IMAGE = (
    "ghcr.io/carbonphysicsai/carbon-motor-reference@sha256:"
    "599521e79786ee0326a0754ba0545f51ee9665adff73c3515c8d4b8ba24c1c05"
)
KINDS = {
    "elmer": {
        "native": {
            "version_command": "ElmerSolver -v | head -1",
            "version_expect": "ELMER SOLVER (v 26.2)",
        },
        "solvers": ["ElmerSolver", "ElmerGrid", "gmsh"],
        "images": [MOTOR_MESH_IMAGE],
    },
    "calculix": {
        "native": {
            "version_command": "ccx -v",
            "version_expect": "This is Version 2.23",
        },
        "solvers": ["ccx", "gmsh"],
        "images": [MOTOR_MESH_IMAGE],
    },
    "openfoam2506": {
        "native": {
            "version_command": "echo WM_PROJECT_VERSION=$WM_PROJECT_VERSION;"
            " simpleFoam -help > /dev/null",
            "version_expect": "WM_PROJECT_VERSION=v2506",
            "memory_cap": "rss",
        },
        "solvers": ["simpleFoam", "blockMesh"],
        "images": [],
    },
}
SRC = "/opt/src"
#: Small text outputs worth serving from a work dir, unless a step says.
DEFAULT_KEEP = {
    "patterns": ["*.log", "*.json", "*.dat", "*.csv", "*.txt", "*.sif", "*.inp"],
    "max_file_bytes": 2_000_000,
}
#: The decks' container path; a native case runs in its own work dir.
CONTAINER_CASE = "/case"
NON_PUBLIC = (
    "private",
    "sealed",
    "hidden",
    "quiz",
    "tuning",
    "stress",
    "root_commitment",
)


class StepRefused(Exception):
    pass


# --------------------------------------------------------------- the pod


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def pod_size(config):
    """The CPUs and memory this pod may use: the dispatch's vCPU count and
    flavor memory, never more than the cgroup and affinity allow."""
    affinity = len(os.sched_getaffinity(0))
    cpus = [affinity, int(config.get("vcpu") or affinity)]
    quota = (_read("/sys/fs/cgroup/cpu.max") or "max").split()
    if quota and quota[0] != "max" and len(quota) == 2:
        cpus.append(max(1, math.floor(int(quota[0]) / int(quota[1]))))
    mem = [br.host_info().get("mem_total_bytes") or 0]
    limit = _read("/sys/fs/cgroup/memory.max")
    if limit and limit.isdigit():
        mem.append(int(limit))
    if config.get("memory_gib"):
        mem.append(int(float(config["memory_gib"]) * GIB))
    mem = [m for m in mem if m]
    return min(cpus), (min(mem) if mem else None)


def environment_record(kind, config):
    cpus, mem = pod_size(config)
    record = {
        "schema": "carbon.reference-solvers.pod-environment.v1",
        "kind": kind,
        "environment": os.environ.get("CARBON_REFERENCE_ENV"),
        "code_ref": os.environ.get("CODE_REF"),
        "python": platform.python_version(),
        "host": br.host_info(),
        "affinity_cores": len(os.sched_getaffinity(0)),
        "cgroup_cpu_max": _read("/sys/fs/cgroup/cpu.max"),
        "cgroup_memory_max": _read("/sys/fs/cgroup/memory.max"),
        "usable_cpus": cpus,
        "usable_memory_bytes": mem,
        "solvers": {},
    }
    for name in KINDS[kind]["solvers"]:
        path = shutil.which(name)
        record["solvers"][name] = (
            {"path": path, "sha256": br._sha_file(path)} if path else None
        )
    return record


def install_shim(bin_dir, images, identity, log_path):
    """Put the docker shim first on PATH for a step's tools."""
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim = bin_dir / "docker"
    script = Path(__file__).with_name("docker_shim.py")
    shim.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -I {shlex.quote(str(script))} "$@"\n'
    )
    shim.chmod(0o755)
    return {
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "CARBON_DOCKER_SHIM": json.dumps(
            {"images": list(images), "identity": identity, "log": str(log_path)}
        ),
    }


# ------------------------------------------------------------ the plan


def public_plan(doc):
    """Refuse a plan naming anything but public material (invariant 1)."""
    text = json.dumps(doc).lower()
    hit = [t for t in NON_PUBLIC if t in text]
    if hit:
        raise SystemExit(f"refusing: the pod plan names non-public material {hit}")
    return doc


def load_plan(path, kind):
    doc = public_plan(json.loads(Path(path).read_text()))
    problems = []
    if doc.get("schema") != PLAN_SCHEMA:
        problems.append(f"schema must be {PLAN_SCHEMA}")
    if doc.get("kind") != kind:
        problems.append(f"plan kind {doc.get('kind')!r} is not this pod's {kind!r}")
    names = [s.get("name") for s in doc.get("steps") or []]
    if not names or len(names) != len(set(names)):
        problems.append("steps must be a non-empty list with unique names")
    for step in doc.get("steps") or []:
        name = step.get("name", "")
        if not isinstance(name, str) or not br.NAME.match(name):
            problems.append(f"step name {name!r} must match [A-Za-z0-9._-]")
        if step.get("type") == "script":
            if not isinstance(step.get("argv"), list) or not step["argv"]:
                problems.append(f"{name}: argv is required")
        elif step.get("type") == "bulk":
            if not isinstance(step.get("manifest"), str):
                problems.append(f"{name}: manifest is required")
            if ("freeze" in step) == ("decks" in step):
                problems.append(f"{name}: exactly one of freeze or decks")
            if not isinstance(step.get("families"), dict) or not step["families"]:
                problems.append(f"{name}: families is required")
        else:
            problems.append(f"{name}: type must be script or bulk")
    if problems:
        raise SystemExit("refusing: " + "; ".join(problems))
    return doc


def expand(argv, values):
    return [str(a).format(**values) for a in argv]


def keep_files(src, dest, keep):
    """Copy the files under ``src`` that match the keep patterns and size."""
    keep = keep or DEFAULT_KEEP
    patterns, limit = keep.get("patterns", []), keep.get("max_file_bytes", 2_000_000)
    copied = skipped = 0
    for path in sorted(Path(src).rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(src)
        if (
            any(fnmatch.fnmatch(path.name, p) for p in patterns)
            and path.stat().st_size <= limit
        ):
            target = Path(dest) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            copied += 1
        else:
            skipped += 1
    return {"copied": copied, "not_copied": skipped}


# ---------------------------------------------------------------- steps


def run_script(step, values, env, timeout_s):
    out = Path(values["out"])
    with open(out / "step.log", "wb") as log:
        result = br.run_native(
            expand(step["argv"], values),
            ROOT,
            env,
            timeout_s,
            threading.Event(),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    passed = result["exit"] == 0 and result["stop_reason"] == "exit"
    if passed and step.get("jsonl_all"):
        lines = []
        for line in (out / "step.log").read_text(errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                lines.append(row)
        want = step["jsonl_all"]
        passed = bool(lines) and all(
            all(str(r.get(k)) == str(v) for k, v in want.items()) for r in lines
        )
        result["jsonl_rows"] = len(lines)
    if Path(values["work"]).exists():
        result["kept"] = keep_files(values["work"], out / "work", step.get("keep"))
    return passed, result


def verify_decks(manifest, decks, select):
    """Every manifest case against the decks on disk: which selected cases
    differ (refusal) and a per-case record of all of them."""
    generated = {}
    gen_path = Path(decks) / "manifest.generated.json"
    if gen_path.exists():
        generated = {
            (c.get("family"), c.get("case")): c
            for c in json.loads(gen_path.read_text()).get("cases", [])
        }
    cases, refused = [], []
    for entry in manifest["cases"]:
        key = (entry.get("family"), entry.get("case"))
        bad = br.verify_case_files(Path(decks) / key[0] / key[1], entry["files"])
        gen = generated.get(key)
        command_ok = gen is None or gen.get("command") == entry["command"]
        container = CONTAINER_CASE in entry["command"]
        chosen = selected(entry, select)
        row = {
            "family": key[0],
            "case": key[1],
            "selected": chosen,
            "files": len(entry["files"]),
            "files_differing": bad,
            "command_matches_freeze": command_ok,
            "command_uses_container_path": container,
        }
        cases.append(row)
        if chosen and (bad or not command_ok or container):
            refused.append(f"{key[0]}/{key[1]}")
    return cases, refused


def selected(entry, select):
    select = select or {}
    return (
        entry.get("family") in select.get("families", [entry.get("family")])
        and entry.get("reservation")
        in select.get("reservations", [entry.get("reservation")])
        and entry.get("case") in select.get("cases", [entry.get("case")])
    )


def bulk_plan(step, manifest, decks, cpus, mem_bytes, stop_epoch, now):
    """A bulk_run plan for the selected cases, sized to this pod."""
    machine = {
        "reserve_cpus": 0,
        "reserve_memory_gib": 1,
        "margin_minutes": 0,
        "starvation_s": 900,
        "min_case_window_s": 300,
        **step.get("machine", {}),
    }
    machine |= {
        "cpus": cpus,
        "memory_gib": round(mem_bytes / GIB, 3),
        "node_hours": max(1e-6, (stop_epoch - now) / 3600),
        "clock_start": now,
    }
    families = []
    for name, fam in sorted(step["families"].items()):
        native = {**KINDS[step["_kind"]]["native"], **fam.get("native", {})}
        families.append(
            {
                "family": name,
                "manifest_dir": str(decks),
                "image": manifest["image"],
                "priority": fam.get("priority", 10),
                "case_limits": fam["case_limits"],
                "ceilings": fam["ceilings"],
                "shell": fam.get("shell", "sh"),
                "env": fam.get("env", {}),
                "native": native,
                **(
                    {"reservation_order": fam["reservation_order"]}
                    if "reservation_order" in fam
                    else {}
                ),
            }
        )
    return {
        "schema": br.PLAN_SCHEMA,
        "plan_id": step["name"],
        "authority": step.get("authority", "OWNER-RUNPOD-SOLVER-READINESS-01"),
        "host_profile": "runpod-cpu-pod-native",
        "machine": machine,
        "families": families,
    }


def run_bulk(step, values, env, config, kind):
    out, work = Path(values["out"]), Path(values["work"])
    decks = work / "decks"
    pinned = json.loads((ROOT / step["manifest"]).read_text())
    if pinned.get("schema") != br.MANIFEST_SCHEMA:
        raise StepRefused(f"{step['manifest']} is not a {br.MANIFEST_SCHEMA} manifest")
    record = {
        "manifest": step["manifest"],
        "manifest_sha256": br._sha_file(ROOT / step["manifest"]),
    }
    if "freeze" in step:
        decks.mkdir(parents=True)
        values = {**values, "decks": str(decks)}
        with open(out / "freeze.log", "wb") as log:
            freeze = br.run_native(
                expand(step["freeze"]["argv"], values),
                ROOT,
                env,
                float(step["freeze"].get("timeout_s", 3600)),
                threading.Event(),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        record["freeze"] = {
            k: freeze[k] for k in ("exit", "stop_reason", "wall_s", "rusage_cpu_s")
        }
        if freeze["exit"] != 0 or freeze["stop_reason"] != "exit":
            raise StepRefused(
                f"freeze failed (exit {freeze['exit']}, {freeze['stop_reason']})"
            )
        if (decks / "manifest.json").exists():
            (decks / "manifest.json").rename(decks / "manifest.generated.json")
    else:
        shutil.copytree(ROOT / step["decks"], decks)
    cases, refused = verify_decks(pinned, decks, step.get("select"))
    # REFERENCE-SOLVERS-HOST-MESH-01: Gmsh output can differ between CPU
    # vendors for the same binary and script. A plan may name the files the
    # host regenerates (e.g. mesh.inp); a selected case differing only in
    # those, with a matching command, runs on the regenerated files, both
    # digests are recorded before any solve, and the solved files are kept.
    host_files = set(step.get("host_regenerated_files", []))
    if refused and host_files and "freeze" in step:
        by_name = {f"{c['family']}/{c['case']}": c for c in cases}
        for entry in pinned["cases"]:
            name = f"{entry['family']}/{entry['case']}"
            row = by_name[name]
            differing = set(row["files_differing"])
            if (
                name not in refused
                or not differing
                or not differing <= host_files
                or not row["command_matches_freeze"]
                or row["command_uses_container_path"]
            ):
                continue
            case_dir = decks / entry["family"] / entry["case"]
            if not all((case_dir / rel).is_file() for rel in differing):
                continue
            kept = out / "decks-solved" / entry["family"] / entry["case"]
            kept.mkdir(parents=True, exist_ok=True)
            row["host_regenerated"] = {}
            for rel in sorted(differing):
                solved = br._sha_file(case_dir / rel)
                row["host_regenerated"][rel] = {
                    "pinned": entry["files"][rel],
                    "solved": solved,
                }
                entry["files"][rel] = solved
                shutil.copy2(case_dir / rel, kept / Path(rel).name)
            refused.remove(name)
    verification = {
        "manifest": step["manifest"],
        "decks": "regenerated on the pod" if "freeze" in step else step["decks"],
        "cases": cases,
        "selected": sum(c["selected"] for c in cases),
        "selected_refused": refused,
        "all_cases_matching": sum(
            not c["files_differing"] and c["command_matches_freeze"] for c in cases
        ),
    }
    (out / "deck-verification.json").write_text(
        json.dumps(verification, indent=1) + "\n"
    )
    record["verification"] = {
        k: verification[k]
        for k in ("selected", "selected_refused", "all_cases_matching")
    }
    if not verification["selected"]:
        raise StepRefused("no case selected")
    if refused:
        raise StepRefused(
            f"{len(refused)} selected case(s) differ from the manifest: {refused[:5]}"
        )
    # The pinned manifest, narrowed to the selected cases, is what runs.
    narrowed = dict(
        pinned, cases=[c for c in pinned["cases"] if selected(c, step.get("select"))]
    )
    (decks / "manifest.json").write_text(json.dumps(narrowed, indent=1) + "\n")
    cpus, mem = pod_size(config)
    stop = float(config.get("stop_admitting_epoch") or time.time() + 3600)
    plan = bulk_plan(
        dict(step, _kind=kind), narrowed, decks, cpus, mem, stop, time.time()
    )
    plan_path = out / "bulk-plan.json"
    plan_path.write_text(json.dumps(plan, indent=1) + "\n")
    bulk_out = work / "bulk"
    with open(out / "bulk.log", "wb") as log:
        done = subprocess.run(
            [sys.executable, str(Path(br.__file__).resolve()),
             "--plan", str(plan_path), "--out", str(bulk_out), "--executor", "native",
             "--poll-s", "1"],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=False,
        )  # fmt: skip
    record["bulk_exit"] = done.returncode
    for name in ("ledger.jsonl", "summary"):
        src = bulk_out / name
        if src.is_dir():
            shutil.copytree(src, out / name, dirs_exist_ok=True)
        elif src.exists():
            shutil.copyfile(src, out / name)
    for case_dir in sorted((bulk_out / "cases").glob("*/*")):
        rel = case_dir.relative_to(bulk_out)
        keep_files(
            case_dir / "meta",
            out / rel / "meta",
            {"patterns": ["*"], "max_file_bytes": 2_000_000},
        )
        if (case_dir / "work").is_dir():
            keep_files(case_dir / "work", out / rel / "work", step.get("keep"))
    summary_path = bulk_out / "summary" / "all.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    record["outcomes"] = {
        f: s.get("outcomes") for f, s in summary.get("families", {}).items()
    }
    record["not_launched"] = {
        f: s.get("not_launched") for f, s in summary.get("families", {}).items()
    }
    launched_all = all(not v for v in record["not_launched"].values())
    completed = all(set(o or {}) <= {"COMPLETED"} for o in record["outcomes"].values())
    return done.returncode == 0 and bool(summary) and launched_all and completed, record


# ----------------------------------------------------------------- main


def progress(out, **kw):
    (Path(out) / "progress.json").write_text(json.dumps({"utc": time.time(), **kw}))


def run(kind, out, config, work_root="/tmp/work"):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    plan = load_plan(ROOT / config["pod_plan"], kind)
    record = environment_record(kind, config)
    (out / "pod-environment.json").write_text(json.dumps(record, indent=1) + "\n")
    stop = float(config.get("stop_admitting_epoch") or time.time() + 3600)
    steps, ok = [], True
    for index, step in enumerate(plan["steps"]):
        name = step["name"]
        progress(out, step=name, index=index, of=len(plan["steps"]))
        left = stop - time.time()
        if left <= 60:
            steps.append({"name": name, "status": "SKIPPED_DEADLINE"})
            ok = False
            continue
        step_out, step_work = out / name, Path(work_root) / name
        step_out.mkdir(parents=True, exist_ok=True)
        if step_work.exists():
            shutil.rmtree(step_work)
        step_work.mkdir(parents=True)
        images = [*KINDS[kind]["images"], *step.get("docker_images", [])]
        env = {k: v for k, v in os.environ.items() if not br.NATIVE_ENV_DROP.search(k)}
        env.update(
            install_shim(
                Path(work_root) / ".shim-bin",
                images,
                f"native:{kind} {os.environ.get('CARBON_REFERENCE_ENV', '')}".strip(),
                step_out / "docker-shim.jsonl",
            )
        )
        env["PYTHONPATH"] = ":".join(
            p for p in (str(ROOT), env.get("PYTHONPATH", "")) if p
        )
        env.update(step.get("env", {}))
        values = {
            "out": str(step_out),
            "work": str(step_work),
            "src": SRC,
            "root": str(ROOT),
        }
        t0 = time.time()
        try:
            if step["type"] == "script":
                timeout = min(float(step.get("timeout_s", 3600)), left)
                passed, detail = run_script(step, values, env, timeout)
            else:
                passed, detail = run_bulk(step, values, env, config, kind)
            status = "PASS" if passed else "FAIL"
        except StepRefused as exc:
            passed, status, detail = False, "REFUSED", {"why": str(exc)}
        except Exception as exc:  # noqa: BLE001 -- recorded, the next step runs
            passed, status, detail = False, "ERROR", {"why": repr(exc)[:500]}
        ok &= passed
        row = {
            "name": name,
            "type": step["type"],
            "status": status,
            "wall_s": round(time.time() - t0, 1),
            **detail,
        }
        (step_out / "step.json").write_text(
            json.dumps(row, indent=1, default=str) + "\n"
        )
        steps.append(row)
        shutil.rmtree(step_work, ignore_errors=True)
    summary = {
        "schema": PHASE_SCHEMA,
        "plan_id": plan.get("plan_id"),
        "pod_plan": config["pod_plan"],
        "pod_plan_sha256": br._sha_file(ROOT / config["pod_plan"]),
        "kind": kind,
        "steps": [{k: s.get(k) for k in ("name", "status", "wall_s")} for s in steps],
        "all_passed": ok,
        "maturity": "DEVELOPMENT engineering run on public decks; no adequacy, qualification or LIVE claim",
    }
    (out / "pod-phase.json").write_text(json.dumps(summary, indent=1) + "\n")
    progress(out, step=None, done=True, all_passed=ok)
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", choices=sorted(KINDS))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--config", help="PHASE_CONFIG JSON (default: the environment's)"
    )
    parser.add_argument("--work", default="/tmp/work", help="scratch root (not served)")
    args = parser.parse_args(argv)
    config = json.loads(args.config or os.environ.get("PHASE_CONFIG", "{}"))
    if not config.get("pod_plan"):
        parser.error("PHASE_CONFIG names no pod_plan")
    return run(args.kind, args.out, config, args.work)


if __name__ == "__main__":
    sys.exit(main())
