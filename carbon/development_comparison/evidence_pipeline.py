"""Pinned public-development panels to comparisons and an evidence-pack page.

No solver, model execution, remote access, publication or authority mutation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import platform
import re
import sys
import time
from pathlib import Path

from carbon.design_search import equal_budget as eb
from carbon.design_search import producer_panels, reference_resolution, tasks
from carbon.development_comparison import cheap_baselines as cb
from carbon.development_comparison import portfolio_baselines as pb
from carbon.development_comparison import value_bar as vb

SCHEMA = "carbon.development-evidence-pipeline.v1"
PREDICTIONS = "carbon.development-prediction-input.v1"
BINDINGS = "carbon.development-replay-bindings.v1"
CONTEXT = "carbon.development-value-context.v1"
INDEXED_F02 = "carbon.development-indexed-f02-materials.v1"
ROLES = {"export", "comparator", "carbon", "replay", "bindings", "context", "rule"}
ALIASES = {
    "battery-v3": "battery-fastcharge-ageing-development-v1",
    "motor": "electric-motor-magnetics",
    "f02": "f02",
}
ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 32 * 1024 * 1024


class Refusal(ValueError):
    def __init__(self, stage, code):
        self.stage, self.code = stage, code
        super().__init__(f"{stage}: {code}")


def _shape(value, keys, stage):
    if type(value) is not dict or set(value) != set(keys):
        raise Refusal(stage, "CLOSED_SCHEMA_REQUIRED")


def _stage(stage, operation):
    try:
        return operation()
    except Refusal:
        raise
    except (
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        OverflowError,
        AttributeError,
        StopIteration,
    ):
        raise Refusal(stage, "INVALID_OR_INCOMPLETE_INPUT") from None
    except RecursionError:
        raise Refusal(stage, "RESOURCE_LIMIT") from None


def _sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json(data):
    def pairs(rows):
        out = {}
        for key, value in rows:
            if key in out:
                raise Refusal("load", "DUPLICATE_JSON_KEY")
            out[key] = value
        return out

    return json.loads(
        data,
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(
            Refusal("load", "NONFINITE_JSON")
        ),
    )


def _read(path, digest):
    if str(path).startswith(("\\\\", "//")):
        raise Refusal("load", "REMOTE_PATH_REFUSED")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(digest)):
        raise Refusal("load", "BYTE_PIN_REQUIRED")
    if not path.is_file() or path.is_symlink():
        raise Refusal("load", "REGULAR_LOCAL_FILE_REQUIRED")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise Refusal("load", "RESOURCE_LIMIT")
    if _sha(raw) != digest:
        raise Refusal("load", "BYTE_PIN_MISMATCH")
    return _stage("load", lambda: _json(raw))


def load(path, digest):
    manifest = _read(path, digest)
    _shape(
        manifest,
        {"schema", "scope", "family", "method", "files", "analysis"},
        "manifest",
    )
    if manifest["schema"] != SCHEMA or manifest["scope"] not in (
        "PUBLIC_DEVELOPMENT",
        "SYNTHETIC_FIXTURE",
    ):
        raise Refusal("manifest", "PUBLIC_DEVELOPMENT_ONLY")
    _shape(manifest["files"], ROLES, "manifest")
    documents, pins = {}, {"manifest": digest}
    base = path.parent.resolve()
    for role in sorted(ROLES):
        descriptor = manifest["files"][role]
        if descriptor is None:
            if role not in ("rule", "comparator"):
                raise Refusal("load", "MISSING_" + role.upper())
            documents[role] = None
            continue
        _shape(descriptor, {"path", "sha256"}, "load")
        relative = descriptor["path"]
        if (
            not isinstance(relative, str)
            or not re.fullmatch(r"[A-Za-z0-9_./-]+", relative)
            or ".." in relative.split("/")
            or Path(relative).is_absolute()
        ):
            raise Refusal("load", "LOCAL_RELATIVE_PATH_REQUIRED")
        target = base / relative
        if not target.resolve().is_relative_to(base) or any(
            p.is_symlink() for p in [target, *target.parents] if p.is_relative_to(base)
        ):
            raise Refusal("load", "PATH_ESCAPE")
        documents[role] = _read(target, descriptor["sha256"])
        pins[role] = descriptor["sha256"]
    return manifest, documents, pins


def _predictions(export, supplied):
    _shape(
        supplied,
        {
            "schema",
            "scope",
            "export_digest",
            "model_id",
            "source_receipt_digest",
            "rows",
        },
        "carbon",
    )
    if (
        supplied["schema"] != PREDICTIONS
        or supplied["scope"] not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
        or supplied["export_digest"] != export["export_digest"]
    ):
        raise Refusal("carbon", "SOURCE_IDENTITY_MISMATCH")
    vb._sha(supplied["source_receipt_digest"], "prediction source receipt")
    if not isinstance(supplied["model_id"], str) or not supplied["model_id"]:
        raise Refusal("carbon", "MODEL_ID_REQUIRED")
    known = {
        (r["band"], r["candidate"], r["condition"]): r
        for r in cb._physical_rows(export)
    }
    out, seen = {}, set()
    for row in supplied["rows"]:
        _shape(row, {"band", "candidate", "condition", "values"}, "carbon")
        key = (row["band"], row["candidate"], row["condition"])
        if key not in known or key in seen:
            raise Refusal("carbon", "UNKNOWN_OR_DUPLICATE_PREDICTION")
        seen.add(key)
        if row["values"] is None:  # explicit abstention, never repaired
            continue
        if type(row["values"]) is not dict or set(row["values"]) != set(
            known[key]["values"]
        ):
            raise Refusal("carbon", "OBSERVABLE_INVENTORY_MISMATCH")
        if any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in row["values"].values()
        ):
            raise Refusal("carbon", "FINITE_OBSERVABLES_REQUIRED")
        out[key] = row["values"]
    if len(supplied["rows"]) != len(known):
        raise Refusal("carbon", "INCOMPLETE_PREDICTION_INVENTORY")
    return out


def _baseline(export, material, method):
    family = export["family"]
    if family == "battery-v3" and method in ("protocol", "band"):
        predicted, envelopes, cost = cb.battery_predictions(export, holdout=method)
        return predicted, envelopes, cost
    if family == "motor" and method in ("gaussian", "multiquadric"):
        if material is None:
            raise Refusal("comparator", "MISSING_GEOMETRY_AND_SIGNED_CURVES")
        predicted, cost = cb.motor_predictions(export, material, kernel=method)
        return predicted, None, cost
    if family == "f02" and method == "impulse-response":
        if material is None:
            raise Refusal("comparator", "MISSING_COMPARATOR_MATERIALS")
        if export["questions"][0]["task"]["schema"] == tasks.INDEXED_SCHEMA:
            _shape(
                material, {"schema", "scope", "export_digest", "indices"}, "comparator"
            )
            if (
                material["schema"] != INDEXED_F02
                or material["export_digest"] != export["export_digest"]
                or material["scope"] not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE")
            ):
                raise Refusal("comparator", "INDEXED_SOURCE_IDENTITY_MISMATCH")
            predicted, costs, seen = {}, {}, set()
            expected = {
                r["index_value"] for r in export["questions"][0]["task"]["indices"]
            }
            for row in material["indices"]:
                _shape(row, {"index_value", "materials"}, "comparator")
                if row["materials"].get("scope") != material["scope"]:
                    raise Refusal("comparator", "FIXTURE_SCOPE_MISMATCH")
                value = row["index_value"]
                if value in seen or value not in expected:
                    raise Refusal("comparator", "INDEX_INVENTORY_MISMATCH")
                seen.add(value)
                view = f02_view(export, value)
                verified = pb.validate_materials(view, row["materials"])
                predictions, cost = pb._predict(view, verified)
                predicted.update(
                    {(value, c, cond): v for (_, c, cond), v in predictions.items()}
                )
                costs[str(value)] = cost
            if seen != expected:
                raise Refusal("comparator", "INDEX_INVENTORY_MISMATCH")
            return (
                predicted,
                None,
                {
                    "per_index": costs,
                    "fold_unit": "whole_action_waveform_per_registered_context",
                },
            )
        verified = pb.validate_materials(export, material)
        predicted, cost = pb._predict(export, verified)
        return predicted, None, cost
    raise Refusal("comparator", "UNREGISTERED_METHOD")


def f02_view(export, index_value):
    """Identity-bound plain view for #994; no change to the indexed buyer job."""
    body = {k: copy.deepcopy(v) for k, v in export.items() if k != "export_digest"}
    for entry in body["questions"]:
        matches = [
            (i, r)
            for i, r in enumerate(entry["task"]["indices"])
            if r["index_value"] == index_value
        ]
        if len(matches) != 1:
            raise Refusal("comparator", "INDEX_INVENTORY_MISMATCH")
        i, row = matches[0]
        entry["task"] = row["task"]
        entry["reference"] = next(
            r["panel"] for r in entry["reference"] if r["index_value"] == index_value
        )
        if "settled" in entry:
            entry["settled"] = entry["settled"][i]["verdicts"]
    return producer_panels.seal_export(body)


