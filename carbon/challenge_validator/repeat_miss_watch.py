"""The per-hotkey repeat-miss watch (Validator V7 rulings, codex-queue/reports/VALIDATOR_V7_RULINGS_20261029.md; values: owner record OWNER-V7-CONTROL-REBUILD-VALUES-01).

A crown repeat that misses (FAILED_INFRA, or after V7 `candidate_not_reproducible`) is recorded against the
submission's hotkey and Challenge. When one hotkey has `COUNT` misses on one Challenge within `WINDOW_BLOCKS` (one
day, `exam_cap.DAY_BLOCKS`), an operator alert is filed (one per hotkey, Challenge and window) and logged.

It is an operator alert only: no block, no change to scoring, crowns or the allowance, and nothing reaches a miner. The
numbers are an operational value for the owner's review before mainnet, not a score input. The watch never raises:
a failure to record or alert leaves the outcome exactly as it was.
"""

from __future__ import annotations

import json
import logging

from . import exam_cap

LOG = logging.getLogger("carbon.repeat_miss_watch")
STATUS = "OWNER-V7-CONTROL-REBUILD-VALUES-01"
COUNT = 3
WINDOW_BLOCKS = exam_cap.DAY_BLOCKS


def miss_kind(outcome):
    """The kind of crown repeat miss ``outcome`` is, or None when it is not one."""
    from carbon.challenge_validator import bank_promotion as bp

    if type(outcome) is not dict:
        return None
    if outcome.get("outcome") == bp.CANDIDATE_NOT_REPRODUCIBLE:
        return bp.CANDIDATE_NOT_REPRODUCIBLE
    if (
        outcome.get("outcome") == bp.FAILED_INFRA
        and outcome.get("reason") == bp.REPEAT_MISMATCH
    ):
        return bp.FAILED_INFRA
    return None


def watch(store, adapter, submission_id, outcome):
    """Record ``outcome`` if it is a repeat miss and alert on a hotkey with `COUNT` of them within the window.

    Returns the alert filed now, or None. Never raises."""
    try:
        kind = miss_kind(outcome)
        if kind is None:
            return None
        hotkey = adapter.owner(submission_id)
        block = exam_cap.submission_block(
            adapter.ledger, adapter.contract_digest, submission_id
        )
        if hotkey is None or block is None:
            return None
        store.record_repeat_miss(
            submission_id,
            outcome["evaluation_key"],
            hotkey=hotkey,
            challenge_id=adapter.challenge_id,
            block=block,
            kind=kind,
        )
        recent = [
            b
            for b in store.repeat_miss_blocks(hotkey, adapter.challenge_id)
            if block - WINDOW_BLOCKS < b <= block
        ]
        if len(recent) < COUNT:
            return None
        window = block // WINDOW_BLOCKS
        if not store.record_repeat_miss_alert(
            hotkey, adapter.challenge_id, window, len(recent)
        ):
            return None
        alert = {
            "alert": "repeat_miss_watch",
            "status": STATUS,
            "hotkey": hotkey,
            "challenge_id": adapter.challenge_id,
            "misses_in_window": len(recent),
            "window_blocks": WINDOW_BLOCKS,
        }
        LOG.warning("repeat_miss_alert %s", json.dumps(alert, sort_keys=True))
        return alert
    except Exception:  # noqa: BLE001 - the watch never changes an outcome
        return None
