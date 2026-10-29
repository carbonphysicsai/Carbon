"""Seed a fixture git checkout with every worker build input (the digest refuses a checkout missing any of them).

Used by the fixtures that build a small git repository and compute `build_inputs.digest` on it. The files are
placeholders; the real set file is copied in so the fixture reads the real list of inputs.
"""

from __future__ import annotations

from pathlib import Path

from carbon.reconstruction.worker import build_inputs


def seed_build_inputs(root: Path) -> list:
    """Create the set file and a placeholder under every build input; returns the repo-relative files written.

    The caller adds and commits them (the digest reads the committed tree)."""
    written = []
    inputs = root / build_inputs.INPUTS_FILE_IN_REPO
    inputs.parent.mkdir(parents=True, exist_ok=True)
    inputs.write_text(
        build_inputs.INPUTS_FILE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    written.append(build_inputs.INPUTS_FILE_IN_REPO)
    for path in build_inputs.paths():
        target = root / path
        if target.exists():
            continue
        if "." in Path(path).name:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture " + path + "\n", encoding="utf-8")
            written.append(path)
        else:  # a directory input (carbon/, .devcontainer/torch ...)
            marker = target / "fixture-input.txt"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("fixture " + path + "\n", encoding="utf-8")
            written.append(path + "/fixture-input.txt")
    return written
