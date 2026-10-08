"""Level 4 G0 intake, G3 isolated parse and the lowering CLI (development only).

Claims tested:

1. `python -m carbon.level4.tooling lower` turns a JAX spec (init graph) and
   a PyTorch spec (init spec) into a submission that intake accepts and G4
   validates.
2. Unset bounds block intake (HUMAN_INPUT); nothing is refused on the
   submission's account.
3. Oversized manifests, documents and submissions are refused before parsing.
4. The isolated parser's refusals reach the caller with their codes.
5. A parser that crashes or overruns is the submission's refusal; a parser
   that cannot start, or reports Carbon's environment broken, is
   FAILED_INFRA (`IntakeInfraFailure`), never a refusal.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, intake, validate

REPOSITORY = Path(__file__).resolve().parents[2]
#: Fixture bounds for tests ONLY; every real bound stays HUMAN_INPUT.
FIXTURE_BOUNDS = {
    "manifest_bytes": 1 << 20,
    "document_bytes": 1 << 26,
    "submission_bytes": 1 << 27,
    "parse_seconds": 60,
    "parse_memory_bytes": 2 << 30,
}
CHALLENGE = "example-challenge"
INTERFACE = validate.Interface(
    inputs=(("inputs/x", "float32", (3,)),), outputs=(("float32", (2,)),)
)

JAX_SPEC = """
import jax
import jax.numpy as jnp

FRAMEWORK = "jax"
INPUTS = {"inputs/x": ((3,), "float32")}


def init(key):
    k1, k2 = jax.random.split(key)
    return [jax.random.normal(k1, (3, 8)) * 0.5, jnp.zeros(8), jax.random.normal(k2, (8, 2)) * 0.3, jnp.zeros(2)]


def forward(p, x):
    return jax.nn.relu(x @ p[0] + p[1]) @ p[2] + p[3]
"""

TORCH_SPEC = """
import torch

FRAMEWORK = "torch"
INPUTS = {"inputs/x": ((3,), "float32")}
INIT_SPEC = [
    {"initializer": "he_normal", "fan_in_axes": [0], "fan_out_axes": [1]},
    {"initializer": "zeros", "fan_in_axes": [], "fan_out_axes": []},
]


def build():
    params = [torch.randn(3, 2), torch.zeros(2)]
    return params, lambda p, x: torch.tanh(x @ p[0] + p[1])