def _assess(entry, predicted, *, envelopes=None, reference=False):
    rows = {}
    for i, (band, task, panel) in enumerate(cb._panels(entry)):
        values = {}
        for c in task["candidates"]:
            for cond in task["conditions"]:
                key = (band, c, cond["id"])
                if reference:
                    values[(c, cond["id"])] = next(
                        r["values"]
                        for r in panel
                        if r["candidate"] == c and r["condition"] == cond["id"]
                    )
                elif key in predicted:
                    if envelopes is None:
                        values[(c, cond["id"])] = predicted[key]
                    elif key in envelopes:
                        try:
                            values[(c, cond["id"])] = cb.conservative_values(
                                task, envelopes[key]
                            )
                        except cb.Unsupported:
                            pass
        if reference and "settled" in entry:
            verdicts = (
                entry["settled"] if band is None else entry["settled"][i]["verdicts"]
            )
            assessed = reference_resolution.assessed(task, values, verdicts)
        else:
            assessed = tasks.assess(task, values, reference=reference)
        rows["plain" if band is None else str(band)] = (task, assessed)
    return rows


def _order(assessed, task):
    registered = {c: i for i, c in enumerate(task["candidates"])}

    def key(c):
        row = assessed[c]
        if row["feasible"] is None or row["objective"] is None:
            return 2, 0, 0, registered[c]
        return (
            0 if row["feasible"] else 1,
            row["objective"] * (1 if task["objective"]["sense"] == "min" else -1),
            (
                0
                if task["secondary"] is None
                else row["secondary"]
                * (1 if task["secondary"]["sense"] == "min" else -1)
            ),
            registered[c],
        )

    return sorted(assessed, key=key)


