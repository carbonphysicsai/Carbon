"""The study harness: Phases A-H for any Challenge (TRAINING-BUDGET-01 slice 2).

`CHALLENGE_TRAINING_BUDGET_STUDY.md` is the spec; the rules are frozen
(`DECISION_RULES.md`, `DECISION_RULES_R9_R11.md`). The harness plans each
phase's rebuilds from the Challenge's sheet and adapter, runs them through an
executor, and keeps every record. It applies only the one gate it must hold
to run at all, R1's determinism check after Phase A; the analysis applies
R2-R11 (slice 4).

**What it holds, outside any executor:**
- **The order.** A first, then B, C and F after R1 passes, then G; D, E and H
  only after the owner has frozen L. A failed R1 ends the study.
- **The confirmation set** is opened once, after L is frozen, and used only
  by Phase D.
- **The released image.** The sheet's image must be a `worker-images-vN`
  release record's own reference (`carbon.worker-image-release.v1`). The
  study runs on released digests only.
- **The sheet.** A phase whose sheet values are unset is refused
  (`sheet.SheetIncomplete`).
- **The ledger.** A run is reserved before it is dispatched and its record
  written once. A finished run is never repeated. A run still reserved after
  a crash is not re-dispatched: `reconcile` marks it FAILED_INFRA, and its
  retry is a new attempt. These are the validator work ledger's semantics,
  kept in files under the study root.
- **The journal** (`journal.jsonl`), append-only: the study's opening, each
  phase's plan digest, the R1 result, the frozen limit and the confirmation
  set's single use.

The study root is owner-only and outside the repository. It never holds the
study seed root, which stays on the producer host.

**Reconstruction seeds** are derived from each run's public identity, not
from the study seed root: they are rebuild randomness, not case data.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import sheet as sheets

RECORD_SCHEMA = "carbon.training-budget.study-record.v1"
JOURNAL_SCHEMA = "carbon.training-budget.study-journal.v1"
PLAN_SCHEMA = "carbon.training-budget.study-plan.v1"
RELEASE_SCHEMA = "carbon.worker-image-release.v1"
PHASES = ("A", "B", "C", "D", "E", "F", "G", "H")
#: Phases the frozen limit opens (runbook step 10).
AFTER_LIMIT = ("D", "E", "H")
#: Phase C's cost multiples and Phase D's multiples of L (the spec's values).
EQUAL_COST_MULTIPLES = (1, 4, 16)
RANKING_MULTIPLES = (1, 4)
RANKING_TOP = 4
RANKING_SEEDS = 5
#: Phase E: back to back alone, then this many at once on one GPU.
LOAD_SHARES = (2, 4)
#: Phase H: fractions of L (R10), and its seeds.
SCREENING_FRACTIONS = (1 / 64, 1 / 32, 1 / 16, 1 / 8, 1 / 4, 1)
SCREENING_SEEDS = 3
#: Phase G: the three best recipes (R9).
BEST = 3

RECORD_GROUPS = {
    "identity": (
        "recipe_digest",
        "settings",
        "seed",
        "image_digest",
        "backend",
        "gpu_model",
        "driver_version",
        "cuda_version",
    ),
    "time": ("compile_s", "train_s", "wall_s"),
    "resources": ("peak_memory_bytes", "steps_completed"),
    "training": ("final_loss",),
    "score": (
        "exam_score",
        "key_region_score",
        "gates",
        "error_components",
        "key_region_cases",
    ),
    "determinism": ("weight_digest", "prediction_digest"),
}

_RELEASE_TAG = re.compile(r"worker-images-v[0-9]+(\.[0-9]+)*")


class StudyRefused(RuntimeError):
    """The study cannot take this step, by a closed code."""

    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class Run:
    """One planned rebuild. `parameters` is the recipe's settings; `group`
    ties runs that are compared (same-seed pairs) or run at once on one GPU
    (`concurrency`)."""

    phase: str
    recipe: str
    parameters: dict
    seed_index: int
    train_size: int | None = None
    evaluation: str = "study"
    group: str | None = None
    concurrency: int = 1
    budget: float | None = None
    note: str = ""

    def document(self):
        return {k: v for k, v in asdict(self).items()}

    @property
    def run_id(self):
        return self.phase + "-" + digest(self.document())[7:23]


def reconstruction_seed(challenge_id, run):
    """Rebuild randomness from the run's public identity (not case data):
    the same for every repeat of a same-seed pair."""
    body = canonical(
        {
            "challenge": challenge_id,
            "recipe": run.recipe,
            "parameters": run.parameters,
            "seed_index": run.seed_index,
        }
    )
    return int.from_bytes(hashlib.sha256(body).digest()[:4], "big") >> 1


def check_release(image, record):
    """The sheet's image is this release record's own reference."""
    if not (
        type(record) is dict
        and record.get("schema") == RELEASE_SCHEMA
        and type(record.get("release_tag")) is str
        and _RELEASE_TAG.fullmatch(record["release_tag"])
        and record.get("reference") == image
        and record.get("repository", "") + "@" + record.get("registry_digest", "")
        == image
    ):
        raise StudyRefused(
            "study_image_not_released",
            "the sheet's image must be a worker-images release record's reference",
        )
    return record


# -- Plans ---------------------------------------------------------------------


def _ladder(default, low, high, integer):
    """From one doubling below the default up to the study range's top,
    doubling each step, within the study range; the default is always in. A
    default of 0 (a setting that is off by default) starts four doublings
    below the top."""
    values, value = set(), (default / 2 if default > 0 else high / 16)
    if value <= 0:
        raise StudyRefused(
            "study_ladder_empty", "the study range's top is not positive"
        )
    while value <= high:
        if value >= low:
            values.add(round(value) if integer else float(value))
        value *= 2
    values.add(default)
    if high not in values and high > default:
        values.add(int(high) if integer else float(high))
    return sorted(values)


def plan_a(study_recipes, largest):
    """Each study recipe at its defaults twice with one seed; the largest
    recipe allowed today twice; two rebuilds sharing one GPU, beside their
    lone twin (R1's pairs)."""
    runs = []
    for i, parameters in enumerate(study_recipes):
        for repeat in (0, 1):
            runs.append(
                Run(
                    "A",
                    f"study-{i}",
                    parameters,
                    0,
                    group=f"pair:study-{i}",
                    note=f"repeat {repeat}",
                )
            )
    for repeat in (0, 1):
        runs.append(
            Run(
                "A",
                "largest",
                largest,
                0,
                group="pair:largest",
                note=f"repeat {repeat}",
            )
        )
    shared = study_recipes[0]
    for slot in (0, 1):
        runs.append(
            Run(
                "A",
                "study-0",
                shared,
                0,
                group="shared:study-0",
                concurrency=2,
                note=f"slot {slot}",
            )
        )
    return runs


def plan_b(study_recipes, settings, ranges, seeds):
    """One setting at a time from each recipe's defaults, from below its
    default to the study range's top (`_ladder`)."""
    runs = []
    for i, parameters in enumerate(study_recipes):
        for name, spec in sorted(settings.items()):
            if name not in ranges:
                continue
            low, high = ranges[name]
            default = parameters.get(name, spec["default"])
            for value in _ladder(default, low, high, spec["integer"]):
                for seed in range(seeds):
                    runs.append(
                        Run(
                            "B",
                            f"study-{i}",
                            {**parameters, name: value},
                            seed,
                            note=name,
                        )
                    )
    return runs


def plan_c(variants, seeds):
    """Equal-cost trade-offs: `variants` maps (multiple, how) to the recipe
    the adapter scaled to that multiple of the default's cost."""
    return [
        Run(
            "C", f"{how}x{multiple}", parameters, seed, budget=float(multiple), note=how
        )
        for (multiple, how), parameters in sorted(variants.items())
        for seed in range(seeds)
    ]


def plan_d(top, limit):
    """The top configurations at L and 4L, once each on the confirmation set,
    with Phase D's five seeds."""
    if len(top) != RANKING_TOP:
        raise StudyRefused("study_ranking_needs_top_four", str(len(top)))
    return [
        Run("D", name, parameters, seed, evaluation="confirmation", budget=m * limit)
        for name, by_multiple in sorted(top.items())
        for m in RANKING_MULTIPLES
        for parameters in [by_multiple[m]]
        for seed in range(RANKING_SEEDS)
    ]


def plan_e(costliest, limit, back_to_back):
    """The costliest recipe allowed at L back to back, then 2 and 4 at once."""
    runs = [
        Run("E", "costliest", costliest, i, budget=limit, note="alone")
        for i in range(back_to_back)
    ]
    for share in LOAD_SHARES:
        runs += [
            Run(
                "E",
                "costliest",
                costliest,
                slot,
                budget=limit,
                group=f"shared:{share}",
                concurrency=share,
            )
            for slot in range(share)
        ]
    return runs


def plan_f(stress, seeds):
    """One recipe built to be slow for its cost per suspect setting."""
    return [
        Run("F", f"stress-{name}", parameters, seed, note=name)
        for name, parameters in sorted(stress.items())
        for seed in range(seeds)
    ]


def plan_g(best, sizes, seeds):
    """The three best recipes at L on nested study TRAIN sets."""
    if len(best) != BEST:
        raise StudyRefused("study_data_size_needs_three_best", str(len(best)))
    return [
        Run("G", name, parameters, seed, train_size=size)
        for name, parameters in sorted(best.items())
        for size in sizes
        for seed in range(seeds)
    ]


def plan_h(panel, minimum, by_fraction):
    """The study panel at fractions of L and at L, three seeds each.
    `by_fraction(parameters, f)` is the recipe scaled to f·L."""
    if len(panel) < minimum:
        raise StudyRefused("study_panel_too_small", f"{len(panel)} < {minimum}")
    return [
        Run("H", name, by_fraction(parameters, f), seed, budget=f, note=f"fraction {f}")
        for name, parameters in sorted(panel.items())
        for f in SCREENING_FRACTIONS
        for seed in range(SCREENING_SEEDS)
    ]


def train_sizes(current, ladder, ceiling):
    """Phase G's nested sizes: the ladder's multiples of the current TRAIN
    size, within the generation ceiling."""
    sizes = sorted({max(1, round(current * m)) for m in ladder})
    return [s for s in sizes if s <= ceiling]


# -- R1, the determinism gate ---------------------------------------------------


def r1(records):
    """R1 as written: every same-seed pair matches in weight and prediction
    digests, including the largest recipe and the shared-GPU runs. The
    shared-GPU runs must match their lone twin."""
    groups, mismatches = {}, []
    for record in records:
        if record["phase"] == "A" and record["state"] == "COMPLETED":
            groups.setdefault(record["run"]["group"], []).append(record)
    lone = {}
    for name, members in groups.items():
        digests = {
            (m["determinism"]["weight_digest"], m["determinism"]["prediction_digest"])
            for m in members
        }
        if len(members) < 2 or len(digests) != 1:
            mismatches.append(name)
        if name.startswith("pair:"):
            lone[name[5:]] = digests
    for name, members in groups.items():
        if name.startswith("shared:"):
            twin = lone.get(name[7:])
            if (
                twin is None
                or {
                    (
                        m["determinism"]["weight_digest"],
                        m["determinism"]["prediction_digest"],
                    )
                    for m in members
                }
                != twin
            ):
                mismatches.append(name + " vs its lone twin")
    expected = {g for r in records if r["phase"] == "A" for g in [r["run"]["group"]]}
    missing = sorted(expected - set(groups))
    return {
        "rule": "R1",
        "result": "PASS" if not mismatches and not missing and groups else "FAIL",
        "mismatches": sorted(mismatches),
        "missing": missing,
    }


# -- The study ------------------------------------------------------------------


@dataclass
class Study:
    """One Challenge's study under one root."""

    root: Path
    sheet: sheets.Sheet
    release: dict
    repository: Path = field(
        default_factory=lambda: Path(__file__).resolve().parents[2]
    )

    def __post_init__(self):
        self.root = Path(self.root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = os.lstat(self.root)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise StudyRefused("study_root_not_owner_only")
        if self.root.resolve().is_relative_to(self.repository.resolve()):
            raise StudyRefused("study_root_inside_repository")
        image = self.sheet.get("image_digest")
        if image is None:
            raise sheets.SheetIncomplete("A", ["image_digest"])
        check_release(image, self.release)
        for name in ("records", "reserved"):
            (self.root / name).mkdir(mode=0o700, exist_ok=True)
        if not self.journal():
            self._append(
                {
                    "event": "opened",
                    "challenge": self.sheet.challenge_id,
                    "image": image,
                    "release_tag": self.release["release_tag"],
                    "sheet_digest": digest(self.sheet.values),
                }
            )

    # The journal.

    def journal(self):
        path = self.root / "journal.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line]

    def _append(self, event):
        with (self.root / "journal.jsonl").open("ab") as stream:
            stream.write(canonical({"schema": JOURNAL_SCHEMA, **event}) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _events(self, kind):
        return [e for e in self.journal() if e["event"] == kind]

    def limit(self):
        frozen = self._events("limit_frozen")
        return frozen[-1] if frozen else None

    # Gates.

    def _admit(self, phase):
        if phase not in PHASES:
            raise StudyRefused("study_phase_unknown", str(phase))
        self.sheet.require(phase)
        gate = self._events("r1")
        if phase != "A":
            if not gate:
                raise StudyRefused("study_r1_not_applied", "Phase A and R1 come first")
            if gate[-1]["result"] != "PASS":
                raise StudyRefused("study_stopped_by_r1")
        if phase in AFTER_LIMIT and self.limit() is None:
            raise StudyRefused("study_limit_not_frozen", f"Phase {phase} runs after L")

    def plan(self, phase, runs):
        """Record a phase's plan (its digest in the journal) and return it."""
        self._admit(phase)
        if any(run.phase != phase for run in runs):
            raise StudyRefused("study_plan_mixes_phases")
        if phase != "D" and any(run.evaluation != "study" for run in runs):
            raise StudyRefused("study_confirmation_only_in_phase_d")
        document = {
            "schema": PLAN_SCHEMA,
            "phase": phase,
            "runs": [run.document() for run in runs],
        }
        self._append(
            {"event": "planned", "phase": phase, "plan_digest": digest(document)}
        )
        return runs

    def apply_r1(self):
        result = r1(self.records())
        self._append({"event": "r1", **result})
        return result

    def freeze_limit(self, value, unit, by):
        """The owner's frozen L (runbook step 9), once."""
        if self.limit() is not None:
            raise StudyRefused("study_limit_already_frozen")
        if not (type(value) in (int, float) and value > 0 and unit and by):
            raise StudyRefused("study_limit_malformed")
        self._append({"event": "limit_frozen", "value": value, "unit": unit, "by": by})

    def open_confirmation(self):
        """The sealed confirmation set, opened once, after L is frozen."""
        if self.limit() is None:
            raise StudyRefused(
                "study_limit_not_frozen", "the confirmation set waits for L"
            )
        if self._events("confirmation_opened"):
            raise StudyRefused("study_confirmation_already_used")
        self._append({"event": "confirmation_opened"})

    # Runs.

    def records(self):
        return [
            json.loads(p.read_text())
            for p in sorted((self.root / "records").glob("*.json"))
        ]

    def unresolved(self):
        done = {p.stem for p in (self.root / "records").glob("*.json")}
        return sorted(
            p.stem for p in (self.root / "reserved").iterdir() if p.stem not in done
        )

    def reconcile(self, attempt_id):
        """A run left reserved by a crash becomes FAILED_INFRA; its retry is a
        new attempt."""
        if attempt_id not in self.unresolved():
            raise StudyRefused("study_nothing_to_reconcile", attempt_id)
        reserved = json.loads(
            (self.root / "reserved" / f"{attempt_id}.json").read_text()
        )
        self._write(
            attempt_id, reserved["run"], reserved["attempt"], "FAILED_INFRA", {}
        )

    def _write(self, attempt_id, run, attempt, state, body):
        record = {
            "schema": RECORD_SCHEMA,
            "challenge": self.sheet.challenge_id,
            "phase": run["phase"],
            "run_id": attempt_id.rsplit(".", 1)[0],
            "attempt": attempt,
            "run": run,
            "state": state,
            **body,
        }
        path = self.root / "records" / f"{attempt_id}.json"
        with path.open("xb") as stream:
            stream.write(canonical(record))
        return record

    def execute(self, runs, executor, *, cost=None):
        """Run each planned rebuild once. `executor(run, seed)` returns the
        record groups (`RECORD_GROUPS`); `cost(run)` the calculated cost
        F0-F4. A completed run is never repeated; an unresolved one blocks
        until it is reconciled."""
        if self.unresolved():
            raise StudyRefused("study_unresolved_runs", ", ".join(self.unresolved()))
        if any(run.evaluation == "confirmation" for run in runs):
            if not self._events("confirmation_opened"):
                raise StudyRefused("study_confirmation_sealed")
            if any(r["run"]["evaluation"] == "confirmation" for r in self.records()):
                raise StudyRefused("study_confirmation_already_used")
        done = {}
        for record in self.records():
            done.setdefault(record["run_id"], []).append(record)
        written = []
        for run in runs:
            history = done.get(run.run_id, [])
            if any(r["state"] in ("COMPLETED", "FAILED_CANDIDATE") for r in history):
                continue
            attempt = len(history)
            attempt_id = f"{run.run_id}.{attempt}"
            reservation = {"run": run.document(), "attempt": attempt}
            with (self.root / "reserved" / f"{attempt_id}.json").open("xb") as stream:
                stream.write(canonical(reservation))
            seed = reconstruction_seed(self.sheet.challenge_id, run)
            try:
                groups = executor(run, seed)
            except Exception as failure:  # noqa: BLE001 - classified below
                candidate = bool(getattr(failure, "candidate", False))
                state = "FAILED_CANDIDATE" if candidate else "FAILED_INFRA"
                written.append(
                    self._write(
                        attempt_id,
                        run.document(),
                        attempt,
                        state,
                        {"failure": getattr(failure, "code", type(failure).__name__)},
                    )
                )
                continue
            missing = [
                f"{g}.{k}"
                for g, keys in RECORD_GROUPS.items()
                for k in keys
                if k not in (groups.get(g) or {})
            ]
            if missing:
                raise StudyRefused("study_record_incomplete", ", ".join(missing[:6]))
            body = {g: groups[g] for g in RECORD_GROUPS}
            body["calculated_cost"] = cost(run) if cost is not None else None
            written.append(
                self._write(attempt_id, run.document(), attempt, "COMPLETED", body)
            )
        return written
