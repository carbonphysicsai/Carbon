"""Host-side f17 observers on raw OpenFOAM output (no solver post-processing).

    python3 f17_extract.py CASE_DIR [--out OBSERVED.json]

For every flow: Δp (ρ × area-weighted inlet kinematic p), mass balance,
outlet backflow count, iterations, convergence (N2). For every scalar: the
packet observer on raw outlet face c and face flux (`outlet_observer`),
raw c extrema over all cells, advective + diffusive solute balance over every
boundary face (`balances`, B2 floor), iterations and N5 convergence, and the
retained-phi identity. Values judged against F17-SCIENCE-VALUES-01.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3]))

from carbon.challenge_pipeline import micromixer_readiness as mm

import f17_foam as foam

RHO = 998.0
BANDS = {
    "mass_balance": 0.005,
    "solute_balance": 0.005,
    "c_bounds": (-0.001, 1.001),
    "volume_rel": 0.005,
    "flow_p_stationary_rel": 1e-5,
    "solute_floor_fraction": 1e-6,
}


def latest_time(case_dir):
    times = [
        p.name
        for p in Path(case_dir).iterdir()
        if p.is_dir() and p.name.replace(".", "").isdigit() and p.name != "0"
    ]
    return max(times, key=float) if times else None


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def data_sha(path):
    buf = Path(path).read_bytes()
    return hashlib.sha256(buf[buf.index(b"\ndimensions") + 1 :]).hexdigest()


class Case:
    def __init__(self, case_dir):
        self.dir = Path(case_dir)
        self.deck = json.loads((self.dir / "deck.json").read_text())
        poly = self.dir / "mesh/constant/polyMesh"
        self.mesh = foam.Mesh(poly)
        self.patches = list(self.mesh.boundary)
        self.volume = float(
            np.sum(foam.read_field(self.dir / "mesh/constant/V")["internal"])
        )
        cc = foam.read_field(self.dir / "mesh/constant/C", self.patches)
        self.centres, self.face_centres = cc["internal"], cc["patch"]
        self.geom = {
            n: self.mesh.face_geometry(n)
            for n in ("inlet0", "inlet1", "outlet")
            if self.mesh.boundary[n]["nFaces"]
        }

    def owner(self, patch):
        return self.mesh.owner[self.mesh.patch_slice(patch)]

    def mesh_report(self):
        analytic = self.deck["analytic_volume_m3"]
        log = (self.dir / "mesh/log.checkMesh").read_text()
        stats = {}
        for key in ("cells", "faces", "points"):
            line = next(x for x in log.splitlines() if x.strip().startswith(key + ":"))
            stats[key] = int(line.split()[-1])
        nonorth = next(
            x for x in log.splitlines() if "non-orthogonality Max" in x
        ).split()
        skew = next(x for x in log.splitlines() if "Max skewness" in x).split()
        rel = self.volume / analytic - 1
        return {
            **stats,
            "mesh_ok": "Mesh OK" in log,
            "max_non_orthogonality_deg": float(nonorth[3]),
            "max_skewness": float(skew[3]),
            "patch_faces": {n: b["nFaces"] for n, b in self.mesh.boundary.items()},
            "fluid_volume_m3": self.volume,
            "analytic_volume_m3": analytic,
            "volume_rel_error": rel,
            "volume_ok": abs(rel) <= BANDS["volume_rel"],
            "mesh_sha256": (self.dir / "mesh/mesh.sha256").read_text().split()[::2],
        }

    def flow(self, name):
        d = self.dir / name
        t = latest_time(d)
        if t is None:
            return {"flow": name, "status": "MISSING"}
        p = foam.read_field(d / t / "p", ["inlet0", "inlet1"])
        phi = foam.read_field(d / t / "phi", self.patches)["patch"]
        p_internal = p["internal"]
        areas = {
            n: np.linalg.norm(self.geom[n][0], axis=1) for n in ("inlet0", "inlet1")
        }
        # zero-gradient inlets: face p is the owner cell p
        p_face = {n: p_internal[self.owner(n)] for n in ("inlet0", "inlet1")}
        a = np.concatenate([areas["inlet0"], areas["inlet1"]])
        pf = np.concatenate([p_face["inlet0"], p_face["inlet1"]])
        f = np.concatenate([-phi["inlet0"], -phi["inlet1"]])
        all_phi = np.concatenate(
            [
                np.atleast_1d(np.asarray(phi[n], dtype=float))
                * np.ones(self.mesh.boundary[n]["nFaces"])
                for n in self.patches
                if self.mesh.boundary[n]["nFaces"]
            ]
        )
        inflow = float(f.sum())
        out_phi = np.asarray(phi["outlet"], dtype=float)
        hist = _history(d / "postProcessing/inletP/0/surfaceFieldValue.dat")
        hist0 = _history(d / "postProcessing/inletP0/0/surfaceFieldValue.dat")
        stationary = None
        if len(hist) > 10:
            stationary = abs(hist[-1][1] - hist[-11][1]) / abs(hist[-1][1])
        log = (d / "log.simpleFoam").read_text()
        converged = "SIMPLE solution converged" in log
        receipt = (
            (d / "receipt.txt").read_text() if (d / "receipt.txt").exists() else ""
        )
        return {
            "flow": name,
            "time": t,
            "iterations": int(float(t)),
            "solver_converged": converged,
            "p_stationary_rel_last10": stationary,
            "converged": bool(
                converged
                and stationary is not None
                and stationary <= BANDS["flow_p_stationary_rel"]
            ),
            "delta_p_pa": RHO * float((a * pf).sum() / a.sum()),
            "delta_p_flux_weighted_pa": RHO * float((f * pf).sum() / f.sum()),
            "delta_p_infunction_pa": (
                RHO
                * (
                    hist[-1][1] * areas["inlet1"].sum()
                    + hist0[-1][1] * areas["inlet0"].sum()
                )
                / a.sum()
                if hist and hist0
                else None
            ),
            "inflow_m3_s": inflow,
            "mass_residual_fraction": abs(float(all_phi.sum())) / inflow,
            "outlet_backflow_faces": int((out_phi < 0).sum()),
            "receipt": receipt.split("\n")[0] if receipt else None,
            "phi_data_sha256": data_sha(d / t / "phi"),
        }

    def scalar(self, name, diffusivity, q_m3_s):
        d = self.dir / name
        status = (d / "STATUS").read_text().strip() if (d / "STATUS").exists() else None
        t = latest_time(d)
        if t is None:
            return {"scalar": name, "status": status or "MISSING"}
        T = foam.read_field(d / t / "T", self.patches)
        phi = foam.read_field(d / t / "phi", self.patches)["patch"]
        c = T["internal"]
        adv, dif, flux = [], [], []
        incoming_solute = 0.0
        for n in self.patches:
            nf = self.mesh.boundary[n]["nFaces"]
            if not nf:
                continue
            own = self.owner(n)
            ph = np.asarray(phi[n], dtype=float) * np.ones(nf)
            val = T["patch"].get(n)
            fixed = val is not None and n.startswith("inlet")
            cf = np.asarray(val, dtype=float) * np.ones(nf) if fixed else c[own]
            a = ph * cf
            if fixed and diffusivity > 0:
                sf = self.geom[n][0]
                delta = self.face_centres[n] - self.centres[own]
                mag = np.linalg.norm(sf, axis=1)
                nhat = sf / mag[:, None]
                dcoef = 1 / np.einsum("ij,ij->i", nhat, delta)
                g = -diffusivity * (cf - c[own]) * dcoef * mag
            else:
                g = np.zeros(nf)
            adv.append(a)
            dif.append(g)
            flux.append(ph)
            if n.startswith("inlet"):
                incoming_solute -= float((a + g).sum())
        adv, dif, flux = map(np.concatenate, (adv, dif, flux))
        inflow = float(-flux[flux < 0].sum())
        bal = mm.balances(
            flux,
            adv,
            dif,
            incoming_volume=inflow,
            incoming_solute=max(incoming_solute, 0.0),
            solute_floor=BANDS["solute_floor_fraction"] * q_m3_s,
        )
        own = self.owner("outlet")
        out_c, out_phi = c[own], np.asarray(phi["outlet"], dtype=float)
        try:
            obs = mm.outlet_observer(out_c, out_phi, self.volume, 0.0, 0.0)
            obs.pop("pressure_pa")
            obs["applicable"] = True
        except ValueError as exc:
            obs = {"applicable": False, "reason": str(exc)}
        hist = _history(d / "postProcessing/outletMix/0/surfaceFieldValue.dat")
        span = None
        if len(hist) > 10:
            ms = [1 - math.sqrt(max(r[2] - r[1] ** 2, 0) / 0.25) for r in hist[-10:]]
            span = max(ms) - min(ms)
        ceiling = int(
            (d / "system/controlDict").read_text().split("endTime")[1].split(";")[0]
        )
        lo, hi = BANDS["c_bounds"]
        return {
            "scalar": name,
            "status": status,
            "diffusivity_m2_s": diffusivity,
            "time": t,
            "iterations": int(float(t)),
            "converged": int(float(t)) < ceiling and status is None,
            "M_span_last10": span,
            **obs,
            "cell_c_min_max": [float(c.min()), float(c.max())],
            "bounds_ok": bool(c.min() >= lo and c.max() <= hi),
            "incoming_solute": incoming_solute,
            **bal,
            "mass_ok": bal["mass_residual_fraction"] <= BANDS["mass_balance"],
            "solute_ok": bal["solute_residual_fraction"] <= BANDS["solute_balance"],
            "phi_data_sha256": data_sha(d / t / "phi"),
            "T_data_sha256": data_sha(d / t / "T"),
        }


def _history(path):
    if not Path(path).exists():
        return []
    rows = []
    for line in Path(path).read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        rows.append([float(x) for x in line.split()])
    return rows


def observe(case_dir):
    case = Case(case_dir)
    deck = case.deck
    flows = {f"flow_q{q:g}": case.flow(f"flow_q{q:g}") for q in deck["flows_ul_min"]}
    scalars = {}
    for s in deck["scalars"]:
        q = s["flow_ul_min"] * 1e-9 / 60
        r = case.scalar(s["dir"], s["diffusivity_m2_s"], q)
        f = flows.get(f"flow_q{s['flow_ul_min']:g}", {})
        if "mixing" in r:
            r["pressure_pa"] = f.get("delta_p_pa")
            r["residence_s"] = case.volume / q
            r["phi_is_flow_phi"] = r["phi_data_sha256"] == f.get("phi_data_sha256")
        scalars[s["dir"]] = {**s, **r}
    runs = {}
    for p in sorted(case.dir.glob("run*.json")):
        runs[p.name] = json.loads(p.read_text())
    return {
        "schema": "carbon.f17.observed.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "label": deck.get("label"),
        "design": deck["design"],
        "mesh_h_um": deck["mesh_h_um"],
        "mesh": case.mesh_report(),
        "flows": flows,
        "scalars": scalars,
        "runs": runs,
        "bands": BANDS,
        "decision": deck["decision"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    result = observe(args.case)
    text = json.dumps(result, indent=1, default=float) + "\n"
    if args.out:
        args.out.write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
