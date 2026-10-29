"""The grading entrypoint of the 4090 class probes (scripts/dev/practice_grade_entry.py): one catalog entry through
the practice, a deterministic canonical grade line (what `grade_repeat` hashes), and the GPU/CPU totals pair
(`parity --totals`). Practice stand-ins only; no Docker, no GPU, no sealed material."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/dev/practice_grade_entry.py"
spec = importlib.util.spec_from_file_location("practice_grade_entry", SCRIPT)
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)

KIND = "motor"
ID = entry.curves.candidates(KIND)[0]
COMMON = ["--kind", KIND, "--entry", ID, "--parent-identity", "p", "--cache-root", "c"]


def _outcome(accuracy, design, backend_kind="C03_DOCKER", note=None, wall=1.0):
    backend = {"kind": backend_kind, "parent": "sha256:p"}
    if note:
        backend["gpu_note"] = note
    return {
        "practice_dual": {
            "available": True,
            "accuracy": accuracy,
            "accuracy_legs": {"A_acc": accuracy},
            "design_value": design,
            "design_parts": {"C": design},
            "eligible": accuracy is not None,
            "gates": {"physics_laws": True},
            "n_cases": 60,
            "speed": {"per_call_median_seconds": wall},
        },
        "fit": {"state_digest": "sha256:" + "a" * 64},
        "backend": backend,
    }


def _factory(cpu, gpu, seen=None):
    def factory(kind, args):
        class Practice:
            gpu_image = None

            def __call__(self, identity, recipe):
                if seen is not None:
                    seen.append(self.gpu_image)
                return gpu if self.gpu_image else cpu

        return Practice()

    return factory


def _run(capsys, argv, factory):
    code = entry.main(argv, factory=factory, load_identity=lambda path: f"id:{path}")
    return code, capsys.readouterr().out


def test_grade_prints_one_deterministic_line_without_timings(capsys):
    cpu = _outcome(0.8, 0.4, wall=1.0)
    first = _run(capsys, ["grade", *COMMON], _factory(cpu, None))
    cpu["practice_dual"]["speed"]["per_call_median_seconds"] = 99.0
    second = _run(capsys, ["grade", *COMMON], _factory(cpu, None))
    assert first == second and first[0] == 0
    document = json.loads(first[1])
    assert document["total"] == pytest.approx(0.6) and document["device"] == "cpu"
    assert document["state_digest"] == "sha256:" + "a" * 64
    assert "speed" not in first[1] and "wall" not in first[1]
    assert first[1].count("\n") == 1


def test_grade_with_a_gpu_image_labels_the_device_and_passes_the_image(capsys):
    seen = []
    gpu = _outcome(0.8, 0.4, backend_kind="C03_DOCKER_GPU")
    code, out = _run(
        capsys,
        ["grade", *COMMON, "--gpu-image", "g.json"],
        _factory(_outcome(0.8, 0.4), gpu, seen),
    )
    assert code == 0 and seen == ["id:g.json"]
    assert json.loads(out)["device"] == "gpu"


def test_a_gpu_request_that_ran_the_cpu_build_is_exit_3_not_a_gpu_datum(capsys):
    fell_back = _outcome(0.8, 0.4, note="gpu_overlay_not_installed")
    code, out = _run(
        capsys,
        ["grade", *COMMON, "--gpu-image", "g.json"],
        _factory(None, fell_back),
    )
    assert code == 3
    assert json.loads(out)["gpu_note"] == "gpu_overlay_not_installed"


def test_an_entry_that_does_not_score_is_exit_1(capsys):
    code, out = _run(capsys, ["grade", *COMMON], _factory(_outcome(None, None), None))
    assert code == 1 and json.loads(out)["total"] is None


def test_parity_prints_the_totals_file_entry(capsys):
    cpu = _outcome(0.80, 0.40)
    gpu = _outcome(0.81, 0.40, backend_kind="C03_DOCKER_GPU")
    code, out = _run(
        capsys, ["parity", *COMMON, "--gpu-image", "g.json"], _factory(cpu, gpu)
    )
    assert code == 0
    pair = json.loads(out)[ID]
    assert pair["cpu_total"] == pytest.approx(0.6)
    assert pair["gpu_total"] == pytest.approx(0.605)


def test_parity_refuses_a_cpu_fallback_and_needs_the_gpu_image(capsys):
    fell_back = _outcome(0.8, 0.4, note="gpu_build_failed")
    code, _out = _run(
        capsys,
        ["parity", *COMMON, "--gpu-image", "g.json"],
        _factory(_outcome(0.8, 0.4), fell_back),
    )
    assert code == 3
    with pytest.raises(SystemExit):
        entry.main(["parity", *COMMON])


def test_the_gpu_leg_uses_its_own_scratch_cache_and_the_cpu_leg_the_installs():
    seen = []

    def factory(kind, args):
        seen.append(args.cache_root)

        class Practice:
            gpu_image = None

            def __call__(self, identity, recipe):
                return _outcome(
                    0.8,
                    0.4,
                    backend_kind=("C03_DOCKER_GPU" if self.gpu_image else "C03_DOCKER"),
                )

        return Practice()

    argv = ["parity", *COMMON, "--gpu-image", "g.json", "--gpu-cache-root", "SCRATCH"]
    code = entry.main(argv, factory=factory, load_identity=lambda path: path)
    assert code == 0
    assert seen == [
        "c",
        "SCRATCH",
    ]  # CPU leg first on the install's cache, then the GPU leg on the scratch one
    seen.clear()
    entry.main(
        ["grade", *COMMON, "--gpu-image", "g.json"],
        factory=factory,
        load_identity=lambda path: path,
    )
    assert seen == ["c"]  # no scratch cache named: the one cache
