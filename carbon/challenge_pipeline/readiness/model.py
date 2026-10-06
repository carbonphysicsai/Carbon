"""The readiness gate's vocabulary: statuses, results, items and the gate document.

`items.json` lists every gate item as data. `docs/development/graphite/
GRAPHITE_READINESS_GATE.md` is the specification: a test asserts the two agree
row for row, so a gate item cannot be added or changed in one place only.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PASS = "PASS"
FAIL = "FAIL"
NOT_BUILT = "NOT_BUILT"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
STATUSES = (PASS, FAIL, NOT_BUILT, REVIEW_REQUIRED)

KINDS = ("auto", "review", "auto+review")
PACKAGE = Path(__file__).resolve().parent
REPOSITORY = PACKAGE.parents[2]
#: Where a gate run writes its history and reports: committed evidence, kept
#: OUT of `carbon/` so a run never dirties shipped code (the pre-live check
#: refuses uncommitted changes under `carbon/`). Static gate config (items,
#: challenges, policies, records, reviews) stays under `PACKAGE`.
RUNTIME = REPOSITORY / "docs/development/challenge_pipeline/readiness"
GATE_DOCUMENT = REPOSITORY / "docs/development/graphite/GRAPHITE_READINESS_GATE.md"
ITEMS_SCHEMA = "carbon.challenge-pipeline.readiness-items.v1"
CHALLENGE_TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*\Z")
ITEM_ID = re.compile(r"^[A-Z][0-9]\Z")


@dataclass(frozen=True)
class Result:
    """What one check found. `evidence` is JSON data (test ids, file digests,
    decision ids); `detail` says why in words."""

    status: str
    detail: str
    evidence: tuple = field(default_factory=tuple)

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r}")


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def file_digest(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_items():
    document = json.loads((PACKAGE / "items.json").read_bytes())
    if document.get("schema") != ITEMS_SCHEMA:
        raise ValueError("readiness items.json has the wrong schema")
    items = document["items"]
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("readiness items.json repeats an item id")
    for item in items:
        if not ITEM_ID.match(item["id"]) or item["kind"] not in KINDS:
            raise ValueError(f"readiness item {item.get('id')!r} is malformed")
    return items


def parse_gate_document(path=GATE_DOCUMENT):
    """The gate document's table rows: `[{id, check, kind, lesson}]` in order.
    A row is `| id | check | kind | lesson |`; kind comes from the `[auto]` and
    `[review]` markers in the third cell."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not ITEM_ID.match(cells[0]):
            continue
        markers = re.findall(r"\[(auto|review)\]", cells[2])
        kind = "+".join(dict.fromkeys(markers))
        rows.append(
            {"id": cells[0], "check": cells[1], "kind": kind, "lesson": cells[3]}
        )
    return rows
