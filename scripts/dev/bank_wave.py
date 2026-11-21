"""Motor Specialist Bank, PATH B: run a staged WAVE of retrains, then aggregate it per regime stratum.

Owner B5 (custody2 / custody3, run by custody-ops on V2's receipt of each run line, idle behind exam jobs, no spend)
and BANK-K (wave A = K 3 in the 5 largest S-PUB strata, then wave B). The wave folder is staged by
codex-queue/reports/BANK/bank_waveA_pick_ro.py: ``rNN/{recipe.json, envelope.json, arms.txt, stratum.txt[,
expect.txt]}``. Both subcommands run INSIDE the build's pinned worker image on the custody host, never on GPUYard.

``run``: for every rNN, the original recipe at seed 0 (the official build seed; ``--expect`` only when expect.txt
exists = a CPU-built task), then every arm in arms.txt at every ``--seeds`` bank seed, one at a time, through
``bank_retrain.retrain`` (which holds the seed and arm rules). Resumable: a finished report is never re-run. Polite:
before each retrain it waits while the host's load1 is above ``--load-max`` and stops cleanly if ``<out>/STOP``
exists. A retrain that raises is recorded as ``ERROR`` with the exception's class name only (never a traceback) and
the wave goes on: it is Carbon's failure, never the recipe's.

``aggregate``: per (stratum, arm) it compares each arm with the SAME recipe's original at the SAME seed and reports
only aggregates over at least ``--min-recipes`` distinct recipes (V2: >= 3 before anything leaves custody): recipe
and run counts, admitted share, the change in kit verify designs within U (median, improved / same / worse counts),
the train-loss ratio median; plus seed spread of the originals and the seed-0 reproduction counts per stratum, and
the wave's cost. Cells under the minimum are counted as suppressed and say nothing else. Labels: public signals
only, S-PUB (no hidden-derived selection; recipes were shaped on official feedback), observed, never causal.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

SCHEMA = "carbon.bank-wave.v0"
CAVEAT = (
    "public signals only; S-PUB: no hidden-derived selection, recipes shaped on official feedback;"
    " observed, not causal; no accuracy claim before a fresh holdout"
)


def _load1():
    try:
        return float(Path("/proc/loadavg").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0


def report_name(folder, arm, seed):
    return "{}__{}__{}.json".format(
        folder, arm.replace(":", "-").replace("/", "-"), seed
    )


def jobs(wave, seeds):
    """[(folder, arm, seed, expect)] in run order."""
    out = []
    for folder in sorted(
        p for p in Path(wave).iterdir() if p.is_dir() and p.name.startswith("r")
    ):
        expect = folder / "expect.txt"
        out.append(
            (
                folder,
                "original",
                0,
                expect.read_text().strip() if expect.is_file() else None,
            )
        )
        arms = [
            a.strip()
            for a in (folder / "arms.txt").read_text().splitlines()
            if a.strip()
        ]
        for arm in arms:
            for seed in seeds:
                out.append((folder, arm, seed, None))
    return out


def run(
    wave,
    out,
    verify,
    verify_sha256,
    seeds,
    *,
    load_max,
    pause_s,
    retrain=None,
    load1=_load1,
    sleep=time.sleep,
):
    import bank_retrain

    retrain = bank_retrain.retrain if retrain is None else retrain
    from carbon.level4 import staging

    out = Path(out)
    verify_bytes = Path(verify).read_bytes()
    done = skipped = 0
    graphs = {}
    for folder, arm, seed, expect in jobs(wave, seeds):
        target = out / report_name(folder.name, arm, seed)
        if target.exists():
            skipped += 1
            continue
        if (out / "STOP").exists():
            print(json.dumps({"stopped": True, "done": done, "skipped": skipped}))
            return 3
        while load1() > load_max:
            if (out / "STOP").exists():
                print(json.dumps({"stopped": True, "done": done, "skipped": skipped}))
                return 3
            sleep(pause_s)
        if folder.name not in graphs:
            envelope = json.loads(
                (folder / "envelope.json").read_text(encoding="utf-8")
            )
            _digest, raw_manifest, files = staging.from_envelope(envelope)
            graphs[folder.name] = (raw_manifest, files)
        raw_manifest, files = graphs[folder.name]
        recipe = json.loads((folder / "recipe.json").read_text(encoding="utf-8"))
        started = time.perf_counter()
        try:
            report = retrain(
                recipe,
                raw_manifest,
                files,
                verify_bytes,
                verify_sha256,
                seed=seed,
                arm=arm,
                expect_state_digest=expect,
            )
        except bank_retrain.BankRefused as refused:
            report = {
                "arm": arm,
                "seed": seed,
                "admission": {"state": "REFUSED", "code": refused.code},
            }
        except Exception as error:  # Carbon's failure, recorded by its class name only
            report = {
                "arm": arm,
                "seed": seed,
                "admission": {"state": "ERROR", "code": type(error).__name__},
            }
        report.setdefault("wall_s", time.perf_counter() - started)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(
            json.dumps(report, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
        )
        os.replace(tmp, target)
        done += 1
        print(json.dumps({"job": target.name, "state": report["admission"]["state"]}))
    print(json.dumps({"finished": True, "done": done, "skipped": skipped}))
    return 0


def _metrics(report):
    if report.get("admission", {}).get("state") != "ADMITTED":
        return None
    within = ((report.get("verify") or {}).get("aggregate") or {}).get(
        "accuracy_vs_u"
    ) or {}
    fit = report.get("fit") or {}
    return {
        "within": within.get("n_within_u")
        if isinstance(within.get("n_within_u"), int)
        else None,
        "loss": fit.get("train_loss")
        if isinstance(fit.get("train_loss"), (int, float))
        else None,
    }


def aggregate(wave, out, *, min_recipes=3):
    wave, out = Path(wave), Path(out)
    stratum = {
        p.name: (p / "stratum.txt").read_text().strip()
        for p in wave.iterdir()
        if p.is_dir() and (p / "stratum.txt").is_file()
    }
    reports = {}
    for path in out.glob("r*__*__*.json"):
        folder, named, seed = path.stem.split("__")
        report = json.loads(path.read_text(encoding="utf-8"))
        # the file name carries a path-safe arm; the report carries the arm itself
        reports[(folder, report.get("arm") or named, int(seed))] = report
    cells = defaultdict(list)
    spreads = defaultdict(list)
    repro = defaultdict(lambda: {"equal": 0, "differs": 0, "no_expect": 0})
    walls = []
    for (folder, arm, seed), report in reports.items():
        walls.append(report.get("wall_s") or 0.0)
        s = stratum.get(folder, "unknown")
        if arm == "original":
            if seed == 0:
                r = report.get("reproduced")
                repro[s][
                    "no_expect" if r is None else ("equal" if r else "differs")
                ] += 1
            continue
        base = reports.get((folder, "original", seed))
        cells[(s, arm)].append(
            (folder, _metrics(report), None if base is None else _metrics(base))
        )
    by_folder_seed = defaultdict(dict)
    for (folder, arm, seed), report in reports.items():
        if arm == "original" and seed != 0:
            m = _metrics(report)
            if m and m["loss"] is not None:
                by_folder_seed[folder][seed] = m["loss"]
    for folder, losses in by_folder_seed.items():
        if len(losses) >= 2:
            values = list(losses.values())
            spreads[stratum.get(folder, "unknown")].append(
                (folder, max(values) - min(values))
            )
    result = {
        "schema": SCHEMA,
        "caveat": CAVEAT,
        "min_recipes": min_recipes,
        "cells": {},
        "suppressed": 0,
    }
    for (s, arm), rows in sorted(cells.items()):
        recipes = {f for f, _m, _b in rows}
        if len(recipes) < min_recipes:
            result["suppressed"] += 1
            continue
        admitted = [r for r in rows if r[1] is not None]
        deltas = [
            m["within"] - b["within"]
            for _f, m, b in admitted
            if b and m["within"] is not None and b["within"] is not None
        ]
        ratios = [
            m["loss"] / b["loss"]
            for _f, m, b in admitted
            if b and m["loss"] is not None and b["loss"] not in (None, 0)
        ]
        result["cells"][s + " || " + arm] = {
            "recipes": len(recipes),
            "runs": len(rows),
            "admitted_share": round(len(admitted) / len(rows), 3),
            "within_u_delta_median": statistics.median(deltas) if deltas else None,
            "within_u_improved": sum(d > 0 for d in deltas),
            "within_u_same": sum(d == 0 for d in deltas),
            "within_u_worse": sum(d < 0 for d in deltas),
            "train_loss_ratio_median": round(statistics.median(ratios), 6)
            if ratios
            else None,
        }
    result["seed_spread_train_loss_median"] = {
        s: statistics.median(v for _f, v in rows)
        for s, rows in sorted(spreads.items())
        if len({f for f, _v in rows}) >= min_recipes
    }
    result["seed0_reproduction"] = {
        s: c for s, c in sorted(repro.items()) if sum(c.values()) >= min_recipes
    }
    result["cost"] = {
        "runs": len(reports),
        "wall_s_total": round(sum(walls), 1),
        "wall_s_median": round(statistics.median(walls), 1) if walls else None,
    }
    target = out / "aggregate.json"
    target.write_text(
        json.dumps(result, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--wave", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--verify", required=True)
    r.add_argument("--verify-sha256", required=True)
    r.add_argument("--seeds", required=True, help="comma-separated bank seeds")
    r.add_argument("--load-max", type=float, required=True)
    r.add_argument("--pause-s", type=float, default=60.0)
    a = sub.add_parser("aggregate")
    a.add_argument("--wave", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--min-recipes", type=int, default=3)
    args = parser.parse_args(argv)
    if args.command == "run":
        import bank_retrain

        try:
            seeds = [
                bank_retrain.check_seed(int(s))
                for s in args.seeds.split(",")
                if s.strip()
            ]
        except (bank_retrain.BankRefused, ValueError):
            seeds = []
        # seed 0 runs only as each recipe's original check, never as a wave seed
        if not seeds or 0 in seeds:
            print(json.dumps({"refused": "seeds_not_bank"}))
            return 2
        return run(
            args.wave,
            args.out,
            args.verify,
            args.verify_sha256,
            seeds,
            load_max=args.load_max,
            pause_s=args.pause_s,
        )
    if args.min_recipes < 3:
        print(json.dumps({"refused": "min_recipes_below_v2_rule"}))
        return 2
    print(
        json.dumps(
            aggregate(args.wave, args.out, min_recipes=args.min_recipes), sort_keys=True
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
