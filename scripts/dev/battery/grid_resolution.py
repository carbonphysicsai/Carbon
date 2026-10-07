"""quiz-diagnostics-v1 (b): grid-resolution sensitivity of the Q3 pick, on
the public stand-in only. It is a reported diagnostic and never a gate.

    python -m scripts.dev.battery.grid_resolution select --out DIR
    python -m scripts.dev.battery.grid_resolution jobs --out DIR
    python -m scripts.dev.battery.grid_resolution predict --out DIR --dev-results FILE
    python -m scripts.dev.battery.grid_resolution analyse --out DIR --dev-results FILE

- **Refined grid.** c1 in 0.125 C steps over 0.5–2.0 (13) × c2 in 0.1 C steps
  over 0.2–1.0 (9) = 117 points, the registered count. It contains EV4's
  35-point grid, so a scenario needs only 82 new solves.
- **Pool.** EV4's verification scenarios that have a feasible design (the v5
  rule).
- **Model-only.** For each member (the known-good set plus the run-5
  winner), its EV4-rules pick on the refined grid, snapped to the nearest
  coarse point, is compared with its pick on the coarse grid.
- **Reference-judged.** On 2 scenarios, the verdict (feasible, infeasible,
  unresolved) of each member's refined pick is compared with its coarse
  pick's. The 2 scenarios are fixed by the rule in `select` before any solve:
  the pool scenarios with the most coarse candidates within 1 band of a
  limit, ties to the lower id.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT = ROOT / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
REFS = ROOT / "docs/development/evidence/ev4-2026-10-01/decision-references.jsonl.gz"
C1 = tuple(round(0.5 + 0.125 * i, 3) for i in range(13))
C2 = tuple(round(0.2 + 0.1 * j, 3) for j in range(9))
WINNER = "graphite-run5-p-1d4aaff5d292-s3718551111"


def _load():
    from carbon.battery.value import contract as ev

    contract, _ = ev.load(CONTRACT)
    refs = {}
    for line in gzip.decompress(REFS.read_bytes()).decode().splitlines():
        if line.strip():
            record = json.loads(line)
            refs[record["case_id"]] = record
    return contract, refs


def refined_candidates():
    return [
        {"id": f"c1={c1:g},c2={c2:g}", "c1": c1, "c2": c2} for c1 in C1 for c2 in C2
    ]


def pool(contract, refs):
    from carbon.battery.value import contract as ev
    from carbon.battery.value import quiz

    return [
        s
        for s in ev.scenarios(contract, "verification")
        if quiz.q3_feasible(contract, s, refs)
    ]


def select(out):
    from carbon.battery.value import contract as ev
    from carbon.battery.value import margins

    contract, refs = _load()
    scenarios = pool(contract, refs)

    def near_count(scenario):
        count = 0
        for candidate in ev.candidates(contract):
            record = refs.get(ev.case_id(contract, scenario, candidate, 0))
            if record and record.get("status") == "OK":
                m = margins._margins(contract, record["outputs"])
                count += min(abs(v) for v in m.values()) <= 1.0
        return count

    ranked = sorted(scenarios, key=lambda s: (-near_count(s), s["id"]))
    chosen = [s["id"] for s in ranked[:2]]
    document = {
        "pool": [s["id"] for s in scenarios],
        "reference_judged": chosen,
        "rule": "the pool scenarios with the most coarse candidates within 1 band of a limit; ties to the lower id; fixed before any solve",
    }
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / "selection.json").write_text(json.dumps(document, indent=1) + "\n")
    return document


def _case(scenario_id, candidate):
    return f"grid117:{scenario_id}:{candidate['id']}:0"


def jobs(out):
    contract, _refs = _load()
    from carbon.battery.value import contract as ev

    selection = json.loads((Path(out) / "selection.json").read_text())
    coarse = {c["id"] for c in ev.candidates(contract)}
    scenarios = {s["id"]: s for s in ev.scenarios(contract, "verification")}
    out_jobs = []
    for sid in selection["reference_judged"]:
        t, soc = scenarios[sid]["conditions"][0]
        for candidate in refined_candidates():
            if candidate["id"] in coarse:
                continue
            out_jobs.append(
                {
                    "case_id": _case(sid, candidate),
                    "c1": candidate["c1"],
                    "c2": candidate["c2"],
                    "t_amb_c": float(t),
                    "soc0": float(soc),
                }
            )
    path = Path(out) / "jobs.json"
    path.write_text(
        json.dumps({"fingerprint": "public-grid117-v1", "jobs": out_jobs}, indent=1)
        + "\n"
    )
    return {"jobs": len(out_jobs)}


def _members(dev_results):

    results = json.loads(Path(dev_results).read_text())
    members = results["summary"]["members"]
    ev4 = [
        m
        for m, row in members.items()
        if row["kind"] == "RECONSTRUCTED" and not m.startswith("graphite-")
    ]
    values = {
        m: members[m]["loss_development"]
        for m in ev4
        if members[m]["loss_development"] is not None
    }
    best = sorted(values, key=lambda m: (values[m], m))[: max(1, len(values) // 4)]
    return best + [WINNER]


def predict(out, dev_results):
    """Rebuild each member on host CPU and predict the refined grid at every
    pool scenario."""
    from carbon.battery.value import panel as pn
    from carbon.battery.value.experiment import member_bundle
    from carbon.battery.worker import DirectBackend

    contract, refs = _load()
    scenarios = pool(contract, refs)
    inputs = {}
    for scenario in scenarios:
        t, soc = scenario["conditions"][0]
        for candidate in refined_candidates():
            inputs[_case(scenario["id"], candidate)] = {
                "c1": candidate["c1"],
                "c2": candidate["c2"],
                "t_amb_c": float(t),
                "soc0": float(soc),
            }
    wanted = set(_members(dev_results))
    rows = [
        r
        for panel in ("ev4", "graphite-run5")
        for r in pn.members(panel)
        if r[0] in wanted
    ]
    backend = DirectBackend(str(ROOT))
    target = Path(out) / "predictions"
    target.mkdir(parents=True, exist_ok=True)
    for member, _label, strategy, seed in rows:
        path = target / f"{member}.json.gz"
        if path.exists():
            continue
        bundle, _state = member_bundle(backend, member, strategy, seed, inputs)
        path.write_bytes(
            gzip.compress(json.dumps(bundle["predictions"]).encode(), mtime=0)
        )
    return {"members": len(rows), "inputs": len(inputs)}


def _pick(contract, scenario, candidates, predictions):
    from carbon.battery.value import decision as d

    quantities = {}
    for candidate in candidates:
        outputs = predictions.get(_case(scenario["id"], candidate))
        if outputs is None:
            return "MISSING"
        quantities[(candidate["id"], 0)] = d.measure(contract, outputs)
    predicted = d.assess_predicted(contract, scenario, candidates, quantities)
    selection = d.select(candidates, predicted)
    return selection


def _snap(candidate_id):
    c1, c2 = (float(x.split("=")[1]) for x in candidate_id.split(","))
    c1 = min((0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0), key=lambda v: (abs(v - c1), v))
    c2 = min((0.2, 0.4, 0.6, 0.8, 1.0), key=lambda v: (abs(v - c2), v))
    return f"c1={c1:g},c2={c2:g}"


def analyse(out, dev_results):
    from carbon.battery.value import contract as ev
    from carbon.battery.value import decision as d

    contract, refs = _load()
    scenarios = pool(contract, refs)
    selection = json.loads((Path(out) / "selection.json").read_text())
    coarse = ev.candidates(contract)
    refined = refined_candidates()
    coarse_ids = {c["id"] for c in coarse}
    # Refined references: coarse points from EV4's committed records, the
    # rest from the new solves.
    solved = {}
    path = Path(out) / "records.jsonl"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                solved[record["case_id"]] = record
    bands = contract["reference"]["uncertainty"]["bands"]

    def verdict(scenario, candidate_id):
        if candidate_id is None:
            return "ABSTAIN"
        cand = next(c for c in refined if c["id"] == candidate_id)
        if candidate_id in coarse_ids:
            record = refs.get(ev.case_id(contract, scenario, cand, 0))
        else:
            record = solved.get(_case(scenario["id"], cand))
        if not record or record.get("status") != "OK":
            return "REFERENCE_UNAVAILABLE"
        checks = d.check(contract, d.measure(contract, record["outputs"]), bands)
        if any(v == d.FAIL for v in checks.values()):
            return "INFEASIBLE"
        if any(v == d.UNRESOLVED for v in checks.values()):
            return "UNRESOLVED"
        return "FEASIBLE"

    def chosen_id(selection_obj):
        if selection_obj in (None, "MISSING"):
            return None
        if isinstance(selection_obj, dict):
            return selection_obj.get("id")
        return selection_obj

    members = sorted(
        p.name[: -len(".json.gz")]
        for p in (Path(out) / "predictions").glob("*.json.gz")
    )
    rows, shifts, total, changed, judged = {}, 0, 0, 0, 0
    for member in members:
        predictions = json.loads(
            gzip.decompress(
                (Path(out) / "predictions" / f"{member}.json.gz").read_bytes()
            )
        )
        member_rows = {}
        for scenario in scenarios:
            coarse_pick = chosen_id(_pick(contract, scenario, coarse, predictions))
            refined_pick = chosen_id(_pick(contract, scenario, refined, predictions))
            snapped = None if refined_pick is None else _snap(refined_pick)
            shifted = snapped != coarse_pick
            shifts += shifted
            total += 1
            entry = {
                "coarse": coarse_pick,
                "refined": refined_pick,
                "snapped": snapped,
                "shifted": shifted,
            }
            if scenario["id"] in selection["reference_judged"]:
                vc, vr = verdict(scenario, coarse_pick), verdict(scenario, refined_pick)
                entry["verdict_coarse"], entry["verdict_refined"] = vc, vr
                judged += 1
                changed += vc != vr
            member_rows[scenario["id"]] = entry
        rows[member] = member_rows
    document = {
        "schema": "carbon.battery.quiz-grid-resolution.v1",
        "diagnostic": "quiz-diagnostics-v1 (b); reported, never a gate",
        "grid": {
            "coarse": 35,
            "refined": len(refined),
            "c1_step": 0.125,
            "c2_step": 0.1,
        },
        "pool": [s["id"] for s in scenarios],
        "reference_judged": selection["reference_judged"],
        "members": len(members),
        "pick_shift_rate": shifts / total if total else None,
        "shifts": shifts,
        "decisions": total,
        "verdict_change_rate": changed / judged if judged else None,
        "verdict_changes": changed,
        "verdicts_judged": judged,
        "rows": rows,
    }
    (Path(out) / "grid-resolution.json").write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n"
    )
    return {
        k: document[k]
        for k in (
            "pick_shift_rate",
            "shifts",
            "decisions",
            "verdict_change_rate",
            "verdict_changes",
            "verdicts_judged",
        )
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="grid_resolution")
    parser.add_argument("command", choices=("select", "jobs", "predict", "analyse"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dev-results", type=Path)
    args = parser.parse_args(argv)
    if args.command == "select":
        result = select(args.out)
    elif args.command == "jobs":
        result = jobs(args.out)
    elif args.command == "predict":
        result = predict(args.out, args.dev_results)
    else:
        result = analyse(args.out, args.dev_results)
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