def _screen(export, predicted, envelopes, material_digest, cost):
    rankings = []
    for entry in export["questions"]:
        bands = _assess(entry, predicted, envelopes=envelopes)
        objective = entry["task"].get(
            "objective", entry["task"]["identity"].get("objective")
        )
        rankings.append(
            {
                "case": entry["case"],
                "task_digest": entry["task"]["task_digest"],
                "objective": objective,
                "per_index": {
                    b: {"candidate_order": _order(a, t), "assessment": a}
                    for b, (t, a) in bands.items()
                },
            }
        )
    return {
        "schema": vb.SCREEN_SCHEMA,
        "export_digest": export["export_digest"],
        "materials_digest": material_digest,
        "candidate_rankings": rankings,
        "query_cost": cost,
        "tail_rule": "unpredicted_or_abstained_last_in_registered_order",
        "status": "DESCRIPTIVE_HELD_OUT_NOT_EQUAL_BUDGET_RUN",
    }


def _reference(parts, choices, weights):
    if type(choices) is not dict or set(choices) != set(parts):
        raise Refusal("replay", "INCOMPLETE_INDEX_MAP")
    result = {}
    for band, (task, assessed) in parts.items():
        if choices.get(band) not in assessed:
            raise Refusal("replay", "UNKNOWN_BOUND_ACTION")
        row = assessed[choices[band]]
        status = (
            "UNRESOLVED"
            if row["feasible"] is None
            else "FEASIBLE" if row["feasible"] else "INFEASIBLE"
        )
        result[band] = {
            "status": status,
            "value": row["objective"] if status == "FEASIBLE" else None,
        }
    if weights is None:
        return result["plain"]
    states = {r["status"] for r in result.values()}
    status = (
        "INFEASIBLE"
        if "INFEASIBLE" in states
        else "UNRESOLVED" if "UNRESOLVED" in states else "FEASIBLE"
    )
    return {
        "status": status,
        "value": (
            sum(weights[b] * r["value"] for b, r in result.items())
            if status == "FEASIBLE"
            else None
        ),
        "per_index": result,
    }


