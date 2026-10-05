"""Cooling construction scoring on Carbon's pods (CHALLENGE-AI-COOLING-07).

This adapter reuses the existing public cold-plate DEVELOPMENT practice rule
without changing its cases, gates, components, scales or aggregate. The
Graphite-wave paired comparison is a testing-only policy on adaptively seen
public cases, not an official or fresh-case scientific promotion rule.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .scoring import COVERAGE_RULE, ChallengeScoring, PracticeRule, clean, cover

BUILT_SCHEMA = "carbon.graphite.pod-built.v1"
COMPARISON_VERSION = "cooling-graphite-practice-comparison-v1"
MARGIN_RECORD = "docs/development/evidence/cold-plate-equivalence-margin-v1/result.json"
MARGIN_SHA256 = "a559dc0e624892811c64c45a3e57c91ee9d43e3574eda4cecb093515274d603c"
N_MIN, N_BOOT, ALPHA, IMPORTANT_MIN = 30, 4000, 0.05, 10
BOOTSTRAP_SEED = 20261005
DISPOSITIONS = {
    "IMPROVEMENT": "ACCEPTED_DEVELOPMENT_IMPROVEMENT",
    "REGRESSION": "DEVELOPMENT_REGRESSION",
    "TRADE_OFF": "DEVELOPMENT_TRADEOFF",
    "NO_IMPROVEMENT": "DEVELOPMENT_EQUIVALENT",
    "INSUFFICIENT_EVIDENCE": "INDETERMINATE_REPLICA_OR_EFFECT_RESOLUTION",
}


def _registered_margin():
    """Fail closed if the Test Lead's committed testing evidence changed."""
    path = Path(__file__).resolve().parents[2] / MARGIN_RECORD
    body = path.read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(body).hexdigest() != MARGIN_SHA256:
        raise ValueError("cooling comparison margin record digest mismatch")
    record = json.loads(body)
    if (
        record.get("schema") != "carbon.cold-plate.practice-equivalence-margin.v1"
        or record.get("chosen_from")
        != "bootstrap (max of bootstrap and stochastic-recipe values; no stochastic family)"
        or record.get("equivalence_margin_rel") != 0.13157222884271824
    ):
        raise ValueError("cooling comparison margin record is not registered")
    return record["equivalence_margin_rel"]


def _classify(deltas, incumbent_mean, margin, rng):
    draws = rng.choice(deltas, size=(N_BOOT, len(deltas)), replace=True).mean(axis=1)
    lo, hi = (float(v) for v in np.quantile(draws, [ALPHA / 2, 1 - ALPHA / 2]))
    mean = float(np.mean(deltas))
    width = margin * incumbent_mean
    if hi < 0 and mean < -width:
        return "better", [lo, hi]
    if lo > 0 and mean > width:
        return "worse", [lo, hi]
    if lo >= -width and hi <= width:
        return "equivalent", [lo, hi]
    return "unresolved", [lo, hi]


def _scorable(row, important):
    if row.get("state") != "SCORABLE" or row.get("important") is not important:
        return False
    values = [row.get("error")]
    components = row.get("components")
    if not isinstance(components, dict) or set(components) != {
        "peak",
        "profile",
        "pressure",
    }:
        return False
    values.extend(components.values())
    return all(type(value) in (int, float) and math.isfinite(value) for value in values)


