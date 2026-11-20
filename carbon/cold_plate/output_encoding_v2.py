"""DRAFT: Cooling's 34-slot output encoding (intended path
carbon/cold_plate/output_encoding_v2.py). Not wired into any version.

Owner ruling (19 Nov, via model-eval): Cooling 1.8 scores all outputs with
truths, adding `outlet_c` and `peak_x_mm`. `mean_c` is NOT a slot: it is the
length mean of the 30 profile segments. v1 (`output_encoding`) is unchanged and
keeps serving Cooling 1.3-1.7; this module is a NEW versioned encoding.

Slots 0-31 are exactly v1's (slot 0 raw peak excess e, slots 1-30 profile_c,
slot 31 raw pressure q); they are decoded by importing v1's helpers, never by a
copy. Two slots are added:

- slot 32: `outlet_c`, plain and unconstrained. No law is guaranteed on the
  reference read: `exam.GATES` (exam.py:66-96) has no outlet gate; the reference
  reads outlet_c as the solver's `bulkOut` surface value (analysis.py:122,225);
  the reference checks (analysis.py:285-312: mass, energy, iteration change,
  fluid max, Re) never state outlet_c > inlet_c, and the coldest fluid is
  allowed to undershoot the inlet (`inlet_undershoot_k`, analysis.py:234, "not
  judged", analysis.py:299-301). domain.derived_outputs (domain.py:199-208)
  gives inlet + heat/(m cp) > inlet, but that is Carbon's closed form, not the
  reference's read. A softplus excess would therefore invent a law.
- slot 33: `peak_x_mm`, a sigmoid map onto the open interval (0, L) with
  L = FIXED["footprint_mm"] (domain.py:65): peak_x_mm = L * sigmoid(z). The
  reference takes the peak at a heated-face solid cell centre (analysis.py:
  176-188), and centres lie strictly inside the footprint, so the law is
  guaranteed by the reference read. The inverse is logit(peak_x_mm / L); a
  reference outside the open interval is refused (no clamp, no constant).
  Decoded values may touch 0 or L only by float saturation of the sigmoid,
  which stays inside the closed law [0, L].
"""

from __future__ import annotations

import numpy as np

from . import output_encoding as _v1
from .domain import FIXED

ENCODING = "carbon.cold-plate.law-safe-output-encoding.v2"
WIDTH = 34
V1_WIDTH = 32
V1 = slice(0, V1_WIDTH)
OUTLET, PEAK_X = slice(32, 33), slice(33, 34)

#: Registry tokens (carbon/challenge_kit/version_registry.py:39-40 holds the v1 one). The v2 token is new.
TOKEN_V1 = "cooling-law-safe-output-encoding"
TOKEN_V2 = "cooling-law-safe-output-encoding-v2"


def encoding_for_token(token):
    """FAIL-CLOSED lookup (review 19 Nov item 2): the module that serves a version's registry `output_encoding`.

    Exactly TOKEN_V1 -> the v1 module, exactly TOKEN_V2 -> this module. None (a native-row version), any other
    string, or any other type is REFUSED with ValueError: today's rule "any non-None means v1"
    (physical_public.py:55-58; pool_adapters.py:141) must not decide a v2 version. Callers that serve native rows
    test `token is None` themselves BEFORE calling this.
    """
    if token == TOKEN_V1 and type(token) is str:
        return _v1
    if token == TOKEN_V2 and type(token) is str:
        import sys

        return sys.modules[__name__]
    raise ValueError("unknown or missing Cooling output-encoding token")


def require_v2(token):
    """The v2 module for ``token`` or a refusal: the lookup above, then the answer must BE v2 (a v1 token on a
    version that needs 34 slots is refused). Every consumer of a v2 version calls this; none compares strings itself.
    """
    module = encoding_for_token(token)
    if module is _v1:
        raise ValueError("this version needs the v2 Cooling output encoding")
    return module


def arm(challenge_id="chip-cold-plate", version="1.8"):
    """DOOR-START ARMING (call ONCE, from the 1.8 overlay dispatch, cooling18_v2_dual_pack.dispatch): resolve the
    registry entry's `output_encoding` through the fail-closed lookup, so a bad, mistyped or v1 token refuses at door
    start. The overlay accepts any string here (version_overlay._build :97-109 refuses only unknown field names;
    Version.output_encoding is a plain str | None, version_registry.py:93), so this is the only check.
    """
    from carbon.challenge_kit import version_registry

    return require_v2(version_registry.entry(challenge_id, version).output_encoding)


def width_for_token(token):
    """32 for the v1 token, 34 for the v2 token; refuses anything else (same rule as `encoding_for_token`)."""
    module = encoding_for_token(token)  # resolve (and refuse) FIRST, for every token
    return WIDTH if module is not _v1 else V1_WIDTH


def _sigmoid(z):
    z = np.asarray(z, dtype=np.float64)
    e = np.exp(-np.abs(z))
    return np.where(z >= 0, 1.0 / (1.0 + e), e / (1.0 + e))


def _logit(s):
    s = np.asarray(s, dtype=np.float64)
    if not np.all((s > 0.0) & (s < 1.0)):
        raise ValueError("a peak_x_mm reference lies outside the open footprint")
    return np.log(s) - np.log1p(-s)


def encode_targets(targets):
    """Native (n, 34) TRAIN targets as the encoded slots, float64."""
    y = np.asarray(targets, dtype=np.float64)
    if y.ndim != 2 or y.shape[1] != WIDTH or not np.all(np.isfinite(y)):
        raise ValueError("Cooling targets are finite (n, 34) rows")
    length = float(FIXED["footprint_mm"])
    out = np.empty_like(y)
    out[:, V1] = _v1.encode_targets(y[:, V1])  # v1 laws, validation and floor
    out[:, OUTLET] = y[:, OUTLET]  # plain: no law guaranteed by the reference
    out[:, PEAK_X] = _logit(y[:, PEAK_X] / length)
    return out


def decode_row(values):
    """One encoded predicted row (34 numbers) as the native named outputs."""
    row = np.asarray(values, dtype=np.float64).reshape(-1)
    if row.shape != (WIDTH,):
        raise ValueError("an encoded Cooling row holds 34 values")
    native = _v1.decode_row(row[V1])
    if not np.isfinite(row[32]):
        raise ValueError("a decoded outlet_c is not finite")
    native["outlet_c"] = float(row[32])
    if not np.isfinite(
        row[33]
    ):  # rev 6: +-inf saturates the sigmoid to 0 or L; refuse it like NaN
        raise ValueError("an encoded peak_x_mm logit is not finite")
    length = float(FIXED["footprint_mm"])
    peak_x = float(length * _sigmoid(row[33]))
    # decode-side refusal (review item 3): NaN or a value outside [0, L] is refused, never passed through
    if not (0.0 <= peak_x <= length):
        raise ValueError("a decoded peak_x_mm lies outside the footprint [0, L]")
    native["peak_x_mm"] = peak_x
    return native


def decode_flat(values):
    """One encoded row as the native 34-value row (peak, 30 profile, pressure,
    outlet, peak_x_mm)."""
    native = decode_row(values)
    return [
        native["peak_c"],
        *native["profile_c"],
        native["pressure_drop_pa"],
        native["outlet_c"],
        native["peak_x_mm"],
    ]
