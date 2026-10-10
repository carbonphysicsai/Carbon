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
4. An incumbent with no weight is ATTENTION (`incumbent_unpaid`), not a
   blocker. Its promotion may be legitimately ineligible (a same-miner
   tweak, an overdue pool), and the winner ledger saying so is private.

A surface that cannot be read is UNVERIFIED, never a pass. Testnet 567 only.
It signs nothing and sets no weight. DEVELOPMENT evidence; not a security
or economic qualification of the weight path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
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
        return {"state": UNVERIFIED, "findings": [{"code": "no_weights_set"}]}
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


def load_config(path):
    config = json.loads(Path(path).read_text())
    keys = {"schema", "validator_hotkey", "intake_url", "feed_key", "policy"}
    if type(config) is not dict or set(config) != keys or config["schema"] != SCHEMA:
        raise ValueError("incentive_config_malformed")
    return config


def read_incumbent(intake_url, feed_key, challenge=BATTERY, *, opener=None):
    """The incumbent hotkey the validator's signed feed names, or None."""
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
    incumbent = (feed.get("leaderboard") or {}).get("incumbent")
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


def check(config, *, weights_reader=None, incumbent_reader=None, context=None):
    """One check of the current epoch. Returns the result line."""
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
    return verify_epoch(
        row,
        hotkeys,
        {BATTERY: incumbent},
        len(policy.challenges),
        frozenset(CANARY_HOTKEYS),
        burn_uid=policy.burn_uid,
    )


EXIT = {PASS: 0, ATTENTION: 0, UNVERIFIED: 1, BLOCKER: 3}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="scripts.dev.canary.incentive")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").add_argument("--config", required=True)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except (OSError, ValueError):
        print(json.dumps({"state": UNVERIFIED, "findings": [{"code": "config"}]}))
        return 2
    result = check(config)
    print(json.dumps(result, sort_keys=True))
    return EXIT[result["state"]]


if __name__ == "__main__":
    sys.exit(main())