class CoolingPracticeRule(PracticeRule):
    """The existing rule plus the registered Graphite-wave practice comparison."""

    def __init__(self, root):
        from carbon.cold_plate.challenge import PublicMaterial
        from carbon.cold_plate.practice import PracticeSet

        self.root = Path(root)
        self.practice = PracticeSet.load(root)
        self.material = PublicMaterial.load(root)
        self.margin = _registered_margin()
        self.identity = {
            "rule": "cold-plate-public-practice-v2",
            "authority": "OWNER-CHALLENGE-DESIGN-01; OWNER-GRAPHITE-TEST-WAVE-06 section 1",
            "status": "GRAPHITE_WAVE_TESTING_ONLY_NON_QUALIFYING",
            "score": "mean TRAIN-normalized peak, profile and pressure error",
            "comparison": {
                "kind": COMPARISON_VERSION,
                "margin_rel": self.margin,
                "margin_evidence": {
                    "path": MARGIN_RECORD,
                    "sha256": "sha256:" + MARGIN_SHA256,
                },
                "n_min": N_MIN,
                "n_boot": N_BOOT,
                "alpha": ALPHA,
                "important_min": IMPORTANT_MIN,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "scope": "fixed_adaptively_seen_public_practice_graphite_testing_only",
                "fresh_confirmation": False,
            },
            "cases": "public PRACTICE, 100, fixed and adaptively seen",
            "coverage": COVERAGE_RULE,
        }

    def score(self, predictions):
        from carbon.cold_plate.practice import score_practice

        asked, missing = cover(predictions, self.practice.case_ids)
        rows, summary = score_practice(asked, self.practice, self.material)
        return [clean(row) for row in rows], {
            **clean(summary),
            "n_missing": len(missing),
        }

    def compare(self, baseline_rows, rows, eligible):
        from carbon.cold_plate import exam

        def has_state(source, state):
            return isinstance(source, (list, tuple)) and any(
                isinstance(row, dict) and row.get("state") == state for row in source
            )

        expected = {
            record["case_id"]: exam.important(record)
            for record in self.practice.records
        }
        base = {
            "interpretation": "PAIRED_BOOTSTRAP_FIXED_PUBLIC_PRACTICE_TESTING_ONLY",
            "comparison_version": COMPARISON_VERSION,
            "promotable": False,
            "registered_cases": len(expected),
            "n": 0,
            "mean_delta": None,
            "ci": None,
            "overall": None,
            "important": None,
            "known_gate_failure": has_state(rows, "GATE_FAILED"),
            "reference_available": all(
                record.get("status") == "OK" for record in self.practice.records
            )
            and not has_state(baseline_rows, "REFERENCE_INVALID")
            and not has_state(rows, "REFERENCE_INVALID"),
            "evidence_complete": False,
        }

        def stop(outcome, reason):
            return {
                **base,
                "outcome": outcome,
                "reason": reason,
                "existing_disposition": DISPOSITIONS[outcome],
            }

        if base["known_gate_failure"]:
            return stop(
                "REGRESSION", "candidate failed a mandatory public-practice gate"
            )
        if not eligible:
            return stop("REGRESSION", "candidate is ineligible under the practice rule")

        def indexed(source):
            if not isinstance(source, (list, tuple)) or len(source) != len(expected):
                return None
            by_case = {}
            for row in source:
                if not isinstance(row, dict):
                    return None
                case = row.get("case_id")
                if case not in expected or case in by_case:
                    return None
                by_case[case] = row
            return by_case if set(by_case) == set(expected) else None

        incumbent, challenger = indexed(baseline_rows), indexed(rows)
        if incumbent is None or challenger is None:
            return stop(
                "INSUFFICIENT_EVIDENCE",
                "registered case set is incomplete or duplicated",
            )
        for case, important in expected.items():
            if not _scorable(incumbent[case], important) or not _scorable(
                challenger[case], important
            ):
                return stop(
                    "INSUFFICIENT_EVIDENCE",
                    "reference or prediction evidence is unavailable",
                )

        ids = sorted(expected)
        if len(ids) < N_MIN:
            return stop("INSUFFICIENT_EVIDENCE", "too few scorable paired cases")
        rng = np.random.default_rng(BOOTSTRAP_SEED)
        delta = np.array([challenger[c]["error"] - incumbent[c]["error"] for c in ids])
        incumbent_mean = float(np.mean([incumbent[c]["error"] for c in ids]))
        overall, ci = _classify(delta, incumbent_mean, self.margin, rng)
        important_ids = [c for c in ids if expected[c]]
        if len(important_ids) >= IMPORTANT_MIN:
            delta_important = np.array(
                [challenger[c]["error"] - incumbent[c]["error"] for c in important_ids]
            )
            important, important_ci = _classify(
                delta_important,
                float(np.mean([incumbent[c]["error"] for c in important_ids])),
                self.margin,
                rng,
            )
        else:
            important, important_ci = "insufficient", None
        components = {}
        for component in exam.COMPONENTS:
            component_delta = np.array(
                [
                    challenger[c]["components"][component]
                    - incumbent[c]["components"][component]
                    for c in ids
                ]
            )
            components[component], _ = _classify(
                component_delta,
                float(np.mean([incumbent[c]["components"][component] for c in ids])),
                self.margin,
                rng,
            )
        if overall == "worse":
            outcome, reason = (
                "REGRESSION",
                "overall error higher beyond the testing margin",
            )
        elif important == "worse" and overall != "better":
            outcome, reason = (
                "REGRESSION",
                "important region worse without overall gain",
            )
        elif overall == "better" and important == "worse":
            outcome, reason = "TRADE_OFF", "overall better but important region worse"
        elif overall == "better" and important == "insufficient":
            outcome, reason = "INSUFFICIENT_EVIDENCE", "too few important-region cases"
        elif overall == "better":
            outcome, reason = (
                "IMPROVEMENT",
                "overall better; important region not worse",
            )
        elif overall == "equivalent" and important == "better":
            outcome, reason = "TRADE_OFF", "overall equivalent; important region better"
        elif (
            overall == "equivalent"
            and "worse" in components.values()
            and "better" in components.values()
        ):
            outcome, reason = (
                "TRADE_OFF",
                "equivalent overall; components move in opposite directions",
            )
        elif overall == "equivalent":
            outcome, reason = "NO_IMPROVEMENT", "within the testing equivalence margin"
        else:
            outcome, reason = (
                "INSUFFICIENT_EVIDENCE",
                "paired interval does not resolve the testing margin",
            )
        return clean(
            {
                **base,
                "outcome": outcome,
                "reason": reason,
                "existing_disposition": DISPOSITIONS[outcome],
                "promotable": outcome == "IMPROVEMENT",
                "n": len(ids),
                "n_important": len(important_ids),
                "mean_delta": float(np.mean(delta)),
                "ci": ci,
                "overall": overall,
                "important": important,
                "important_ci": important_ci,
                "components": components,
                "regional_block": important == "worse",
                "reference_available": True,
                "evidence_complete": True,
            }
        )


