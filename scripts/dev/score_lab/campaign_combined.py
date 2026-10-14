"""Prospectively registered, bounded combinations of existing toy scorers.

This producer has no real-data fitting or holdout interface. Candidate Python
is trusted developer input, pinned before import. All score callbacks receive
only score-side material. The buyer-value view is evaluated afterwards.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import importlib.util
import itertools
import json
import os
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

from . import campaign_gate, campaign_goodhart, candidates, components, core, physics
from .core import LabRefused, canonical_sha

SCHEMA = "carbon.dev.score-lab-combined-plan.v1"
RESULT_SCHEMA = "carbon.dev.score-lab-combined-cell.v1"
SCOPES = ("in_range", "shifted", "extrapolated", "neighbourhood_blend")


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_sha(path):
    data = Path(path).read_bytes()
    if Path(path).suffix in (".py", ".json", ".md"):
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def catalogue(settings):
    if set(settings) != components.COMPONENT_KEYS:
        raise LabRefused("combined_component_catalogue")
    keys = sorted(settings)
    return [None] + [
        {key: copy.deepcopy(settings[key]) for key in subset}
        for size in range(1, len(keys) + 1)
        for subset in itertools.combinations(keys, size)
    ]


def validate_plan(plan):
    if plan.get("schema") != SCHEMA or plan.get("scope") != "SYNTHETIC_DEVELOPMENT":
        raise LabRefused("combined_plan_scope")
    profiles = plan.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise LabRefused("combined_profiles")
    names = [row["id"] for row in profiles]
    if len(names) != len(set(names)) or not all(type(x) is str and x for x in names):
        raise LabRefused("combined_profile_identity")
    for row in profiles:
        physics.validate_config(row["config"])
        if canonical_sha(row["config"]) != row["config_sha256"]:
            raise LabRefused("combined_config_digest")
        if row["config"].get("value_definition", "v2_shortlist") != "v2_shortlist":
            raise LabRefused("combined_buyer_job")
    if plan.get("value_scopes") != list(SCOPES):
        raise LabRefused("combined_value_scopes")
    if plan.get("physics_indices") != [0, 1, 2, 3]:
        raise LabRefused("combined_physics_catalogue")
    cells = catalogue(plan["components"])
    if plan.get("components_sha256") != canonical_sha(cells):
        raise LabRefused("combined_component_digest")
    ids = plan.get("candidate_ids", [])
    if len(ids) != 16 or len(set(ids)) != 16:
        raise LabRefused("combined_candidate_catalogue")
    ablations = plan.get("ablations", [])
    if len(ablations) != 6 or any(row["id"] not in ids for row in ablations):
        raise LabRefused("combined_ablation_catalogue")
    caps = plan.get("caps", {})
    required = {
        "total_cpu_seconds",
        "total_wall_seconds",
        "cell_cpu_seconds",
        "cell_wall_seconds",
        "address_space_bytes",
        "controls_cpu_seconds",
    }
    if set(caps) != required or any(
        type(value) is not int or value < 1 for value in caps.values()
    ):
        raise LabRefused("combined_caps")
    if caps["cell_cpu_seconds"] > caps["total_cpu_seconds"]:
        raise LabRefused("combined_unaffordable_cell")
    return plan


def verify_sources(plan, root, candidate_path):
    """Only registered repository-relative sources and the pinned developer file."""
    root = Path(root).resolve()
    for item in plan["sources"]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or path == root:
            raise LabRefused("combined_source_path")
        if source_sha(path) != item["sha256"]:
            raise LabRefused("combined_source_digest")
    registered_paths = {item["path"] for item in plan["sources"]}
    if any(
        plan["controls"][key] not in registered_paths
        for key in ("audit_path", "stress_path")
    ):
        raise LabRefused("combined_control_source_unregistered")
    if file_sha(candidate_path) != plan["candidates_sha256"]:
        raise LabRefused("combined_candidate_digest")


def load_specs(plan, path):
    # Hash before import: this is the existing trusted developer source, never
    # miner code or a source discovered by a run's predictions/outcomes.
    if file_sha(path) != plan["candidates_sha256"]:
        raise LabRefused("combined_candidate_digest")
    specs, digest = candidates.load(path)
    module_spec = importlib.util.spec_from_file_location("combined_candidates", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    specs = dict(specs)
    for row in plan["ablations"]:
        base = module._registry_rule(row["weights"], row["gates"])
        specs[row["id"]] = {
            "rule": module.with_physics(module.with_neighbourhood(base)),
            "tier2_registry_id": None,
        }
    if sorted(specs) != sorted(plan["candidate_ids"]):
        raise LabRefused("combined_candidate_identity")
    return specs, digest


def freeze_scores(scoring, rule):
    """Compute each input once; reject changed input on subsequent value views."""
    cache, by_member = {}, {}
    for member in scoring["members"]:
        metadata = {
            "score_row": member.get("score_row"),
            **scoring.get("score_metadata", {}),
            **member.get("score_metadata", {}),
        }
        args = [member["score_predictions"], scoring["score_questions"], metadata]
        key = canonical_sha(args)
        if key not in cache:
            value = rule(*args)
            core._number(value)  # Validate every attempted result, including probes.
            cache[key] = copy.deepcopy(value)
        by_member[member["id"]] = copy.deepcopy(cache[key])

    def replay(predictions, references, metadata):
        key = canonical_sha([predictions, references, metadata])
        if key not in cache:
            raise LabRefused("combined_score_input_changed")
        return copy.deepcopy(cache[key])

    replay.rule_identity = copy.deepcopy(rule.rule_identity)
    return replay, by_member, len(cache)


def evaluate_cell(plan, profile_index, component_index, specs, digest):
    validate_plan(plan)
    config = plan["profiles"][profile_index]["config"]
    component_spec = catalogue(plan["components"])[component_index]
    panel = physics.build(config)
    # This context is intentionally created from an allow-list. In particular,
    # no value_questions, value_losses or exact_oracle_losses enter a scorer.
    score_context = {
        "scope": panel["scope"],
        "score_questions": panel["score_questions"],
    }
    cheap = campaign_goodhart._legacy_cheap_score_control(
        config, score_context, panel["members"][0]["score_metadata"]
    )
    score_context["members"] = [] if cheap is None else [cheap]
    views = {
        scope: physics.value_view(panel, scope, config["neighbourhood"]["value_weight"])
        for scope in SCOPES
    }
    rows, calls = [], 0
    for candidate_id in plan["candidate_ids"]:
        rule = candidates.rule_from_spec(
            candidate_id,
            specs[candidate_id],
            path_digest=digest,
            panel=score_context,
            component_spec=component_spec,
        )
        for mode_index in plan["physics_indices"]:
            switch = config["physics_sweep"][mode_index]
            scoring = {
                "score_questions": panel["score_questions"],
                "members": [
                    {
                        key: member[key]
                        for key in (
                            "id",
                            "score_predictions",
                            "score_row",
                            "score_metadata",
                        )
                    }
                    for member in panel["members"]
                ],
                "score_metadata": {
                    "knobs": {
                        "physics": switch,
                        "neighbourhood_weight": config["neighbourhood"]["score_weight"],
                    }
                },
            }
            missing = None
            if component_spec and "cheap_margin_weight" in component_spec:
                if cheap is None:
                    missing = "missing_cheap_score_predictions"
                elif switch["mode"] != "OFF" and not cheap["score_metadata"].get(
                    "physics"
                ):
                    missing = "missing_cheap_physics_measurements"
            if missing:
                outcomes = {
                    scope: {"status": "INSUFFICIENT_EVIDENCE", "reason": missing}
                    for scope in SCOPES
                }
                scores = {member["id"]: None for member in panel["members"]}
            else:
                replay, scores, attempted = freeze_scores(scoring, rule)
                calls += attempted
                outcomes = {}
                for scope, view in views.items():
                    view = {**view, "score_metadata": scoring["score_metadata"]}
                    outcome = core.analyze(view, replay, bootstrap=config["bootstrap"])
                    common = sorted(
                        q
                        for q in view["value_questions"]
                        if all(
                            m["value_losses"][q] is not None for m in view["members"]
                        )
                    )
                    values = (
                        {
                            m["id"]: -statistics.fmean(
                                m["value_losses"][q] for q in common
                            )
                            for m in view["members"]
                        }
                        if common
                        else {}
                    )
                    outcomes[scope] = {
                        **outcome,
                        "common_mask_sha256": canonical_sha(common),
                        "value_by_member": values,
                        "top1_value": values.get(outcome.get("top1_member")),
                    }
            rows.append(
                {
                    "candidate": candidate_id,
                    "physics_index": mode_index,
                    "physics": switch,
                    "scores": scores,
                    "outcomes": outcomes,
                }
            )
    return {
        "schema": RESULT_SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "plan_sha256": canonical_sha(plan),
        "profile_index": profile_index,
        "component_index": component_index,
        "component_spec": component_spec,
        "panel_sha256": canonical_sha(panel),
        "scorer_evaluations": calls,
        "model_inference_calls": 0,
        "solver_calls": 0,
        "rows": rows,
    }


def summarize(cells):
    """Retain denominators and paired effects, including withheld cells."""
    flat = []
    for cell in cells:
        for row in cell["rows"]:
            for scope, result in row["outcomes"].items():
                flat.append(
                    {
                        "profile": cell["profile_index"],
                        "components": cell["component_index"],
                        "candidate": row["candidate"],
                        "physics": row["physics_index"],
                        "value_scope": scope,
                        **result,
                    }
                )
    baseline = {
        (r["profile"], r["candidate"], r["physics"], r["value_scope"]): r
        for r in flat
        if r["components"] == 0
    }
    paired = []
    for row in flat:
        if row["components"] == 0:
            continue
        base = baseline.get(
            (row["profile"], row["candidate"], row["physics"], row["value_scope"])
        )
        comparable = base is not None and base.get("common_mask_sha256") == row.get(
            "common_mask_sha256"
        )
        value, base_value = row.get("top1_value"), (
            base.get("top1_value") if base else None
        )
        paired.append(
            {
                key: row[key]
                for key in (
                    "profile",
                    "components",
                    "candidate",
                    "physics",
                    "value_scope",
                )
            }
            | {
                "delta_selected_value": (
                    value - base_value
                    if comparable and value is not None and base_value is not None
                    else None
                ),
                "reason": (
                    None
                    if comparable and value is not None and base_value is not None
                    else "no_common_scored_pair"
                ),
            }
        )
    reasons = {}
    for row in flat:
        key = row.get("reason", row["status"])
        reasons[key] = reasons.get(key, 0) + 1
    return {
        "scoped_outcomes": len(flat),
        "status_counts": reasons,
        "paired_component_effects": paired,
        "selection": None,
        "weight_search": "NOT_PERFORMED_FIXED_REGISTERED_EXAMPLES_ONLY",
    }


def _dump(path, value):
    data = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()
    Path(path).write_bytes(
        gzip.compress(data, mtime=0) if str(path).endswith(".gz") else data
    )


def _limits(caps, controls=False):
    import resource

    cpu = caps["controls_cpu_seconds"] if controls else caps["cell_cpu_seconds"]
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(
        resource.RLIMIT_AS, (caps["address_space_bytes"], caps["address_space_bytes"])
    )


def cell_affordable(caps, spent_cpu, elapsed_wall):
    return (
        spent_cpu + caps["cell_cpu_seconds"] <= caps["total_cpu_seconds"]
        and elapsed_wall + caps["cell_wall_seconds"] <= caps["total_wall_seconds"]
    )


def run(plan_path, candidate_path, output, root):
    """Linux-only isolated workers; reserves a complete cell before dispatch."""
    if sys.platform != "linux":
        raise LabRefused("combined_requires_canonical_linux")
    import resource

    plan = validate_plan(json.loads(Path(plan_path).read_text(encoding="utf-8")))
    verify_sources(plan, root, candidate_path)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    wall_start = time.monotonic()
    base_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    caps = plan["caps"]
    records, cells = [], []
    controls_cpu = 0.0

    def dispatch(kind, args, filename):
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        env = {
            **os.environ,
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        command = [
            sys.executable,
            "-m",
            "scripts.dev.score_lab.campaign_combined",
            kind,
            str(plan_path),
            str(candidate_path),
            str(output / filename),
            *args,
        ]
        proc = subprocess.Popen(
            command,
            env=env,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        limit = min(
            caps["cell_wall_seconds"],
            caps["total_wall_seconds"] - (time.monotonic() - wall_start),
        )
        try:
            _, err = proc.communicate(timeout=max(0.001, limit))
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            _, err = proc.communicate()
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        record = {
            "file": filename,
            "returncode": proc.returncode,
            "cpu_seconds": after.ru_utime
            + after.ru_stime
            - before.ru_utime
            - before.ru_stime,
            "wall_seconds": time.monotonic() - start,
            "stderr": err.decode("utf-8", errors="replace")[-2000:],
        }
        if proc.returncode == 0:
            record["sha256"] = file_sha(output / filename)
        records.append(record)
        return record

    control = dispatch("_controls", [str(root)], "CONTROLS.json")
    controls_cpu = control["cpu_seconds"]
    status = "CONTROL_FAILED"
    if (
        control["returncode"] == 0
        and json.loads((output / "CONTROLS.json").read_text())["status"]
        == "CONTROL_PASS"
    ):
        status = "COMPLETE"
        for p, c in itertools.product(
            range(len(plan["profiles"])), range(len(catalogue(plan["components"])))
        ):
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            spent = (
                usage.ru_utime
                + usage.ru_stime
                - base_cpu.ru_utime
                - base_cpu.ru_stime
                - controls_cpu
            )
            if not cell_affordable(caps, spent, time.monotonic() - wall_start):
                status = "STOPPED_BEFORE_UNAFFORDABLE_CELL"
                break
            record = dispatch("_cell", [str(p), str(c)], f"CELL_{p}_{c}.json.gz")
            if record["returncode"] != 0:
                status = "STOPPED_WORKER_FAILURE_OR_CAP"
                break
            cells.append(
                json.loads(gzip.decompress((output / record["file"]).read_bytes()))
            )
            _dump(
                output / "PROGRESS.json",
                {"completed_cells": len(cells), "last": record},
            )
    result = {
        "schema": "carbon.dev.score-lab-combined-run.v1",
        "status": status,
        "plan_sha256": canonical_sha(plan),
        "records": records,
        "completed_cells": len(cells),
        "offered_cells": len(plan["profiles"]) * len(catalogue(plan["components"])),
        "controls_cpu_seconds": controls_cpu,
        "evaluation_cpu_seconds": sum(r["cpu_seconds"] for r in records[1:]),
        "total_wall_seconds": time.monotonic() - wall_start,
        "caps": caps,
        "summary": summarize(cells),
        "scope": "SYNTHETIC_DEVELOPMENT",
    }
    _dump(output / "RUN.json.gz", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "_cell", "_controls"))
    parser.add_argument("plan", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("extra", nargs="*")
    args = parser.parse_args()
    plan = validate_plan(json.loads(args.plan.read_text(encoding="utf-8")))
    if args.mode == "run":
        result = run(
            args.plan.resolve(),
            args.candidates.resolve(),
            args.output.resolve(),
            Path.cwd(),
        )
        print(
            json.dumps(
                {
                    key: result[key]
                    for key in ("status", "completed_cells", "evaluation_cpu_seconds")
                }
            )
        )
        return 0 if result["status"] == "COMPLETE" else 2
    _limits(plan["caps"], controls=args.mode == "_controls")
    if args.mode == "_controls":
        root = Path(args.extra[0])
        ctl = plan["controls"]
        result = campaign_gate.run(
            audit_path=root / ctl["audit_path"],
            stress_path=root / ctl["stress_path"],
            problem=ctl["problem"],
            questions_per_side=ctl["questions_per_side"],
            cap=ctl["cap"],
        )
    else:
        specs, digest = load_specs(plan, args.candidates)
        result = evaluate_cell(
            plan, int(args.extra[0]), int(args.extra[1]), specs, digest
        )
    _dump(args.output, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
