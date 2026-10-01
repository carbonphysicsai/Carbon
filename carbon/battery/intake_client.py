"""A miner's side of the battery intake: build, send and poll. It never signs.

The miner signs in its own tooling. Carbon holds no key, so this module has
no signing function and imports no wallet: it builds the exact bytes to sign
and sends bytes with headers the miner produced, for example::

    import bittensor as bt
    from carbon.battery import intake_client as ic

    facts = ic.read_intake(url)
    body = ic.submission_message(facts, strategy, contract_digest)
    headers = bt.http_auth.sign(
        wallet, method="POST", path=facts["path"], body=body,
        receiver_ss58=facts["receiver"],
    )
    answer = ic.post(url, body, headers)        # 202, {"submission_id": ...}

A signature is valid for 10 seconds and the snapshot for 60, so sign and send
straight after building. Poll with `status_message` the same way.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from carbon.transport.models import message

from .intake import INFO_PATH, PUBLIC_SCHEMA, STATUS_TOOL

SUBMIT_TOOL = "battery_submit"


class IntakeMismatch(ValueError):
    """The intake describes a chain or Challenge this client does not."""


def read_intake(url, *, timeout=10.0):
    """The intake's public facts, checked against this client's chain."""
    with urllib.request.urlopen(url.rstrip("/") + INFO_PATH, timeout=timeout) as r:
        facts = json.loads(r.read(65536))
    if type(facts) is not dict or facts.get("schema") != PUBLIC_SCHEMA:
        raise IntakeMismatch("not a battery intake")
    return facts


def _context(facts):
    from carbon.development_session.chain_onboarding import carbon_testnet_context

    context = carbon_testnet_context()
    if (context.network, context.genesis_hash, context.netuid) != (
        facts["network"],
        facts["genesis"],
        facts["netuid"],
    ):
        raise IntakeMismatch("the intake serves another chain")
    return context


def _challenge(facts):
    from .challenge import CHALLENGE

    if [CHALLENGE.challenge_id, CHALLENGE.version] != [
        facts["challenge"]["id"],
        facts["challenge"]["version"],
    ]:
        raise IntakeMismatch("the intake serves another Challenge")
    return CHALLENGE


def _body(facts, tool, fields, request):
    return message(
        _context(facts),
        facts["snapshot"]["id"],
        _challenge(facts),
        session="carbon-battery-intake",
        request=request or f"battery-{time.time_ns()}",
        tool=tool,
        fields=fields,
    )


def submission_message(facts, strategy, contract_digest, *, request=None):
    """The exact bytes of one `battery_submit`, ready for the miner to sign."""
    return _body(
        facts,
        SUBMIT_TOOL,
        {
            "strategy_json": json.dumps(
                strategy, sort_keys=True, separators=(",", ":")
            ),
            "contract_digest": contract_digest,
        },
        request,
    )


def status_message(facts, submission_id, *, request=None):
    """The exact bytes of one status request for the miner's own submission."""
    return _body(facts, STATUS_TOOL, {"submission_id": submission_id}, request)


def post(url, body, headers, *, timeout=30.0):
    """Send signed bytes; returns `(status, answer)`. Refusals are answers."""
    request = urllib.request.Request(
        url.rstrip("/") + "/carbon/v1/mcp",
        data=body,
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            return r.status, json.loads(r.read(65536))
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read(65536) or b"{}")
