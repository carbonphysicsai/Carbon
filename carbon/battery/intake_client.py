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


def submission_id(hotkey, strategy, contract_digest):
    """The submission id the intake answers for this hotkey, recipe and
    contract, worked out before anything is sent (LP-PROD-G).

    The same three always name the same submission
    (`daemon.submission_identity`, over the recipe exactly as
    `submission_message` sends it), so a client resending a frozen candidate
    first checks that the resend names the submission it means - never a
    second one under another hotkey. The value built here is read for its
    identity only; nothing is authenticated or admitted by it.
    """
    from .challenge import CHALLENGE
    from .daemon import AuthenticatedSubmission, submission_identity

    sent = json.loads(json.dumps(strategy, sort_keys=True, separators=(",", ":")))
    return submission_identity(
        AuthenticatedSubmission(
            hotkey=hotkey,
            receipt={},
            challenge_id=CHALLENGE.challenge_id,
            challenge_version=CHALLENGE.version,
            strategy=sent,
            contract_digest=contract_digest,
        )
    )[1]


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


# --- plain-language feedback ------------------------------------------------------

#: Why a request was refused, and what the miner does about it. Every code the
#: intake or the daemon can return has an entry; `describe` never guesses.
REFUSALS = {
    "rate": "Too many requests from your address. Wait a few seconds and retry.",
    "capacity": "The intake is busy. Retry in a few seconds.",
    "inbox_full": "The validator's queue is full. Retry in a few minutes.",
    "body": "The request is larger than the intake accepts (64 KiB).",
    "body_timeout": (
        "The request's body did not arrive in time. Check your connection, "
        "then send it again."
    ),
    "headers": "A request header is repeated; send each header once.",
    "not_found": "No submission with that id belongs to your hotkey.",
    "tool": "The intake only accepts battery_submit and battery_status.",
    "submission_fields": "A submission needs exactly strategy_json and contract_digest.",
    "development_variant_not_served": (
        "The contract digest names a development-only contract variant, which "
        "is never served to miners. Nothing was sent for evaluation; write the "
        "recipe against the Challenge's published contract digest."
    ),
    "status_fields": "A status request needs exactly submission_id.",
    # The validator's neutral checks (`challenge_validator.Validator.screen`),
    # answered at once; nothing was queued, evaluated or counted.
    "malformed_submission": (
        "The submission's identity or receipt fields are malformed. Rebuild it "
        "with your client and send again."
    ),
    "contract_digest_malformed": (
        "The contract digest is not of the form sha256: plus 64 lowercase hex "
        "characters. Copy it exactly from the Challenge's construction contract."
    ),
    "contract_not_served": (
        "This validator does not serve that construction contract. Read the "
        "Challenge's current contract digest, compile against it and send again."
    ),
    "challenge_mismatch": (
        "The submission or its strategy names another Challenge than the "
        "contract it was sent under. Send each strategy under its own "
        "Challenge's contract."
    ),
    "oversized_submission": "The strategy is larger than this validator accepts.",
    "strategy_not_utf8": "The strategy is not valid UTF-8 text.",
    "strategy_bom": "The strategy starts with a byte-order mark; remove it.",
    "strategy_nesting_too_deep": "The strategy nests objects or lists too deeply.",
    "strategy_not_json": "The strategy is not valid JSON.",
    "strategy_not_object": "The strategy must be a JSON object.",
    "non_finite_value": (
        "The strategy contains NaN or Infinity, or a number too large to be "
        "finite. Use finite numbers only."
    ),
    "duplicate_key": "The strategy repeats a key in one object; give each key once.",
    "integer_out_of_range": "The strategy has an integer outside the signed 64-bit range.",
    "snapshot_unknown": (
        "Your message names a chain snapshot this validator no longer holds. "
        "Read the intake again, rebuild and sign, then send at once."
    ),
    "snapshot_unavailable": (
        "The validator cannot read the chain right now. This is on the "
        "validator's side; retry in a minute."
    ),
    "hotkey_window_used": (
        "Your hotkey already has its submission for this tempo. Send this one "
        "again once the next window opens."
    ),
    "receipt_block_missing": "The validator could not date this request; resend it.",
    "commitment_reader_unavailable": (
        "This validator requires an on-chain commitment it cannot yet read."
    ),
    "commitment_required": "Commit this recipe's hash on chain, then resend.",
    "commitment_contested": (
        "Another hotkey committed this same recipe hash on chain first, so "
        "this submission cannot count for you."
    ),
    "commitment_stale": (
        "Your on-chain commitment was posted before your previous submission "
        "here, so it was already used. Commit this recipe's hash again, then "
        "resend."
    ),
    "backend_not_served": (
        "This validator has no worker image for your recipe's backend. This is "
        "not a verdict on your recipe and nothing was recorded; send it to a "
        "validator that serves the backend, or resend once this one does."
    ),
    # A campaign's own trip through an intake (`campaign._evaluate_through_intake`).
    "evaluation_queued": (
        "Your submission is on the validator's queue and has no verdict yet. "
        "Your candidate stays frozen; submit again later to ask for its result. "
        "It is the same submission, never a second one."
    ),
    "intake_unreachable": (
        "The validator's intake could not be reached, or the address did not "
        "answer as an intake. Nothing was evaluated; check the intake address "
        "and your connection, then submit again."
    ),
    "intake_mismatch": (
        "The configured intake serves another chain or Challenge, or is not a "
        "battery intake. Nothing was sent for evaluation; check the intake "
        "address."
    ),
    "intake_signer_changed": (
        "This epoch's candidate was submitted under another hotkey than the "
        "signer now connected. Nothing was sent; connect the signer of the "
        "hotkey that submitted it to read its result. A candidate is never "
        "submitted again under a second hotkey."
    ),
    "signer_unavailable": (
        "Your signer did not sign this request: it is not running, or it "
        "declined. Start carbon-miner-signer, then submit again; a submission "
        "the validator already received stays the same submission."
    ),
    "evaluation_failed_infra": (
        "The validator's infrastructure failed on every retry. This is not a "
        "verdict on your recipe and your epoch is not used."
    ),
    "intake_changed_since_submission": (
        "This epoch's candidate was submitted to another validator intake than "
        "the one now configured. Configure that intake again to read its "
        "result; a candidate is never submitted twice."
    ),
    "intake_answer_unrecognised": (
        "The validator answered in a way this client does not recognise. "
        "Nothing was evaluated; check the intake serves this version."
    ),
    "TRANSPORT_IDENTITY": (
        "Your hotkey is not registered on this subnet (or the validator's is "
        "not). Register first, then resend."
    ),
    "TRANSPORT_STALE": "The request is too old. Rebuild, sign and send at once.",
    "TRANSPORT_REPLAY": "This exact request was already received.",
    "TRANSPORT_CONFLICT": "A different request reused this request id.",
    "TRANSPORT_CONTEXT": "The message names another network, subnet or Challenge.",
    "TRANSPORT_MALFORMED": "The message is not a valid Carbon request.",
    "TRANSPORT_RATE": "More than 32 requests a second from your hotkey.",
    "TRANSPORT_CAPACITY": "The validator's receipt journal is full.",
    "TRANSPORT_STORE": (
        "The validator could not record the request. This is on the "
        "validator's side; retry."
    ),
    "AUTH_BAD_SIGNATURE": "The signature does not verify for your hotkey.",
    "AUTH_WRONG_RECEIVER": "The request was signed for another validator.",
    "AUTH_STALE": "The signature is older than 10 seconds. Sign and send at once.",
    "AUTH_REPLAY": "This signature was already used.",
    "AUTH_MALFORMED": "The signature headers are missing or malformed.",
    "AUTH_UNAVAILABLE": "The validator cannot verify signatures right now.",
}

