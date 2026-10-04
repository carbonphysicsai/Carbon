"""The research stages' share of the miner's own provider ceilings.

A FULL campaign researches, then builds, inside one budget: the miner's own
`provider_nanodollars` and `provider_attempts` ceilings. Its research stages
(the hunt's Reader calls and the Planner) may spend at most `research_share`
of each (OWNER-GRAPHITE-MINER-01 item 4); the build gets the rest.

`StageLedger` is the campaign ledger as the research stages see it. Every
method is the ledger's own except `reserve`, which first refuses a new
reservation that would take the stages' spend past the share, raising
`ResearchShareReached` (code `research_share_reached`) before anything is
reserved or sent. A replayed identity - one the ledger already holds - is
never refused, so a resume replays every recorded call exactly. What the
stages spent is read from the ledger itself, by identity namespace, so it
survives restarts: the hunt's Reader calls are `graphite-reader-*` and the
Planner's are `epoch-1-plan-*` (the research loop's stage identities).

The campaign ledger's own ceilings still bind every call: the share only
narrows them. A campaign holds one owner lock and its stages run one at a
time, so the share is read and the reservation made by one writer.
"""

from __future__ import annotations

import json
import math

#: The provider dimensions a research share narrows.
SHARE_DIMENSIONS = ("provider_nanodollars", "provider_attempts")
#: The identity prefixes of the research stages' operations.
READER_PREFIX = "graphite-reader-"
PLAN_PREFIX = "epoch-1-plan-"
RESEARCH_NAMESPACE = (READER_PREFIX, PLAN_PREFIX)
RESEARCH_SHARE_REACHED = "research_share_reached"


class ResearchShareReached(RuntimeError):
    """A research stage reached the miner's research share; nothing was
    reserved or sent. Not a ValueError, so no stage mistakes it for a
    malformed request it may answer and continue past."""

    code = RESEARCH_SHARE_REACHED

    def __init__(self, dimension, spent, want, cap):
        super().__init__(RESEARCH_SHARE_REACHED)
        self.dimension, self.spent, self.want, self.cap = dimension, spent, want, cap

    def record(self):
        return {
            "code": RESEARCH_SHARE_REACHED,
            "dimension": self.dimension,
            "spent": self.spent,
            "requested": self.want,
            "share_cap": self.cap,
        }


def share_caps(ceilings, fraction):
    """`{dimension: cap}` for each share dimension the miner capped with a
    whole number: the floor of `fraction` of it. A dimension the miner left
    uncapped has no share cap; its campaign ceiling (none) is the bound."""
    caps = {}
    for key in SHARE_DIMENSIONS:
        value = (ceilings or {}).get(key)
        if type(value) is int and value >= 0:
            caps[key] = math.floor(value * fraction)
    return caps


def namespace_spend(ledger, owner, namespace=RESEARCH_NAMESPACE):
    """What `owner`'s operations under `namespace` hold now, per share
    dimension: an operation's settled actual, else its reservation, as the
    ledger itself counts use."""
    spent = dict.fromkeys(SHARE_DIMENSIONS, 0)
    with ledger.db() as db:
        rows = db.execute(
            "SELECT id,reservation,actual FROM operations WHERE owner=?", (owner,)
        ).fetchall()
    for identity, reserved, actual in rows:
        if not identity.startswith(tuple(namespace)):
            continue
        vector = json.loads(actual if actual is not None else reserved)
        for key in SHARE_DIMENSIONS:
            spent[key] += vector.get(key, 0)
    return spent


class StageLedger:
    """The campaign ledger with a research share on `reserve`."""

    def __init__(self, ledger, *, owner, caps, namespace=RESEARCH_NAMESPACE):
        if type(caps) is not dict or set(caps) - set(SHARE_DIMENSIONS):
            raise ValueError("a research share caps provider dimensions only")
        if type(namespace) is not tuple or not namespace:
            raise ValueError("a research share names its identity namespace")
        self._ledger = ledger
        self._owner = owner
        self.caps = dict(caps)
        self.namespace = namespace
        #: The refusal that stopped a stage, once one did.
        self.reached = None

    def __getattr__(self, name):
        return getattr(self._ledger, name)

    @property
    def ledger(self):
        return self._ledger

    def spent(self):
        return namespace_spend(self._ledger, self._owner, self.namespace)

    def _known(self, identity, owner):
        return self._ledger.operation_state(identity, owner=owner) is not None

    def reserve(self, identity, *, owner, phase, request, resources):
        if self.caps and not self._known(identity, owner):
            spent = self.spent()
            for key, cap in sorted(self.caps.items()):
                want = (resources or {}).get(key, 0)
                if want and spent[key] + want > cap:
                    refused = ResearchShareReached(key, spent[key], want, cap)
                    self.reached = refused.record()
                    raise refused
        return self._ledger.reserve(
            identity, owner=owner, phase=phase, request=request, resources=resources
        )