class CoolingScoring(ChallengeScoring):
    """The periodic-cell Cooling Challenge's public DEVELOPMENT scoring."""

    served_backends = ("numpy",)
    wrong_challenge_code = "not_the_cold_plate_development_challenge"
    construction_objective = (
        "Propose bounded kernel-ridge recipes that reduce the existing public "
        "cold-plate PRACTICE error while passing its prediction-validity gates. "
        "Carbon runs, scores and rebuilds each proposal; the comparison is "
        "descriptive DEVELOPMENT feedback only."
    )

    def __init__(self):
        from carbon.cold_plate.challenge import (
            CALIBRATION_PATH,
            CHALLENGE,
            PRACTICE_PATH,
            TRAIN_PATH,
        )

        self.challenge_id = CHALLENGE.challenge_id
        self.challenge_version = CHALLENGE.version
        self.data_paths = (TRAIN_PATH, PRACTICE_PATH, CALIBRATION_PATH)

    def built_record(self, strategy, contract_digest, seed, root):
        from carbon.cold_plate.practice import PROGRAM, PracticeSet, staged_files
        from carbon.development_session.profile import digest
        from carbon.reconstruction.challenge_contracts import compile_submission

        admitted = compile_submission(strategy, contract_digest=contract_digest)
        recipe = admitted.construction
        plan = admitted.compiled.construction_plan
        files = staged_files(root, PracticeSet.load(root), recipe)
        record = {
            "schema": BUILT_SCHEMA,
            "challenge": recipe.document()["challenge"],
            "contract_digest": admitted.contract_digest,
            "recipe": recipe.document(),
            "recipe_digest": recipe.recipe_digest,
            "strategy_hash": plan.strategy_hash.value,
            "plan_digest": plan.to_ref().content_digest,
            "staged": {name: digest(body) for name, body in sorted(files.items())},
            "program": digest(PROGRAM.encode()),
            "seed": seed,
        }
        return record, files, PROGRAM

    def refusal(self, error):
        from carbon.development_session.research_catalog import RecipeRejected
        from carbon.reconstruction.challenge_contracts import SubmissionRefused

        if isinstance(error, SubmissionRefused):
            return "contract_refused", [(i.code, i.path) for i in error.issues]
        if isinstance(error, RecipeRejected):
            return "recipe_rejected", [(i.code, i.path) for i in error.rejected.issues]
        return None

    def backend(self, record):
        return "numpy"

    def frozen_rule(self, root):
        return CoolingPracticeRule(root)

    def baseline_strategy(self):
        from carbon.cold_plate.research import SCAFFOLD

        return SCAFFOLD

    def fixture_variant_strategy(self):
        import copy

        strategy = copy.deepcopy(self.baseline_strategy())
        strategy["parameters"]["length"] = "length_4"
        return strategy

    def fixture_refused_strategy(self):
        return {**self.baseline_strategy(), "backbone": "transolver"}

    def synthetic_predictions(self, quality, root):
        import math

        predictions = {}
        for index, ref in enumerate(self.frozen_rule(root).practice.records):
            wave = 1.0 + 0.5 * math.sin(index * 0.7)
            out = ref["outputs"]
            temperature_error = quality * 0.5 * wave
            predictions[ref["case_id"]] = {
                "peak_c": out["peak_c"] + temperature_error,
                "profile_c": [t + temperature_error for t in out["profile_c"]],
                "pressure_drop_pa": out["pressure_drop_pa"]
                * math.exp(quality * 0.02 * wave),
            }
        return predictions


__all__ = ["BUILT_SCHEMA", "CoolingPracticeRule", "CoolingScoring"]
