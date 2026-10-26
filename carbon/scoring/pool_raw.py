"""A pool runner's raw output laid out as the bank's native flat output row.

The pool merge keeps each solved design's own record outputs (`pool-raw-<tid>.json`, `raw_outputs`): a dict keyed
by output name (Motor `{"torque_nm": [60 values]}`), not the flat row `pool_grader.attach_raw` and the gates read.
The flat row is the one the sealed bank builders lay a reference record out as (`motor_sealed_pack`,
`cooling_sealed_pack`, `f02_sealed_pack`, `f08_sealed_pack`): zeros of the interface width, every named output
written into its slice. This is that layout, read from the same interface documents, so a pool truth and a bank
reference are the same row for the same record. It is a layout only: it checks widths and finiteness, never a
physical value.

F08's slices also hold the damped peaks, which the reference record keeps under `damping`, not `outputs`; its raw
item is therefore the record's two fields, `{"outputs": ..., "damping": ...}`. An F08 item without them cannot be
laid out and is refused, never filled with zeros.
"""

from __future__ import annotations

import math

KINDS = ("f02", "f08", "motor", "cooling")


class PoolRawRefused(ValueError):
    """A typed refusal (the code names the check)."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _finite(values):
    out = [float(v) for v in values]
    if not all(math.isfinite(v) for v in out):
        raise PoolRawRefused("pool_raw_not_finite")
    return out


def _slices(kind, version):
    if kind == "f02":
        from carbon.challenge_kit import f02_public

        return f02_public.interface_document("f02", version)["output"]["named_slices"]
    if kind == "f08":
        from carbon.challenge_kit import f08_public

        return f08_public.interface_document("f08-ribbed-bracket", version)["output"][
            "named_slices"
        ]
    from carbon.challenge_kit import physical_public_train

    challenge_id = "electric-motor-magnetics" if kind == "motor" else "chip-cold-plate"
    return physical_public_train.numeric_interface_document(challenge_id)[
        "target_slices"
    ]


def _place(row, slices, name, value):
    start, end = slices[name]
    value = value if type(value) is list else [value]
    if len(value) != end - start:
        raise PoolRawRefused("pool_raw_output_has_the_wrong_width")
    row[start:end] = _finite(value)


def flat_row(kind, version, raw):
    """The bank's native flat output row of one pool raw item, or `PoolRawRefused`.

    A list is already a flat row (its width checked); a dict is the runner's outputs, laid out by the version's
    interface slices (F08: the record's `outputs` and `damping`)."""
    if type(raw) is tuple:
        raw = list(raw)
    if type(raw) is list and kind not in KINDS:
        return _finite(
            raw
        )  # a flat row for a kind with no registered layout (a toy binding): finite only
    if kind not in KINDS:
        raise PoolRawRefused("pool_raw_kind_unknown")
    slices = _slices(kind, version)
    width = max(end for _, end in slices.values())
    if type(raw) is list:
        if len(raw) != width:
            raise PoolRawRefused("pool_raw_row_is_not_the_interface_width")
        return _finite(raw)
    if type(raw) is not dict:
        raise PoolRawRefused("pool_raw_item_is_not_a_row_or_outputs")
    row = [0.0] * width
    if kind == "f08":
        from carbon.challenge_kit.f08_sealed_pack import TARGETS

        outputs, damping = raw.get("outputs"), raw.get("damping")
        if type(outputs) is not dict or type(damping) is not dict:
            raise PoolRawRefused("pool_raw_f08_needs_the_records_outputs_and_damping")
        try:
            for name, zeta, key in TARGETS:
                _place(
                    row,
                    slices,
                    name,
                    outputs[name] if zeta is None else damping[zeta][key],
                )
        except (KeyError, TypeError):
            raise PoolRawRefused("pool_raw_f08_output_missing") from None
        return row
    try:
        if kind == "f02":
            _place(row, slices, "peak_top_c", raw["peak_top_c"])
        else:
            for name in slices:
                _place(row, slices, name, raw[name])
    except (KeyError, TypeError):
        raise PoolRawRefused("pool_raw_output_missing") from None
    return row


__all__ = ["KINDS", "PoolRawRefused", "flat_row"]
