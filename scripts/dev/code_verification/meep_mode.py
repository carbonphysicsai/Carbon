"""Native CPU FDTD vacuum Bloch-mode check; Data Collection executes.

Basic propagation check, not dielectric-interface or 3D overlap verification.
"""

import argparse
import hashlib
import json
from pathlib import Path


def run(resolution):
    import meep as mp

    if mp.__version__ != "1.32.0":
        raise RuntimeError("Meep package version must match the registered pin")
    mode = mp.Harminv(mp.Ex, mp.Vector3(0, 0, 0.17), 0.2, 0.08)
    simulation = mp.Simulation(
        cell_size=mp.Vector3(0, 0, 1),
        dimensions=1,
        resolution=resolution,
        force_complex_fields=True,
        k_point=mp.Vector3(0, 0, 0.2),
        sources=[
            mp.Source(
                mp.GaussianSource(0.2, fwidth=0.05),
                component=mp.Ex,
                center=mp.Vector3(),
            )
        ],
    )
    simulation.run(mp.after_sources(mode), until_after_sources=200)
    modes = [m for m in mode.modes if abs(m.freq - 0.2) < 0.04 and m.err < 1e-8]
    if len(modes) != 1:
        raise RuntimeError(
            "analytic mode unresolved; extend registered sampling prospectively"
        )
    row = {
        "h": 1 / resolution,
        "t": 0,
        "points": [[0.2]],
        "values": [float(modes[0].freq)],
        "weights": [1],
    }
    raw = {
        "frequency": float(modes[0].freq),
        "fit_error": float(modes[0].err),
        "resolution": resolution,
        "sampling_after_source": 200,
    }
    simulation.reset_meep()
    return row, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--spec-digest", required=True)
    args = parser.parse_args()
    rows, raw = [], []
    for n in (20, 40, 80):
        row, result = run(n)
        rows.append(row)
        raw.append(result)
    raw_path = args.output.with_suffix(".native.json")
    raw_path.write_text(json.dumps(raw, indent=2) + "\n")
    report = {
        "schema": "carbon.code-verification.fields.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "kind": "meep-bloch-mode",
        "family": "f06",
        "image_digest": args.image_digest,
        "spec_digest": args.spec_digest,
        "adapter_digest": "sha256:"
        + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
        "raw_outputs": [
            "sha256:"
            + hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
            for r in raw
        ],
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
