"""Work done once while one capability document is built, and forgotten when the build ends.

Building the document describes every catalog version, and describing a version rebuilds the same construction kit
once per catalog entry (Motor 1.5 has 78). Inside `scope()` that kit is built once per (Challenge, version) and each
caller gets its own copy; outside a scope nothing is kept, so a later read, a changed input or a test's patch is
never answered from an old build."""

from __future__ import annotations

import contextlib
import contextvars
import copy

_MEMO = contextvars.ContextVar("carbon_registry_build_memo", default=None)


@contextlib.contextmanager
def scope():
    """Memoize `once` for the duration of the block (one build)."""
    if _MEMO.get() is not None:  # nested: the outer build's memo stands
        yield
        return
    token = _MEMO.set({})
    try:
        yield
    finally:
        _MEMO.reset(token)


def once(key, compute):
    """`compute()`, kept under `key` for the rest of the current build (a copy each time); not kept outside one."""
    memo = _MEMO.get()
    if memo is None:
        return compute()
    if key not in memo:
        memo[key] = compute()
    return copy.deepcopy(memo[key])
