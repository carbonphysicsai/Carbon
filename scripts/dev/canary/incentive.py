"""INCENTIVE-CANARY-01 slice 1: is the best model getting paid?

    python -m scripts.dev.canary.incentive check --config <file>

A passive check, run on the miner side over **public surfaces only**:
- valV2's on-chain weight row (`SubtensorModule.Weights`), at a finalized
  metagraph snapshot;
- the validator's signed score feed: its live `king`, bound to the publisher's
  WinnerLedger policy and current finalized observation, never released standing;
- the registered weight policy (`rewards.winner_decay`, `testnet-winner-v1`);
- the registered canary list (OWNER-CANARY-LIST-01).

What it verifies each epoch (`verify_epoch`):
1. Weight goes only to the burn UID and to the incumbent the feed names.
   Weight to anyone else is a BLOCKER (`weight_to_non_incumbent`).
2. No canary-listed hotkey has weight. Otherwise it is a BLOCKER
   (`canary_weighted`).
3. The incumbent's weight is its Challenge's 1/N share, either in full or
   halved a whole number of times (the decay). Any other fraction is a
   BLOCKER (`share_not_a_decay_level`).
4. With the incentive roles (slice 2, `roles.ROLES`): the degraded role
   holding the incumbency while the strong role's released accuracy is
   better, or the two ordered the wrong way in the feed's standing, is
   ATTENTION (`role_order_inverted`). Recipe quality is a hypothesis, so
   this is evidence about the recipes, never a payment blocker.
5. An incumbent with no weight is ATTENTION (`incumbent_unpaid`), not a
   blocker. Its promotion may be legitimately ineligible (a same-miner
   tweak, an overdue pool), and the winner ledger saying so is private.

A surface that cannot be read or bound is UNVERIFIED, never a pass. The same
guards apply to any registered policy network; a testnet policy never authorizes
mainnet. Unregistered freshness values remain HUMAN_INPUT/UNVERIFIED.
It signs nothing and sets no weight. DEVELOPMENT evidence; not a security
or economic qualification of the weight path.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import math
import sys
import time
from pathlib import Path

from scripts.dev.canary import incentive_observation as observation
from scripts.dev.canary.incentive_observation import Unverified

SCHEMA = observation.CONFIG_SCHEMA
PASS, ATTENTION, UNVERIFIED, BLOCKER = "PASS", "ATTENTION", "UNVERIFIED", "BLOCKER"
#: The u16 weight row's resolution: a share may round by a few units.
U16 = 65535
TOLERANCE_UNITS = 4
BATTERY = "battery-fastcharge-ageing-development-v1"


def verify_epoch(
    row,
    hotkeys,
    incumbents,
    n_challenges,
    canaries,
    burn_uid=0,
    *,
    expected_targets=None,
):
    """`row`: `[[uid, u16 weight], ...]` one validator set. `hotkeys`:
    `{uid: hotkey}`. `incumbents`: `{challenge: hotkey or None}` for the
    Challenges this validator serves. Returns `{"state", "findings"}`."""
    weights = {uid: value for uid, value in row if value}
    total = sum(weights.values())
    findings = []
    if total == 0:
        return {
            "state": UNVERIFIED,
            "findings": [{"level": UNVERIFIED, "code": "no_weights_set"}],
        }
    paid = {hotkey for hotkey in incumbents.values() if hotkey is not None}
    # The feed names the incumbent only once its windows are released; until
    # then the publisher may rightly pay it, and the check cannot tell.
    unreleased = expected_targets is None and any(
        hotkey is None for hotkey in incumbents.values()
    )
    for uid, value in sorted(weights.items()):
        if uid == burn_uid:
            continue
        hotkey = hotkeys.get(uid)
        if hotkey in canaries:
            findings.append({"level": BLOCKER, "code": "canary_weighted", "uid": uid})
        elif hotkey not in paid and unreleased:
            findings.append(
                {
                    "level": UNVERIFIED,
                    "code": "weight_to_unreleased_incumbent",
                    "uid": uid,
                }
            )
        elif hotkey not in paid:
            findings.append(
                {"level": BLOCKER, "code": "weight_to_non_incumbent", "uid": uid}
            )
    by_hotkey = {hotkey: uid for uid, hotkey in hotkeys.items()}
    if expected_targets is None and any(
        list(incumbents.values()).count(h) > 1 for h in paid
    ):
        findings.append({"level": UNVERIFIED, "code": "aggregate_targets_unbound"})
        levels = {f["level"] for f in findings}
        return {
            "state": next(
                (s for s in (BLOCKER, ATTENTION, UNVERIFIED) if s in levels), PASS
            ),
            "findings": findings,
        }
    if expected_targets is not None:
        from carbon.rewards.winner_decay import Q12

        targets = (
            expected_targets.get("winners") if type(expected_targets) is dict else None
        )
        burn = expected_targets.get("burn") if type(expected_targets) is dict else None
        if (
            type(targets) is not dict
            or set(expected_targets) != {"winners", "burn"}
            or type(burn) is not int
            or not 0 <= burn <= Q12
            or any(
                type(h) is not str or type(v) is not int or not 0 <= v <= Q12
                for h, v in targets.items()
            )
            or sum(targets.values()) + burn != Q12
            or not set(targets) <= paid
        ):
            return {
                "state": UNVERIFIED,
                "findings": [
                    {"level": UNVERIFIED, "code": "aggregate_targets_unbound"}
                ],
            }
        # epoch_targets aggregates hotkeys before UID mapping and preserves the
        # exact burn/remainder. Never compare each Challenge to the shared UID.
        wanted = {burn_uid: burn}
        for hotkey, amount in targets.items():
            if hotkey not in by_hotkey:
                return {
                    "state": UNVERIFIED,
                    "findings": [
                        {"level": UNVERIFIED, "code": "aggregate_holder_not_registered"}
                    ],
                }
            wanted[by_hotkey[hotkey]] = amount
        for uid in sorted(set(wanted) | set(weights)):
            fraction = weights.get(uid, 0) / total
            expected = wanted.get(uid, 0) / Q12
            if abs(fraction - expected) > TOLERANCE_UNITS / U16:
                findings.append(
                    {
                        "level": BLOCKER,
                        "code": "observed_row_not_current_target",
                        "uid": uid,
                    }
                )
        if not findings:
            findings.append(
                {"level": PASS, "code": "registered_aggregate_targets_match"}
            )
        levels = {f["level"] for f in findings}
        return {
            "state": next(
                (s for s in (BLOCKER, ATTENTION, UNVERIFIED) if s in levels), PASS
            ),
            "findings": findings,
        }
    share = 1 / n_challenges
    tolerance = TOLERANCE_UNITS / U16
    for challenge, hotkey in sorted(incumbents.items()):
        if hotkey is None:
            findings.append(
                {
                    "level": UNVERIFIED,
                    "code": "incumbent_not_released",
                    "challenge": challenge,
                }
            )
            continue
        uid = by_hotkey.get(hotkey)
        if uid is None:
            # Not registered: its share burns, as the publisher pays nobody.
            findings.append(
                {
                    "level": PASS,
                    "code": "incumbent_not_registered",
                    "challenge": challenge,
                }
            )
            continue
        fraction = weights.get(uid, 0) / total
        if fraction == 0:
            findings.append(
                {"level": ATTENTION, "code": "incumbent_unpaid", "challenge": challenge}
            )
            continue
        halvings = round(-math.log2(fraction / share))
        if halvings < 0 or abs(fraction - share * 2.0**-halvings) > tolerance:
            findings.append(
                {
                    "level": BLOCKER,
                    "code": "share_not_a_decay_level",
                    "challenge": challenge,
                    "fraction": round(fraction, 6),
                }
            )
        else:
            findings.append(
                {
                    "level": PASS,
                    "code": "incumbent_paid",
                    "challenge": challenge,
                    "halvings": halvings,
                }
            )
    levels = {f["level"] for f in findings}
    for state in (BLOCKER, ATTENTION, UNVERIFIED):
        if state in levels:
            return {"state": state, "findings": findings}
    return {"state": PASS, "findings": findings}


# --- the public surfaces --------------------------------------------------------


def _sybil_scenarios():
    from scripts.dev.canary.roles import SCENARIOS

    return SCENARIOS


def config_document(config):
    keys = {
        "schema",
        "validator_hotkey",
        "intake_url",
        "feed_key",
        "policy",
        "challenge",
        "network",
        "chain_endpoint",
        "cursor",
    }
    if (
        type(config) is not dict
        or not keys <= set(config) <= keys | {"roles", "sybil", "additional_challenges"}
        or config["schema"] != SCHEMA
        or type(config.get("roles", False)) is not bool
        or config.get("sybil", "sybil-near") not in _sybil_scenarios()
    ):
        raise ValueError("incentive_config_malformed")
    return config


def load_config(path):
    return config_document(
        json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=observation.unique_object,
        )
    )


def verify_roles(leaderboard, roles):
    """Findings on the incentive roles from the feed's leaderboard:
    `role_order_inverted` (ATTENTION) when the degraded role ranks above the
    strong role, or holds the incumbency while strong is ranked above it."""
    by_role = {entry["role"]: hotkey for hotkey, entry in roles.items()}
    strong, degraded = by_role.get("strong"), by_role.get("degraded")
    ranks = {
        e["hotkey"]: e.get("rank", i + 1)
        for i, e in enumerate(leaderboard.get("standing") or [])
    }
    incumbent = (leaderboard.get("incumbent") or {}).get("hotkey")
    findings = []
    if strong in ranks and degraded in ranks:
        if ranks[degraded] < ranks[strong] or incumbent == degraded:
            findings.append({"level": ATTENTION, "code": "role_order_inverted"})
        else:
            findings.append({"level": PASS, "code": "role_order_held"})
    else:
        findings.append({"level": UNVERIFIED, "code": "roles_not_both_released"})
    return findings


def verify_sybil(row, hotkeys, honest, sybil):
    """`(findings, shares)` for one sybil pair: `sybil_split` (BLOCKER) when
    both hotkeys hold weight in one epoch (one incumbent per Challenge), else
    `sybil_not_split`. `shares`: each one's fraction of the row."""
    weights = {hotkeys.get(uid): value for uid, value in row if value}
    total = sum(weights.values()) or 1
    shares = {
        "honest": weights.get(honest, 0) / total,
        "sybil": weights.get(sybil, 0) / total,
    }
    if shares["honest"] and shares["sybil"]:
        return [{"level": BLOCKER, "code": "sybil_split"}], shares
    return [{"level": PASS, "code": "sybil_not_split"}], shares


