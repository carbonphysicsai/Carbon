"""A kit takes an exam's sizes from its pack and interface, never from a literal (model-eval row 6266; blind audit class).

A static scan of every kit and sealed-grader module: a length or shape compared with an integer literal, or an array
made or reshaped with one, of at least `SMALLEST`. ``FROZEN`` is the shrink-only list of what main held when the scan
was written: loaders of frozen, sha-pinned TRAIN files. A new line fails; a removed one must leave the list too.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
SCANNED = (
    "carbon/challenge_kit/*.py",
    "carbon/scoring/*dual_pack.py",
    "carbon/scoring/*sealed*.py",
    "kits/**/*.py",
    "scripts/dev/sealed_exam/*.py",
)
#: Below this a literal is an index or a small fixed count, not a TRAIN row count or an output width.
SMALLEST = 20
#: Digest and key lengths: 32 bytes, 64 hex, "sha256:" + 64 hex.
NOT_A_SIZE = frozenset({32, 64, 71})
MAKERS = frozenset({"reshape", "zeros", "empty", "ones", "full"})

#: {file: the literals it holds}, one per use, sorted.
FROZEN = {
    "carbon/challenge_kit/f02_train.py": (24, 40, 40, 40, 40, 40, 40, 40),
    "carbon/challenge_kit/f08_train.py": (
        *(255, 255, 255, 255, 255, 255),
        *(256, 256, 256),
        *(287, 287, 287, 287, 287, 287),
    ),
}


def _measures(node):
    return any(
        (isinstance(inner, ast.Attribute) and inner.attr in ("shape", "size"))
        or (
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "len"
        )
        for inner in ast.walk(node)
    )


def _literals(nodes):
    return [
        inner.value
        for node in nodes
        for inner in ast.walk(node)
        if isinstance(inner, ast.Constant)
        and type(inner.value) is int
        and inner.value >= SMALLEST
        and inner.value not in NOT_A_SIZE
    ]


def size_literals(source):
    """Every size literal of one module's source, sorted."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            if any(_measures(side) for side in sides):
                found += _literals(sides)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in MAKERS
        ):
            found += _literals(node.args)
    return tuple(sorted(found))


def test_no_kit_holds_a_size_literal_beyond_the_frozen_loaders():
    found = {}
    for pattern in SCANNED:
        files = sorted(REPOSITORY.glob(pattern))
        assert files, pattern
        for path in files:
            literals = size_literals(path.read_text(encoding="utf-8"))
            if literals:
                found[path.relative_to(REPOSITORY).as_posix()] = literals
    # a kit reads its sizes from the pack / interface metadata; a frozen loader that lost a literal leaves the list
    assert found == FROZEN


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("if len(rows) != 240: raise ValueError", (240,)),
        ("assert x.shape == (n, 241)", (241,)),
        ("y = z.reshape(-1, 240)", (240,)),
        ("import numpy as np\nx = np.zeros((400, 5))", (400,)),
        ("if len(rows) != pack['rows']: raise ValueError", ()),
        ("if len(digest) != 64: raise ValueError", ()),
        ("seed = 20261124", ()),
        ("limit = 240", ()),
    ],
)
def test_the_scan_sees_a_size_and_only_a_size(source, expected):
    assert size_literals(source) == expected
