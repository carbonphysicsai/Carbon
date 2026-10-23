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
#: The miner operations that sign for the chain, send to a validator or read
#: one (a result check reads the validator's intake). A practice-only profile
#: is refused each of them; everything that reads its own campaign, stops or
#: practises is not listed here (Validator receipt: research and report only).
REGISTERED_ONLY = frozenset({"freeze_candidate", "submit", "commit", "check_result"})
#: The one Graphite submission policy a practice-only launch may take: retain
#: a selected candidate, never commit or submit it. Its selection itself is a
#: phase the ledger refuses a practice-only campaign, so the campaign stops
#: there, registration_required.
RETAIN_ONLY = "retain_only_v1"


def is_practice_only(profile) -> bool:
    """Whether `profile` is a practice-only one: its `practice_identity` is
    typed `PRACTICE_ONLY`, or - for the read operations, whose gate knows
    only whose campaigns these are - its principal is a practice principal
    (`practice:<hex>`, never an ss58)."""
    from carbon.chain.practice import is_practice_principal

    if type(profile) is not dict:
        return False
    identity = profile.get("practice_identity")
    if type(identity) is dict and identity.get("kind") == PRACTICE_ONLY:
        return True
    return is_practice_principal(profile.get("principal"))


def require_registered(profile, operation: str, request=None) -> None:
    """Refuse `registration_required` (403) when a practice-only profile asks
    for an operation that needs a registration, or launches an agent that
    would submit on its own; otherwise nothing."""
    from scripts.dev.miner_launchpad.controller import Rejected

    if not is_practice_only(profile):
        return
    if operation in REGISTERED_ONLY:
        raise Rejected(REGISTRATION_REQUIRED, 403)
    if operation == "launch" and type(request) is dict and _submits(request):
        raise Rejected(REGISTRATION_REQUIRED, 403)


def _submits(request) -> bool:
    """Whether a launch's agent would freeze or submit on its own: Carbon's
    autonomous agent always; Graphite unless it only researches (RESEARCH)
    or only retains (`retain_only_v1`)."""
    agent = request.get("agent", "autonomous")
    if agent in ("autonomous", "carbon-autonomous"):
        return True
    if agent in ("graphite", "carbon-graphite"):
        return (
            request.get("graphite_mode", "FULL") != "RESEARCH"
            and request.get("submission_policy") != RETAIN_ONLY
        )
    return False
