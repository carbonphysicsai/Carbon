"""When a file's stat can stand in for its bytes.

A cache kept under a file's stat (size, mtime, ctime, inode) is never stale as long as every write moves the stat.
It does not, for a write that lands in the same timestamp tick as the one before it: kernels stamp files with a
coarse clock (ticks of a few milliseconds, two seconds on some filesystems), so two writes inside one tick look
identical. Git calls that "racily clean". The rule here is git's: a stat is only trusted once the file has been quiet
for longer than `RACY_NS`, so a file written just now is read again on every call until it has settled, and a file
that settled long ago (an installed wheel, the shipped manifest) is read once."""

from __future__ import annotations

import time

#: A file must have been left alone this long (mtime and ctime) before its stat stands in for its bytes.
RACY_NS = 2_000_000_000


def stat_seal(path, stat):
    """What a file is at this moment: path, size, mtime, ctime and inode."""
    return (
        str(path),
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
        stat.st_ino,
    )


def settled(*times_ns, now_ns=None):
    """True when the newest of these timestamps (ns) is older than `RACY_NS`: nothing can still be rewriting
    inside the same tick, so a seal taken now is safe to keep."""
    now = time.time_ns() if now_ns is None else now_ns
    return all(t < now - RACY_NS for t in times_ns)
