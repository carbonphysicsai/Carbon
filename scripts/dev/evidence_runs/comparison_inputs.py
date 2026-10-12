"""Producer-side comparison inputs for the evidence campaign (EVIDENCE-PRODUCER-STAGES-01,
Test Lead 2026-10-12: Data Collection builds these from registered evidence; the
Optimizer Codex owns the comparison design that consumes them).

- `candidate_view(export)`: the sealed export with every reference value and
  settlement removed. It keeps the true `export_digest` and the candidates,
  actions, conditions and observable names. The TRAIN stage, which must never
  see held-out reference values, builds the model's predictions from it.
- `cost_ledger_*`: per physical candidate (band, candidate, condition), every
  reference solve behind it (standard and refinement rungs), with its measured
  wall time and its CPU time where the record measured it.
- `plain_bindings(export)`: the replay bindings for a plain (non-indexed)
  export. Each question's bank, one design per candidate. Indexed exports
  (battery v3) bind designs across bands, a comparison-design choice the
  replay panel makes, so they are refused here.
- `predictions(...)`: the Carbon arm's registered default recipe
  (`carbon_arm.run`) trained on the registered TRAIN and queried on the
  candidate view.

Reads values only; sets no limit, band, design or fold.
"""

from __future__ import annotations

import copy
import itertools
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CANDIDATE_VIEW = "carbon.development-evidence-campaign.producer-candidate-view.v1"
COST_LEDGER = "carbon.development-evidence-campaign.producer-cost-ledger.v1"
BINDINGS = "carbon.development-replay-bindings.v1"


def candidate_view(export):
    """No reference value, refined rung or settlement leaves the reference stage."""
    from carbon.development_comparison import cheap_baselines as cb

    body = copy.deepcopy(export)
    for entry in body["questions"]:
        entry.pop("settled", None)
        for _band, _task, panel in cb._panels(entry):
            for row in panel:
                row["values"] = {
                    q: 0.0 for q in row["values"] if not q.startswith("refined.")
                }
    return {"schema": CANDIDATE_VIEW, "export_digest": export["export_digest"], "family": export["family"],
            "export": body}  # fmt: skip


def _rows(export):
    from carbon.development_comparison import cheap_baselines as cb

    return cb._physical_rows(export)


def _ledger(export, solves_for, basis):
    rows = []
    for row in _rows(export):
        solves = solves_for(row)
        if not solves:
            raise ValueError(
                f"no reference solve behind {row['band']}/{row['candidate']}/{row['condition']}"
            )
        core = [s["core_s"] for s in solves]
        rows.append({"band": row["band"], "candidate": row["candidate"], "condition": row["condition"],
                     "solves": solves, "wall_s": sum(s["wall_s"] for s in solves),
                     "core_s": None if None in core else sum(core)})  # fmt: skip
    return {"schema": COST_LEDGER, "family": export["family"], "export_digest": export["export_digest"],
            "basis": basis, "rows": rows}  # fmt: skip


def cost_ledger_battery(export, runs, standard_dirs, rung3_dirs):
    """Battery solves run one process each (CPU cap 1); records hold wall time only."""

    def key(c1, c2, sv, h, t):
        return (
            round(float(c1), 4),
            round(float(c2), 4),
            round(float(sv), 4),
            round(float(h), 4),
            float(t),
        )

    index = {}
    for rung3, dirs in ((False, standard_dirs), (True, rung3_dirs)):
        for name in dirs:
            path = Path(runs) / name / "records.jsonl"
            if not path.exists():
                continue
            for line in path.read_text().splitlines():
                r = json.loads(line) if line.strip() else None
                if (
                    not r
                    or r.get("case_id", "").startswith("control-")
                    or r.get("soc0", 0.1) != 0.1
                    or "wall_s" not in r
                ):
                    continue
                k = key(
                    r["c1"],
                    r["c2"],
                    r.get("switch_voltage_v", 4.0),
                    r["h_multiplier"],
                    r["t_amb_c"],
                )
                rung = (
                    "rung3"
                    if rung3
                    else "rung2" if r["case_id"].startswith("refined:") else "standard"
                )
                index.setdefault(k, []).append({"source": f"{name}:{r['case_id']}", "rung": rung, "status": r["status"],
                                                "wall_s": float(r["wall_s"]), "core_s": None})  # fmt: skip

    def solves_for(row):
        a, band = row["action"], row["band"]
        return index.get(key(a["c1"], a["c2"], a["switch_v"], a["cooling"], band), [])

    return _ledger(
        export,
        solves_for,
        "battery: one PyBaMM process per solve, CPU cap 1; wall_s from each record, "
        "core_s not measured per solve (at most wall_s)",
    )


