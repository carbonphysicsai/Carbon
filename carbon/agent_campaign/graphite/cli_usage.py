"""What the Graphite runners tell a person or an agent at the command line
(GRAPHITE-RUNNER-USABILITY-01).

- `ChallengeParser`: an `argparse` parser whose usage errors about
  `--challenge` also list the Challenge tokens the neutral driver accepts.
  `--challenge` stays required with no default: the driver never substitutes
  a Challenge (B-02B, #584), even on a host that registers only one.
- `next_step`: the typed next step for a session's recorded end, so a
  terminal `reconciliation_required` session names what to do instead of
  inviting a rerun that only prints the same end again.
"""

from __future__ import annotations

import argparse

from carbon.challenge_validator import scoring as challenge_scoring


def challenge_tokens():
    """The Challenge tokens with a registered scoring, sorted. Every phase
    command resolves `--challenge` through this registry first; a phase may
    refuse a registered token later (phase 4 needs an attack adapter)."""
    return tuple(challenge_scoring.registered())


def challenge_help(what="the Challenge's contract token"):
    return f"{what}, required, no default: one of {', '.join(challenge_tokens())}"


class ChallengeParser(argparse.ArgumentParser):
    """`argparse.ArgumentParser` whose `--challenge` usage errors list the
    accepted tokens. Subcommand parsers inherit it."""

    def error(self, message):
        if "--challenge" in message:
            message = (
                f"{message} (accepted --challenge tokens: "
                f"{', '.join(challenge_tokens())}; there is no default)"
            )
        super().error(message)


#: A session's recorded failure code -> what the operator does next. The
#: session is terminal either way: running the same command again prints its
#: recorded end and changes nothing.
NEXT_STEPS = {
    "reconciliation_required": {
        "terminal": True,
        "resumable": False,
        "do": [
            (
                "phase 3: run `phase3 reconcile` (same --root, --challenge, "
                "--grant, --code-ref and RunPod key file): it terminates and "
                "settles every pod the session may have left; it exits 0 when "
                "none is live"
            ),
            (
                "read `status`: each pod's booked amount and its basis; an "
                "interrupted proposal or an unknown model call keeps its full "
                "reservation, nothing settles it"
            ),
            (
                "a further attempt is a new session number (`--session N`) "
                "within the grant's permitted runs, never a rerun of this one"
            ),
        ],
    },
}


def next_step(state, failure):
    """The next step for a session ended `state` with `failure`, or None when
    the end needs no operator step beyond reading it."""
    if state != "failed" or not isinstance(failure, dict):
        return None
    step = NEXT_STEPS.get(failure.get("code"))
    if step is None:
        return None
    return {"failure_code": failure["code"], **step}
