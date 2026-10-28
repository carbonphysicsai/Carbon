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
#: 1.4 is graph route v2 (`challenge_kit.version_registry`): 1.3's encoded
#: TRAIN, bank and measurement under 1.3's evaluation version.
VERSIONS = {
    version: (EVALUATION_VERSION, CASE_ID) for version in (VERSION, "1.4", "1.5")
}
#: Pool-graded: the sealed grader's cells and probes plus the pool set (`pool_exam`).
POOL_VERSIONS = {
    "1.5": ("cooling-pool-sealed-v1", "cooling-sealed-pool-set"),
    "1.6": ("cooling-pool-sealed-v2", "cooling-sealed-pool-set"),
}
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
    therefore comparable. 1.4 (graph route v2, construction only) is graded the
    same way, from 1.3's sealed batches. Cooling 1.6 dispatches to its prospective
    hotspot-response correction, including callers of this module's pack writer.
    None for any other version."""
    if version == "1.6":
        from carbon.scoring import cooling_hotspot_dual_pack

        return cooling_hotspot_dual_pack.sealed_adapter(version)
    if version not in VERSIONS:
        return None
    if version in POOL_VERSIONS:
        from carbon.scoring import pool_version

        evaluation, case_id = POOL_VERSIONS[version]
        return pool_version.variant(
            _SELF, version, evaluation, case_id, challenge_id=CHALLENGE
        )
    from carbon.scoring import physical_dual_pack as physical

    return physical.Variant(
        _SELF, version, _cooling.SEALED_EVALUATION_VERSION, _cooling.CASE_ID
    )


#: The sealed pack's version suffix and grid (16 cells: 4 designs x 4 conditions).
PACK_SUFFIX = "-sealed-batch-16"
GRID = 4


def is_sealed_bank(bank) -> bool:
    """Whether a bank declares Cooling's sealed grid: 16 cells, every cohort ``decision_sealed_grid`` (private
    probes aside), each a distinct design x condition cell of the 4 x 4 grid."""
    from carbon.scoring import probe_design
    from carbon.scoring import sealed_grid_common as grid_common

    if type(bank) is not dict:
        return False
    cohorts, records = bank.get("cohorts"), bank.get("reference_records")
    if (
        type(cohorts) not in (tuple, list)
        or type(records) not in (tuple, list)
        or len(cohorts) != len(records)
    ):
        return False
    keep = [i for i, c in enumerate(cohorts) if c != probe_design.PROBE_COHORT]
    return grid_common.is_grid_bank(
        [cohorts[i] for i in keep],
        [records[i] for i in keep],
        shape=(GRID, GRID),
        design_of=lambda r: r.get("design_id"),
        condition_of=lambda r: r.get("condition_id"),
    )


def is_pool_bank(bank) -> bool:
    """Whether a bank is a pool version's: the sealed grid (and its probes) plus at least one pool row
    (cohort `pool_design`, inputs only), nothing else."""
    from carbon.scoring import pool_version

    return pool_version.is_pool_bank(bank, is_sealed_bank)


def write_sealed_pack(root, bank, *, version="1.5", **platform):
    """Write a Cooling sealed batch's complete receiver pack (see `sealed_pack_writer.write`): the sealed grid
    with its private probes and, for a pool version, the pool rows. The model answers in the encoded space, so
    the pack's adapter is this module's sealed adapter (decoded, then Cooling's own measurement).
    """
    from carbon.challenge_kit import cooling_sealed_pack
    from carbon.scoring import sealed_pack_writer

    return sealed_pack_writer.write(
        sealed_adapter(version),
        cooling_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=version,
        is_sealed_bank=is_pool_bank if version in POOL_VERSIONS else is_sealed_bank,
        refusal=_cooling.Refused("cooling_bank_population"),
        pack_suffix=PACK_SUFFIX,
        **platform,
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
