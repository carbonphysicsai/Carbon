"""Public motor practice in the pinned isolated CPU worker.

The worker receives the compiled recipe, exact public TRAIN bytes and public
PRACTICE inputs.  Labels stay on the trusted host, which applies the existing
exam gates and aggregate score after the worker returns predictions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import exam
from .challenge import (
    PRACTICE_CASES,
    PRACTICE_PATH,
    PRACTICE_SHA256,
    TRAIN_PATH,
    TRAIN_SHA256,
    PublicMaterial,
    canonical_text,
)
from .contracts import canonical

#: v2 (PRACTICE-SAFETY-01) adds the feedback-only `safety` block; nothing
#: else changes. A v1 result keeps its meaning: it never carried the block.
FEEDBACK_SCHEMA = "carbon.motor.practice-feedback.v2"
FEEDBACK_SCHEMA_V1 = "carbon.motor.practice-feedback.v1"
PROVENANCE = "MOTOR_PUBLIC_PRACTICE"
STAGED_MODULES = {
    "learned-baseline.py": "../learned_baseline.py",
    "motor-domain.py": "domain.py",
    "motor-recipes.py": "recipes.py",
}

PROGRAM = r'''"""Carbon motor practice worker: rebuild KRR and predict PRACTICE."""
import json, shutil, sys, time
from pathlib import Path

work = Path.cwd()
out = work.parent / "output"
package = work / "carbon"
motor = package / "motor"
motor.mkdir(parents=True)
(package / "__init__.py").write_text("")
(motor / "__init__.py").write_text("")
shutil.copyfile(work / "learned-baseline.py", package / "learned_baseline.py")
shutil.copyfile(work / "motor-domain.py", motor / "domain.py")
shutil.copyfile(work / "motor-recipes.py", motor / "recipes.py")
sys.path.insert(0, str(work))

from carbon.motor import recipes  # noqa: E402

recipe = json.loads((work / "recipe.json").read_text())
train = [json.loads(line) for line in (work / "train-v1.jsonl").read_text().splitlines() if line]
cases = json.loads((work / "practice-inputs.json").read_text())["cases"]
started = time.perf_counter()
model = recipes.build(recipe["family"], recipe["settings"], train)
fit_s = time.perf_counter() - started
predictions = {case["case_id"]: model.predict(case["inputs"]) for case in cases}
(out / "predictions.json").write_text(json.dumps(predictions, allow_nan=True))
(out / "fit.json").write_text(json.dumps({"fit_seconds": fit_s, "training_cases": len(train)}))
'''


@dataclass(frozen=True)
class PracticeSet:
    records: tuple[dict, ...]
    source_sha256: str

    @staticmethod
    def load(root="."):
        material = PublicMaterial.load(root)
        return PracticeSet(material.practice, PRACTICE_SHA256)

    @property
    def case_ids(self):
        return [record["case_id"] for record in self.records]

    def inputs_document(self):
        return {
            "schema": "carbon.motor.practice-inputs.v1",
            "cases": [
                {"case_id": record["case_id"], "inputs": record["inputs"]}
                for record in self.records
            ],
        }

    def public_bytes(self):
        return b"".join(canonical(record) + b"\n" for record in self.records)


def staged_files(root, practice, recipe):
    here = Path(__file__).parent
    files = {
        staged: (here / relative).resolve().read_bytes()
        for staged, relative in STAGED_MODULES.items()
    }
    files["train-v1.jsonl"] = canonical_text(
        Path(root) / TRAIN_PATH, TRAIN_SHA256, "train"
    )
    # Only inputs cross the worker boundary; PRACTICE labels remain host-side.
    files["practice-inputs.json"] = canonical(practice.inputs_document())
    files["recipe.json"] = canonical(
        {
            "family": recipe.family,
            "settings": recipe.settings,
            "recipe_digest": recipe.recipe_digest,
        }
    )
    return files


def score_practice(predictions, practice, material):
    scales = exam.scales_from_train(material.train)
    rows = [
        exam.score_case(predictions.get(record["case_id"]), record, scales)
        for record in practice.records
    ]
    return rows, exam.aggregate(rows)


def feedback(summary, fit, *, recipe, backend, worker, safety=None):
    """The public practice feedback. With `safety` (`practice_safety.safety`),
    the v2 shape: the same fields plus the feedback-only safety block.
    Without it, exactly the v1 shape."""
    out = {
        "schema": FEEDBACK_SCHEMA if safety is not None else FEEDBACK_SCHEMA_V1,
        "provenance": PROVENANCE,
        "challenge": recipe.document()["challenge"],
        "recipe_digest": recipe.recipe_digest,
        "backbone": recipe.family,
        "summary": summary,
        "fit": fit,
        "backend": backend,
        "worker": worker,
        "adaptively_seen": True,
        "final_exam": False,
        "official_eligible": False,
        "scientific_qualification": False,
    }
    if safety is not None:
        out["safety"] = safety
    return out


def material_paths():
    """The two public files this provider owns; useful to discovery/tests."""

    return {
        "train": {"path": TRAIN_PATH, "sha256": TRAIN_SHA256},
        "practice": {
            "path": PRACTICE_PATH,
            "sha256": PRACTICE_SHA256,
            "cases": PRACTICE_CASES,
        },
    }
