"""Battery's fixed TRAIN decoder and raw tensor boundary for construction.

The registered identity belongs to the original gzip JSONL bytes. Decoding or
flattening them never creates a replacement TRAIN identity. These helpers select
no training procedure, normalization, scoring rule or model family.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math

import numpy as np

from carbon.reconstruction.worker.model import INPUT_BYTES, OUTPUT_BYTES

from . import challenge, domain

OUTPUT_WIDTH = 2 * domain.GRID_POINTS + 1 + len(domain.CAPACITY_CYCLES)


def decode_train(raw: bytes) -> domain.TrainingData:
    """Decode only Battery's exact 400-record public TRAIN, in retained order."""
    if (
        type(raw) is not bytes
        or not 0 < len(raw) <= INPUT_BYTES
        or hashlib.sha256(raw).hexdigest() != challenge.TRAIN_V1_SHA256
    ):
        raise challenge.MaterialMismatch("train_v1 does not match its pinned digest")
    try:
        records = [
            json.loads(line)
            for line in gzip.decompress(raw).splitlines()
            if line.strip()
        ]
        if len(records) != challenge.TRAIN_V1_CASES or any(
            type(row) is not dict
            or row.get("role") != "train"
            or row.get("status") != "OK"
            for row in records
        ):
            raise challenge.MaterialMismatch("train_v1 is not 400 OK TRAIN cases")
        train = domain.TrainingData.from_records(records)
        count = challenge.TRAIN_V1_CASES
        for array, shape in (
            (train.x, (count, len(domain.INPUTS))),
            (train.v, (count, domain.GRID_POINTS)),
            (train.t, (count, domain.GRID_POINTS)),
            (train.eta, (count,)),
            (train.q, (count, len(domain.CAPACITY_CYCLES))),
        ):
            if (
                array.shape != shape
                or array.dtype.kind not in "fiu"
                or not np.isfinite(array).all()
            ):
                raise challenge.MaterialMismatch(
                    "train_v1 tensor shape or value differs"
                )
        if len(set(train.case_ids)) != count or any(
            type(case) is not str or not case for case in train.case_ids
        ):
            raise challenge.MaterialMismatch("train_v1 case identities differ")
        return train
    except (
        OSError,
        EOFError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        RecursionError,
    ) as error:
        if type(error) is challenge.MaterialMismatch:
            raise
        raise challenge.MaterialMismatch("train_v1 record malformed") from None


def train_tensors(raw: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Raw inputs and [voltage, temperature, plating, capacity] TRAIN targets."""
    train = decode_train(raw)
    return train.x.copy(), np.column_stack((train.v, train.t, train.eta, train.q))


def case_inputs(cases: list[dict]) -> np.ndarray:
    """Convert input-only cases using Battery's existing raw input order/bounds."""
    if (
        type(cases) is not list
        or not cases
        or len(cases) * len(domain.INPUTS) * np.dtype(float).itemsize > INPUT_BYTES
    ):
        raise challenge.MaterialMismatch("battery input cases invalid")
    seen = set()
    rows = []
    for case in cases:
        if type(case) is not dict or set(case) != {"case_id", "inputs"}:
            raise challenge.MaterialMismatch("battery input cases invalid")
        case_id, values = case["case_id"], case["inputs"]
        if (
            type(case_id) is not str
            or not case_id
            or case_id in seen
            or type(values) is not dict
            or set(values) != set(domain.INPUTS)
        ):
            raise challenge.MaterialMismatch("battery input cases invalid")
        seen.add(case_id)
        row = []
        for name in domain.INPUTS:
            value = values[name]
            low, high = domain.INPUT_BOUNDS[name]
            if (
                type(value) not in (int, float)
                or not low <= value <= high
                or not math.isfinite(value)
            ):
                raise challenge.MaterialMismatch("battery input value invalid")
            row.append(value)
        rows.append(row)
    return np.asarray(rows, dtype=float)


def output_predictions(values, case_ids) -> dict:
    """Split flat raw physical outputs into the established Battery wire shape."""
    from .recipes import to_predictions

    if (
        type(case_ids) not in (list, tuple)
        or not case_ids
        or any(type(case) is not str or not case for case in case_ids)
        or len(set(case_ids)) != len(case_ids)
    ):
        raise challenge.MaterialMismatch("battery prediction case identities invalid")
    try:
        array = np.asarray(values)
        if (
            array.shape != (len(case_ids), OUTPUT_WIDTH)
            or array.dtype.kind not in "fiu"
            or array.nbytes > OUTPUT_BYTES
            or not np.isfinite(array).all()
        ):
            raise challenge.MaterialMismatch("battery prediction tensor invalid")
        g = domain.GRID_POINTS
        return to_predictions(
            {
                "v": array[:, :g],
                "t": array[:, g : 2 * g],
                "eta": array[:, 2 * g],
                "q": array[:, 2 * g + 1 :],
            },
            case_ids,
        )
    except (ValueError, TypeError) as error:
        if type(error) is challenge.MaterialMismatch:
            raise
        raise challenge.MaterialMismatch("battery prediction tensor invalid") from None