def cost_ledger_f02(export, root):
    """f02 solves record their container's user+system CPU (`times`)."""
    sys.path.insert(0, str(ROOT / "scripts/dev/reference_packages/elmer"))
    import f02_menu as menu

    ledger = {}
    for line in (Path(root) / "ledger.jsonl").read_text().splitlines():
        r = json.loads(line) if line.strip() else None
        if r:
            ledger[r["case"]] = r

    def solves_for(row):
        a = row["action"]
        out = []
        for tag in ("primary", "mesh2", "dt0.5"):
            r = ledger.get(
                menu.case_name(row["condition"], a["peak_w"], a["on_time_s"], tag)
            )
            if r is not None:
                cpu = menu._cpu_s(r["children_cpu"]) if r.get("children_cpu") else None
                out.append({"source": f"ledger:{r['case']}", "rung": tag, "status": r.get("outcome"),
                            "wall_s": float(r["wall_s"]), "core_s": cpu})  # fmt: skip
        return out

    return _ledger(
        export,
        solves_for,
        "f02: one ElmerSolver per solve, CPU cap 1; wall_s and the container's "
        "measured user+system CPU (times) per solve",
    )


def plain_bindings(export):
    from carbon.development_comparison import cheap_baselines as cb

    jobs = []
    for entry in export["questions"]:
        panels = cb._panels(entry)
        if len(panels) != 1 or panels[0][0] is not None:
            raise ValueError(
                "indexed exports bind designs across bands: the replay panel's choice"
            )
        jobs.append({"job_id": entry["case"], "case": entry["case"],
                     "candidates": {c: {"plain": c} for c in panels[0][1]["candidates"]}})  # fmt: skip
    return {"schema": BINDINGS, "export_digest": export["export_digest"], "jobs": jobs}


def predictions(family, view, train_jsonl, *, scope, material=None, seed=0):
    """(predictions, receipt) from the registered default recipe on registered TRAIN."""
    import hashlib

    from carbon.development_comparison import carbon_arm

    if view.get("schema") != CANDIDATE_VIEW or view["family"] != family:
        raise ValueError("a matching candidate view is required")
    kit = carbon_arm.kits()[family](material)
    train = carbon_arm.load_train(
        kit, train_jsonl, "sha256:" + hashlib.sha256(train_jsonl).hexdigest()
    )
    return carbon_arm.run(kit, view["export"], train, scope=scope, seed=seed)


def _write(path, document):
    Path(path).write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    )


def main(argv=None):
    """`view EXPORT OUT` | `ledger-battery EXPORT RUNS OUT` | `ledger-f02 EXPORT ROOT OUT`
    | `bindings EXPORT OUT` | `predict FAMILY VIEW TRAIN_JSONL PREDICTIONS RECEIPT`
    | `f02-materials EXPORT ROOT BASELINE_ROOT OUTDIR`."""
    argv = sys.argv[1:] if argv is None else argv
    cmd, args = argv[0], argv[1:]
    if cmd == "f02-materials":
        export = json.loads(Path(args[0]).read_text())
        materials, chunks = f02_materials(export, args[1], args[2])
        out = Path(args[3])
        out.mkdir(parents=True, exist_ok=True)
        _write(out / "comparator-materials.json", materials)
        files = []
        for chunk in chunks:
            files.append(out / f"comparator-witness-{chunk['chunk']:03d}.json")
            _write(files[-1], chunk)
        _write(
            out / "comparator-witness-manifest.json",
            witness_manifest(export["export_digest"], files),
        )
        return 0
    if cmd == "predict":
        family, view, train, out_pred, out_receipt = args[:5]
        material = None
        if (
            family == "motor"
        ):  # the geometry-only material from the registered reference plan
            material = json.dumps(motor_geometry(ROOT / args[5])).encode()
        pred, receipt = predictions(family, json.loads(Path(view).read_text()), Path(train).read_bytes(),
                                    scope="PUBLIC_DEVELOPMENT", material=material)  # fmt: skip
        _write(out_pred, pred)
        _write(out_receipt, receipt)
        return 0
    export = json.loads(Path(args[0]).read_text())
    if cmd == "view":
        _write(args[1], candidate_view(export))
    elif cmd == "bindings":
        _write(args[1], plain_bindings(export))
    elif cmd == "ledger-motor":
        _write(args[2], cost_ledger_motor(export, args[1]))
    elif cmd == "motor-curves":
        _write(args[3], motor_curve_set(export, args[1], args[2]))
    elif cmd == "ledger-f02":
        _write(args[2], cost_ledger_f02(export, args[1]))
    elif cmd == "ledger-battery":
        sys.path.insert(0, str(ROOT / "scripts/dev/battery"))
        import feasibility02_tier4 as t4
        import middle_bands_refine as mbr
        import v3_panel_export as v3

        standard = (*t4.DIRS, mbr.STAGE_A_DIR, mbr.RUNG2_DIR)
        _write(
            args[2],
            cost_ledger_battery(
                export, args[1], standard, (v3.RUNG3_DIR, mbr.RUNG3_DIR)
            ),
        )
    else:
        raise SystemExit(f"unknown command {cmd}")
    return 0


