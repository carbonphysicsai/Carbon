"""SUBMISSION-RATE-STUDY-01 analysis (run sheet A.3): the registered measures.

    python scripts/dev/rate_study/analyze.py stage0 --records DIR --out DIR
    python scripts/dev/rate_study/analyze.py report --records DIR --out FILE

It reads the operator-side per-submission records (run sheet A.2) and nothing
else. It never sees a case, seed, fingerprint or prediction: a record carrying
any field outside `FIELDS` is refused. It chooses no value:
- the interval settings are battery's registered comparison settings
  (`carbon.battery.exam.DEVELOPMENT_RULE["comparison"]`: `n_boot`, `alpha`);
- "within noise" is arm H's bootstrap band, nothing else;
- the bootstrap seed is a public string, derived from nothing hidden.

Definitions (plan sections 3 and 7, measures-v1.json):
- `D = s_fresh - s_current` for a lower-is-better score: positive means the
  model does better on the batch it was scored on than on a fresh set.
- `D_at_P` of a run is D of its last scored submission whose `probes_case_max`
  is at most P (no averaging, no extra parameter).
- Only `state == "SCORED"` submissions are observations. Every other state
  (`UNAVAILABLE`, `WINDOW_USED`, `REPEATED`, `NOT_SCORED`) is counted and excluded; it is
  never drift.

Provenance. A record is `STUDY` (a real run) or `FIXTURE` (synthetic, used only
by tests and dry runs). A FIXTURE report is stamped as such and `stage0`
refuses to write it into the committed evidence tree, so a fixture can never
become Stage 0 evidence or enter a freeze.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))

import numpy as np

from carbon.battery import exam

EVIDENCE = REPOSITORY / "docs/development/evidence/submission-rate-study-01"
SETTINGS = exam.DEVELOPMENT_RULE["comparison"]
N_BOOT = SETTINGS["n_boot"]
ALPHA = SETTINGS["alpha"]
SEED_NAMESPACE = "SUBMISSION-RATE-STUDY-01/bootstrap/"
ARMS = ("H", "S-sealed", "S-revealed", "G-sealed")
#: The arms whose rate decides the safe rate; S-revealed is the reported bound.
REALISTIC_ARMS = ("S-sealed", "G-sealed")
#: `NOT_SCORED`: the route had a candidate failure, a scored submission had no
#: aggregate score, or the fresh-set scoring had a candidate failure. Excluded and
#: counted like the other non-scored states; never a drift observation.
STATES = ("SCORED", "UNAVAILABLE", "WINDOW_USED", "REPEATED", "NOT_SCORED")
PROVENANCES = ("STUDY", "FIXTURE")
FIELDS = (
    "arm",
    "rate",
    "replicate",
    "window",
    "t",
    "probes_batch",
    "probes_case_max",
    "d_index",
    "s_current",
    "s_fresh",
    "state",
    "wall_s",
    "provenance",
)
#: Pricing terms that are facts of battery's bank rule, not choices.
WINDOW_CASES = exam.DEVELOPMENT_RULE_V2_BANK["bank"]["pool"]["window_cases"]
ROTATION_BLOCKS = exam.DEVELOPMENT_RULE_V2["rotation"]["every_blocks"]
BLOCK_SECONDS = 12


class RecordRefused(ValueError):
    """A record the analysis will not read; `args[0]` says why."""


def rng(tag):
    digest = hashlib.sha256((SEED_NAMESPACE + tag).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


# -- reading ------------------------------------------------------------------------------------
def check_record(record):
    if not isinstance(record, dict):
        raise RecordRefused("record_not_an_object")
    extra = sorted(set(record) - set(FIELDS))
    missing = sorted(set(FIELDS) - set(record))
    if extra:
        raise RecordRefused("record_has_fields_outside_the_schema: " + ",".join(extra))
    if missing:
        raise RecordRefused("record_missing_fields: " + ",".join(missing))
    if record["arm"] not in ARMS:
        raise RecordRefused("unknown_arm")
    if record["state"] not in STATES:
        raise RecordRefused("unknown_state")
    if record["provenance"] not in PROVENANCES:
        raise RecordRefused("unknown_provenance")
    if record["rate"] not in (1, 2, 4):
        raise RecordRefused("unknown_rate")
    if record["state"] == "SCORED":
        for key in ("d_index", "s_current", "s_fresh", "wall_s"):
            value = record[key]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise RecordRefused(f"scored_record_{key}_not_finite")
        if abs((record["s_fresh"] - record["s_current"]) - record["d_index"]) > 1e-9:
            raise RecordRefused("d_index_is_not_s_fresh_minus_s_current")
    return record


def load_records(directory):
    """Every record under `directory` (`*.jsonl`, recursively), validated."""
    records = []
    for path in sorted(Path(directory).rglob("*.jsonl")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                records.append(check_record(json.loads(line)))
            except (ValueError, RecordRefused) as error:
                raise RecordRefused(f"{path.name}:{number}: {error}") from None
    if not records:
        raise RecordRefused("no_records")
    return records


def provenance_of(records):
    kinds = {r["provenance"] for r in records}
    if len(kinds) != 1:
        raise RecordRefused("mixed_provenance")
    return kinds.pop()


def runs_of(records, arm, rate):
    """`{replicate: [scored records in order]}` for one arm and rate."""
    runs = {}
    for r in records:
        if r["arm"] == arm and r["rate"] == rate and r["state"] == "SCORED":
            runs.setdefault(r["replicate"], []).append(r)
    return {k: sorted(v, key=lambda r: r["t"]) for k, v in sorted(runs.items())}


def excluded_counts(records):
    counts = {state: 0 for state in STATES if state != "SCORED"}
    for r in records:
        if r["state"] != "SCORED":
            counts[r["state"]] += 1
    return counts


# -- the measures -------------------------------------------------------------------------------
def d_at_probes(run, probes):
    """D of the run's last scored submission with `probes_case_max <= probes`,
    or None if it has none yet."""
    best = None
    for r in run:
        if r["probes_case_max"] <= probes:
            best = r["d_index"]
    return best


def final_probes(runs_by_group):
    """The largest probe count every run reached: the matched final P."""
    reached = [
        max(r["probes_case_max"] for r in run)
        for runs in runs_by_group
        for run in runs.values()
        if run
    ]
    return min(reached) if reached else None


def slope(run):
    """OLS slope of D on `probes_case_max` for one run; None when it has fewer
    than two distinct probe counts."""
    xs = [r["probes_case_max"] for r in run]
    ys = [r["d_index"] for r in run]
    if len(set(xs)) < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def bootstrap_mean(values, tag):
    """Mean and the percentile bootstrap interval over runs (`N_BOOT`, `ALPHA`)."""
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return {"n": 0, "mean": None, "lower": None, "upper": None}
    generator = rng(tag)
    index = generator.integers(0, values.size, size=(N_BOOT, values.size))
    means = values[index].mean(axis=1)
    lower, upper = np.quantile(means, [ALPHA / 2, 1 - ALPHA / 2])
    return {
        "n": int(values.size),
        "mean": float(values.mean()),
        "lower": float(lower),
        "upper": float(upper),
    }


def bootstrap_difference(a, b, tag):
    """The percentile interval of mean(a) - mean(b), resampling each over runs."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        return None
    generator = rng(tag)
    ma = a[generator.integers(0, a.size, size=(N_BOOT, a.size))].mean(axis=1)
    mb = b[generator.integers(0, b.size, size=(N_BOOT, b.size))].mean(axis=1)
    lower, upper = np.quantile(ma - mb, [ALPHA / 2, 1 - ALPHA / 2])
    return {"lower": float(lower), "upper": float(upper)}


