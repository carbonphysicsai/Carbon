"""GRAPHITE-L4-STAGING-01 (R1): the analysis image carries the Level 4 miner
tooling, so an agent lowers its own model in its own sandbox and Carbon only
reads the documents it writes.

Claims tested:
- a real lowering, run against exactly the shipped files (nothing else of
  `carbon` importable), succeeds and writes a submission Carbon verifies;
- the modules that lowering imports are exactly the registered tooling, all
  miner-facing public code: no evaluator, validator, session or private module;
- the validator package ships as an empty stub, never its own `__init__`;
- every shipped tooling file is the repository's own bytes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.development_session import research_image as ri

REPO = Path(__file__).resolve().parents[2]
jax = pytest.importorskip("jax")

SPEC = """
import jax, jax.numpy as jnp
FRAMEWORK = "jax"
INPUTS = {"inputs/features": ((3,), "float32")}
def init(key):
    return [jax.random.normal(key, (3, 2), jnp.float32), jnp.zeros((2,), jnp.float32)]
def forward(params, x):
    w, b = params
    return jnp.tanh(x @ w + b)
"""

PROBE = """
import io, json, sys, contextlib
sys.path.insert(0, sys.argv[1])
from carbon.level4.tooling import __main__ as tool
out = io.StringIO()
with contextlib.redirect_stdout(out):
    code = tool.main(["lower", sys.argv[2], sys.argv[3], "--challenge", "x",
                      "--interface", "sha256:" + "0" * 64, "--batch", "4"])
print(json.dumps({"code": code, "modules": sorted(
    m for m in sys.modules if m == "carbon" or m.startswith("carbon."))}))
"""


@pytest.fixture(scope="module")
def lowered(tmp_path_factory):
    """Lower a small JAX model with only the image's `carbon` files present."""
    root = tmp_path_factory.mktemp("image")
    for name, body in ri.permitted_files().items():
        target = root / "lib" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
    (root / "spec.py").write_text(SPEC)
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            PROBE,
            str(root / "lib"),
            str(root / "spec.py"),
            str(root / "out"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return root, json.loads(done.stdout.strip().splitlines()[-1])


def test_a_lowering_runs_on_the_shipped_files_alone(lowered):
    root, result = lowered
    assert result["code"] == 0
    from carbon.level4 import staging, submission

    found, raw, files = staging.read_directory(root / "out")
    assert found == submission.digest(json.loads(raw))
    assert found.startswith("sha256:") and files


def test_the_lowering_reaches_only_the_registered_public_tooling(lowered):
    _root, result = lowered
    reached = set(result["modules"]) - {"carbon", "carbon.challenge_validator"}
    assert reached <= set(ri.LEVEL4_TOOLING), sorted(reached - set(ri.LEVEL4_TOOLING))
    assert not [m for m in result["modules"] if m.startswith(ri.KIT_FORBIDDEN)]
    for private in (
        "carbon.challenge_validator.dispatch",
        "carbon.challenge_validator.ledger",
        "carbon.development_session",
        "carbon.level4.compile",
        "carbon.level4.intake",
    ):
        assert not [m for m in result["modules"] if m.startswith(private)], private


def test_the_validator_package_ships_as_an_empty_stub():
    shipped = ri.permitted_files()
    assert shipped["carbon/challenge_validator/__init__.py"] == b""
    assert not [
        n
        for n in shipped
        if n.startswith("carbon/challenge_validator/")
        and n
        not in (
            "carbon/challenge_validator/__init__.py",
            "carbon/challenge_validator/strict_json.py",
        )
    ]


def test_every_tooling_file_is_the_repositorys_own_bytes():
    shipped = ri.permitted_files()
    for name, body in ri.level4_tooling_files(REPO).items():
        if name in ri.LEVEL4_STUB_PACKAGES:
            continue
        assert shipped[name] == body == (REPO / name).read_bytes(), name
