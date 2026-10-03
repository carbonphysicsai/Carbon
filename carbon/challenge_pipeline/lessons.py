"""Lessons learned, one entry after every execution (OWNER-CHALLENGE-ROADMAP-03).

The owner, 2026-10-02: "Make sure everything we have is a generalizable test and
design protocol that can be adapted to any challenge and improved as we go.
Note lessons learned after every execution."

Every execution appends one file to `carbon/challenge_pipeline/lessons/`. That
covers a test run, a campaign session or block, a pod run, a ladder climb, an
optimizer pilot, a coverage run, a stage gate or a build. It is one file per
entry, so parallel work never conflicts. An entry says:
- what ran, and what was expected against what was observed;
- what to keep and what to change;
- which protocol elements it bears on.

A lesson that should change the protocol carries a proposed revision.
- It stays PROPOSED until a named owner adopts or declines it.
- Before lock, any of the three owners may decide; after lock, the process
  owner decides.
- An adopted revision is applied as a recorded change: a roadmap revision, a
  protocol or suite version. It is never applied silently.

The log describes the work. It grants nothing.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

LESSONS = Path(__file__).with_name("lessons")
SCHEMA = "carbon.challenge-pipeline.lesson.v1"
KEYS = {
    "schema",
    "lesson_id",
    "recorded_at",
    "challenge",
    "stage",
    "execution",
    "expected",
    "observed",
    "keep",
    "change",
    "protocol_elements",
    "proposed_revision",
    "status",
}
OPTIONAL = {"decision"}
STAGES = ("prioritize", "design", "test_iterate", "rank", "protocol")
KINDS = (
    "test_run",
    "campaign_session",
    "campaign_block",
    "pod_run",
    "ladder_climb",
    "optimizer_pilot",
    "coverage_run",
    "stage_gate",
    "build",
)
STATUSES = ("RECORDED", "PROPOSED", "ADOPTED", "DECLINED")
LESSON_ID = re.compile(r"^(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*$")
TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class LessonError(ValueError):
    """A lessons entry breaks the log's rules."""


def _text(value):
    return isinstance(value, str) and value.strip() != ""


def _texts(value, *, at_least=0):
    return (
        isinstance(value, list)
        and len(value) >= at_least
        and all(_text(item) for item in value)
    )


def validate(entry, name, protocol):
    where = f"lesson {name}"
    if not isinstance(entry, dict) or not (KEYS <= set(entry) <= KEYS | OPTIONAL):
        raise LessonError(
            f"{where}: keys are {sorted(KEYS)} (and an optional decision)"
        )
    if entry["schema"] != SCHEMA:
        raise LessonError(f"{where}: unknown schema")
    match = LESSON_ID.match(str(entry["lesson_id"]))
    if not match or entry["lesson_id"] != name:
        raise LessonError(f"{where}: lesson_id is the file name, <YYYY-MM-DD>-<slug>")
    try:
        recorded = datetime.datetime.fromisoformat(str(entry["recorded_at"]))
    except ValueError as error:
        raise LessonError(f"{where}: recorded_at is an ISO time") from error
    if recorded.utcoffset() != datetime.timedelta(0):
        raise LessonError(f"{where}: recorded_at is UTC")
    if recorded.date().isoformat() != match.group(1):
        raise LessonError(f"{where}: the id's date is the recorded date")
    if not (entry["challenge"] == "protocol" or TOKEN.match(str(entry["challenge"]))):
        raise LessonError(f"{where}: challenge is a Challenge token or 'protocol'")
    if entry["stage"] not in STAGES:
        raise LessonError(f"{where}: stage is one of {STAGES}")
    execution = entry["execution"]
    if (
        not isinstance(execution, dict)
        or set(execution) != {"kind", "ref", "description"}
        or execution["kind"] not in KINDS
        or not _text(execution["ref"])
        or not _text(execution["description"])
    ):
        raise LessonError(
            f"{where}: execution is {{kind, ref, description}} with kind one of {KINDS}"
        )
    for key in ("expected", "observed"):
        if not _text(entry[key]):
            raise LessonError(f"{where}: {key} is a statement")
    if not (_texts(entry["keep"]) and _texts(entry["change"])):
        raise LessonError(f"{where}: keep and change are lists of statements")
    if not _texts(entry["protocol_elements"], at_least=1):
        raise LessonError(f"{where}: name at least one protocol element it bears on")
    status, revision = entry["status"], entry["proposed_revision"]
    if status not in STATUSES:
        raise LessonError(f"{where}: status is one of {STATUSES}")
    if status == "RECORDED":
        if revision is not None:
            raise LessonError(f"{where}: a proposed revision makes the lesson PROPOSED")
    elif not (
        isinstance(revision, dict)
        and set(revision) == {"target", "text"}
        and _text(revision["target"])
        and _text(revision["text"])
    ):
        raise LessonError(
            f"{where}: {status} needs a proposed revision {{target, text}}"
        )
    decision = entry.get("decision")
    if status in ("ADOPTED", "DECLINED"):
        owners = protocol["owners"]
        allowed = (
            {owners["process"]}
            if protocol["state"] == "LOCKED"
            else set(owners.values())
        )
        if (
            not isinstance(decision, dict)
            or set(decision) != {"by", "on", "ref"}
            or decision["by"] not in allowed
            or not DATE.match(str(decision["on"]))
            or not _text(decision["ref"])
        ):
            raise LessonError(
                f"{where}: {status} needs a decision {{by, on, ref}} by "
                + (
                    "the process owner"
                    if protocol["state"] == "LOCKED"
                    else "a named owner"
                )
            )
    elif decision is not None:
        raise LessonError(
            f"{where}: only an adopted or declined lesson carries a decision"
        )
    return entry


def load_lessons(protocol, directory=LESSONS):
    """Every entry, validated, oldest first."""
    entries = []
    for path in sorted(Path(directory).glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        entries.append(validate(entry, path.stem, protocol))
    return sorted(entries, key=lambda e: (e["recorded_at"], e["lesson_id"]))


def open_revisions(entries):
    return [e for e in entries if e["status"] == "PROPOSED"]