def run_values_at(runs, probes):
    return [
        v for v in (d_at_probes(run, probes) for run in runs.values()) if v is not None
    ]


_NOISE_CACHE = {}


def noise_band(records, probes):
    key = (id(records), len(records), probes)
    if key not in _NOISE_CACHE:
        _NOISE_CACHE[key] = _noise_band(records, probes)
    return _NOISE_CACHE[key]


def window_end_grid(records, upto):
    """The probe counts the scans consider: each run's probe count at the end of
    every window (the last scored submission of the window), up to `upto`. A
    coarse, structural grid: no value is chosen."""
    ends = set()
    last = {}
    for r in records:
        if r["state"] != "SCORED":
            continue
        key = (r["arm"], r["rate"], r["replicate"], r["window"])
        if key not in last or r["t"] > last[key][0]:
            last[key] = (r["t"], r["probes_case_max"])
    ends = {p for _, p in last.values() if p <= upto}
    return sorted(ends)


def _noise_band(records, probes):
    """Arm H's band at matched probe count `probes`: per rate, pooled, and whether
    arm H shows a rate effect (any pair of rates whose difference interval
    excludes 0). The band used is pooled when there is no rate effect, else the
    per-rate values (`honest_values`)."""
    per_rate, values = {}, {}
    for rate in (1, 2, 4):
        runs = runs_of(records, "H", rate)
        values[rate] = run_values_at(runs, probes)
        per_rate[rate] = bootstrap_mean(values[rate], f"H/{rate}/{probes}")
    pooled_values = [v for rate in values for v in values[rate]]
    pooled = bootstrap_mean(pooled_values, f"H/pooled/{probes}")
    effects = {}
    for i, a in enumerate((1, 2, 4)):
        for b in (1, 2, 4)[i + 1 :]:
            interval = bootstrap_difference(
                values[a], values[b], f"H/diff/{a}-{b}/{probes}"
            )
            effects[f"{a}-{b}"] = {
                "interval": interval,
                "excludes_zero": bool(
                    interval and (interval["lower"] > 0 or interval["upper"] < 0)
                ),
            }
    effect = any(e["excludes_zero"] for e in effects.values())
    return {
        "probes": probes,
        "per_rate": per_rate,
        "pooled": pooled,
        "values": {"per_rate": values, "pooled": pooled_values},
        "rate_effect": effect,
        "pairwise": effects,
    }


