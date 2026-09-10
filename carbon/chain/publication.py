"""Complete-target compilation; pure values here do not grant signing authority."""

from dataclasses import asdict, dataclass
from fractions import Fraction

from carbon.rewards.core import Q12
from carbon.rewards.ledger import encode
from carbon.transport.models import digest

from .models import MetagraphSnapshot, identifier, uint

RUNTIME_RELEASE = "v445"
RUNTIME_SPEC = 445
RUNTIME_COMMIT = "d3f40e44bda9019c606aeb0c907bb52ba7fe386c"
U16 = 65535


class PublicationFailure(ValueError):
    """Closed operator reason; provider messages and credentials are never retained."""


@dataclass(frozen=True)
class RuntimeCapabilities:
    snapshot_id: str
    spec_version: int
    mechanism_count: int
    maximum_mechanisms: int
    burn_mode: str
    owner_coldkey: str
    owner_hotkey: str
    owner_hotkeys: tuple[str, ...]
    min_weights: int
    max_weight: int
    version_key: int
    rate_limit: int
    last_update: int
    commit_reveal: bool
    validator_permit: bool
    sufficient_stake: bool
    pending_commits: int = 0

    def validate(self, snapshot, publisher):
        if (
            type(snapshot) is not MetagraphSnapshot
            or snapshot.context.network != "localnet"
        ):
            raise PublicationFailure("LOCALNET_SNAPSHOT_REQUIRED")
        if self.snapshot_id != snapshot.snapshot_id:
            raise PublicationFailure("CAPABILITY_SNAPSHOT_MISMATCH")
        if self.spec_version != RUNTIME_SPEC:
            raise PublicationFailure("UNSUPPORTED_RUNTIME_VERSION")
        uint(self.pending_commits)
        if self.pending_commits:
            raise PublicationFailure("EXISTING_UNREVEALED_COMMITMENTS")
        for value in (
            self.mechanism_count,
            self.maximum_mechanisms,
            self.min_weights,
            self.max_weight,
        ):
            uint(value, U16)
        for value in (self.version_key, self.rate_limit, self.last_update):
            uint(value)
        if not 1 <= self.mechanism_count <= self.maximum_mechanisms <= 2:
            raise PublicationFailure("UNSUPPORTED_MECHANISM_CONFIGURATION")
        if self.burn_mode != "Burn":
            raise PublicationFailure("VERIFIED_BURN_MODE_REQUIRED")
        if type(self.owner_hotkeys) is not tuple or len(set(self.owner_hotkeys)) != len(
            self.owner_hotkeys
        ):
            raise PublicationFailure("MALFORMED_OWNER_IDENTITY")
        for key in (self.owner_coldkey, self.owner_hotkey, *self.owner_hotkeys):
            identifier(key)
        sink = snapshot.resolve(self.owner_hotkey)
        if sink is None or self.owner_hotkey not in self.owner_hotkeys:
            raise PublicationFailure("REGISTERED_RUNTIME_OWNER_SINK_REQUIRED")
        if sink.coldkey != self.owner_coldkey:
            raise PublicationFailure("CONFLICTING_OWNER_SINK")
        member = snapshot.resolve(publisher)
        if member is None:
            raise PublicationFailure("PUBLISHER_NOT_REGISTERED")
        if any(
            type(v) is not bool
            for v in (self.commit_reveal, self.validator_permit, self.sufficient_stake)
        ):
            raise PublicationFailure("MALFORMED_PUBLISHER_CAPABILITY")
        if not self.sufficient_stake:
            raise PublicationFailure("INSUFFICIENT_PUBLISHER_STAKE")
        if not self.validator_permit and publisher != self.owner_hotkey:
            raise PublicationFailure("VALIDATOR_PERMIT_REQUIRED")
        if (
            self.last_update
            and snapshot.finalized_block - self.last_update < self.rate_limit
        ):
            raise PublicationFailure("PUBLICATION_RATE_LIMITED")
        return member, sink


@dataclass(frozen=True)
class CompiledTargets:
    intent_digest: str
    snapshot_id: str
    capabilities_digest: str
    publisher: str
    publisher_uid: int
    burn_uid: int
    q12: tuple[tuple[int, int], ...]
    integers: tuple[tuple[int, int], ...]
    tolerance_q12: int
    version_key: int
    commit_reveal: bool

    @property
    def identity(self):
        return digest(encode(asdict(self)).encode())


def _units(value):
    if type(value) is not int or not 0 <= value <= Q12:
        raise PublicationFailure("MALFORMED_COMPLETE_TARGET")
    return value


