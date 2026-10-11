"""Bounded read-only Git artifact milestones; never adjudicates stage exits."""

import re
import subprocess
from copy import deepcopy
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path, PurePosixPath

from carbon.challenge_pipeline.onboarding import packet

SUPPLEMENT = (
    "docs/development/challenge_pipeline/onboarding-automation/timeline-sources.json"
)
MAX_ROWS = 1000
MAX_BYTES = 300_000


def git(root, *args):
    try:
        result = subprocess.run(
            ["git", "--no-replace-objects", "--no-pager", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=True,
            timeout=10,
        ).stdout
    except (OSError, UnicodeError, subprocess.SubprocessError) as error:
        raise packet.DraftError("Git history unavailable") from error
    if len(result.encode("utf-8")) > MAX_BYTES:
        raise packet.DraftError("Git metadata exceeds bound")
    return result.strip()


def pin(root, ref):
    # No revision expressions, options, shell commands or arbitrary object reads.
    if type(ref) is not str or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9/_.-]{0,159}", ref
    ):
        raise packet.DraftError("named history reference required")
    sha = git(root, "rev-parse", "--verify", ref + "^{commit}")
    if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise packet.DraftError("immutable history identity required")
    return sha


def metadata_path(name):
    # Metadata only. Never opens these files or any bank body, even in old trees.
    if type(name) is not str or not re.fullmatch(r"[A-Za-z0-9_. /-]{1,350}", name):
        raise packet.DraftError("public history path required")
    parts = PurePosixPath(name).parts
    if not parts or any(p in ("", ".", "..") for p in name.split("/")):
        raise packet.DraftError("public history path required")
    allowed = (
        name.startswith(
            (
                "docs/development/",
                "Design_Specs/",
                ".agent/decisions/",
                ".agent/tickets/",
                "carbon/challenge_readiness/records/",
            )
        )
        or name == "carbon/battery/reference.py"
    )
    if not allowed or any(
        p.lower() in {"hidden", "protected", "secrets", ".git", ".aws"} for p in parts
    ):
        raise packet.DraftError("history source refused")
    return name


