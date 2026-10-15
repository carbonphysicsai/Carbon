"""Truthful, named-revision acceptance labels (T06, owner D4).

Reads only public v1 cells. Never dispatches, writes evidence, checks a wallet,
or promotes a fixture, availability flag or successful call into acceptance.
The future T05 writer/matrix may reuse this reader; it owns no writing policy.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

AcceptanceStatus = Literal["UNTESTED", "TESTED"]
ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = "docs/development/evidence"
SCHEMA = "carbon.launchpad.acceptance-cell.v1"
SCOPE = "NAMED_CELL_REVISION_ONLY"
_REVISION = re.compile(r"[0-9a-f]{40}\Z")
_CELL = re.compile(r"[A-Z][A-Z0-9-]{0,47}\Z")
_REQUIRED = {
    "schema",
    "cell",
    "date",
    "revision",
    "machine_kind",
    "result",
    "refusal_code",
    "evidence",
    "within_cap",
    "actor",
}
# Bindings come from LAUNCHPAD_ACCEPTANCE_PLAN sections 3.3-3.5, not from
# adapter availability, source comments or a caller-provided 'verified' flag.
_BINDINGS = {
    "inference": {
        "engy-chat": "I1",
        "chutes": "I2",
        "engy-anthropic": "I3",
        "openai-responses": "I4",
        "anthropic": "I5",
        "openai-compatible-chat": "I6",
        "openai-compatible-responses": "I7",
    },
    "compute": {
        "this-machine-cpu": "C1",
        "CPU": "C1",
        "this-machine-gpu": "C2",
        "ISOLATED_CARRIER_GPU": "C2",
    },
    "agent": {"carbon-graphite": "A1", "graphite": "A1", "hermes": "A2"},
    "client": {"claude-code": "A3", "codex": "A4", "hermes": "A5"},
    "remote": {
        "own-server": "C3",
        "runpod": "C4",
        "vast": "C5",
        "lambda": "C7",
        "lium": "C8",
        "targon": "C9",
    },
}
_FLOWS = {
    "begin": "F03",
    "register": "F03",
    "review": "F05",
    "launch": "F07",
    "practice": "F08",
    "freeze_candidate": "F09",
    "commit": "F10",
    "submit": "F11",
    "observe": "F12",
    "resume": "F14",
}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate acceptance field")
        result[key] = value
    return result


def _nonfinite(_value):
    raise ValueError("nonfinite acceptance field")


@dataclass(frozen=True)
class _Cell:
    cell: str
    revision: str
    result: str
    order: tuple[str, int]
    reference: str


def _cell(document, reference):
    if (
        type(document) is not dict
        or not _REQUIRED <= document.keys()
        or document["schema"] != SCHEMA
        or type(document["cell"]) is not str
        or not _CELL.fullmatch(document["cell"])
        or type(document["revision"]) is not str
        or not _REVISION.fullmatch(document["revision"])
        or document["result"] not in ("PASS", "FAIL", "BLOCKED")
        or type(document["within_cap"]) is not bool
        or type(document["evidence"]) is not dict
        or not document["evidence"]
        or any(
            type(document[k]) is not str or not document[k]
            for k in ("date", "machine_kind", "actor")
        )
        or type(document.get("attempt", 0)) is not int
        or document.get("attempt", 0) < 0
    ):
        raise ValueError("malformed acceptance cell")
    if date.fromisoformat(document["date"]).isoformat() != document["date"]:
        raise ValueError("malformed acceptance date")
    return _Cell(
        document["cell"],
        document["revision"],
        document["result"],
        (document["date"], document.get("attempt", 0)),
        reference,
    )


@dataclass(frozen=True)
class Cells:
    """A snapshot of public records; malformed/ambiguous data never passes."""

    records: dict[str, _Cell]
    usable: bool = True

    def status(self, cell=None):
        record = self.records.get(cell) if self.usable else None
        result = record.result if record else "UNRUN"
        if not self.usable:
            reason = "EVIDENCE_UNUSABLE"
        elif result == "PASS":
            reason = "NAMED_REVISION_PASS"
        else:
            reason = "CELL_" + result if record else "NO_PASS_CELL"
        return {
            "status": "TESTED" if result == "PASS" else "UNTESTED",
            "cell": cell,
            "revision": record.revision if record else None,
            "result": result,
            "scope": SCOPE,
            "evidence": record.reference if record else None,
            "reason": reason,
        }


def load_cells(repository=ROOT):
    """Read fixed public cell paths, never arbitrary references inside evidence.

    Latest means recorded date then attempt. Equal latest identities with
    different bytes are ambiguous, rather than a lexicographic PASS selection.
    A malformed record invalidates the snapshot so an older PASS cannot hide it.
    """
    root = Path(repository)
    records, bodies = {}, {}
    try:
        if any(
            (root / name).is_symlink()
            for name in ("docs", "docs/development", EVIDENCE)
        ):
            raise ValueError("symlink acceptance root")
        for folder in sorted((root / EVIDENCE).glob("launchpad-acceptance-*")):
            if folder.is_symlink() or (folder / "cells").is_symlink():
                raise ValueError("symlink acceptance evidence")
            for path in sorted((folder / "cells").glob("*.json")):
                if path.is_symlink() or not path.is_file():
                    raise ValueError("nonfile acceptance evidence")
                raw = path.read_bytes()
                document = json.loads(
                    raw, object_pairs_hook=_unique, parse_constant=_nonfinite
                )
                record = _cell(document, path.relative_to(root).as_posix())
                previous = records.get(record.cell)
                if previous is None or record.order > previous.order:
                    records[record.cell], bodies[record.cell] = record, raw
                elif record.order == previous.order and raw != bodies[record.cell]:
                    raise ValueError("ambiguous acceptance evidence")
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return Cells({}, usable=False)
    return Cells(records)


def choice(kind, identity, *, cells=None, transport=None):
    cells = load_cells() if cells is None else cells
    if kind == "construction" and identity != "parameters":
        return {
            **cells.status(),
            "result": "BLOCKED",
            "reason": "LEVELS_AFTER_FIRST_REAL_F12_AND_FOLLOWING_WEEK",
        }
    if kind == "level" and identity not in (0, "0"):
        return {
            **cells.status(),
            "result": "BLOCKED",
            "reason": "LEVELS_AFTER_FIRST_REAL_F12_AND_FOLLOWING_WEEK",
        }
    if kind == "bootstrap":
        return {
            **cells.status(),
            "result": "BLOCKED",
            "reason": "LA_F17_REQUIRES_SEPARATE_SECURITY_ACCEPTANCE",
        }
    cell = _BINDINGS.get(kind, {}).get(identity)
    if kind == "remote" and identity == "vast" and transport == "ssh-container":
        cell = "C6"
    return cells.status(cell)


def operation(name, cells=None):
    return (load_cells() if cells is None else cells).status(_FLOWS.get(name))


def project(payload, name=None, *, cells=None):
    """Copy known public choices and add metadata; never change their gates.

    Parallel choice maps preserve existing string-list request contracts.
    No recursive rewrite of scientific results or arbitrary evidence happens.
    """
    if type(payload) is not dict:
        return payload
    cells = load_cells() if cells is None else cells
    result = copy.deepcopy(payload)
    result["acceptance"] = operation(name, cells)
    result["acceptance_status"] = result["acceptance"]["status"]
    result["acceptance_choices"] = {}

    def rows(items, kind):
        if type(items) is not list:
            return
        for row in items:
            if type(row) is not dict:
                continue
            identity = row.get(
                "id", row.get("type", row.get("value", row.get("challenge_id")))
            )
            if type(identity) not in (str, int):
                identity = None
            row["acceptance"] = choice(
                kind, identity, cells=cells, transport=row.get("transport")
            )
            key = kind + "/" + str(identity)
            if kind == "remote":
                key += "/" + str(row.get("transport"))
            result["acceptance_choices"][key] = row["acceptance"]["status"]
            if kind == "compute":
                guides = row.get("guides")
                if type(guides) is dict:
                    rows(guides.get("cards"), "remote")
            connect = row.get("connect")
            if type(connect) is dict:
                rows(connect.get("clients"), "client")

    def setup(document):
        for kind in ("inference", "compute", "agent"):
            rows(document.get(kind), kind)

    setup(result)
    if type(result.get("choices")) is dict:
        setup(result["choices"])
    for key, kind, group in (
        ("agents", "agent", "choices"),
        ("model", "inference", "providers"),
        ("compute", "compute", "choices"),
    ):
        if type(result.get(key)) is dict:
            rows(result[key].get(group), kind)
    rows(result.get("clients"), "client")
    rows(result.get("types"), "construction")
    rows(result.get("levels"), "level")
    rows(result.get("challenges"), "challenge")
    constructions = result.get("construction_options")
    for document in (constructions if type(constructions) is dict else {}).values():
        if type(document) is dict:
            rows(document.get("types"), "construction")
    if type(result.get("steps")) is list:
        for step in result["steps"]:
            if type(step) is dict:
                step["acceptance"] = operation(step.get("id"), cells)
    nxt = result.get("next")
    if type(nxt) is dict and type(nxt.get("options")) is dict:
        options, kind = nxt["options"], nxt.get("step")
        if kind in ("agent", "inference", "compute"):
            items = options.get("provider_id" if kind == "inference" else "choice", [])
            rows(items, kind)
            options["acceptance_by_choice"] = {
                item: choice(kind, item, cells=cells)
                for item in items
                if type(item) is str
            }
            for identity, status in options["acceptance_by_choice"].items():
                result["acceptance_choices"][kind + "/" + identity] = status["status"]
            rows(options.get("setups"), "remote")
    return result


def check_labels(document, *, cells=None, name=None):
    """Refuse a missing/false label on any known offered choice."""
    cells = load_cells() if cells is None else cells
    expected = project(document, name, cells=cells)

    def compare(want, actual):
        if type(want) is dict:
            if type(actual) is not dict:
                raise ValueError("acceptance projection missing")
            for key, value in want.items():
                if key in (
                    "acceptance",
                    "acceptance_status",
                    "acceptance_choices",
                    "acceptance_by_choice",
                ):
                    if actual.get(key) != value:
                        raise ValueError("acceptance label unsupported by named cell")
                elif key in actual:
                    compare(value, actual[key])
        elif type(want) is list and type(actual) is list:
            for value, item in zip(want, actual, strict=True):
                compare(value, item)

    compare(expected, document)


def main():
    """Check the actual shared public choice providers before release rehearsal."""
    from scripts.dev.miner_launchpad.construction_options import for_profile
    from scripts.dev.miner_launchpad.environment_setup import choices

    cells = load_cells()
    offered = choices()
    offered["construction_options"] = for_profile({})
    labelled = project(offered, cells=cells)
    check_labels(labelled, cells=cells)
    # Historical F01/F03 stay visible as named records, never current-release PASS.
    print(
        json.dumps(
            {
                "schema": "carbon.launchpad.release-label-check.v1",
                "status": "TRUTHFUL_LABELS",
                "acceptance": cells.status(),
                "historical_cells": {key: cells.status(key) for key in ("F01", "F03")},
                "qualification": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
