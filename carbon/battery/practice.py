"""Battery practice: a miner's recipe trained in the isolated worker, scored by Carbon.

A practice trial is a research task, not an evaluation. It has three parts:
1. **Compile (trusted host).** The recipe is admitted through the battery
   contract. Anything outside it is refused by name before anything runs.
2. **Train and predict (isolated worker).** The carrier
   (`research_carrier._run`) runs a fixed program with no network, a bounded
   wall-clock and a precharged trial. It stages the exact bytes of
   `domain.py`, `recipes.py` and `training.py`, public TRAIN v1, the OCV table
   and the public PRACTICE inputs. The worker gets no PRACTICE label and no
   Carbon module beyond those three files.
3. **Score (trusted host).** The worker's predictions are gated and scored
   against the public PRACTICE references with the exam's own gates, TRAIN
   scales and frozen tolerances.

The feedback is service-produced. It is adaptively seen public evidence, not a
final exam, and grants no reward, frontier or qualification.

The public PRACTICE set is the exam-design campaign's own practice role: 200
reference solves, retained with the campaign and pinned here by the source
file's exact bytes. It shares no case with TRAIN v1, and nothing the testnet
exam scores is drawn from it: the exam's private pools come from the seed
service (`seeds.py`).
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import exam
from .challenge import (
    INPUTS,
    OCV_TABLE_PATH,
    OCV_TABLE_SHA256,
    TRAIN_V1_PATH,
    TRAIN_V1_SHA256,
    MaterialMismatch,
)

PRACTICE_SOURCE_PATH = (
    "docs/development/evidence/exam-design-2026-09-24/refs-a-part2/out/records.jsonl"
)
PRACTICE_SOURCE_SHA256 = (
    "7d3955b278b0aab08fe0abc530eded6511531d086e7f0cd94f6c09dc3e98fb8d"
)
PRACTICE_CASES = 200
#: v2 (PRACTICE-SAFETY-01) adds the feedback-only `safety` block; nothing
#: else changes. A v1 result keeps its meaning: it never carried the block.
#: v3 computes the block's B4 on the committed practice decision set (or
#: gives its typed refusal), and the block's `unmeasured` also counts that
#: set's cases. A v2 result keeps its meaning: its B4 is always BLOCKED.
FEEDBACK_SCHEMA = "carbon.battery.practice-feedback.v3"
FEEDBACK_SCHEMA_V2 = "carbon.battery.practice-feedback.v2"
FEEDBACK_SCHEMA_V1 = "carbon.battery.practice-feedback.v1"
PROVENANCE = "BATTERY_PUBLIC_PRACTICE"
#: The files the worker receives, by staged name. Nothing else is staged.
STAGED_MODULES = {
    "battery-domain.py": "domain.py",
    "battery-recipes.py": "recipes.py",
    "battery-training.py": "training.py",
    "battery-torch-training.py": "torch_training.py",
    "battery-torch-families.py": "torch_families.py",
}

PROGRAM = r'''"""Carbon battery practice worker: train one compiled recipe, predict PRACTICE.

