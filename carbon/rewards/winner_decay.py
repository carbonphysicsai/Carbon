"""Testnet winner-decay weights (VALIDATOR-14; OWNER-TESTNET-WEIGHTS-01).

The owner's rule, as pure integer arithmetic in Q12 units of one epoch's
emissions:
- **Shares.** Each of the policy's N Challenges gets `Q12 // N`.
- **The winner.** A Challenge's current winner receives all of its share for
  24 hours from its promotion (finalized-chain time). After that the share is
  halved every 24 hours: 1/2 on the second day, 1/4 on the third, and so on.
- **Clock reset.** Being beaten under the Challenge's own promotion rule
  starts a new winner's 24 hours. Deciding who is eligible, including the
  same-miner factor, is the eligibility layer's job, not this module's.
- **Burn.** Anything not paid in an epoch burns to UID 0: the decayed
  remainder, Challenges with no eligible winner, and integer remainders.
  Nothing carries over.

The policy is a registered, digest-pinned document in `weight_policies/`.
Changing it, N included, is a new version, never a code edit. Testnet only:
the policy names its network and netuid, and nothing here signs, publishes or
settles.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .core import DAY_MS, Q12, RewardFailure, tick

POLICY_DIR = Path(__file__).resolve().parent / "weight_policies"
POLICY_SCHEMA = "carbon.rewards.testnet-winner-policy.v1"
REGISTRY_SCHEMA = "carbon.rewards.weight-policy-registry.v1"
AUTHORITY = "OWNER-TESTNET-WEIGHTS-01"
#: The owner records that may author a registered policy, per network.
#: OWNER-TESTNET-WEIGHTS-01 covers testnet 567 only. OWNER-WEIGHTS-AUTHORITY-01
#: (no authorization-only weight blocks, testnet or mainnet; its hold lifted
#: by OWNER-WEIGHTS-HOLD-LIFT-01) covers both, so the same rule runs on
#: mainnet. A network outside this table has no policy.
MAINNET_AUTHORITY = "OWNER-WEIGHTS-AUTHORITY-01"
NETWORK_AUTHORITIES = {
    "testnet": frozenset({AUTHORITY, MAINNET_AUTHORITY}),
    "finney": frozenset({MAINNET_AUTHORITY}),
}
TESTNET_NETUID = 567


def network_authorized(network, netuid, authority):
    """Whether `authority` may name `network`/`netuid`: a network in
    `NETWORK_AUTHORITIES`, one of its records, a real netuid, and testnet
    567 only under OWNER-TESTNET-WEIGHTS-01."""
    return (
        type(network) is str
        and network in NETWORK_AUTHORITIES
        and type(authority) is str
        and authority in NETWORK_AUTHORITIES[network]
        and type(netuid) is int
        and 0 < netuid <= 65535
        and (authority != AUTHORITY or netuid == TESTNET_NETUID)
    )


_KEYS = frozenset(
    {
        "schema",
        "version",
        "authority",
        "network",
        "netuid",
        "challenges",
        "decay",
        "self_improvement_factor",
        "burn_uid",
        "cadence_blocks",
        "baselines",
        "membership_note",
    }
)
_DECAY = {"full_ms": DAY_MS, "halving_ms": DAY_MS}
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class WinnerPolicy:
    version: str
    digest: str
    network: str
    netuid: int
    challenges: tuple
    self_improvement_factor: str | None
    burn_uid: int
    cadence_blocks: int
    #: Each Challenge's registered public baseline (a construction digest), or
    #: None while testnet keeps the validator's first-incumbent rule
    #: (OWNER-TESTNET-WEIGHTS-01 §2b).
    baselines: tuple = ()
    #: The owner record the policy names (`NETWORK_AUTHORITIES`).
    authority: str = AUTHORITY

    def baseline(self, challenge):
        return dict(self.baselines)[challenge]

    @property
    def share(self):
        """One Challenge's share of an epoch, in Q12 units."""
        return Q12 // len(self.challenges)