def utc(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise packet.DraftError("timezone-aware Git time required")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def additions(root, sha, relative, *, main=False):
    args = [
        "log",
        "--reverse",
        "--topo-order",
        "--no-renames",
        "--diff-filter=A",
        f"--max-count={MAX_ROWS + 1}",
        "--format=%H|%aI|%cI|%P",
    ]
    args.append("--first-parent" if main else "--no-merges")
    output = git(root, *args, sha, "--", relative)
    lines = output.splitlines() if output else []
    if len(lines) > MAX_ROWS:
        raise packet.DraftError("history addition bound exceeded")
    rows = []
    for line in lines:
        commit, authored, committed, parents = line.split("|")
        rows.append(
            {
                "commit": commit,
                "authored_utc": utc(authored),
                "committed_utc": utc(committed),
                "parents": parents.split(),
                "kind": (
                    "MERGE_INTEGRATION" if len(parents.split()) > 1 else "DIRECT_COMMIT"
                ),
            }
        )
    return rows


def artifact(root, relative, head, main):
    metadata_path(relative)
    out = {
        "path": relative,
        "first_recorded": None,
        "first_main_integration": None,
        "accepted_stage_completion_utc": None,
    }
    try:
        starts = additions(root, head, relative)
        integrated = additions(root, main, relative, main=True) if main else []
        # A historical rename is ambiguous: we deliberately do not follow it into
        # unallowlisted old paths or silently stitch different versioned contracts.
        renamed = bool(
            git(
                root,
                "log",
                "--max-count=1",
                "--format=%H",
                "--diff-filter=R",
                "--follow",
                head,
                "--",
                relative,
            )
        )
        out.update(
            first_recorded=starts[0] if starts else None,
            first_main_integration=integrated[0] if integrated else None,
            path_additions=len(starts),
            main_additions=len(integrated),
            rename_seen=renamed,
        )
        out["coverage"] = (
            "AMBIGUOUS_RENAME_OR_MULTIPLE_ADDITIONS"
            if renamed or len(starts) > 1 or len(integrated) > 1
            else (
                "PATH_HISTORY_OBSERVED"
                if starts
                else "NO_ADDITION_IN_AVAILABLE_HISTORY"
            )
        )
        out["main_state"] = (
            "INTEGRATION_OBSERVED"
            if integrated
            else "NOT_INTEGRATED_OR_HISTORY_UNAVAILABLE"
        )
    except packet.DraftError:
        out["coverage"] = "HISTORY_UNAVAILABLE_OR_BOUNDED"
    return out


@lru_cache(maxsize=512)
def complete_artifact(root, relative, head, main):
    # Only complete histories are cached, and both refs are immutable SHAs.
    # Unshallowing cannot reuse a cached partial view. No file bytes are cached.
    return artifact(root, relative, head, main)


def generate(root: Path, challenge, stages, *, main_ref="origin/main", head_ref="HEAD"):
    """Stage paths only; optional public supplement adds historical versions."""
    root = root.resolve()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", challenge):
        raise packet.DraftError("planning challenge required")
    head, main, shallow = None, None, None
    try:
        head = pin(root, head_ref)
        shallow = git(root, "rev-parse", "--is-shallow-repository") == "true"
    except packet.DraftError:
        pass
    try:
        main = pin(root, main_ref)
    except packet.DraftError:
        pass
    bindings = {s["id"]: [a["path"] for a in s["artifacts"]] for s in stages}
    supplement_digest = None
    supplement_path = root / SUPPLEMENT
    if supplement_path.is_file():
        doc = packet.read_json(packet.source_path(root, SUPPLEMENT))
        if (
            set(doc) != {"schema", "challenges"}
            or doc["schema"] != "carbon.onboarding.history-sources.v1"
            or type(doc["challenges"]) is not dict
        ):
            raise packet.DraftError("closed history supplement required")
        extra = doc["challenges"].get(challenge, {})
        if type(extra) is not dict or set(extra) - set(bindings):
            raise packet.DraftError("known stage history paths required")
        for stage, paths in extra.items():
            if type(paths) is not list:
                raise packet.DraftError("history path list required")
            bindings[stage] = list(dict.fromkeys(bindings[stage] + paths))
        supplement_digest = packet.digest(supplement_path.read_bytes())
    rows, cache = [], {}
    for stage in stages:
        paths = bindings[stage["id"]]
        if len(paths) > 20:
            raise packet.DraftError("history artifact count exceeds bound")
        artifacts = []
        for relative in paths:
            metadata_path(relative)
            if relative not in cache:
                cache[relative] = (
                    (complete_artifact if shallow is False else artifact)(
                        root, relative, head, main
                    )
                    if head
                    else {
                        "path": relative,
                        "coverage": "GIT_UNAVAILABLE",
                        "first_recorded": None,
                        "first_main_integration": None,
                        "accepted_stage_completion_utc": None,
                    }
                )
            artifacts.append(deepcopy(cache[relative]))
        rows.append(
            {
                "id": stage["id"],
                "artifacts": artifacts,
                "accepted_entry_utc": None,
                "accepted_exit_utc": None,
                "stage_cycle_seconds": None,
                "effort_person_hours": None,
            }
        )
    return {
        "schema": "carbon.onboarding.artifact-timeline.v1",
        "challenge": challenge,
        "basis": {
            "head": head,
            "main": main,
            "shallow": shallow,
            "supplement_sha256": supplement_digest,
        },
        "coverage": (
            "PARTIAL_SHALLOW_HISTORY"
            if shallow
            else "PINNED_GIT_HISTORY" if head else "GIT_UNAVAILABLE"
        ),
        "stages": rows,
        "brief_to_tested_seconds": None,
        "human_effort_saved_hours": None,
        "limits": [
            "Artifact creation and integration are not stage entry or completion.",
            "First is path-history topology, not oldest wall-clock timestamp; renames and repeated additions are ambiguous.",
            "Main integration time is Git committer time, not GitHub mergedAt; main is the locally available pinned ref, never fetched here.",
            "Missing or shallow history cannot establish absence. Legacy versions and pre-brief reusable infrastructure do not qualify the current contract.",
            "Calendar milestones are not effort, blocked time, spend or measured time saved. TESTED requires #970 plus the owner's cheap-baseline comparison.",
        ],
    }
