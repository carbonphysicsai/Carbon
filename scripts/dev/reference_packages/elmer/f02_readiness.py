"""f02 solver-data readiness: freeze, run and judge (F02-SCIENCE-VALUES-01).

    python3 f02_readiness.py freeze SET DIR [--labels A,B]   # SET: convergence | sample | bank
    python3 f02_readiness.py run DIR --image ID --ledger L.jsonl [--parallel N]
    python3 f02_readiness.py judge DIR OUT.json [--ledger L.jsonl]

`freeze` writes decks and DIR/manifest.json in the shared
`carbon.reference-triage.frozen-decks.v1` schema (family, case, reservation,
command, files{relpath: sha256}, mesh), so the bulk runner can take it.

- convergence: the 8 triage primaries (reference-route-panels.json f02) at
  mesh 1/dt 1, mesh 2 and dt/2; the packet's 4 controls; the 4 steady 20 W
  baselines (2 cooling pairs x 2 splits, direct solver) and the 8 transient
  20 W baselines of the menu (baseline-decks-manifest.json).
- sample: menu-v2 primaries named by --labels (case names of
  f02-menu-v2/decks-manifest.json); every deck's bytes are checked against
  that registered manifest.
- bank: the full public bank (sizing only; see the sizing note): 384 menu
  primaries, 8 transient and 4 steady baselines, the 24 audit refinements
  (one seeded primary per context at both rungs) and the 960 TRAIN decks.
  Decision-contender refinements are added after the primaries solve
  (`f02_menu.py plan-refine` generalised to the [89, 96] C window, B8).

`run` is a local runner for this box: one CPU and an explicit memory limit
per container, no network, read-only root; each case's files are re-hashed
against the manifest first. The ledger records wall, the container cgroup's
CPU time (v1 cpuacct.usage or v2 cpu.stat usage_usec) and memory peak (v1
memory.max_usage_in_bytes or v2 memory.peak), nproc, CPU model and the host
profile. Local timings are a non-comparable dev-box profile.

`judge` applies the registered bands (f02-readiness/bands.json) and writes
per-case observables and per-rung verdicts.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for entry in (str(HERE), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import f02_baselines as baselines
import f02_controls as controls
import f02_deck as deck
import f02_menu as menu

SCHEMA = "carbon.reference-triage.frozen-decks.v1"
SOLVE = "ElmerSolver case.sif > solver.log 2>&1"
EVIDENCE = ROOT / "docs/development/evidence/reference-packages-01"
MENU_MANIFEST = EVIDENCE / "f02-menu-v2/decks-manifest.json"
BASELINE_MANIFEST = EVIDENCE / "f02-menu-v2/baseline-decks-manifest.json"
TRAIN_MANIFEST = EVIDENCE / "f02-menu-v2/train-decks-manifest.json"
BANDS = EVIDENCE / "f02-readiness/bands.json"
HOST_PROFILE = "local-dev-4vcpu-15g-contended"
AUDIT_SEED = 20261015
MEMORY = {"mesh2": "2g"}  # per-case container memory limit; default below
DEFAULT_MEMORY = "1g"


def _hashes(case_dir):
    case_dir = Path(case_dir)
    return {
        str(p.relative_to(case_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(case_dir.rglob("*"))
        if p.is_file()
    }


def steady_regimes():
    """(name, case) for the 4 steady 20 W baselines: cooling pair x split."""
    for (coolant, h), split in itertools.product(menu.COOLING, menu.SPLITS):
        yield f"steady-{coolant:g}C-{h:g}-{split:g}", {
            "coolant_c": coolant, "h_w_m2_k": h, "initial_c": coolant,
            "left_source_fraction": split, "waveform": "constant",
            "peak_w": deck.BASE_W, "on_time_s": 0.0}  # fmt: skip


def steady_name(case):
    return f"steady-{case['coolant_c']:g}C-{case['h_w_m2_k']:g}-{case['left_source_fraction']:g}"


def _registered(manifest_path):
    return {e["case"]: e for e in json.loads(Path(manifest_path).read_text())["cases"]}


def _menu_case(entry, contexts=None):
    contexts = contexts or dict(menu.contexts())
    return {
        **contexts[entry["context"]],
        "peak_w": entry["peak_w"],
        "on_time_s": entry["on_time_s"],
    }


def audit_choice(primaries):
    """One seeded primary per context (B9 audit refinement)."""
    rng = random.Random(AUDIT_SEED)
    by_ctx = {}
    for name in sorted(primaries):
        by_ctx.setdefault(primaries[name]["context"], []).append(name)
    return [rng.choice(by_ctx[c]) for c in sorted(by_ctx)]


def freeze(kind, out, labels=None):
    out = Path(out)
    entries = []

    def add(
        name, reservation, case, *, level=1, dt=1.0, steady=False, check=None, **opts
    ):
        d = out / "f02" / name
        meta = deck.write_case(case, d, level, dt, steady, **opts)
        files = _hashes(d)
        if check is not None and files != check:
            raise SystemExit(
                f"{name}: regenerated deck differs from its registered manifest"
            )
        entries.append({"family": "f02", "case": name, "reservation": reservation,
                        "command": SOLVE, "files": files, "mesh": meta["mesh"]})  # fmt: skip

    if kind == "convergence":
        for label in [c["label"] for c in _panel_cases()]:
            case = deck.panel_case(label)
            add(f"{label}-primary", "primary", case)
            add(f"{label}-mesh2", "mesh_and_time", case, level=2)
            add(f"{label}-dt0.5", "mesh_and_time", case, dt=0.5)
        for name, (case, opts) in controls.CONTROLS.items():
            add(f"control-{name}", "controls", case, **opts)
        for name, case in steady_regimes():
            add(name, "steady_baselines", case, steady=True)
        registered = _registered(BASELINE_MANIFEST)
        for name, case in baselines.contexts():
            add(name, "transient_baselines", case, check=registered[name]["files"])
    elif kind == "sample":
        registered, ctx = _registered(MENU_MANIFEST), dict(menu.contexts())
        for name in labels:
            entry = registered[name]
            add(name, "primary", _menu_case(entry, ctx), check=entry["files"])
    elif kind == "bank":
        return _freeze_bank(out)
    else:
        raise SystemExit(f"unknown set {kind}")
    _write_manifest(out, kind, entries)
    return len(entries)


def _write_manifest(out, kind, entries, extra=None):
    counts = {}
    for e in entries:
        counts[e["reservation"]] = counts.get(e["reservation"], 0) + 1
    doc = {"schema": SCHEMA, "ticket": "F02-SCIENCE-VALUES-01", "set": kind,
           "image": None, "bands": str(BANDS.relative_to(ROOT)),
           "counts": {"f02": counts}, **(extra or {}), "cases": entries}  # fmt: skip
    (Path(out) / "manifest.json").write_text(json.dumps(doc, indent=1) + "\n")


def _panel_cases():
    panels = json.loads(deck.PANELS.read_text())["families"]["f02"]
    return panels["public_cases"]


def _freeze_bank(out):
    """Write every bank deck and the manifest; menu, baseline and TRAIN decks
    are checked byte-for-byte against their registered manifests."""
    out = Path(out)
    entries, ctx = [], dict(menu.contexts())

    def add(name, reservation, case, *, level=1, dt=1.0, steady=False, check=None):
        d = out / "f02" / name
        meta = deck.write_case(case, d, level, dt, steady)
        files = _hashes(d)
        if check is not None and files != check:
            raise SystemExit(
                f"{name}: regenerated deck differs from its registered manifest"
            )
        entries.append({"family": "f02", "case": name, "reservation": reservation,
                        "command": SOLVE, "files": files, "mesh": meta["mesh"]})  # fmt: skip

    primaries = _registered(MENU_MANIFEST)
    for name, entry in primaries.items():
        add(name, "primary", _menu_case(entry, ctx), check=entry["files"])
    for name, entry in _registered(BASELINE_MANIFEST).items():
        case = dict(baselines.contexts())[name]
        add(name, "transient_baselines", case, check=entry["files"])
    for name, case in steady_regimes():
        add(name, "steady_baselines", case, steady=True)
    for name in audit_choice(primaries):
        case = _menu_case(primaries[name], ctx)
        stem = name[: -len("-primary")]
        add(f"{stem}-mesh2", "audit_refinement", case, level=2)
        add(f"{stem}-dt0.5", "audit_refinement", case, dt=0.5)
    train = json.loads(TRAIN_MANIFEST.read_text())["cases"]
    for entry in train:
        add(entry["case"], "train", _menu_case(entry, ctx), check=entry["files"])
    _write_manifest(
        out,
        "bank",
        entries,
        {
            "deferred": "decision-contender refinements (primary peak in [89, 96] C, "
            "mesh 2 and dt/2 each) are frozen after the primaries solve: "
            "f02_readiness.py freeze-contenders"
        },
    )
    return len(entries)


def freeze_contenders(bank_dir, out):
    """B8: every solved bank primary with peak in [89, 96] C gets both rungs."""
    bank_dir, out = Path(bank_dir), Path(out)
    bands = json.loads(BANDS.read_text())
    lo, hi = bands["B8_refine_window_c"]
    ctx, entries = dict(menu.contexts()), []
    primaries = _registered(MENU_MANIFEST)
    for name, entry in primaries.items():
        d = bank_dir / "f02" / name
        if not (d / "scalars.dat").exists():
            continue
        peak = deck.observe(d)["peak_top_c"]
        if not lo <= peak <= hi:
            continue
        case, stem = _menu_case(entry, ctx), name[: -len("-primary")]
        for tag, level, dt in (("mesh2", 2, 1.0), ("dt0.5", 1, 0.5)):
            c = out / "f02" / f"{stem}-{tag}"
            meta = deck.write_case(case, c, level, dt)
            entries.append({"family": "f02", "case": c.name, "reservation": "contender_refinement",
                            "command": SOLVE, "files": _hashes(c), "mesh": meta["mesh"]})  # fmt: skip
    _write_manifest(out, "contenders", entries)
    return len(entries)


# --- runner ----------------------------------------------------------------------------

ACCOUNT = (
    "rc=$?; "
    "if [ -f /sys/fs/cgroup/cpu.stat ]; then "
    "awk '/^usage_usec/ {print $2*1000}' /sys/fs/cgroup/cpu.stat > cgroup.cpu_ns; "
    "cat /sys/fs/cgroup/memory.peak > cgroup.mem_peak 2>/dev/null; "
    "else cat /sys/fs/cgroup/cpuacct/cpuacct.usage > cgroup.cpu_ns; "
    "cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes > cgroup.mem_peak; fi; "
    "exit $rc"
)


def _cpu_model():
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None


def run(decks, image, ledger, parallel=1):
    decks, ledger = Path(decks), Path(ledger)
    manifest = json.loads((decks / "manifest.json").read_text())
    done = set()
    if ledger.exists():
        done = {json.loads(x)["case"] for x in ledger.read_text().splitlines() if x}
    lock, model = threading.Lock(), _cpu_model()

    def one(entry):
        d = decks / entry["family"] / entry["case"]
        bad = [f for f, h in entry["files"].items()
               if hashlib.sha256((d / f).read_bytes()).hexdigest() != h]  # fmt: skip
        if bad:
            raise SystemExit(
                f"{entry['case']}: files differ from the manifest: {bad[:3]}"
            )
        tag = entry["case"].rsplit("-", 1)[-1]
        memory = MEMORY.get(tag, DEFAULT_MEMORY)
        cmd = ["docker", "run", "--rm", "--name", f"carbon-f02rd-{entry['case']}"[:100],
               "--network", "none", "--read-only", "--tmpfs", "/tmp", "--cpus", "1",
               "--memory", memory, "--memory-swap", memory, "--pids-limit", "16",
               "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{d.resolve()}:/case",
               "-w", "/case", image, "bash", "-c", f"{entry['command']}; {ACCOUNT}"]  # fmt: skip
        started, t0 = time.time(), time.monotonic()
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=7200
        )
        wall = time.monotonic() - t0

        def read(name):
            p = d / name
            return (
                int(p.read_text().split()[0])
                if p.exists() and p.read_text().strip()
                else None
            )

        cpu_ns, mem = read("cgroup.cpu_ns"), read("cgroup.mem_peak")
        row = {"family": "f02", "case": entry["case"], "reservation": entry["reservation"],
               "started_unix": round(started, 3), "wall_s": round(wall, 2),
               "cgroup_cpu_s": None if cpu_ns is None else round(cpu_ns / 1e9, 2),
               "cgroup_memory_peak_bytes": mem, "memory_limit": memory, "cpus": 1,
               "exit": proc.returncode, "outcome": "COMPLETED" if proc.returncode == 0 else "FAILED",
               "nproc": os.cpu_count(), "cpu_model": model, "host_profile": HOST_PROFILE,
               "image": image, "mesh_nodes": (entry.get("mesh") or {}).get("nodes")}  # fmt: skip
        with lock, ledger.open("a") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        print(
            entry["case"],
            row["outcome"],
            row["wall_s"],
            row["cgroup_cpu_s"],
            flush=True,
        )

    order = {
        "controls": 0,
        "steady_baselines": 1,
        "primary": 2,
        "transient_baselines": 3,
    }
    todo = sorted((e for e in manifest["cases"] if e["case"] not in done),
                  key=lambda e: (order.get(e["reservation"], 9), "mesh2" not in e["case"]))  # fmt: skip
    with ThreadPoolExecutor(parallel) as pool:
        list(pool.map(one, todo))


# --- judge -----------------------------------------------------------------------------


def steady_observe(case_dir):
    """Steady 20 W baseline: top-die max and the Robin balance (B6)."""
    cols, rows = deck.read_scalars(case_dir)
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
    i_bottom = next(i for i, c in enumerate(cols)
                    if c.startswith("boundary int") and c.endswith("bc 1"))  # fmt: skip
    h, tc = meta["case"]["h_w_m2_k"], meta["case"]["coolant_c"] + 273.15
    area = (2 * deck.LAYERS["copper"][0] * deck.MM) ** 2
    r = rows[-1]
    out = h * (r[i_bottom] - tc * area)
    return {
        "steady_top_c": r[i_top] - 273.15,
        "robin_out_w": out,
        "balance_rel": (deck.BASE_W - out) / deck.BASE_W,
    }


def _curve_diff(a, b):
    sa = {round(t, 3): v for t, v in a}
    sb = {round(t, 3): v for t, v in b}
    common = sorted(set(sa) & set(sb))
    return max(abs(sa[t] - sb[t]) for t in common) if common else None


def _event_diff(a, b):
    """(difference or None, verdict) for crossing/recovery times."""
    na, nb = isinstance(a, (int, float)), isinstance(b, (int, float))
    if na and nb:
        return abs(a - b), None
    if na != nb:
        return None, "UNRESOLVED_ONE_RUNG_ONLY"
    return None, None


def judge(decks, out, ledger=None):
    decks = Path(decks)
    bands = json.loads(BANDS.read_text())
    manifest = json.loads((decks / "manifest.json").read_text())
    names = {e["case"]: e for e in manifest["cases"]}
    obs, steady = {}, {}
    for name, e in names.items():
        d = decks / "f02" / name
        if not (d / "scalars.dat").exists():
            obs[name] = {"status": "NOT_SOLVED"}
            continue
        if e["reservation"] == "steady_baselines":
            steady[name] = obs[name] = steady_observe(d)
    for name, e in names.items():
        d = decks / "f02" / name
        if e["reservation"] in ("steady_baselines",) or name in obs:
            continue
        if e["reservation"] == "controls":
            obs[name] = controls.score(name[len("control-") :], d)
            continue
        meta = json.loads((d / "deck.json").read_text())
        base = steady.get(steady_name(meta["case"]))
        o = deck.observe(d, base and base["steady_top_c"])
        try:
            o["energy"] = deck.energy_balance(d)
        except (OSError, StopIteration, AttributeError) as error:
            o["energy"] = {"error": repr(error)}
        obs[name] = o
    rungs, verdicts = {}, []
    for name in names:
        if not name.endswith("-primary") or "peak_top_c" not in obs.get(name, {}):
            continue
        stem, p = name[: -len("-primary")], obs[name]
        row = {"case": stem, "primary_peak_c": p["peak_top_c"],
               "primary_energy_residual": p["energy"].get("residual_rel"), "rungs": {}}  # fmt: skip
        ok = (
            abs(p["energy"].get("residual_rel") or 1) <= bands["B5_energy_residual_rel"]
        )
        for tag in ("mesh2", "dt0.5"):
            r = obs.get(f"{stem}-{tag}")
            if r is None:
                continue
            if "peak_top_c" not in r:
                row["rungs"][tag] = {"status": "NOT_SOLVED"}
                ok = False
                continue
            dc, vc = _event_diff(p["first_95c_crossing_s"], r["first_95c_crossing_s"])
            dr, vr = _event_diff(p["recovery_s"], r["recovery_s"])
            g = {"peak_shift_c": r["peak_top_c"] - p["peak_top_c"],
                 "crossing_shift_s": dc, "crossing_flag": vc,
                 "recovery_shift_s": dr, "recovery_flag": vr,
                 "curve_max_diff_c": _curve_diff(p["top_max_c_at_0p5s"], r["top_max_c_at_0p5s"]),
                 "energy_residual": r["energy"].get("residual_rel")}  # fmt: skip
            g["pass"] = (
                abs(g["peak_shift_c"]) <= bands["B1_peak_c"]
                and (dc is None or dc <= bands["B2_crossing_s"]) and vc is None
                and (dr is None or dr <= bands["B3_recovery_s"]) and vr is None
                and g["curve_max_diff_c"] is not None
                and g["curve_max_diff_c"] <= bands["B4_curve_c"]
                and g["energy_residual"] is not None
                and abs(g["energy_residual"]) <= bands["B5_energy_residual_rel"]
            )  # fmt: skip
            ok = ok and g["pass"]
            row["rungs"][tag] = g
        row["pass"] = ok and len(row["rungs"]) == 2 if row["rungs"] else None
        rungs[stem] = row
    for name, s in steady.items():
        base_pass = abs(s["balance_rel"]) <= bands["B6_steady_balance_rel"]
        verdicts.append({"case": name, "check": "B6", "pass": base_pass})
    for name, e in names.items():
        if e["reservation"] != "transient_baselines" or "peak_top_c" not in obs[name]:
            continue
        meta = json.loads((decks / "f02" / name / "deck.json").read_text())
        s = steady.get(steady_name(meta["case"]))
        if s is None:
            continue
        end = obs[name]["top_max_c_at_0p5s"][-1][1]
        diff = end - s["steady_top_c"]
        verdicts.append({"case": name, "check": "B7", "end_minus_steady_c": diff,
                         "pass": abs(diff) <= bands["B7_baseline_consistency_c"]})  # fmt: skip
    cost = _cost(ledger) if ledger else None
    slim = {
        k: {kk: vv for kk, vv in v.items() if kk not in ("top_max_c_at_0p5s", "patch_centres_c_at_0p5s")}
        for k, v in obs.items()
    }  # fmt: skip
    doc = {"schema": "carbon.f02-readiness.judgement.v1", "bands": bands["decision"],
           "set": manifest.get("set"), "image": manifest.get("image"),
           "observables": slim, "rung_comparisons": rungs, "baseline_checks": verdicts,
           "cost": cost}  # fmt: skip
    Path(out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return doc


def _cost(ledger):
    rows = [json.loads(x) for x in Path(ledger).read_text().splitlines() if x]
    kinds = {}
    for r in rows:
        if r["outcome"] != "COMPLETED":
            continue
        tag = r["case"].rsplit("-", 1)[-1]
        kind = r["reservation"] + (f":{tag}" if tag in ("mesh2", "dt0.5") else "")
        kinds.setdefault(kind, []).append(r)
    out = {}
    for kind, rs in sorted(kinds.items()):
        cpu = sorted(r["cgroup_cpu_s"] for r in rs if r["cgroup_cpu_s"] is not None)
        wall = sorted(r["wall_s"] for r in rs)
        mem = [
            r["cgroup_memory_peak_bytes"] for r in rs if r["cgroup_memory_peak_bytes"]
        ]
        out[kind] = {"n": len(rs), "cpu_s_min": cpu[0], "cpu_s_p50": cpu[len(cpu) // 2],
                     "cpu_s_max": cpu[-1], "cpu_s_mean": round(sum(cpu) / len(cpu), 2),
                     "wall_s_p50": wall[len(wall) // 2], "wall_s_max": wall[-1],
                     "peak_mib_max": round(max(mem) / 2**20, 1) if mem else None}  # fmt: skip
    out["failed"] = [r["case"] for r in rows if r["outcome"] != "COMPLETED"]
    out["host_profile"] = HOST_PROFILE
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_readiness")
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("set", choices=("convergence", "sample", "bank"))
    f.add_argument("out", type=Path)
    f.add_argument("--labels", default="")
    c = sub.add_parser("freeze-contenders")
    c.add_argument("bank", type=Path)
    c.add_argument("out", type=Path)
    r = sub.add_parser("run")
    r.add_argument("decks", type=Path)
    r.add_argument("--image", required=True)
    r.add_argument("--ledger", type=Path, required=True)
    r.add_argument("--parallel", type=int, default=1)
    j = sub.add_parser("judge")
    j.add_argument("decks", type=Path)
    j.add_argument("out", type=Path)
    j.add_argument("--ledger", type=Path)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        labels = [x for x in args.labels.split(",") if x]
        print(freeze(args.set, args.out, labels))
    elif args.command == "freeze-contenders":
        print(freeze_contenders(args.bank, args.out))
    elif args.command == "run":
        run(args.decks, args.image, args.ledger, args.parallel)
    else:
        doc = judge(args.decks, args.out, args.ledger)
        print(json.dumps(doc["cost"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
