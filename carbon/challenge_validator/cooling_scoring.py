"""Cooling construction scoring on Carbon's pods (CHALLENGE-AI-COOLING-07).

This adapter reuses the existing public cold-plate DEVELOPMENT practice rule
without changing its cases, gates, components, scales or aggregate.  The
baseline comparison is descriptive only: the public cases are shared and
adaptively visible, and no scientific promotion or uncertainty rule is
registered for Cooling.
"""

from __future__ import annotations

from pathlib import Path
from statistics import fmean

from .scoring import ChallengeScoring, PracticeRule, clean

BUILT_SCHEMA = "carbon.graphite.pod-built.v1"


def _rows_by_case(rows):
    return {
        row["case_id"]: row
        for row in rows
        if row.get("case_id") is not None and row.get("error") is not None
    }


def _paired_difference(baseline_rows, rows, *, important=None):
    baseline = _rows_by_case(baseline_rows)
    candidate = _rows_by_case(rows)
    common = sorted(set(baseline) & set(candidate))
    if important is not None:
        common = [case for case in common if bool(candidate[case].get("important"))]
    if not common:
        return {"n": 0, "mean_delta": None}
    return {
        "n": len(common),
        "mean_delta": fmean(
            candidate[case]["error"] - baseline[case]["error"] for case in common
        ),
    }


class CoolingPracticeRule(PracticeRule):
    """The existing cold-plate rule on public PRACTICE, plus a deliberately
    non-promoting descriptive baseline comparison."""

    def __init__(self, root):
        from carbon.cold_plate.challenge import PublicMaterial
        from carbon.cold_plate.practice import PracticeSet

        self.root = Path(root)
        self.practice = PracticeSet.load(root)
        self.material = PublicMaterial.load(root)
        self.identity = {
            "rule": "cold-plate-public-practice-v1",
            "authority": "OWNER-CHALLENGE-DESIGN-01",
            "status": "PROVISIONAL_DEVELOPMENT_NON_QUALIFYING",
            "score": "mean TRAIN-normalized peak, profile and pressure error",
            "comparison": {
                "kind": "DESCRIPTIVE_PAIRED_MEAN_DIFFERENCE",
                "confidence_interval": None,
                "promotable": False,
                "reason": "no approved cooling promotion or sampling rule",
            },
            "cases": "public PRACTICE, 100, fixed and adaptively seen",
        }

    def score(self, predictions):
        from carbon.cold_plate.practice import score_practice

        asked = {case: predictions.get(case) for case in self.practice.case_ids}
        rows, summary = score_practice(asked, self.practice, self.material)
        return [clean(row) for row in rows], clean(summary)

    def compare(self, baseline_rows, rows, eligible):
        overall = _paired_difference(baseline_rows, rows)
        important = _paired_difference(baseline_rows, rows, important=True)
        if not eligible:
            outcome = "REGRESSION"
            reason = "the candidate failed the existing public-practice rule"
        elif overall["n"] == 0:
            outcome = "INSUFFICIENT_EVIDENCE"
            reason = "no common scorable public-practice cases"
        elif overall["mean_delta"] < 0:
            outcome = "IMPROVEMENT"
            reason = "lower mean error on the shared public cases"
        elif overall["mean_delta"] > 0:
            outcome = "REGRESSION"
            reason = "higher mean error on the shared public cases"
        else:
            outcome = "NO_IMPROVEMENT"
            reason = "equal mean error on the shared public cases"
        return clean(
            {
                "outcome": outcome,
                "reason": reason + "; no approved promotion rule",
                "interpretation": "DESCRIPTIVE_PAIRED_MEAN_DIFFERENCE",
                "promotable": False,
                "n": overall["n"],
                "mean_delta": overall["mean_delta"],
                "ci": None,
                "overall": overall,
                "important": important,
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
