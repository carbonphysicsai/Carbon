"""A Challenge's training budget sheet: the values the owner sets.

The schema is `docs/development/training_budget_study/SHEET_TEMPLATE.md`.
One file per Challenge, `carbon/training_budget/sheets/<challenge_id>.json`.
A value that is missing, null or `HUMAN_INPUT` is unset, and it blocks every
phase that uses it: the study fails closed. A Challenge with no sheet file has
every value unset.

Two constraints hold for every sheet:
- **The study seed root is never in a sheet.** It lives only on the producer
  host that draws the study sets. A sheet records only where it is held and
  its commitment (`{"held_by": ..., "commitment": "sha256:<64 hex>"}`); a raw
  seed is refused.
- **The image is a released worker image**, named by registry digest
  (`ghcr.io/carbonphysicsai/<repository>@sha256:<64 hex>`). The study runs on
  released digests only; the harness checks the release record.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "carbon.training-budget.sheet.v1"
HUMAN_INPUT = "HUMAN_INPUT"
SHEETS = Path(__file__).resolve().parent / "sheets"

#: Every phase and rule a sheet value can block.
PHASES = ("A", "B", "C", "D", "E", "F", "G", "H", "R3", "R9", "R11", "stop")
_ALL = PHASES

#: Each sheet field and what uses it (the template's "Used by" column).
FIELDS = {
    "challenge_id": _ALL,
    "challenge_version": _ALL,
    "gpu_model": _ALL,
    "image_digest": _ALL,
    "spend_ceiling": ("stop",),
    "study_seed_root": ("A", "B", "C", "D", "E", "F", "G", "H"),
    "study_contract_ranges": ("B", "C", "F"),
    "rebuild_time_target": ("R3",),
    "memory_ceiling": ("R3",),
    "study_time_limit": _ALL,
    "seeds_per_setting": ("B", "C", "G", "H"),
    "study_recipes": ("A", "B", "C"),
    "train_size_ladder": ("G",),
    "generation_ceiling": ("G", "R9"),
    "minimum_panel_size": ("H",),
    "target_utilization": ("R11",),
    "gpu_ceiling": ("R11",),
    "expected_participation": ("R11",),
    # The study sets' sizes, which the producer draws (#738).
    "study_eval_size": ("A", "B", "C", "E", "F", "G", "H"),
    "confirmation_size": ("D",),
}
#: A sheet's own record of what it is. Every value of a sheet that is not
#: production says so; no production sheet exists yet.
STATUSES = ("TEAM_PROPOSED_OWNER_APPROVED_FOR_TESTING",)
META = ("status", "authority", "rationale")

#: The template's default ladder: multiples of the current TRAIN size.
DEFAULT_TRAIN_SIZE_LADDER = (0.25, 0.5, 1, 2, 4, 8)

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_IMAGE = re.compile(
    r"ghcr\.io/carbonphysicsai/[a-z0-9]+([._-][a-z0-9]+)*@sha256:[0-9a-f]{64}"
)
_TOKEN = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")


class SheetInvalid(ValueError):
    """A sheet value that is set but malformed. Never read as unset."""

    def __init__(self, field, why):
        super().__init__(f"{field}: {why}")
        self.field = field


class SheetIncomplete(LookupError):
    """A phase needs values the sheet leaves unset (HUMAN_INPUT)."""

    def __init__(self, phase, fields):
        super().__init__(
            f"phase {phase} needs HUMAN_INPUT values: " + ", ".join(fields)
        )
        self.phase, self.fields = phase, tuple(fields)


def _unset(value):
    return value is None or value == HUMAN_INPUT


def _positive(value):
    return type(value) in (int, float) and value > 0


def _check(field, value):
    """Refuse a set value of the wrong form. No threshold is chosen here
    beyond the template's own (at least 3 seeds per setting)."""
    ok = True
    if field in ("challenge_id", "challenge_version", "gpu_model"):
        ok = type(value) is str and bool(_TOKEN.fullmatch(value.lower()))
    elif field == "image_digest":
        ok = type(value) is str and bool(_IMAGE.fullmatch(value))
    elif field == "study_seed_root":
        ok = (
            type(value) is dict
            and set(value) == {"held_by", "commitment"}
            and type(value["held_by"]) is str
            and bool(value["held_by"])
            and type(value["commitment"]) is str
            and bool(_DIGEST.fullmatch(value["commitment"]))
        )
        if not ok:
            raise SheetInvalid(
                field,
                "a sheet holds only where the study seed root is held and its"
                " commitment, never the root",
            )
    elif field == "study_contract_ranges":
        ok = (
            type(value) is dict
            and bool(value)
            and all(
                type(k) is str
                and type(v) is list
                and len(v) == 2
                and all(type(x) in (int, float) for x in v)
                and v[0] <= v[1]
                for k, v in value.items()
            )
        )
    elif field == "seeds_per_setting":
        ok = type(value) is int and value >= 3
    elif field == "study_recipes":
        ok = type(value) is list and bool(value) and all(type(r) is dict for r in value)
    elif field == "train_size_ladder":
        ok = type(value) is list and bool(value) and all(_positive(x) for x in value)
    elif field == "target_utilization":
        ok = type(value) in (int, float) and 0 < value <= 1
    elif field in ("gpu_ceiling", "study_eval_size", "confirmation_size"):
        ok = type(value) is int and value >= 1
    elif field in (
        "spend_ceiling",
        "rebuild_time_target",
        "memory_ceiling",
        "study_time_limit",
        "generation_ceiling",
        "minimum_panel_size",
        "expected_participation",
    ):
        ok = _positive(value)
    if not ok:
        raise SheetInvalid(field, "malformed value")


