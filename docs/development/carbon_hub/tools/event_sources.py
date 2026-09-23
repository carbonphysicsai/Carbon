"""The change ledger, assembled from one file per event plus the array.

Why this exists: git merges text, and the ledger's semantics are per-event. Two
workstreams appending to one array conflict, and the conflict is not presented
as two records — git interleaves them field by field inside a single object, so
a resolver chooses lines inside one record. A mechanical resolution can drop one
event, or both, and leave valid JSON behind. The immutability check compares the
candidate against the PR base, so it catches the loss of an event that already
reached main and reports nothing for a sibling branch's event that never did.
`hub_source_shape_reproduction.py` demonstrates all of that against the real
ledger.

One file per event removes it rather than mitigating it: two new files are not a
contested region, so there is no resolution to get wrong.

**The existing array is not moved.** Rewriting 235 events out of it would
conflict with every in-flight branch that appends one, which is the cost this
change exists to remove. So the array keeps its history in its recorded order,
new events are files, and the rendered output is unchanged on the day this
lands. Draining the array is a later tidy-up, not a precondition.

Ordering is a function of content, never of history: array events first, in
their recorded order, then file events by `recorded_at` with `event_id` as a
total tiebreak. Commit-date ordering was considered and rejected on core
platform's argument — it would make the render depend on git history, so a
shallow checkout or an export would render a different document, which would
break the byte-identical control used to prove this migration safe. An
author-assigned sequence number was rejected because it reintroduces the
collision: in the verification, two independent branches both chose 236.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: One file per event, named for the event it contains.
EVENTS_DIRECTORY = "data/events"
LEDGER_FILE = "data/change_events.json"


class EventSourceError(Exception):
    """A ledger source that cannot be assembled. Each caller reports its own way."""


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EventSourceError(f"{path.name} is not readable JSON: {error}") from None


def event_files(hub_root: Path) -> list[Path]:
    directory = hub_root / EVENTS_DIRECTORY
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"))


def load_file_events(hub_root: Path) -> list[dict]:
    """Every per-event file, validated enough to be ordered and identified.

    The filename must equal the event id. That is not tidiness: it makes two
    files claiming one event impossible to create, and it means a reader can see
    which event a file holds without opening it.
    """
    events: list[dict] = []
    seen: dict[str, str] = {}
    for path in event_files(hub_root):
        value = _read(path)
        if not isinstance(value, dict):
            raise EventSourceError(
                f"{EVENTS_DIRECTORY}/{path.name} must be one event object"
            )
        event_id = value.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise EventSourceError(f"{EVENTS_DIRECTORY}/{path.name} has no event_id")
        if path.stem != event_id:
            raise EventSourceError(
                f"{EVENTS_DIRECTORY}/{path.name} holds event {event_id}; "
                "the file must be named for the event it contains"
            )
        recorded_at = value.get("recorded_at")
        if not isinstance(recorded_at, str) or not recorded_at:
            raise EventSourceError(
                f"{EVENTS_DIRECTORY}/{path.name} has no recorded_at, which is what "
                "orders it; an ISO 8601 date or timestamp is required"
            )
        if event_id in seen:
            raise EventSourceError(f"event {event_id} appears in two files")
        seen[event_id] = path.name
        events.append(value)
    return events


def assemble(hub_root: Path) -> tuple[dict, list[dict]]:
    """Return the ledger bundle and every event, in render order."""
    bundle = _read(hub_root / LEDGER_FILE)
    if not isinstance(bundle, dict):
        raise EventSourceError(f"{LEDGER_FILE} must be a JSON object")
    array_events = bundle.get("events")
    if not isinstance(array_events, list) or not all(
        isinstance(item, dict) for item in array_events
    ):
        raise EventSourceError(f"{LEDGER_FILE} must contain an events array of objects")

    file_events = load_file_events(hub_root)
    array_ids = {
        item["event_id"]
        for item in array_events
        if isinstance(item.get("event_id"), str)
    }
    for event in file_events:
        if event["event_id"] in array_ids:
            raise EventSourceError(
                f"event {event['event_id']} is in both {LEDGER_FILE} and "
                f"{EVENTS_DIRECTORY}/; it can only be recorded once"
            )
    # Content, not history: the array in its recorded order, then the files by
    # when they say they were recorded, with the id as a total tiebreak.
    file_events.sort(key=lambda event: (event["recorded_at"], event["event_id"]))
    return bundle, [*array_events, *file_events]


def array_event_ids(bundle: dict) -> set[str]:
    return {
        item["event_id"]
        for item in bundle.get("events", [])
        if isinstance(item, dict) and isinstance(item.get("event_id"), str)
    }
