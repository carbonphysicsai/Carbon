"""How a graph submission's forward runs: eager (op by op) or jitted (compiled once per input shape, so once per params state).

One rule for every path: `train.prepare(..., forward=mode(challenge_id, version))` builds `Prepared.apply`, and practice, the
trainer's train predictions and the judge's inference all call that same `apply`, so a version runs jitted everywhere or nowhere.
A version opts in only by a Validator ruling, listed here; every live (graded) version stays eager, so nothing graded is rescored.
"""

from __future__ import annotations

EAGER = "eager"
JIT = "jit"
MODES = (EAGER, JIT)

#: (challenge_id, version) pairs whose graph forward is jitted. Empty until the Validator rules which versions opt in.
JIT_FORWARD_VERSIONS: frozenset = frozenset()


def mode(challenge_id: str, version: str) -> str:
    """`JIT` for an opted-in version, else `EAGER` (the default, and every live version's)."""
    return JIT if (challenge_id, version) in JIT_FORWARD_VERSIONS else EAGER
