"""f06 feature and control proof on the local box (DEVELOPMENT).

    python3 f06_controls.py build  --work DIR            # write all control cases
    python3 f06_controls.py run    --work DIR [--only PREFIX] [--parallel N]
    python3 f06_controls.py report --work DIR --out EVIDENCE.json

Acceptance values come from F06-SCIENCE-VALUES-01 (``ACCEPT`` below) and
were registered before these controls ran. Each job runs in the pinned Meep
image with ``--network none``, one CPU, an explicit memory limit, and records
cgroup CPU (cpu.stat usage_usec), memory.peak and wall time. Costs are a
NON-COMPARABLE ``local-dev-4vcpu-15g-contended`` profile.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import pairwise
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f06_deck as F

IMAGE = os.environ.get("F06_MEEP_IMAGE", "carbon-ref-meep:1.32.0")
RUNNER = HERE / "f06_run.py"
PANEL = (
    HERE.parents[3]
    / "docs/development/challenge_pipeline/round1/reference-route-panels.json"
)
DECISION = "F06-SCIENCE-VALUES-01"
#: Registered before the controls ran (F06-SCIENCE-VALUES-01).
ACCEPT = {
    "e_C": 0.010,
    "e_R": 0.005,
    "grid_C": 0.005,
    "grid_R": 0.0025,
    "pml_C": 0.002,
    "pml_R": 0.001,
    "pad_C": 0.002,
    "pad_R": 0.001,
    "time_C": 0.001,
    "time_R": 0.0005,
    "broadband_C": 0.002,
    "broadband_R": 0.001,
    "symmetry_C": 0.001,
    "symmetry_R": 0.001,
    "residual_abs": 0.010,
    "top_fields_vs_flux_abs": 0.002,
    "incident_drift_rel": 0.005,
    "flux_parity_rel": 0.002,
    "straight_reflection": 1e-4,
    "straight_transmission_rel": 0.002,
    "gaussian_overlap_rel": 0.005,
    "slab_neff_abs": 0.003,
    "repeat_abs": 0.0,
    "memory_headroom": 1.25,
    "local_3d_memory_gib": 10.0,
}
GRID_2D_NM = (40, 30, 20, 15, 10)
PROBE_STEPS = 300
#: cgroup v2 (cpu.stat usage_usec, memory.peak) or v1 (cpuacct.usage ns,
#: memory.max_usage_in_bytes), normalised to usage_usec / bytes.
CGROUP_CAPTURE = (
    "if [ -f /sys/fs/cgroup/cpu.stat ]; then cp /sys/fs/cgroup/cpu.stat cpu.stat; "
    "cat /sys/fs/cgroup/memory.peak > memory.peak; else "
    "echo usage_usec $(( $(cat /sys/fs/cgroup/cpuacct/cpuacct.usage) / 1000 )) > cpu.stat; "
    "cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes > memory.peak; fi"
)
HOST_PROFILE = "local-dev-4vcpu-15g-contended"


def panel():
    cases = json.loads(PANEL.read_text())["families"]["f06"]["public_cases"]
    return {c["label"]: F.design(*c["parameters"], label=c["label"]) for c in cases}


def case_doc(decks):
    return {"schema": "carbon.f06.meep-case.v1", "decks": decks}


def device_case(d, dim, h, groups=None, **kw):
    """Normalization + device decks for the given geometry groups."""
    groups = groups or [F.geometry_groups()[0]]
    decks = [F.deck(d, dim, h, vectors=groups[0], kind="normalization", **kw)]
    decks += [F.deck(d, dim, h, vectors=g, **kw) for g in groups]
    return case_doc(decks)


def single_frequency_cases(d, dim, h):
    out = []
    for i, f in enumerate(F.FREQUENCIES):
        kw = {"frequencies": [f], "fcen": f}
        out.append((f"sf{i}", device_case(d, dim, h, **kw)))
    return out


def jobs():
    """(name, case, memory) for every control; names sort into run groups."""
    P = panel()
    nominal, small = P["nominal"], P["short-narrow"]
    out = []
    slab = []
    for h_nm in GRID_2D_NM:
        for etch in (0, 70, 130):
            d = dict(nominal)
            dk = F.deck(d, 2, h_nm / 1000, kind="slab_mode")
            dk["geometry"]["etch_um"] = 0.0
            dk["stack"] = dict(dk["stack"], t_si_um=F.T_SI - etch / 1000)
            dk["extra"] = {"label": f"slab-{h_nm}nm-t{220 - etch}"}
            slab.append(dk)
    out.append(("c1-slab-mode", case_doc(slab), "2g"))
    g2 = F.deck(nominal, 2, 0.03, kind="gaussian_free")
    out.append(("c2-gaussian-2d", case_doc([g2]), "2g"))
    wide = dict(nominal, width_um=12.0)
    g3 = F.deck(wide, 3, 0.1, kind="gaussian_free", symmetric=False)
    g3["fibre"] = dict(
        g3["fibre"], w0_um=3.0, note="control beam w0 3.0 um fits the box"
    )
    out.append(("c3-gaussian-3d", case_doc([g3]), "4g"))
    norm = F.deck(small, 3, 0.03, kind="normalization")
    out.append(("c4-straight-3d-30nm", case_doc([norm]), "6g"))
    out.append(("c4-straight-3d-30nm-repeat", case_doc([norm]), "6g"))
    for label, d in P.items():
        for h_nm in GRID_2D_NM:
            out.append(
                (f"c5-grid2d-{label}-{h_nm}nm", device_case(d, 2, h_nm / 1000), "3g")
            )
    for label in ("nominal", "short-narrow"):
        d = P[label]
        out.append((f"c6-pml2d-{label}", device_case(d, 2, 0.03, pml=2.0), "2g"))
        out.append((f"c6-pad2d-{label}", device_case(d, 2, 0.03, pad_scale=2.0), "2g"))
        out.append(
            (f"c6-time2d-{label}", device_case(d, 2, 0.03, decay_tol=1e-8), "2g")
        )
        for tag, c in single_frequency_cases(d, 2, 0.03):
            out.append((f"c7-bb2d-{label}-{tag}", c, "2g"))
        out.append(
            (
                f"c7-bb2d-{label}-all-groups",
                device_case(d, 2, 0.03, groups=F.geometry_groups()),
                "2g",
            )
        )
    # Symmetry is a property of the deck, not the grid: check it coarse.
    for sym in (True, False):
        out.append((f"c8-sym3d-90nm-{'mirror' if sym else 'full'}",
                    device_case(small, 3, 0.09, symmetric=sym), "6g"))  # fmt: skip
    # Complete 45-row 3D panel (feature proof of the observer, not adequacy).
    out.append(
        (
            "c9-panel3d-90nm",
            device_case(small, 3, 0.09, groups=F.geometry_groups()),
            "6g",
        )
    )
    # Cost/memory probes: a few hundred steps, no observables (lead directive).
    for label, h_nm in (("short-narrow", 90), ("short-narrow", 60), ("short-narrow", 45),
                        ("long-wide", 60), ("short-narrow", 30), ("long-wide", 30)):  # fmt: skip
        for kind in ("normalization", "device"):
            dk = F.deck(P[label], 3, h_nm / 1000, kind=kind)
            dk["probe_steps"] = PROBE_STEPS
            out.append(
                (
                    f"p-{label}-{h_nm}nm-{kind}",
                    case_doc([dk]),
                    "12g" if h_nm == 30 else "6g",
                )
            )
    for label in ("nominal", "long-wide"):
        for h_nm in (30, 10):
            dk = F.deck(P[label], 2, h_nm / 1000)
            dk["probe_steps"] = PROBE_STEPS
            out.append((f"p2d-{label}-{h_nm}nm-device", case_doc([dk]), "2g"))
    return out


def build(work):
    work = Path(work)
    index = {}
    for name, case, mem in jobs():
        d = work / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "case.json").write_text(json.dumps(case, indent=1, sort_keys=True) + "\n")
        (d / "f06_run.py").write_bytes(RUNNER.read_bytes())
        index[name] = {
            "memory": mem,
            "case_sha256": hashlib.sha256((d / "case.json").read_bytes()).hexdigest(),
            "cells": [dk.get("cells") for dk in case["decks"]],
        }
    (work / "index.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    return index


def run_one(work, name, mem, cpus=1):
    d = Path(work) / name
    if (d / "result.json").exists():
        return
    script = (
        "python3 f06_run.py case.json result.json > meep.log 2>&1; rc=$?; "
        + CGROUP_CAPTURE
        + "; exit $rc"
    )
    cmd = ["docker", "run", "--rm", "--name", f"f06-{name}"[:60], "--network", "none",
           "--cpus", str(cpus), "--memory", mem, "--memory-swap", mem,
           "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{d.resolve()}:/case", "-w", "/case",
           IMAGE, "bash", "-c", script]  # fmt: skip
    t0 = time.time()
    rc = subprocess.run(cmd, capture_output=True, text=True, check=False).returncode
    wall = time.time() - t0
    cpu = {}
    if (d / "cpu.stat").exists():
        for line in (d / "cpu.stat").read_text().splitlines():
            k, v = line.split()[:2]
            cpu[k] = int(v)
    peak = (
        int((d / "memory.peak").read_text()) if (d / "memory.peak").exists() else None
    )
    (d / "cost.json").write_text(json.dumps({
        "rc": rc, "wall_s": wall, "cpu_s": cpu.get("usage_usec", 0) / 1e6,
        "memory_peak_mib": peak / 2**20 if peak else None, "memory_limit": mem,
        "cpus": cpus, "host_profile": HOST_PROFILE}, indent=1) + "\n")  # fmt: skip
    print(f"{name}: rc={rc} wall={wall:.0f}s", flush=True)


def run(work, only=None, parallel=1):
    index = json.loads((Path(work) / "index.json").read_text())
    names = [n for n in sorted(index) if not only or n.startswith(only)]
    with ThreadPoolExecutor(parallel) as pool:
        list(pool.map(lambda n: run_one(work, n, index[n]["memory"]), names))


# ----------------------------------------------------------------- analysis


def slab_neff_exact(lam, t, n_core=F.N_SI, n_sub=F.N_SIO2, n_clad=F.N_AIR):
    """TE0 of an asymmetric slab (E parallel to the layers), by bisection."""
    k0 = 2 * math.pi / lam

    def g(neff):
        kap = k0 * math.sqrt(n_core**2 - neff**2)
        gs = k0 * math.sqrt(neff**2 - n_sub**2)
        gc = k0 * math.sqrt(neff**2 - n_clad**2)
        return math.tan(kap * t) - kap * (gs + gc) / (kap**2 - gs * gc)

    lo, hi = n_sub + 1e-9, n_core - 1e-9
    # TE0 lies above the first pole of tan(kappa t); scan for the sign change
    grid = [lo + (hi - lo) * i / 20000 for i in range(20001)]
    roots = []
    for a, b in pairwise(grid):
        ga, gb = g(a), g(b)
        if ga * gb < 0 and abs(ga) < 1e3 and abs(gb) < 1e3:
            for _ in range(80):
                m = (a + b) / 2
                if g(a) * g(m) <= 0:
                    b = m
                else:
                    a = m
            roots.append((a + b) / 2)
    return max(roots)


def _load(work, name):
    d = Path(work) / name
    res = (
        json.loads((d / "result.json").read_text())
        if (d / "result.json").exists()
        else None
    )
    cost = (
        json.loads((d / "cost.json").read_text())
        if (d / "cost.json").exists()
        else None
    )
    return res, cost


def _device_rows(res):
    """{(vector, wavelength_um): (C, R)} plus per-row diagnostics."""
    out, diag = {}, []
    for r in res["results"]:
        if r["kind"] != "device":
            continue
        for row in r["rows"]:
            lam = round(row["wavelength_um"], 4)
            for v, c in row["coupling"].items():
                out[(int(v), lam)] = (c, row["reflection_te0"])
            diag.append({
                "vectors": r["vectors"], "wavelength_um": lam, "residual": row["residual"],
                "top_fields_minus_flux": row["top_from_fields"] - row["top"],
                "incident_drift": row["incident_amplitude_drift"],
                "R_flux": row["R_flux"], "R_te0": row["reflection_te0"],
                "top": row["top"], "bottom": row["bottom"], "front": row["front"],
                "sides": row.get("side_plus", 0) + row.get("side_minus", 0),
            })  # fmt: skip
    return out, diag


def _maxdiff(a, b, keys=None):
    keys = keys or sorted(set(a) & set(b))
    dc = max(abs(a[k][0] - b[k][0]) for k in keys)
    dr = max(abs(a[k][1] - b[k][1]) for k in keys)
    return dc, dr


def report(work, out):
    work = Path(work)
    index = json.loads((work / "index.json").read_text())
    ev = {"schema": "carbon.f06.control-proof.v1", "decision": DECISION, "accept": ACCEPT,
          "host_profile": HOST_PROFILE, "image": IMAGE, "checks": {}, "costs": {}}  # fmt: skip
    checks = ev["checks"]
    for name in sorted(index):
        res, cost = _load(work, name)
        if cost:
            entry = dict(
                cost, case_sha256=index[name]["case_sha256"], cells=index[name]["cells"]
            )
            if res:
                entry["runs"] = [{k: r.get(k) for k in ("kind", "label", "cells", "timesteps", "sim_time", "wall_s")} for r in res["results"]]  # fmt: skip
            ev["costs"][name] = entry
    # C1 slab
    res, _ = _load(work, "c1-slab-mode")
    if res:
        rows = []
        for r in res["results"]:
            h_nm, t_nm = r["label"].split("-")[1], int(r["label"].split("-t")[1])
            for row in r["rows"]:
                exact = slab_neff_exact(row["wavelength_um"], t_nm / 1000)
                rows.append({"grid": h_nm, "t_nm": t_nm, "wavelength_um": row["wavelength_um"],
                             "neff": row["neff"], "exact": exact, "error": row["neff"] - exact})  # fmt: skip
        per_grid = {}
        for row in rows:
            per_grid[row["grid"]] = max(per_grid.get(row["grid"], 0), abs(row["error"]))
        checks["c1_slab_mode"] = {"max_abs_error_by_grid": per_grid, "rows": rows,
                                  "pass_by_grid": {g: e <= ACCEPT["slab_neff_abs"] for g, e in per_grid.items()}}  # fmt: skip
    # C2/C3 gaussian
    for name, key in (
        ("c2-gaussian-2d", "c2_gaussian_2d"),
        ("c3-gaussian-3d", "c3_gaussian_3d"),
    ):
        res, _ = _load(work, name)
        if res:
            r = res["results"][0]
            frac = r["overlap_fraction_of_flux"]
            fvf = r["top_from_fields"] / r["top_flux"] - 1
            checks[key] = {"overlap_fraction_of_flux": frac, "fields_vs_flux_rel": fvf,
                           "pass": abs(frac - 1) <= ACCEPT["gaussian_overlap_rel"] and abs(fvf) <= ACCEPT["flux_parity_rel"]}  # fmt: skip
    # C4 straight
    a, _ = _load(work, "c4-straight-3d-30nm")
    b, _ = _load(work, "c4-straight-3d-30nm-repeat")
    if a:
        rows = a["results"][0]["rows"]
        ok = all(abs(r["flux_parity"]) <= ACCEPT["flux_parity_rel"]
                 and r["te0_reflection_straight"] <= ACCEPT["straight_reflection"]
                 and abs(r["te0_transmission_0p6um"] - 1) <= ACCEPT["straight_transmission_rel"] for r in rows)  # fmt: skip
        rep = None
        if b:
            rep = max(abs(x["p_in_mode"] - y["p_in_mode"]) / x["p_in_mode"] for x, y in zip(rows, b["results"][0]["rows"]))  # fmt: skip
        checks["c4_straight_3d_30nm"] = {"rows": rows, "pass": ok, "repeat_max_rel_diff": rep,
                                         "repeat_pass": rep is not None and rep <= ACCEPT["repeat_abs"]}  # fmt: skip
    # C5 grid ladder (2D)
    grid = {}
    for label in panel():
        vals = {}
        for h_nm in GRID_2D_NM:
            res, _ = _load(work, f"c5-grid2d-{label}-{h_nm}nm")
            if res:
                vals[h_nm] = _device_rows(res)[0]
        if 10 in vals and 15 in vals:
            fine = vals[10]
            keys = sorted(fine)
            tail_c, tail_r = _maxdiff(vals[15], fine, keys)
            entry = {
                "richardson_tail_C": 2 * tail_c,
                "richardson_tail_R": 2 * tail_r,
                "by_grid": {},
            }
            for h_nm in (40, 30, 20):
                if h_nm in vals:
                    dc, dr = _maxdiff(vals[h_nm], fine, keys)
                    entry["by_grid"][h_nm] = {"max_dC_vs_10nm": dc, "max_dR_vs_10nm": dr,
                                              "E_C": dc + 2 * tail_c, "E_R": dr + 2 * tail_r}  # fmt: skip
            entry["values"] = {
                str(h): {f"{k[0]}@{k[1]}": v for k, v in vals[h].items()} for h in vals
            }
            grid[label] = entry
    if grid:
        verdict = {}
        for h_nm in (40, 30, 20):
            rows = [g["by_grid"][h_nm] for g in grid.values() if h_nm in g["by_grid"]]
            if len(rows) == len(grid):
                ec = max(r["E_C"] for r in rows)
                er = max(r["E_R"] for r in rows)
                verdict[h_nm] = {"E_C_max": ec, "E_R_max": er,
                                 "pass": ec <= ACCEPT["grid_C"] and er <= ACCEPT["grid_R"]}  # fmt: skip
        passing = [h for h in (40, 30, 20) if verdict.get(h, {}).get("pass")]
        checks["c5_grid_2d"] = {"designs": grid, "verdict": verdict,
                                "coarsest_passing_nm": max(passing) if passing else None}  # fmt: skip
    # C6 PML / padding / time (2D) and residual diagnostics
    for label in ("nominal", "short-narrow"):
        base, _ = _load(work, f"c5-grid2d-{label}-30nm")
        if not base:
            continue
        b, _ = _device_rows(base)
        for kind, kc, kr in (
            ("pml", "pml_C", "pml_R"),
            ("pad", "pad_C", "pad_R"),
            ("time", "time_C", "time_R"),
        ):
            res, _ = _load(work, f"c6-{kind}2d-{label}")
            if res:
                dc, dr = _maxdiff(_device_rows(res)[0], b)
                checks[f"c6_{kind}_2d_{label}"] = {"max_dC": dc, "max_dR": dr,
                                                   "pass": dc <= ACCEPT[kc] and dr <= ACCEPT[kr]}  # fmt: skip
        # C7 broadband vs five single-frequency runs
        sf = {}
        for i in range(5):
            res, _ = _load(work, f"c7-bb2d-{label}-sf{i}")
            if res:
                sf.update(_device_rows(res)[0])
        if len(sf) == len(b):
            dc, dr = _maxdiff(b, sf)
            checks[f"c7_broadband_2d_{label}"] = {"max_dC": dc, "max_dR": dr,
                                                  "pass": dc <= ACCEPT["broadband_C"] and dr <= ACCEPT["broadband_R"]}  # fmt: skip
    # C8 symmetry
    a, _ = _load(work, "c8-sym3d-90nm-mirror")
    b, _ = _load(work, "c8-sym3d-90nm-full")
    if a and b:
        dc, dr = _maxdiff(_device_rows(a)[0], _device_rows(b)[0])
        checks["c8_symmetry_3d_90nm"] = {"max_dC": dc, "max_dR": dr,
                                         "pass": dc <= ACCEPT["symmetry_C"] and dr <= ACCEPT["symmetry_R"]}  # fmt: skip
    # Residual / flux-field / drift diagnostics over every device run
    diag_all = []
    for name in sorted(index):
        res, _ = _load(work, name)
        if res and any(r["kind"] == "device" for r in res["results"]):
            for row in _device_rows(res)[1]:
                diag_all.append(dict(row, job=name))
    if diag_all:
        worst = {
            "residual": max(abs(r["residual"]) for r in diag_all),
            "top_fields_minus_flux": max(
                abs(r["top_fields_minus_flux"]) for r in diag_all
            ),
            "incident_drift": max(r["incident_drift"] for r in diag_all),
        }
        checks["power_accounting"] = {
            "rows": len(diag_all), "worst": worst,
            "pass_residual": worst["residual"] <= ACCEPT["residual_abs"],
            "pass_top_fields": worst["top_fields_minus_flux"] <= ACCEPT["top_fields_vs_flux_abs"],
            "pass_incident_drift": worst["incident_drift"] <= ACCEPT["incident_drift_rel"],
            "failing_rows": [r for r in diag_all if abs(r["residual"]) > ACCEPT["residual_abs"]][:20],
        }  # fmt: skip
    # C9 witness
    res, cost = _load(work, "c9-panel3d-90nm")
    if res:
        rows, diag = _device_rows(res)
        checks["c9_panel_3d_90nm"] = {
            "rows": {f"{k[0]}@{k[1]}": v for k, v in rows.items()},
            "diagnostics": diag,
            "runs": [{k: r.get(k) for k in ("kind", "cells", "timesteps", "sim_time", "wall_s")} for r in res["results"]],
        }  # fmt: skip
    Path(out).write_text(json.dumps(ev, indent=1, sort_keys=True) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("build", "run", "report"))
    ap.add_argument("--work", required=True)
    ap.add_argument("--only")
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.action == "build":
        idx = build(a.work)
        print(json.dumps({k: v["cells"] for k, v in idx.items()}, indent=0))
    elif a.action == "run":
        run(a.work, a.only, a.parallel)
    else:
        report(a.work, a.out)


if __name__ == "__main__":
    main()