def _verify_replay(export, replay, binding, baseline, carbon, envelopes):
    eb._validate(replay)
    _shape(binding, {"schema", "export_digest", "jobs"}, "replay")
    if (
        binding["schema"] != BINDINGS
        or binding["export_digest"] != export["export_digest"]
        or replay["source_digest"] != export["export_digest"]
        or replay["challenge"] != export["family"]
    ):
        raise Refusal("replay", "SOURCE_IDENTITY_MISMATCH")
    entries = {r["case"]: r for r in export["questions"]}
    bound, cases = {}, set()
    for row in binding["jobs"]:
        _shape(row, {"job_id", "case", "candidates"}, "replay")
        if row["job_id"] in bound or row["case"] not in entries or row["case"] in cases:
            raise Refusal("replay", "UNKNOWN_OR_DUPLICATE_JOB")
        cases.add(row["case"])
        bound[row["job_id"]] = row
    if set(bound) != {r["job_id"] for r in replay["jobs"]} or {
        r["case"] for r in bound.values()
    } != set(entries):
        raise Refusal("replay", "QUESTION_INVENTORY_MISMATCH")
    for job in replay["jobs"]:
        row = bound[job["job_id"]]
        entry = entries[row["case"]]
        if job["cluster_id"] != entry["support_case"]:
            raise Refusal("replay", "CLUSTER_PROVENANCE_MISMATCH")
        parts = _assess(entry, {}, reference=True)
        weights = None
        if export["family"] == "battery-v3":
            weights = {
                str(r["index_value"]): r["buyer_weight"]
                for r in entry["task"]["indices"]
            }
            if (
                set(weights) != {"5", "15", "25", "35", "40"}
                or weights != replay["objective"]["index_weights"]
            ):
                raise Refusal("replay", "BUYER_WEIGHT_MISMATCH")
        elif set(parts) != {"plain"}:
            if export["family"] != "f02":
                raise Refusal("replay", "UNSUPPORTED_INDEXED_FAMILY")
            weights = {
                str(r["index_value"]): r["buyer_weight"]
                for r in entry["task"]["indices"]
            }
        definition = next(iter(parts.values()))[0]["objective"]
        if (definition["unit"], definition["sense"]) != (
            replay["objective"]["unit"],
            replay["objective"]["direction"],
        ):
            raise Refusal("replay", "OBJECTIVE_MISMATCH")
        if type(row["candidates"]) is not dict or set(row["candidates"]) != {
            r["design_id"] for r in job["candidates"]
        }:
            raise Refusal("replay", "ACTION_INVENTORY_MISMATCH")
        signatures = [tasks.digest(v) for v in row["candidates"].values()]
        if len(set(signatures)) != len(signatures):
            raise Refusal("replay", "DUPLICATE_BOUND_ACTION")
        if weights is None and sorted(
            v.get("plain") for v in row["candidates"].values()
        ) != sorted(parts["plain"][0]["candidates"]):
            raise Refusal("replay", "ACTION_INVENTORY_MISMATCH")
        truth = {}
        for candidate in job["candidates"]:
            identity = candidate["design_id"]
            actual = _reference(parts, row["candidates"][identity], weights)
            if export["family"] != "battery-v3":
                actual = {k: v for k, v in actual.items() if k != "per_index"}
            if candidate["reference"] != actual:
                raise Refusal("replay", "REFERENCE_VALUE_MISMATCH")
            truth[identity] = actual
        if any(r["status"] == "UNRESOLVED" for r in truth.values()):
            raise Refusal("replay", "UNSETTLED_REFERENCE")
        for arm, predictions, env in (
            ("baseline", baseline, envelopes),
            ("model", carbon, None),
        ):
            assessed = _assess(entry, predictions, envelopes=env)
            order = {c["design_id"]: i for i, c in enumerate(job["candidates"])}

            def ranking_key(
                c,
                row=row,
                assessed=assessed,
                weights=weights,
                parts=parts,
                definition=definition,
            ):
                choices = row["candidates"][c]
                rows = [a[choices[b]] for b, (_, a) in assessed.items()]
                tie = tuple(
                    t["candidates"].index(choices[b]) for b, (t, _) in assessed.items()
                )
                if any(r["feasible"] is None or r["objective"] is None for r in rows):
                    return 2, 0, 0, tie
                objective = sum(
                    (1 if weights is None else weights[b]) * a[choices[b]]["objective"]
                    for b, (_, a) in assessed.items()
                )
                secondary = (
                    0
                    if weights is not None or parts["plain"][0]["secondary"] is None
                    else rows[0]["secondary"]
                    * (1 if parts["plain"][0]["secondary"]["sense"] == "min" else -1)
                )
                return (
                    0 if all(r["feasible"] for r in rows) else 1,
                    objective * (1 if definition["sense"] == "min" else -1),
                    secondary,
                    tie,
                )

            expected = sorted(order, key=ranking_key)
            supplied = sorted(
                order,
                key=lambda c: next(
                    r["screen_rank"][arm]
                    for r in job["candidates"]
                    if r["design_id"] == c
                ),
            )
            if supplied != expected:
                raise Refusal("replay", "SCREEN_ORDER_MISMATCH")


