"""KNN-STATE-DIGEST-01: battery KNN's versioned state digest.

`params_sha256` keeps its meaning (the stored TRAIN targets only, as the
exam-design campaign's research KNN reports it); `state_sha256`
(`carbon.battery.knn-state.v1`) also binds `k`, `train_fraction` and the unit
inputs. Engineering fixtures only: a 48-case TRAIN subset, seed 0.

KNN-STATE-GPU-01: Carbon's pods build a KNN with GPU program v2, which stages
this module; every other recipe keeps v1. Run here on CPU JAX, never a GPU.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from carbon.battery import knn_state


@pytest.fixture(scope="module")
def material():
    pytest.importorskip("jax")
    from carbon.battery import challenge as ch

    loaded = ch.PublicMaterial.load()
    return loaded, loaded.train.subset(48)


def _fit(material, **parameters):
    from carbon.battery.compile import compile_recipe, rebuild
    from carbon.reconstruction import capability_registry as r

    loaded, train = material
    strategy = {
        "schema_version": "1.0",
        "challenge_id": r.BATTERY_CHALLENGE,
        "backbone": "knn",
        "parameters": parameters,
    }
    _, recipe = compile_recipe(strategy)
    return rebuild(recipe, loaded, 0, train=train)


def test_params_sha256_keeps_its_meaning(material):
    model, stats = _fit(material)
    assert stats["params_sha256"] == hashlib.sha256(model.y.tobytes()).hexdigest()
    assert stats["state_schema"] == knn_state.SCHEMA == "carbon.battery.knn-state.v1"
    assert stats["state_sha256"] == knn_state.state_sha256(model)
    assert stats["state_sha256"] != stats["params_sha256"]


def test_state_digest_binds_neighbours_and_train_fraction(material):
    _, base = _fit(material, neighbours=3)
    _, other_k = _fit(material, neighbours=7)
    _, half = _fit(material, neighbours=3, train_fraction=0.5)
    assert base["params_sha256"] == other_k["params_sha256"]
    assert base["state_sha256"] != other_k["state_sha256"]
    assert half["state_sha256"] not in {base["state_sha256"], other_k["state_sha256"]}
    assert knn_state.trained_identity(base) != knn_state.trained_identity(other_k)


def test_state_digest_is_deterministic(material):
    _, first = _fit(material, neighbours=5)
    _, again = _fit(material, neighbours=5)
    assert first["state_sha256"] == again["state_sha256"]


def test_records_without_the_digest_keep_their_identity():
    old = {"seconds": 0.0, "params_sha256": "a" * 64}
    assert knn_state.trained_identity(old) == ("params_sha256", "a" * 64)
    new = {**old, "state_schema": knn_state.SCHEMA, "state_sha256": "b" * 64}
    assert knn_state.trained_identity(new) == (knn_state.SCHEMA, "b" * 64)
    with pytest.raises(ValueError):
        knn_state.trained_identity(
            {**new, "state_schema": "carbon.battery.knn-state.v9"}
        )
    with pytest.raises(ValueError):
        knn_state.trained_identity({**old, "state_sha256": "b" * 64})


def test_other_families_and_unfitted_knns():
    stats = {"params_sha256": "c" * 64}
    assert knn_state.with_state(object(), stats) is stats
    with pytest.raises(TypeError):
        knn_state.state_sha256(object())
    with pytest.raises(ValueError):
        knn_state.state_sha256(knn_state.KNN(3))


def test_digest_module_moves_no_level0_identity():
    """Outside the implementation digest and the practice worker's staged
    files, so Level-0 recipe, built-record and program digests stay put."""
    from carbon.battery import contracts, practice

    assert "knn_state.py" not in contracts.IMPLEMENTATION_MODULES
    assert "knn_state.py" not in set(practice.STAGED_MODULES.values())


# --- KNN-STATE-GPU-01: the pod's GPU program, version 2 ------------------------

REPOSITORY = Path(__file__).resolve().parents[2]
#: GPU program v1's digest, as #611 pinned it (`test_battery_level1.LEVEL0_PINS`).
PROGRAM_V1 = "sha256:264413438e3456605279d89aa3f066386bbf0dfaa497198a0957bdf912a9746a"


def _strategy(backbone, **parameters):
    from carbon.reconstruction import capability_registry as r

    return {
        "schema_version": "1.0",
        "challenge_id": r.BATTERY_CHALLENGE,
        "backbone": backbone,
        "parameters": parameters,
    }


def _built(strategy):
    from carbon.challenge_validator.scoring import scoring_for
    from carbon.reconstruction import capability_registry as r

    return scoring_for(r.BATTERY_CHALLENGE).built_record(
        strategy, r.contract(r.BATTERY_CHALLENGE).digest, 7, str(REPOSITORY)
    )


def test_program_versions_resolve_and_v1_is_unchanged():
    from carbon.development_session import battery_gpu as gpu
    from carbon.development_session.profile import digest

    v2 = digest(gpu.KNN_GPU_PROGRAM.encode())
    assert digest(gpu.GPU_PROGRAM.encode()) == PROGRAM_V1
    assert gpu.program_version(PROGRAM_V1) == gpu.PROGRAM_V1
    assert gpu.program_version(v2) == gpu.PROGRAM_V2
    assert gpu.PROGRAMS[PROGRAM_V1][1] == gpu.GPU_PROGRAM
    with pytest.raises(ValueError):
        gpu.program_version("sha256:" + "0" * 64)
    # v2 is v1 with the state digest added after the fit, nothing else.
    assert gpu.KNN_GPU_PROGRAM.replace(gpu._KNN_STATE, "") == gpu.GPU_PROGRAM
    # Every other family, and the Level-1 program, stay on v1.
    from carbon.battery import level1_worker

    assert gpu.pod_program("mlp") == (gpu.GPU_PROGRAM, {})
    assert "knn_state" not in level1_worker.program()


def test_only_a_knn_pod_build_moves_to_v2():
    from carbon.battery.research import SCAFFOLD
    from carbon.development_session import battery_gpu as gpu
    from carbon.development_session.profile import digest

    record, files, program = _built(SCAFFOLD)
    assert record["program"] == PROGRAM_V1 and program == gpu.GPU_PROGRAM
    assert "battery-knn-state.py" not in files
    record, files, program = _built(_strategy("knn", neighbours=5))
    assert program == gpu.KNN_GPU_PROGRAM
    assert gpu.program_version(record["program"]) == gpu.PROGRAM_V2
    body = (REPOSITORY / "carbon/battery/knn_state.py").read_bytes()
    assert files["battery-knn-state.py"] == body
    assert record["staged"]["battery-knn-state.py"] == digest(body)


def _run(program, files, tmp_path):
    work, out = tmp_path / "work", tmp_path / "output"
    work.mkdir(parents=True)
    out.mkdir()
    for name, body in files.items():
        (work / name).write_bytes(body)
    subprocess.run(
        [sys.executable, "-c", program],
        cwd=work,
        env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "JAX_PLATFORMS": "cpu"},
        capture_output=True,
        check=True,
        timeout=600,
    )
    return (
        json.loads((out / "fit.json").read_text()),
        (out / "predictions.json").read_bytes(),
    )


def test_the_pod_program_emits_the_hosts_state_digest(tmp_path):
    """v2 run as the pod runs it (CPU JAX here, no GPU) reports the state
    digest Carbon's host computes; v1 on the same files reports none, and
    both report the same `params_sha256` and predictions."""
    pytest.importorskip("jax")
    from carbon.battery import challenge as ch
    from carbon.battery.compile import compile_recipe, rebuild
    from carbon.development_session import battery_gpu as gpu

    strategy = _strategy("knn", neighbours=5)
    _record, files, program = _built(strategy)
    fit, predictions = _run(program, files, tmp_path / "v2")
    old_fit, old_predictions = _run(gpu.GPU_PROGRAM, files, tmp_path / "v1")
    _, host = rebuild(compile_recipe(strategy)[1], ch.PublicMaterial.load(), 7)
    assert fit["state_schema"] == knn_state.SCHEMA
    assert fit["state_sha256"] == host["state_sha256"]
    assert fit["params_sha256"] == old_fit["params_sha256"] == host["params_sha256"]
    assert "state_sha256" not in old_fit
    assert knn_state.trained_identity(old_fit) == (
        "params_sha256",
        host["params_sha256"],
    )
    assert predictions == old_predictions
