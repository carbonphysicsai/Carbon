"""The CPU-dispatch pin (CPU_DISPATCH_PIN_RULING_20261029): one set of constants, every site carries it, the guard fails closed."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from carbon.challenge_validator import cpu_pin

ROOT = Path(__file__).resolve().parents[2]
BLAS = cpu_pin.OPENBLAS_CORETYPE
OK_VIEW = lambda: ([], [])
OK_CORE = lambda: "Haswell"
NPY = cpu_pin.NPY_DISABLE_CPU_FEATURES


def test_the_constants_are_the_ruled_ones():
    assert BLAS == "Haswell"
    names = set(NPY.split(","))
    # the AVX-512 dispatch targets of numpy 2.4.6 (X86_V3, the AVX2 loops, stays on)
    assert names == {"X86_V4", "AVX512_ICL", "AVX512_SPR"}
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
    assert cpu_pin.require(dict(cpu_pin.PIN), view=OK_VIEW, core=OK_CORE) == cpu_pin.PIN
    # the feature list is a set: order and separators do not matter
    spaced = {
        **cpu_pin.PIN,
        "NPY_DISABLE_CPU_FEATURES": " ".join(reversed(NPY.split(","))),
    }
    assert cpu_pin.require(spaced, view=OK_VIEW, core=OK_CORE)


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
        cpu_pin.require(environ, view=OK_VIEW, core=OK_CORE)
    assert refused.value.code == code


def test_the_guard_refuses_a_pin_numpy_is_not_honouring():
    with pytest.raises(cpu_pin.CpuPinRefused) as refused:
        cpu_pin.require(dict(cpu_pin.PIN), view=lambda: (["X86_V4"], []), core=OK_CORE)
    assert refused.value.code == "cpu_dispatch_pin_not_effective"
    # unless the caller opts out of the NumPy check (the variables alone)
    assert cpu_pin.require(
        dict(cpu_pin.PIN),
        check_effective=False,
        view=lambda: (["X86_V4"], []),
        core=OK_CORE,
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


def test_cannot_tell_is_a_refusal_not_a_pass():
    def refuse(**kwargs):
        with pytest.raises(cpu_pin.CpuPinRefused) as refused:
            cpu_pin.require(dict(cpu_pin.PIN), **kwargs)
        return refused.value

    assert (
        refuse(view=lambda: None, core=OK_CORE).code == "cpu_dispatch_pin_unverifiable"
    )
    unknown = refuse(view=lambda: ([], ["X86_V4"]), core=OK_CORE)
    assert unknown.code == "cpu_dispatch_pin_unverifiable" and "X86_V4" in str(unknown)
    assert (
        refuse(view=OK_VIEW, core=lambda: None).code == "cpu_dispatch_pin_unverifiable"
    )
    assert (
        refuse(view=OK_VIEW, core=lambda: "SkylakeX").code
        == "cpu_dispatch_pin_not_effective"
    )


def test_every_pinned_name_is_a_known_feature_of_the_installed_numpy():
    """Otherwise `__cpu_features__.get(name)` would read an unknown name as off and the effectiveness check would be vacuous."""
    seen = cpu_pin.numpy_view()
    assert seen is not None
    _active, unknown = seen
    assert unknown == [], unknown
    from numpy._core._multiarray_umath import __cpu_dispatch__

    # and at least one pinned name is an actual dispatch target of this build (the pin can bite)
    assert set(cpu_pin.NPY_DISABLE_CPU_FEATURES.split(",")) & set(__cpu_dispatch__) or (
        "X86_V3" in __cpu_dispatch__
    )


def test_the_live_openblas_core_is_read_from_the_library_not_the_variable(tmp_path):
    import subprocess
    import sys

    code = (
        "from carbon.challenge_validator import cpu_pin; print(cpu_pin.openblas_core())"
    )
    env = {**__import__("os").environ, "OPENBLAS_CORETYPE": BLAS}
    done = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.strip() == BLAS