def _context_provenance(context, export):
    """Check observable custody contradictions even without an owner value rule."""
    by_case = {r["case"]: r["support_case"] for r in export["questions"]}
    folds = context["folds"]
    if folds is not None:
        _shape(folds, {"schema", "export_digest", "folds"}, "value")
        if type(folds["folds"]) is not list:
            raise Refusal("value", "FOLD_INVENTORY_REQUIRED")
        seen, banks, identities, sources = set(), set(), set(), set()
        for fold in folds["folds"]:
            _shape(fold, {"fold_id", "source_digest", "questions"}, "value")
            vb._sha(fold["source_digest"], "fold source")
            if (
                not isinstance(fold["fold_id"], str)
                or not fold["fold_id"]
                or type(fold["questions"]) is not list
            ):
                raise Refusal("value", "FOLD_INVENTORY_REQUIRED")
            if fold["fold_id"] in identities or fold["source_digest"] in sources:
                raise Refusal("value", "DUPLICATE_FOLD_IDENTITY")
            identities.add(fold["fold_id"])
            sources.add(fold["source_digest"])
            current = set()
            for case in fold["questions"]:
                if case not in by_case or case in seen:
                    raise Refusal("value", "UNKNOWN_OR_DUPLICATE_FOLD_QUESTION")
                seen.add(case)
                current.add(by_case[case])
            if banks & current:
                raise Refusal("value", "FOLDS_SHARE_REFERENCE_SUPPORT")
            banks.update(current)
    speed = context["speed"]
    if speed is not None:
        _shape(
            speed,
            {"schema", "export_digest", "status", "query_unit", "route", "pairs"},
            "value",
        )
        if (
            speed["query_unit"] != "full_registered_decision_query"
            or not isinstance(speed["route"], str)
            or not speed["route"]
            or type(speed["pairs"]) is not list
        ):
            raise Refusal("value", "FULL_DECISION_COST_RECEIPT_REQUIRED")
        seen = set()
        for pair in speed["pairs"]:
            _shape(pair, {"query", "reference_wall_s", "carbon_wall_s"}, "value")
            if pair["query"] not in by_case or pair["query"] in seen:
                raise Refusal("value", "UNKNOWN_OR_DUPLICATE_SPEED_QUESTION")
            seen.add(pair["query"])
            for field in ("reference_wall_s", "carbon_wall_s"):
                vb._number(pair[field], field, positive=True)