def honest_values(noise, rate):
    """The honest D values at the matched probe count that apply at `rate`:
    pooled over rates when arm H shows no rate effect, else that rate's own."""
    values = noise["values"]
    return values["per_rate"][rate] if noise["rate_effect"] else values["pooled"]


def arm_at(records, arm, rate, probes):
    return bootstrap_mean(
        run_values_at(runs_of(records, arm, rate), probes), f"{arm}/{rate}/{probes}"
    )


def distinguishable(records, arm, rate, probes, noise):
    """Whether `arm` at `rate` is distinguishable from arm H's noise at matched probe
    count `probes`: the percentile bootstrap interval (battery's registered `n_boot`
    and `alpha`) of `mean(arm D) - mean(honest D)` has its lower bound above 0. The
    honest replicates are the noise estimate; the arm's own replicate noise is in the
    same interval. With no observations in either, the arm is NOT within noise
    (returns True): absence never reads as safe.

    History: the first rule compared the arm's interval upper bound with the honest
    interval upper bound, which the fixture dry run showed flags about half of null
    arms (two equally noisy intervals cross by chance); comparing the arm's mean with
    the honest band flagged about 40 percent (it ignores the arm's own sampling error).
    The difference interval is the two-sample form of the same registered settings."""
    arm_values = run_values_at(runs_of(records, arm, rate), probes)
    base = honest_values(noise, rate)
    if not arm_values or not base:
        return True
    diff = bootstrap_difference(arm_values, base, f"diff/{arm}/{rate}/{probes}")
    return diff["lower"] > 0


def drift_slopes(records, arm, rate):
    slopes = [
        s
        for s in (slope(run) for run in runs_of(records, arm, rate).values())
        if s is not None
    ]
    return bootstrap_mean(slopes, f"slope/{arm}/{rate}")


def sealed_vs_revealed(records, probes):
    """Revealed over sealed drift at equal rate: ratio of mean D at the matched P
    and of mean slopes; None where the sealed value is 0 or missing."""
    out = {}
    for rate in (1, 2, 4):
        sealed = arm_at(records, "S-sealed", rate, probes)["mean"]
        revealed = arm_at(records, "S-revealed", rate, probes)["mean"]
        s_slope = drift_slopes(records, "S-sealed", rate)["mean"]
        r_slope = drift_slopes(records, "S-revealed", rate)["mean"]
        out[rate] = {
            "d_ratio": _ratio(revealed, sealed),
            "slope_ratio": _ratio(r_slope, s_slope),
        }
    return out


def _ratio(num, den):
    if num is None or den is None or den == 0:
        return None
    return num / den