_STATES = {
    "RECEIVED": "Received. Waiting for the validator to admit it.",
    "ADMITTED": "Admitted. Waiting to be rebuilt and scored.",
    "RECONSTRUCTED": "Rebuilt by the validator. Waiting to be scored.",
    "FAILED_INFRA": (
        "The validator hit an infrastructure failure. This is not a verdict on "
        "your recipe; it will be retried."
    ),
    "FAILED_INFRA_EXHAUSTED": (
        "The validator's infrastructure failed on every retry. This is not a "
        "verdict on your recipe; nothing was scored."
    ),
    "INVALID_CONSTRUCTION": "Refused: the recipe cannot be built as submitted.",
    "RECONSTRUCTION_FAILED": "The validator could not rebuild your recipe.",
}

_WAITING = {
    "QUEUED": "It is queued behind other submissions.",
    "ROTATION_PENDING": "Scoring is paused until the validator prepares a batch.",
    "POOL_NOT_OPEN": "The validator's exam pool is not open yet.",
}


def _minutes(seconds):
    return max(1, round(seconds / 60))


def explain(code):
    """The plain explanation of one closed refusal code, or None for a code
    this client does not know (shown as the code itself, never guessed)."""
    return REFUSALS.get(code)


def describe(status, answer):
    """One plain-language paragraph for any intake answer."""
    if "refused" in answer:
        code = answer["refused"]
        text = REFUSALS.get(code, f"Refused ({code}).")
        if code == "hotkey_window_used":
            text += (
                f" Next window: block {answer['next_block']}, in about "
                f"{_minutes(answer['retry_after_s'])} min."
            )
        return text
    state = answer.get("state")
    if state == "REFUSED":
        failure = answer.get("failure", {})
        text = REFUSALS.get(failure.get("code"), f"Refused ({failure.get('code')}).")
        if failure.get("next_block") is not None:
            text += f" Next window: block {failure['next_block']}."
        return text
    if status == 202:
        return (
            f"Submitted as {answer['submission_id']}. Ask for its status in a "
            "few minutes; rebuilding and scoring take several."
        )
    if state == "VOID":
        return (
            "Void: the hidden window it was scored on was withdrawn after an "
            "incident. That is not a result about your model: it was never a "
            "score, it is not ranked or weighted, and it does not use your "
            "scoring slot. Submit again when you are ready."
        )
    if state == "SCORED" and "screening" not in answer:
        return (
            "Scored. Under this exam rule its results are sealed: they are "
            "computed on hidden cases, and only Carbon and the validators see "
            "them until Carbon releases those cases to the training data. Your "
            "practice results on public data are unaffected. Development "
            "evidence only: no reward, not a qualification."
        )
    if state == "SCORED":
        s = answer["screening"]
        if not s["eligible"]:
            gates = ", ".join(s.get("gates_failed") or []) or "a mandatory gate"
            return (
                f"Scored on pool version {s['pool_version']}: NOT ELIGIBLE. "
                f"It failed {gates}; a failed gate is never offset by score."
            )
        text = (
            f"Scored on pool version {s['pool_version']}: eligible, score "
            f"{s['score']} (important region {s['important_score']}); lower is "
            "better."
        )
        if answer.get("nominated"):
            text += " Nominated for a finalist comparison against the incumbent."
        for final in answer.get("finals", []):
            text += f" Final: {final['state']}"
            if final.get("outcome"):
                text += f", {final['outcome']}"
                text += " (promoted)" if final.get("promoted") else ""
            text += "."
        return text + " Development evidence only: no reward, not a qualification."
    text = _STATES.get(state, f"State: {state}.")
    if state == "INVALID_CONSTRUCTION" and answer.get("failure"):
        f = answer["failure"]
        issues = "; ".join(
            f"{i.get('code')} at {'/'.join(map(str, i.get('path', [])))}"
            for i in f.get("issues", [])
        )
        text += f" Reason: {f.get('code')}" + (f" ({issues})." if issues else ".")
    if answer.get("waiting") in _WAITING:
        text += " " + _WAITING[answer["waiting"]]
    return text
