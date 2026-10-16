"""Independent receiver-bound trips; no combined scientific verdict or score."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from carbon.development_session.intake_targets import journal, result_path, validate
from carbon.development_session.profile import canonical

SCHEMA = "carbon.battery.permitted-feedback.multi.v1"
STATUS_NAME = "permitted-validator-status.json"
REFUSAL_SCHEMA = "carbon.battery.intake-refusal.v1"


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical(value))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _result_path(root, target, epoch):
    return result_path(root, target, epoch)


def _refusal_path(root, target, epoch):
    return journal(root, target) / f"intake-refusal-epoch-{epoch}.json"


def _cached(root, target, epoch):
    path = _result_path(root, target, epoch)
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError("validator result unreadable")
    found = json.loads(path.read_bytes())
    from carbon.battery.campaign import VERDICT_STATES

    if (
        type(found) is not dict
        or found.get("schema") != "carbon.battery.permitted-feedback.v1"
        or type(found.get("epoch")) is not int
        or found.get("epoch") != epoch
        or type(found.get("via")) is not dict
        or found.get("via", {}).get("intake") != target["intake_url"]
        or type(found.get("outcome")) is not dict
        or found["outcome"].get("state") not in VERDICT_STATES
    ):
        raise ValueError("validator result differs")
    return found


def aggregate(root, epoch, rows):
    from carbon.battery.campaign import CHALLENGE

    value = {
        "schema": SCHEMA,
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "epoch": epoch,
        # An execution summary, never SCORED or scientific agreement.
        "outcome": {"state": "MULTI_VALIDATOR"},
        "validators": rows,
        "description": "Each validator reports independently; no combined score.",
        "official_eligible": False,
        "reward": False,
    }
    _write(Path(root) / f"epoch-{epoch}" / STATUS_NAME, value)
    return value


def _row(target, feedback=None, code=None):
    return {
        **target,
        "feedback": feedback,
        "state": (
            feedback["outcome"]["state"]
            if feedback
            else (
                "QUEUED"
                if code == "evaluation_queued"
                else (
                    "FAILED_INFRA"
                    if code in {"evaluation_failed_infra", "intake_unreachable"}
                    else "REFUSED"
                )
            )
        ),
        "code": code,
    }


def _finish(root, epoch, rows):
    from carbon.development_session.research_campaign import OperationRefused

    feedback = aggregate(root, epoch, rows)
    if any(row["state"] == "QUEUED" for row in rows):
        raise OperationRefused("evaluation_queued")
    if not any(row["feedback"] is not None for row in rows):
        raise OperationRefused(rows[0]["code"])
    return feedback


async def evaluate(prepared, epoch, record, targets):
    from carbon.battery import campaign
    from carbon.development_session.research_campaign import OperationRefused
    from carbon.development_session.submission_policy import require_submission

    require_submission(prepared)
    targets = validate(targets)
    root = prepared.ledger.root
    gate = getattr(prepared.args, "commitment_gate", None)
    asks = getattr(prepared, "agent", "none") != "none"
    if gate is not None and campaign.commitment_due(prepared.args, root, epoch):
        await campaign._committed(
            gate, root, epoch, record, prepared.manifest, request=asks
        )

    recommit_task = None

    async def stale_recommit():
        nonlocal recommit_task
        # No await between checking and assigning: all target trips run on
        # this event loop. Success or refusal is shared; no duplicate request.
        if recommit_task is None:
            recommit_task = asyncio.create_task(
                campaign._committed(
                    gate,
                    root,
                    epoch,
                    record,
                    prepared.manifest,
                    request=True,
                    recommit=True,
                )
            )
        await recommit_task

    async def one(target):
        try:
            cached = _cached(root, target, epoch)
        except (OSError, ValueError, KeyError, TypeError):
            return _row(target, code="intake_answer_unrecognised")
        if cached is not None:
            return _row(target, cached)
        child = SimpleNamespace(**vars(prepared))
        child.args = SimpleNamespace(**vars(prepared.args))
        child.args.commitment_gate = None  # The same model's gate above, once.
        child.args.receivers = {
            campaign.CHALLENGE.challenge_id: target["receiver_hotkey"]
        }
        directory = journal(root, target)
        try:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError:
            return _row(target, code="evaluation_failed_infra")
        try:
            feedback = await campaign._evaluate_through_intake(
                child,
                epoch,
                record,
                target["intake_url"],
                submission_root=directory,
                stale_recommit=stale_recommit if gate is not None else None,
            )
        except OperationRefused as refused:
            row = _row(target, code=campaign.intake_code(refused.code))
            if row["state"] == "REFUSED":
                try:
                    _write(
                        _refusal_path(root, target, epoch),
                        {
                            "schema": REFUSAL_SCHEMA,
                            "epoch": epoch,
                            "target": target,
                            "state": row["state"],
                            "code": row["code"],
                        },
                    )
                except OSError:
                    # A missing private journal is infrastructure, not proof
                    # that the target's refusal was durably retained.
                    return _row(target, code="evaluation_failed_infra")
            return row
        try:
            _write(_result_path(root, target, epoch), feedback)
        except OSError:
            return _row(target, code="evaluation_failed_infra")
        except (ValueError, TypeError, KeyError, AttributeError):
            return _row(target, code="intake_answer_unrecognised")
        return _row(target, feedback)

    rows = [
        {**target, "feedback": None, "state": "PENDING", "code": None}
        for target in targets
    ]
    aggregate(root, epoch, rows)

    async def publishing(index, target):
        rows[index] = await one(target)
        # Runs on this event loop: a finished peer is visible while another
        # trip is still waiting. No score is selected from the partial set.
        aggregate(root, epoch, rows)

    await asyncio.gather(
        *(publishing(index, target) for index, target in enumerate(targets))
    )
    return _finish(root, epoch, rows)


def queued(
    args, root, epoch, connect, targets, *, now=None, read=None, post=None, floor=None
):
    """Read each recorded target once with the retained receiver/floor/tempo guards."""
    import http.client
    import time

    from carbon.battery import campaign, intake_client
    from carbon.battery import remote_submission as rs
    from carbon.chain.external_signer import SignerFailure
    from carbon.development_session.research_campaign import OperationRefused

    rows, signer = [], None
    for target in validate(targets):
        try:
            feedback = _cached(root, target, epoch)
        except (OSError, ValueError, KeyError, TypeError):
            rows.append(_row(target, code="intake_answer_unrecognised"))
            continue
        if feedback is None:
            try:
                directory = journal(root, target)
                record_path = rs._record_path(directory, epoch)
                if not record_path.exists():
                    rows.append(_row(target, code="evaluation_queued"))
                    continue
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                claimed = rs.claim_status_read(
                    directory,
                    epoch,
                    now=time.time() if now is None else now,
                    floor=rs.READ_FLOOR_S if floor is None else floor,
                )
            except OSError:
                # The infrastructure read failure cannot consume a queued candidate.
                rows.append(
                    {**_row(target, code="evaluation_failed_infra"), "state": "QUEUED"}
                )
                continue
            if claimed:
                try:
                    if signer is None:
                        signer = connect()
                    found = rs.read_status_once(
                        target["intake_url"],
                        signer,
                        root=directory,
                        epoch=epoch,
                        read=read or intake_client.read_intake,
                        post=post or intake_client.post,
                        receiver=target["receiver_hotkey"],
                        once_per_tempo=True,
                    )
                    if found is not None:
                        feedback = campaign.intake_feedback(
                            epoch, target["intake_url"], *found
                        )
                        _write(_result_path(root, target, epoch), feedback)
                except (
                    rs.IntakeRefusal,
                    OperationRefused,
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    AttributeError,
                    http.client.HTTPException,
                    SignerFailure,
                ):
                    pass  # A failed read never becomes a scientific verdict.
        rows.append(_row(target, feedback, None if feedback else "evaluation_queued"))
    try:
        return _finish(root, epoch, rows)
    except OperationRefused:
        return None
