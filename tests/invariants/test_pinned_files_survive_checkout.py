"""Every sha256-pinned repository file re-hashes to its pin after a fresh
checkout, whatever the clone's line-ending settings (Validator, 2026-10-20).

A pin is a (path, sha256) pair written in the source: a tuple or dict entry
whose path names a committed file, including paths built from module-level
string constants (`EVIDENCE + "/x.json"`). For each, git's own checkout
conversion under `core.autocrlf=true` (`git cat-file --filters`) must give
the pinned bytes. That holds only where `.gitattributes` turns text
conversion off for the file (`-text`) or git treats it as binary, so an
unprotected pinned text file fails here, by name.
"""

from __future__ import annotations

import ast
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("carbon", "scripts", "tests")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _fold(node, constants):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _fold(node.left, constants), _fold(node.right, constants)
        if left is not None and right is not None:
            return left + right
    return None


def pins():
    """{repository path: {sha256}} for every pin found in the scanned code."""
    found = {}
    for base in SCANNED:
        for source in sorted((ROOT / base).rglob("*.py")):
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            constants = {}
            for node in tree.body:
                if (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                ):
                    value = _fold(node.value, constants)
                    if value is not None:
                        constants[node.targets[0].id] = value
            for node in ast.walk(tree):
                pairs = []
                if isinstance(node, ast.Tuple) and len(node.elts) == 2:
                    pairs.append(tuple(node.elts))
                if isinstance(node, ast.Dict):
                    pairs.extend(zip(node.keys, node.values, strict=True))
                for key, value in pairs:
                    path = _fold(key, constants) if key is not None else None
                    pin = _fold(value, constants)
                    if path is None or pin is None:
                        continue
                    pin = pin.removeprefix("sha256:")
                    if _HEX.fullmatch(pin) and "/" in path and (ROOT / path).is_file():
                        found.setdefault(path, set()).add(pin)
    return found


def test_pins_are_found():
    found = pins()
    # Anchors across the pin tables: a Challenge TRAIN, an evidence ladder
    # built from a constant, a reference-solver script, a battery contract.
    for path in (
        "carbon/challenge_kit/data/f08-dev-train-287-v2.npz",
        "docs/development/evidence/f08-near-limit-public-20261020/ladder-actions.json",
        "scripts/dev/battery/plating_rereference.py",
    ):
        assert path in found, path
    assert len(found) >= 48


def test_every_pin_survives_an_autocrlf_checkout():
    # Fail, never skip, when git or HEAD is missing (Validator, 2026-10-20).
    assert shutil.which("git"), "git is required for this invariant"
    subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        check=True,
    )
    failures = []
    for path, pinned in sorted(pins().items()):
        tracked = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", path],
            capture_output=True,
            check=False,
        )
        if tracked.returncode != 0:
            continue  # not committed yet in this checkout
        checkout = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "-c",
                "core.autocrlf=true",
                "-c",
                "core.eol=crlf",
                "cat-file",
                "--filters",
                f"HEAD:{path}",
            ],
            capture_output=True,
            check=True,
        ).stdout
        if hashlib.sha256(checkout).hexdigest() not in pinned:
            failures.append(path)
    assert not failures, f"pinned files altered by an autocrlf checkout: {failures}"
