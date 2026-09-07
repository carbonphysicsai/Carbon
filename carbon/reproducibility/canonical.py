"""Deterministic canonical fixture encoding for B-E1 values."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from enum import Enum

from .refs import REPRODUCIBILITY_DOCUMENT_HEADER

MAX_REPRODUCIBILITY_DOCUMENT_BYTES = 8 * 1024 * 1024


def _payload(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "record_type": type(value).__name__,
            **{
                field.name: _payload(getattr(value, field.name))
                for field in fields(value)
            },
        }
    if type(value) is tuple:
        return [_payload(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError("value is not canonically encodable")


def canonical_payload(value: object) -> dict[str, object]:
    payload = _payload(value)
    if type(payload) is not dict:
        raise TypeError("canonical root must be an immutable record")
    return payload


def canonical_bytes(value: object) -> bytes:
    encoded = json.dumps(
        canonical_payload(value),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    document = REPRODUCIBILITY_DOCUMENT_HEADER + encoded
    if len(document) > MAX_REPRODUCIBILITY_DOCUMENT_BYTES:
        raise ValueError("canonical reproducibility document exceeds its bound")
    return document


def canonical_digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"
