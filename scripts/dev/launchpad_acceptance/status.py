"""Read-only named-revision scoreboard and seven evidence predicates.

The result describes recorded engineering evidence, never launch permission.
No missing owner acknowledgment or disposition is inferred from prose.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .cell import public_reference
from .matrix import AGENTS, COMPUTE, D1, D5, FLOWS, MATRIX
from .release_check import (
    EVIDENCE,
    ROOT,
    _cell,
    _nonfinite,
    _unique,
    check_capture,
    load_cells,
)

_REVISION = re.compile(r"[0-9a-f]{40}\Z")


def read_public_json(reference, repository=ROOT):
    """Only explicitly supplied files in the public Launchpad evidence tree."""
    if not public_reference(reference) or not re.fullmatch(
        r"docs/development/evidence/launchpad-acceptance-\d{4}-\d{2}-\d{2}/[A-Za-z0-9_./-]+\.json",
        reference,
    ):
        raise ValueError("PUBLIC_LAUNCHPAD_JSON_REQUIRED")
    path = _public_path(reference, repository)
    if path.stat().st_size > 2**20:
        raise ValueError("PUBLIC_EVIDENCE_TOO_LARGE")
    return json.loads(
        path.read_bytes(), object_pairs_hook=_unique, parse_constant=_nonfinite
    )


def _public_path(reference, repository):
    root = Path(repository)
    if root.is_symlink() or not public_reference(reference):
        raise ValueError("INVALID_PUBLIC_REFERENCE")
    path = root
    for part in reference.split("#", 1)[0].split("/"):
        path = path / part
        if path.is_symlink():
            raise ValueError("SYMLINK_PUBLIC_EVIDENCE")
    if not path.is_file():
        raise ValueError("PUBLIC_EVIDENCE_MISSING")
    return path


def _proof(proof, repository, *, marker=None, owner=False):
    if type(proof) is not dict or set(proof) != {"reference", "sha256"}:
        return False
    reference = proof["reference"]
    if type(reference) is not str or (
        owner and not reference.startswith(".agent/decisions/")
    ):
        return False
    try:
        path = _public_path(reference, repository)
        if path.stat().st_size > 2**20:
            return False
        raw = path.read_bytes()
        return (
            type(proof["sha256"]) is str
            and hashlib.sha256(raw).hexdigest() == proof["sha256"]
            and (
                marker is None
                or re.search(
                    r"(?<![A-Za-z0-9-])" + re.escape(marker) + r"(?![A-Za-z0-9-])",
                    raw.decode("utf-8"),
                )
            )
        )
    except (OSError, ValueError, TypeError):
        return False


def _history(cells, repository):
    """Inventory after the authoritative reader succeeds, using its validator.

    This does not select latest records or serve as a fallback on reader failure.
    It preserves failed attempts alongside the shared Cells.status selection.
    """
    if not cells.usable:
        return [], False
    rows = []
    try:
        for folder in sorted(
            (Path(repository) / EVIDENCE).glob("launchpad-acceptance-*")
        ):
            for path in sorted((folder / "cells").glob("*.json")):
                reference = path.relative_to(repository).as_posix()
                checked = _public_path(reference, repository)
                document = json.loads(
                    checked.read_bytes(),
                    object_pairs_hook=_unique,
                    parse_constant=_nonfinite,
                )
                record = _cell(document, reference)
                rows.append(
                    {
                        "cell": record.cell,
                        "result": record.result,
                        "revision": record.revision,
                        "date": record.order[0],
                        "attempt": record.order[1],
                        "evidence": reference,
                    }
                )
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return [], False
    return rows, True


def _strings(value):
    if type(value) is str:
        yield value
    elif type(value) is dict:
        for child in value.values():
            yield from _strings(child)
    elif type(value) is list:
        for child in value:
            yield from _strings(child)


def _clients(value):
    if type(value) is dict:
        if type(value.get("clients")) is list:
            yield from value["clients"]
        for key, child in value.items():
            if key != "clients":
                yield from _clients(child)
    elif type(value) is list:
        for child in value:
            yield from _clients(child)


def _selected_refusal(cells, identity, repository):
    record = cells.records.get(identity) if cells.usable else None
    if record is None:
        return None
    try:
        path = _public_path(record.reference, repository)
        document = json.loads(
            path.read_bytes(), object_pairs_hook=_unique, parse_constant=_nonfinite
        )
        if _cell(document, record.reference) == record:
            return document.get("refusal_code")
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        pass
    return None


def scoreboard(
    repository=ROOT, *, revision=None, door_capture=None, completion_evidence=None
):
    """Compute evidence states; false/unknown predicates never become permission."""
    root = Path(repository)
    if revision is not None and (
        type(revision) is not str or not _REVISION.fullmatch(revision)
    ):
        raise ValueError("EXACT_SOURCE_REVISION_REQUIRED")
    cells = load_cells(root)
    rows = []
    for definition in MATRIX:
        status = cells.status(definition.cell)
        if definition.blocked_reason:
            status = {
                **status,
                "status": "UNTESTED",
                "result": "BLOCKED",
                "reason": definition.blocked_reason,
            }
        rows.append(
            {
                **status,
                "family": definition.family,
                "option": definition.option,
                "pass_means": definition.pass_means,
                "required_evidence_fields": list(definition.required_evidence_fields),
                "base_required": definition.base_required,
                "owner": (
                    "Carbon Validator / owner"
                    if definition.family in ("level", "security")
                    else "Root / Platform2"
                ),
            }
        )
    predicates = []

    def line(number, name, owner, examined, missing, *, unknown=False):
        predicates.append(
            {
                "line": number,
                "predicate": name,
                "owner": owner,
                "result": "UNKNOWN" if unknown else "UNMET" if missing else "PASS",
                "examined": examined,
                "missing": missing,
            }
        )

    def required(definitions, number, name):
        ids = [entry.cell for entry in definitions]
        missing = [cell for cell in ids if cells.status(cell)["result"] != "PASS"]
        line(number, name, "Root / Platform2", ids, missing)

    required(FLOWS, 1, "Base flows F01-F15 PASS (owner D6)")
    required(
        [entry for entry in COMPUTE if entry.base_required],
        2,
        "Tier-1 compute C1-C5 PASS",
    )
    supplied = (
        type(completion_evidence) is dict
        and completion_evidence.get("schema")
        == "carbon.launchpad.completion-evidence.v1"
        and type(revision) is str
        and _REVISION.fullmatch(revision)
        and completion_evidence.get("source_revision") == revision
        and not set(completion_evidence)
        - {"schema", "source_revision", "key_blocks", "findings"}
    )
    evidence = completion_evidence if supplied else {}
    key_blocks = evidence.get("key_blocks", {})
    missing = []
    for index in range(1, 8):
        cell = "I" + str(index)
        result = cells.status(cell)["result"]
        acknowledged = (
            index >= 3
            and result == "BLOCKED"
            and _selected_refusal(cells, cell, root) == "OWNER_KEY_UNAVAILABLE"
            and type(key_blocks) is dict
            and type(key_blocks.get(cell)) is dict
            and key_blocks[cell].get("reason") == "OWNER_KEY_UNAVAILABLE"
            and _proof(
                key_blocks[cell].get("owner_acknowledgment"),
                root,
                marker=cell,
                owner=True,
            )
        )
        if result != "PASS" and not acknowledged:
            missing.append(cell)
    line(
        3,
        "I1/I2 PASS; I3-I7 PASS or key-blocked with recorded owner awareness",
        "Root / owner",
        ["I" + str(i) for i in range(1, 8)],
        missing,
    )
    required([entry for entry in AGENTS if entry.base_required], 4, "Agents A1-A4 PASS")
    capture_valid = False
    if door_capture is not None:
        try:
            check_capture(door_capture, revision, cells=cells)
            capture_valid = True
        except (ValueError, TypeError, KeyError, RecursionError):
            pass
    clients = (
        [row for row in _clients(door_capture) if type(row) is dict]
        if capture_valid
        else []
    )
    expected_clients = {"claude-code", "codex", "hermes"}
    seen = {
        row.get("id")
        for row in clients
        if type(row.get("id")) is str and row["id"] in expected_clients
    }
    bad_clients = [
        (
            row["id"]
            if type(row.get("id")) is str and row["id"] in expected_clients
            else "UNKNOWN_CLIENT"
        )
        for row in clients
        if type(row.get("id")) is not str
        or row["id"] not in expected_clients
        or type(row.get("snippets")) is not list
        or not row["snippets"]
        or any(
            type(snippet) is not dict
            or type(snippet.get("text")) is not str
            or not snippet["text"]
            for snippet in row.get("snippets", [])
            if type(row.get("snippets")) is list
        )
        or type(row.get("verified")) is not str
        or not row["verified"]
        or bool(row.get("unverified"))
        or any("UNVERIFIED" in text.upper() for text in _strings(row))
    ]
    missing_clients = sorted(expected_clients - seen) + bad_clients
    line(
        5,
        "No UNVERIFIED mcp_connect marker in actual captured snippets",
        "Platform2 / client owner",
        sorted(seen),
        missing_clients or ([] if clients else ["SNIPPET_CAPTURE_MISSING"]),
        unknown=not capture_valid,
    )
    findings = set()
    registers_usable = True
    try:
        for folder in sorted((root / EVIDENCE).glob("launchpad-acceptance-*")):
            reference = (folder / "FINDINGS.md").relative_to(root).as_posix()
            if not (folder / "FINDINGS.md").exists():
                continue
            text = _public_path(reference, root).read_text(encoding="utf-8")
            findings.update(re.findall(r"^##\s+(LA-F\d+):", text, re.MULTILINE))
    except (OSError, ValueError, UnicodeError):
        registers_usable = False
    dispositions = evidence.get("findings", {})
    unresolved = []
    for finding in sorted(findings - {"LA-F17"}):
        disposition = dispositions.get(finding) if type(dispositions) is dict else None
        if (
            type(disposition) is not dict
            or disposition.get("disposition") not in ("FIXED", "OWNER_ACCEPTED")
            or not _proof(
                disposition.get("proof"),
                root,
                marker=finding,
                owner=disposition.get("disposition") == "OWNER_ACCEPTED",
            )
        ):
            unresolved.append(finding)
    if not findings or not registers_usable:
        unresolved.append("FINDINGS_REGISTER_UNAVAILABLE")
    line(
        6,
        "Every base finding has recorded fix/owner disposition (D1 excludes LA-F17)",
        "Root / finding owner",
        sorted(findings - {"LA-F17"}),
        unresolved,
        unknown=not supplied or not registers_usable,
    )
    line(
        7,
        "T06 actual emitted-door release labels pass at the selected revision",
        "Root / release owner",
        ["8 actual HTTP/MCP surfaces"] if capture_valid else [],
        [] if capture_valid else ["VALID_EXACT_REVISION_CAPTURE_REQUIRED"],
        unknown=door_capture is None,
    )
    history, history_usable = _history(cells, root)
    return {
        "schema": "carbon.launchpad.acceptance-status.v1",
        "source_revision": revision,
        "evidence_usable": cells.usable,
        "cells": rows,
        "history": history,
        "history_usable": history_usable,
        "completion": predicates,
        "recorded_predicate": (
            "PASS"
            if cells.usable and all(row["result"] == "PASS" for row in predicates)
            else "UNMET"
        ),
        "scope": "NAMED_CELL_REVISIONS_ONLY",
        "qualification": False,
        "launch_authorized": False,
        "nonblocking": {"tier2": ["C6", "C7", "C8", "C9"], "levels": D5, "LA-F17": D1},
    }


def render(report):
    lines = [
        "Launchpad acceptance: named cell revisions only; no launch/qualification authority."
    ]
    for row in report["cells"]:
        lines.append(
            f"{row['cell']:7} {row['result']:7} {row['revision'] or 'UNRECORDED':40} {row['option']}"
        )
    lines.append("Recorded attempts (including failures):")
    if not report["history_usable"]:
        lines.append("  History inventory unavailable; no absence-of-failures claim.")
    for row in report["history"]:
        lines.append(
            f"  {row['cell']} {row['result']} {row['revision'] or 'UNRECORDED'} {row['evidence']}"
        )
    lines.append("Plan 3.6 predicates:")
    for row in report["completion"]:
        lines.append(
            f"  {row['line']}. {row['result']}: {row['predicate']}; owner={row['owner']}; examined={len(row['examined'])}; unmet={','.join(row['missing']) or 'none'}"
        )
    lines.append(
        "Recorded predicate: "
        + report["recorded_predicate"]
        + "; qualification=false; launch_authorized=false"
    )
    return "\n".join(lines)
