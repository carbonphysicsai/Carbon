"""Per-request step timings of the door's construction submit (mcp_slow, live 116 21 Nov 2026).

A submit (POST /carbon/v1/mcp answered 202) took 1.5-26.4 s (median 10 s) and the miner client stops at 30 s; py-spy
cannot attach to the receiver (kernel.yama.ptrace_scope 1, live-ops 06:51Z), so the door names its own slow step: the
submit path opens a collection (`collecting`), each instrumented step adds its wall milliseconds (`step`), and the
caller writes ONE journal line (``submit_timing``) with the step names and milliseconds only: never a hotkey, task id,
recipe, path or value. Outside a collection every `step` is a no-op, so no other caller changes.
"""

from __future__ import annotations

import contextlib
import contextvars
import time

_STEPS: contextvars.ContextVar = contextvars.ContextVar(
    "carbon_submit_steps", default=None
)


@contextlib.contextmanager
def collecting():
    """Collect the step timings of the calling context; yields the ``{step: ms}`` dict."""
    steps = {}
    token = _STEPS.set(steps)
    try:
        yield steps
    finally:
        _STEPS.reset(token)


@contextlib.contextmanager
def step(name):
    """Add this block's wall milliseconds to ``name`` in the current collection (a no-op outside one)."""
    steps = _STEPS.get()
    if steps is None:
        yield
        return
    began = time.monotonic()
    try:
        yield
    finally:
        steps[name] = steps.get(name, 0) + int((time.monotonic() - began) * 1000)


def enter(stack, name, context):
    """Enter ``context`` on ``stack`` and time only the entering (a lock or place WAIT), as `step` ``name``."""
    with step(name):
        return stack.enter_context(context)
