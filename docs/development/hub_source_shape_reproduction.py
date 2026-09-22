#!/usr/bin/env python3
"""Reproduce the Development Hub ledger's merge-loss modes, and their absence.

Evidence for `CARBON_HUB_SOURCE_SHAPE_PROPOSAL.md`. Read-only with respect to
this repository: everything happens in a temporary git repository built from a
copy of the current Hub sources, which is removed afterwards.

    python3 docs/development/hub_source_shape_reproduction.py

It prints, for each scenario, what the merge produced and what
`validate_hub.py`'s immutability comparison would have reported. The comparison
is reimplemented here rather than imported, deliberately: a reviewer checking
whether the claim is true should be able to see the whole comparison in front of
them, and the point being made is about which two trees it compares.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
LEDGER = "docs/development/carbon_hub/data/change_events.json"


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.email=demo@local", "-c", "user.name=demo", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout


def event(event_id: str, map_ref: str) -> str:
    return json.dumps(
        {
            "map_ref": map_ref,
            "event_type": "evidence",
            "event_id": event_id,
            "owner_lane": "engineering",
            "status": "implemented",
            "summary": "Synthetic event for the Hub source-shape reproduction.",
            "primary_detail": "docs/development/carbon_hub/README.md",
            "affects": [map_ref],
            "supersedes": None,
        },
        indent=2,
    )


def append_to_array(repo: Path, event_id: str, map_ref: str) -> None:
    path = repo / LEDGER
    text = path.read_text()
    block = "\n".join("    " + line for line in event(event_id, map_ref).split("\n"))
    tail = "\n  ]\n}"
    path.write_text(text[: text.rindex(tail)] + ",\n" + block + tail + "\n")


def ids(text: str) -> dict[str, dict]:
    return {e["event_id"]: e for e in json.loads(text)["events"]}


def immutability_report(base: str, candidate: str) -> str:
    """Exactly what validate_hub.py compares: the candidate against its base."""
    prior, current = ids(base), ids(candidate)
    removed = sorted(set(prior) - set(current))
    rewritten = sorted(k for k in set(prior) & set(current) if prior[k] != current[k])
    added = sorted(set(current) - set(prior))
    verdict = "FAIL" if removed or rewritten else "pass"
    return (
        f"      removed={removed or 'none'} rewritten={rewritten or 'none'} "
        f"added={added or 'none'} -> {verdict}"
    )


def prepare(root: Path) -> Path:
    repo = root / "demo"
    (repo / "docs/development/carbon_hub").mkdir(parents=True)
    shutil.copytree(
        REPOSITORY / "docs/development/carbon_hub/data",
        repo / "docs/development/carbon_hub/data",
    )
    git(repo, "init", "-q", ".")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "hub sources as they stand")
    return repo


def current_shape(repo: Path) -> None:
    base = git(repo, "show", f"HEAD:{LEDGER}")
    git(repo, "checkout", "-q", "-b", "workstream-a")
    append_to_array(repo, "WS-A-EVENT-01", "SYSTEM/BUSINESS-AUTHORITY")
    git(repo, "commit", "-qam", "A records its event")
    a_side = git(repo, "show", f"HEAD:{LEDGER}")
    git(repo, "checkout", "-q", "HEAD~1")
    git(repo, "checkout", "-q", "-b", "workstream-b")
    append_to_array(repo, "WS-B-EVENT-01", "SYSTEM/AGENT-EXECUTION")
    git(repo, "commit", "-qam", "B records its event")
    b_side = git(repo, "show", f"HEAD:{LEDGER}")
    git(repo, "checkout", "-q", "workstream-a")
    merge = subprocess.run(
        ["git", "merge", "--no-edit", "workstream-b"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    conflicted = "CONFLICT" in merge.stdout + merge.stderr
    print("  current shape: one shared array")
    print(f"    two independently appended events conflict: {conflicted}")
    text = (repo / LEDGER).read_text()
    hunks = text.count("<<<<<<<")
    print(f"    conflict hunks inside the one new object: {hunks}")
    print("    (git interleaves the two events field by field, so the resolver")
    print("     is choosing lines inside one record, not between two records)")

    # Resolution that keeps this side. The other event is destroyed.
    kept = a_side
    print("\n    resolution 'keep our side' -> B's event is gone")
    print("      as a sibling PR, B never reached main:")
    print(immutability_report(base, kept))
    print("      had B already merged to main:")
    print(immutability_report(b_side, kept))
    git(repo, "merge", "--abort")


def proposed_shape(repo: Path) -> None:
    git(repo, "checkout", "-q", "-B", "split-base", "main")
    ledger = json.loads((repo / LEDGER).read_text())
    events = repo / "docs/development/carbon_hub/data/events"
    events.mkdir(parents=True, exist_ok=True)
    for item in ledger["events"]:
        (events / f"{item['event_id']}.json").write_text(
            json.dumps(item, indent=2, ensure_ascii=False) + "\n"
        )
    (repo / LEDGER).unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "proposed shape: one file per event")

    git(repo, "checkout", "-q", "-b", "split-a")
    (events / "WS-A-EVENT-01.json").write_text(
        event("WS-A-EVENT-01", "SYSTEM/BUSINESS-AUTHORITY") + "\n"
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "A records its event")
    git(repo, "checkout", "-q", "split-base")
    git(repo, "checkout", "-q", "-b", "split-b")
    (events / "WS-B-EVENT-01.json").write_text(
        event("WS-B-EVENT-01", "SYSTEM/AGENT-EXECUTION") + "\n"
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "B records its event")
    git(repo, "checkout", "-q", "split-a")
    merge = subprocess.run(
        ["git", "merge", "--no-edit", "split-b"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    conflicted = "CONFLICT" in merge.stdout + merge.stderr
    survived = sorted(p.name for p in events.glob("WS-*.json"))
    print("\n  proposed shape: one file per event")
    print(f"    the same two events conflict: {conflicted}")
    print(f"    events present after the merge: {survived}")
    print("    (no contested region, so there is no resolution to get wrong)")


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="carbon-hub-shape-"))
    try:
        repo = prepare(root)
        head = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
        if head != "main":
            git(repo, "branch", "-m", head, "main")
        print(
            f"Hub ledger under test: {len(ids(git(repo, 'show', f'HEAD:{LEDGER}')))} events\n"
        )
        current_shape(repo)
        proposed_shape(repo)
        print("\nNothing in this repository was modified.")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
