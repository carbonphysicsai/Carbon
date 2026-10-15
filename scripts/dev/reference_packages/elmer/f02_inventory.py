"""f02 public solve-inventory snapshot producer
(`carbon.development.solve-inventory-snapshot.v1`, F02-SCIENCE-VALUES-01).

    python3 f02_inventory.py pins --image ID --runtime-packages FILE --out PINS.json
    python3 f02_inventory.py snapshot --pins PINS.json --out SNAPSHOT.json \
        [--completed DECKS_DIR LEDGER ...] [--scheduled DECKS_DIR ...]

The registration handoff (carbon/challenge_pipeline/onboarding/registration.py)
deduplicates a proposed panel against every COMPLETED and SCHEDULED public
solve. This producer lists them for f02:

- COMPLETED: a deck in a solved frozen-deck directory whose ledger row is
  COMPLETED on the pinned image, whose files still match its manifest, and
  whose observables pass the registered conservation band (B5; B6 for
  steady baselines). Anything else is not usable reference work and is
  returned in `excluded` on stdout, never in the snapshot.
- SCHEDULED: a deck in a frozen-deck directory (manifest.json plus decks)
  that has no COMPLETED row.

Each row body is {challenge, coordinates, inputs, rung_settings, pins}:
coordinates = the action (peak W, on-time s), inputs = the context
(coolant, h, initial, split, waveform; `solve` transient or steady),
rung_settings = mesh level and dt scale. The five pins are digests of the
retained manifests in PINS.json (solver image, runtime environment,
materials, observer source, geometry/mesh grammar source), so a panel seed
built from the same PINS.json matches exactly. A source hash proves bytes,
not that every possible solve was included; the producer lists exactly the
directories and manifests it is given (an empty list gives an explicit
empty snapshot).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
for entry in (str(HERE), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import f02_deck as deck
import f02_readiness as readiness

from carbon.challenge_pipeline.onboarding import registration
from carbon.design_search import tasks

NAMESPACE = "public-development/f02/elmer-26.2.1"


def pin_manifests(image, runtime_packages):
    """The retained manifests behind the five pins."""
    raw = Path(runtime_packages).read_bytes()
    return {
        "solver": {"package": "elmer-26.2.1", "image_id": image,
                   "sources_lock_sha256": hashlib.sha256((HERE / "sources.lock.json").read_bytes()).hexdigest(),
                   "solver_banner": "ELMER SOLVER (v 26.2)", "heat_solver": "HeatSolve, hex808, BDF2"},
        "environment": {"runtime_packages_sha256": hashlib.sha256(raw).hexdigest(),
                        "isolation": "docker --network none --read-only --tmpfs /tmp --cpus 1, non-root",
                        "threads": {"OPENBLAS_NUM_THREADS": 1, "OMP_NUM_THREADS": 1},
                        "command": readiness.SOLVE},
        "materials": {"layers": {n: {"half_side_mm": v[0], "thickness_mm": v[1], "k": v[2], "rho": v[3], "cp": v[4]}
                                 for n, v in deck.LAYERS.items()},
                      "contact": "perfect", "cooling": "Robin on the whole copper underside"},
        "observer": {"limit_c": deck.LIMIT_C, "horizon_s": deck.HORIZON_S, "base_w": deck.BASE_W,
                     "source_sha256": hashlib.sha256("".join(inspect.getsource(f) for f in (
                         deck.read_scalars, deck.observe, deck.energy_balance, deck.stored_energy_j)).encode()).hexdigest()},
        "geometry_grammar": {"patch_half_mm": deck.PATCH_HALF, "patch_x_mm": deck.PATCH_X,
                             "burst_start_s": deck.BURST_START_S,
                             "source_sha256": hashlib.sha256("".join(inspect.getsource(f) for f in (
                                 deck._axis, deck._graded, deck.mesh, deck.write_mesh, deck.schedule,
                                 deck.time_steps, deck.sif)).encode()).hexdigest()},
    }  # fmt: skip


def pins(manifests):
    return {key: tasks.digest(value) for key, value in manifests.items()}


def body(meta, pin):
    case = meta["case"]
    steady = bool(meta.get("steady"))
    return {
        "challenge": "f02",
        "coordinates": {"peak_w": float(case["peak_w"]), "on_time_s": float(case["on_time_s"])},
        "inputs": {"coolant_c": float(case["coolant_c"]), "h_w_m2_k": float(case["h_w_m2_k"]),
                   "initial_c": float(case["initial_c"]),
                   "left_source_fraction": float(case["left_source_fraction"]),
                   "waveform": case["waveform"], "solve": "steady" if steady else "transient",
                   "source": "on" if meta.get("source", True) else "off",
                   "domain": "slab" if meta.get("slab") else "stack"},
        "rung_settings": {"mesh_level": int(meta["mesh"]["level"]),
                          "dt_scale": float(meta["dt_scale"])},
        "pins": pin,
    }  # fmt: skip


def _usable(case_dir, meta, bands):
    if meta.get("steady"):
        s = readiness.steady_observe(case_dir)
        return abs(s["balance_rel"]) <= bands["B6_steady_balance_rel"]
    if meta.get("slab") or not meta.get("source", True):
        return True  # controls are judged by their own analytic bands
    e = deck.energy_balance(case_dir)
    return abs(e["residual_rel"]) <= bands["B5_energy_residual_rel"]


def snapshot(pin_doc, completed=(), scheduled=(), as_of=None, commit=None):
    pin = pin_doc["pins"]
    image = pin_doc["manifests"]["solver"]["image_id"]
    bands = json.loads(readiness.BANDS.read_text())
    rows, excluded, seen = [], [], {}
    for decks, ledger in completed:
        decks = Path(decks)
        manifest = json.loads((decks / "manifest.json").read_text())
        ledger_rows = {}
        for line in Path(ledger).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                ledger_rows[r["case"]] = r
        for entry in manifest["cases"]:
            d = decks / entry["family"] / entry["case"]
            r = ledger_rows.get(entry["case"])
            meta = json.loads((d / "deck.json").read_text())
            b = body(meta, pin)
            identity = tasks.digest(b)
            reason = None
            if r is None:
                reason = "NOT_RUN"
            elif r["outcome"] != "COMPLETED" or r["image"] != image:
                reason = f"{r['outcome']} on {r['image']}"
            elif any(
                hashlib.sha256((d / f).read_bytes()).hexdigest() != h
                for f, h in entry["files"].items()
            ):
                reason = "DECK_FILES_CHANGED"
            elif not _usable(d, meta, bands):
                reason = "CONSERVATION_BAND_MISS"
            if reason:
                excluded.append({"case": entry["case"], "reason": reason})
                continue
            if identity in seen:
                continue
            line = json.dumps(r, sort_keys=True).encode()
            receipt = (f"ledger {Path(ledger).name} row sha256:{hashlib.sha256(line).hexdigest()}; "
                       f"deck {entry['case']} files {tasks.digest(entry['files'])}; image {image}")  # fmt: skip
            seen[identity] = "COMPLETED"
            rows.append(
                {
                    "identity": identity,
                    "state": "COMPLETED",
                    "receipt": receipt,
                    "body": b,
                }
            )
    for decks in scheduled:
        decks = Path(decks)
        manifest = json.loads((decks / "manifest.json").read_text())
        for entry in manifest["cases"]:
            d = decks / entry["family"] / entry["case"]
            meta = json.loads((d / "deck.json").read_text())
            b = body(meta, pin)
            identity = tasks.digest(b)
            if identity in seen:
                continue
            seen[identity] = "SCHEDULED"
            receipt = f"frozen manifest {decks.name}/manifest.json case {entry['case']} files {tasks.digest(entry['files'])}"
            rows.append(
                {
                    "identity": identity,
                    "state": "SCHEDULED",
                    "receipt": receipt,
                    "body": b,
                }
            )
    commit = commit or subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                      capture_output=True, text=True, check=True).stdout.strip()  # fmt: skip
    as_of = (
        as_of or datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat()
    )
    snap = registration.seal_inventory({
        "schema": registration.INVENTORY, "challenge": "f02", "scope": "PUBLIC_DEVELOPMENT",
        "source_commit": commit, "as_of_utc": as_of, "namespace": NAMESPACE, "rows": rows,
    })  # fmt: skip
    registration.inventory_rows(snap, "f02")  # the consumer's own validation
    return snap, excluded


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_inventory")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pins")
    p.add_argument("--image", required=True)
    p.add_argument("--runtime-packages", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--pins", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument(
        "--completed", nargs=2, action="append", default=[], metavar=("DECKS", "LEDGER")
    )
    s.add_argument("--scheduled", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    if args.command == "pins":
        m = pin_manifests(args.image, args.runtime_packages)
        doc = {
            "schema": "carbon.f02-readiness.pins.v1",
            "manifests": m,
            "pins": pins(m),
        }
        args.out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        print(json.dumps(doc["pins"], indent=1))
        return 0
    snap, excluded = snapshot(
        json.loads(args.pins.read_text()), args.completed, args.scheduled
    )
    args.out.write_text(json.dumps(snap, indent=1, sort_keys=True) + "\n")
    states = {}
    for r in snap["rows"]:
        states[r["state"]] = states.get(r["state"], 0) + 1
    print(
        json.dumps(
            {"rows": states, "excluded": excluded, "digest": snap["inventory_digest"]},
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
