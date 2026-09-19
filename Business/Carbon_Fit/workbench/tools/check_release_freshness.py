#!/usr/bin/env python3
"""Read-only freshness gate for the current Workbench release artifacts.

The determinism test proves that repeating a build reproduces its own output.
It cannot prove that the artifacts tracked in the repository were built from the
sources tracked beside them, because it runs a build before capturing its first
comparison bytes and therefore overwrites the very artifact under test. A stale
artifact that rebuilds identically twice still passes it.

This gate supplies the missing condition:

    tracked artifact bytes == output generated from the tracked source inputs

The expected bytes are captured from the repository first and never written to.
Only the *source* inputs are staged into a throwaway directory outside the
repository, so a generator that exits zero without writing cannot be credited
with the artifact that was already there: the file is simply absent and the run
fails. Every declared artifact must also be tracked, so a stray file on disk is
never mistaken for release content.

Exit status: 0 current, 1 stale, 2 the check could not run.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Generators in dependency order, with the artifacts each one must produce.
# Packaging globs the tree, so the HTML and schema must exist before it runs.
GENERATOR_OUTPUTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "tools/build.py",
        (
            "Carbon_Opportunity_Workbench.html",
            "Carbon_Client_Intake_Preview.html",
            "Carbon_Client_Pilot_Designer_Preview.html",
        ),
    ),
    (
        "tools/build_goal_schema.py",
        (
            "data/goal_workspace.schema.json",
            "data/goal_constants.json",
        ),
    ),
    (
        "tools/package_release.py",
        (
            "MANIFEST.json",
            "Carbon_Physics_Goal_Workbench_v0_10.zip",
        ),
    ),
)

GENERATED: dict[str, str] = {
    artifact: generator
    for generator, artifacts in GENERATOR_OUTPUTS
    for artifact in artifacts
}

MANIFEST_NAME = "MANIFEST.json"
ARCHIVE_NAME = "Carbon_Physics_Goal_Workbench_v0_10.zip"
ARCHIVE_PREFIX = "carbon_goal_workbench_v0_10/"
ARCHIVE_MANIFEST = ARCHIVE_PREFIX + MANIFEST_NAME

# package_release.py records the Git HEAD that packaged the release. A commit
# cannot contain its own hash, so this one field is packaging provenance and is
# never evidence of staleness. Its value is excluded from equality; its shape is
# still validated. Nothing else is normalised.
PROVENANCE_FIELD = "integration_revision_at_packaging"
PROVENANCE_PLACEHOLDER = "<normalised-for-comparison>"
PROVENANCE_SHAPE = re.compile(r"\A(?:[0-9a-f]{40}|UNAVAILABLE)\Z")

# The packager writes permission bits only, leaving the file-type field clear.
# Any other type (symlink, directory, device) changes what extraction produces.
ARCHIVE_TYPE_MASK = 0o170000


class FreshnessError(RuntimeError):
    """The gate could not establish a trustworthy comparison."""


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise FreshnessError(f"git {' '.join(args)} failed: {error}")


def tracked_sources() -> list[str]:
    """Workbench paths tracked by Git, relative to the workbench root.

    The release archive is assembled by globbing the workbench directory, so
    generating from the working tree would let untracked scratch files, local
    build output or credentials reach the comparison. Restricting the staged
    set to tracked paths keeps the check reproducible and keeps stray files out
    of the regenerated archive.
    """
    paths = [entry for entry in _git("ls-files", "-z", "--", ".").split("\0") if entry]
    if not paths:
        raise FreshnessError("no tracked Workbench sources were found")
    return paths


def expected_artifacts(tracked: set[str]) -> dict[str, bytes]:
    """Read the artifacts under test before anything is generated.

    Membership is established from Git, not from the filesystem, so a file that
    merely exists on disk is never treated as tracked release content.
    """
    expected: dict[str, bytes] = {}
    for relative in sorted(GENERATED):
        if relative not in tracked:
            raise FreshnessError(
                f"{relative} is a declared release artifact but is not tracked"
            )
        path = ROOT / relative
        if not path.is_file():
            raise FreshnessError(f"tracked release artifact {relative} is missing")
        expected[relative] = path.read_bytes()
    return expected


def stage(destination: Path, sources: list[str]) -> None:
    """Copy the tracked *source* inputs into a throwaway tree.

    The declared artifacts are deliberately not copied. If they were, a
    generator that exits zero without writing would leave the previous file in
    place and the comparison would credit it as freshly produced.
    """
    for relative in sources:
        if relative in GENERATED:
            continue
        source = ROOT / relative
        if not source.is_file():
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def generate(destination: Path) -> None:
    """Run each generator in order and require the outputs it declares."""
    for generator, artifacts in GENERATOR_OUTPUTS:
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
        # A zero exit is not evidence of output. Require each declared artifact
        # to exist as a regular file before anything downstream consumes it.
        for artifact in artifacts:
            produced = destination / artifact
            if not produced.is_file() or produced.is_symlink():
                raise FreshnessError(
                    f"{generator} exited 0 but did not produce {artifact} "
                    "as a regular file"
                )


def _load_manifest(raw: bytes, label: str) -> dict:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FreshnessError(f"{label} is not readable JSON: {error}")
    if not isinstance(document, dict):
        raise FreshnessError(f"{label} is not a JSON object")
    return document


def normalise_manifest(raw: bytes, label: str = "manifest") -> bytes:
    """Blank packaging provenance so the comparison stays acyclic.

    The field's shape is still validated; only its value is excluded.
    """
    document = _load_manifest(raw, label)
    if PROVENANCE_FIELD in document:
        value = document[PROVENANCE_FIELD]
        if not isinstance(value, str) or not PROVENANCE_SHAPE.match(value):
            raise FreshnessError(
                f"{label} {PROVENANCE_FIELD} must be an exact lowercase commit "
                f"SHA or UNAVAILABLE, not {value!r}"
            )
        document[PROVENANCE_FIELD] = PROVENANCE_PLACEHOLDER
    return json.dumps(document, indent=2, sort_keys=True).encode("utf-8")


def archive_members(raw: bytes, label: str) -> dict[str, tuple[int, bytes]]:
    """Validate archive structure, then return each member's mode and payload.

    Reducing an archive to a name/payload mapping read through ``namelist`` hides
    two things that change what extraction produces: a duplicated member name,
    where only one entry survives the mapping, and a member re-typed as a link
    while its bytes stay identical. Entries are therefore walked through
    ``infolist`` and validated before any comparison.
    """
    members: dict[str, tuple[int, bytes]] = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        for info in bundle.infolist():
            name = info.filename
            if name in members:
                raise FreshnessError(f"{label} repeats the member name {name!r}")
            if info.is_dir():
                raise FreshnessError(f"{label} contains a directory entry {name!r}")
            if not name.startswith(ARCHIVE_PREFIX):
                raise FreshnessError(
                    f"{label} member {name!r} is outside {ARCHIVE_PREFIX!r}"
                )
            pure = Path(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                raise FreshnessError(f"{label} member {name!r} is not a safe path")
            mode = info.external_attr >> 16
            if mode & ARCHIVE_TYPE_MASK:
                raise FreshnessError(
                    f"{label} member {name!r} is not a regular file "
                    f"(mode {stat.filemode(mode)})"
                )
            payload = bundle.read(info)
            if name == ARCHIVE_MANIFEST:
                payload = normalise_manifest(payload, f"{label} {MANIFEST_NAME}")
            members[name] = (mode, payload)
    if ARCHIVE_MANIFEST not in members:
        raise FreshnessError(f"{label} does not contain {ARCHIVE_MANIFEST}")
    return members


def describe_archive_drift(
    tracked: dict[str, tuple[int, bytes]], rebuilt: dict[str, tuple[int, bytes]]
) -> list[str]:
    """Explain how two archives differ, member by member."""
    missing = sorted(set(tracked) - set(rebuilt))
    added = sorted(set(rebuilt) - set(tracked))
    detail = [f"    no longer generated: {name}" for name in missing]
    detail += [f"    missing from the tracked archive: {name}" for name in added]
    for name in sorted(set(tracked) & set(rebuilt)):
        before, after = tracked[name], rebuilt[name]
        if before[0] != after[0]:
            detail.append(
                f"    member mode differs: {name} "
                f"({stat.filemode(before[0])} -> {stat.filemode(after[0])})"
            )
        elif before[1] != after[1]:
            detail.append(f"    content differs: {name}")
    return detail


def compare(expected: dict[str, bytes], destination: Path) -> list[str]:
    """Return a report of every stale artifact; empty means fresh."""
    stale: list[str] = []
    for relative, generator in sorted(GENERATED.items()):
        tracked_bytes = expected[relative]
        rebuilt_path = destination / relative
        # generate() already required this, so absence here is a broken run.
        if not rebuilt_path.is_file():
            raise FreshnessError(f"{generator} output {relative} disappeared")
        rebuilt_bytes = rebuilt_path.read_bytes()
        detail: list[str] = []
        if relative == ARCHIVE_NAME:
            before = archive_members(tracked_bytes, "the tracked archive")
            after = archive_members(rebuilt_bytes, "the regenerated archive")
            equal = before == after
            if not equal:
                detail = describe_archive_drift(before, after)
        elif relative == MANIFEST_NAME:
            equal = normalise_manifest(
                tracked_bytes, "the tracked manifest"
            ) == normalise_manifest(rebuilt_bytes, "the regenerated manifest")
        else:
            equal = tracked_bytes == rebuilt_bytes
        if equal:
            continue
        entry = (
            f"  {relative}: tracked bytes differ from {generator} output "
            f"({len(tracked_bytes)} tracked, {len(rebuilt_bytes)} rebuilt)"
        )
        stale.append("\n".join([entry, *detail]) if detail else entry)
    return stale


def check(keep: bool = False) -> list[str]:
    """Capture, stage, regenerate and compare without touching a tracked file."""
    sources = tracked_sources()
    expected = expected_artifacts(set(sources))
    # Outside the repository, so the generators cannot resolve its Git HEAD and
    # cannot reach files that are not part of the staged source set.
    destination = Path(tempfile.mkdtemp(prefix="carbon-workbench-freshness-"))
    try:
        stage(destination, sources)
        generate(destination)
        return compare(expected, destination)
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
