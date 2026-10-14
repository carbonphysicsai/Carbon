"""Identity/freshness evidence for a passive observer, never payout authority."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from carbon.chain.models import MetagraphSnapshot
from carbon.challenge_validator.feed_file import FEED_SCHEMA, canonical, verify_feed

CONFIG_SCHEMA = "carbon.incentive-canary.config.v2"
# No adopted observer freshness record exists. These are intentionally absent,
# shared across networks, and cannot be supplied by an untrusted feed/config.
FRESHNESS = {
    "authority": "HUMAN_INPUT",
    "max_feed_age_ms": None,
    "max_block_lag": None,
}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_HASH = re.compile(r"0x[0-9a-f]{64}")


class Unverified(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_field")
        result[key] = value
    return result


def _uint(value):
    return type(value) is int and value >= 0


def freshness_policy():
    if (
        type(FRESHNESS["authority"]) is not str
        or not FRESHNESS["authority"]
        or FRESHNESS["authority"] == "HUMAN_INPUT"
        or not _uint(FRESHNESS["max_feed_age_ms"])
        or not _uint(FRESHNESS["max_block_lag"])
    ):
        raise Unverified("feed_freshness_human_input")
    return dict(FRESHNESS)


@dataclass(frozen=True)
class WeightObservation:
    """The actual row/incentives and identities at one finalized snapshot."""

    snapshot: MetagraphSnapshot
    row: tuple
    incentives: tuple
    feed_anchor: dict | None = None
    publication: dict | None = None

    def __post_init__(self):
        if type(self.snapshot) is not MetagraphSnapshot:
            raise Unverified("chain_snapshot_unbound")
        count = len(self.snapshot.participants)
        if self.publication is not None and (
            type(self.publication) is not dict
            or set(self.publication) != {"number", "hash", "timestamp_ms"}
            or not _uint(self.publication["number"])
            or self.publication["number"] > self.snapshot.finalized_block
            or not _uint(self.publication["timestamp_ms"])
            or self.publication["timestamp_ms"] > self.snapshot.timestamp_ms
            or type(self.publication["hash"]) is not str
            or not _HASH.fullmatch(self.publication["hash"])
        ):
            raise Unverified("publication_epoch_context_malformed")
        if (
            self.publication is not None
            and self.publication["number"] == self.snapshot.finalized_block
            and (
                self.publication["hash"] != self.snapshot.block_hash
                or self.publication["timestamp_ms"] != self.snapshot.timestamp_ms
            )
        ):
            raise Unverified("publication_epoch_context_conflict")
        if (
            type(self.row) is not tuple
            or len(self.row) > count
            or any(
                type(pair) is not tuple
                or len(pair) != 2
                or not _uint(pair[0])
                or pair[0] >= count
                or not _uint(pair[1])
                or pair[1] > 65535
                for pair in self.row
            )
            or len({pair[0] for pair in self.row}) != len(self.row)
        ):
            raise Unverified("weights_malformed")
        if (
            type(self.incentives) is not tuple
            or len(self.incentives) != count
            or any(not _uint(v) or v > 65535 for v in self.incentives)
        ):
            raise Unverified("incentives_malformed")

    @property
    def hotkeys(self):
        return {p.uid: p.hotkey for p in self.snapshot.participants}


def expected_scope(config, policy, context):
    if config.get("schema") != CONFIG_SCHEMA:
        raise Unverified("observer_config_upgrade_required")
    challenge, network = config.get("challenge"), config.get("network")
    if type(challenge) is not dict or set(challenge) != {
        "id",
        "version",
        "rule_digest",
    }:
        raise Unverified("observer_challenge_unbound")
    if (
        type(challenge["id"]) is not str
        or challenge["id"] not in policy.challenges
        or type(challenge["version"]) is not str
        or not challenge["version"]
        or type(challenge["rule_digest"]) is not str
        or not _DIGEST.fullmatch(challenge["rule_digest"])
    ):
        raise Unverified("observer_challenge_human_input")
    if (
        type(network) is not dict
        or set(network) != {"name", "netuid", "genesis_hash"}
        or (network["name"], network["netuid"]) != (policy.network, policy.netuid)
        or type(network["netuid"]) is not int
        or type(network["genesis_hash"]) is not str
        or not _HASH.fullmatch(network["genesis_hash"])
    ):
        raise Unverified("observer_policy_context_mismatch")
    if (
        context.network != network["name"]
        or context.netuid != network["netuid"]
        or context.genesis_hash != network["genesis_hash"]
    ):
        raise Unverified("chain_context_mismatch")
    return {
        "challenge": dict(challenge),
        "network": dict(network),
        "validator_hotkey": config["validator_hotkey"],
        "feed_key": config["feed_key"],
        "policy_digest": policy.digest,
    }


def validate_feed(feed, scope, observation, *, now_ms, freshness):
    if type(feed) is not dict or not verify_feed(feed, scope["feed_key"]):
        raise Unverified("feed_signature_invalid")
    if feed.get("schema") != FEED_SCHEMA:
        raise Unverified("feed_schema_mismatch")
    if feed.get("challenge") != scope["challenge"]:
        raise Unverified("feed_challenge_mismatch")
    if feed.get("validator") != {
        "hotkey": scope["validator_hotkey"],
        "feed_key": scope["feed_key"],
    }:
        raise Unverified("feed_validator_mismatch")
    if feed.get("network") != scope["network"]:
        raise Unverified("feed_network_mismatch")
    if feed.get("labels") != ["DEVELOPMENT"] + (
        ["TESTNET"] if scope["network"]["name"] == "testnet" else []
    ):
        raise Unverified("feed_labels_mismatch")
    if type(observation) is not WeightObservation:
        raise Unverified("chain_snapshot_unbound")
    snap = observation.snapshot
    if {
        "name": snap.context.network,
        "netuid": snap.context.netuid,
        "genesis_hash": snap.context.genesis_hash,
    } != scope["network"] or snap.resolve(scope["validator_hotkey"]) is None:
        raise Unverified("chain_validator_context_mismatch")
    block = feed.get("as_of_block")
    if (
        type(block) is not dict
        or set(block) != {"number", "hash", "timestamp_ms"}
        or not _uint(block["number"])
        or type(block["hash"]) is not str
        or not _HASH.fullmatch(block["hash"])
        or not _uint(block["timestamp_ms"])
    ):
        raise Unverified("feed_finalized_block_missing")
    lag = snap.finalized_block - block["number"]
    if lag < 0 or lag > freshness["max_block_lag"]:
        raise Unverified("feed_block_stale_or_future")
    anchor = (
        {
            "number": snap.finalized_block,
            "hash": snap.block_hash,
            "timestamp_ms": snap.timestamp_ms,
        }
        if lag == 0
        else (observation.feed_anchor or {}).get(block["number"])
    )
    if anchor is None:
        raise Unverified("feed_finalized_anchor_unavailable")
    if anchor != block:
        raise Unverified("feed_finalized_anchor_conflict")
    try:
        generated = feed["generated_at"]
        if type(generated) is not str or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", generated
        ):
            raise ValueError
        generated_ms = int(
            datetime.datetime.fromisoformat(generated).timestamp() * 1000
        )
    except (KeyError, ValueError, OverflowError):
        raise Unverified("feed_time_malformed") from None
    if (
        not _uint(now_ms)
        or not 0 <= now_ms - generated_ms <= freshness["max_feed_age_ms"]
        or not 0 <= now_ms - snap.timestamp_ms <= freshness["max_feed_age_ms"]
    ):
        raise Unverified("feed_or_chain_time_stale_or_future")
    version = feed.get("version")
    if type(version) is not int or version < 1:
        raise Unverified("feed_version_malformed")
    source = feed.get("winner_observation")
    if (
        type(source) is not dict
        or set(source) != {"schema", "source", "state", "policy_digest"}
        or source["schema"] != "carbon.validator.winner-observation.v1"
        or source["source"] != "WINNER_LEDGER_AND_LIVE_DEPLOYMENT"
        or source["state"] not in ("CURRENT", "NO_PAYABLE_WINNER")
    ):
        raise Unverified("winner_ledger_observation_missing")
    if source["policy_digest"] != scope["policy_digest"]:
        raise Unverified("winner_policy_unbound")
    king = feed.get("king")
    common = {
        "feed_version": version,
        "block": dict(block),
        "generated_ms": generated_ms,
        "chain_block": {
            "number": snap.finalized_block,
            "hash": snap.block_hash,
            "timestamp_ms": snap.timestamp_ms,
        },
        "feed_digest": "sha256:" + hashlib.sha256(canonical(feed).encode()).hexdigest(),
    }
    if source["state"] == "NO_PAYABLE_WINNER":
        if king is not None and (
            type(king) is not dict
            or king.get("eligible") is not False
            or king.get("policy_digest") != scope["policy_digest"]
        ):
            raise Unverified("winner_state_conflict")
        return {**common, "winner": None, "registration": None}
    if type(king) is not dict:
        raise Unverified("winner_ledger_observation_missing")
    if king.get("policy_digest") != scope["policy_digest"]:
        raise Unverified("winner_policy_unbound")
    if king.get("eligible") is not True:
        raise Unverified("winner_not_payable")
    if (
        type(king.get("hotkey")) is not str
        or not king["hotkey"]
        or type(king.get("submission_id")) is not str
        or not king["submission_id"]
        or not _uint(king.get("crowned_utc_ms"))
        or king["crowned_utc_ms"] > block["timestamp_ms"]
    ):
        raise Unverified("winner_identity_unbound")
    participant = snap.resolve(king["hotkey"])
    if (
        participant is None
        or type(king.get("uid")) is not int
        or king["uid"] != participant.uid
        or king.get("coldkey") != participant.coldkey
    ):
        if (
            participant is None
            and king.get("uid") is None
            and king.get("coldkey") is None
        ):
            return {**common, "winner": None, "registration": None}
        raise Unverified("winner_registration_drift")
    return {
        **common,
        "winner": {
            key: king[key]
            for key in ("hotkey", "submission_id", "policy_digest", "crowned_utc_ms")
        },
        "registration": {
            "uid": participant.uid,
            "coldkey": participant.coldkey,
            "registered_at": participant.registered_at,
        },
    }


def record_observation(path, scope, observation):
    return record_observations(
        path, {scope["challenge"]["id"]: scope}, {scope["challenge"]["id"]: observation}
    )


def _advance(previous, current):
    if any(current[key] < previous[key] for key in ("feed_version", "generated_ms")):
        raise Unverified("feed_observation_rollback")
    for key in ("block", "chain_block"):
        if (
            current[key]["number"] < previous[key]["number"]
            or current[key]["timestamp_ms"] < previous[key]["timestamp_ms"]
        ):
            raise Unverified("feed_observation_rollback")
        if (
            current[key]["number"] == previous[key]["number"]
            and current[key]["hash"] != previous[key]["hash"]
        ):
            raise Unverified("feed_block_conflict")
    if (
        current["feed_version"] == previous["feed_version"]
        and current["winner"] != previous["winner"]
    ):
        raise Unverified("feed_version_winner_conflict")
    if (
        current["winner"] is not None
        and previous["winner"] is not None
        and current["winner"]["hotkey"] == previous["winner"]["hotkey"]
        and current["registration"] != previous["registration"]
    ):
        raise Unverified("winner_registration_changed_since_observation")


def _stamp(value):
    if (
        type(value) is not dict
        or set(value)
        != {
            "feed_version",
            "block",
            "generated_ms",
            "chain_block",
            "feed_digest",
            "winner",
            "registration",
        }
        or not _uint(value["feed_version"])
        or value["feed_version"] < 1
        or not _uint(value["generated_ms"])
        or type(value["feed_digest"]) is not str
        or not _DIGEST.fullmatch(value["feed_digest"])
    ):
        raise Unverified("observer_cursor_unavailable")
    for key in ("block", "chain_block"):
        block = value[key]
        if (
            type(block) is not dict
            or set(block) != {"number", "hash", "timestamp_ms"}
            or not _uint(block["number"])
            or not _uint(block["timestamp_ms"])
            or type(block["hash"]) is not str
            or not _HASH.fullmatch(block["hash"])
        ):
            raise Unverified("observer_cursor_unavailable")
    winner, registration = value["winner"], value["registration"]
    if winner is None:
        if registration is not None:
            raise Unverified("observer_cursor_unavailable")
    elif (
        type(winner) is not dict
        or set(winner) != {"hotkey", "submission_id", "policy_digest", "crowned_utc_ms"}
        or any(
            type(winner[k]) is not str or not winner[k]
            for k in ("hotkey", "submission_id", "policy_digest")
        )
        or not _uint(winner["crowned_utc_ms"])
        or type(registration) is not dict
        or set(registration) != {"uid", "coldkey", "registered_at"}
        or not _uint(registration["uid"])
        or not _uint(registration["registered_at"])
        or type(registration["coldkey"]) is not str
    ):
        raise Unverified("observer_cursor_unavailable")


def record_observations(path, scopes, observations):
    """Append a private scoped watermark under one OS lock; never a payment ledger."""
    import fcntl

    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise Unverified("observer_cursor_unavailable")
    identity = "sha256:" + hashlib.sha256(canonical(scopes).encode()).hexdigest()
    try:
        try:
            descriptor = os.open(
                path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            created = True
        except FileExistsError:
            descriptor = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            created = False
        with os.fdopen(descriptor, "r+b") as stream:
            if stat.S_IMODE(os.fstat(stream.fileno()).st_mode) & 0o077:
                raise Unverified("observer_cursor_not_owner_only")
            fcntl.flock(stream, fcntl.LOCK_EX)
            rows = [
                json.loads(line, object_pairs_hook=unique_object)
                for line in stream.read().splitlines()
            ]
            if not created and not rows:
                raise Unverified("observer_cursor_unavailable")
            previous = None
            for row in rows + [{"scope": identity, "observations": observations}]:
                if (
                    type(row) is not dict
                    or set(row) != {"scope", "observations"}
                    or row["scope"] != identity
                ):
                    raise Unverified("observer_cursor_scope_mismatch")
                saved = row["observations"]
                if type(saved) is not dict or set(saved) != set(scopes):
                    raise Unverified("observer_cursor_unavailable")
                for challenge, stamp in saved.items():
                    _stamp(stamp)
                    if previous is not None:
                        _advance(previous[challenge], stamp)
                previous = saved
            if rows and observations == rows[-1]["observations"]:
                return
            stream.seek(0, os.SEEK_END)
            stream.write(
                (
                    canonical({"scope": identity, "observations": observations}) + "\n"
                ).encode()
            )
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, ValueError, KeyError, TypeError):
        raise Unverified("observer_cursor_unavailable") from None