def run(manifest, documents, pins):
    family = manifest["family"]
    if family not in ALIASES:
        raise Refusal("replay", "FAMILY_ROUTE_NOT_IMPLEMENTED_BY_OPTIMIZER")
    export = documents["export"]
    _stage("export", lambda: producer_panels.adapt_export(export))
    if export["family"] != family:
        raise Refusal("export", "FAMILY_MISMATCH")
    if (
        len(export["questions"]) > 256
        or len(cb._physical_rows(export)) > 4096
        or any(
            len(t["candidates"]) > 512
            for e in export["questions"]
            for _, t, _ in cb._panels(e)
        )
    ):
        raise Refusal("export", "RESOURCE_LIMIT")
    if documents["carbon"].get("scope") != manifest["scope"] or (
        manifest["scope"] == "PUBLIC_DEVELOPMENT"
        and (documents["comparator"] or {}).get("scope") == "SYNTHETIC_FIXTURE"
    ):
        raise Refusal("manifest", "FIXTURE_SCOPE_MISMATCH")
    if any(r["refinement_demand"] and "settled" not in r for r in export["questions"]):
        raise Refusal("export", "REFINED_TRUTH_REQUIRED")
    carbon = _stage("carbon", lambda: _predictions(export, documents["carbon"]))
    predicted, envelopes, costs = _stage(
        "comparator",
        lambda: _baseline(export, documents["comparator"], manifest["method"]),
    )
    screen = _stage(
        "comparator",
        lambda: _screen(
            export, predicted, envelopes, pins.get("comparator", pins["export"]), costs
        ),
    )
    baseline_report = {
        "schema": vb.BASELINE_SCHEMA,
        "family": family,
        "material": "DEVELOPMENT",
        "export_digest": export["export_digest"],
        "method": manifest["method"],
        "held_out": {
            "pointwise": cb.pointwise_errors(export, predicted),
            "decision": cb.decision_report(export, predicted, envelopes=envelopes),
        },
        "equal_budget_screening": screen,
        "costs": costs,
        "other_costs": "NOT_MEASURED_BY_COMPARATOR",
    }
    carbon_report = {
        "schema": vb.CARBON_SCHEMA,
        "challenge": family,
        "model_id": documents["carbon"]["model_id"],
        "export_digest": export["export_digest"],
        "decisions": cb.decision_report(export, carbon)["decisions"],
        "pointwise": cb.pointwise_errors(export, carbon),
    }
    _stage(
        "replay",
        lambda: _verify_replay(
            export,
            documents["replay"],
            documents["bindings"],
            predicted,
            carbon,
            envelopes,
        ),
    )
    analysis = manifest["analysis"]
    _shape(analysis, {"bootstrap_replicates", "confidence", "seed"}, "analysis")
    if (
        type(analysis["bootstrap_replicates"]) is not int
        or analysis["bootstrap_replicates"] > 10000
        or len(documents["replay"]["budgets"]) > 32
        or len(documents["replay"]["jobs"]) > 256
        or any(len(j["candidates"]) > 512 for j in documents["replay"]["jobs"])
    ):
        raise Refusal("analysis", "RESOURCE_LIMIT")
    replay = _stage("replay", lambda: eb.compare(documents["replay"], **analysis))
    context = documents["context"]
    _shape(
        context,
        {"schema", "export_digest", "selection", "folds", "speed", "item_1", "item_4"},
        "value",
    )
    if (
        context["schema"] != CONTEXT
        or context["export_digest"] != export["export_digest"]
        or context["selection"]["carbon_model_id"] != carbon_report["model_id"]
        or context["selection"]["baseline_id"] != family
    ):
        raise Refusal("value", "SELECTION_IDENTITY_MISMATCH")
    for field, schema in (("folds", vb.FOLDS_SCHEMA), ("speed", vb.SPEED_SCHEMA)):
        value = context[field]
        if value is not None and (
            value.get("schema") != schema
            or value.get("export_digest") != export["export_digest"]
        ):
            raise Refusal("value", "CONTEXT_IDENTITY_MISMATCH")
    _stage("value", lambda: _context_provenance(context, export))
    if (
        documents["replay"]["cost_basis"] != "MEASURED"
        and manifest["scope"] != "SYNTHETIC_FIXTURE"
    ):
        raise Refusal("replay", "MEASURED_COSTS_REQUIRED")
    evidence = vb.seal(
        {
            "schema": vb.EVIDENCE_SCHEMA,
            "scope": "DEVELOPMENT",
            "challenge": family,
            "export_digest": export["export_digest"],
            "selection": context["selection"],
            "baseline_report": baseline_report,
            "carbon_report": carbon_report,
            "equal_budget": replay,
            **{k: context[k] for k in ("folds", "speed", "item_1", "item_4")},
        }
    )
    report = _stage(
        "value",
        lambda: vb.evaluate(
            evidence,
            documents["rule"],
            bootstrap_replicates=analysis["bootstrap_replicates"],
            seed=analysis["seed"],
        ),
    )
    if manifest["scope"] == "SYNTHETIC_FIXTURE":
        report["fixture_only"] = True
    return {
        "baseline.json": baseline_report,
        "carbon.json": carbon_report,
        "screening.json": screen,
        "equal-budget.json": replay,
        "value-evidence.json": evidence,
        "value-report.json": report,
    }


