"""Cooling 1.3's dual pack adapter: Cooling's measurement on decoded rows.

Cooling 1.3 serves the law-safe output encoding (Validator ruling
VALIDATOR_RULING_COOLING12_PEAK_GATE_20261022, finding G1;
`carbon.cold_plate.output_encoding`): its TRAIN and every model's predicted row
carry slot 0 as a raw peak excess and slot 31 as a raw pressure. This adapter
decodes each predicted row to the native 32 values and hands Cooling's own
measurement (`cooling_dual_pack`) the native TRAIN, so the gates, components,
scales, baseline and score are exactly Cooling's, on decoded outputs.

It is its own module so Cooling 1.0-1.2's producer files, and every pack
already bound to their producer digest, are unchanged; its producer identity
covers Cooling's files and this one. Everything not defined here is
`cooling_dual_pack`'s.
"""

from __future__ import annotations

from carbon.scoring import cooling_dual_pack as _cooling

CHALLENGE = _cooling.CHALLENGE
VERSION = "1.3"
EVALUATION_VERSION = "cooling-dual-development-bank-48-v4"
CASE_ID = _cooling.CASE_ID
VERSIONS = {VERSION: (EVALUATION_VERSION, CASE_ID)}
FILES = (*_cooling.FILES, "cooling_encoded_dual_pack.py")


def _native_train():
    from carbon.challenge_kit import physical_public_train

    return physical_public_train.load_public_train(CHALLENGE)["train"]


def _decoded(rows):
    """Each predicted row decoded; a row that is not 32 finite numbers stays
    malformed (32 NaN), so Cooling's `schema_finite` gate fails that case as
    the candidate's typed gate failure, never an exception (Validator,
    chosen-implementation receipt)."""
    import math

    from carbon.cold_plate.output_encoding import decode_flat

    def one(row):
        try:
            values = [float(v) for v in row]
        except (TypeError, ValueError):
            values = []
        if len(values) != 32 or not all(math.isfinite(v) for v in values):
            return [math.nan] * 32
        return decode_flat(values)

    return [one(row) for row in rows]


def definition(*, bank, train_raw, rule="baseline_legs"):
    del train_raw
    return _cooling.definition(bank=bank, train_raw=_native_train(), rule=rule)


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """Cooling's measurement of decoded rows against the native TRAIN."""
    del train_raw
    return _cooling.measure(
        bank_rows=bank_rows,
        outputs=_decoded(outputs),
        repeats=[_decoded(repeat) for repeat in repeats],
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=_native_train(),
        names=names,
    )


def applied_pack(*, bank_rows, definition, limits, objective, train_raw, names):
    """Cooling's applied pack: its learned-krr-v1 baseline on the native
    TRAIN, measured natively (the baseline's rows are native)."""
    del train_raw
    return _cooling.applied_pack(
        bank_rows=bank_rows,
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=_native_train(),
        names=names,
    )


def sealed_adapter(version):
    """Cooling 1.3's sealed exam adapter (``cooling-dual-sealed-batch-16-v2``): the
    model's encoded rows are decoded, then Cooling's own sealed measurement runs on the
    native rows against the unchanged sealed bank. The 1.2 and 1.3 sealed scores are
    therefore comparable. None for any other version."""
    if version != VERSION:
        return None
    from carbon.scoring import physical_dual_pack as physical

    return physical.Variant(
        _SELF, VERSION, _cooling.SEALED_EVALUATION_VERSION, _cooling.CASE_ID
    )


def adapter(rule="baseline_legs"):
    """This adapter; 1.3 serves the default leg-minimum rule only."""
    if rule != "baseline_legs":
        raise ValueError("Cooling 1.3 serves the baseline_legs rule")
    return _SELF


def producer_digest():
    from carbon.scoring import physical_dual_pack as physical

    return physical.producer_digest(_SELF)


def produce(**kwargs):
    from carbon.scoring import physical_dual_pack as physical

    return physical.produce(_SELF, **kwargs)


def __getattr__(name):
    return getattr(_cooling, name)


_SELF = __import__("sys").modules[__name__]