# -- f02 comparator materials (Test Lead 2026-10-12: separate grids) ---------------------

WITNESS = "carbon.development-evidence-campaign.producer-f02-witness.v1"
WITNESS_MANIFEST = (
    "carbon.development-evidence-campaign.producer-f02-witness-manifest.v1"
)
COARSE_DT_S, FINE_DT_S, FIR_LAGS = (
    0.5,
    0.02,
    128,
)  # 128 lags of 0.5 s = 64 s (Test Lead)
WITNESS_CHUNK_ROWS = 96


def _sha256_hex(raw):
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def _integral(sched, a, b):
    """Exact integral of a piecewise-linear schedule [(t, w)] over [a, b]."""
    total = 0.0
    for (t0, p0), (t1, p1) in itertools.pairwise(sched):
        lo, hi = max(a, t0), min(b, t1)
        if hi <= lo or t1 <= t0:
            continue
        slope = (p1 - p0) / (t1 - t0)
        total += (hi - lo) * (p0 + slope * ((lo + hi) / 2 - t0))
    return total


def _top_trace(case_dir):
    import f02_deck as deck

    cols, rows = deck.read_scalars(case_dir)
    i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
    return [r[0] for r in rows], [r[i_top] - 273.15 for r in rows]


def _on_grid(times, values, dt, start, stop):
    """The trace at every coarse grid time, by linear interpolation between solver
    steps (the deck's steps lie on or within 1e-6 s of these times). This feeds
    the FIR fit only; the exact peak check uses the fine witness."""
    import numpy as np

    grid = [start + k * dt for k in range(round((stop - start) / dt) + 1)]
    return [float(v) for v in np.interp(grid, times, values)]


def _bin_max(times, values, start, stop, dt):
    """Per 0.02 s bin, the largest solver value in it, so the witness's maximum is
    the export's peak over every solver step exactly. A bin with no step is
    filled by linear interpolation, which never exceeds a step value."""
    import numpy as np

    n = round((stop - start) / dt) + 1
    bins = [None] * n
    for t, v in zip(times, values):
        k = round((t - start) / dt)
        if 0 <= k < n and (bins[k] is None or v > bins[k]):
            bins[k] = v
    grid = [start + k * dt for k in range(n)]
    if any(b is None for b in bins):
        filled = np.interp(grid, times, values)
        bins = [float(filled[k]) if b is None else b for k, b in enumerate(bins)]
    return bins


