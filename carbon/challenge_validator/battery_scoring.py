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

from .scoring import COVERAGE_RULE, ChallengeScoring, PracticeRule, clean, cover

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
            "coverage": COVERAGE_RULE,
        }

    def score(self, predictions):
        from carbon.battery.practice import score_practice

        # A case without a prediction fails the schema gate (`cover`).
        asked, missing = cover(predictions, self.practice.case_ids)
        rows, summary = score_practice(asked, self.practice, self.material, self.root)
        return [_row(r) for r in rows], {**clean(summary), "n_missing": len(missing)}

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


#: The backends Carbon's pods build, by scoring version (DEVELOPMENT).
#: v1 built JAX only. v2 (TORCH-POD-01) adds PyTorch: the same practice
#: program with PyTorch's runtime record, in the released torch-gpu worker
#: image, its pod build checked against Carbon's rebuild identity. A record
#: made under v1 keeps its meaning: its backend was JAX.
SERVED_BACKENDS = {
    "battery-scoring-v1": ("jax",),
    "battery-scoring-v2-pytorch": ("jax", "pytorch"),
}
SCORING_VERSION = "battery-scoring-v2-pytorch"


class BatteryScoring(ChallengeScoring):
    """The battery DEVELOPMENT Challenge's construction scoring."""

    scoring_version = SCORING_VERSION
    served_backends = SERVED_BACKENDS[SCORING_VERSION]
    #: Development levels 1-3 train with their own JAX programs, so a
    #: development construction is built on JAX only.
    development_backends = ("jax",)
    data_paths = (
        EVIDENCE + "/datasets/train-v1.jsonl.gz",
        EVIDENCE + "/ocv_table.json",
        EVIDENCE + "/refs-a-part2/out/records.jsonl",
    )
    wrong_challenge_code = "not_the_battery_development_challenge"
    #: The score-tuning legs a development score variant may weight: the one
    #: candidate definition, `carbon.battery.value.score_tuning.LEGS`.
    declared_score_components = ("a", "r", "g", "m", "n", "p", "q")
    #: The practice value contract a variant's legs are computed under: EV4's
    #: development decision contract (the Test Lead, #668, 2026-10-05), never
    #: EV5's frozen confirmation or a panel copy. Its digest, which #654's
    #: `load_variant` compares a variant's record with, and its file.
    practice_value_contract = (
        "sha256:fedd753c0e7aa69d2fd4d6efbf3d877ac8eeb211859d9f32d76a61f38bbe38d1"
    )
    practice_value_contract_file = "ev4-charge-protocol-selection.v1.json"
    construction_objective = (
        "Propose battery TrainingStrategy recipes that beat the baseline under "
        "Carbon's frozen rule on public PRACTICE. Carbon runs, scores and "
        "rebuilds each proposal; you see development feedback only."
    )

    def __init__(self):
        from carbon.battery.challenge import CHALLENGE

        self.challenge_id = CHALLENGE.challenge_id
        self.challenge_version = CHALLENGE.version

    def built_record(self, strategy, contract_digest, seed, root, implementation=None):
        """`implementation` names a registered battery implementation
        version: a record made under an earlier version is rebuilt from that
        version's own module bytes (TORCH-GPU-01)."""
        from carbon.reconstruction.challenge_contracts import (
            CompiledSubmission,
            compile_submission,
        )

        admitted = compile_submission(strategy, contract_digest=contract_digest)
        if implementation is not None:
            from carbon.battery.compile import compile_recipe

            compiled, recipe = compile_recipe(strategy, implementation=implementation)
            admitted = CompiledSubmission(
                admitted.challenge, admitted.contract_digest, compiled, recipe
            )
        return self.built_from(admitted, seed, root, implementation=implementation)

    def built_from(self, admitted, seed, root, implementation=None):
        from carbon.battery.practice import PracticeSet, staged_files
        from carbon.development_session.battery_gpu import pod_program
        from carbon.development_session.profile import digest

        recipe = admitted.construction
        plan = admitted.compiled.construction_plan
        # KNN-STATE-GPU-01: a KNN builds with GPU program v2, which stages the
        # versioned state digest; every other recipe keeps v1 byte for byte.
        program, extra = pod_program(
            recipe.family, self.backend({"recipe": recipe.document()})
        )
        base = staged_files(
            root, PracticeSet.load(root), recipe, seed, implementation=implementation
        )
        files = {**base, **extra}
        development = getattr(admitted, "development", None)
        found = None
        if development is not None:
            # A development construction (Graphite only, Levels 1-3) is staged
            # with its record and trained by its level's program.
            from carbon.battery import development_rebuild, level1_worker

            found = development_rebuild.record(
                getattr(admitted, "reconstruction", None)
            )
            program, files, _trainer = development_rebuild.stage(
                found, program, files, level1_program=level1_worker.program
            )
        record = {
            "schema": BUILT_SCHEMA,
            "challenge": recipe.document()["challenge"],
            "contract_digest": admitted.contract_digest,
            "recipe": recipe.document(),
            "recipe_digest": recipe.recipe_digest,
            "strategy_hash": plan.strategy_hash.value,
            "plan_digest": plan.to_ref().content_digest,
            "staged": {name: digest(body) for name, body in sorted(files.items())},
            "program": digest(program.encode()),
            "seed": seed,
        }
        if development is not None:
            # A development construction (Graphite only) carries its variant
            # binding beside the base fields; a Level 0 record never does.
            record["development"] = development
        if found is not None:
            # Until GPU identity is measured (Test Lead Q6), a development
            # rebuild says it is verified on CPU only.
            record["rebuild"] = development_rebuild.rebuild_label(found)
        return record, files, program

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