def summarize(lines, challenge_share):
    """The observed half of a #974 `sybil` prediction row, from `check
    --observe` lines (one per epoch, oldest first)."""
    epochs = [line for line in lines if "shares" in line]
    if not epochs:
        return {"strategy": "sybil", "sybil_hotkeys": 2, "observed": None}
    holders = [
        "sybil" if e["shares"]["sybil"] else "honest" if e["shares"]["honest"] else None
        for e in epochs
    ]
    takeovers = sum(
        1 for a, b in itertools.pairwise(holders) if a == "honest" and b == "sybil"
    )
    return {
        "strategy": "sybil",
        "sybil_hotkeys": 2,
        "observed": {
            "epochs": len(epochs),
            "attacker_weight_fraction": sum(e["shares"]["sybil"] for e in epochs)
            / (challenge_share * len(epochs)),
            "honest_weight_fraction": sum(e["shares"]["honest"] for e in epochs)
            / (challenge_share * len(epochs)),
            "split_epochs": sum(
                1 for e in epochs if e["shares"]["sybil"] and e["shares"]["honest"]
            ),
            "sybil_takeovers": takeovers,
        },
    }


def verify_incentive(row, incentives, burn_uid=0):
    """Whether the weight became payment: the chain's per-UID incentive (u16)
    after Yuma. A weighted miner with no incentive, or a miner paid that this
    validator does not weight, is ATTENTION: consensus lags one epoch step
    after a change, and another active validator can outweigh this one."""
    weighted = {uid for uid, value in row if value and uid != burn_uid}
    findings = []
    for uid in sorted(weighted):
        value = incentives[uid] if uid < len(incentives) else 0
        if value:
            findings.append(
                {
                    "level": PASS,
                    "code": "weighted_uid_paid",
                    "uid": uid,
                    "incentive": round(value / U16, 6),
                }
            )
        else:
            findings.append(
                {"level": ATTENTION, "code": "weighted_uid_no_incentive", "uid": uid}
            )
    for uid, value in enumerate(incentives):
        if value and uid != burn_uid and uid not in weighted:
            findings.append(
                {
                    "level": ATTENTION,
                    "code": "incentive_not_from_this_validator",
                    "uid": uid,
                }
            )
    return findings