def safe_rate(records, probes, noise):
    """The largest tested rate at which every realistic arm present is not
    distinguishable from arm H at the matched final probe count, with the per-arm
    detail. None means even m = 1 is distinguishable for some realistic arm, or no
    realistic arm ran."""
    arms = [a for a in REALISTIC_ARMS if any(r["arm"] == a for r in records)]
    detail = {
        rate: {
            arm: {
                "interval": arm_at(records, arm, rate, probes),
                "within_noise": not distinguishable(records, arm, rate, probes, noise),
            }
            for arm in arms
        }
        for rate in (1, 2, 4)
    }
    safe = None
    for rate in (1, 2, 4):
        if arms and all(v["within_noise"] for v in detail[rate].values()):
            safe = rate
        else:
            break
    return {"arms": arms, "safe_rate": safe, "detail": detail}


def first_distinguishable(records, rate, arms, grid):
    """The smallest probe count in `grid` at which some realistic arm is
    distinguishable from arm H at `rate`, or None. The noise is recomputed at each
    probe count."""
    for probes in sorted(grid):
        noise = noise_band(records, probes)
        if any(distinguishable(records, arm, rate, probes, noise) for arm in arms):
            return probes
    return None


def largest_probes_within_noise(records, grid, arms):
    """P*: the largest probe count in `grid` at which no realistic arm is
    distinguishable at any rate it ran; None if there is none."""
    best = None
    for probes in sorted(grid):
        noise = noise_band(records, probes)
        if not any(
            distinguishable(records, arm, rate, probes, noise)
            for arm in arms
            for rate in (1, 2, 4)
            if runs_of(records, arm, rate)
        ):
            best = probes
    return best


def bank_table(
    p_star, rates, hotkeys, per_solve_cpu_s, bank_size, window_cases=WINDOW_CASES
):
    """For each (m, H): the largest E with E <= P* / (3 m H) (at least 1 would be
    needed to run at all), the new reference solves per window `n / E`, per day,
    and the CPU-hours per day at the measured per-solve cost."""
    windows_per_day = 86400 / (ROTATION_BLOCKS * BLOCK_SECONDS)
    rows = []
    for m in rates:
        for h in hotkeys:
            e_max = math.floor(p_star / (3 * m * h)) if p_star is not None else None
            if not e_max:
                rows.append({"m": m, "H": h, "E": e_max, "feasible": False})
                continue
            per_window = math.ceil(window_cases / e_max)
            per_day = windows_per_day * window_cases / e_max
            rows.append(
                {
                    "m": m,
                    "H": h,
                    "E": e_max,
                    "feasible": True,
                    "solves_per_window": per_window,
                    "solves_per_day": per_day,
                    "cpu_hours_per_day": per_day * per_solve_cpu_s / 3600,
                    "bank_fill_cases": bank_size,
                }
            )
    return {"p_star": p_star, "windows_per_day": windows_per_day, "rows": rows}


def throughput(records):
    out = {}
    for rate in (1, 2, 4):
        walls = sorted(
            r["wall_s"] for r in records if r["rate"] == rate and r["state"] == "SCORED"
        )
        if not walls:
            continue
        p95 = walls[min(len(walls) - 1, math.ceil(0.95 * len(walls)) - 1)]
        out[rate] = {
            "scored": len(walls),
            "wall_s_median": statistics.median(walls),
            "wall_s_p95": p95,
            "excluded": excluded_counts([r for r in records if r["rate"] == rate]),
        }
    return out


def selection_check(records, probes):
    """Arm H's best-of-sequence D (the maximum D any H run reaches by `probes`)."""
    best = {}
    for rate in (1, 2, 4):
        values = [
            max(
                (r["d_index"] for r in run if r["probes_case_max"] <= probes),
                default=None,
            )
            for run in runs_of(records, "H", rate).values()
        ]
        values = [v for v in values if v is not None]
        best[rate] = {
            "runs": len(values),
            "max_of_max": max(values) if values else None,
        }
    return best


# -- the reports --------------------------------------------------------------------------------
def _public_noise(noise):
    """The noise record as written: bands and tests; the per-run values stay in
    the operator's records."""
    return {k: v for k, v in noise.items() if k != "values"}


