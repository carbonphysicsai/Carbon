"""A counter that says "the catalog install changed under any earlier reading".

The installer's launcher bumps it when an install starts, and while one runs; the display-only readiness snapshot
(the verifier beside this module) reads it and discards any run that began under an older value. It holds no readiness data and
no decision reads it, so the install path can import this module without touching the snapshot.
"""

import threading

_lock = threading.Lock()
_value = 0


def bump() -> int:
    global _value
    with _lock:
        _value += 1
        return _value


def current() -> int:
    with _lock:
        return _value
