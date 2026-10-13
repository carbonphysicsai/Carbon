"""Retained-public-data f02 L0 -> three-arm OPT-12 pilot, no reference solves.

Data Collection supplies the closed pinned bundle described in the runbook.
`run` rebuilds the registered L0 on TRAIN only. `dry-run` is structurally
fixture-only and does not train a real network or claim physical evidence.
`pod-spec` composes, but never runs, the existing public pod-job launcher.
"""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import math
import os
import re
from pathlib import Path

from carbon.design_search import equal_budget as eb
from carbon.design_search import producer_panels, tasks
from carbon.design_search import winnability_pilot as wp
from carbon.development_comparison import carbon_arm as ca
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import evidence_pipeline as ep
from carbon.development_comparison.campaign_adapters import assembly_design as ad
from carbon.development_comparison.f02_kit import KIT, context
from scripts.dev.reference_packages.elmer import f02_deck as deck

SCHEMA = "carbon.f02.winnability-bundle.v1"
SCREEN = "carbon.f02.train-only-spatial-rom-screen.v1"
COSTS = "carbon.f02.winnability-costs.v1"
RESULT = "carbon.f02.winnability-run.v1"
FIXTURE = "carbon.f02.winnability-dry-run.v1"
IMAGE = "sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675"
METHOD = "multi-input-spatial-impulse-response-or-state-space-v1"
SEEDS = (0, 1, 2)
MAX_FIT_CPU_S = 4 * 3600
ROLES = {"export", "train", "cheap_screen", "costs", "policy", "reference_receipt"}
ROOT = Path(__file__).resolve().parents[2]


class PilotHold(ValueError):
    """Missing or incompatible public producer data; never a candidate failure."""


