"""The miner edition's stages under the miner's own limits: the research
share, and the typed stop at the miner's own ceilings.

A FULL campaign researches, then builds, inside one budget: the miner's own
`provider_nanodollars` and `provider_attempts` ceilings. Its research stages
(the hunt's Reader calls and the Planner) may spend at most `research_share`
of each (OWNER-GRAPHITE-MINER-01 item 4); the build gets the rest.

`StageLedger` is the campaign ledger as a miner-edition stage sees it. Every
method is the ledger's own except `reserve`:

- with a research share, it first refuses a new reservation that would take
  the stages' spend past the share, raising `ResearchShareReached` (code
  `research_share_reached`) before anything is reserved or sent;
- for every stage, when the campaign ledger refuses a model call's
  reservation because one of the miner's own limits bound - a ceiling the
  miner set (`miner budget: <dimension>`) or the campaign's elapsed time -
  it raises `MinerCeilingReached` (code `miner_ceiling_reached`, with the
  dimension), so the session ends STOPPED at the limit, which is the normal
  end of a miner-edition run (OWNER-GRAPHITE-MINER-01 item 6: limits are
  money and time). Nothing of that call was reserved or sent. Any other
  refusal, and a refusal of a reservation that is not a model call (a
  practice trial is its tool's own to refuse), propagates unchanged.

A replayed identity - one the ledger already holds - is never refused, so a
resume replays every recorded call exactly. What the stages spent is read
from the ledger itself, by identity namespace, so it survives restarts: the
hunt's Reader calls are `graphite-reader-*` and the Planner's are
`epoch-1-plan-*` (the research loop's stage identities, compaction calls
included). In FULL the hunt has its own, smaller cap over its own namespace
(`edition.HUNT_PART_OF_SHARE`), and the Planner the whole share over both.

Both stops are the engine's typed ceiling refusal
(`research_loop.CeilingReached`) where the engine defines it, so a research
loop session one stops ends STOPPED with its code, journalled; the hunt's
Reader turns either into the hunt's own not-sent stop (`hunt.ReaderNotSent`).

The campaign ledger's own ceilings still bind every call: the share only
narrows them. A campaign holds one owner lock and its stages run one at a
time, so the share is read and the reservation made by one writer.
"""

from __future__ import annotations

import json
import math
import re

from carbon.development_session import research_loop
from carbon.development_session.research_ledger import PLAIN_REFUSALS

#: The provider dimensions a research share narrows.
SHARE_DIMENSIONS = ("provider_nanodollars", "provider_attempts")
#: The identity prefixes of the research stages' operations: the hunt's
#: Reader calls (as the Launchpad's view reads them) and the Planner stage.
READER_PREFIX = "graphite-reader-"
PLAN_PREFIX = "epoch-1-plan-"
HUNT_NAMESPACE = (READER_PREFIX,)
RESEARCH_NAMESPACE = (READER_PREFIX, PLAN_PREFIX)
RESEARCH_SHARE_REACHED = "research_share_reached"
MINER_CEILING_REACHED = "miner_ceiling_reached"
#: The campaign ledger's refusal of a reservation past a ceiling the miner
#: set (`CampaignLedger._reserve`): this prefix and the dimension.
_BUDGET_PREFIX = "miner budget: "
#: The campaign ledger's refusals of a reservation once the campaign's own
#: time is spent (`CampaignLedger._reserve`), by their exact text. Internal
#: Graphite reads the first the same way (`provider._LIMIT_MESSAGES`).
_TIME_REFUSALS = (
    "campaign elapsed-time exhausted or clock regressed",
    "provider timeout cannot fit remaining grant",
)
#: A model call's own time check, made before it reserves anything
#: (`research_agent.request_model`): the call cannot finish inside the time
#: the campaign has left.
CALL_TIME_REFUSAL = "provider timeout cannot fit remaining campaign time"
ELAPSED = "elapsed_seconds"
_DIMENSION = re.compile(r"[a-z_]{1,64}\Z")
#: The engine's typed ceiling refusal, where it defines one.
_CEILING = getattr(research_loop, "CeilingReached", None)