def read_feed(intake_url, feed_key, challenge=BATTERY, *, opener=None):
    """Authenticate the full public feed; observation context is checked later."""
    import urllib.request

    from carbon.challenge_validator.feed_file import FEED_SCHEMA, verify_feed

    url = intake_url.rstrip("/") + "/carbon/v1/feed/" + challenge
    try:
        with (opener or urllib.request.urlopen)(url, timeout=10) as response:
            feed = json.loads(
                response.read(), object_pairs_hook=observation.unique_object
            )
    except Exception:  # noqa: BLE001 - any failed read is unverified, never a pass
        raise Unverified("feed_unavailable") from None
    if type(feed) is not dict or not verify_feed(feed, feed_key):
        raise Unverified("feed_signature_invalid")
    if feed.get("schema") != FEED_SCHEMA:
        raise Unverified("feed_schema_mismatch")
    if (
        type(feed.get("challenge")) is not dict
        or feed["challenge"].get("id") != challenge
    ):
        raise Unverified("feed_challenge_mismatch")
    return feed


def read_leaderboard(intake_url, feed_key, challenge=BATTERY, *, opener=None):
    """Released display history, never the paying winner source."""
    feed = read_feed(intake_url, feed_key, challenge, opener=opener)
    leaderboard = feed.get("leaderboard")
    return leaderboard if type(leaderboard) is dict else {}


