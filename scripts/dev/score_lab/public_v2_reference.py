"""Prospective public EV4 admission using the exact registered plating v2.

This adapter never changes the historical reference file. The numerical
plating policy comes solely from the registered reader; other constraints
keep the original EV4 measurement and bands. No model input affects admission.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from carbon.battery.value import contract as ct
from carbon.battery.value import decision as d
from scripts.dev.battery.plating_rereference import V2_RULES, v2_label

from . import bank, owner_dev_v1
from .core import LabRefused, canonical_sha

LABEL_SHA256 = "cac1e23001c227d9221653b2a90cee4755f62ca06fec58305d11cb9cba510069"
VERSION = "battery-plating-ref-v2"
SCHEMA = "carbon.dev.ev4-public-v2-admission.v1"


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def label_index(document, allowed_case_ids):
    """Validate rows and join by source; shared ID prefixes carry no authority."""
    if (
        document.get("schema") != "carbon.battery.plating-v2-labels.v1"
        or document.get("version") != VERSION
        or document.get("decision") != "VALIDATOR-PLATING-REF-V2-02"
        or not isinstance(document.get("rows"), list)
    ):
        raise LabRefused("public_v2_label_contract")
    index, seen, counts = {}, set(), Counter()
    for row in document["rows"]:
        cid = row.get("case_id")
        if type(cid) is not str or cid in seen:
            raise LabRefused("public_v2_duplicate_case")
        seen.add(cid)
        if row.get("source") not in ("ev4", "pdd") or row.get("rule") not in V2_RULES:
            raise LabRefused("public_v2_source_or_rule")
        m20, m160 = row.get("m20_mv"), row.get("m160_mv")
        if not _finite(m20) or (m160 is not None and not _finite(m160)):
            raise LabRefused("public_v2_nonfinite_margin")
        expected = v2_label(m20 / 1000, None if m160 is None else m160 / 1000)
        if expected != {"rule": row["rule"], "label": row.get("label")}:
            raise LabRefused("public_v2_label_mismatch")
        counts[f"{row['source']}:{row['label']}"] += 1
        if row["source"] == "ev4":
            if cid not in allowed_case_ids:
                raise LabRefused("public_v2_ev4_case_not_in_contract")
            index[cid] = row
        elif cid in allowed_case_ids:
            raise LabRefused("public_v2_wrong_source_join")
    return index, dict(sorted(counts.items()))


def load_labels(path, allowed_case_ids):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != LABEL_SHA256:
        raise LabRefused("public_v2_label_digest")
    return label_index(json.loads(raw), allowed_case_ids)


def plating_verdict(cid, margin, labels):
    """Registered v2 outcome or explicit lack of applicability/reference."""
    row = labels.get(cid)
    if row is not None and not math.isclose(
        row["m20_mv"] / 1000, margin, rel_tol=0, abs_tol=1e-12
    ):
        raise LabRefused("public_v2_mesh20_join_mismatch")
    measured = None if row is None or row["m160_mv"] is None else row["m160_mv"] / 1000
    verdict = v2_label(margin, measured)
    if verdict is None:
        return "FAILED_REFERENCE", None, "PLATING_V2_OUTSIDE_CLAIM"
    label, rule = verdict["label"], verdict["rule"]
    if row is not None and verdict != {"label": row["label"], "rule": row["rule"]}:
        raise LabRefused("public_v2_join_verdict_mismatch")
    reason = (
        "PENDING_MESH160"
        if rule == "pending-m160-r1"
        else "SOLVED_IN_BAND" if label == "UNRESOLVED" else None
    )
    return label, rule, reason


def assess_condition(contract, cid, record, labels):
    if record is None or record.get("status") != "OK":
        return {
            "status": "FAILED_REFERENCE",
            "objective": None,
            "reason": "ORIGINAL_REFERENCE_MISSING_OR_FAILED",
            "case_id": cid,
        }
    quantities = d.measure(contract, record["outputs"])
    if any(not _finite(value) for value in quantities.values() if value is not None):
        raise LabRefused("public_v2_reference_nonfinite")
    objective = quantities["time_to_cv_onset_s"]
    if objective is not None and not _finite(objective):
        raise LabRefused("public_v2_reference_nonfinite")
    plate, rule, reason = plating_verdict(cid, quantities["plating_margin_v"], labels)
    checks = d.check(
        contract, quantities, contract["reference"]["uncertainty"]["bands"]
    )
    checks["no_plating_onset"] = {
        "FEASIBLE": d.PASS,
        "INFEASIBLE": d.FAIL,
        "UNRESOLVED": d.UNRESOLVED,
        "FAILED_REFERENCE": "FAILED_REFERENCE",
    }[plate]
    states = set(checks.values())
    status = (
        "INFEASIBLE"
        if d.FAIL in states
        else (
            "FAILED_REFERENCE"
            if "FAILED_REFERENCE" in states
            else "UNRESOLVED" if d.UNRESOLVED in states else "FEASIBLE"
        )
    )
    return {
        "status": status,
        "objective": objective,
        "checks": checks,
        "case_id": cid,
        "reason": reason,
        "plating_reference": {"version": VERSION, "rule": rule, "label": plate},
    }


def _within_envelope(contract, scenario):
    envelope = contract["operating_conditions"]["envelope"]
    return all(
        envelope["t_amb_c"][0] <= t <= envelope["t_amb_c"][1]
        and envelope["soc0"][0] <= soc <= envelope["soc0"][1]
        for t, soc in scenario["conditions"]
    )


def admission(contract, refs, labels, *, label_counts):
    """Return internal bank questions plus a public reference-only receipt."""
    candidates = ct.candidates(contract)
    if len(candidates) != 35 or len({c["id"] for c in candidates}) != 35:
        raise LabRefused("public_v2_full_35_action_grammar")
    expected = {job["case_id"] for job in ct.decision_cases(contract)}
    if set(refs) != expected or set(labels) - expected:
        raise LabRefused("public_v2_reference_coverage")
    questions, rows = {}, []
    handoff = {}
    status_counts, plate_counts = Counter(), Counter()
    for scenario in ct.scenarios(contract):
        qid = scenario["id"]
        q = {
            "question_id": qid,
            "block_id": qid,
            "half": "development",
            "split": scenario["split"],
            "task": "target",
            "weight": 1.0,
            "fallback_action": ct.candidate_id(contract["baseline"]["protocol"]),
            "actions": {},
        }
        reasons, incomplete, unresolved = Counter(), [], []
        for candidate in candidates:
            conditions = []
            for i in range(len(scenario["conditions"])):
                cid = ct.case_id(contract, scenario, candidate, i)
                row = assess_condition(contract, cid, refs[cid], labels)
                conditions.append(row)
                status_counts[row["status"]] += 1
                if row.get("plating_reference"):
                    plate_counts[row["plating_reference"]["label"]] += 1
                reason = row["reason"]
                if reason:
                    reasons[reason] += 1
                if row["status"] == "FAILED_REFERENCE":
                    incomplete.append(cid)
                elif row["status"] == "UNRESOLVED":
                    unresolved.append(cid)
            q["actions"][candidate["id"]] = conditions
        classification, determined = bank.classify(q)
        feasible = [
            max(c["objective"] for c in conditions)
            for conditions in q["actions"].values()
            if all(c["status"] == "FEASIBLE" for c in conditions)
        ]
        best = min(feasible) if feasible else None
        for aid, conditions in q["actions"].items():
            states = {c["status"] for c in conditions}
            blocking_unresolved = (
                "UNRESOLVED" in states
                and "INFEASIBLE" not in states
                and "FAILED_REFERENCE" not in states
                and (
                    aid == q["fallback_action"]
                    or best is None
                    or max(c["objective"] for c in conditions) < best
                )
            )
            for condition in conditions:
                if condition["reason"] and (
                    condition["status"] == "FAILED_REFERENCE"
                    or (blocking_unresolved and condition["status"] == "UNRESOLVED")
                ):
                    handoff.setdefault(condition["reason"], []).append(
                        condition["case_id"]
                    )
        if not _within_envelope(contract, scenario):
            classification, determined = "INCOMPLETE", False
            reasons["QUESTION_OUTSIDE_DECLARED_ENVELOPE"] = 1
            handoff.setdefault("QUESTION_OUTSIDE_DECLARED_ENVELOPE", []).append(qid)
        q["class"] = classification
        questions[qid] = q
        rows.append(
            {
                "question_id": qid,
                "split": scenario["split"],
                "class": classification,
                "decision_determined": determined,
                "actions": len(q["actions"]),
                "condition_count": len(scenario["conditions"]),
                "reason_counts": dict(sorted(reasons.items())),
                "failed_reference_cases": len(incomplete),
                "unresolved_cases": len(unresolved),
            }
        )
    masks = {
        split: [
            row["question_id"]
            for row in rows
            if row["split"] == split and row["class"] == "SCORED"
        ]
        for split in ("development", "verification")
    }
    return questions, {
        "schema": SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "reference_version": VERSION,
        "label_sha256": LABEL_SHA256,
        "label_source_counts": label_counts,
        "full_grammar_actions": 35,
        "pruned_actions": 0,
        "class_counts": dict(sorted(Counter(row["class"] for row in rows).items())),
        "condition_status_counts": dict(sorted(status_counts.items())),
        "plating_status_counts": dict(sorted(plate_counts.items())),
        "questions": rows,
        "common_mask_by_split": masks,
        "common_mask_sha256": canonical_sha(masks),
        "admission_records_sha256": canonical_sha(questions),
        "public_missing_case_handoff": {
            key: sorted(values) for key, values in sorted(handoff.items())
        },
        "status": (
            "ADMITTED_PUBLIC_QUESTIONS"
            if any(masks.values())
            else "INSUFFICIENT_EVIDENCE"
        ),
        "reason": (
            None if any(masks.values()) else "NO_V2_ADMISSIBLE_FULL_GRAMMAR_QUESTIONS"
        ),
    }


def covered_admission(contract, refs, labels, *, label_counts):
    """Owner 2026-10-15 D3; preserve the historical admission above.

    Require applicability and settled plating for EVERY registered condition,
    even if that action cannot win or fails another gate. No action is pruned.
    The common scored mask also retains the existing other-constraint and
    fallback checks. A completed new label export must be bound upstream to
    its actual digest; this function never authenticates a caller's receipt.
    """
    questions, legacy = admission(contract, refs, labels, label_counts=label_counts)
    manifests, rows = {}, {}
    for scenario in ct.scenarios(contract):
        qid = scenario["id"]
        manifests[qid] = []
        for candidate in ct.candidates(contract):
            for i in range(len(scenario["conditions"])):
                cid = ct.case_id(contract, scenario, candidate, i)
                manifests[qid].append(cid)
                record = refs.get(cid)
                if record is None or record.get("status") != "OK":
                    continue
                margin = d.measure(contract, record["outputs"])["plating_margin_v"]
                if not _finite(margin):
                    continue
                row = {"m20_mv": margin * 1000, "sealed_v2": labels.get(cid)}
                if cid not in labels and abs(margin) < 0.015:
                    # Outside the refinement window the exact sealed reader
                    # can decide from m20 alone; pending remains UNRESOLVED.
                    row["sealed_v2"] = {
                        "case_id": cid,
                        "source": "ev4",
                        "m20_mv": margin * 1000,
                        "m160_mv": None,
                        **v2_label(margin),
                    }
                rows[cid] = row
    coverage = owner_dev_v1.covered_questions(manifests, rows)
    covered = set(coverage["common_questions"])
    for qid, question in questions.items():
        if qid not in covered:
            question["class"] = "INCOMPLETE"
        for conditions in question["actions"].values():
            for condition in conditions:
                cid = condition["case_id"]
                if cid in coverage["excluded_questions"].get(qid, {}):
                    condition["status"] = "UNRESOLVED"
                    condition["reason"] = coverage["excluded_questions"][qid][cid]
    masks = {
        split: [q for q in ids if q in covered]
        for split, ids in legacy["common_mask_by_split"].items()
    }
    return questions, {
        "first_line": owner_dev_v1.ESTIMAND,
        "schema": "carbon.scorelab.public-ev4-covered-v2-admission.v1",
        "scope": "PUBLIC_DEVELOPMENT",
        "status": (
            "ADMITTED_PUBLIC_QUESTIONS"
            if any(masks.values())
            else "INSUFFICIENT_EVIDENCE"
        ),
        "reference_coverage": coverage,
        "common_mask_by_split": masks,
        "common_mask_sha256": canonical_sha(masks),
        "admission_records_sha256": canonical_sha(questions),
        "full_grammar_actions": legacy["full_grammar_actions"],
        "pruned_actions": 0,
        "legacy_admission": legacy,
        "qualification": False,
    }
