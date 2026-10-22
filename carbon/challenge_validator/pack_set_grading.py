"""Grade one retained model on every batch of its pack set (OWNER-FULL-EXAM-BANK-01).

The per-pack path is unchanged: each batch is graded as its own evaluation record
by the existing regrade routine (`lean_recipe_retention.regrade_retained_entry`,
which runs the retained frozen state on that pack's own case bank, with the cap,
Ladder and KOTH steps off). `pack_set_result.grade_set` then reads those per-batch
graded rows and writes the one set-level result under the pack-set key.

``batch_adapters`` maps each batch's manifest digest to a trusted served adapter
whose discovery is bound to that batch's pack (the receiver builds them from the
delivered pack set, `SealedPackStore.pack_set`). Only bundle recipes are regraded
today; a graph recipe is typed unavailable (`regrade_source_kind_unavailable`) and
so gives no set result. DEVELOPMENT only.
"""

from __future__ import annotations

from . import lean_recipe_retention as retention
from . import pack_set_result as psr


def grade_entry_on_set(
    cap,
    store,
    batch_adapters,
    *,
    set_key,
    batches,
    entry_id,
    artifact_directory,
    entry_directory,
    hotkey,
    challenge_id,
    challenge_version,
    submission_id,
    block,
    runner=None,
):
    """The set-level result for one retained entry, or ``{"state": "UNAVAILABLE",
    "reason": code}`` (slot returned, nothing written) when any batch cannot be
    graded. ``batches`` are the set's digests in order."""

    def grade_batch(digest):
        adapter = batch_adapters.get(digest)
        if adapter is None:
            raise psr.SetResultRefused("set_batch_adapter_missing")
        regraded = retention.regrade_retained_entry(
            adapter,
            entry_id,
            artifact_directory=artifact_directory,
            entry_directory=entry_directory,
            runner=runner,
        )
        row = regraded.get("graded_row")
        if type(row) is not dict:
            # The bound evaluation could not be completed (UNAVAILABLE or
            # evidence missing): infrastructure, never a score.
            raise psr.SetResultRefused(
                "set_batch_"
                + str(regraded.get("private_evaluation_state", "ungraded")).lower()
            )
        return row

    return psr.grade_set(
        cap,
        store,
        hotkey=hotkey,
        challenge_id=challenge_id,
        challenge_version=challenge_version,
        set_key=set_key,
        batches=batches,
        submission_id=submission_id,
        block=block,
        grade_batch=grade_batch,
    )