def page(outputs, family):
    # Static known repository script, never a caller-supplied executable path.
    path = ROOT / "scripts/dev/onboarding/build_pack.py"
    spec = importlib.util.spec_from_file_location("evidence_pack_renderer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ledger = module.ledger_module.build(ALIASES[family])
    ledger = copy.deepcopy(ledger)
    report = outputs["value-report.json"]
    for i, key in enumerate(module.CONDITIONS, 1):
        item = report["items"][str(i)]
        if item["status"] != vb.INSUFFICIENT:
            ledger["outputs"]["passes_value"][key] = module.ledger_module.measured(
                item, "value-report.json"
            )
    ledger["outputs"]["model_accuracy"] = module.ledger_module.measured(
        outputs["carbon.json"]["pointwise"], "carbon.json"
    )
    ledger["outputs"]["decision_quality_vs_cheap_baseline"] = (
        module.ledger_module.measured(
            {
                "baseline": outputs["baseline.json"]["held_out"]["decision"]["summary"],
                "comparison": report["items"]["2"],
            },
            "baseline.json; value-report.json",
        )
    )
    text = module.challenge_page(ledger) + "\n" + vb.evidence_page(report)
    text += "\n## Pipeline evidence basis\n\n"
    text += f"Held-out decision questions checked: {outputs['baseline.json']['held_out']['decision']['questions']}. Input and output bytes and executed code are pinned in `receipt.json`. Raw reports remain local; this command publishes nothing.\n"
    if report.get("fixture_only"):
        text = "> SYNTHETIC FIXTURE — NOT ACQUIRED CHALLENGE EVIDENCE.\n\n" + text
    return ledger, text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", choices=sorted(producer_panels.FAMILIES))
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    wall, cpu = time.perf_counter(), time.process_time()
    try:
        if str(args.output_dir).startswith(("\\\\", "//")):
            raise Refusal("output", "REMOTE_PATH_REFUSED")
        if args.output_dir.exists():
            raise Refusal("output", "OUTPUT_ALREADY_EXISTS")
        manifest, documents, pins = load(args.manifest, args.manifest_sha256)
        if manifest["family"] != args.family:
            raise Refusal("manifest", "CLI_FAMILY_MISMATCH")
        outputs = _stage("pipeline", lambda: run(manifest, documents, pins))
        ledger, text = _stage("page", lambda: page(outputs, args.family))
        outputs["ledger.json"] = ledger
        code = [
            Path(m.__file__)
            for name, m in tuple(sys.modules.items())
            if (
                name.startswith(
                    ("carbon.design_search.", "carbon.development_comparison.")
                )
            )
            and getattr(m, "__file__", None)
        ]
        code += [Path(__file__)]
        code += [
            ROOT / "scripts/dev/onboarding" / name
            for name in ("build_pack.py", "build_ledger.py")
        ]
        receipt = {
            "schema": SCHEMA + ".receipt",
            "status": "COMPLETED_DEVELOPMENT_ANALYSIS",
            "scope": manifest["scope"],
            "family": args.family,
            "input_byte_pins": pins,
            "export_digest": outputs["value-report.json"]["export_digest"],
            "code_byte_pins": {
                p.relative_to(ROOT).as_posix(): _sha(p.read_bytes()) for p in code
            },
            "python": platform.python_version(),
            "numerical_packages": {
                name: importlib.metadata.version(name) for name in ("numpy", "scipy")
            },
            "platform": platform.platform(),
            "pipeline_wall_s": time.perf_counter() - wall,
            "pipeline_cpu_s": time.process_time() - cpu,
            "timing_scope": "load_validate_compare_replay_evaluate_render_excludes_artifact_writes",
            "cost_exclusions": [
                "original_acquisition",
                "reference_refinement",
                "retained_verification",
                "Carbon_training_rebuild",
                "money_and_licences",
            ],
            "canonical": False,
            "reference_solves": 0,
            "qualifies_challenge": False,
            "publishes_page": False,
            "value_status": outputs["value-report.json"]["status"],
        }
        payloads = {
            name: json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
            for name, value in outputs.items()
        }
        payloads["evidence.md"] = text
        receipt["output_byte_pins"] = {
            name: _sha(value.encode("utf-8")) for name, value in payloads.items()
        }
        args.output_dir.mkdir(parents=False, exist_ok=False)
        for name, payload in payloads.items():
            with (args.output_dir / name).open(
                "x", encoding="utf-8", newline="\n"
            ) as stream:
                stream.write(payload)
        with (args.output_dir / "receipt.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "value_status": receipt["value_status"],
                    "scope": manifest["scope"],
                }
            )
        )
        return 0
    except Refusal as error:
        print(
            json.dumps(
                {"status": "REFUSED", "stage": error.stage, "reason": error.code}
            )
        )
        return 2
    except (OSError, UnicodeError):
        print(
            json.dumps(
                {
                    "status": "REFUSED",
                    "stage": "io",
                    "reason": "LOCAL_IO_UNAVAILABLE_NO_COMPLETION_RECEIPT",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