def f02_materials(export, root, baseline_root, *, scope="PUBLIC_DEVELOPMENT"):
    """(materials, witness chunks, witness manifest) for the impulse-response comparator."""
    sys.path.insert(0, str(ROOT / "scripts/dev/reference_packages/elmer"))
    import f02_baselines as fb
    import f02_deck as deck
    import f02_menu as menu

    from carbon.design_search import tasks
    from carbon.development_comparison import portfolio_baselines as pb

    ledger = {}
    for line in (Path(root) / "ledger.jsonl").read_text().splitlines():
        r = json.loads(line) if line.strip() else None
        if r:
            ledger[r["case"]] = r
    contexts = dict(menu.contexts())
    rows, witness, observers = [], [], set()
    for entry in export["questions"]:
        observers.add(entry["task"]["identity"]["observer_version"])
    for row in _rows(export):
        ctx, a = row["condition"], row["action"]
        case = menu.case_name(ctx, a["peak_w"], a["on_time_s"])
        case_dir, base_dir = Path(root) / "cases" / case, Path(
            baseline_root
        ) / "cases" / fb.baseline_name(ctx)
        context = contexts[ctx]
        sched = deck.schedule(
            {**context, "peak_w": a["peak_w"], "on_time_s": a["on_time_s"]}
        )
        left = context["left_source_fraction"]
        times, top = _top_trace(case_dir)
        btimes, btop = _top_trace(base_dir)
        grid = [k * COARSE_DT_S for k in range(round(deck.HORIZON_S / COARSE_DT_S) + 1)]
        extra = []
        for t in grid[:-1]:
            mean = _integral(sched, t, t + COARSE_DT_S) / COARSE_DT_S - deck.BASE_W
            extra.append([left * mean, (1 - left) * mean])
        extra.append([0.0, 0.0])
        payload = {
            "time_s": grid,
            "extra_power_w": extra,
            "baseline_temperature_c": [
                [v] for v in _on_grid(btimes, btop, COARSE_DT_S, 0.0, deck.HORIZON_S)
            ],
            "temperature_c": [
                [v] for v in _on_grid(times, top, COARSE_DT_S, 0.0, deck.HORIZON_S)
            ],
        }
        source = _sha256_hex((case_dir / "scalars.dat").read_bytes())
        rows.append({
            "candidate": row["candidate"], "condition": ctx,
            "context_sha256": _sha256_hex(json.dumps(context, sort_keys=True).encode()),
            "coordinates": [a["peak_w"], a["on_time_s"]],
            "reference_source_sha256": source,
            "calibration_source_sha256": _sha256_hex((base_dir / "scalars.dat").read_bytes()),
            "payload": payload,
        })  # fmt: skip
        events = [t for t, _ in sched if 0 < t < deck.HORIZON_S]
        peak_t = times[max(range(len(top)), key=top.__getitem__)]
        start = min(deck.BURST_START_S, FINE_DT_S * int(peak_t / FINE_DT_S))
        stop = max(
            (max(events) + 10.0) if events else deck.BURST_START_S + 10.0, peak_t
        )
        stop = start + FINE_DT_S * math.ceil((stop - start) / FINE_DT_S - 1e-9)
        trace = _bin_max(times, top, start, stop, FINE_DT_S)
        if max(trace) != max(top) or max(top) != row["values"]["peak_top_c"]:
            raise ValueError(f"{case}: the witness does not reproduce the export peak")
        witness.append({"candidate": row["candidate"], "condition": ctx, "reference_source_sha256": source,
                        "window_start_s": start, "dt_s": FINE_DT_S, "top_c": trace,
                        "peak_top_c": row["values"]["peak_top_c"]})  # fmt: skip
    cpu = {"primary": [], "refine": []}
    for r in ledger.values():
        if r.get("children_cpu"):
            cpu["primary" if r["tag"] == "primary" else "refine"].append(
                menu._cpu_s(r["children_cpu"])
            )
    peaks = [
        int(r["cgroup_memory_peak_bytes"])
        for r in ledger.values()
        if r.get("cgroup_memory_peak_bytes")
    ]
    body = {
        "schema": pb.SCHEMA, "family": "f02", "scope": scope, "export_digest": export["export_digest"],
        "observer_versions": sorted(observers),
        "settings": {"coordinate_fields": ["peak_w", "on_time_s"], "lags": FIR_LAGS,
                     "reducers": [{"quantity": "peak_top_c", "unit": "C", "kind": "temperature_max"},
                                  {"quantity": "extra_energy_j", "unit": "J", "kind": "extra_energy_j"}]},
        "rows": rows,
        "costs": {"original_acquisition_cpu_s": sum(cpu["primary"]), "reference_refinement_cpu_s": sum(cpu["refine"]),
                  "retained_verification_cpu_s": None, "peak_process_ram_bytes": max(peaks) if peaks else None,
                  "money_eur": None},
    }  # fmt: skip
    materials = {**body, "materials_digest": tasks.digest(body)}
    chunks = [
        {"schema": WITNESS, "family": "f02", "export_digest": export["export_digest"], "chunk": i,
         "rows": witness[i * WITNESS_CHUNK_ROWS:(i + 1) * WITNESS_CHUNK_ROWS]}
        for i in range(-(-len(witness) // WITNESS_CHUNK_ROWS))
    ]  # fmt: skip
    return materials, chunks


def witness_manifest(export_digest, chunk_files):
    """Order and sha256 of each witness chunk file, for reassembly and verification."""
    return {"schema": WITNESS_MANIFEST, "family": "f02", "export_digest": export_digest,
            "chunks": [{"order": i, "name": Path(f).name, "sha256": _sha256_hex(Path(f).read_bytes())}
                       for i, f in enumerate(chunk_files)]}  # fmt: skip


# -- motor 10p/12s (the holding reference panel of panel_export.py) ---------------------


def _motor_candidate(candidate):
    design, span = candidate.split("-skew")
    return int(design[1:]), float(span)


def _motor_case_ids(i, span):
    """The solves behind one candidate's stacked observables, as stages.py reads them."""
    from scripts.dev.motor.feasibility02 import stages

    half = span / 2
    loaded = [
        stages.cid(i, 10, 0.0 - stages.PP * d, "s1" if d == 0 else "s2")
        for d in (-half, 0.0, half)
    ]
    refined = [
        stages.cid(i, 10, 0.0 - stages.PP * d, "s3r2") for d in (-half, 0.0, half)
    ]
    return (list(dict.fromkeys(loaded)), stages.cid(i, 0, 0),
            list(dict.fromkeys(refined)), stages.cid(i, 0, 0, "s3r2"))  # fmt: skip


def cost_ledger_motor(export, runs):
    """Motor solves run at a CPU cap of 2 with one GetDP thread; records hold wall time."""
    from scripts.dev.motor.feasibility02 import stages

    records = stages._records([runs])

    def solves_for(row):
        i, span = _motor_candidate(row["candidate"])
        loaded, cog, refined, cog_r2 = _motor_case_ids(i, span)
        out = []
        for rung, ids in (("standard", [*loaded, cog]), ("rung2", [*refined, cog_r2])):
            for case_id in ids:
                r = records.get(case_id)
                if r is not None and "wall_s" in r:
                    out.append({"source": f"records:{case_id}", "rung": rung, "status": r["status"],
                                "wall_s": float(r["wall_s"]), "core_s": None})  # fmt: skip
        return out

    return _ledger(
        export,
        solves_for,
        "motor: one GetDP case per container at CPU cap 2 (single-threaded); wall_s "
        "from each record, core_s not measured per solve",
    )


def motor_curve_set(export, runs, plan):
    """The comparator's curve set: each candidate's stacked loaded and cogging curves
    on the observer's own grid, with its physical geometry and skew."""
    from carbon.development_comparison import cheap_baselines as cb
    from scripts.dev.motor.feasibility02 import stages
    from scripts.dev.motor.feasibility02 import topology as tp

    records = stages._records([runs])
    designs = json.loads(Path(plan).read_text())["designs"]
    observers = {e["task"]["identity"]["observer_version"] for e in export["questions"]}
    rows = []
    for row in _rows(export):
        i, span = _motor_candidate(row["candidate"])
        _, cog_id, _, _ = _motor_case_ids(i, span)
        half = span / 2
        slices = []
        for d in (-half, 0.0, half):
            case_id = stages.cid(i, 10, 0.0 - stages.PP * d, "s1" if d == 0 else "s2")
            slices.append(
                tp.slice_curve(
                    records[case_id]["outputs"]["torque_nm"], round(d / stages.STEP_DEG)
                )
            )
        loaded = tp.stack_curve(slices)
        curve = records[cog_id]["outputs"]["torque_nm"]
        off = round(half / stages.STEP_DEG)
        cogging = tp.stack_curve([tp.slice_curve(curve, o) for o in (-off, 0, off)])
        reduced = cb.curve_observables(loaded, cogging)
        if any(
            not math.isclose(reduced[q], row["values"][q], rel_tol=1e-12, abs_tol=1e-12)
            for q in reduced
        ):
            raise ValueError(
                f"{row['candidate']}: curves do not reproduce the export's observables"
            )
        rows.append({"candidate": row["candidate"], "geometry_id": f"d{i:02d}",
                     "coordinates": {**{k: designs[i][k] for k in cb.MOTOR_FEATURES if k != "skew_deg"},
                                     "skew_deg": span},
                     "loaded_nm": loaded, "cogging_nm": cogging})  # fmt: skip
    source = Path(runs) / "records.jsonl"
    return {"export_digest": export["export_digest"], "sampling": "one-period-without-repeated-endpoint",
            "source_hashes": [_sha256_hex(source.read_bytes()), _sha256_hex(Path(plan).read_bytes())],
            "observer_version": observers.pop() if len(observers) == 1 else sorted(observers),
            "angle_deg": [k * stages.STEP_DEG for k in range(len(rows[0]["loaded_nm"]))], "rows": rows}  # fmt: skip


def motor_geometry(plan):
    """The kit's material: the panel designs' grammar only, never a curve."""
    from carbon.development_comparison import motor_10p12s_kit as mk

    designs = json.loads(Path(plan).read_text())["designs"]
    return {"schema": mk.SIDECAR_SCHEMA,
            "designs": {f"{mk.PANEL_TAG}{i:02d}": {"tags": [f"{mk.PANEL_TAG}{i:02d}"],
                                                    "grammar": {k: d[k] for k in mk.GRAMMAR}}
                        for i, d in enumerate(designs)}}  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
