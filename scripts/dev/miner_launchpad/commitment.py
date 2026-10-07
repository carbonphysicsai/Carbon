"""The strategy commitment at the Launchpad's doors (LAUNCHPAD-ACCEPT-02).

A validator that requires a commitment admits a submission only against the
hotkey's on-chain commitment of the frozen candidate's digest
(`daemon.commitment_digest`, OWNER-COMMITMENT-POSTER-01). The `commit`
operation asks for it; `carbon.chain.commitment_poster` reads, prepares and
broadcasts, and the miner's own signer signs after the miner types on its
terminal. This module holds only what the doors show and read:

- `frozen_candidate`: the open epoch's frozen candidate, read from the
  campaign's files, as the freeze and submit rules read them;
- `view`: the campaign's commitment as `observe` and `campaign_view` show it,
  from the request the campaign recorded and the poster's never-resend record.
  It reads no chain and holds no key.

Every field is closed: digests, blocks, the chain's extrinsic id, closed codes
and fixed text. A chain's own error text never reaches a door.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from carbon.chain import commitment_poster as cp
from carbon.chain.external_signer import COMMIT_TIMEOUT_S

SCHEMA = "carbon.launchpad.commitment.v1"
_SS58 = re.compile(r"[1-9A-HJ-NP-Za-km-z]{46,48}")
#: How long a broadcast may wait for finality before it reads as reconciling.
_BROADCAST_SECONDS = cp.FINALITY_SECONDS + 30
#: What a miner is told while their signer asks them.
CONFIRM_INSTRUCTION = (
    "Your signer is asking you to post this commitment. Check the digest, "
    "network and fee it shows, then type the last 8 characters of the digest "
    "in the signer's terminal. An agent cannot confirm it."
)
RECONCILING_STEP = (
    "Carbon never sends this commitment again. It reads the chain until the "
    "request's era has passed (about 26 minutes); observe again, and commit "
    "again only if it did not land."
)
COMMITTED_STEP = (
    "The frozen candidate's digest is your hotkey's commitment. Submit it "
    "(carbon_submit), or resume where Carbon's agent selects."
)
BROADCAST_STEP = "Broadcast; waiting for finality. Observe again in a minute."
QUEUED_STEP = "Waiting for the campaigns' supervisor to ask your signer."


def frozen_candidate(root):
    """`(epoch, record, manifest)` of the open epoch's frozen candidate.

    The open epoch is the first committed final epoch without permitted final
    feedback, as `research_campaign.retained_candidate` reads it; whoever froze
    the candidate (the miner, or Carbon's agent, D10). Raises `Rejected`
    `freeze_a_candidate_first` or `final_exams_used`."""
    from carbon.development_session.research_campaign import FINAL_EPOCHS
    from scripts.dev.miner_launchpad.controller import Rejected

    root = Path(root)
    manifest_path = root / "campaign-manifest.json"
    if not manifest_path.exists():
        raise Rejected("campaign_not_prepared", 409)
    for epoch in FINAL_EPOCHS:
        folder = root / ("epoch-" + str(epoch))
        if (folder / "permitted-final-feedback.json").exists():
            continue
        selected = folder / "selected-recipe.json"
        if not selected.exists():
            raise Rejected("freeze_a_candidate_first", 409)
        return (
            epoch,
            json.loads(selected.read_bytes()),
            json.loads(manifest_path.read_bytes()),
        )
    raise Rejected("final_exams_used", 409)


def _when(value):
    try:
        return datetime.datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None


def _digest(value):
    return value if type(value) is str and cp.DIGEST.fullmatch(value) else None


def _block(value):
    return value if type(value) is int and value >= 0 else None


def _poster_record(records, hotkey):
    if records is None or type(hotkey) is not str or not _SS58.fullmatch(hotkey):
        return None
    try:
        row = json.loads(
            (Path(records) / f"commitment-{hotkey}.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    return row if type(row) is dict else None


def view(root, records, in_flight, *, now=None):
    """The campaign's commitment, or None when none was ever requested.

    `records` is the poster's state directory (`RunnerAdapter.commitment_dir`)
    and `in_flight` the campaign's admitted, unfinished dispatch. States:
    QUEUED, CONFIRM_COMMITMENT (the miner is being asked:
    `human_action_required: confirm_commitment`), BROADCAST, RECONCILING (an
    outcome not known yet, never resent), COMMITTED and ALREADY_ON_CHAIN (the
    digest read back at the finalized head), and NOT_COMMITTED with its
    closed `code` and next step."""
    from scripts.dev.miner_launchpad.supervisor import _CODE, next_action

    request = cp.read_request(root)
    if request is None or _digest(request.get("digest")) is None:
        return None
    digest = request["digest"]
    now = datetime.datetime.now(datetime.UTC).timestamp() if now is None else now
    asked_at = _when(request.get("requested_at"))
    record = _poster_record(records, request.get("hotkey"))
    already = request.get("outcome") == cp.PostCode.ALREADY_ON_CHAIN.value
    if record is not None and record.get("digest") != digest:
        record = None  # the poster's record is of another digest
    elif (
        record is not None
        and (asked_at is None or (_when(record.get("updated_at")) or 0) < asked_at)
        # Older than this request. A post still unsettled stays the truth (a
        # new request only reads it, never resends), unless the request
        # itself read the digest back at the finalized head (L3).
        and (already or record.get("state") not in cp.PENDING)
    ):
        record = None
    plan = request.get("plan") if type(request.get("plan")) is dict else None
    working = type(in_flight) is dict and in_flight.get("state") in (
        "QUEUED",
        "RUNNING",
    )
    state, code, on_chain = None, None, None
    row = record.get("state") if record is not None else None
    age = now - (_when(record.get("updated_at")) or 0) if record is not None else None
    if row is None:
        if already and plan is not None:
            state = "ALREADY_ON_CHAIN"
            on_chain = {
                "digest": digest,
                "block": _block(plan.get("current_block")),
                "extrinsic_id": None,
            }
        elif working:
            state = "QUEUED"
        else:
            state = "NOT_COMMITTED"
    elif row == "REQUESTED":
        state = (
            "CONFIRM_COMMITMENT"
            if working and age <= COMMIT_TIMEOUT_S + 5
            else "RECONCILING"
        )
    elif row == "BROADCAST":
        state = "BROADCAST" if working and age <= _BROADCAST_SECONDS else "RECONCILING"
    elif row == "AMBIGUOUS":
        state = "RECONCILING"
    elif row == "COMMITTED":
        state = "COMMITTED"
        extrinsic = record.get("extrinsic_id")
        on_chain = {
            "digest": digest,
            "block": _block(record.get("block")),
            "extrinsic_id": (
                extrinsic
                if type(extrinsic) is str and cp.EXTRINSIC_ID.fullmatch(extrinsic)
                else None
            ),
        }
    elif row == "EXPIRED":
        # Its era passed unseen; a new request may be made.
        state = "QUEUED" if working else "NOT_COMMITTED"
    else:
        state = "NOT_COMMITTED"
        code = {
            "FAILED": cp.PostCode.FAILED.value,
            "NOT_OBSERVED": cp.PostCode.NOT_OBSERVED.value,
        }.get(row) or cp.closed_code(record.get("code"))
        if not _CODE.fullmatch(code):
            code = cp.PostCode.FAILED.value
    confirming = state == "CONFIRM_COMMITMENT"
    if confirming:
        step = CONFIRM_INSTRUCTION
    elif state == "RECONCILING":
        step = RECONCILING_STEP
    elif state in ("COMMITTED", "ALREADY_ON_CHAIN"):
        step = COMMITTED_STEP
    elif state == "BROADCAST":
        step = BROADCAST_STEP
    elif state == "QUEUED":
        step = QUEUED_STEP
    else:
        step = next_action(code) if code is not None else None
    epoch = request.get("epoch")
    return {
        "schema": SCHEMA,
        "digest": digest,
        "epoch": epoch if type(epoch) is int else None,
        "requested_by": "miner" if request.get("requested_by") == "miner" else "agent",
        "recommit": request.get("recommit") is True,
        "state": state,
        "human_action_required": "confirm_commitment" if confirming else None,
        "confirm_with": digest[-8:] if confirming else None,
        "plan": (
            None
            if plan is None
            else {
                "current": _digest(plan.get("current")),
                "current_block": _block(plan.get("current_block")),
                "needed": plan.get("needed") is True,
                "warning": (
                    plan.get("warning") if type(plan.get("warning")) is str else None
                ),
                "queued_other_digests": [
                    d
                    for d in plan.get("queued_other_digests") or []
                    if _digest(d) is not None
                ][:16],
            }
        ),
        "on_chain": on_chain,
        "code": code,
        "next_step": step,
    }
