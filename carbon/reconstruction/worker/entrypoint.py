"""Fixed C-03 image entry point with a controller verification gate."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from carbon.reconstruction.worker.protocol import run_staged_worker

_released = False


def _release(signum: int, frame: object) -> None:
    del signum, frame
    global _released
    _released = True


def main() -> int:
    scratch = Path("/scratch")
    for child in ("home", "tmp", "cache", "jax-cache"):
        (scratch / child).mkdir(mode=0o700, exist_ok=False)
    (scratch / "control-ready").touch(mode=0o400, exist_ok=False)
    signal.signal(signal.SIGTERM, _release)
    signal.signal(signal.SIGINT, _release)
    while not (scratch / "authorized").is_file():
        if _released:
            return 143
        time.sleep(0.05)
    result = run_staged_worker(Path("/input"), scratch)
    if result:
        return result
    # Keep the tmpfs mounted while the trusted controller snapshots output.
    # TERM ends this provisional state; success is decided only afterwards.
    while not _released:
        time.sleep(0.1)
    try:
        os.sync()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
