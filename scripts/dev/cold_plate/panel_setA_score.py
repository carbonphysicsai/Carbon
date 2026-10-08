"""Score the set-A panel (cooling-feasibility-02/panel-setA-registry.json).

    python -m scripts.dev.cold_plate.panel_setA_score --jobs DIR --witness DIR --controls JSON --out JSON

Verdict (registered): the interval is the composed TIM2-interface peak plus
or minus the observed changes around it: the last coupling change, the
refinement change (the job's own rungs where it has them; otherwise the
largest change observed among the refined jobs of the same map, or of all
refined jobs for a uniform map) and, where the job has one, the 3D witness
difference. Entirely <= 85 C PASS, entirely > 85 C FAIL, otherwise
UNRESOLVED. The two hotspot maps are one question scored on the worse map.

Value checks: the Test Lead's revised T2 (2026-10-08), applied to every
question. (a) contested decisions: >= 5 PASS and >= 5 FAIL designs, the
FAILs within one band of the limit; the pass fraction is reported, not
gated. (b) margin spread >= 5 K. (c) >= 1 design PASS in all four
questions. (d) the best design (lowest dp x flow among PASS, ties by
margin) differs across >= 2 questions. Plus the complete-feasible count and
the residual UNRESOLVED rate (T4).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.cold_plate import panel_setA as pa

LIMIT = pa.LIMIT_C
QUESTIONS = {
    "cold_uniform": ("cold_uniform",),
    "typical_uniform": ("typical_uniform",),
    "warm_uniform": ("warm_uniform",),
    "warm_hotspot": ("warm_central_band", "warm_outlet_band"),
}
SPREAD_K, CONTESTED_N = 5.0, 5


def load(jobs_dir):
    jobs = {}
    for path in sorted(Path(jobs_dir).glob("*/job.json")):
        rec = json.loads(path.read_text())
        jobs[rec["job"]["job_id"]] = rec
    return jobs


def load_witnesses(witness_dir):
    out = {}
    if witness_dir and Path(witness_dir).exists():
        for path in Path(witness_dir).glob("*/witness.json"):
            rec = json.loads(path.read_text())
            if rec.get("interface_peak_c") is not None:
                out[(rec["design"], rec["context"])] = rec["interface_peak_c"]
    return out


def bands(jobs, witnesses):
    """Per (design, context): peak, band parts, verdict."""
    refine = {}
    for rec in jobs.values():
        if rec["job"]["kind"] != "refinement" or "verdict_inputs" not in rec:
            continue
        base = jobs.get(f"base-{rec['job']['design']}-{rec['job']['context']}", {}).get(
            "verdict_inputs"
        )
        if base:
            key = (rec["job"]["design"], rec["job"]["context"])
            change = abs(
                rec["verdict_inputs"]["interface_peak_c"] - base["interface_peak_c"]
            )
            refine[key] = max(refine.get(key, 0.0), change)
    by_context = {}
    for (_, ctx), change in refine.items():
        by_context[ctx] = max(by_context.get(ctx, 0.0), change)
    overall = max(refine.values(), default=None)
    cells = {}
    for design in pa.DESIGNS:
        for ctx in pa.CONTEXTS:
            rec = jobs.get(f"base-{design}-{ctx}")
            if rec is None:
                cells[(design, ctx)] = {"verdict": "NOT_RUN"}
                continue
            v = rec.get("verdict_inputs")
            if not v:
                cells[(design, ctx)] = {
                    "verdict": rec.get("verdict", "REFERENCE_UNRESOLVED"),
                    "why": rec.get("why"),
                }
                continue
            peak = v["interface_peak_c"]
            own = refine.get((design, ctx))
            ref = own if own is not None else by_context.get(ctx, overall)
            wit = (
                abs(witnesses[(design, ctx)] - peak)
                if (design, ctx) in witnesses
                else None
            )
            parts = {"coupling_k": v["last_peak_change_k"], "refinement_k": ref,
                     "refinement_source": "own" if own is not None else ("context" if ctx in by_context else "all"),
                     "witness_k": wit}  # fmt: skip
            if ref is None:
                verdict, band = "REFERENCE_UNRESOLVED", None
            else:
                band = parts["coupling_k"] + ref + (wit or 0.0)
                verdict = (
                    "PASS"
                    if peak + band <= LIMIT
                    else ("FAIL" if peak - band > LIMIT else "UNRESOLVED")
                )
            cells[(design, ctx)] = {"verdict": verdict, "peak_c": peak, "band_k": band, "margin_k": LIMIT - peak,
                                    "parts": parts, "hydraulic_power_w": v["hydraulic_power_w"],
                                    "applicability": v.get("cell_reasons")}  # fmt: skip
    return cells


def question(cells, design, contexts):
    rows = [cells[(design, c)] for c in contexts]
    verdicts = [r["verdict"] for r in rows]
    if "FAIL" in verdicts:
        verdict = "FAIL"
    elif all(v == "PASS" for v in verdicts):
        verdict = "PASS"
    else:
        verdict = "UNRESOLVED"
    scored = [r for r in rows if "peak_c" in r]
    worse = max(scored, key=lambda r: r["peak_c"]) if scored else {}
    return {"verdict": verdict, "peak_c": worse.get("peak_c"), "band_k": worse.get("band_k"),
            "margin_k": worse.get("margin_k"),
            "hydraulic_power_w": max((r["hydraulic_power_w"] for r in scored), default=None)}  # fmt: skip


def value_checks(per_q):
    out, best = {}, {}
    for q, rows in per_q.items():
        passes = [d for d, r in rows.items() if r["verdict"] == "PASS"]
        fails = [d for d, r in rows.items() if r["verdict"] == "FAIL"]
        near = [
            d
            for d in fails
            if rows[d]["band_k"] is not None
            and -rows[d]["margin_k"] <= rows[d]["band_k"] * 2
        ]
        resolved = len(passes) + len(fails)
        margins = [r["margin_k"] for r in rows.values() if r["margin_k"] is not None]
        if passes:
            best[q] = min(
                passes,
                key=lambda d: (rows[d]["hydraulic_power_w"], -rows[d]["margin_k"]),
            )
        out[q] = {
            "pass": len(passes), "fail": len(fails), "fail_near_frontier": len(near),
            "unresolved": sum(r["verdict"] not in ("PASS", "FAIL") for r in rows.values()),
            "pass_fraction_reported": len(passes) / resolved if resolved else None,
            "a_contested": len(passes) >= CONTESTED_N and len(near) >= CONTESTED_N,
            "margin_spread_k": max(margins) - min(margins) if margins else None,
            "b_spread": bool(margins) and max(margins) - min(margins) >= SPREAD_K,
            "best_min_hydraulic": best.get(q),
        }  # fmt: skip
    complete = sorted(
        d for d in pa.DESIGNS if all(per_q[q][d]["verdict"] == "PASS" for q in per_q)
    )
    return {
        "per_question": out,
        "a_all": all(v["a_contested"] for v in out.values()),
        "b_all": all(v["b_spread"] for v in out.values()),
        "c": bool(complete),
        "complete_feasible_designs": complete,
        "d": len(set(best.values())) >= 2,
        "distinct_bests": sorted(set(best.values())),
    }


def score(jobs_dir, witness_dir, controls, out):
    jobs, witnesses = load(jobs_dir), load_witnesses(witness_dir)
    cells = bands(jobs, witnesses)
    per_q = {
        q: {d: question(cells, d, ctxs) for d in pa.DESIGNS}
        for q, ctxs in QUESTIONS.items()
    }
    n_q = sum(len(v) for v in per_q.values())
    unresolved = sum(
        r["verdict"] not in ("PASS", "FAIL") for v in per_q.values() for r in v.values()
    )
    document = {
        "schema": "carbon.cooling.setA-score.v1",
        "registry": "docs/development/evidence/cooling-feasibility-02/panel-setA-registry.json",
        "near_frontier_rule": "a FAIL counts as near the frontier when its overshoot is within 2 x its band (one refinement band either side of the limit)",
        "cells": {f"{d}|{c}": v for (d, c), v in cells.items()},
        "questions": per_q,
        "value_checks": value_checks(per_q),
        "t4_unresolved_rate": unresolved / n_q,
        "witnesses": {f"{d}|{c}": p for (d, c), p in witnesses.items()},
        "controls": json.loads(Path(controls).read_text())
        if controls and Path(controls).exists()
        else None,
        "jobs_scored": len(jobs),
        "cell_wall_s": {jid: rec.get("cell_wall_s_total") for jid, rec in jobs.items()},
    }
    Path(out).write_text(
        json.dumps(document, indent=1, sort_keys=True, default=str) + "\n"
    )
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(prog="panel_setA_score")
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--witness", type=Path)
    parser.add_argument("--controls", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    doc = score(args.jobs, args.witness, args.controls, args.out)
    print(json.dumps(doc["value_checks"], indent=1))
    print("T4 unresolved rate", doc["t4_unresolved_rate"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
