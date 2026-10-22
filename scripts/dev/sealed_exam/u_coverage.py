"""C8 (VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022): does the registered U cover the exam region?

    PYTHONPATH=REPO python3 u_coverage.py plan KEY OUT_PLAN
    PYTHONPATH=REPO python3 u_coverage.py disjoint KEY CONFIG PLAN
    PYTHONPATH=REPO python3 u_coverage.py compute KEY RECORDS OUT

plan: 8 public cases drawn by the Challenge's own exam population (the placed
law the sealed batches use, which skips every published case) with the recorded
public seed `SEED`, in the family runner's plan format.
disjoint: counts how many plan geometries equal a geometry of any sealed batch
in the producer's store for the Challenge; prints only that count, exits 1 if it
is not 0 (no sealed value is shown).
compute: the largest rung step over the 8 cases against the registered U
(`exam_batch_qa.registered_u`). A step above U means the panel does not cover the
exam region: the answer is a re-measured U (v2) from these cases, never a
widened U (C8). Exits 1 on any case that is not a complete OK record or when a
step exceeds U. DEVELOPMENT; public cases only, nothing sealed.

Challenges: `f02` (rungs primary / mesh2 / dt0.5; the sealed QA spot-check is the
mesh2 step). F08 has its own v2 panel payload (Roache form); Motor, Cooling and
Battery are added here at their next rebuild.
"""

import importlib
import importlib.util
import json
import random
import sys
from pathlib import Path

SEED = 20261022
CASES = 8
CHALLENGES = {
    "f02": {
        "cid": "f02",
        "population": "carbon.f02.population",
        "quantity": "peak_top_c",
        "rungs": ("primary", "mesh2", "dt0.5"),
        "rung_field": "rung_peaks_c",
        "spot": ("mesh2", "primary"),
    },
}


def _spec(key):
    if key not in CHALLENGES:
        raise SystemExit(f"u_coverage: no coverage config for {key!r} yet")
    return CHALLENGES[key]


def plan(key, out):
    spec = _spec(key)
    module = importlib.import_module(spec["population"])
    cases, tries = module.draw(random.Random(SEED), CASES)
    document = {
        "batch": f"{key}-u-coverage",
        "kind": "screening",
        "seed": SEED,
        "draw_tries": tries,
        "cases": [{"case_id": f"ucov-{i}", "inputs": c} for i, c in enumerate(cases)],
    }
    Path(out).write_text(json.dumps(document, indent=1, sort_keys=True))
    print(json.dumps({"challenge": key, "seed": SEED, "cases": len(cases)}))


def disjoint(key, config, plan_path):
    from carbon.challenge_validator.producer import Producer

    spec = _spec(key)
    wanted = {
        tuple(sorted(c["inputs"].items()))
        for c in json.loads(Path(plan_path).read_text())["cases"]
    }
    source = Producer.from_config(config)._source(spec["cid"])
    overlap = 0
    for fingerprint in source.store.fingerprints():
        for case in source.store.batch(fingerprint)["document"]["cases"]:
            overlap += tuple(sorted(case["inputs"].items())) in wanted
    print(json.dumps({"sealed_overlap": overlap}))
    return 1 if overlap else 0


def _registered_u(key):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "exam_batch_qa", root / "scripts/dev/challenge_pools/exam_batch_qa.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.registered_u(_spec(key)["cid"])[_spec(key)["quantity"]]


def compute(key, records_path, out):
    spec = _spec(key)
    u = _registered_u(key)
    rows, stops = {}, []
    for line in Path(records_path).read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        rungs = record.get(spec["rung_field"]) or {}
        if record.get("status") != "OK" or set(rungs) != set(spec["rungs"]):
            stops.append(f"{record.get('case_id')}: {record.get('status')}, not a complete OK record")
            continue
        base = rungs[spec["rungs"][0]]
        steps = {r: abs(rungs[r] - base) for r in spec["rungs"][1:]}
        spot = abs(rungs[spec["spot"][0]] - rungs[spec["spot"][1]])
        rows[record["case_id"]] = {"rungs": rungs, "max_step": max(steps.values()), "spot_step": spot}
    if len(rows) + len(stops) != CASES or stops:
        stops.append(f"{len(rows)} OK records of {CASES}")
    largest = max((r["max_step"] for r in rows.values()), default=None)
    covered = largest is not None and largest <= u and not stops
    result = {
        "schema": "carbon.sealed-u-coverage.v1",
        "challenge": key,
        "seed": SEED,
        "quantity": spec["quantity"],
        "u": u,
        "largest_step": largest,
        "ratio_to_u": None if largest is None else largest / u,
        "covered": covered,
        "cases": rows,
        "stops": stops,
        "note": "a step above U means re-measure U on these cases (v2), never widen it (C8)",
    }
    Path(out).write_text(json.dumps(result, indent=1, sort_keys=True))
    print(json.dumps({k: result[k] for k in ("challenge", "u", "largest_step", "ratio_to_u", "covered")}))
    return 0 if covered else 1


if __name__ == "__main__":
    command, args = sys.argv[1], sys.argv[2:]
    if command == "plan" and len(args) == 2:
        plan(*args)
    elif command == "disjoint" and len(args) == 3:
        sys.exit(disjoint(*args))
    elif command == "compute" and len(args) == 3:
        sys.exit(compute(*args))
    else:
        raise SystemExit(__doc__)
