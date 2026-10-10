"""INCENTIVE-CANARY-01 slice 1: is the best model getting paid?

    python -m scripts.dev.canary.incentive check --config <file>

A passive check, run on the miner side over **public surfaces only**:
- valV2's on-chain weight row (`SubtensorModule.Weights`), at a finalized
  metagraph snapshot;
- the validator's signed score feed (VALIDATOR-29): its
  `leaderboard.incumbent`;
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

A surface that cannot be read is UNVERIFIED, never a pass. Testnet 567 only.
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

SCHEMA = "carbon.incentive-canary.config.v1"
PASS, ATTENTION, UNVERIFIED, BLOCKER = "PASS", "ATTENTION", "UNVERIFIED", "BLOCKER"
#: The u16 weight row's resolution: a share may round by a few units.
U16 = 65535
TOLERANCE_UNITS = 4
BATTERY = "battery-fastcharge-ageing-development-v1"


class Unverified(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def verify_epoch(row, hotkeys, incumbents, n_challenges, canaries, burn_uid=0):
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
    for uid, value in sorted(weights.items()):
        if uid == burn_uid:
            continue
        hotkey = hotkeys.get(uid)
        if hotkey in canaries:
            findings.append({"level": BLOCKER, "code": "canary_weighted", "uid": uid})
        elif hotkey not in paid:
            findings.append(
                {"level": BLOCKER, "code": "weight_to_non_incumbent", "uid": uid}
            )
    by_hotkey = {hotkey: uid for uid, hotkey in hotkeys.items()}
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


def load_config(path):
    config = json.loads(Path(path).read_text())
    keys = {"schema", "validator_hotkey", "intake_url", "feed_key", "policy"}
    if (
        type(config) is not dict
        or not keys <= set(config) <= keys | {"roles", "sybil"}
        or config["schema"] != SCHEMA
        or type(config.get("roles", False)) is not bool
        or config.get("sybil", "sybil-near") not in _sybil_scenarios()
    ):
        raise ValueError("incentive_config_malformed")
    return config


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


def read_leaderboard(intake_url, feed_key, challenge=BATTERY, *, opener=None):
    """The signed feed's `leaderboard` (incumbent and standing)."""
    import urllib.request

    from carbon.challenge_validator.feed_file import verify_feed

    url = intake_url.rstrip("/") + "/carbon/v1/feed/" + challenge
    try:
        with (opener or urllib.request.urlopen)(url, timeout=10) as response:
            feed = json.loads(response.read())
    except Exception:  # noqa: BLE001 - any failed read is unverified, never a pass
        raise Unverified("feed_unavailable") from None
    if not verify_feed(feed, feed_key):
        raise Unverified("feed_signature_invalid")
    leaderboard = feed.get("leaderboard")
    return leaderboard if type(leaderboard) is dict else {}


def read_incumbent(intake_url, feed_key, challenge=BATTERY, *, opener=None):
    """The incumbent hotkey the validator's signed feed names, or None."""
    leaderboard = read_leaderboard(intake_url, feed_key, challenge, opener=opener)
    incumbent = leaderboard.get("incumbent")
    return incumbent.get("hotkey") if type(incumbent) is dict else None


async def read_weights(context, validator_hotkey):
    """`(row, {uid: hotkey})` of `validator_hotkey`'s weights, read at one
    finalized snapshot, from the endpoint whose genesis is the context's."""
    import bittensor as bt

    from carbon.chain.models import hash256
    from carbon.chain.sdk import BittensorReader

    snapshot = await BittensorReader().capture(context)
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
    finally:
        await client.close()
    if type(row) is not list:
        raise Unverified("weights_malformed")
    return [[int(u), int(v)] for u, v in row], hotkeys


def check(
    config,
    *,
    weights_reader=None,
    incumbent_reader=None,
    leaderboard_reader=None,
    context=None,
):
    """One check of the current epoch. Returns the result line. With
    `"roles": true` in the config, the incentive roles' ordering too; with
    `"sybil": "<scenario>"`, the sybil pair's split and shares."""
    from carbon.challenge_validator.canary import CANARY_HOTKEYS
    from carbon.rewards.winner_decay import load_policy

    try:
        if context is None:
            from carbon.development_session.chain_onboarding import (
                carbon_testnet_context,
            )

            context = carbon_testnet_context()
        if context.network != "testnet":
            raise Unverified("testnet_only")
        policy = load_policy(config["policy"])
        row, hotkeys = asyncio.run(
            (weights_reader or read_weights)(context, config["validator_hotkey"])
        )
        if config.get("roles"):
            leaderboard = (leaderboard_reader or read_leaderboard)(
                config["intake_url"], config["feed_key"]
            )
            incumbent = (leaderboard.get("incumbent") or {}).get("hotkey")
        else:
            leaderboard = None
            incumbent = (incumbent_reader or read_incumbent)(
                config["intake_url"], config["feed_key"]
            )
    except Unverified as failed:
        return {"state": UNVERIFIED, "findings": [{"code": failed.code}]}
    except Exception as failed:  # noqa: BLE001 - infrastructure is unverified
        return {
            "state": UNVERIFIED,
            "findings": [{"code": "read_failed", "type": type(failed).__name__}],
        }
    result = verify_epoch(
        row,
        hotkeys,
        {BATTERY: incumbent},
        len(policy.challenges),
        frozenset(CANARY_HOTKEYS),
        burn_uid=policy.burn_uid,
    )
    if leaderboard is not None:
        from scripts.dev.canary.roles import ROLES

        result["findings"] += verify_roles(leaderboard, ROLES)
    if config.get("sybil"):
        scenario = _sybil_scenarios()[config["sybil"]]
        findings, shares = verify_sybil(
            row, hotkeys, scenario["of"], scenario["hotkey"]
        )
        result["findings"] += findings
        result["shares"] = shares
        result["challenge_share"] = 1 / len(policy.challenges)
    if leaderboard is not None or config.get("sybil"):
        levels = {f.get("level", UNVERIFIED) for f in result["findings"]}
        result["state"] = next(
            (s for s in (BLOCKER, ATTENTION, UNVERIFIED) if s in levels), PASS
        )
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
