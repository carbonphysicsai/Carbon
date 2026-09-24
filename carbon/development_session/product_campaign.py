"""A campaign a miner launches from a product surface (C-MLP-02-D11).

Registration is the only admission gate, so a launch is built from a
`RegisteredMiner` - never from a grant, and never from an address plus a flag.
The runtime is what the miner's own profile declares, and the budget is theirs:
optional, closed in shape, and absent unless they set it.

The development grant does not appear here and is not importable from here. A
founder capping Carbon's spend on Carbon's accounts still uses it, through the
development CLI; a miner never meets it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .chain_onboarding import RegisteredMiner
from .research_ledger import PRODUCT, VERSION, _check_budget

#: The owner decision a product campaign runs under, recorded in its manifest.
AUTHORITY = "C-MLP-02-D11"

#: What a miner may say about their own spending. Everything is optional.
BUDGET_KEYS = frozenset({"ceilings", "elapsed_seconds", "final_reserve"})


def miner_budget(value: object) -> dict:
    """The miner's budget, validated and never supplemented.

    `None` or an empty object is no budget, which is a supported state and
    blocks nothing. A budget is refused only when it is incoherent - an unknown
    key or dimension, a negative cap - and never for being too large or too
    small: there is no bound to be outside of.
    """
    if value is None:
        return {}
    if type(value) is not dict or set(value) - BUDGET_KEYS:
        raise ValueError(
            "a budget may set only ceilings, elapsed_seconds and final_reserve"
        )
    budget = {key: item for key, item in value.items() if item is not None}
    _check_budget({"schema": VERSION, **budget})
    return budget


#: Who selects in a campaign. "none" is a person driving the whole journey.
AGENTS = ("none", "autonomous")


@dataclass(frozen=True)
class ProductLaunch:
    """Everything a product campaign is admitted with, and nothing more."""

    campaign_id: str
    principal: str
    miner: RegisteredMiner
    runtime: dict
    budget: dict
    #: Who selects: Carbon's autonomous agent, or no agent - the miner does.
    agent: str = "autonomous"

    def __post_init__(self):
        if self.agent not in AGENTS:
            raise ValueError("agent is one of: " + ", ".join(AGENTS))
        if type(self.miner) is not RegisteredMiner:
            raise TypeError("a product launch requires a RegisteredMiner")
        for value in (self.campaign_id, self.principal):
            if type(value) is not str or not 1 <= len(value) <= 128:
                raise ValueError("bounded campaign identity required")
        if type(self.runtime) is not dict or not {"implementation", "images"} <= set(
            self.runtime
        ):
            raise ValueError("a declared runtime with implementation and images")
        if miner_budget(self.budget) != self.budget:
            raise ValueError("the budget must be exactly what the miner set")

    def manifest_fields(self) -> dict:
        """What the frozen manifest records about this launch."""
        return {
            "schema": PRODUCT,
            "authority": AUTHORITY,
            "campaign_id": self.campaign_id,
            "principal": self.principal,
            "runtime": self.runtime,
            "admission": self.miner.record(),
            "agent": self.agent,
            **self.budget,
        }