def _complete(targets):
    if type(targets) is not dict or set(targets) != {"challenges", "winners", "burn"}:
        raise PublicationFailure("MALFORMED_COMPLETE_TARGET")
    rows = targets["challenges"]
    if type(rows) is not list or len(rows) > 64:
        raise PublicationFailure("MALFORMED_CHALLENGE_TARGETS")
    seen, aggregate, allocated, earned = set(), {}, 0, 0
    for row in rows:
        if type(row) is not dict or set(row) != {
            "context_id",
            "allocated",
            "earned",
            "unearned",
            "holder",
        }:
            raise PublicationFailure("MALFORMED_CHALLENGE_TARGETS")
        context = row["context_id"]
        if type(context) is not str or len(context) != 64 or context in seen:
            raise PublicationFailure("DUPLICATE_CHALLENGE_TARGET")
        seen.add(context)
        a, e, u = (_units(row[k]) for k in ("allocated", "earned", "unearned"))
        if e + u != a:
            raise PublicationFailure("LOST_UNEARNED_ALLOCATION")
        allocated += a
        earned += e
        if e:
            holder = row["holder"]
            if type(holder) is not dict or set(holder) != {
                "hotkey",
                "coldkey",
                "registered_at",
            }:
                raise PublicationFailure("MALFORMED_HOLDER")
            identity = (holder["hotkey"], holder["coldkey"], holder["registered_at"])
            identifier(identity[0])
            identifier(identity[1])
            uint(identity[2])
            aggregate[identity] = aggregate.get(identity, 0) + e
    if allocated > Q12 or _units(targets["burn"]) != Q12 - earned:
        raise PublicationFailure("INCOMPLETE_BURN_VECTOR")
    expected = [
        [dict(zip(("hotkey", "coldkey", "registered_at"), key)), value]
        for key, value in sorted(aggregate.items())
    ]
    if targets["winners"] != expected:
        raise PublicationFailure("CONFLICTING_WINNER_AGGREGATION")
    return aggregate


def validate_integers(plan, uids, values, capabilities):
    """Check the actual final representation, including zero/dust recipient changes."""
    if len(uids) != len(values) or not uids or len(set(uids)) != len(uids):
        raise PublicationFailure("INVALID_FINAL_RECIPIENTS")
    expected = dict(plan.q12)
    if any(type(uid) is not int or uid not in expected for uid in uids):
        raise PublicationFailure("UNAUTHORIZED_FINAL_RECIPIENT")
    if any(type(value) is not int or not 1 <= value <= U16 for value in values):
        raise PublicationFailure("INVALID_FINAL_INTEGER_WEIGHT")
    actual, total = dict(zip(uids, values)), sum(values)
    error = sum(
        abs(Fraction(actual.get(uid, 0) * Q12, total) - target)
        for uid, target in expected.items()
    )
    if error > plan.tolerance_q12:
        raise PublicationFailure("TARGET_DISTORTION_EXCEEDS_QUANTIZATION")
    self_only = uids == [plan.publisher_uid]
    if not self_only and len(uids) < capabilities.min_weights:
        raise PublicationFailure("MINIMUM_WEIGHT_COUNT_INCOMPATIBLE")
    if not self_only and max(values) * U16 > capabilities.max_weight * total:
        raise PublicationFailure("MAXIMUM_WEIGHT_LIMIT_INCOMPATIBLE")


def compile_targets(resolved, snapshot, capabilities, publisher):
    """Caller must resolve NET-4A provenance; this function cannot issue authority."""
    if type(capabilities) is not RuntimeCapabilities:
        raise PublicationFailure("RUNTIME_CAPABILITIES_REQUIRED")
    member, sink = capabilities.validate(snapshot, publisher)
    body, projection = resolved["intent"], resolved["projection"]
    if body["context"] != asdict(snapshot.context):
        raise PublicationFailure("INTENT_NETWORK_MISMATCH")
    aggregate = _complete(projection["targets"])
    mapped = {}
    for (hotkey, coldkey, registered), amount in aggregate.items():
        recipient = snapshot.resolve(hotkey)
        if recipient is None or (recipient.coldkey, recipient.registered_at) != (
            coldkey,
            registered,
        ):
            raise PublicationFailure("WINNER_IDENTITY_CHANGED_REFRESH_TO_BURN")
        if (
            hotkey in capabilities.owner_hotkeys
            or coldkey == capabilities.owner_coldkey
        ):
            raise PublicationFailure("OWNER_ASSOCIATED_WINNER_WOULD_BURN")
        if recipient.uid == member.uid:
            raise PublicationFailure("PUBLISHER_SELF_WINNER_CONSENSUS_DISTORTION")
        mapped[recipient.uid] = mapped.get(recipient.uid, 0) + amount
    burn = projection["targets"]["burn"]
    if burn:
        mapped[sink.uid] = burn
    q12 = tuple(sorted(mapped.items()))
    if not q12 or sum(mapped.values()) != Q12:
        raise PublicationFailure("INCOMPLETE_BURN_VECTOR")
    top = max(mapped.values())
    integers = tuple(
        (uid, value)
        for uid, amount in q12
        if (value := round(Fraction(amount * U16, top)))
    )
    plan = CompiledTargets(
        digest(encode(body).encode()),
        snapshot.snapshot_id,
        digest(encode(asdict(capabilities)).encode()),
        publisher,
        member.uid,
        sink.uid,
        q12,
        integers,
        (len(q12) * Q12 + U16 - 1) // U16,
        capabilities.version_key,
        capabilities.commit_reveal,
    )
    validate_integers(
        plan, [u for u, _ in integers], [v for _, v in integers], capabilities
    )
    return plan