def read_incumbent(intake_url, feed_key, challenge=BATTERY, *, opener=None):
    """The signed live king's label; full observation bindings are still needed.

    No released-standing fallback. This scalar alone cannot certify payment.
    """
    feed = read_feed(intake_url, feed_key, challenge, opener=opener)
    king = feed.get("king")
    return king.get("hotkey") if type(king) is dict else None


async def read_weights(context, validator_hotkey, *, feed_block=None):
    """`(row, {uid: hotkey}, incentives)` of `validator_hotkey`'s weights and
    the subnet's per-UID incentive (u16), read at one finalized snapshot, from
    the endpoint whose genesis is the context's."""
    import bittensor as bt

    from carbon.chain.models import hash256
    from carbon.chain.sdk import BittensorReader

    snapshot = await BittensorReader().capture(context)
    if (
        type(snapshot) is not observation.MetagraphSnapshot
        or snapshot.context != context
    ):
        raise Unverified("chain_snapshot_unbound")
    hotkeys = {p.uid: p.hotkey for p in snapshot.participants}
    uids = [uid for uid, hotkey in hotkeys.items() if hotkey == validator_hotkey]
    if len(uids) != 1:
        raise Unverified("validator_not_registered")
    sub = bt.RpcSubstrate(
        context.endpoint,
        fallback_endpoints=[],
        archive_endpoints=[],
        retry_forever=False,
    )
    client = bt.Client(context.endpoint, substrate=sub)
    try:
        await sub.connect()
        if hash256(await sub.block_hash(0)) != context.genesis_hash:
            raise Unverified("endpoint_genesis_mismatch")
        block_hash = await sub.block_hash(snapshot.finalized_block)
        if hash256(block_hash) != snapshot.block_hash:
            raise Unverified("conflicting_block")
        row = await sub.query(
            "SubtensorModule",
            "Weights",
            [context.netuid, uids[0]],
            block_hash=block_hash,
        )
        view = await client.at(snapshot.finalized_block)
        graph = await view.read("metagraph", netuid=context.netuid)
        publication = None
        updates = await sub.query(
            "SubtensorModule", "LastUpdate", [context.netuid], block_hash=block_hash
        )
        if type(updates) is list and uids[0] < len(updates):
            number = updates[uids[0]]
            if type(number) is int and 0 < number <= snapshot.finalized_block:
                published_hash = await sub.block_hash(number)
                published_time = await sub.query(
                    "Timestamp", "Now", block_hash=published_hash
                )
                publication = {
                    "number": number,
                    "hash": hash256(published_hash),
                    "timestamp_ms": int(published_time),
                }
        anchor = {}
        blocks = feed_block if type(feed_block) is list else [feed_block]
        for feed_at in blocks:
            if type(feed_at) is not dict or type(feed_at.get("number")) is not int:
                raise Unverified("feed_finalized_block_missing")
            number = feed_at["number"]
            lag = snapshot.finalized_block - number
            if not 0 <= lag <= observation.freshness_policy()["max_block_lag"]:
                raise Unverified("feed_block_stale_or_future")
            if lag:
                anchor_hash = await sub.block_hash(number)
                stamp = await sub.query("Timestamp", "Now", block_hash=anchor_hash)
                anchor[number] = {
                    "number": number,
                    "hash": hash256(anchor_hash),
                    "timestamp_ms": int(stamp),
                }
        if (
            hash256(await sub.block_hash(snapshot.finalized_block))
            != snapshot.block_hash
        ):
            raise Unverified("conflicting_finalized_snapshot")
    finally:
        await client.close()
    if type(row) is not list:
        raise Unverified("weights_malformed")
    if any(
        type(pair) not in (tuple, list)
        or len(pair) != 2
        or any(type(v) is not int for v in pair)
        for pair in row
    ):
        raise Unverified("weights_malformed")
    incentives = graph.get("incentives") if type(graph) is dict else None
    if type(incentives) is not list or any(type(v) is not int for v in incentives):
        raise Unverified("incentives_malformed")
    return observation.WeightObservation(
        snapshot,
        tuple((u, v) for u, v in row),
        tuple(incentives),
        anchor,
        publication,
    )