"""


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


def _lower(tmp_path, source, batch=4):
    spec = tmp_path / "spec.py"
    spec.write_text(textwrap.dedent(source))
    out = tmp_path / "out"
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "carbon.level4.tooling",
            "lower",
            str(spec),
            str(out),
            "--challenge",
            CHALLENGE,
            "--interface",
            INTERFACE.digest(),
            "--batch",
            str(batch),
        ],
        env={**os.environ, "PYTHONPATH": str(REPOSITORY), "JAX_PLATFORMS": "cpu"},
        capture_output=True,
        text=True,
        check=True,
    )
    digest = json.loads(done.stdout.strip().splitlines()[-1])["submission"]
    raw_manifest = (out / "manifest.json").read_bytes()
    files = {
        "sha256:" + p.stem: p.read_bytes()
        for p in out.glob("*.json")
        if p.name != "manifest.json"
    }
    return digest, raw_manifest, files


def _intake(allowlist, raw_manifest, files, **kwargs):
    return intake.intake(
        raw_manifest,
        files,
        allowlist=allowlist,
        challenge=CHALLENGE,
        interface=INTERFACE.digest(),
        **{"bounds": FIXTURE_BOUNDS, **kwargs},
    )


def test_cli_jax_submission_through_intake_and_g4(allowlist, tmp_path):
    from carbon.level4 import submission

    digest, raw_manifest, files = _lower(tmp_path, JAX_SPEC)
    manifest, parsed = _intake(allowlist, raw_manifest, files)
    assert submission.digest(manifest) == digest and set(parsed) == {"forward", "init"}
    verdict = validate.validate_submission(
        parsed, allowlist, interface=INTERFACE, batch=4
    )
    assert verdict["status"] == "blocked_human_input" and verdict["batch"] == 4
    named = {
        n["params"]["name"]
        for g in parsed["forward"]["graphs"].values()
        for n in g["nodes"]
        if n["op"] == "named_function"
    }
    assert named == {"relu"}


def test_cli_torch_submission_uses_carbon_init(allowlist, tmp_path):
    pytest.importorskip("torch")
    _, raw_manifest, files = _lower(tmp_path, TORCH_SPEC)
    _, parsed = _intake(allowlist, raw_manifest, files)
    assert set(parsed) == {"forward", "init_spec"}
    validate.validate_submission(parsed, allowlist, interface=INTERFACE, batch=4)


def test_unset_bounds_block(allowlist, tmp_path):
    _, raw_manifest, files = _lower(tmp_path, JAX_SPEC)
    with pytest.raises(intake.IntakeBlocked):
        intake.intake(
            raw_manifest,
            files,
            allowlist=allowlist,
            challenge=CHALLENGE,
            interface=INTERFACE.digest(),
        )
    partial = dict(FIXTURE_BOUNDS, parse_seconds=allowlist_module.HUMAN_INPUT)
    with pytest.raises(intake.IntakeBlocked):
        _intake(allowlist, raw_manifest, files, bounds=partial)


def test_sizes_refused_before_parsing(allowlist, tmp_path):
    _, raw_manifest, files = _lower(tmp_path, JAX_SPEC)
    for bound, code in (
        ("manifest_bytes", "oversized_manifest"),
        ("document_bytes", "oversized_document"),
        ("submission_bytes", "oversized_submission"),
    ):
        with pytest.raises(graph.GraphRefused) as refused:
            _intake(
                allowlist, raw_manifest, files, bounds={**FIXTURE_BOUNDS, bound: 10}
            )
        assert refused.value.code == code


def test_isolated_refusal_reaches_the_caller(allowlist, tmp_path):
    _, raw_manifest, files = _lower(tmp_path, JAX_SPEC)
    name = next(iter(files))
    tampered = {**files, name: files[name] + b" "}
    with pytest.raises(graph.GraphRefused) as refused:
        _intake(allowlist, raw_manifest, tampered)
    assert refused.value.code == "document_digest_mismatch"
    assert refused.value.where == "isolated parse"


@pytest.mark.parametrize(
    ("script", "bounds", "outcome"),
    [
        (
            "import os, signal; os.kill(os.getpid(), signal.SIGKILL)",
            {},
            "parse_resource_limit",
        ),
        ("import time; time.sleep(30)", {"parse_seconds": 1}, "parse_deadline"),
        ('print(\'{"state": "FAILED_INFRA"}\')', {}, intake.IntakeInfraFailure),
    ],
)
def test_worker_failure_classes(allowlist, tmp_path, script, bounds, outcome):
    _, raw_manifest, files = _lower(tmp_path, JAX_SPEC)
    worker = [sys.executable, "-c", script]
    if isinstance(outcome, str):
        with pytest.raises(graph.GraphRefused) as refused:
            _intake(
                allowlist,
                raw_manifest,
                files,
                bounds={**FIXTURE_BOUNDS, **bounds},
                worker=worker,
            )
        assert refused.value.code == outcome
    else:
        with pytest.raises(outcome):
            _intake(allowlist, raw_manifest, files, worker=worker)


def test_worker_that_cannot_start_is_infra(allowlist, tmp_path):
    _, raw_manifest, files = _lower(tmp_path, JAX_SPEC)
    with pytest.raises(intake.IntakeInfraFailure) as failure:
        _intake(
            allowlist, raw_manifest, files, worker=[str(tmp_path / "no-such-python")]
        )
    assert failure.value.kind == intake.FAILED_INFRA
