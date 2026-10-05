"""Battery's construction scoring on Carbon's pods (VALIDATOR-01 slice 2).

The battery-specific parts of Graphite's pod scoring, moved here unchanged:
- `built_record` (from `graphite/pod_phase.py`): the compiled recipe, the staged
  files of a practice trial and the fixed GPU practice program, by digest;
- `BatteryPracticeRule` (from `graphite/experiment.py`'s `FrozenRule`): the
  battery exam's gates, frozen calibration and score on the public PRACTICE
  references (`carbon.battery.practice.score_practice`), and rule v2's frozen
  paired comparison (`carbon.battery.exam.final_compare`);
- the public material a pod reads (from `graphite/pods.py`'s `DATA_PATHS`):
  TRAIN v1, the OCV table and the public PRACTICE records;
- the session's baseline, battery's research scaffold.

Nothing here changes what battery builds, ships or scores.
"""

from __future__ import annotations

from pathlib import Path

from .scoring import ChallengeScoring, PracticeRule, clean

BUILT_SCHEMA = "carbon.graphite.pod-built.v1"
EVIDENCE = "docs/development/evidence/exam-design-2026-09-24"


class BatteryPracticeRule(PracticeRule):
    """The battery exam's frozen gates, calibration, score and comparison, on
    the public PRACTICE references (development feedback only)."""

    def __init__(self, root):
        from carbon.battery import exam
        from carbon.battery.challenge import PublicMaterial
        from carbon.battery.practice import PracticeSet

        self.root = Path(root)
        self.practice = PracticeSet.load(root)
        self.material = PublicMaterial.load(root)
        rule = exam.RULES["v2"]
        self.comparison = exam.ComparisonRule(
            equivalence_margin=rule["equivalence_margin_rel"], **rule["comparison"]
        )
        self.identity = {
            "rule": "v2",
            "authority": rule["authority"],
            "status": rule["status"],
            "equivalence_margin_rel": rule["equivalence_margin_rel"],
            "comparison": rule["comparison"],
            "cases": "public PRACTICE, 200, adaptively seen",
        }

    def score(self, predictions):
        from carbon.battery.practice import score_practice

        asked = {case: predictions.get(case) for case in self.practice.case_ids}
        rows, summary = score_practice(asked, self.practice, self.material, self.root)
        return [_row(r) for r in rows], clean(summary)

    def compare(self, baseline_rows, rows, eligible):
        from carbon.battery import exam

        def errors(source):
            return {
                r["case_id"]: r["error"] for r in source if r.get("error") is not None
            }

        def components(source):
            return {
                r["case_id"]: r["components"]
                for r in source
                if r.get("components") is not None
            }

        important = {r["case_id"]: bool(r.get("important")) for r in rows}
        result = exam.final_compare(
            errors(baseline_rows),
            errors(rows),
            important,
            self.comparison,
            chal_eligible=eligible,
            inc_components=components(baseline_rows),
            chal_components=components(rows),
        )
        return clean(result)


def _row(row):
    keep = ("case_id", "state", "error", "components", "important", "gates")
    return clean({k: row[k] for k in keep if k in row})


class BatteryScoring(ChallengeScoring):
    """The battery DEVELOPMENT Challenge's construction scoring."""

    served_backends = ("jax",)
    data_paths = (
        EVIDENCE + "/datasets/train-v1.jsonl.gz",
        EVIDENCE + "/ocv_table.json",
        EVIDENCE + "/refs-a-part2/out/records.jsonl",
    )
    wrong_challenge_code = "not_the_battery_development_challenge"
    construction_objective = (
        "Propose battery TrainingStrategy recipes that beat the baseline under "
        "Carbon's frozen rule on public PRACTICE. Carbon runs, scores and "
        "rebuilds each proposal; you see development feedback only."
    )

    def __init__(self):
        from carbon.battery.challenge import CHALLENGE

        self.challenge_id = CHALLENGE.challenge_id
        self.challenge_version = CHALLENGE.version

    def built_record(self, strategy, contract_digest, seed, root):
        from carbon.battery.practice import PracticeSet, staged_files
        from carbon.development_session.battery_gpu import GPU_PROGRAM
        from carbon.development_session.profile import digest
        from carbon.reconstruction.challenge_contracts import compile_submission

        admitted = compile_submission(strategy, contract_digest=contract_digest)
        recipe = admitted.construction
        plan = admitted.compiled.construction_plan
        files = staged_files(root, PracticeSet.load(root), recipe, seed)
        record = {
            "schema": BUILT_SCHEMA,
            "challenge": recipe.document()["challenge"],
            "contract_digest": admitted.contract_digest,
            "recipe": recipe.document(),
            "recipe_digest": recipe.recipe_digest,
            "strategy_hash": plan.strategy_hash.value,
            "plan_digest": plan.to_ref().content_digest,
            "staged": {name: digest(body) for name, body in sorted(files.items())},
            "program": digest(GPU_PROGRAM.encode()),
            "seed": seed,
        }
        return record, files, GPU_PROGRAM

    def refusal(self, error):
        from carbon.development_session.research_catalog import RecipeRejected
        from carbon.reconstruction.challenge_contracts import SubmissionRefused

        if isinstance(error, SubmissionRefused):
            return "contract_refused", [(i.code, i.path) for i in error.issues]
        if isinstance(error, RecipeRejected):
            return "recipe_rejected", [(i.code, i.path) for i in error.rejected.issues]
        return None

    def backend(self, record):
        return record["recipe"]["settings"].get("backend", "jax")

    def frozen_rule(self, root):
        return BatteryPracticeRule(root)

    def baseline_strategy(self):
        from carbon.battery.research import SCAFFOLD

        return SCAFFOLD

    def fixture_variant_strategy(self):
        import copy

        strategy = copy.deepcopy(self.baseline_strategy())
        strategy["parameters"]["width"] = 128
        return strategy

    def fixture_refused_strategy(self):
        return {**self.baseline_strategy(), "backbone": "transolver"}

    def synthetic_predictions(self, quality, root):
        import math

        from carbon.battery.practice import PracticeSet

        predictions = {}
        for index, ref in enumerate(PracticeSet.load(root).records):
            wave = 1.0 + 0.5 * math.sin(index * 0.7)
            out = ref["outputs"]
            predictions[ref["case_id"]] = {
                "voltage_v": out["voltage_v"],
                "temperature_c": [out["temperature_c"][0]]
                + [t + quality * 0.5 * wave for t in out["temperature_c"][1:]],
                "plating_margin_v": out["plating_margin_v"] + quality * 0.002 * wave,
                "capacity_ah": out["capacity_ah"],
            }
        return predictions


__all__ = ["BUILT_SCHEMA", "BatteryPracticeRule", "BatteryScoring"]
