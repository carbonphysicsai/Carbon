"""Bounded fixture-only in-memory store for B-05 canonical objects."""

from __future__ import annotations

from .canonical import canonical_bytes, load_canonical_document, measurement_ref
from .errors import MeasurementInputCode, MeasurementStoreError
from .model import (
    MeasurementAuthoringObject,
    MeasurementContract,
    MeasurementQualificationEvidence,
    UncertaintyPolicy,
)
from .refs import MeasurementTopLevelRef, reconstruct_measurement_ref

MAX_MEASUREMENT_STORE_OBJECTS = 1024


class MeasurementFixtureStore:
    """Store exact fixture bytes; this grants no persistence or LIVE authority."""

    def __init__(self) -> None:
        self._documents: dict[MeasurementTopLevelRef, bytes] = {}

    def put(self, value: MeasurementAuthoringObject) -> MeasurementTopLevelRef:
        if type(value) not in (
            MeasurementContract,
            MeasurementQualificationEvidence,
            UncertaintyPolicy,
        ):
            raise MeasurementStoreError(MeasurementInputCode.WRONG_TYPE, path="/")
        if value.fixture_origin is not True:
            raise MeasurementStoreError(
                MeasurementInputCode.FIXTURE_REQUIRED, path="/fixture_origin"
            )
        ref = measurement_ref(value)
        if (
            ref not in self._documents
            and len(self._documents) >= MAX_MEASUREMENT_STORE_OBJECTS
        ):
            raise MeasurementStoreError(MeasurementInputCode.SIZE_LIMIT, path="/")
        self._documents[ref] = canonical_bytes(value)
        return ref

    def get(self, ref: MeasurementTopLevelRef) -> MeasurementAuthoringObject:
        try:
            exact_ref = reconstruct_measurement_ref(ref)
        except (AttributeError, TypeError, ValueError):
            raise MeasurementStoreError(
                MeasurementInputCode.WRONG_TYPE, path="/ref"
            ) from None
        source = self._documents.get(exact_ref)
        if source is None:
            raise MeasurementStoreError(
                MeasurementInputCode.UNKNOWN_OBJECT, path="/ref"
            )
        value = load_canonical_document(source)
        if measurement_ref(value) != exact_ref:
            raise MeasurementStoreError(
                MeasurementInputCode.DIGEST_MISMATCH, path="/ref"
            )
        return value

    def __len__(self) -> int:
        return len(self._documents)


__all__ = ("MAX_MEASUREMENT_STORE_OBJECTS", "MeasurementFixtureStore")
