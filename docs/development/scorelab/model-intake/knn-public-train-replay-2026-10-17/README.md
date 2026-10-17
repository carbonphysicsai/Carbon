# Prospective KNN public-TRAIN intake addendum

This directory is a producer-side, versioned addendum to the immutable
historical intake record. The JSON record keeps the existing model-bank
reference schema identifier and labels itself `record_revision: 2`; this is
not a claim that a receiver parser or formal acceptance path exists.

The original manifest and all saved-state/replay artifacts remain in the
existing public-artifact store under `codex-queue/reports/`; this source PR
does not duplicate model bytes. Their exact paths, SHA-256 digests, and byte
lengths are bound in `prospective-intake-v2.json`. The parent manifest's
historical `INCOMPLETE` disposition is preserved.

The replay is prospective evidence only. It does not reproduce missing
historical output chronology, and the receiver's independent scratch replay
is not a formal intake ACK. The new record remains `RECEIVER_ACK_PENDING`,
`ingested: false`, `scored: false`, `qualification_claimed: false`, and outside
the frozen-18 cohort. No fitting, solver execution, hidden/reference access,
truth join, or score use is authorized by this addendum.

Run the local development check from the repository root with:

```powershell
python -m scripts.dev.score_lab.knn_intake_replay docs/development/scorelab/model-intake/knn-public-train-replay-2026-10-17/prospective-intake-v2.json --artifact-root .
```

The helper in `scripts/dev/score_lab/knn_intake_replay.py` wraps Carbon's
existing safe `recipes.model_from_bytes` codec. It emits a local prospective
replay check only; it is not an integrated intake service or formal ACK.
Optimizer owns the separate receiver ACK and any later acceptance decision.
This directory must not be treated as an accepted model-bank entry.
