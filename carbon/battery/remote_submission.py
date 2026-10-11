"""A campaign's frozen candidate, submitted from the miner's machine (C-MLP-03 slice 6).

When the validator does not run beside the campaign, a frozen battery
candidate goes the way any external miner's does: a `battery_submit` message
built by `intake_client`, signed by the miner's own `carbon-miner-signer`
(`btauth/1`, through `BittensorMessageSigner`), and POSTed to the validator's
battery intake (OD-7(b), `carbon.battery.intake`). The miner's machine then
asks for that submission's status until the validator has finished with it.

One submission per epoch, ever: the submission id is recorded (owner-only,
in the campaign root) the moment the intake answers, and a later attempt for
the same epoch only asks for its status. Nothing here scores, holds a key or
reaches the chain: the signer signs, the validator evaluates.

Exposure is not this module's: an operator exposes the intake under the
owner's record (OWNER-INTAKE-EXPOSURE-01), over TLS.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import intake_client

#: How long one evaluation call waits for a verdict before handing back
#: `evaluation_queued` (the submission stays recorded and is asked about
#: again next time).
WAIT_S = 1800.0
POLL_S = 30.0
TERMINAL = {
    "SCORED",
    "INVALID_CONSTRUCTION",
    "RECONSTRUCTION_FAILED",
    "FAILED_INFRA_EXHAUSTED",
    "REFUSED",
    "VOID",
}


class IntakeRefusal(Exception):
    """No evaluation happened; `code` is the intake's or the transport's."""

    def __init__(self, code, description=None):
        super().__init__(code)
        self.code, self.description = code, description


def _record_path(root, epoch):
    return Path(root) / f"intake-submission-epoch-{int(epoch)}.json"


def _signed(signer, facts, body):
    from carbon.chain.auth import BittensorMessageSigner

    return BittensorMessageSigner(signer).sign(
        body, receiver=facts["receiver"], nonce_ns=time.time_ns()
    )


#: The intake reports another receiver than the profile pins (LAUNCHPAD-ACCEPT-03).
RECEIVER_MISMATCH = "intake_receiver_mismatch"


def check_receiver(facts, receiver):
    """The intake's public facts, once their `receiver` is the one the miner's
    profile pins for this Challenge (LAUNCHPAD-ACCEPT-03).

    Asked after every read of the facts and before anything is signed: a
    submit, a resend and a status poll. The signer signs for the receiver it
    is given, so an intake at a wrong or substituted address would otherwise
    be signed for and sent to. A mismatch raises `IntakeRefusal`
    (`intake_receiver_mismatch`) with nothing signed or sent. `receiver` None
    is a profile written before receivers were pinned: it is not checked here,
    and setup and the prelaunch review warn about it."""
    if receiver is not None and (
        type(facts) is not dict or facts.get("receiver") != receiver
    ):
        raise IntakeRefusal(RECEIVER_MISMATCH, intake_client.explain(RECEIVER_MISMATCH))
    return facts


#: The intake takes no Level 4 envelope parts (LAUNCHPAD-LEVELS-01 S4).
LEVEL4_TRANSPORT_UNAVAILABLE = "level4_envelope_transport_unavailable"


def _level4_held(url, signer, submission, read, post, receiver):
    """`(held indices, part count or None)` the intake answers for the
    envelope named `submission`; `IntakeRefusal` for any refusal."""
    facts = check_receiver(read(url), receiver)
    body = intake_client.level4_status_message(facts, submission)
    status, answer = post(url, body, _signed(signer, facts, body))
    if "refused" in answer:
        raise IntakeRefusal(answer["refused"], intake_client.describe(status, answer))
    held, parts = answer.get("held"), answer.get("parts")
    if (
        status != 200
        or answer.get("submission") != submission
        or type(held) is not list
        or any(type(i) is not int for i in held)
        or (parts is not None and type(parts) is not int)
    ):
        raise IntakeRefusal("intake_answer_unrecognised")
    return set(held), parts


def send_level4_envelope(
    url,
    signer,
    *,
    submission,
    envelope,
    read=intake_client.read_intake,
    post=intake_client.post,
    receiver=None,
):
    """A Level 4 candidate's frozen staging envelope, sent ahead of its
    `battery_submit` as signed `battery_level4_part` calls
    (`carbon.battery.level4_parts`, VALIDATOR-25 slice 4).

    The envelope's bytes are sent exactly as frozen, cut by
    `level4_parts.split`. The intake is asked first which parts it holds
    (`battery_level4_status`) and only the missing ones are sent, so a
    resumed or replayed send uploads nothing twice. Each request is signed by
    the miner's signer for the intake's receiver after `check_receiver`.
    Every refusal raises `IntakeRefusal` with its code, never retried: an
    intake that lists no part tools is `level4_envelope_transport_unavailable`
    (nothing signed); a part the intake holds with other bytes is
    `level4_part_conflict`, and another part count `level4_parts_mismatch`.
    Returns the number of parts sent; raises `level4_envelope_incomplete`
    unless the intake then holds every part."""
    from .level4_parts import PartRefused, carries_parts, split

    try:
        chunks = split(envelope)
    except PartRefused as refused:
        raise IntakeRefusal(refused.code, intake_client.explain(refused.code)) from None
    if not carries_parts(check_receiver(read(url), receiver)):
        raise IntakeRefusal(
            LEVEL4_TRANSPORT_UNAVAILABLE,
            intake_client.explain(LEVEL4_TRANSPORT_UNAVAILABLE),
        )
    held, parts = _level4_held(url, signer, submission, read, post, receiver)
    if parts is not None and parts != len(chunks):
        code = "level4_parts_mismatch"
        raise IntakeRefusal(code, intake_client.explain(code))
    sent = 0
    for index, data in enumerate(chunks):
        if index in held:
            continue
        facts = check_receiver(read(url), receiver)
        body = intake_client.level4_part_message(
            facts, submission, index, len(chunks), data
        )
        status, answer = post(url, body, _signed(signer, facts, body))
        if "refused" in answer:
            raise IntakeRefusal(
                answer["refused"], intake_client.describe(status, answer)
            )
        if status != 200:
            raise IntakeRefusal("intake_answer_unrecognised")
        sent += 1
    held, parts = _level4_held(url, signer, submission, read, post, receiver)
    if parts != len(chunks) or held != set(range(len(chunks))):
        code = "level4_envelope_incomplete"
        raise IntakeRefusal(code, intake_client.explain(code))
    return sent


def submit_and_wait(
    url,
    signer,
    *,
    root,
    epoch,
    strategy,
    contract_digest,
    read=intake_client.read_intake,
    post=intake_client.post,
    clock=time.monotonic,
    sleep=time.sleep,
    wait_s=WAIT_S,
    receiver=None,
):
    """Submit once (or recall the epoch's submission), then poll for a verdict.

    Returns `(status, answer, submission_id)` once the answer is terminal.
    Raises `IntakeRefusal` when no evaluation happened, including
    `evaluation_queued` when the wait ran out with the submission still on the
    validator's queue, and `intake_receiver_mismatch` when the intake reports
    another receiver than `receiver`, the profile's pinned one
    (`check_receiver`), before that request is signed.
    """
    from carbon.development_session.data import write_once

    record = _record_path(root, epoch)
    if record.exists():
        submission_id = json.loads(record.read_bytes())["submission_id"]
    else:
        facts = check_receiver(read(url), receiver)
        body = intake_client.submission_message(facts, strategy, contract_digest)
        status, answer = post(url, body, _signed(signer, facts, body))
        if status != 202 or "submission_id" not in answer:
            raise IntakeRefusal(
                answer.get("refused", f"http_{status}"),
                intake_client.describe(status, answer),
            )
        submission_id = answer["submission_id"]
        write_once(
            record,
            json.dumps(
                {"url": url, "epoch": epoch, "submission_id": submission_id},
                sort_keys=True,
            ).encode(),
        )
        record.chmod(0o600)
    deadline = clock() + wait_s
    while True:
        facts = check_receiver(read(url), receiver)
        body = intake_client.status_message(facts, submission_id)
        status, answer = post(url, body, _signed(signer, facts, body))
        if "refused" in answer:
            raise IntakeRefusal(
                answer["refused"], intake_client.describe(status, answer)
            )
        if answer.get("state") in TERMINAL:
            return status, answer, submission_id
        if clock() >= deadline:
            raise IntakeRefusal(
                "evaluation_queued", intake_client.describe(status, answer)
            )
        sleep(POLL_S)