def load_policy(version=None, directory=None):
    """The registered policy (`version`, or the registry's current one).
    Refused when the registry or document is altered or malformed."""
    directory = POLICY_DIR if directory is None else Path(directory)
    try:
        registry = json.loads((directory / "registry.json").read_text())
        version = registry["current"] if version is None else version
        pinned = registry["versions"][version]
        document = json.loads((directory / f"{version}.json").read_text())
    except (OSError, ValueError, KeyError, TypeError):
        raise RewardFailure("WEIGHT_POLICY_UNREADABLE") from None
    if registry.get("schema") != REGISTRY_SCHEMA:
        raise RewardFailure("WEIGHT_POLICY_REGISTRY_MALFORMED")
    found = "sha256:" + hashlib.sha256(_canonical(document)).hexdigest()
    if found != pinned:
        raise RewardFailure("WEIGHT_POLICY_ALTERED")
    challenges = document.get("challenges") if type(document) is dict else None
    factor = document.get("self_improvement_factor") if challenges else None
    baselines = document.get("baselines") if challenges else None
    if (
        type(document) is not dict
        or set(document) != _KEYS
        or document["schema"] != POLICY_SCHEMA
        or document["version"] != version
        or not network_authorized(
            document["network"], document["netuid"], document["authority"]
        )
        or type(challenges) is not list
        or not challenges
        or len(set(challenges)) != len(challenges)
        or not all(type(c) is str and c for c in challenges)
        or document["decay"] != _DECAY
        or not (factor is None or type(factor) is str)
        or document["burn_uid"] != 0
        or document["cadence_blocks"] != 360
        or type(baselines) is not dict
        or set(baselines) != set(challenges)
        or not all(
            b is None or (type(b) is str and DIGEST.fullmatch(b))
            for b in baselines.values()
        )
    ):
        raise RewardFailure("WEIGHT_POLICY_MALFORMED")
    return WinnerPolicy(
        version=version,
        digest=pinned,
        network=document["network"],
        netuid=document["netuid"],
        challenges=tuple(challenges),
        self_improvement_factor=factor,
        burn_uid=document["burn_uid"],
        cadence_blocks=document["cadence_blocks"],
        baselines=tuple(sorted(baselines.items())),
        authority=document["authority"],
    )


def winner_fraction(clock_ms, now_ms):
    """The winner's fraction of its Challenge's share, in Q12 units: all of it
    for the first 24 hours from `clock_ms` (its promotion), then halved at
    each further 24 hours."""
    tick(clock_ms)
    tick(now_ms)
    if now_ms < clock_ms:
        raise RewardFailure("CLOCK_BEFORE_PROMOTION")
    days = (now_ms - clock_ms) // DAY_MS
    return Q12 >> days if days < 64 else 0


@dataclass(frozen=True)
class Winner:
    """A Challenge's weight-eligible winner: its hotkey and the finalized-chain
    time its 24 hours started (the last eligible promotion)."""

    hotkey: str
    clock_ms: int

    def __post_init__(self):
        if type(self.hotkey) is not str or not 1 <= len(self.hotkey) <= 128:
            raise RewardFailure("INVALID_HOLDER")
        tick(self.clock_ms)


def epoch_targets(policy, winners, now_ms):
    """One epoch's targets, `{"winners": {hotkey: q12}, "burn": q12}`, summing
    exactly to Q12. `winners` maps a Challenge id to its `Winner`, or omits
    it when the Challenge has none. A Challenge outside the policy is
    refused."""
    if type(policy) is not WinnerPolicy:
        raise TypeError("a WinnerPolicy is required")
    unknown = set(winners) - set(policy.challenges)
    if unknown:
        raise RewardFailure("CHALLENGE_NOT_IN_POLICY")
    paid = {}
    for challenge in policy.challenges:
        winner = winners.get(challenge)
        if winner is None:
            continue
        if type(winner) is not Winner:
            raise TypeError("a Winner is required")
        amount = policy.share * winner_fraction(winner.clock_ms, now_ms) // Q12
        if amount:
            paid[winner.hotkey] = paid.get(winner.hotkey, 0) + amount
    burn = Q12 - sum(paid.values())
    if burn < 0:
        raise RewardFailure("OVER_ALLOCATED")
    return {"winners": dict(sorted(paid.items())), "burn": burn}
