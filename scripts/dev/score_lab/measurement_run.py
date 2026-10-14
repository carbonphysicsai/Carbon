"""Bounded local driver for the prospective, finite-population toy study."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import signal
import statistics
import subprocess
import time
from pathlib import Path

from . import campaign_gate, candidates, core
from . import campaign_measurement as study

CANDIDATE_IDS = (
    "INFORCE-G-FEAS/A-Q>@0.05",
    "V9-ENV/ARP-V3",
    "V10-SIGN+ENV/ARP-V3S",
    "V2r2@k1,kappa0.05",
    "V2r2@k3,kappa0.1",
    "V2r2@k5,kappa0.25",
    "N1-DECISION-RELEVANCE-ERROR",
    "N2-VERIFIED-REGRET-ON-PICK",
    "N3-SAFE-PICK-RATE-x-GAIN",
    "N4-TOP-REGION-RANKING",
)
SOURCE_PATHS = tuple(
    f"scripts/dev/score_lab/{name}.py"
    for name in (
        "measurement_run",
        "campaign_measurement",
        "campaign_gate",
        "campaign_blocks",
        "campaign_reference",
        "campaign_goodhart",
        "candidates",
        "components",
        "core",
        "physics",
        "synthetic",
    )
) + (
    "uv.lock",
    "pyproject.toml",
    "carbon/battery/value/score_proof.py",
    "carbon/battery/value/score_tuning.py",
    "scripts/dev/score_lab/physics-error-example.json",
    "scripts/dev/score_lab/campaign-gate-toy.json",
    "Business/research/value-metric-audit/results.json",
    "Business/research/value-metric-v2-stress/results.json",
)


def normalized_sha(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def register(root, candidate_path):
    """No candidate import or evaluation; commit this document before run."""
    return {
        "schema": study.SCHEMA,
        "scope": study.SCOPE,
        "label": "ASSUMPTION: finite toy population, not a Challenge power or sample-size claim",
        "config": json.loads(
            (root / "scripts/dev/score_lab/physics-error-example.json").read_text(
                encoding="utf-8"
            )
        ),
        "cells": study.cells(),
        "bootstrap": 60,
        "candidate_sha256": study.file_sha(candidate_path),
        "candidate_ids": list(CANDIDATE_IDS),
        "sources": {p: normalized_sha(root / p) for p in SOURCE_PATHS},
        "caps": {
            "cpu_seconds": 1800,
            "wall_seconds": 1900,
            "address_space_bytes": 2147483648,
            "complete_cell_reservation_cpu_seconds": 60,
        },
        "controls": {
            "audit_path": "Business/research/value-metric-audit/results.json",
            "stress_path": "Business/research/value-metric-v2-stress/results.json",
            "problem": json.loads(
                (root / "scripts/dev/score_lab/campaign-gate-toy.json").read_text(
                    encoding="utf-8"
                )
            ),
            "questions_per_side": 6,
            "cap": 3,
        },
        "selection": None,
        "limits": [
            "Scores and the six model traits stay fixed; seeds vary draws, not models.",
            "Cheap map acquisition cost and physical traits are unmeasured; physics OFF.",
            "Crossed recipe bootstrap is exploratory with six illustrative model traits.",
            "Three sampling seeds cannot establish frequentist coverage or real power.",
            "With exclusions, the estimand is conditional on retained draws.",
            "No holdout, model training, solver or host-side execution.",
        ],
    }


def verify(root, plan, candidate_path):
    expected = register(root, candidate_path)
    if plan != expected:
        raise core.LabRefused("measurement_registration_or_source_changed")
    if (
        Path(__file__).resolve()
        != (root / "scripts/dev/score_lab/measurement_run.py").resolve()
    ):
        raise core.LabRefused("measurement_imported_source_mismatch")


def _stop(signum, frame):
    raise TimeoutError("measurement_resource_limit")


def run(root, plan_path, candidate_path, output):
    """Fresh directory, committed plan, identity first, checkpoints after cells."""
    import resource

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    verify(root, plan, candidate_path)
    relative = plan_path.resolve().relative_to(root.resolve()).as_posix()
    committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=root)
    if json.loads(committed) != plan:
        raise core.LabRefused("measurement_plan_not_committed")
    output.mkdir(parents=True, exist_ok=False)
    start_cpu, start_wall = time.process_time(), time.monotonic()
    identity = {
        "schema": study.SCHEMA,
        "scope": study.SCOPE,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "plan_sha256": core.canonical_sha(plan),
        "candidate_sha256": plan["candidate_sha256"],
        "sources": plan["sources"],
        "execution": "actual local synthetic evaluator, no worker substitution",
    }
    study.write(output / "START.json", identity)
    study.write(output / "REGISTERED_PLAN.json", plan)
    caps = plan["caps"]
    resource.setrlimit(
        resource.RLIMIT_AS, (caps["address_space_bytes"], caps["address_space_bytes"])
    )
    cpu_limit = int(start_cpu) + caps["cpu_seconds"]
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
    signal.signal(signal.SIGXCPU, _stop)
    signal.signal(signal.SIGALRM, _stop)
    signal.alarm(caps["wall_seconds"])
    completed, scorer_calls, status, reason = 0, 0, "STOPPED", None
    try:
        controls_args = {
            **plan["controls"],
            "audit_path": root / plan["controls"]["audit_path"],
            "stress_path": root / plan["controls"]["stress_path"],
        }
        controls = campaign_gate.run(**controls_args)
        study.write(output / "CONTROLS.json", controls)
        if controls["status"] != "CONTROL_PASS":
            raise core.LabRefused("measurement_controls_failed")
        panel = study.build_population(plan["config"])
        specs, digest = candidates.load(candidate_path)
        if digest != plan["candidate_sha256"] or set(specs) != set(
            plan["candidate_ids"]
        ):
            raise core.LabRefused("measurement_candidate_inventory")
        rules = {
            name: study.frozen_rule(
                panel,
                candidates.rule_from_spec(name, spec, path_digest=digest, panel=panel),
            )
            for name, spec in specs.items()
        }
        scorer_calls = sum(rule.scorer_calls for rule in rules.values())
        study.write(output / "POPULATION.json", panel)
        for index, cell in enumerate(plan["cells"]):
            if (
                time.process_time()
                - start_cpu
                + caps["complete_cell_reservation_cpu_seconds"]
                > caps["cpu_seconds"]
            ):
                raise TimeoutError("measurement_complete_cell_unaffordable")
            cell_cpu = time.process_time()
            law = study.finite_law(panel, cell["proposal"])
            result = study.compare(panel, law, cell, rules, bootstrap=plan["bootstrap"])
            result["evaluation_cpu_seconds"] = time.process_time() - cell_cpu
            data = (
                json.dumps(
                    result, sort_keys=True, separators=(",", ":"), allow_nan=False
                )
                + "\n"
            ).encode()
            (output / f"CELL_{index:03d}.json.gz").write_bytes(
                gzip.compress(data, mtime=0)
            )
            completed += 1
            study.write(
                output / "PROGRESS.json",
                {
                    "complete_cells": completed,
                    "planned_cells": len(plan["cells"]),
                    "cpu_seconds": time.process_time() - start_cpu,
                },
            )
        status = "COMPLETED"
    except (core.LabRefused, TimeoutError, MemoryError) as exc:
        reason = str(exc) or type(exc).__name__
    finally:
        signal.alarm(0)
        study.write(
            output / "RUN.json",
            {
                "status": status,
                "reason": reason,
                "complete_cells": completed,
                "planned_cells": len(plan["cells"]),
                "scorer_calls": scorer_calls,
                "cpu_seconds": time.process_time() - start_cpu,
                "wall_seconds": time.monotonic() - start_wall,
            },
        )
        identity["artifacts_sha256"] = {
            p.name: study.file_sha(p) for p in sorted(output.iterdir()) if p.is_file()
        }
        study.write(output / "IDENTITY.json", identity)
    return status


def readout(plan_path, directory):
    """No partial pass: verify the complete committed receipt chain."""
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    identity = json.loads((directory / "IDENTITY.json").read_text(encoding="utf-8"))
    start = json.loads((directory / "START.json").read_text(encoding="utf-8"))
    if (
        identity.get("schema") != study.SCHEMA
        or {k: v for k, v in identity.items() if k != "artifacts_sha256"} != start
    ):
        raise core.LabRefused("measurement_identity_binding")
    if (
        identity["plan_sha256"] != core.canonical_sha(plan)
        or json.loads((directory / "REGISTERED_PLAN.json").read_text(encoding="utf-8"))
        != plan
        or identity["candidate_sha256"] != plan["candidate_sha256"]
        or identity["sources"] != plan["sources"]
    ):
        raise core.LabRefused("measurement_plan_binding")
    if plan["cells"] != study.cells() or plan["candidate_ids"] != list(CANDIDATE_IDS):
        raise core.LabRefused("measurement_design_inventory")
    files = {
        p.name for p in directory.iterdir() if p.is_file() and p.name != "IDENTITY.json"
    }
    if files != set(identity["artifacts_sha256"]):
        raise core.LabRefused("measurement_artifact_inventory")
    for name, digest in identity["artifacts_sha256"].items():
        if Path(name).name != name or study.file_sha(directory / name) != digest:
            raise core.LabRefused("measurement_artifact_binding")
    run_receipt = json.loads((directory / "RUN.json").read_text(encoding="utf-8"))
    if run_receipt["status"] != "COMPLETED" or run_receipt["complete_cells"] != len(
        plan["cells"]
    ):
        raise core.LabRefused("measurement_incomplete_run")
    if (
        json.loads((directory / "CONTROLS.json").read_text(encoding="utf-8"))["status"]
        != "CONTROL_PASS"
    ):
        raise core.LabRefused("measurement_controls_failed")
    rows = []
    for index, cell in enumerate(plan["cells"]):
        result = json.loads(
            gzip.decompress((directory / f"CELL_{index:03d}.json.gz").read_bytes())
        )
        if result["cell"] != cell:
            raise core.LabRefused("measurement_cell_binding")
        if set(result["rows"]) != set(plan["candidate_ids"]):
            raise core.LabRefused("measurement_candidate_inventory")
        for name, measures in result["rows"].items():
            row = {
                "cell_index": index,
                **cell,
                "candidate": name,
                "status": measures["status"],
                "complete_blocks": result["block_mask"]["complete_blocks_available"],
                "unresolved_questions": result["block_mask"]["unresolved_questions"],
                "resolved_questions_excluded": result["block_mask"][
                    "resolved_questions_in_incomplete_blocks"
                ],
                "reported_estimand": result["estimand"],
            }
            if measures["status"] == "MEASURED_DEVELOPMENT":
                row["population_tau"] = measures["population_tau"]
                for unit in ("case", "block"):
                    row[unit] = {
                        key: measures[unit][key]
                        for key in (
                            "tau",
                            "tau_ci95",
                            "interval_width",
                            "tau_undefined_fraction",
                            "covers_population_tau",
                            "selected_value",
                            "top1_member",
                            "top1_regret",
                            "admissibility_failures",
                            "cheap_baseline_rank",
                            "always_abstain_rank",
                            "known_bad_in_top_half",
                            "adversarial_in_top_half",
                        )
                    }
            rows.append(row)
    return {
        "schema": study.SCHEMA,
        "scope": study.SCOPE,
        "plan_sha256": identity["plan_sha256"],
        "source_commit": identity["source_commit"],
        "run": run_receipt,
        "rows": rows,
        "descriptive_seed_summary": summarize(rows),
        "limits": plan["limits"],
        "selection": None,
    }


def summarize(rows):
    """Three-seed descriptions only, never a power/coverage qualification."""
    groups = {}
    dimensions = (
        "study",
        "N",
        "B",
        "dependence",
        "proposal",
        "estimand",
        "outage",
        "policy",
        "candidate",
    )
    for row in rows:
        key = tuple(row[k] for k in dimensions)
        groups.setdefault(key, []).append(row)
    output = []
    for key, members in groups.items():
        result = dict(zip(dimensions, key, strict=True))
        measured = [r for r in members if r["status"] == "MEASURED_DEVELOPMENT"]
        result.update(
            offered_sampling_seeds=len(members), measured_sampling_seeds=len(measured)
        )
        for unit in ("case", "block"):
            widths = [
                r[unit]["interval_width"]
                for r in measured
                if r[unit]["interval_width"] is not None
            ]
            taus = [r[unit]["tau"] for r in measured if r[unit]["tau"] is not None]
            coverage = [
                r[unit]["covers_population_tau"]
                for r in measured
                if r[unit]["covers_population_tau"] is not None
            ]
            result[unit] = {
                "mean_interval_width": statistics.fmean(widths) if widths else None,
                "tau_range": [min(taus), max(taus)] if taus else None,
                "descriptive_coverage_hits": sum(coverage),
                "coverage_defined": len(coverage),
                "selected_members": sorted(
                    {
                        r[unit]["top1_member"]
                        for r in measured
                        if r[unit]["top1_member"] is not None
                    }
                ),
            }
        output.append(result)
    return output


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("operation", choices=("register", "run", "readout"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.operation == "register":
        study.write(args.plan, register(args.root, args.candidates))
    elif args.operation == "run":
        status = run(args.root, args.plan, args.candidates, args.output)
        print(status)
        raise SystemExit(0 if status == "COMPLETED" else 1)
    else:
        print(json.dumps(readout(args.plan, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
