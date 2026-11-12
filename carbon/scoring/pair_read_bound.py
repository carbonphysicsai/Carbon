"""The repeat pair's byte bound, sized from the graded query's shape (CV-Motor-C, Thu 12 Nov 17:24, SEAL-PATH FINDING).

The source-free pair reader (`inference_pair_evidence`) holds a fixed 4 MiB ceiling, which every live version's pair
fits (about 1.9 MB at Motor 1.5's 646 x 60). Motor 1.8's bank is 2564 rows of a 240-wide row: each phase's
predictions alone are about 12 MB, so the fixed ceiling would refuse EVERY 1.8 grade (`pair_bytes`, typed unavailable,
no miner graded). The reader and both of its grade callers are shared producer files (`physical_dual_pack._SHARED_FILES`)
whose bytes every live pack pins (`accuracy_definition.producer_digest`), so the ceiling is not edited there: a version
that needs more opts in here (`size_produce`), and its grade alone reads under a ceiling sized from ITS bank. Every
other version's grade reads under the unchanged 4 MiB, and no live producer byte moves.

The bound is an upper bound on the bytes, never an estimate: a float64 that ``json.dumps`` writes is at most 24
characters ('-2.2250738585072014e-308') and its separator two more, so 32 bytes per value plus 4 per row of nesting
bounds a phase's predictions; each phase carries them and its receipt (at most the reader's own 64 KiB) as base64,
and the envelope's own fields get 1 MiB. It is a resource cap, not a scientific value: a pair inside it is read and
checked exactly as before (shapes, digests, identities), and a pair outside it is still refused as unavailable.

Raising the ceiling is a process-global change of the reader's module constant, so it happens only under one lock that
every sized produce also holds while it runs (`held`): no other grade in the process reads while a 1.8 grade's ceiling
is up, and the constant is restored however the grade ends.
"""

from __future__ import annotations

import contextlib
import functools
import threading

#: The most bytes ``json.dumps`` writes for one float64 with its ', ' separator (24 + 2), rounded up.
VALUE_BYTES = 32
#: Per row of nesting: '[', ']' and the ', ' after it.
ROW_BYTES = 4
#: The reader's own receipt ceiling (`inference_pair_evidence._MAX_RECEIPT`).
RECEIPT_BYTES = 64 * 1024
#: The envelope's own fields (identities, accounting, timings), far above what they take.
ENVELOPE_BYTES = 1024**2

_LOCK = threading.RLock()
_SIZED: set[tuple[str, str]] = set()


def _base64(n):
    return 4 * ((n + 2) // 3)


def predictions_bytes(rows, width):
    """The most bytes one phase's ``predictions.json`` of ``rows`` x ``width`` takes."""
    if type(rows) is not int or type(width) is not int or rows < 1 or width < 1:
        raise ValueError("pair_read_bound_shape")
    return rows * (width * VALUE_BYTES + ROW_BYTES) + 2


def pair_bytes(rows, width):
    """The most bytes a whole source-free pair of ``rows`` x ``width`` predictions takes (both phases, base64)."""
    return (
        2 * (_base64(predictions_bytes(rows, width)) + _base64(RECEIPT_BYTES))
        + ENVELOPE_BYTES
    )


@contextlib.contextmanager
def held():
    """Hold the bound's lock: nothing in this process reads the pair under a raised ceiling meanwhile."""
    with _LOCK:
        yield


@contextlib.contextmanager
def raised(limit):
    """Read pairs under ``max(the reader's ceiling, limit)`` inside the block; the ceiling is restored after it."""
    from carbon.scoring import inference_pair_evidence as reader

    if type(limit) is not int or limit < 1:
        raise ValueError("pair_read_bound_limit")
    with _LOCK:
        before = reader._MAX_BYTES
        reader._MAX_BYTES = max(before, limit)
        try:
            yield reader._MAX_BYTES
        finally:
            reader._MAX_BYTES = before


def _bank_shape(bank):
    try:
        rows, width = len(bank["case_ids"]), len(bank["references"][0])
    except (KeyError, IndexError, TypeError):
        return None
    return (rows, width) if rows > 0 and width > 0 else None


def size_produce(challenge, version):
    """Grade ``challenge`` ``version`` under a pair ceiling sized from its own bank (idempotent).

    Wraps `physical_dual_pack.produce` once per process: a sized version's produce runs under `raised` at its bank's
    `pair_bytes`; every other produce runs unchanged under `held`. A bank whose shape cannot be read is passed through
    unchanged (the producer refuses it its own way)."""
    from carbon.scoring import physical_dual_pack as physical

    _SIZED.add((challenge, version))
    if getattr(physical.produce, "pair_read_bound", False):
        return
    original = physical.produce

    @functools.wraps(original)
    def produce(adapter, **kwargs):
        key = (getattr(adapter, "CHALLENGE", None), getattr(adapter, "VERSION", None))
        shape = _bank_shape(kwargs.get("bank")) if key in _SIZED else None
        if shape is None:
            with held():
                return original(adapter, **kwargs)
        with raised(pair_bytes(*shape)):
            return original(adapter, **kwargs)

    produce.pair_read_bound = True
    physical.produce = produce
