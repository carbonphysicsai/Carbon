"""The CPU-dispatch pin: the same floating-point bytes on every x86-64-v3 host (Validator ruling CPU_DISPATCH_PIN_RULING_20261029).

With one thread, a result still depends on which SIMD kernels the CPU is given: OpenBLAS picks its linear-algebra kernel
per CPU, and NumPy picks its ufunc loops (the AVX-512 ``exp``/``log``/``log1p``/``expm1``) per CPU. Two environment
variables remove both choices:

- ``OPENBLAS_CORETYPE=Haswell`` (AVX2 + FMA, present on every x86-64-v3 machine);
- ``NPY_DISABLE_CPU_FEATURES=<the AVX-512 names>``, keeping the ufuncs on the AVX2 loops everywhere.

They are set in the worker image (``ENV``), the validator receiver's service environment and CI / canonical.sh, from
the constants here (``tests/cpu/test_cpu_dispatch_pin.py`` checks every site against them). ``require`` is the
fail-closed guard: the receiver and the calibration run refuse to score when either variable is unset or different,
or, where NumPy reports it, when a disabled feature is still active. A typed refusal, never a silent unpinned score.

This module is not a producer FILE and changes no producer digest. Standard library only (NumPy is read lazily).
"""

from __future__ import annotations

import os

OPENBLAS_CORETYPE = "Haswell"
#: The AVX-512 feature names NumPy may dispatch on (comma separated: no quoting needed in ENV, Environment= or YAML).
NPY_DISABLE_CPU_FEATURES = (
    "AVX512F,AVX512CD,AVX512_SKX,AVX512_CLX,AVX512_CNL,AVX512_ICL,AVX512_SPR"
)
PIN = {
    "OPENBLAS_CORETYPE": OPENBLAS_CORETYPE,
    "NPY_DISABLE_CPU_FEATURES": NPY_DISABLE_CPU_FEATURES,
}


class CpuPinRefused(RuntimeError):
    """The CPU-dispatch pin is missing, different or not in effect; ``code`` is the closed reason."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def _names(value: str) -> frozenset:
    return frozenset(part for part in value.replace(",", " ").split() if part)


def active_disabled_features():
    """The pinned features NumPy still reports active, or None when NumPy cannot say."""
    try:
        from numpy._core._multiarray_umath import __cpu_features__
    except ImportError:
        return None
    return sorted(
        name for name in _names(NPY_DISABLE_CPU_FEATURES) if __cpu_features__.get(name)
    )


def require(environ=None, *, check_effective=True, features=active_disabled_features):
    """Refuse (``CpuPinRefused``) unless both variables carry exactly the pinned values.

    ``check_effective`` also refuses when NumPy reports a disabled feature still active (the variables were set after
    NumPy started). ``features`` returns the still-active names (a test seam)."""
    environ = os.environ if environ is None else environ
    for name, wanted in PIN.items():
        value = environ.get(name)
        if value is None or value == "":
            raise CpuPinRefused("cpu_dispatch_pin_missing", name)
        same = (
            _names(value) == _names(wanted)
            if name == "NPY_DISABLE_CPU_FEATURES"
            else value == wanted
        )
        if not same:
            raise CpuPinRefused("cpu_dispatch_pin_differs", name)
    if check_effective:
        active = features()
        if active:
            raise CpuPinRefused(
                "cpu_dispatch_pin_not_effective",
                "NumPy still dispatches on " + ",".join(active),
            )
    return dict(PIN)
