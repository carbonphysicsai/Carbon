"""The standing receipt job: the only writer of the official GPU receipt store (OWNER-GPU-OPEN-WITH-READY-01).

It produces official receipts in the background, one entry at a time, and never at the expense of official grading:

- it lowers its own scheduling priority (``os.nice``) before any work;
- before it starts an entry, and between the steps of one (``produce`` is handed ``should_yield``), it asks whether
  official grading is running; while it is, the job waits, and an entry it had to abandon is retried afterwards;
- official grading announces itself by holding the advisory lock ``official-grading.lock`` in the validator state
  (`grading_busy`): the job never takes it, only tests it.

`produce(entry, should_yield)` runs the entry's two rebuilds on the registered class and returns the record to append
(`receipt_store.check_record` refuses a malformed one), or raises `Yielded` when ``should_yield()`` became true.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

GRADING_LOCK = "official-grading.lock"


class Yielded(Exception):
    """The entry's rebuilds were abandoned because official grading started."""


def grading_busy(state_dir) -> bool:
    """Whether official grading holds its lock in ``state_dir`` (the job only tests it, never holds it)."""
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


def run_standing(
    store,
    entries,
    produce,
    *,
    busy,
    nice=19,
    poll_seconds=5.0,
    sleep=time.sleep,
    stop=lambda: False,
):
    """Receipt every entry in ``entries`` in order; returns the digests appended.

    ``busy()`` is the grading probe. The job waits while it is true, yields mid-entry through ``produce``, and stops
    cleanly when ``stop()`` is true."""
    if hasattr(os, "nice"):
        os.nice(nice)
    appended = []
    for entry in entries:
        while True:
            while busy():
                if stop():
                    return appended
                sleep(poll_seconds)
            if stop():
                return appended
            try:
                record = produce(entry, busy)
            except Yielded:
                continue  # grading started mid-entry: wait for it to end, then redo the entry
            appended.append(store.append(record))
            break
    return appended