def stage0_report(records):
    """Arm H only: the noise estimate, throughput and replicate counts."""
    if any(r["arm"] != "H" for r in records):
        raise RecordRefused("stage0_is_arm_h_only")
    _NOISE_CACHE.clear()
    provenance = provenance_of(records)
    groups = [runs_of(records, "H", rate) for rate in (1, 2, 4)]
    probes = final_probes(groups)
    if probes is None:
        raise RecordRefused("no_scored_runs")
    return {
        "schema": "carbon.submission-rate-study.stage0.v1",
        "provenance": provenance,
        "settings": {
            "n_boot": N_BOOT,
            "alpha": ALPHA,
            "source": "carbon.battery.exam.DEVELOPMENT_RULE comparison",
        },
        "final_probes": probes,
        "replicates": {str(rate): len(groups[i]) for i, rate in enumerate((1, 2, 4))},
        "noise": _public_noise(noise_band(records, probes)),
        "throughput": throughput(records),
        "selection_check": selection_check(records, probes),
        "claims": {
            "qualification": False,
            "live": False,
            "reward": False,
            "production_rate": False,
        },
    }


def study_report(records, per_solve_cpu_s, hotkeys=(1, 2, 4, 8), bank_size=3000):
    """The Stage 1 report: drift vs rate, sealed vs revealed, the safe rate, P*
    and the bank/E table."""
    _NOISE_CACHE.clear()
    provenance = provenance_of(records)
    groups = [
        runs_of(records, arm, rate)
        for arm in ARMS
        for rate in (1, 2, 4)
        if runs_of(records, arm, rate)
    ]
    probes = final_probes(groups)
    if probes is None:
        raise RecordRefused("no_scored_runs")
    noise = noise_band(records, probes)
    result = safe_rate(records, probes, noise)
    grid = window_end_grid(records, probes)
    p_star = largest_probes_within_noise(records, grid, result["arms"])
    next_rate = {None: 1, 1: 2, 2: 4}.get(result["safe_rate"])
    return {
        "schema": "carbon.submission-rate-study.report.v1",
        "provenance": provenance,
        "settings": {"n_boot": N_BOOT, "alpha": ALPHA},
        "final_probes": probes,
        "noise": _public_noise(noise),
        "drift_slopes": {
            arm: {str(rate): drift_slopes(records, arm, rate) for rate in (1, 2, 4)}
            for arm in ARMS
            if any(r["arm"] == arm for r in records)
        },
        "sealed_vs_revealed": {
            str(k): v for k, v in sealed_vs_revealed(records, probes).items()
        },
        "safe_rate": result["safe_rate"],
        "safe_rate_detail": {str(k): v for k, v in result["detail"].items()},
        "first_distinguishable_probes_at_next_rate": (
            first_distinguishable(records, next_rate, result["arms"], grid)
            if next_rate and result["arms"]
            else None
        ),
        "p_star": p_star,
        "bank_table": bank_table(
            p_star, (1, 2, 4), hotkeys, per_solve_cpu_s, bank_size
        ),
        "throughput": throughput(records),
        "claims": {
            "qualification": False,
            "live": False,
            "reward": False,
            "production_rate": False,
        },
    }


def write_json(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def is_evidence_path(path):
    try:
        Path(path).resolve().relative_to(EVIDENCE.resolve())
    except ValueError:
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(prog="analyze")
    sub = parser.add_subparsers(dest="command", required=True)
    s0 = sub.add_parser("stage0")
    s0.add_argument("--records", required=True)
    s0.add_argument("--out", required=True)
    rp = sub.add_parser("report")
    rp.add_argument("--records", required=True)
    rp.add_argument("--out", required=True)
    rp.add_argument("--per-solve-cpu-s", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        records = load_records(args.records)
        if args.command == "stage0":
            report = stage0_report(records)
        else:
            report = study_report(records, args.per_solve_cpu_s)
    except RecordRefused as refused:
        print(f"refused: {refused}")
        return 2
    if report["provenance"] == "FIXTURE" and is_evidence_path(args.out):
        print(
            "refused: a FIXTURE report is never written into the committed evidence tree"
        )
        return 2
    out = Path(args.out)
    if args.command == "stage0":
        write_json(
            out / "noise.json",
            {
                k: report[k]
                for k in (
                    "schema",
                    "provenance",
                    "settings",
                    "final_probes",
                    "replicates",
                    "noise",
                    "selection_check",
                )
            },
        )
        write_json(out / "throughput.json", report["throughput"])
    else:
        write_json(out, report)
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