@dataclass(frozen=True)
class Sheet:
    """One Challenge's sheet. `values` holds only set values; `status` says
    what the values are (never production yet)."""

    challenge_id: str
    values: dict
    status: str | None = None

    def get(self, field):
        if field not in FIELDS:
            raise KeyError(field)
        if field == "train_size_ladder" and field not in self.values:
            return list(DEFAULT_TRAIN_SIZE_LADDER)
        return self.values.get(field)

    def missing_for(self, phase):
        """The unset fields `phase` needs, in template order."""
        if phase not in PHASES:
            raise KeyError(phase)
        return [
            f
            for f, uses in FIELDS.items()
            if phase in uses and f != "train_size_ladder" and f not in self.values
        ]

    def require(self, phase):
        """Refuse a phase whose values are not all set (fail closed)."""
        missing = self.missing_for(phase)
        if missing:
            raise SheetIncomplete(phase, missing)
        return self


def parse(document, challenge_id):
    """A sheet from its JSON document. Unknown fields are refused."""
    if type(document) is not dict or document.get("schema") != SCHEMA:
        raise SheetInvalid("schema", "not " + SCHEMA)
    unknown = sorted(set(document) - set(FIELDS) - set(META) - {"schema"})
    if unknown:
        raise SheetInvalid(unknown[0], "unknown field")
    status = document.get("status")
    if status is not None and status not in STATUSES:
        raise SheetInvalid("status", "not a known sheet status")
    rationale = document.get("rationale", {})
    if type(rationale) is not dict or not all(
        k in FIELDS and type(v) is str and v.strip() for k, v in rationale.items()
    ):
        raise SheetInvalid("rationale", "a one-line reason per sheet field")
    values = {}
    for field in FIELDS:
        value = document.get(field)
        if _unset(value):
            continue
        _check(field, value)
        values[field] = value
    if values.get("challenge_id", challenge_id) != challenge_id:
        raise SheetInvalid("challenge_id", "the sheet is another Challenge's")
    if status is not None:
        unexplained = sorted(set(values) - set(rationale) - {"challenge_id"})
        if unexplained:
            raise SheetInvalid(unexplained[0], "a set value has no rationale")
    return Sheet(challenge_id, values, status)


def load(challenge_id, root=SHEETS):
    """The Challenge's sheet, or an all-unset sheet when it has none."""
    if type(challenge_id) is not str or not _TOKEN.fullmatch(challenge_id):
        raise SheetInvalid("challenge_id", "malformed")
    path = Path(root) / f"{challenge_id}.json"
    if not path.exists():
        return Sheet(challenge_id, {})
    return parse(json.loads(path.read_text(encoding="utf-8")), challenge_id)
