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


def _set_exam_facts(batch_adapters, batches):
    """The version's exam version and hard gates, from the batch packs (they must
    agree), or a refusal."""
    versions, gates = set(), set()
    for digest in batches:
        discovery = batch_adapters[digest].discovery
        snapshot = discovery.evaluation_pack_snapshot
        private_root = discovery.evaluation_pack_private_root
        source = snapshot.read_source_registration(private_root)
        versions.add(source["evaluation_version"])
        score_pack = snapshot.read_json_role(
            private_root, "private", "score_pack", max_bytes=65536
        )
        gates.add(tuple(score_pack["hard_gates"]))
    if len(versions) != 1 or len(gates) != 1:
        raise psr.SetResultRefused("set_batches_disagree")
    return versions.pop(), list(gates.pop())


def grade_set_entry(
    batch_adapters,
    *,
    batches,
    set_key,
    entry_id,
    artifact_directory,
    entry_directory,
    runner=None,
):
    """The operator step: grade one retained entry on its whole pack set and, when
    a set result exists, record it once on the miner's Ladder under the set key.

    The owner and the submission are the retained task's own (`_regrade_origin`);
    the epoch slot is the submission's, taken once under the set key. Returns the
    set result (with ``ladder_feedback_state``) or the typed UNAVAILABLE."""
    from . import exam_cap

    primary = batch_adapters[batches[0]]
    base = retention._owner_directory(artifact_directory, "artifact_directory")
    entries = retention._owner_directory(entry_directory, "entry_directory")
    _entry, origin, owner, *_rest = retention._regrade_origin(
        primary, base, entries, entry_id
    )
    cap = exam_cap.ExamCap(
        primary.ledger, cadence=getattr(primary, "exam_cadence", None)
    )
    store = psr.SetResultStore(primary.ledger)
    result = grade_entry_on_set(
        cap,
        store,
        batch_adapters,
        set_key=set_key,
        batches=batches,
        entry_id=entry_id,
        artifact_directory=artifact_directory,
        entry_directory=entry_directory,
        hotkey=owner,
        challenge_id=primary.challenge_id,
        challenge_version=primary.challenge_version,
        submission_id=origin,
        block=exam_cap.submission_block(
            primary.ledger, primary.contract_digest, origin
        ),
        runner=runner,
    )
    if "graded" not in result:
        return result
    version, gates = _set_exam_facts(batch_adapters, batches)
    return {
        **result,
        "ladder_feedback_state": retention._record_ladder(
            primary,
            origin,
            exam_key=set_key,
            exam_version=version,
            gates=gates,
            graded=result["graded"],
        ),
    }
