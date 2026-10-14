"""Prospective, digest-bound public EV4 v2 replay; no fitting or solver calls.

Run as a standalone module to keep ownership disjoint from open campaign CLI
work. All utility inputs are explicit diagnostic assumptions. The historical
score reference and prospective decision reference are reported separately.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import random
import statistics
from pathlib import Path

import numpy as np

from carbon.battery import exam
from carbon.battery.calibration import SHAPES, frozen_calibration
from carbon.battery.challenge import PublicMaterial
from carbon.battery.value import contract as ct
from carbon.battery.value import decision as d
from carbon.battery.value import panel as battery_panel
from carbon.battery.value import score_proof
from carbon.battery.value import score_tuning as st

from . import bank, public_ev4, public_physics
from . import public_v2_reference as v2
from .core import LabRefused, canonical_sha

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = "carbon.dev.ev4-public-v2-replay.v2"
MANIFEST = "docs/development/evidence/ev4-dev-tuning-v1/predictions.sha256"
MANIFEST_SHA = "b1811937663d1c38d220122335cb5e159c899f6966ac430088ccdaf4c40857cd"
CHEAP_SOURCES = {
    "Business/research/value-metric-audit/res07-analyze.py.txt": "e91f89f9cae53cd7b5e1f252910f197f8a0334adbf47e2bb492d7601dffa91ff",
    "Business/research/value-metric-v2-rev2-curves/analyze.py": "6b047b27c18baf865bfb86e2ea0706ae2b394e5b9a1072c7d5355ab211b08df1",
    "Business/research/battery-advantage-families/analyze.py": "8dfa5204709e40f6fdd34f996b5e6e2ae074e0c0306d8ca14f639ceb153482de",
}
PRIMARY_CHEAP = "bilinear_trace_D"
CHEAP_METHODS = (PRIMARY_CHEAP, "bilinear_scalar_D", "nearest_scalar_D")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_references(public_dir, contract):
    raw = (Path(public_dir) / "ev4-decision-references.jsonl").read_bytes()
    if sha(raw) != public_ev4.PUBLIC_REFERENCE_SHA256:
        raise LabRefused("public_v2_original_reference_digest")
    allowed = {job["case_id"] for job in ct.decision_cases(contract)}
    refs = {}
    for line in raw.splitlines():
        row = json.loads(line)
        if row["case_id"] not in allowed or row.get("refined"):
            continue
        if row["case_id"] in refs:
            raise LabRefused("public_v2_duplicate_original_reference")
        refs[row["case_id"]] = row
    if set(refs) != allowed:
        raise LabRefused("public_v2_original_reference_coverage")
    return refs


def inventory(public_dir):
    """Verify the complete public bundle manifest without parsing model outputs."""
    raw = (ROOT / MANIFEST).read_bytes().replace(b"\r\n", b"\n")
    if sha(raw) != MANIFEST_SHA:
        raise LabRefused("public_v2_bundle_manifest_digest")
    files, pins = {}, {}
    for line in raw.decode("utf-8").splitlines():
        digest, filename = line.split()
        if Path(filename).name != filename or not filename.endswith(".json.gz"):
            raise LabRefused("public_v2_bundle_path")
        name = filename.removesuffix(".json.gz")
        if name in files:
            raise LabRefused("public_v2_duplicate_bundle_member")
        paths = [
            Path(public_dir) / folder / filename
            for folder in (
                "experiment-predictions",
                "proof-predictions",
                "attack-predictions",
            )
        ]
        matching = [p for p in paths if p.is_file() and sha(p.read_bytes()) == digest]
        if not matching:
            raise LabRefused("public_v2_missing_or_changed_bundle")
        files[name], pins[name] = matching[0], digest
    if len(files) != 137 or len(set(pins.values())) != 137:
        raise LabRefused("public_v2_bundle_cohort")
    return files, pins


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cheap_predictions(contract, refs):
    """Reuse fixed research maps; only D records enter the calibration namespace."""
    source = {}
    for relative, digest in CHEAP_SOURCES.items():
        raw = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
        if sha(raw) != digest:
            raise LabRefused("public_v2_cheap_source_changed")
        source[relative] = raw
    scalar = _module(
        ROOT / "Business/research/value-metric-v2-rev2-curves/analyze.py",
        "v2_scalar_map",
    )
    trace = _module(
        ROOT / "Business/research/battery-advantage-families/analyze.py", "v2_trace_map"
    )
    candidates = ct.candidates(contract)
    index, train = {}, {}
    for scenario in ct.scenarios(contract, "development"):
        for candidate in candidates:
            for i, (t, soc) in enumerate(scenario["conditions"]):
                cid = ct.case_id(contract, scenario, candidate, i)
                index[candidate["c1"], candidate["c2"], float(t), float(soc)] = cid
                train[cid] = refs[cid]
    namespace = {
        "CAND": candidates,
        "CON": contract,
        "decision": d,
        "REFS": train,
        "REF_INDEX": index,
        "SOURCE_RAW": source[
            "Business/research/value-metric-audit/res07-analyze.py.txt"
        ],
    }
    result = {name: {} for name in CHEAP_METHODS}
    for scenario in ct.scenarios(contract):
        qid = scenario["id"]
        for name, method in (
            ("bilinear_scalar_D", "bilinear_D_clamped"),
            ("nearest_scalar_D", "nearest_D"),
        ):
            result[name][qid] = scalar.map_assessments(namespace, scenario, method)
        quantities = trace.trace_map(namespace, scenario)
        complete = [
            c
            for c in candidates
            if all(
                quantities[c["id"], i] is not None
                for i in range(len(scenario["conditions"]))
            )
        ]
        assessed = d.assess_predicted(
            contract,
            scenario,
            complete,
            {key: value for key, value in quantities.items() if value is not None},
        )
        result[PRIMARY_CHEAP][qid] = {
            c["id"]: {
                "feasible": assessed.get(c["id"], {}).get("feasible", False),
                "objective": assessed.get(c["id"], {}).get("objective"),
            }
            for c in candidates
        }
    return result, {
        "primary": PRIMARY_CHEAP,
        "methods": list(CHEAP_METHODS),
        "sources_sha256": CHEAP_SOURCES,
        "calibration_split": "development_only",
        "calibration_case_ids_sha256": canonical_sha(sorted(train)),
        "calibration_cases": len(train),
        "verification_response_training": False,
        "reference_version_for_training": "ORIGINAL_EV4_NUMERICAL_OUTPUTS",
        "frozen_before_this_replay": True,
        "limits": "historically inspected public comparison; GP/RBF/adaptive arms and matched acquisition cost absent; no strongest-industry or qualification claim",
    }


def model_predictions(contract, predictions):
    """Measure each complete full-grammar prediction; no partial question masks."""
    candidates = ct.candidates(contract)
    result = {}
    for scenario in ct.scenarios(contract):
        measured = {}
        for candidate in candidates:
            for i in range(len(scenario["conditions"])):
                cid = ct.case_id(contract, scenario, candidate, i)
                raw = predictions.get(cid)
                if raw is None:
                    result[scenario["id"]] = None
                    break
                try:
                    values = d.measure(contract, raw)
                    if any(
                        type(v) not in (int, float) or not math.isfinite(v)
                        for v in values.values()
                        if v is not None
                    ):
                        raise ValueError("nonfinite")
                    measured[candidate["id"], i] = values
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    result[scenario["id"]] = None
                    break
            if scenario["id"] in result:
                break
        else:
            assessed = d.assess_predicted(contract, scenario, candidates, measured)
            result[scenario["id"]] = {
                aid: {"feasible": row["feasible"], "objective": row["objective"]}
                for aid, row in assessed.items()
            }
    return result


def outcomes(questions, predictions, mask, *, cap, kappa, unit):
    if any(predictions.get(qid) is None for qid in mask):
        return None
    result = {
        qid: bank._v2_question(
            questions[qid],
            predictions[qid],
            cap=cap,
            kappa=kappa,
            unit=unit,
            detail=True,
        )
        for qid in mask
    }
    for qid, row in result.items():
        actions = questions[qid]["actions"]
        base = max(c["objective"] for c in actions[questions[qid]["fallback_action"]])
        best = min(
            max(c["objective"] for c in conditions)
            for conditions in actions.values()
            if all(c["status"] == "FEASIBLE" for c in conditions)
        )
        row["ceiling_gain"] = max(0.0, (base - best) / unit)
        row["missed_opportunity_gain"] = max(0.0, row["ceiling_gain"] - row["G"])
    return result


def paired_margin(model, cheap, questions, *, replicates, seed, level):
    """Paired block resampling on the same reference-only mask; no model fitting."""
    if model is None or cheap is None:
        return {"status": "UNMEASURED_MISSING_PREDICTIONS"}
    ids = sorted(model)
    if set(ids) != set(cheap):
        raise LabRefused("public_v2_pair_mask_mismatch")
    if not ids:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "NO_ADMITTED_QUESTIONS",
            "questions": 0,
        }
    groups = {}
    for qid in ids:
        groups.setdefault(questions[qid]["block_id"], []).append(qid)
    delta = {qid: model[qid]["U"] - cheap[qid]["U"] for qid in ids}
    rng, keys = random.Random(seed), sorted(groups)
    values = (
        [
            statistics.fmean(
                delta[qid]
                for key in (rng.choice(keys) for _ in keys)
                for qid in groups[key]
            )
            for _ in range(replicates)
        ]
        if len(keys) >= 2
        else []
    )
    return {
        "status": "MEASURED_PUBLIC_DIAGNOSTIC",
        "questions": len(ids),
        "blocks": len(keys),
        "common_mask_sha256": canonical_sha(ids),
        "mean_net_margin": statistics.fmean(delta.values()),
        "paired_ci": score_proof._interval(values, level) if values else None,
        "ci_level": level,
        "bootstrap_replicates": replicates,
        "ci_limitation": None if values else "FEWER_THAN_TWO_BLOCKS",
        "infeasible_attempt_question_share": sum(
            row["infeasible_attempts"] > 0 for row in model.values()
        )
        / len(ids),
        "unresolved_attempt_question_share": sum(
            row["unresolved_attempts"] > 0 for row in model.values()
        )
        / len(ids),
        "abstention_question_share": sum(row["n"] == 0 for row in model.values())
        / len(ids),
        "mean_missed_opportunity_gain": statistics.fmean(
            row["missed_opportunity_gain"] for row in model.values()
        ),
        "missed_opportunity_question_share": sum(
            row["missed_opportunity_gain"] > 0 for row in model.values()
        )
        / len(ids),
        "reference_acquisition_cost_matched": False,
        "conditional_on": "fixed D map calibration and common public references; no independent confirmation",
    }


def _legacy_store(contract, refs):
    ids = sorted(
        job["case_id"]
        for job in ct.decision_cases(contract, "development")
        if refs[job["case_id"]]["status"] == "OK"
    )
    material = PublicMaterial.load(ROOT)
    ocv = {
        cid: float(
            np.interp(refs[cid]["inputs"]["soc0"], material.ocv_soc, material.ocv_v)
        )
        for cid in ids
    }
    tol, scales = frozen_calibration(ROOT)
    return exam.CaseStore(refs, ocv, tol, scales, SHAPES, {}), ids


def _gate_evidence(candidate, rows, members):
    """Separate measured failures from unknown measures and operational refusal."""
    statuses = {m: [] for m in members}
    measurements, missing_measures, missing_members = [], set(), set()
    for gate in candidate.gates:
        verdicts = {}
        for member in members:
            value = rows[member]["gates"].get(gate["measure"])
            if type(value) not in (int, float) or not math.isfinite(value):
                verdicts[member] = "UNKNOWN"
                missing_measures.add(gate["measure"])
                missing_members.add(member)
            else:
                verdicts[member] = st.one_gate_verdict(gate, rows[member])
            statuses[member].append(verdicts[member])
        measurements.append(
            {
                **gate,
                "measured_members": sum(v != "UNKNOWN" for v in verdicts.values()),
                "unmeasured_members": sum(v == "UNKNOWN" for v in verdicts.values()),
                "measured_failures": sum(v == "FAIL" for v in verdicts.values()),
                "measured_passes": sum(v == "PASS" for v in verdicts.values()),
            }
        )
    return {
        "legacy_gate_failures": sum("FAIL" in values for values in statuses.values()),
        "legacy_gate_unknown_members": sum(
            "UNKNOWN" in values and "FAIL" not in values for values in statuses.values()
        ),
        "missing_required_gate_members": len(missing_members),
        "missing_required_gate_measures": sorted(missing_measures),
        "gate_measurements": measurements,
        "gate_measurement_status": (
            "UNMEASURED"
            if missing_members
            else "MEASURED" if candidate.gates else "NOT_APPLICABLE"
        ),
    }


def legacy_report(rows, utilities, members, recipe_of, *, replicates, seed, level):
    """Exact registered legacy scorer; missing Q3/VERIFY inputs never supplied."""
    results = {}
    for version in (5, 9, 10):
        path = (
            ROOT
            / f"docs/development/evidence/battery-score-tuning/registry-v{version}.json"
        )
        candidates, identity = st.load_registry(path)
        for cid, candidate in candidates.items():
            scores, verdicts = st.candidate_scores(
                candidate, {m: rows[m] for m in members}, recipe_of
            )
            gate_evidence = _gate_evidence(candidate, rows, members)
            missing = [m for m in members if scores[m] is None]
            missing_legs = sorted(
                {
                    leg
                    for leg, weight in candidate.weights.items()
                    if weight > 0
                    and any(rows[m]["legs"].get(leg) is None for m in members)
                }
            )
            report = {
                "registry_sha256": identity["sha256"],
                "registered_candidate": cid,
                "score_reference": "ORIGINAL_EV4_AND_FROZEN_CALIBRATION",
                "value_reference": v2.VERSION,
                "members": len(members),
                "missing_score_members": len(missing),
                "missing_required_legs": missing_legs,
                **gate_evidence,
                "operational_fail_closed_verdicts": sum(
                    v == "FAIL" for v in verdicts.values()
                ),
                "gate_basis": "legacy reference; not prospective v2 eligibility",
                "full_v3_measured": False,
                "Q3": "UNMEASURED_NO_PUBLIC_Q3_JOB",
            }
            if (
                missing
                or missing_legs
                or gate_evidence["missing_required_gate_members"]
            ):
                report["status"] = "UNMEASURED_INCOMPLETE_RULE_INPUTS"
            elif not utilities or any(
                utilities.get(m) is None or not utilities[m] for m in members
            ):
                report["status"] = "UNMEASURED_NO_COMMON_V2_VALUE"
            else:
                losses = {
                    m: [-row["U"] for row in utilities[m].values()] for m in members
                }
                means = {m: statistics.fmean(losses[m]) for m in members}
                report.update(
                    status="MEASURED_PUBLIC_DIAGNOSTIC",
                    tau=score_proof._tau(scores, means, members),
                    bootstrap=score_proof.bootstrap(
                        scores,
                        {},
                        losses,
                        recipe_of,
                        members,
                        n=replicates,
                        seed=seed,
                        level=level,
                    ),
                )
            results[f"v{version}:{cid}"] = report
    return results


def run(public_dir, plt_readings, *, cap, kappa, unit, replicates, seed, level):
    if (
        type(cap) is not int
        or not 1 <= cap <= 35
        or type(replicates) is not int
        or replicates < 1
        or type(seed) is not int
        or seed < 0
    ):
        raise LabRefused("public_v2_diagnostic_inputs")
    if (
        any(
            type(x) not in (int, float) or not math.isfinite(x) or x <= 0
            for x in (kappa, unit, level)
        )
        or level >= 1
    ):
        raise LabRefused("public_v2_diagnostic_inputs")
    implementation = {
        relative: sha((ROOT / relative).read_bytes().replace(b"\r\n", b"\n"))
        for relative in (
            "scripts/dev/score_lab/public_v2_reference.py",
            "scripts/dev/score_lab/public_v2_replay.py",
            "scripts/dev/score_lab/bank.py",
            "scripts/dev/battery/plating_rereference.py",
            "carbon/battery/value/decision.py",
            "carbon/battery/value/score_tuning.py",
            "carbon/battery/value/score_proof.py",
            "carbon/battery/value/panel.py",
        )
    }
    contract, digest = ct.load(
        ROOT / "carbon/battery/value/contracts/ev4-dev-proof-v1.json"
    )
    refs = read_references(public_dir, contract)
    labels, counts = v2.load_labels(
        ROOT
        / "docs/development/evidence/plating-rereference-01/d3-results/labels-v2-r1.json",
        set(refs),
    )
    questions, admission = v2.admission(contract, refs, labels, label_counts=counts)
    admission["input_identity"] = {
        "contract_digest": digest,
        "original_reference_sha256": public_ev4.PUBLIC_REFERENCE_SHA256,
        "v2_label_sha256": v2.LABEL_SHA256,
        "implementation_sha256": implementation,
    }
    files, pins = inventory(public_dir)
    traits = public_physics.load_traits(
        plt_readings,
        ROOT
        / "docs/development/evidence/physics-consistency-gates-01/measurements.json",
    )
    control_names = {f"control-{kind}" for kind in battery_panel.CONTROLS}
    if set(files) | control_names != set(traits["members"]):
        raise LabRefused("public_v2_traits_cohort_mismatch")
    primary_source = ROOT / "Business/research/value-metric-v2-stress/results.json"
    primary = json.loads(primary_source.read_bytes())["real_members"]
    if len(primary) != 100 or not set(primary) <= set(files):
        raise LabRefused("public_v2_primary_cohort")
    cheap, cheap_receipt = cheap_predictions(contract, refs)
    masks = admission["common_mask_by_split"]
    cheap_values = {
        split: {
            name: outcomes(questions, predicted, mask, cap=cap, kappa=kappa, unit=unit)
            for name, predicted in cheap.items()
        }
        for split, mask in masks.items()
    }
    store, score_ids = _legacy_store(contract, refs)
    rows, values, recipe_of = {}, {split: {} for split in masks}, {}
    member_reports = {}
    inputs = [(name, files[name], None) for name in sorted(files)] + [
        (f"control-{kind}", None, kind) for kind in battery_panel.CONTROLS
    ]
    for name, path, kind in inputs:
        if path:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                bundle = json.load(handle)
            if bundle.get("member") != name:
                raise LabRefused("public_v2_bundle_member_mismatch")
            predictions = bundle["predictions"]
        else:
            predictions = battery_panel.control_predictions(kind, refs)
        recipe_of[name] = name.rsplit("-s", 1)[0]
        rows[name] = st.member_legs(contract, predictions, store, score_ids)
        if rows[name]["legs"]["q"] is not None:
            raise LabRefused("public_v2_unexpected_q3_input")
        predicted = model_predictions(contract, predictions)
        member_reports[name] = {
            "kind": "PUBLIC_RAW_MEMBER" if path else "PUBLIC_SYNTHETIC_CONTROL",
            "split": {},
        }
        for split, mask in masks.items():
            value = outcomes(
                questions, predicted, mask, cap=cap, kappa=kappa, unit=unit
            )
            values[split][name] = value
            member_reports[name]["split"][split] = {
                cheap_name: paired_margin(
                    value,
                    cheap_value,
                    questions,
                    replicates=replicates,
                    seed=seed,
                    level=level,
                )
                for cheap_name, cheap_value in cheap_values[split].items()
            }
    legs = {}
    for leg in st.SCORE_LEGS:
        measured = [
            row["legs"].get(leg)
            for row in rows.values()
            if row["legs"].get(leg) is not None
        ]
        legs[leg] = {
            "measured_members": len(measured),
            "unmeasured_members": len(rows) - len(measured),
            "range": [min(measured), max(measured)] if measured else None,
        }
    return admission, {
        "schema": SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "status": (
            "PUBLIC_REPLAY_DIAGNOSTIC"
            if any(masks.values())
            else "INSUFFICIENT_EVIDENCE"
        ),
        "reason": None if any(masks.values()) else admission["reason"],
        "identity": {
            "implementation_sha256": implementation,
            "contract_digest": digest,
            "original_reference_sha256": public_ev4.PUBLIC_REFERENCE_SHA256,
            "v2_labels_sha256": v2.LABEL_SHA256,
            "prediction_manifest_sha256": MANIFEST_SHA,
            "bundle_sha256": pins,
            "trait_sources_sha256": traits["source_sha256"],
            "definition_sha256": sha(
                (
                    ROOT / "docs/development/value-metric-v2/definition.v2.json"
                ).read_bytes()
            ),
            "primary_cohort_sha256": sha(primary_source.read_bytes()),
            "common_mask_sha256": admission["common_mask_sha256"],
        },
        "diagnostic_inputs_ASSUMPTION": {
            "cap": cap,
            "kappa": kappa,
            "unit_seconds": unit,
            "replicates": replicates,
            "seed": seed,
            "ci_level": level,
        },
        "coverage": {
            "raw_bundles": len(files),
            "constructed_controls": len(control_names),
            "physics_members": len(traits["members"]),
            "primary_ev4_models": len(primary),
            "original_scoring_cases": len(score_ids),
        },
        "comparator": cheap_receipt,
        "population_proposal_weights": {
            "P": "UNREGISTERED_FOR_A_PROSPECTIVE_PROOF_BANK",
            "Q": "original fixed public EV4 D/V scenario grid, bound by contract digest",
            "w": "uniform per-question diagnostic inside each common split mask",
            "weights_sha256": canonical_sha(
                {split: {qid: 1.0 for qid in mask} for split, mask in masks.items()}
            ),
        },
        "common_mask_by_split": masks,
        "legacy_leg_availability": legs,
        "member_comparisons": member_reports,
        "legacy_rules": {
            split: legacy_report(
                rows,
                values[split],
                primary,
                recipe_of,
                replicates=replicates,
                seed=seed,
                level=level,
            )
            for split in masks
        },
        "realism_fitting": "NOT_RUN; public trait coverage only",
        "rule_selection": "NOT_RUN",
        "final_confirmation": "NOT_RUN; holdout unopened",
        "limitations": [
            "historical public EV4 CV-onset proxy, not battery-v3 charging-time job",
            "reference applicability/missing evidence is never a miner penalty",
            "Q3 and full v3 unmeasured",
            "shared D calibration and old public model construction cost are not matched",
            "no independent future-batch or VALUE-BAR claim",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-dir", type=Path, required=True)
    parser.add_argument("--plt-readings", type=Path, required=True)
    parser.add_argument("--cap", type=int, required=True)
    parser.add_argument("--kappa", type=float, required=True)
    parser.add_argument("--unit-seconds", type=float, required=True)
    parser.add_argument("--bootstrap", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--ci-level", type=float, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        raise LabRefused("public_v2_output_already_exists")
    admission, replay = run(
        args.public_dir,
        args.plt_readings,
        cap=args.cap,
        kappa=args.kappa,
        unit=args.unit_seconds,
        replicates=args.bootstrap,
        seed=args.seed,
        level=args.ci_level,
    )
    args.out.mkdir(parents=True)
    for name, data in (("admission.json", admission), ("replay.json", replay)):
        (args.out / name).write_bytes(
            (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
                "utf-8"
            )
        )
    print(
        json.dumps(
            {
                "status": replay["status"],
                "common_mask_by_split": admission["common_mask_by_split"],
                "coverage": replay["coverage"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
