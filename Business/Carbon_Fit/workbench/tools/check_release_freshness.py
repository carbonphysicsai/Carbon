#!/usr/bin/env python3
"""Read-only freshness gate for the current Workbench release artifacts.

The existing determinism test proves that repeating a build reproduces its own
output. It cannot prove that the artifacts tracked in the repository were built
from the sources tracked beside them, because it runs a build before capturing
its first comparison bytes and therefore overwrites the very artifact under
test. A stale artifact that rebuilds identically twice still passes it.

This gate supplies the missing condition:

    tracked artifact bytes == output generated from the tracked source inputs

It stages the tracked Workbench sources into a throwaway directory outside the
repository, regenerates there, and compares. It never writes to a tracked file,
so a failure reports staleness instead of quietly repairing it.

Exit status: 0 fresh, 1 stale, 2 the check could not run.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Artifacts generated from tracked sources, with the generator that emits them.
GENERATED: dict[str, str] = {
    "Carbon_Opportunity_Workbench.html": "tools/build.py",
    "Carbon_Client_Intake_Preview.html": "tools/build.py",
    "Carbon_Client_Pilot_Designer_Preview.html": "tools/build.py",
    "data/goal_workspace.schema.json": "tools/build_goal_schema.py",
    "data/goal_constants.json": "tools/build_goal_schema.py",
    "MANIFEST.json": "tools/package_release.py",
    "Carbon_Physics_Goal_Workbench_v0_10.zip": "tools/package_release.py",
}

GENERATORS = (
    "tools/build.py",
    "tools/build_goal_schema.py",
    "tools/package_release.py",
)

MANIFEST_NAME = "MANIFEST.json"
ARCHIVE_NAME = "Carbon_Physics_Goal_Workbench_v0_10.zip"

# package_release.py records the Git HEAD that packaged the release. A commit
# cannot contain its own hash, so this field is packaging provenance and never
# evidence of staleness. Comparing it would demand a self-referential repin on
# every commit, so it is normalised on both sides instead.
PROVENANCE_FIELDS = ("integration_revision_at_packaging",)


class FreshnessError(RuntimeError):
    """The gate could not establish a trustworthy comparison."""


def tracked_sources() -> list[str]:
    """Workbench paths tracked by Git, relative to the workbench root.

    The release archive is assembled by globbing the workbench directory, so
    generating from the working tree would let untracked scratch files, local
    build output or credentials reach the comparison. Restricting the staged
    set to tracked paths keeps the check reproducible and keeps stray files out
    of the regenerated archive.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "."],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise FreshnessError(f"could not list tracked Workbench sources: {error}")
    paths = [entry for entry in result.stdout.split("\0") if entry]
    if not paths:
        raise FreshnessError("no tracked Workbench sources were found")
    return paths


def stage(destination: Path, sources: list[str]) -> None:
    """Copy tracked sources into a throwaway tree outside the repository."""
    for relative in sources:
        source = ROOT / relative
        if not source.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def generate(destination: Path) -> None:
    """Run each generator inside the staged copy."""
    for generator in GENERATORS:
        script = destination / generator
        if not script.is_file():
            raise FreshnessError(f"generator {generator} is not tracked")
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=destination,
            text=True,
            capture_output=True,
            check=False,
        )
        # Report the real child status rather than trusting a shell pipeline.
        if completed.returncode != 0:
            raise FreshnessError(
                f"{generator} exited {completed.returncode}: "
                f"{(completed.stderr or completed.stdout).strip()[:400]}"
            )


def normalise_manifest(raw: bytes) -> bytes:
    """Blank packaging provenance so the comparison stays acyclic."""
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FreshnessError(f"manifest is not readable JSON: {error}")
    for field in PROVENANCE_FIELDS:
        if field in document:
            document[field] = "<normalised-for-comparison>"
    return json.dumps(document, indent=2, sort_keys=True).encode("utf-8")


