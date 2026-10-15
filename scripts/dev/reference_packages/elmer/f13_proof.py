"""f13 v2 feature/control proof helpers (F13-SCIENCE-VALUES-01).

    python -m scripts.dev.reference_packages.elmer.f13_proof run DIR [--cpus 1 --memory 3g]
    python -m scripts.dev.reference_packages.elmer.f13_proof observe DIR [--lead-mm 50]

`run` meshes a case directory written by f13_deck.write_case in the pinned
Gmsh image and solves it in the pinned Elmer image, one container each, with
no network, a read-only root and explicit CPU/memory limits. Cost comes from
the container's own cgroup (CPU ns and peak memory, cgroup v1 or v2) and the
monotonic wall clock, written to DIR/cost.json. `observe` maps ports.dat by
its explicit column names and applies the de-embedded panel-plane observer
(silencer_readiness.observe_rows) for any ordered frequency list.

Helpers for the comparisons the decision registers (C4 resolved/notch floor,
D6 prominent extrema, interval p10/mean) live here so the proof, the triage
freeze and the bank path share one implementation.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.challenge_pipeline import silencer_readiness as sr
from carbon.development_comparison.portfolio_baselines import (
    interval_p10,
)
from scripts.dev.reference_packages.elmer import f13_deck as deck

IMAGE = sr.IMAGE
HOST_PROFILE = "local-dev-4vcpu-15g-contended"
SOLVE = "ElmerGrid 14 2 mesh.msh -autoclean -out mesh > grid.log 2>&1 && ElmerSolver case.sif > solver.log 2>&1"
#: Written after the command inside the container: cgroup v1 then v2 paths.
ACCOUNT = (
    "rc=$?; times > times.txt; "
    "{ cat /sys/fs/cgroup/cpuacct/cpuacct.usage 2>/dev/null || "
    "awk '/usage_usec/{print $2*1000}' /sys/fs/cgroup/cpu.stat; } > cpu.ns; "
    "{ cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null || "
    "cat /sys/fs/cgroup/memory.peak; } > memory.peak; exit $rc"
)

# F13-SCIENCE-VALUES-01 bands (decision file is the authority).
RESOLVED_TL_DB = 20.0  # C4
NOTCH_FLOOR_W = 1.0e-3  # C4
PROMINENCE_DB = 3.0  # D6
RESONANCE_HZ = 10.0  # D1/D3
MESH_TL_DB = 0.5  # D1
LEAD_TL_DB = 0.25  # D2
LEAD_T_ABS = 0.03  # D2
INTEGRAL_DB = 0.25  # D1/D2/D3 p10 and mean
PARITY_TL_DB = 0.01  # D4/D5
PARITY_T_ABS = 1e-4  # D4/D5


def _container(image, case_dir, command, cpus, memory, name, timeout):
    case_dir = Path(case_dir).resolve()
    for f in ("cpu.ns", "memory.peak", "times.txt"):
        (case_dir / f).unlink(missing_ok=True)
    cmd = [
        "docker", "run", "--rm", "--name", name, "--network", "none", "--read-only",
        "--tmpfs", "/tmp", "--cpus", str(cpus), "--memory", memory, "--memory-swap", memory,
        "--pids-limit", "16", "--user", f"{os.getuid()}:{os.getgid()}",
        "-e", "HOME=/tmp", "-v", f"{case_dir}:/case", "-w", "/case", image,
        "bash", "-c", f"{command}; {ACCOUNT}",
    ]  # fmt: skip
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        code, outcome = (
            proc.returncode,
            "COMPLETED" if proc.returncode == 0 else "FAILED",
        )
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
        code, outcome = None, "CENSORED_TIMEOUT"
    wall = time.monotonic() - t0

    def read(f):
        p = case_dir / f
        return p.read_text().strip() if p.exists() and p.read_text().strip() else None

    cpu_ns = read("cpu.ns")
    peak = read("memory.peak")
    return {
        "exit": code,
        "outcome": outcome,
        "wall_s": round(wall, 2),
        "cpu_s": round(int(float(cpu_ns)) / 1e9, 2) if cpu_ns else None,
        "peak_mib": round(int(peak) / 2**20, 1) if peak else None,
        "cpus": cpus,
        "memory_limit": memory,
    }


def run(case_dir, image=IMAGE, cpus=1, memory="3g", timeout=7200, tag=None, lock=None):
    """Mesh (if needed) and solve one case directory; write cost.json.

    With `lock` (the shared host's big-run lock file), the solve waits for an
    exclusive flock first; the recorded wall time excludes the wait."""
    case_dir = Path(case_dir)
    tag = tag or case_dir.name
    cost = {"host_profile": HOST_PROFILE, "nproc": os.cpu_count(), "cpu_model": _cpu_model(),
            "image": image, "mesh_image": deck.MESH_IMAGE}  # fmt: skip
    if not (case_dir / "mesh.msh").exists():
        cost["mesh"] = _container(deck.MESH_IMAGE, case_dir, "python3 make_mesh.py", 1, "3g",
                                  f"f13-mesh-{tag}"[:60], timeout)  # fmt: skip
        if cost["mesh"]["exit"] != 0:
            (case_dir / "cost.json").write_text(json.dumps(cost, indent=1) + "\n")
            return cost
    groups = case_dir / "groups.json"
    if groups.exists():
        cost["nodes"] = json.loads(groups.read_text())["nodes"]
    with open(lock or os.devnull, "a") as held:
        if lock:
            fcntl.flock(held, fcntl.LOCK_EX)
        cost["solve"] = _container(image, case_dir, SOLVE, cpus, memory,
                                   f"f13-solve-{tag}"[:60], timeout)  # fmt: skip
    meta = json.loads((case_dir / "deck.json").read_text())
    cost["frequency_systems"] = len(meta["frequencies_hz"])
    if cost["solve"]["cpu_s"]:
        cost["cpu_s_per_frequency"] = round(
            cost["solve"]["cpu_s"] / cost["frequency_systems"], 2
        )
    (case_dir / "cost.json").write_text(json.dumps(cost, indent=1) + "\n")
    return cost


def _cpu_model():
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return None


def observe(case_dir, lead_mm=None):
    """De-embedded panel-plane rows for a solved case (any frequency list)."""
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    lead_mm = meta.get("stub_mm", 60.0) - 10.0 if lead_mm is None else lead_mm
    integrals = deck.port_integrals(case_dir)
    freqs = [r["f_hz"] for r in integrals]
    if freqs != [float(f) for f in meta["frequencies_hz"]]:
        raise ValueError("saved frequencies differ from the deck")
    rows, finding = sr.observe_rows(freqs, integrals, lead_m=lead_mm / 1000)
    return rows, finding


def summary(rows):
    f = [r["frequency_hz"] for r in rows]
    tl = [r["tl_db"] for r in rows]
    out = {
        "frequencies": len(rows),
        "max_abs_plane_residual": max(abs(r["signed_plane_residual"]) for r in rows),
        "max_abs_integral_residual": max(
            abs(r["signed_integral_residual"]) for r in rows
        ),
        "minimum_tl_db": min(tl),
        "maximum_tl_db": max(tl),
    }
    if len(rows) > 2:
        out["p10_tl_db"] = interval_p10(f, tl)
        out["mean_tl_db"] = sr.interval_mean(f, tl)
    return out


def extrema(freqs, tl, prominence=PROMINENCE_DB):
    """Prominent local extrema (D6): [(kind, f_parabolic, tl)]."""
    out = []
    n = len(tl)
    for i in range(1, n - 1):
        for kind, sign in (("max", 1), ("min", -1)):
            y = [sign * v for v in tl]
            if not (y[i] > y[i - 1] and y[i] >= y[i + 1]):
                continue
            # topographic prominence: drop to the higher of the two bases
            left = min(y[j] for j in range(_reach(y, i, -1), i + 1))
            right = min(y[j] for j in range(i, _reach(y, i, 1) + 1))
            if y[i] - max(left, right) < prominence:
                continue
            y0, y1, y2 = y[i - 1], y[i], y[i + 1]
            den = y0 - 2 * y1 + y2
            df = freqs[i + 1] - freqs[i]
            shift = 0.5 * (y0 - y2) / den * df if den else 0.0
            out.append((kind, freqs[i] + shift, tl[i]))
    return out


def _reach(y, i, step):
    """Index range until a strictly higher point (or the end) on one side."""
    j = i
    while 0 <= j + step < len(y) and y[j + step] <= y[i]:
        j += step
    return j


def compare(a_rows, b_rows, tl_band, complex_band=None):
    """Pointwise/integral/extremum comparison of two curves on their common
    frequencies (C4 resolved rule, D6 extrema matched from curve a)."""
    fa = {r["frequency_hz"]: r for r in a_rows}
    fb = {r["frequency_hz"]: r for r in b_rows}
    common = sorted(set(fa) & set(fb))
    worst_db = worst_w = worst_t = 0.0
    at_db = at_w = None
    fails = []
    for f in common:
        ra, rb = fa[f], fb[f]
        if max(ra["tl_db"], rb["tl_db"]) <= RESOLVED_TL_DB:
            d = abs(ra["tl_db"] - rb["tl_db"])
            if d > worst_db:
                worst_db, at_db = d, f
            if d > tl_band:
                fails.append(f)
        else:
            d = abs(ra["transmitted_w"] - rb["transmitted_w"])
            if d > worst_w:
                worst_w, at_w = d, f
            if d > NOTCH_FLOOR_W:
                fails.append(f)
        if complex_band is not None:
            dt = abs(complex(*ra["t"]) - complex(*rb["t"]))
            worst_t = max(worst_t, dt)
    out = {
        "common_frequencies": len(common),
        "max_abs_dtl_db_resolved": worst_db,
        "at_hz": at_db,
        "max_abs_dpt_w_notch": worst_w,
        "notch_at_hz": at_w,
        "pointwise_band_db": tl_band,
        "pointwise_fail_hz": fails,
    }
    if complex_band is not None:
        out["max_abs_dt"] = worst_t
        out["complex_band"] = complex_band
    if len(common) > 2:
        fs = common
        ta = [fa[f]["tl_db"] for f in fs]
        tb = [fb[f]["tl_db"] for f in fs]
        out["dp10_db"] = interval_p10(fs, ta) - interval_p10(fs, tb)
        out["dmean_db"] = sr.interval_mean(fs, ta) - sr.interval_mean(fs, tb)
        ea, eb = extrema(fs, ta), extrema(fs, tb)
        shifts = []
        for kind, f0, _ in ea:
            same = [g for k, g, _ in eb if k == kind]
            shifts.append(
                {"kind": kind, "f_hz": f0,
                 "shift_hz": min((abs(g - f0) for g in same), default=None)}
            )  # fmt: skip
        out["extrema"] = shifts
        out["extrema_counts"] = [len(ea), len(eb)]
        worst_shift = max(
            (s["shift_hz"] for s in shifts if s["shift_hz"] is not None), default=0.0
        )
        out["max_extremum_shift_hz"] = worst_shift
        out["pass"] = (
            not fails
            and abs(out["dp10_db"]) <= INTEGRAL_DB
            and abs(out["dmean_db"]) <= INTEGRAL_DB
            and all(s["shift_hz"] is not None for s in shifts)
            and worst_shift <= RESONANCE_HZ
            and (complex_band is None or worst_t <= complex_band)
        )
    else:
        out["pass"] = not fails and (complex_band is None or worst_t <= complex_band)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f13_proof")
    parser.add_argument("command", choices=("run", "observe"))
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--cpus", default="1")
    parser.add_argument("--memory", default="3g")
    parser.add_argument("--timeout", type=float, default=7200)
    parser.add_argument("--lead-mm", type=float)
    parser.add_argument("--lock", help="flock this file around the solve")
    args = parser.parse_args(argv)
    if args.command == "run":
        print(
            json.dumps(
                run(
                    args.case_dir,
                    args.image,
                    args.cpus,
                    args.memory,
                    args.timeout,
                    lock=args.lock,
                )
            )
        )
    else:
        rows, finding = observe(args.case_dir, args.lead_mm)
        print(json.dumps({"finding": finding, **summary(rows)}))
    return 0


def frequency_refinement(coarse_rows, fine_rows):
    """D3: each curve on its own grid; prominent minima of the fine curve
    must have a coarse-curve minimum within RESONANCE_HZ."""
    fc = [r["frequency_hz"] for r in coarse_rows]
    ff = [r["frequency_hz"] for r in fine_rows]
    tc = [r["tl_db"] for r in coarse_rows]
    tf = [r["tl_db"] for r in fine_rows]
    dp10 = interval_p10(fc, tc) - interval_p10(ff, tf)
    dmean = sr.interval_mean(fc, tc) - sr.interval_mean(ff, tf)
    coarse_min = [f for k, f, _ in extrema(fc, tc) if k == "min"]
    minima = []
    for kind, f0, tl in extrema(ff, tf):
        if kind == "min":
            near = min((abs(g - f0) for g in coarse_min), default=None)
            minima.append({"f_hz": f0, "tl_db": tl, "nearest_coarse_min_hz": near})
    ok = (
        abs(dp10) <= INTEGRAL_DB
        and abs(dmean) <= INTEGRAL_DB
        and all(m["nearest_coarse_min_hz"] is not None
                and m["nearest_coarse_min_hz"] <= RESONANCE_HZ for m in minima)
    )  # fmt: skip
    return {"dp10_db": dp10, "dmean_db": dmean, "fine_minima": minima,
            "dmin_tl_db": min(tc) - min(tf), "pass": ok}  # fmt: skip


def saved_integral_check(case_dir, revision, image=IMAGE):
    """Run scripts/dev/f13_saved_integral_check.py on a solved case's own
    retained files, with the explicit column map (no new solve)."""
    from scripts.dev import f13_saved_integral_check as sic

    case_dir = Path(case_dir)
    data, names, meta = (
        case_dir / n for n in ("ports.dat", "ports.dat.names", "deck.json")
    )
    cols = deck.column_map(names.read_text())
    mapping = {
        "schema": sic.SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "sha256": {k: hashlib.sha256(f.read_bytes()).hexdigest()
                   for k, f in (("data", data), ("names", names), ("deck", meta))},
        "source": {"revision": revision, "image_digest": image,
                   "model": "EQUAL_PORT_PLANE_ROBIN_REAL_INCIDENT", "phasor": "exp(+i*omega*t)"},
        "area_basis": "OPERATOR_VERIFIED_EQUAL_PORT_AREAS_AND_BC_IDS",
        "columns": {k: {"index": i, "name": n} for k, (i, n) in cols.items()},
    }  # fmt: skip
    raw = json.dumps(mapping).encode()
    return sic.check_saved(
        data.read_bytes(), names.read_bytes(), meta.read_bytes(), raw
    )


def adaptive_emulation(
    dense_rows, start_hz=40.0, floor_hz=10.0, tol_db=0.25, low_margin_db=2.0
):
    """Emulate reference-routes.md rank 3 on a solved dense 10 Hz curve.

    Start on a start_hz grid, probe every interval midpoint (mandatory),
    and keep splitting down to floor_hz wherever the midpoint departs from
    the chord by more than tol_db or the interval touches the low-TL region
    (TL <= running p10 + low_margin_db). Sampling a node returns the dense
    curve's value at that node, which D4 (scan vs separate parity) makes
    equivalent to solving it. Returns the sampled grid and its p10/mean/
    minima against the dense curve (D7 judges adoption)."""
    tl = {r["frequency_hz"]: r["tl_db"] for r in dense_rows}
    f0, f1 = min(tl), max(tl)
    grid = {f0 + i * start_hz for i in range(round((f1 - f0) / start_hz) + 1)}
    width = start_hz
    while width > floor_hz:
        fs = sorted(grid)
        p10 = interval_p10(fs, [tl[f] for f in fs])
        new = set()
        for a, b in itertools.pairwise(fs):
            if b - a <= floor_hz + 1e-9:
                continue
            mid = (a + b) / 2
            if mid not in tl:
                continue
            chord = (tl[a] + tl[b]) / 2
            if (
                width == start_hz
                or abs(tl[mid] - chord) > tol_db
                or min(tl[a], tl[b], tl[mid]) <= p10 + low_margin_db
            ):
                new.add(mid)
        if not new:
            break
        grid |= new
        width /= 2
    fs = sorted(grid)
    rows = [r for r in dense_rows if r["frequency_hz"] in grid]
    out = frequency_refinement(rows, dense_rows)
    out["points"] = len(fs)
    out["dense_points"] = len(dense_rows)
    return out


#: Cost model fitted to this host's measured v2 runs (f13-bulk-sizing.md):
#: solve CPU per frequency system = PER_FREQ_S * (nodes / NODES_REF)^EXP for
#: BiCGStabl+ILU2 on second-order tetrahedra, plus SETUP_S (ElmerGrid and
#: assembly); peak memory = MIB_PER_NODE * nodes + BASE_MIB. Local timings
#: are a contended development profile, so the estimates carry SAFETY.
PER_FREQ_S, NODES_REF, EXP, SETUP_S = 8.3, 32566, 1.29, 3.0
MIB_PER_NODE, BASE_MIB, SAFETY = 0.0055, 20.0, 1.5


def estimate(nodes, frequency_systems):
    """{estimate_cpu_s, estimate_wall_s, estimate_mem_mib} for one curve on
    one dedicated CPU (the bulk runner's manifest fields)."""
    cpu = SETUP_S + frequency_systems * PER_FREQ_S * (nodes / NODES_REF) ** EXP
    return {
        "estimate_cpu_s": round(SAFETY * cpu, 1),
        "estimate_wall_s": round(SAFETY * cpu * 1.1, 1),
        "estimate_mem_mib": round(SAFETY * (MIB_PER_NODE * nodes + BASE_MIB), 1),
    }


if __name__ == "__main__":
    sys.exit(main())
