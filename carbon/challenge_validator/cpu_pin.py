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
#: The AVX-512 DISPATCH TARGETS of the pinned NumPy (2.4.6: ``__cpu_dispatch__`` = X86_V3, X86_V4, AVX512_ICL,
#: AVX512_SPR; X86_V4 is the group carrying AVX512F/CD/SKX/CLX/CNL). Only a dispatch target can be disabled: naming the
#: raw features (AVX512F ...) did nothing on the pinned build (measured on runner2, EPYC Genoa). X86_V3 (AVX2) stays.
#: Comma separated: no quoting needed in ENV, Environment= or YAML.
NPY_DISABLE_CPU_FEATURES = "X86_V4,AVX512_ICL,AVX512_SPR"
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


def numpy_view():
    """(still-active, unknown): the pinned names NumPy reports ON, and the pinned names it does not know at all.

    ``None`` when NumPy cannot say. A name absent from NumPy's feature dictionary would read as "off" and make the
    check vacuous, so an unknown name is reported separately and refused."""
    try:
        from numpy._core._multiarray_umath import __cpu_features__
    except ImportError:
        return None
    names = sorted(_names(NPY_DISABLE_CPU_FEATURES))
    unknown = [name for name in names if name not in __cpu_features__]
    active = [name for name in names if __cpu_features__.get(name)]
    return active, unknown


_SYMBOLS = (
    "scipy_openblas_get_corename64_",
    "scipy_openblas_get_corename",
    "openblas_get_corename64_",
    "openblas_get_corename",
)


def openblas_core():
    """The core name of the OpenBLAS NumPy actually runs, or None when it cannot be read.

    Loads the same bundled library NumPy already loaded (``numpy.libs``), so the answer is the live core, not the
    environment variable."""
    try:
        import ctypes
        import glob

        import numpy

        libs = os.path.join(os.path.dirname(numpy.__file__), os.pardir, "numpy.libs")
        for path in sorted(glob.glob(os.path.join(libs, "*openblas*"))):
            try:
                library = ctypes.CDLL(path)
            except OSError:
                continue
            for symbol in _SYMBOLS:
                if hasattr(library, symbol):
                    function = getattr(library, symbol)
                    function.restype = ctypes.c_char_p
                    return function().decode("ascii")
    except Exception:  # noqa: BLE001 - unreadable is the answer, never a crash
        return None
    return None


def require(environ=None, *, check_effective=True, view=numpy_view, core=openblas_core):
    """Refuse (``CpuPinRefused``) unless both variables carry exactly the pinned values AND the pin is in effect.

    With ``check_effective`` (the default) it also refuses when NumPy cannot be read, when a pinned name is not a
    feature of this NumPy (``cpu_dispatch_pin_unverifiable``: the check would be vacuous), when a pinned feature is
    still active, or when OpenBLAS's live core is not the pinned one (``cpu_dispatch_pin_not_effective``). "Cannot
    tell" is a refusal, never a pass. ``view`` and ``core`` are test seams."""
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
        seen = view()
        if seen is None:
            raise CpuPinRefused("cpu_dispatch_pin_unverifiable", "NumPy dispatch")
        active, unknown = seen
        if unknown:
            raise CpuPinRefused(
                "cpu_dispatch_pin_unverifiable",
                "not a feature of this NumPy: " + ",".join(unknown),
            )
        if active:
            raise CpuPinRefused(
                "cpu_dispatch_pin_not_effective",
                "NumPy still dispatches on " + ",".join(active),
            )
        live = core()
        if live is None:
            raise CpuPinRefused("cpu_dispatch_pin_unverifiable", "OpenBLAS core")
        if live != OPENBLAS_CORETYPE:
            raise CpuPinRefused(
                "cpu_dispatch_pin_not_effective", f"OpenBLAS core is {live}"
            )
    return dict(PIN)