def archive_members(raw: bytes) -> dict[str, bytes]:
    """Return archive members, with the embedded manifest normalised."""
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        for name in sorted(bundle.namelist()):
            payload = bundle.read(name)
            if name.endswith("/" + MANIFEST_NAME):
                payload = normalise_manifest(payload)
            members[name] = payload
    return members


def describe_archive_drift(tracked: bytes, rebuilt: bytes) -> list[str]:
    """Explain how two archives differ, member by member."""
    before, after = archive_members(tracked), archive_members(rebuilt)
    missing = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    changed = sorted(
        name for name in set(before) & set(after) if before[name] != after[name]
    )
    detail: list[str] = []
    for name in missing:
        detail.append(f"    no longer generated: {name}")
    for name in added:
        detail.append(f"    missing from the tracked archive: {name}")
    for name in changed:
        detail.append(f"    content differs: {name}")
    return detail


def compare(destination: Path) -> list[str]:
    """Return a report of every stale artifact; empty means fresh."""
    stale: list[str] = []
    for relative, generator in sorted(GENERATED.items()):
        tracked_path = ROOT / relative
        rebuilt_path = destination / relative
        if not rebuilt_path.is_file():
            stale.append(f"  {relative}: {generator} did not generate it")
            continue
        if not tracked_path.is_file():
            stale.append(f"  {relative}: generated but not tracked ({generator})")
            continue
        tracked_bytes = tracked_path.read_bytes()
        rebuilt_bytes = rebuilt_path.read_bytes()
        if relative == ARCHIVE_NAME:
            # The archive embeds the manifest, so raw bytes carry the packaging
            # provenance field. Compare member payloads with that field
            # normalised, or every commit would look stale.
            equal = archive_members(tracked_bytes) == archive_members(rebuilt_bytes)
        elif relative == MANIFEST_NAME:
            equal = normalise_manifest(tracked_bytes) == normalise_manifest(
                rebuilt_bytes
            )
        else:
            equal = tracked_bytes == rebuilt_bytes
        if equal:
            continue
        entry = (
            f"  {relative}: tracked bytes differ from {generator} output "
            f"({tracked_path.stat().st_size} tracked, "
            f"{rebuilt_path.stat().st_size} rebuilt)"
        )
        if relative == ARCHIVE_NAME:
            detail = describe_archive_drift(
                tracked_path.read_bytes(), rebuilt_path.read_bytes()
            )
            entry = "\n".join([entry, *detail])
        stale.append(entry)
    return stale


def check(keep: bool = False) -> list[str]:
    """Stage, regenerate and compare without touching a tracked file."""
    sources = tracked_sources()
    # Outside the repository, so the generators cannot resolve its Git HEAD and
    # cannot reach files that are not part of the staged source set.
    destination = Path(tempfile.mkdtemp(prefix="carbon-workbench-freshness-"))
    try:
        stage(destination, sources)
        generate(destination)
        return compare(destination)
    finally:
        if keep:
            print(f"staged comparison tree retained at {destination}")
        else:
            shutil.rmtree(destination, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that the tracked Workbench release artifacts match what "
            "their tracked sources generate. Writes nothing."
        )
    )
    parser.add_argument(
        "--keep-comparison-tree",
        action="store_true",
        help="retain the throwaway tree for inspection",
    )
    options = parser.parse_args()
    try:
        stale = check(keep=options.keep_comparison_tree)
    except FreshnessError as error:
        print(
            f"Workbench release freshness check could not run: {error}",
            file=sys.stderr,
        )
        return 2
    if stale:
        print(
            "Workbench release artifacts are stale; they do not match their "
            "tracked sources:",
            file=sys.stderr,
        )
        for entry in stale:
            print(entry, file=sys.stderr)
        print(
            "\nRegenerate with tools/build.py, tools/build_goal_schema.py and "
            "tools/package_release.py, then review the delta before committing.",
            file=sys.stderr,
        )
        return 1
    print(f"Workbench release artifacts are current: {len(GENERATED)} generated files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