Fixed by Carbon. The recipe arrives compiled; this program does not interpret
miner text. It writes predictions and fit statistics, nothing else.
"""
import gzip, json, shutil, sys
from pathlib import Path

import numpy as np

work = Path.cwd()
out = work.parent / "output"
lab = work / "carbon_battery_lab"
lab.mkdir()
(lab / "__init__.py").write_text("")
for staged, module in (
    ("battery-domain.py", "domain.py"),
    ("battery-recipes.py", "recipes.py"),
    ("battery-training.py", "training.py"),
    ("battery-torch-training.py", "torch_training.py"),
    ("battery-torch-families.py", "torch_families.py"),
):
    shutil.copyfile(work / staged, lab / module)
sys.path.insert(0, str(work))

from carbon_battery_lab import recipes, training  # noqa: E402
from carbon_battery_lab.domain import INPUTS, TrainingData  # noqa: E402

# Trainer v2 (RSURF-D3): practice records a capped TRAIN-loss history for the
# learning curve. The validator's reconstruction program never turns it on.
training.record_training_history(True)
recipe = json.loads((work / "recipe.json").read_text())
train = TrainingData.from_records(
    [
        json.loads(line)
        for line in gzip.decompress((work / "train-v1.jsonl.gz").read_bytes()).splitlines()
        if line.strip()
    ]
)
table = json.loads((work / "ocv-table.json").read_text())
structure = recipes.Structure(
    np.asarray(table["soc"], float), np.asarray(table["ocv_v"], float)
)
model = recipes.build(recipe["family"], recipe["settings"])
stats = model.fit(train, structure, recipe["seed"])
cases = json.loads((work / "practice-inputs.json").read_text())["cases"]
x = np.array([[case["inputs"][k] for k in INPUTS] for case in cases], float)
predictions = recipes.to_predictions(model.predict(x), [c["case_id"] for c in cases])
# Non-finite predictions are kept as JSON NaN/Infinity: a gate, not the
# worker, decides what they mean.
(out / "predictions.json").write_text(json.dumps(predictions))
(out / "fit.json").write_text(
    json.dumps({k: stats[k] for k in sorted(stats)}, allow_nan=True)
)
'''


def _pinned(path, expected, name):
    body = Path(path).read_bytes()
    if hashlib.sha256(body).hexdigest() != expected:
        raise MaterialMismatch(name + " does not match its pinned digest")
    return body


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


@dataclass(frozen=True)
class PracticeSet:
    """The public PRACTICE references, verified against the pinned source."""

    records: tuple
    source_sha256: str

    @staticmethod
    def load(root="."):
        body = _pinned(
            Path(root) / PRACTICE_SOURCE_PATH, PRACTICE_SOURCE_SHA256, "practice"
        )
        records = []
        for line in body.splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("role") == "practice":
                records.append(record)
        if len(records) != PRACTICE_CASES or any(
            r.get("status") != "OK" for r in records
        ):
            raise MaterialMismatch("practice is not 200 OK PRACTICE cases")
        records.sort(key=lambda r: r["case_id"])
        return PracticeSet(tuple(records), PRACTICE_SOURCE_SHA256)

    @property
    def case_ids(self):
        return [r["case_id"] for r in self.records]

    def inputs_document(self, extra=()):
        """What the worker receives: case ids and inputs, never a label.

        `extra` (v2) appends further public cases to predict, as
        {case_id, inputs}: the practice decision set's, for feedback only.
        """
        cases = [
            {"case_id": r["case_id"], "inputs": {k: r["inputs"][k] for k in INPUTS}}
            for r in self.records
        ]
        if not extra:
            return {"schema": "carbon.battery.practice-inputs.v1", "cases": cases}
        added = [
            {"case_id": c["case_id"], "inputs": {k: c["inputs"][k] for k in INPUTS}}
            for c in extra
        ]
        ids = [c["case_id"] for c in cases + added]
        if len(set(ids)) != len(ids):
            raise MaterialMismatch("extra practice inputs repeat a case id")
        return {"schema": "carbon.battery.practice-inputs.v2", "cases": cases + added}

    def public_records(self):
        """The public PRACTICE references as a miner may download them."""
        return [
            {
                "case_id": r["case_id"],
                "role": "practice",
                "status": r["status"],
                "inputs": {k: r["inputs"][k] for k in INPUTS},
                "outputs": r["outputs"],
                "diagnostics": {"t_max_c": r["diagnostics"]["t_max_c"]},
            }
            for r in self.records
        ]

    def public_bytes(self):
        """Deterministic gzip of the public records (mtime 0)."""
        body = b"".join(_canonical(r) + b"\n" for r in self.public_records())
        return gzip.compress(body, mtime=0)


def staged_files(root, practice, recipe, seed, extra_cases=()):
    """Every byte the worker receives, by staged name. `extra_cases` are
    further public inputs to predict (`PracticeSet.inputs_document`)."""
    here = Path(__file__).parent
    files = {
        staged: (here / module).read_bytes()
        for staged, module in STAGED_MODULES.items()
    }
    files["train-v1.jsonl.gz"] = _pinned(
        Path(root) / TRAIN_V1_PATH, TRAIN_V1_SHA256, "train_v1"
    )
    table = json.loads(
        _pinned(Path(root) / OCV_TABLE_PATH, OCV_TABLE_SHA256, "ocv_table")
    )
    files["ocv-table.json"] = _canonical({"soc": table["soc"], "ocv_v": table["ocv_v"]})
    files["practice-inputs.json"] = _canonical(practice.inputs_document(extra_cases))
    files["recipe.json"] = _canonical(
        {
            "family": recipe.family,
            "settings": recipe.settings,
            "recipe_digest": recipe.recipe_digest,
            "seed": seed,
        }
    )
    return files


def score_practice(predictions, practice, material, root="."):
    """Gate and score predictions on the public PRACTICE references.

    Uses the exam's own gates, TRAIN scales and frozen tolerances, so practice
    and the exam agree on what a failure is. There are no hidden duplicates in
    PRACTICE, so the paired-repeat gate has nothing to check here.
    """
    store = practice_store(practice, material, root)
    rows, summary = exam.evaluate(predictions, practice.case_ids, store)
    return rows, summary


def practice_store(practice, material, root="."):
    """The exam's case store over the public PRACTICE references: the exam's
    TRAIN scales and frozen tolerances. `score_practice` scores on it, and a
    Graphite development score variant reads its legs from the same store
    (VALIDATOR-09)."""
    from .calibration import SHAPES, frozen_calibration

    tol, scales = frozen_calibration(root)
    refs = {r["case_id"]: r for r in practice.records}
    ocv = {
        cid: float(np.interp(r["inputs"]["soc0"], material.ocv_soc, material.ocv_v))
        for cid, r in refs.items()
    }
    return exam.CaseStore(refs, ocv, tol, scales, SHAPES)


def feedback(summary, fit, *, recipe, backend, worker, safety=None):
    """The public practice feedback: the exam aggregate on public PRACTICE,
    with fit statistics and the backend that actually ran.

    With `safety` (`practice_safety.safety`), the v3 shape: v2's fields, the
    safety block carrying B4 computed. Without it, exactly the v1 shape.
    """
    out = {
        "schema": FEEDBACK_SCHEMA if safety is not None else FEEDBACK_SCHEMA_V1,
        "provenance": PROVENANCE,
        "challenge": recipe.document()["challenge"],
        "recipe_digest": recipe.recipe_digest,
        "backbone": recipe.family,
        "summary": _summary(summary),
        "fit": _summary(
            {
                **{
                    k: fit[k]
                    for k in (
                        "final_loss",
                        "train_s",
                        "compile_s",
                        "n_params",
                        "params_sha256",
                    )
                    if k in fit
                },
                # Trainer v2's TRAIN-loss history, when the worker recorded a
                # well-formed one (RSURF-D3); anything else is left out.
                **(
                    {"loss_history": _history(fit["loss_history"])}
                    if _history(fit.get("loss_history")) is not None
                    else {}
                ),
            }
        ),
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


def _history(value):
    """A worker's TRAIN-loss history, bounded and checked, or None."""
    import math

    from .training import HISTORY_POINTS

    if type(value) is not dict or type(value.get("points")) is not list:
        return None
    if not 1 <= len(value["points"]) <= HISTORY_POINTS:
        return None
    points = []
    for point in value["points"]:
        if (
            type(point) is not list
            or len(point) != 2
            or type(point[0]) is not int
            or isinstance(point[1], bool)
            or not isinstance(point[1], (int, float))
            or not math.isfinite(point[1])
        ):
            return None
        points.append([point[0], float(point[1])])
    if [p[0] for p in points] != sorted({p[0] for p in points}):
        return None
    kept = {"points": points}
    for key in ("trainer", "objective", "member"):
        if type(value.get(key)) is str:
            kept[key] = value[key][:160]
    if type(value.get("updates")) is int:
        kept["updates"] = value["updates"]
    return kept


def _summary(summary):
    def clean(value):
        if isinstance(value, (float, np.floating)):
            value = float(value)
            return round(value, 6) if np.isfinite(value) else None
        if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
            return int(value)
        if isinstance(value, dict):
            return {str(k): clean(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(v) for v in value]
        return value

    return clean(summary)
