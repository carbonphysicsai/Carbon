# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

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

Exposure is not this module's: the intake binds loopback until the owner's
security review records its exposure (`OWNER-…INTAKE-EXPOSURE-NN`).
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
):
    """Submit once (or recall the epoch's submission), then poll for a verdict.

    Returns `(status, answer, submission_id)` once the answer is terminal.
    Raises `IntakeRefusal` when no evaluation happened, including
    `evaluation_queued` when the wait ran out with the submission still on the
    validator's queue.
    """
    from carbon.development_session.data import write_once

    record = _record_path(root, epoch)
    if record.exists():
        submission_id = json.loads(record.read_bytes())["submission_id"]
    else:
        facts = read(url)
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
        facts = read(url)
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