def _shape(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise PilotHold(label + "_SHAPE")


def _cost(value):
    _shape(value, ("wall_s", "core_s"), "COST")
    if any(
        type(v) not in (int, float) or not math.isfinite(v) or v < 0
        for v in value.values()
    ):
        raise PilotHold("COST_NOT_MEASURED")
    return value.copy()


def _pin(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise PilotHold("DIGEST_REQUIRED")
    return value


def _load(path):
    path = Path(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    _shape(manifest, ("schema", "scope", "sources"), "BUNDLE")
    if manifest["schema"] != SCHEMA or manifest["scope"] != "PUBLIC_DEVELOPMENT":
        raise PilotHold("PUBLIC_BUNDLE_REQUIRED")
    _shape(manifest["sources"], ROLES, "SOURCES")
    documents, pins, paths = {}, {}, set()
    base = path.parent.resolve()
    for role, row in manifest["sources"].items():
        _shape(row, ("path", "sha256"), "SOURCE")
        _pin(row["sha256"])
        rel = Path(row["path"])
        if rel.as_posix() in paths or rel.name == path.name:
            raise PilotHold("DUPLICATE_BUNDLE_PATH")
        paths.add(rel.as_posix())
        target = base / rel
        if (
            rel.is_absolute()
            or ".." in rel.parts
            or not target.resolve().is_relative_to(base)
        ):
            raise PilotHold("LOCAL_PUBLIC_PATH_REQUIRED")
        if any(
            p.is_symlink() for p in (target, *target.parents) if p.is_relative_to(base)
        ):
            raise PilotHold("SYMLINK_REFUSED")
        # Same public upload guard as the launcher; don't read an excluded path.
        from carbon.agent_campaign.pod_jobs import _sealed, _upload_path

        if _sealed(target) or not _upload_path(rel.as_posix()):
            raise PilotHold("PUBLIC_PATH_REQUIRED")
        raw = target.read_bytes()
        if len(raw) > 95 * 1024 * 1024 or ca.sha256(raw) != row["sha256"]:
            raise PilotHold("SOURCE_PIN_OR_SIZE_MISMATCH")
        documents[role] = raw if role == "train" else json.loads(raw)
        pins[role] = row["sha256"]
    return documents, pins


def energy(action, condition):
    """Known waveform objective, identical for all arms, never learned truth."""
    knots = deck.schedule({**context(condition), **action})
    return sum(
        (b - a) * ((pa + pb) / 2 - deck.BASE_W)
        for (a, pa), (b, pb) in itertools.pairwise(knots)
    )


def _inventory(export, train, *, fixture=False):
    producer_panels.adapt_export(export)
    if export["family"] != "f02" or (train.fixture and not fixture):
        raise PilotHold("F02_PUBLIC_DATA_REQUIRED")
    rows = cb._physical_rows(export)
    for row in rows:
        if not math.isclose(
            row["values"]["extra_energy_j"],
            energy(row["action"], row["condition"]),
            rel_tol=1e-10,
            abs_tol=1e-8,
        ):
            raise PilotHold("REFERENCE_WAVEFORM_OBJECTIVE_MISMATCH")
    held = {ca.canonical(KIT.row_inputs(row)) for row in rows}
    training = [ca.canonical(r["inputs"]) for r in train.records]
    if len(training) != len(set(training)) or held.intersection(training):
        raise PilotHold("PHYSICAL_TRAIN_HELDOUT_OVERLAP_OR_DUPLICATE")
    if train.excluded:
        raise PilotHold("TRAIN_NONFINITE_ROWS")
    if not fixture:
        from scripts.dev.evidence_runs.f02 import train_draws
        from scripts.dev.reference_packages.elmer import f02_menu

        required = {
            ca.canonical({**base, "peak_w": p, "on_time_s": d})
            for i, (_ctx, base, p, d) in enumerate(train_draws())
            if i % 40 < 8
        }
        if set(training) != required:
            raise PilotHold("REGISTERED_192_TRAIN_SUBSET_REQUIRED")
        expected = {
            ca.canonical({**base, "peak_w": p, "on_time_s": d})
            for _ctx, base in f02_menu.contexts()
            for p in f02_menu.PEAKS_W
            for d in f02_menu.ON_TIMES_S
        }
        if held != expected or len(rows) != 384 or len(export["questions"]) != 24:
            raise PilotHold("COMPLETE_16_BY_24_MENU_REQUIRED")
        # Rebuild each immutable task; requirements/observer/tie rules cannot drift.
        from scripts.dev.reference_packages.elmer import f02_export

        candidates, actions = f02_export._bank()
        for entry in export["questions"]:
            condition = entry["task"]["conditions"][0]["id"]
            if entry["task"] != f02_export._task(condition, candidates, actions):
                raise PilotHold("MENU_TASK_CONTRACT_DRIFT")
    return rows


def _screen(export, supplied, train_pin, *, fixture=False):
    _shape(
        supplied,
        (
            "schema",
            "scope",
            "method",
            "export_digest",
            "train_sha256",
            "calibration_role",
            "policy_digest",
            "source_digests",
            "predictions",
            "query_costs",
        ),
        "ROM_SCREEN",
    )
    if (
        supplied["schema"] != SCREEN
        or supplied["method"] != METHOD
        or supplied["scope"]
        != ("SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT")
        or supplied["export_digest"] != export["export_digest"]
        or supplied["train_sha256"] != train_pin
        or supplied["calibration_role"] != "TRAIN_ONLY"
    ):
        raise PilotHold("TRAIN_ONLY_SPATIAL_ROM_RECEIPT_REQUIRED")
    _pin(supplied["policy_digest"])
    if type(supplied["source_digests"]) is not list or not supplied["source_digests"]:
        raise PilotHold("ROM_ACQUISITION_PINS_REQUIRED")
    for pin in supplied["source_digests"]:
        _pin(pin)
    predictions = supplied["predictions"]
    if predictions.get("scope") != supplied["scope"]:
        raise PilotHold("ROM_FIXTURE_PROMOTION_REFUSED")
    values = ep._predictions(export, predictions)
    _shape(
        supplied["query_costs"],
        [e["case"] for e in export["questions"]],
        "ROM_QUERY_COSTS",
    )
    return values, {k: _cost(v) for k, v in supplied["query_costs"].items()}


def _prepare(documents, pins, *, fixture=False):
    export = documents["export"]
    train = ca.load_train(KIT, documents["train"], pins["train"])
    _inventory(export, train, fixture=fixture)
    policy, costs = documents["policy"], documents["costs"]
    _shape(
        policy,
        (
            "schema",
            "scope",
            "export_digest",
            "question_law",
            "solver_orders",
            "served_decisions",
            "seed_policy",
            "frozen_before_heldout",
        ),
        "POLICY",
    )
    if (
        policy["schema"] != "carbon.f02.winnability-policy.v1"
        or policy["scope"] != ("SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT")
        or policy["export_digest"] != export["export_digest"]
        or policy["frozen_before_heldout"] is not True
        or policy["seed_policy"] != list(SEEDS)
    ):
        raise PilotHold("PREDECLARED_POLICY_REQUIRED")
    _shape(policy["question_law"], ("P", "Q", "w", "panel_use"), "QUESTION_LAW")
    if any(
        v in (None, "HUMAN_INPUT", "OPEN", "") for v in policy["question_law"].values()
    ):
        raise PilotHold("DIAGNOSTIC_P_Q_W_IDENTITIES_REQUIRED")
    _shape(
        policy["solver_orders"],
        [e["case"] for e in export["questions"]],
        "SOLVER_ORDERS",
    )
    for e in export["questions"]:
        order = policy["solver_orders"][e["case"]]
        if (
            type(order) is not list
            or len(order) != len(e["task"]["candidates"])
            or set(order) != set(e["task"]["candidates"])
        ):
            raise PilotHold("COMPLETE_PREDECLARED_SOLVER_ORDER_REQUIRED")
    cheap, query_costs = _screen(
        export, documents["cheap_screen"], pins["train"], fixture=fixture
    )
    if documents["cheap_screen"]["policy_digest"] != pins["policy"]:
        raise PilotHold("ROM_POLICY_IDENTITY_MISMATCH")
    _shape(
        costs,
        (
            "schema",
            "scope",
            "export_digest",
            "reference",
            "preparation",
            "acquisition_sources",
            "failed_control_cost",
            "lifecycle",
        ),
        "COST_RECORD",
    )
    if (
        costs["schema"] != COSTS
        or costs["scope"] != policy["scope"]
        or costs["export_digest"] != export["export_digest"]
    ):
        raise PilotHold("COST_IDENTITY_MISMATCH")
    reference_costs(export, costs)
    _shape(costs["preparation"], ("model", "baseline"), "PREPARATION")
    for value in costs["preparation"].values():
        _cost(value)
    _cost(costs["failed_control_cost"])
    if (
        type(costs["acquisition_sources"]) is not list
        or not costs["acquisition_sources"]
    ):
        raise PilotHold("COMPLETE_ACQUISITION_COST_RECEIPTS_REQUIRED")
    for source in costs["acquisition_sources"]:
        _pin(source)
    # Actual allocation lifecycle is retained separately from hypothetical replay costs.
    _shape(costs["lifecycle"], ("status", "receipt_digest"), "LIFECYCLE")
    if costs["lifecycle"]["status"] != "NOT_RUN":
        _pin(costs["lifecycle"]["receipt_digest"])
    receipt = documents["reference_receipt"]
    _shape(
        receipt,
        (
            "schema",
            "scope",
            "image_digest",
            "export_digest",
            "observer",
            "convergence",
            "conservation",
            "code_verification",
            "reference_status",
        ),
        "REFERENCE",
    )
    if (
        receipt["schema"] != "carbon.f02.pilot-reference-return.v1"
        or receipt["scope"] != policy["scope"]
        or receipt["image_digest"] != IMAGE
        or receipt["export_digest"] != export["export_digest"]
        or receipt["reference_status"] != "PUBLIC_DIAGNOSTIC_ONLY"
    ):
        raise PilotHold("REFERENCE_FAMILY_IDENTITY_REQUIRED")
    for key in ("observer", "convergence", "conservation", "code_verification"):
        _pin(receipt[key])
    return export, train, cheap, query_costs, policy, costs


def reference_costs(export, costs):
    """Validate all complete reference costs before an expensive fit begins."""
    result = {}
    if type(costs["reference"]) is not list:
        raise PilotHold("REFERENCE_COST_ROWS_REQUIRED")
    for row in costs["reference"]:
        _shape(
            row,
            ("candidate", "condition", "cost", "planning_bound", "source_digests"),
            "REFERENCE_COST",
        )
        key = (row["candidate"], row["condition"])
        if (
            key in result
            or type(row["source_digests"]) is not list
            or not row["source_digests"]
        ):
            raise PilotHold("DUPLICATE_OR_UNBOUND_REFERENCE_COST")
        for pin in row["source_digests"]:
            _pin(pin)
        measured, bound = _cost(row["cost"]), _cost(row["planning_bound"])
        if any(measured[k] <= 0 or bound[k] < measured[k] for k in measured):
            raise PilotHold("POSITIVE_COMPLETE_REFERENCE_COST_AND_BOUND_REQUIRED")
        result[key] = measured, bound
    expected = {(r["candidate"], r["condition"]) for r in cb._physical_rows(export)}
    if set(result) != expected:
        raise PilotHold("COMPLETE_REFERENCE_COST_INVENTORY_REQUIRED")
    return result


def _known_energy(export, values):
    values = copy.deepcopy(values)
    for row in cb._physical_rows(export):
        key = (row["band"], row["candidate"], row["condition"])
        if key in values:
            values[key]["extra_energy_j"] = energy(row["action"], row["condition"])
    return values


def replay(export, model, cheap, query_costs, model_receipt, policy, costs):
    """Build complete candidate banks and learning rows; no physical solves."""
    registered = ad.registration("f02")
    registration = json.loads(
        (
            ROOT
            / "docs/development/challenge_pipeline/equal-budget-registration-v2-f02-menu.json"
        ).read_text(encoding="utf-8")
    )
    model = _known_energy(export, ep._predictions(export, model))
    cheap = _known_energy(export, cheap)
    cost_index = reference_costs(export, costs)
    timing = {
        r["query"]: {"wall_s": r["wall_s"], "core_s": r["cpu_s"]}
        for r in model_receipt["cost"]["inference"]["decision_queries"]
    }
    jobs, learning = [], []
    for e in export["questions"]:
        task, truth = ep._assess(e, {}, reference=True)["plain"]
        _t, learned = ep._assess(e, model)["plain"]
        _t, mapped = ep._assess(e, cheap)["plain"]
        orders = {
            "model": ep._order(learned, task),
            "baseline": ep._order(mapped, task),
        }
        candidates = []
        for candidate in task["candidates"]:
            status = truth[candidate]["feasible"]
            total, bound = {"wall_s": 0, "core_s": 0}, {"wall_s": 0, "core_s": 0}
            for condition in task["conditions"]:
                cost, cap = cost_index[(candidate, condition["id"])]
                for unit in total:
                    total[unit] += cost[unit]
                    bound[unit] += cap[unit]
            candidates.append(
                {
                    "design_id": candidate,
                    "reference": {
                        "status": (
                            "UNRESOLVED"
                            if status is None
                            else "FEASIBLE" if status else "INFEASIBLE"
                        ),
                        "value": (
                            truth[candidate]["objective"] if status is True else None
                        ),
                    },
                    "solve_cost": total,
                    "planning_bound": bound,
                    "screen_rank": {
                        arm: order.index(candidate) for arm, order in orders.items()
                    },
                }
            )
        jobs.append(
            {
                "job_id": e["case"],
                "cluster_id": e["support_case"],
                "candidates": candidates,
                "solver_order": policy["solver_orders"][e["case"]],
                "screen_cost": {
                    "model": timing[e["case"]],
                    "baseline": query_costs[e["case"]],
                },
            }
        )
        unresolved = any(t["feasible"] is None for t in truth.values())
        pick, best = tasks.select(task, learned), tasks.select(task, truth)
        errors = [
            abs(
                model[(None, r["candidate"], r["condition"])]["peak_top_c"]
                - r["values"]["peak_top_c"]
            )
            for r in e["reference"]
            if (None, r["candidate"], r["condition"]) in model
        ]
        learning.append(
            {
                "job_id": e["case"],
                "cluster_id": e["support_case"],
                "stratum": task["conditions"][0]["stratum"],
                "reference_status": (
                    "UNRESOLVED"
                    if unresolved
                    else "FEASIBLE_EXISTS" if best is not None else "NONE_FEASIBLE"
                ),
                "pointwise_error": (
                    None if unresolved or not errors else sum(errors) / len(errors)
                ),
                "decision_agreement": None if unresolved else pick == best,
                "false_feasible": (
                    None
                    if unresolved
                    else pick is not None and truth[pick]["feasible"] is False
                ),
                "missed_feasible": (
                    None if unresolved else pick is None and best is not None
                ),
                "abstained": None if unresolved else pick is None,
            }
        )
    panel = eb.seal(
        {
            "schema": eb.SCHEMA,
            "evidence_class": "DEVELOPMENT",
            "challenge": "f02",
            "source_digest": export["export_digest"],
            "decision_rule_id": "f02-menu-v2-public-diagnostic",
            "objective": {"direction": "max", "unit": "J"},
            "cost_basis": "MEASURED",
            "execution_plan": "SERIAL_COMPLETE_PANELS",
            "jobs": jobs,
            "budgets": [
                registered.cap("f02", tier).time_compute
                for tier in ("half", "base", "double")
            ],
            "registrations": {
                "solver_search": ca.sha256(ca.canonical(policy)),
                "model_screen": KIT.model_id,
                "baseline_screen": METHOD,
                "cost_plan": registered.registration_id,
            },
        }
    )
    fit = model_receipt["cost"]["fit"]
    preparation = copy.deepcopy(costs["preparation"])
    preparation["model"]["wall_s"] += fit["fit_wall_s"]
    preparation["model"]["core_s"] += fit["fit_cpu_s"]
    query = model_receipt["cost"]["inference"]
    # Keep warm per-question queries in screen_cost, and charge every other
    # actually performed inference/compilation pass in preparation.
    preparation["model"]["wall_s"] += (
        query["cold_wall_s"]
        + query["wall_s"]
        + sum(r["cold_wall_s"] for r in query["decision_queries"])
    )
    preparation["model"]["core_s"] += (
        query["cold_cpu_s"]
        + query["cpu_s"]
        + sum(r["cold_cpu_s"] for r in query["decision_queries"])
    )
    # Controls and failed acquisition attempts are charged to both prepared arms,
    # never silently erased or treated as candidate reference failures.
    for arm in preparation:
        for unit in preparation[arm]:
            preparation[arm][unit] += costs["failed_control_cost"][unit]
    source = {
        "schema": wp.SCHEMA,
        "evidence_class": "DEVELOPMENT_PUBLIC",
        "panel": panel,
        "registration": registration,
        "methods": {
            "model": "PLAIN_L0_MLP",
            "cheap": "STRONGEST_APPLICABLE_CHEAP",
            "solver": "REGISTERED_ADAPTIVE_SOLVER",
        },
        "question_law": policy["question_law"],
        "preparation_cost": preparation,
        "served_decisions": policy["served_decisions"],
        "learning": learning,
        "learning_unit": "K",
        "cost_record_digest": ca.sha256(ca.canonical(costs)),
    }
    return source


def execute(documents, pins, *, fixture=False, trainer=None):
    """One fixed seed policy, no post-hoc winner among replicas."""
    export, train, cheap, queries, policy, costs = _prepare(
        documents, pins, fixture=fixture
    )
    scope = "SYNTHETIC_FIXTURE" if fixture else "PUBLIC_DEVELOPMENT"
    reports, fit_cpu = [], 0.0
    candidate_view = copy.deepcopy(export)
    for e in candidate_view["questions"]:
        e.pop("settled", None)
        for r in e["reference"]:
            r["values"] = {k: 0.0 for k in KIT.observables}
    for seed in SEEDS:
        if fit_cpu >= MAX_FIT_CPU_S:
            raise PilotHold("AGGREGATE_FIT_CAP_EXHAUSTED")
        if os.name == "posix" and not fixture:
            import resource

            used = resource.getrusage(resource.RUSAGE_SELF)
            # The shared JAX trainer runs in this process. The soft CPU limit
            # counts every thread, so a fit cannot run past the remaining cap.
            deadline = math.ceil(
                used.ru_utime + used.ru_stime + MAX_FIT_CPU_S - fit_cpu
            )
            resource.setrlimit(resource.RLIMIT_CPU, (min(deadline, 6 * 3600), 6 * 3600))
        predictions, receipt = (trainer or ca.run)(
            KIT, candidate_view, train, scope=scope, seed=seed, backend="jax"
        )
        if os.name == "posix" and not fixture:
            resource.setrlimit(resource.RLIMIT_CPU, (6 * 3600, 6 * 3600))
        fit_cpu += receipt["cost"]["fit"]["fit_cpu_s"]
        if fit_cpu > MAX_FIT_CPU_S:
            raise PilotHold("AGGREGATE_FIT_CAP_EXCEEDED")
        source = replay(export, predictions, cheap, queries, receipt, policy, costs)
        report = wp.evaluate(
            source,
            bootstrap_replicates=100 if fixture else 2000,
            confidence=0.95,
            seed=0,
        )
        reports.append(
            {"seed": seed, "receipt": receipt, "input": source, "report": report}
        )
    return {
        "schema": FIXTURE if fixture else RESULT,
        "scope": scope,
        "source_pins": pins,
        "family": "f02",
        "reports": reports,
        "aggregate_fit_cpu_s": fit_cpu,
        "qualification": "UNDECIDED",
        "thresholds": "HUMAN_INPUT",
        "customer_result": False,
        "real_pilot_executed": not fixture,
        "reference_solves": 0,
    }


def run(bundle, output):
    # The launcher's allocation deadline encloses the whole worker. CPU limits
    # also include trainer subprocesses (the current trainer is in-process).
    if os.name == "posix":
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (6 * 3600, 6 * 3600))
    documents, pins = _load(bundle)
    result = execute(documents, pins)
    _write(output, result)
    return result


def _write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def pod_spec(bundle, code_ref):
    """Generate a validated spec; no network, credentials, quote or grant check."""
    from carbon.agent_campaign.pod_jobs import load_spec

    _documents, _pins = _load(bundle)
    manifest = json.loads(Path(bundle).read_text(encoding="utf-8"))
    files = {Path(bundle).name: Path(bundle)}
    for row in manifest["sources"].values():
        files[row["path"]] = Path(bundle).parent / row["path"]
    spec = {
        "schema": "carbon.pod-job.spec.v1",
        "job_id": "f02-winnability-pilot",
        "code_ref": code_ref,
        "module": "carbon.development_comparison.f02_pilot",
        "args": ["run", "{inputs}/" + Path(bundle).name, "--out", "{out}/pilot.json"],
        "inputs": [
            "docs/development/challenge_pipeline/equal-budget-registration-v2-f02-menu.json"
        ],
        "image": "study",
        "overlays": {},
        "compute": {"kind": "cpu", "flavor": "cpu5c", "vcpus": 32},
        "minutes": 465,
        "rate_ceiling_usd_per_hr": 1.20,
        "cap_usd": 10.0,
        "disk_gb": 20,
        "uploads": {
            name: {
                "sha256": ca.sha256(path.read_bytes())[7:],
                "bytes": path.stat().st_size,
            }
            for name, path in files.items()
        },
        "collect": [],
    }
    load_spec(spec)
    return spec


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    dry = sub.add_parser("dry-run")
    dry.add_argument("--out", type=Path, required=True)
    for cmd in ("run", "check", "pod-spec"):
        p = sub.add_parser(cmd)
        p.add_argument("bundle", type=Path)
        if cmd != "check":
            p.add_argument("--out", type=Path, required=True)
        if cmd == "pod-spec":
            p.add_argument("--code-ref", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "dry-run":
            from carbon.development_comparison.f02_pilot_fixture import dry_run

            _write(args.out, dry_run())
            print(
                json.dumps(
                    {"status": "FIXTURE_WIRING_ONLY", "real_pilot_executed": False}
                )
            )
        elif args.command == "run":
            result = run(args.bundle, args.out)
            print(
                json.dumps(
                    {"status": "COMPLETED_PUBLIC_DIAGNOSTIC", "scope": result["scope"]}
                )
            )
        elif args.command == "check":
            documents, pins = _load(args.bundle)
            _prepare(documents, pins)
            print(
                json.dumps(
                    {
                        "status": "PUBLIC_DATA_CONTRACT_CHECKED_NO_EXECUTION",
                        "pins": pins,
                    }
                )
            )
        else:
            _write(args.out, pod_spec(args.bundle, args.code_ref))
        return 0
    except (
        PilotHold,
        ca.ArmRefused,
        ep.Refusal,
        wp.WinnabilityError,
        eb.EqualBudgetError,
        tasks.TaskError,
        OSError,
    ) as hold:
        print(
            json.dumps(
                {"status": "HOLD", "reason": str(hold), "candidate_failure": False}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
