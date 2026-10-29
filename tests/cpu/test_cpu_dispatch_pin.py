"""The CPU-dispatch pin (CPU_DISPATCH_PIN_RULING_20261029): one set of constants, every site carries it, the guard fails closed."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from carbon.challenge_validator import cpu_pin

ROOT = Path(__file__).resolve().parents[2]
BLAS = cpu_pin.OPENBLAS_CORETYPE
NPY = cpu_pin.NPY_DISABLE_CPU_FEATURES


def test_the_constants_are_the_ruled_ones():
    assert BLAS == "Haswell"
    names = set(NPY.split(","))
    assert names == {
        "AVX512F",
        "AVX512CD",
        "AVX512_SKX",
        "AVX512_CLX",
        "AVX512_CNL",
        "AVX512_ICL",
        "AVX512_SPR",
    }
    assert " " not in NPY and cpu_pin.PIN == {
        "OPENBLAS_CORETYPE": BLAS,
        "NPY_DISABLE_CPU_FEATURES": NPY,
    }


def _text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_the_worker_image_sets_the_pin():
    text = _text(".devcontainer/Dockerfile.reconstruction-worker")
    # in the final stage: after the last FROM
    final = text[text.rindex("\nFROM ") :]
    assert f"OPENBLAS_CORETYPE={BLAS}" in final
    assert f"NPY_DISABLE_CPU_FEATURES={NPY}" in final


def test_the_receiver_service_unit_sets_the_pin(tmp_path):
    from carbon.challenge_validator import receiver_setup

    source = _text("carbon/challenge_validator/receiver_setup.py")
    assert '"Environment=OPENBLAS_CORETYPE=" + cpu_pin.OPENBLAS_CORETYPE' in source
    assert (
        '"Environment=NPY_DISABLE_CPU_FEATURES=" + cpu_pin.NPY_DISABLE_CPU_FEATURES'
        in source
    )
    assert receiver_setup.cpu_pin is cpu_pin


def test_canonical_and_ci_set_the_pin():
    canonical = _text("scripts/dev/canonical.sh")
    assert f"--env OPENBLAS_CORETYPE={BLAS}" in canonical
    assert f"--env NPY_DISABLE_CPU_FEATURES={NPY}" in canonical
    ci = _text(".github/workflows/ci.yml")
    head = ci[: ci.index("jobs:")]
    assert re.search(rf"^  OPENBLAS_CORETYPE: {BLAS}$", head, re.MULTILINE)
    assert re.search(
        rf"^  NPY_DISABLE_CPU_FEATURES: {re.escape(NPY)}$", head, re.MULTILINE
    )


def test_the_guard_accepts_exactly_the_pin():
    assert cpu_pin.require(dict(cpu_pin.PIN), features=list) == cpu_pin.PIN
    # the feature list is a set: order and separators do not matter
    spaced = {
        **cpu_pin.PIN,
        "NPY_DISABLE_CPU_FEATURES": " ".join(reversed(NPY.split(","))),
    }
    assert cpu_pin.require(spaced, features=list)


@pytest.mark.parametrize(
    "mutate, code",
    [
        (lambda e: e.pop("OPENBLAS_CORETYPE"), "cpu_dispatch_pin_missing"),
        (lambda e: e.pop("NPY_DISABLE_CPU_FEATURES"), "cpu_dispatch_pin_missing"),
        (lambda e: e.update(OPENBLAS_CORETYPE=""), "cpu_dispatch_pin_missing"),
        (lambda e: e.update(OPENBLAS_CORETYPE="SkylakeX"), "cpu_dispatch_pin_differs"),
        (lambda e: e.update(OPENBLAS_CORETYPE="haswell"), "cpu_dispatch_pin_differs"),
        (
            lambda e: e.update(NPY_DISABLE_CPU_FEATURES="AVX512F"),
            "cpu_dispatch_pin_differs",
        ),
        (
            lambda e: e.update(NPY_DISABLE_CPU_FEATURES=NPY + ",AVX2"),
            "cpu_dispatch_pin_differs",
        ),
    ],
)
def test_the_guard_refuses_a_missing_or_different_pin(mutate, code):
    environ = dict(cpu_pin.PIN)
    mutate(environ)
    with pytest.raises(cpu_pin.CpuPinRefused) as refused:
        cpu_pin.require(environ, features=list)
    assert refused.value.code == code


def test_the_guard_refuses_a_pin_numpy_is_not_honouring():
    with pytest.raises(cpu_pin.CpuPinRefused) as refused:
        cpu_pin.require(dict(cpu_pin.PIN), features=lambda: ["AVX512F"])
    assert refused.value.code == "cpu_dispatch_pin_not_effective"
    # unless the caller opts out of the NumPy check (the variables alone)
    assert cpu_pin.require(
        dict(cpu_pin.PIN), check_effective=False, features=lambda: ["AVX512F"]
    )


def test_the_receiver_and_the_calibration_run_refuse_unpinned(monkeypatch, capsys):
    from carbon.challenge_validator import calibration_grade_run, direct_receiver

    for name in cpu_pin.PIN:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(cpu_pin.CpuPinRefused):
        direct_receiver.serve(Path("unused.json"))
    assert direct_receiver.main(["--config", "unused.json"]) == 2
    assert "cpu_dispatch_pin_missing" in capsys.readouterr().err
    argv = [
        "--artifact", "a", "--pack", "p", "--challenge", "c", "--version", "v",
        "--work", "w",
    ]  # fmt: skip
    assert calibration_grade_run.main(argv) == 2
    assert "cpu_dispatch_pin_missing" in capsys.readouterr().err


def test_no_producer_file_changed():
    """physical_dual_pack.py is a shared producer file: the pin is set outside it."""
    text = _text("carbon/scoring/physical_dual_pack.py")
    assert "OPENBLAS_CORETYPE" not in text and "NPY_DISABLE_CPU_FEATURES" not in text
