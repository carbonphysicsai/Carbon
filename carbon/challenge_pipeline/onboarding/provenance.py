"""Provenance and freshness of a committed onboarding evidence pack.

A pack is an immutable historical record (invariant 10: historical evidence is
versioned; a fact about what the tools produced on one day is not invalidated by later
code). Its checks are therefore about provenance and internal consistency:

* every output's recorded digest matches the committed bytes;
* every recorded input digest is well formed and, where git history allows, matches the
  file AT the pack's `authority_main` (never at HEAD); an input that lives inside the
  pack itself is checked against its committed bytes;
* the run record is complete.

Freshness is a reported status, never a failure: `STALE_TOOLS`, listing the changed
paths, when a recorded input differs from the current tree. A fresh run is a new,
versioned pack.

Read-only: it reads the run record, the files it names, and `git show` of
`authority_main`. It runs no solver and touches no network.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

COMMIT = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
REQUIRED = (
    "schema",
    "ticket",
    "status",
    "authority_main",
    "recorded_at",
    "inputs_and_tools",
    "outputs",
)
CURRENT = "CURRENT"
STALE_TOOLS = "STALE_TOOLS"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_show(root, commit, relative):
    """`(bytes | None, history_available)`: the file at `commit`, and whether git
    could answer at all (a shallow clone or a missing commit cannot)."""
    try:
        have = subprocess.run(
            ["git", "cat-file", "-e", commit + "^{commit}"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if have.returncode != 0:
            return None, False
        shown = subprocess.run(
            ["git", "show", f"{commit}:{relative}"],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None, False
    return (shown.stdout if shown.returncode == 0 else None), True


def check(root, run_relative):
    """The provenance problems of the pack whose run record is `run_relative`, and
    its freshness. Never raises for a malformed record: a problem is reported."""
    root = Path(root)
    problems, changed = [], []
    try:
        run = json.loads((root / run_relative).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "provenance_problems": ["run record unreadable"],
            "history_checked": False,
            "freshness": STALE_TOOLS,
            "changed_paths": [],
        }
    if type(run) is not dict:
        problems.append("run record is not an object")
        run = {}
    for key in REQUIRED:
        if run.get(key) in (None, "", {}):
            problems.append(f"run record is incomplete: {key} missing or empty")
    authority = run.get("authority_main")
    if not (type(authority) is str and COMMIT.fullmatch(authority)):
        problems.append("authority_main is not a 40-hex commit")
        authority = None
    pack_folder = str(Path(run_relative).parent.as_posix()) + "/"
    history_checked = authority is not None
    outputs = run.get("outputs") if type(run.get("outputs")) is dict else {}
    inputs = (
        run.get("inputs_and_tools") if type(run.get("inputs_and_tools")) is dict else {}
    )
    for relative, recorded in sorted(outputs.items()):
        if not (type(recorded) is str and DIGEST.fullmatch(recorded)):
            problems.append(f"output digest malformed: {relative}")
            continue
        try:
            actual = digest((root / relative).read_bytes())
        except OSError:
            problems.append(f"output missing: {relative}")
            continue
        if actual != recorded:
            problems.append(f"output digest differs from committed bytes: {relative}")
    for relative, recorded in sorted(inputs.items()):
        if not (type(recorded) is str and DIGEST.fullmatch(recorded)):
            problems.append(f"input digest malformed: {relative}")
            continue
        try:
            current = digest((root / relative).read_bytes())
        except OSError:
            current = None
        if relative.startswith(pack_folder):
            # Part of the pack itself: its committed bytes are the record.
            if current != recorded:
                problems.append(f"pack input differs from committed bytes: {relative}")
            continue
        if authority is not None:
            blob, available = _git_show(root, authority, relative)
            if not available:
                history_checked = False
            elif blob is None:
                problems.append(f"input absent at authority_main: {relative}")
            elif digest(blob) != recorded:
                problems.append(f"input digest differs at authority_main: {relative}")
        if current != recorded:
            changed.append(relative)
    return {
        "provenance_problems": problems,
        "history_checked": history_checked,
        "freshness": STALE_TOOLS if changed else CURRENT,
        "changed_paths": changed,
    }


def render(report):
    lines = [
        f"freshness: {report['freshness']}",
        f"history checked at authority_main: {report['history_checked']}",
    ]
    if report["changed_paths"]:
        lines.append("changed since the pack (a fresh run is a new, versioned pack):")
        lines += ["  " + path for path in report["changed_paths"]]
    if report["provenance_problems"]:
        lines.append("PROVENANCE PROBLEMS:")
        lines += ["  " + problem for problem in report["provenance_problems"]]
    else:
        lines.append("provenance: consistent")
    return "\n".join(lines)
