"""The exact OD-4a request the owner approves before one all-burn publication.

OD-4a approves Phase A all-burn weights on testnet only "within a recorded
block window and transaction count". This module turns that approval in
principle into one numbered, digest-bound request for exactly one
publication. The owner approves by its `request_digest`.

    python -m carbon.battery.od4a request --operator-config OP.json \
        --probe PROBE.json --intent EXPORT/weight-intent.json \
        --sequence 1 --start-after 20 --window 600 --expires-utc 2026-10-02T00:00:00Z

Inputs, all read from files, with no chain call and no wallet:
- the operator config: the testnet context and the publisher's public hotkey;
- a fresh runtime probe report (`carbon.chain.runtime_probe`): it must be
  `COMPATIBLE_USED_SURFACE` on this genesis, and its finalized block anchors
  the window;
- the deployment's signed all-burn intent (`operate export`): the signature
  must verify, and the intent must be exactly ALL_BURN.

The window is the operator's proposal: it starts `--start-after` blocks after
the probe's finalized block and lasts `--window` blocks. Nothing here
chooses one. OD-4b (winner weights) is excluded by construction.

The output also carries the operator-config `transaction_authorization`
fragment. Its `authority_record_digest` stays `HUMAN_INPUT` until the owner's
written approval of this exact `request_digest` exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from . import signing

SCHEMA = "carbon.battery.od4a-request.v1"
#: The all-burn row: the burn sink UID 0 takes the whole normalized weight.
ALL_BURN_ROW = [[0, 65535]]
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class RequestRefused(ValueError):
    """A request that cannot be prepared: nothing is written."""


def _digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(body).hexdigest()


def build_request(
    *,
    operator,
    probe,
    intent,
    sequence,
    start_after,
    window,
    expires_utc,
):
    """The request document; refuses anything that is not exactly Phase A."""
    for name, value in (
        ("sequence", sequence),
        ("start_after", start_after),
        ("window", window),
    ):
        if type(value) is not int or value <= 0:
            raise RequestRefused(name + " must be a positive whole number")
    if type(expires_utc) is not str or not _UTC.match(expires_utc):
        raise RequestRefused("expires_utc must be an exact UTC timestamp")
    from carbon.development_testnet.operator import TESTNET_GENESIS

    context = operator["context"]
    if (
        context.get("network") != "testnet"
        or context.get("netuid") != signing.NETUID
        or str(context.get("genesis_hash")).lower() != TESTNET_GENESIS
    ):
        raise RequestRefused("only the approved testnet subnet 567 is served")
    if probe.get("status") != "COMPATIBLE_USED_SURFACE":
        raise RequestRefused("the runtime probe is not compatible")
    if probe["context"]["genesis_hash"].lower() != context["genesis_hash"].lower():
        raise RequestRefused("the probe read another chain")
    if not signing.verify(intent) or intent.get("kind") != "weight_intent":
        raise RequestRefused("the weight intent's signature does not verify")
    payload = intent["payload"]
    if payload.get("mode") != "ALL_BURN" or payload.get("winner_weights") is not False:
        raise RequestRefused("only the Phase A ALL_BURN intent is published")
    finalized = probe["context"]["finalized_block"]
    first = finalized + start_after
    request = {
        "schema": SCHEMA,
        "authority": "OWNER-BATTERY-TESTNET-01 OD-4a",
        "authorization_id": f"OD4A-BATTERY-{sequence:04d}",
        "context": {
            "network": "testnet",
            "endpoint": context["endpoint"],
            "chain_id": context["chain_id"],
            "genesis_hash": context["genesis_hash"],
            "netuid": context["netuid"],
        },
        "publisher": {"uid": 0, "hotkey": operator["publisher"]["hotkey"]},
        "mechanism_id": 0,
        "weights": {"mode": "ALL_BURN", "rows": ALL_BURN_ROW},
        "expected_runtime_spec": probe["spec_version"],
        "runtime_probe": {
            "surface_digest": probe["surface_digest"],
            "finalized_block": finalized,
            "finalized_hash": probe["context"]["finalized_hash"],
        },
        "valid_from_block": first,
        "valid_through_block": first + window - 1,
        "max_dispatches": 1,
        "max_fee_tao": 0,
        "max_spend_tao": 0,
        "fee_rule": "refuse at dispatch if any nonzero fee is observed",
        "expires_utc": expires_utc,
        "source_intent": {
            "digest": _digest(intent),
            "key_id": intent["key_id"],
            "pool_version": payload.get("pool_version"),
        },
        "excluded": [
            "miner weights",
            "winner weights (OD-4b: not authorized)",
            "any row other than UID 0",
        ],
        "ambiguity_rule": "reconcile to finalized state; never resend automatically",
        "consumption_rule": "a finalized dispatch consumes this authorization",
        "authorizes_dispatch": False,
    }
    request["request_digest"] = _digest(request)
    request["operator_config_fragment"] = {
        "transaction_authorization": {
            "authorization_id": request["authorization_id"],
            "authority_record_digest": (
                "HUMAN_INPUT: digest of the owner's written approval of "
                + request["request_digest"]
            ),
            "publisher_hotkey": request["publisher"]["hotkey"],
            "expected_runtime_spec": request["expected_runtime_spec"],
            "valid_from_block": request["valid_from_block"],
            "valid_through_block": request["valid_through_block"],
        }
    }
    return request


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.od4a")
    sub = parser.add_subparsers(dest="command", required=True)
    request = sub.add_parser("request")
    request.add_argument("--operator-config", required=True)
    request.add_argument("--probe", required=True)
    request.add_argument("--intent", required=True)
    request.add_argument("--sequence", type=int, required=True)
    request.add_argument("--start-after", type=int, required=True)
    request.add_argument("--window", type=int, required=True)
    request.add_argument("--expires-utc", required=True)
    args = parser.parse_args(argv)
    try:
        document = build_request(
            operator=json.loads(Path(args.operator_config).read_bytes()),
            probe=json.loads(Path(args.probe).read_bytes()),
            intent=json.loads(Path(args.intent).read_bytes()),
            sequence=args.sequence,
            start_after=args.start_after,
            window=args.window,
            expires_utc=args.expires_utc,
        )
    except RequestRefused as refused:
        print(json.dumps({"refused": str(refused)}))
        return 2
    print(json.dumps(document, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
