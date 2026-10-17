# Prospective KNN public-TRAIN intake addendum

This directory is a producer-side, versioned addendum to the immutable
historical intake record. The JSON record keeps the existing model-bank
reference schema identifier and labels itself `record_revision: 2`. The
producer addendum is not itself an admitted model-bank entry.

The original manifest and all saved-state/replay artifacts remain in the
existing public-artifact store under `codex-queue/reports/`; this source PR
does not duplicate model bytes. Their exact paths, SHA-256 digests, and byte
lengths are bound in `prospective-intake-v2.json`. The parent manifest's
historical `INCOMPLETE` disposition is preserved.

The replay is prospective evidence only. It does not reproduce missing
historical output chronology. The new producer record remains `RECEIVER_ACK_PENDING`,
`ingested: false`, `scored: false`, `qualification_claimed: false`, and outside
the frozen-18 cohort. No fitting, solver execution, hidden/reference access,
truth join, or score use is authorized by this addendum.

Run the local development check from the repository root with:

```powershell
python -m scripts.dev.score_lab.knn_intake_replay docs/development/scorelab/model-intake/knn-public-train-replay-2026-10-17/prospective-intake-v2.json --artifact-root .
```

The helper in `scripts/dev/score_lab/knn_intake_replay.py` wraps Carbon's
existing safe `recipes.model_from_bytes` codec. It emits a local prospective
replay check only and cannot admit or score an entry. Test Lead delegated the
missing bounded receiver operation after Optimizer confirmed that no
trained-model-bank consumer/schema existed. The existing ScoreLab namespace
now has a `model-entry-admit` command which re-verifies the bound addendum and
creates a versioned, create-only receipt containing the addendum, parent,
artifact, and replay-output bindings. A same-byte retry is idempotent; a
different receipt at the same path is refused. The receipt is the prospective
entry record; there is no new service or mutable central registry.

Example command (Product/receiver execution only; do not treat this example as
evidence that admission has occurred):

```powershell
python -m scripts.dev.score_lab model-entry-admit `
  --manifest docs/development/scorelab/model-intake/knn-public-train-replay-2026-10-17/prospective-intake-v2.json `
  --artifact-root . `
  --receipt codex-queue/reports/optimizer-20261017-knn-receiver/prospective-entry-receipt.json
```

The producer manifest remains unchanged with `ingested: false`. Only a
successful invocation against the retained public artifacts creates the
separately bound receiver receipt and reports prospective admission. Neither
the receipt nor this source change recovers historical output, changes
frozen18, scores, qualifies, or creates a truth join.

Optimizer's independent audit found no existing ScoreLab trained-model-bank
consumer or admission schema: the ScoreLab CLI handles question/reference
banks, and `recipes.model_from_bytes` is a codec, not an admission route. The
single missing receiver operation is versioned admission of a prospective
public-TRAIN model entry bound to this addendum, the exact saved-state/artifact
digests, and the replay result, with an immutable receiver receipt and
prospective placement outside frozen18. The bounded receiver operation is now
implemented in `scripts/dev/score_lab/model_entry_admission.py`; it has only
been exercised on synthetic fixtures in this source candidate. Real-artifact
admission has not been run, so the producer addendum still says `ingested:
false` and there is no real-entry acceptance claim.

## Other prepared public-TRAIN test models

Optimizer's separate `ALL TEST MODELS` preparation is retained at
`codex-queue/reports/OPTIMIZER_SCORELAB_PREPARED_MODEL_GUARD_COHORT_20261017.md`
and `codex-queue/reports/scorelab-prospective-cohort-20261017/`. It includes a
new TRAIN-only default-seed-11 MLP state (`model-state.npz`, SHA-256
`8a4367f4c84e500af8717e0141de7043a0551b1dad1d84ad67c000cd1d483ef9`; sidecar
`a99ce88da9c6988ed894b45092a33977933ae1e91e78a47b17d3a5ad64baa99b`) and a
new post-reference TRAIN-only reconstructed ridge state (SHA-256
`235ded5c84f67f104a449de65c0c851176dc2a2d2af11fa0e5a68493484d31d6`). These
are preparation artifacts, not recovered historical states or admitted model
entries. Keep the existing references/files in that artifact store; do not
copy binaries into this source change or publish/export them.

This ticket's replay verifier and admission command support the declared KNN
codec only. MLP and ridge remain unsupported by this entry schema until their
state codecs and exact replay routes are separately demonstrated; unknown
codec kinds are refused, not inferred from a filename or sidecar.
