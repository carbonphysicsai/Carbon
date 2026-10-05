"""Motor public DEVELOPMENT scoring for Graphite Level 0 constructions.

Only the registered public TRAIN and PRACTICE rule are used. This adapter
grants neither private validator access nor scientific qualification.
"""

from __future__ import annotations

from pathlib import Path

from .scoring import ChallengeScoring, PracticeRule, clean, paired_error_difference

BUILT_SCHEMA = "carbon.graphite.pod-built.v1"


class MotorPracticeRule(PracticeRule):
    def __init__(self, root):
        from carbon.motor.challenge import PublicMaterial
        from carbon.motor.practice import PracticeSet

        self.root = Path(root)
        self.practice = PracticeSet.load(root)
        self.material = PublicMaterial.load(root)
        self.identity = {
            "rule": "motor-public-practice-v1",
            "authority": "OWNER-CHALLENGE-DESIGN-01",
            "status": "PROVISIONAL_DEVELOPMENT_NON_QUALIFYING",
            "score": "existing TRAIN-normalized mean-torque and ripple errors",
            "comparison": {
                "kind": "DESCRIPTIVE_PAIRED_MEAN_DIFFERENCE",
                "confidence_interval": None,
                "promotable": False,
                "reason": "no approved motor promotion or sampling rule",
            },
            "cases": "public PRACTICE, 30, fixed and adaptively seen",
        }

    def score(self, predictions):
        from carbon.motor.practice import score_practice

        asked = {case: predictions.get(case) for case in self.practice.case_ids}
        rows, summary = score_practice(asked, self.practice, self.material)
        return [clean(row) for row in rows], clean(summary)

    def compare(self, baseline_rows, rows, eligible):
        overall = paired_error_difference(baseline_rows, rows)
        important = paired_error_difference(baseline_rows, rows, important=True)
        if not eligible:
            outcome, reason = (
                "REGRESSION",
                "the candidate failed the existing public-practice rule",
            )
        elif overall["n"] == 0:
            outcome, reason = (
                "INSUFFICIENT_EVIDENCE",
                "no common scorable public-practice cases",
            )
        elif overall["mean_delta"] < 0:
            outcome, reason = (
                "IMPROVEMENT",
                "lower mean error on the shared public cases",
            )
        elif overall["mean_delta"] > 0:
            outcome, reason = (
                "REGRESSION",
                "higher mean error on the shared public cases",
            )
        else:
            outcome, reason = (
                "NO_IMPROVEMENT",
                "equal mean error on the shared public cases",
            )
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


class MotorScoring(ChallengeScoring):
    served_backends = ("numpy",)
    wrong_challenge_code = "not_the_motor_development_challenge"
    construction_objective = (
        "Propose bounded kernel-ridge recipes that reduce the existing public "
        "motor PRACTICE error while passing its prediction-validity gates. "
        "Carbon runs, scores and rebuilds each proposal; the comparison is "
        "descriptive DEVELOPMENT feedback only."
    )

    def __init__(self):
        from carbon.motor.challenge import (
            CALIBRATION_PATH,
            CHALLENGE,
            PRACTICE_PATH,
            TRAIN_PATH,
        )

        self.challenge_id = CHALLENGE.challenge_id
        self.challenge_version = CHALLENGE.version
        self.data_paths = (TRAIN_PATH, PRACTICE_PATH, CALIBRATION_PATH)

    def built_record(self, strategy, contract_digest, seed, root):
        from carbon.development_session.profile import digest
        from carbon.motor.practice import PROGRAM, PracticeSet, staged_files
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
        return MotorPracticeRule(root)

    def baseline_strategy(self):
        from carbon.motor.research import SCAFFOLD

        return SCAFFOLD

    def fixture_variant_strategy(self):
        import copy

        strategy = copy.deepcopy(self.baseline_strategy())
        strategy["parameters"]["length"] = "length_8"
        return strategy

    def fixture_refused_strategy(self):
        return {**self.baseline_strategy(), "backbone": "transolver"}

    def synthetic_predictions(self, quality, root):
        import math

        predictions = {}
        for index, ref in enumerate(self.frozen_rule(root).practice.records):
            wave = 1.0 + 0.5 * math.sin(index * 0.7)
            predictions[ref["case_id"]] = {
                "torque_nm": [
                    t + quality * 0.05 * wave for t in ref["outputs"]["torque_nm"]
                ]
            }
        return predictions


__all__ = ["BUILT_SCHEMA", "MotorPracticeRule", "MotorScoring"]