def check(
    config,
    *,
    weights_reader=None,
    incumbent_reader=None,
    leaderboard_reader=None,
    feed_reader=None,
    context=None,
    clock=time.time,
):
    """One check of the current epoch. Returns the result line. With
    `"roles": true` in the config, the incentive roles' ordering too; with
    `"sybil": "<scenario>"`, the sybil pair's split and shares."""
    from carbon.challenge_validator.canary import CANARY_HOTKEYS
    from carbon.rewards.winner_decay import load_policy

    try:
        if config.get("schema") != SCHEMA:
            raise Unverified("observer_config_upgrade_required")
        config_document(config)
        if incumbent_reader is not None or leaderboard_reader is not None:
            raise Unverified("legacy_reader_unbound")
        try:
            policy = load_policy(config["policy"])
        except ValueError:
            raise Unverified("weight_policy_unavailable") from None
        if context is None:
            from carbon.chain.models import ChainContext

            network = config.get("network")
            if type(network) is not dict or not config.get("chain_endpoint"):
                raise Unverified("observer_chain_context_human_input")
            context = ChainContext(
                network["name"],
                config["chain_endpoint"],
                "bittensor",
                network["genesis_hash"],
                network["netuid"],
            )
        additional = config.get("additional_challenges", [])
        if type(additional) is not list or len(additional) >= len(policy.challenges):
            raise Unverified("observer_challenge_roster_malformed")
        scopes, feeds = {}, {}
        for challenge in [config["challenge"], *additional]:
            scope = observation.expected_scope(
                {**config, "challenge": challenge}, policy, context
            )
            identity = scope["challenge"]["id"]
            if identity in scopes:
                raise Unverified("observer_challenge_roster_malformed")
            scopes[identity] = scope
        freshness = observation.freshness_policy()
        for identity in scopes:
            feeds[identity] = (feed_reader or read_feed)(
                config["intake_url"], config["feed_key"], identity
            )
        read = asyncio.run(
            (weights_reader or read_weights)(
                context,
                config["validator_hotkey"],
                feed_block=[feed.get("as_of_block") for feed in feeds.values()],
            )
        )
        evidence = {
            identity: observation.validate_feed(
                feed,
                scopes[identity],
                read,
                now_ms=int(clock() * 1000),
                freshness=freshness,
            )
            for identity, feed in feeds.items()
        }
        if type(config.get("cursor")) is not str or not config["cursor"]:
            raise Unverified("observer_cursor_unavailable")
        observation.record_observations(config["cursor"], scopes, evidence)
        row, hotkeys, incentives = read.row, read.hotkeys, read.incentives
        primary = config["challenge"]["id"]
        incumbent = (evidence[primary]["winner"] or {}).get("hotkey")
        leaderboard = feeds[primary].get("leaderboard") if config.get("roles") else None
    except Unverified as failed:
        return {"state": UNVERIFIED, "findings": [{"code": failed.code}]}
    except Exception as failed:  # noqa: BLE001 - infrastructure is unverified
        return {
            "state": UNVERIFIED,
            "findings": [{"code": "read_failed", "type": type(failed).__name__}],
        }
    missing = sorted(set(policy.challenges) - set(evidence))
    if missing:
        result = {
            "state": UNVERIFIED,
            "findings": [
                {
                    "level": UNVERIFIED,
                    "code": "challenge_observations_incomplete",
                    "missing": missing,
                }
            ],
        }
        # Canary exclusion is independently known even when a winner source is
        # missing; do not make any other allocation inference from that gap.
        result["findings"] += [
            f
            for f in verify_epoch(
                row,
                hotkeys,
                {c: None for c in policy.challenges},
                len(policy.challenges),
                frozenset(CANARY_HOTKEYS),
                policy.burn_uid,
            )["findings"]
            if f["code"] == "canary_weighted"
        ]
    else:
        from carbon.rewards.winner_decay import Winner, epoch_targets

        winners = {
            c: Winner(v["winner"]["hotkey"], v["winner"]["crowned_utc_ms"])
            for c, v in evidence.items()
            if v["winner"] is not None
        }
        expected = epoch_targets(policy, winners, read.snapshot.timestamp_ms)
        result = verify_epoch(
            row,
            hotkeys,
            {c: (v["winner"] or {}).get("hotkey") for c, v in evidence.items()},
            len(policy.challenges),
            frozenset(CANARY_HOTKEYS),
            policy.burn_uid,
            expected_targets=expected,
        )
        # Pure complete-vector fixtures compare mathematics. A live stored row
        # also needs its own independently read finalized publication time.
        if read.publication is None:
            result = {
                "state": UNVERIFIED,
                "findings": [
                    f for f in result["findings"] if f["code"] == "canary_weighted"
                ]
                + [
                    {
                        "level": UNVERIFIED,
                        "code": "publication_epoch_context_unavailable",
                    }
                ],
            }
        elif any(
            v["winner"] is not None
            and v["winner"]["crowned_utc_ms"] > read.publication["timestamp_ms"]
            for v in evidence.values()
        ):
            result = {
                "state": UNVERIFIED,
                "findings": [
                    f for f in result["findings"] if f["code"] == "canary_weighted"
                ]
                + [{"level": UNVERIFIED, "code": "winner_clock_after_publication"}],
            }
        else:
            for finding in result["findings"]:
                if finding["code"] == "observed_row_not_current_target":
                    finding["level"] = ATTENTION
                elif finding["code"] == "weight_to_non_incumbent" and any(
                    v["block"]["timestamp_ms"] > read.publication["timestamp_ms"]
                    for v in evidence.values()
                ):
                    finding["level"] = UNVERIFIED
                    finding["code"] = "weight_row_predates_winner_observation"
    if leaderboard is not None:
        from scripts.dev.canary.roles import ROLES

        # Standing remains released display evidence; current holder comes only
        # from the authenticated king, never its lagged incumbent slot.
        result["findings"] += verify_roles(
            {**leaderboard, "incumbent": {"hotkey": incumbent}}, ROLES
        )
    if config.get("sybil"):
        scenario = _sybil_scenarios()[config["sybil"]]
        foreign = {
            v["winner"]["hotkey"]
            for c, v in evidence.items()
            if c != primary and v["winner"] is not None
        }
        if missing or foreign & {scenario["of"], scenario["hotkey"]}:
            result["findings"].append(
                {"level": UNVERIFIED, "code": "sybil_row_not_challenge_specific"}
            )
        else:
            findings, shares = verify_sybil(
                row, hotkeys, scenario["of"], scenario["hotkey"]
            )
            result["findings"] += findings
            result["shares"] = shares
            result["challenge_share"] = 1 / len(policy.challenges)
    if incentives is not None:
        result["findings"] += verify_incentive(
            row, incentives, burn_uid=policy.burn_uid
        )
    if leaderboard is not None or config.get("sybil") or incentives is not None:
        levels = {f.get("level", UNVERIFIED) for f in result["findings"]}
        result["state"] = next(
            (s for s in (BLOCKER, UNVERIFIED, ATTENTION) if s in levels), PASS
        )
    result["observation"] = {
        "challenges": evidence,
        "scopes": scopes,
        "freshness_authority": freshness["authority"],
        "source": (
            "INJECTED_TEST_READERS"
            if weights_reader is not None or feed_reader is not None
            else "FINALIZED_PUBLIC_OBSERVATION"
        ),
        "coverage": (
            "PARTIAL_UNVERIFIED"
            if missing
            else "REGISTERED_AGGREGATE_TARGETS_ONLY_NOT_PUBLICATION_ACCEPTANCE"
        ),
        "payment_claim": "INCENTIVE_ONLY_NOT_ALPHA_RECEIPT_OR_SETTLEMENT",
        "publication": (
            None
            if read.publication is None
            else {
                **read.publication,
                "epoch": read.publication["number"] // policy.cadence_blocks,
            }
        ),
    }
    return result


