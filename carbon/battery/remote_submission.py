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
import os
import tempfile
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


def _status_read_signed(signer, facts, body):
    """A status read's headers, from the signer's read-only kind (LA-F18):
    it signs only a `battery_status` read, never a submission or commitment."""
    from carbon.chain.auth import BittensorMessageSigner

    return BittensorMessageSigner(signer).sign_status_read(
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


# --- observe's read of a queued verdict (LA-F18) ----------------------------------

#: One chain epoch (tempo) in blocks: the battery rule's per-hotkey scoring
#: window (`exam.DEVELOPMENT_RULE_V2["per_hotkey"]["window_blocks"]`), which
#: the miner's signer also pins (`commitment_record.json` `tempo_blocks`).
TEMPO_BLOCKS = 360
#: Observe asks the intake about one recorded submission at most once per
#: chain epoch. Before the intake is contacted at all, the floor is one
#: tempo of nominal 12 s blocks; once the intake's facts are read, a read in
#: the tempo of the last one (its finalized block) is not sent.
READ_FLOOR_S = TEMPO_BLOCKS * 12.0


def _read_mark_path(root, epoch):
    return Path(root) / f"intake-status-read-epoch-{int(epoch)}.json"


def _read_mark(root, epoch):
    try:
        found = json.loads(_read_mark_path(root, epoch).read_bytes())
    except (OSError, ValueError):
        return {}
    return found if type(found) is dict else {}


def _write_mark(root, epoch, value):
    mark = _read_mark_path(root, epoch)
    descriptor, staged = tempfile.mkstemp(prefix=f".{mark.name}.", dir=mark.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(json.dumps({**value, "epoch": int(epoch)}).encode())
        os.chmod(staged, 0o600)
        os.replace(staged, mark)
    except BaseException:
        Path(staged).unlink(missing_ok=True)
        raise


def claim_status_read(root, epoch, *, now, floor=READ_FLOOR_S):
    """Whether observe may ask the intake about this epoch's submission now,
    recording that it does (LA-F18).

    False, with nothing recorded, when the epoch has no recorded submission
    (`intake-submission-epoch-N.json`) or was asked less than `floor`
    seconds (one tempo) ago. The time is recorded (owner-only) before the
    intake is contacted, so a read that fails or is refused waits out the
    floor too. A record that cannot be read is replaced."""
    if not _record_path(root, epoch).exists():
        return False
    mark = _read_mark(root, epoch)
    last = mark.get("polled_unix")
    if type(last) in (int, float) and abs(now - last) < floor:
        return False
    _write_mark(root, epoch, {**mark, "polled_unix": now})
    return True


def _claim_tempo(root, epoch, facts):
    """Whether the read may be sent in the tempo of the intake's finalized
    block, recording that tempo: False when the last read was sent in it.
    Facts without a finalized block leave only the time floor."""
    block = (facts.get("snapshot") or {}).get("finalized_block")
    if type(block) is not int or block < 0:
        return True
    tempo = block // TEMPO_BLOCKS
    mark = _read_mark(root, epoch)
    if mark.get("tempo") == tempo:
        return False
    _write_mark(root, epoch, {**mark, "tempo": tempo})
    return True


def read_status_once(
    url,
    signer,
    *,
    root,
    epoch,
    read=intake_client.read_intake,
    post=intake_client.post,
    receiver=None,
    once_per_tempo=False,
):
    """One read-only status read of the epoch's recorded submission (LA-F18).

    Returns `(status, answer, submission_id)`, or None when the epoch has no
    recorded submission, or, with `once_per_tempo`, when a read was already
    sent in the tempo of the intake's finalized block (`_claim_tempo`). It
    never submits, resends or commits, and it polls once, never waiting: the
    read is signed through the signer's read-only kind
    (`_status_read_signed`), which signs only a `battery_status` read.
    Raises `IntakeRefusal` for a refusal, `intake_changed_since_submission`
    when the epoch was submitted to another intake, and
    `intake_receiver_mismatch` (`check_receiver`) before anything is signed.
    """
    record = _record_path(root, epoch)
    if not record.exists():
        return None
    recorded = json.loads(record.read_bytes())
    if recorded.get("url") != url:
        raise IntakeRefusal("intake_changed_since_submission")
    submission_id = recorded["submission_id"]
    facts = check_receiver(read(url), receiver)
    if once_per_tempo and not _claim_tempo(root, epoch, facts):
        return None
    body = intake_client.status_message(facts, submission_id)
    status, answer = post(url, body, _status_read_signed(signer, facts, body))
    if type(answer) is not dict:
        raise IntakeRefusal("intake_answer_unrecognised")
    if "refused" in answer:
        raise IntakeRefusal(answer["refused"], intake_client.describe(status, answer))
    return status, answer, submission_id