class _Stop(_CEILING or RuntimeError):
    """A stage's model call refused by one of the miner's own limits before
    anything of it was reserved or sent. The engine's `CeilingReached` where
    it defines one, so the research loop ends the session STOPPED with the
    code; otherwise a RuntimeError, so no stage mistakes it for a malformed
    request it may answer and continue past."""

    code = None

    def __init__(self, dimension):
        if _CEILING is not None:
            super().__init__(self.code, dimension=dimension)
        else:
            super().__init__(self.code)
        self.dimension = dimension

    def outcome(self):
        """The session outcome the engine records for it
        (`CeilingReached.outcome`); the same shape without the engine."""
        if _CEILING is not None:
            return super().outcome()
        return {
            "status": "STOPPED",
            "code": self.code,
            "reason": (
                "the ledger refused the next model call: "
                + self.code
                + "; nothing of it was reserved or sent"
            ),
            "dimension": self.dimension,
        }


class ResearchShareReached(_Stop):
    """A research stage reached the miner's research share."""

    code = RESEARCH_SHARE_REACHED

    def __init__(self, dimension, spent, want, cap):
        super().__init__(dimension)
        self.spent, self.want, self.cap = spent, want, cap

    def record(self):
        return {
            "code": RESEARCH_SHARE_REACHED,
            "dimension": self.dimension,
            "spent": self.spent,
            "requested": self.want,
            "share_cap": self.cap,
        }


class MinerCeilingReached(_Stop):
    """A stage reached one of the miner's own limits: a ceiling the miner set
    (`dimension` names it) or the campaign's time (`elapsed_seconds`)."""

    code = MINER_CEILING_REACHED

    def record(self):
        return {"code": MINER_CEILING_REACHED, "dimension": self.dimension}


#: The stops a stage's model call may end with.
STOPS = (ResearchShareReached, MinerCeilingReached)


def _dimension(text):
    return text if _DIMENSION.fullmatch(text) else None


def reserve_limit(error):
    """The miner's limit that `error`, a campaign ledger's refusal of a
    reservation, reports - a ceiling's dimension, or `elapsed_seconds` - or
    None for any other refusal. Exactly a ValueError with the ledger's own
    text, or the ledger's own typed refusal of it (`LedgerRefusal`); any
    other subclass (an operation refusal, a typed stop) is never one."""
    if type(error) not in PLAIN_REFUSALS:
        return None
    text = str(error)
    if text.startswith(_BUDGET_PREFIX):
        return _dimension(text[len(_BUDGET_PREFIX) :])
    return ELAPSED if text in _TIME_REFUSALS else None


def call_time_limit(error):
    """Whether `error` is a model call's own refusal for want of time, made
    before it reserved anything (`CALL_TIME_REFUSAL`, exactly)."""
    return type(error) is ValueError and str(error) == CALL_TIME_REFUSAL


def call_reservation(selection):
    """What one model call on `selection` reserves on the share dimensions
    (`research_agent.request_model`): one attempt, and its most possible
    cost when the selection is priced (an unpriced one reserves no money)."""
    reserved = {"provider_attempts": 1}
    if selection.reservation_nano is not None:
        reserved["provider_nanodollars"] = selection.reservation_nano
    return reserved


def share_shortfall(ceilings, fraction, per_call):
    """The first share dimension on which `fraction` of the miner's
    `ceilings` cannot admit even one model call reserving `per_call`, as
    `{dimension, share_cap, per_call}`; None when one call fits on each."""
    caps = share_caps(ceilings, fraction)
    for key in SHARE_DIMENSIONS:
        want = per_call.get(key, 0)
        if key in caps and want > caps[key]:
            return {"dimension": key, "share_cap": caps[key], "per_call": want}
    return None


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
    """The campaign ledger as a miner-edition stage sees it: a research share
    (`caps`, none outside FULL's research stages) and the typed stop at the
    miner's own limits on `reserve`."""

    def __init__(self, ledger, *, owner, caps, namespace=RESEARCH_NAMESPACE):
        if type(caps) is not dict or set(caps) - set(SHARE_DIMENSIONS):
            raise ValueError("a research share caps provider dimensions only")
        if type(namespace) is not tuple or not namespace:
            raise ValueError("a research share names its identity namespace")
        self._ledger = ledger
        self._owner = owner
        self.caps = dict(caps)
        self.namespace = namespace
        #: The share refusal that stopped a stage, once one did.
        self.reached = None
        #: The miner's limit that stopped a stage, once one did.
        self.limit = None

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
        try:
            return self._ledger.reserve(
                identity, owner=owner, phase=phase, request=request, resources=resources
            )
        except ValueError as refusal:
            # Only a model call's reservation is typed: a practice trial's is
            # its tool's own to refuse.
            dimension = (
                reserve_limit(refusal)
                if (resources or {}).get("provider_attempts")
                else None
            )
            if dimension is None:
                raise
            stopped = MinerCeilingReached(dimension)
            self.limit = stopped.record()
            raise stopped from None
