# SCORELAB-PROSPECTIVE-MODEL-ENTRY-01

**Ticket:** `MODEL-INTAKE-REPLAY-01`  
**Status:** `IMPLEMENTED_WORKING_DECISION`  
**Date:** 2026-10-17

## Problem

Optimizer's exact-state audit independently replayed the retained public-TRAIN
KNN state and found no mismatch, but confirmed that ScoreLab had no
trained-model-bank consumer or admission schema. The producer-side addendum
and replay verifier therefore could not be consumed as a prospective model
entry without inventing an unrelated service or mutating the historical
parent record.

## Decision

Implement the smallest receiver operation inside the existing
`scripts.dev.score_lab` namespace: `model-entry-admit`. It revalidates the
content-bound producer addendum and saved-state replay, then writes a
versioned, create-only receipt that is the prospective entry record. The
receipt binds the addendum digest, historical parent digest, all referenced
state/lineage/fixture/comparison/check artifacts, challenge/recipe/source/TRAIN
identity, exact replay output digests, and prospective placement outside
frozen18. Exact-byte retries are idempotent; a conflicting receipt at the same
path is refused.

The producer addendum remains immutable and continues to report
`ingested: false`. A successful receiver command may report prospective
`ingested: true` in its receipt, but only for the public development entry.
Scoring, truth joins, frozen18 changes, qualification, and LIVE effects remain
false. Historical original output remains unrecovered and `INCOMPLETE`.

## Alternatives considered

- Rewrite or extend the historical parent manifest: rejected because it is
  immutable historical evidence and its previous ACK binds an older digest.
- Create a new database, service, or mutable central registry: rejected as
  unnecessary scope; the bounded entry is the immutable, separately bound
  receiver receipt in the existing artifact store.
- Treat the producer replay report or the earlier parent-manifest ACK as the
  new receiver acceptance: rejected because neither is a separately bound
  admission receipt for this addendum.

## Implementation and evidence

- `scripts/dev/score_lab/model_entry_admission.py`
- `scripts/dev/score_lab/__main__.py` (`model-entry-admit`)
- `tests/cpu/test_score_lab_knn_intake_replay.py`
- Producer record: `docs/development/scorelab/model-intake/knn-public-train-replay-2026-10-17/prospective-intake-v2.json`
- Producer/receiver boundary: adjacent `README.md`

Optimizer independently checked the exact manifest/helper/state and public
fixture; q/v/t/eta output arrays matched. That external result is
`LOCAL_PROSPECTIVE_REPLAY_CHECK_ONLY`, not historical-output recovery or
integrated intake. The new receiver command's synthetic tests do not constitute
an admission of the retained real artifact. Product owns any canonical/build
execution; no further Docker/canonical run is part of this author task.

## Interfaces, invariants, and reversibility

The operation is a local development CLI and writes one create-only JSON
receipt at an explicit output path. It uses the existing safe KNN codec and
replay verifier; it does not load hidden data or model binaries into source
control. The prospective entry is outside frozen18 and has no score or
qualification authority. Removing the command and receipt schema is
reversible; previously emitted receipts remain immutable historical records.

## Human-reserved input

None for this development-only operation. Scientific qualification,
production intake policy, and LIVE admission remain out of scope and fail
closed.

## Smallest superseding change

If the receiver requires another schema or binding, add a prospective receipt
revision and migration/test. Do not rewrite the parent manifest, reinterpret
the earlier ACK, or alter the frozen cohort.
