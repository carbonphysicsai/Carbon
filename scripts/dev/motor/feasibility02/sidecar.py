"""Motor curve sidecar (#917 / #925 return) for the design-search adapter.

    python -m scripts.dev.motor.feasibility02.sidecar --runs DIR... --out JSON

Per geometry: the six grammar coordinates, the physical mesh-builder
geometry (`topology.geometry`), the coil area; per solved case: command (J,
gamma, phase current), the signed torque curve and angles, RMS |B| where the
flux observers ran, convergence checks, status, deck digest and run identity.

Grammar -> physical (topology.geometry, 10p12s): embrace = coverage;
slot_open_deg = opening_frac * 360 / slots; tooth_w (mm) = tooth_frac * 2 pi
r_si / slots with r_si = r_ro + airgap (r_ro 25.6 mm); h_m = magnet_mm;
r_sb = slot_bottom_mm.

Skew (registry design_space.skew): step skew with three equal slices at
mechanical offsets d in {-s/2, 0, +s/2}; slice k is a full-stack-equivalent
2D solve read at rotor angle theta + d_k with current angle gamma - 5 d_k
(5 pole pairs, same phase currents); the stack torque is the mean of the
three slice curves; ripple from that mean curve; zero-current cogging is
the same average of pure shifts of the J 0 curve. No 3D or skew-edge effects.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.motor.feasibility02 import stages
from scripts.dev.motor.feasibility02 import topology as tp

TOPO = tp.TOPOLOGIES["10p12s"]


def build(runs):
    records = stages._records(runs)
    designs = {}
    for cid, r in sorted(records.items()):
        d = r.get("design")
        if not d:
            continue
        key = hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]
        entry = designs.setdefault(key, {
            "grammar": d, "geometry_mm_deg": tp.geometry(TOPO, d),
            "coil_area_mm2": r.get("coil_area_mm2"), "tags": set(), "cases": []})  # fmt: skip
        entry["tags"].add(cid.rsplit("-j", 1)[0])
        out = r.get("outputs") or {}
        entry["cases"].append({
            "case_id": cid, "status": r.get("status"), "j_a_mm2": r.get("j_a_mm2"), "gamma_deg": r.get("gamma_deg"),
            "current_a": r.get("current_a"), "options": r.get("options"), "angle_deg": out.get("angle_deg"),
            "torque_nm": out.get("torque_nm"), "b_rms_t": out.get("b_rms_t"), "checks": r.get("checks"),
            "reasons": r.get("reasons"), "machine_pro_sha256": r.get("machine_pro_sha256"), "image": r.get("image"),
            "mesh": r.get("mesh")})  # fmt: skip
    for entry in designs.values():
        entry["tags"] = sorted(entry["tags"])
    return {"schema": "carbon.motor.curve-sidecar.v1", "skew": __doc__.split("Skew")[1].strip(),
            "mapping": "embrace = coverage; slot_open_deg = opening_frac * 360/slots; tooth_w_mm = tooth_frac * 2 pi (25.6 + airgap_mm) / slots",
            "designs": designs}  # fmt: skip


def main(argv=None):
    parser = argparse.ArgumentParser(prog="motor sidecar")
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = build(args.runs)
    text = json.dumps(doc, sort_keys=True)
    args.out.write_text(text + "\n")
    print(json.dumps({"designs": len(doc["designs"]), "cases": sum(len(d["cases"]) for d in doc["designs"].values()),
                      "sha256": hashlib.sha256((text + "\n").encode()).hexdigest()}))  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
