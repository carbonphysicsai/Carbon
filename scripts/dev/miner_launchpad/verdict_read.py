"""Observe reads a queued submission's verdict (LA-F18).

A submit through a validator intake polls for up to `WAIT_S`, then answers
`evaluation_queued`, keeping the frozen candidate. Before LA-F18 only a second
submit asked again. Now observe does, once, for a campaign where the miner
selects:

- only for the open epoch with a recorded submission
  (`intake-submission-epoch-N.json`) and no verdict, and at most once per
  epoch per `remote_submission.READ_INTERVAL_S`, recorded before the read is
  sent, so observe in a loop never hammers the intake; one read at a time in
  this process;
- only when submit itself would be admitted (`_admissible`,
  `_require_current_revision`, `_require_frozen`) and nothing is running or
  queued for the campaign;
- signed through the signer's read-only kind (`status_read`), which signs a
  `battery_status` read and nothing else. Nothing is submitted, resent or
  committed; the signer is reached only once a read is due.

A verdict found so is stored exactly as a replayed submit stores it: the
Challenge's `record_verdict` (its `evaluate`'s own store) and
`after_stored_verdict` (`submit_frozen`'s completion), under the campaign's
ownership lock and a control generation, settled as `_operate` settles. A
submit's refusal kept as `last_refusal` is then history. Anything else - no
verdict yet, a refusal, an unreachable intake or signer - changes nothing
but the read's recorded time, and observe answers as before.
"""

from __future__ import annotations

import contextlib
import json
import threading
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace

#: One read at a time in this process; a second observe meanwhile skips it.
_READING = threading.Lock()


def read_queued_verdict(host, admitted):
    """True when a verdict was read and stored for the campaign; else False.

    Never raises for a read that did not happen or found nothing; the caller
    still suppresses anything unexpected, since observe must answer."""
    from carbon.challenge_registry.campaigns import campaign_for_manifest
    from scripts.dev.miner_launchpad.commitment import frozen_candidate
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.runner import campaign_args, signer_ready

    identity = admitted.campaign["id"]
    root = Path(admitted.campaign["root"])
    try:
        epoch, _record, manifest = frozen_candidate(root)
    except Rejected:
        return False
    campaign = campaign_for_manifest(manifest)
    if campaign.queued_verdict is None or campaign.record_verdict is None:
        return False
    if not _idle(host, identity):
        return False
    cfg = host.configured()
    as_submit = SimpleNamespace(campaign=admitted.campaign, profile=cfg)
    try:
        host._admissible(as_submit)
        host._require_current_revision(as_submit)
        host._require_frozen(as_submit)
    except Rejected:
        return False
    connect = host.verdict_signer or signer_ready
    if not _READING.acquire(blocking=False):
        return False
    try:
        feedback = campaign.queued_verdict(
            campaign_args(cfg, root=root), root, epoch, lambda: connect(cfg)
        )
    finally:
        _READING.release()
    if feedback is None:
        return False
    return _store(host, admitted, campaign, root, epoch, feedback)


def _idle(host, identity):
    """Nothing running here for the campaign, and nothing queued for it."""
    from scripts.dev.miner_launchpad import supervisor as supervision

    thread = host.threads.get(identity)
    if thread is not None and thread.is_alive():
        return False
    with host.db() as db:
        active = supervision.active(db, principal=host.principal, campaign=identity)
    return active is None


def _store(host, admitted, campaign, root, epoch, feedback):
    """Store the verdict as a replayed submit does, if the campaign is still
    as it was: idle, READY and running, and the epoch still open."""
    from carbon.development_session.research_campaign import after_stored_verdict
    from carbon.development_session.research_control import CampaignControl
    from carbon.development_session.research_ledger import CampaignLedger
    from scripts.dev.miner_launchpad import supervisor as supervision
    from scripts.dev.miner_launchpad.controller import owner_lock

    identity = admitted.campaign["id"]
    with host.lock:
        if not _idle(host, identity):
            return False
        stack = ExitStack()
        try:
            stack.enter_context(owner_lock(root))
        except RuntimeError:
            return False
        with stack:
            folder = root / ("epoch-" + str(epoch))
            if (folder / "permitted-final-feedback.json").exists():
                return False
            ledger = CampaignLedger(root)
            control = CampaignControl(ledger)
            status = control.status()
            if status["state"] != "READY" or status["desired"] != "RUN":
                return False
            with ledger.db() as db:
                frozen = db.execute(
                    "SELECT manifest FROM campaign WHERE id=1"
                ).fetchone()
            if frozen is None:
                return False
            owner = json.loads(frozen[0])["owner"]
            generation = control.acquire()
            ledger.generation = generation
            try:
                campaign.record_verdict(ledger, owner, epoch, feedback)
                after_stored_verdict(ledger, epoch)
            finally:
                complete = (root / "campaign-complete.json").exists()
                state = host._settle_ready(
                    control, generation, ledger, host._cleanup, completed=complete
                )
                host._state(identity, state)
        kept = supervision.read_refusal(admitted.campaign.get("last_refusal"))
        if kept is not None and kept.get("operation") == "submit":
            with contextlib.suppress(Exception):
                host._accepted(identity)
    return True
