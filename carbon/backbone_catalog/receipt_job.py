"""Helpers for the standing receipt worker and the receiver: the official-grading lock.

The WORKER (`scripts/dev/gpu_receipt_worker.py`) is the only writer of the official receipt store
(`receipt_store.ReceiptStore.append`); this module has no append path. It holds what the worker and the receiver
share so official grading is never starved by receipting (OWNER-GPU-OPEN-WITH-READY-01):

- the RECEIVER holds ``official-grading.lock`` (`official_grading`) for each whole official rebuild and grade, and
  releases it on every exit path;
- the WORKER only tests it (`grading_busy`), never takes it, and starts no lane while it is held;
- `Yielded` is what a worker's rebuild raises when it abandons a lane because grading started.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

GRADING_LOCK = "official-grading.lock"


class Yielded(Exception):
    """A rebuild was abandoned because official grading started."""


def grading_busy(state_dir) -> bool:
    """Whether official grading holds its lock in ``state_dir`` (the worker only tests it, never holds it)."""
    import fcntl

    path = Path(state_dir) / GRADING_LOCK
    try:
        fd = os.open(path, os.O_RDWR)
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


@contextmanager
def official_grading(state_dir):
    """Hold ``official-grading.lock`` in ``state_dir`` for the whole of one official rebuild and grade.

    Released on every exit path, an exception included; the lock file is created owner-only. The receiver is the
    only taker."""
    import fcntl

    fd = os.open(Path(state_dir) / GRADING_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
