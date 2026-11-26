"""A graded answer that is not finite, proven by the worker program itself (owner G-LEAD-75, 24 Nov 2026: for the new
exam versions only, the first proven non-finite answer in a day is given back free and every further one counts as a try,
counted per funding group, not per hotkey; only a proven non-finite output counts, not a shape or type error; 1.8 keeps
its current rule).

Today every inference program refuses its own output with ONE sentence for a wrong shape, a wrong dtype or a non-finite value
(`auto_retry.OUTPUT_CONTRACT_DIFFERS`: cause unknown). A version under the rule runs the same program with that one check split
in two: shape, dtype and kind first (today's sentence), then finiteness (`RAISE`, which begins with today's sentence, so every
existing reader still matches it). The second sentence is raised only when the query's own inputs are finite: a non-finite
input is Carbon's, and keeps today's sentence. Nothing else in the program moves, and every other version's text is unchanged
byte for byte.

A version is under the rule when the code names it (`CODE_SERVED`) or its exam registry build row does
(``nonfinite_rule``, `exam_build`): no exam is named anywhere else. The charge itself is `auto_grade` and
`exam_cap.ExamCap.settle_nonfinite`.
"""

from __future__ import annotations

#: The one registered form of the rule (the value of a build row's ``nonfinite_rule``).
RULE = "first_free_per_day.v1"
#: The code-served versions under the rule; a version registered by data names it in its build row.
CODE_SERVED = frozenset()

#: Today's sentence, and the second one (its prefix is today's).
CONTRACT = "bundle inference output contract differs"
RAISE = CONTRACT + ": the model returned a non-finite value"

_FINAL = (
    '    or result.dtype.kind not in "fiu" or not np.isfinite(result).all()):\n'
    f'    raise ValueError("{CONTRACT}")\n'
)
_FINAL_SPLIT = (
    '    or result.dtype.kind not in "fiu"):\n'
    f'    raise ValueError("{CONTRACT}")\n'
    "if not np.isfinite(result).all():\n"
    "    raise ValueError(\n"
    f'        "{RAISE}"\n'
    "        if np.isfinite(inputs).all()\n"
    f'        else "{CONTRACT}"\n'
    "    )\n"
)
#: The same check inside a trust program's split of the raw output (`trust_infer`), one level deeper.
_TRUST = (
    '            or result.dtype.kind not in "fiu" or not np.isfinite(result).all()):\n'
    f'        raise ValueError("{CONTRACT}")\n'
)
_TRUST_SPLIT = (
    '            or result.dtype.kind not in "fiu"):\n'
    f'        raise ValueError("{CONTRACT}")\n'
    "    if not np.isfinite(result).all():\n"
    "        raise ValueError(\n"
    f'            "{RAISE}"\n'
    "            if np.isfinite(inputs).all()\n"
    f'            else "{CONTRACT}"\n'
    "        )\n"
)


def applies(challenge_id: str, version: str) -> bool:
    """Whether this version is under the rule."""
    from carbon.challenge_registry import exam_build

    return (challenge_id, version) in CODE_SERVED or exam_build.nonfinite_rule(
        challenge_id, version
    ) == RULE


def _replace(program, old, new):
    if type(program) is not str or program.count(old) != 1:
        raise RuntimeError("non-finite program anchor moved")
    return program.replace(old, new)


def program(base: str) -> str:
    """``base`` (an inference program) with its one output check split in two."""
    return _replace(base, "\n" + _FINAL, "\n" + _FINAL_SPLIT)


def trust(base: str) -> str:
    """A trust program (`trust_infer.trust_program`) with the check inside its split split the same way (the program it was
    made from already has its final check split)."""
    return _replace(base, "\n" + _TRUST, "\n" + _TRUST_SPLIT)


def for_version(challenge_id: str, version: str, base: str) -> str:
    """``base`` itself, or its split form for a version under the rule."""
    return program(base) if applies(challenge_id, version) else base


def proven(failure) -> bool:
    """Whether ``failure`` is a worker's own refusal of a non-finite output: a `WorkerFailure` whose private diagnostic holds
    `RAISE`, and no replay of an earlier run. A graph inference runs the candidate's graph only, so its diagnostic is the
    program's own traceback."""
    from carbon.reconstruction.worker.model import WorkerFailure

    diagnostic = getattr(failure, "private_diagnostic", None)
    return (
        isinstance(failure, WorkerFailure)
        and getattr(failure, "replayed", False) is not True
        and type(diagnostic) is bytes
        and RAISE.encode() in diagnostic
    )