EXIT = {PASS: 0, ATTENTION: 0, UNVERIFIED: 1, BLOCKER: 3}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="scripts.dev.canary.incentive")
    sub = parser.add_subparsers(dest="command", required=True)
    checked = sub.add_parser("check")
    checked.add_argument("--config", required=True)
    checked.add_argument(
        "--observe", type=Path, help="append the result line to this JSONL file"
    )
    sub.add_parser("summarize").add_argument("--observations", required=True)
    args = parser.parse_args(argv)
    if args.command == "summarize":
        lines = [
            json.loads(line)
            for line in Path(args.observations).read_text().splitlines()
            if line.strip()
        ]
        share = next((x["challenge_share"] for x in lines if "challenge_share" in x), 1)
        print(json.dumps(summarize(lines, share), sort_keys=True))
        return 0
    try:
        config = load_config(args.config)
    except (OSError, ValueError):
        print(json.dumps({"state": UNVERIFIED, "findings": [{"code": "config"}]}))
        return 2
    result = check(config)
    print(json.dumps(result, sort_keys=True))
    if args.observe is not None:
        stamped = {"at": int(time.time()), **result}
        with args.observe.open("a") as journal:
            journal.write(json.dumps(stamped, sort_keys=True) + "\n")
    return EXIT[result["state"]]


if __name__ == "__main__":
    sys.exit(main())
