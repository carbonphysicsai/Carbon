"""Practice-only mode: practise without registering (LP practice-only).

A miner who chose Setup's "Practise without registering" runs their agent and
practises on their own machine with no registration, no keys and no signer.
What reaches the chain or a validator - freezing a candidate, submitting it,
committing its digest - needs a registered hotkey and its signer, so every
such operation refuses `registration_required` for a practice-only profile,
before any gate reads the chain or anything is signed or sent.

A practice-only profile is typed, never a placeholder hotkey: it carries
`practice_identity` with kind `PRACTICE_ONLY`, and no ss58 address stands in
for a registration. Anything that is not exactly that is not practice-only,
so a registered profile keeps every path it had.
"""

from __future__ import annotations

PRACTICE_ONLY = "PRACTICE_ONLY"
#: The one refusal for work that needs a registration, the same code a
#: registered-tier gate answers for a hotkey the chain does not read as
#: registered, so one code has one next step on every door.
REGISTRATION_REQUIRED = "registration_required"
#: The miner operations that sign for the chain or send to a validator. A
#: practice-only profile is refused each of them; everything that reads,
#: stops or practises is not listed here.
REGISTERED_ONLY = frozenset({"freeze_candidate", "submit", "commit"})


def is_practice_only(profile) -> bool:
    """Whether `profile` is a practice-only one: its `practice_identity` is
    typed `PRACTICE_ONLY`."""
    identity = profile.get("practice_identity") if type(profile) is dict else None
    return type(identity) is dict and identity.get("kind") == PRACTICE_ONLY


def require_registered(profile, operation: str) -> None:
    """Refuse `registration_required` (403) when a practice-only profile asks
    for an operation that needs a registration; otherwise nothing."""
    from scripts.dev.miner_launchpad.controller import Rejected

    if operation in REGISTERED_ONLY and is_practice_only(profile):
        raise Rejected(REGISTRATION_REQUIRED, 403)
