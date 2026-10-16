# Executable N1 development diagnostic

This command wraps the existing authenticated producer and N1 diagnostic. It
performs no acquisition, fit, inference, optimizer replay or rule adoption.
It cannot fill an absent reference bank. Root runs it only on explicitly
registered compatible public development evidence or synthetic fixtures.

```sh
python -m scripts.dev.score_lab.n1_diagnostic \
  --input-root /path/to/public-bundle \
  --manifest run.json \
  --manifest-sha256 FULL_INDEPENDENTLY_BOUND_RAW_SHA256 \
  --output-dir /path/to/fresh-diagnostic-output
```

There are no defaults for uncertainty: the manifest must supply the exploratory
bootstrap replicate count and public analysis seed. Root supplies process,
memory and wall-clock bounds through the existing executor. The entry point
does not launch another campaign or reserve resources.

## Run manifest v1

The exact top-level fields are:

| Field | Meaning |
|---|---|
| `schema` | `carbon.scorelab.n1-diagnostic-run.v1` |
| `scope` | `PUBLIC_DEVELOPMENT` or `SYNTHETIC_FIXTURE` |
| `job` | Exact job in the independently pinned N1 registration |
| `population` | One population, never pooled; current public registration accepts P only |
| `registration_sha256` | Raw SHA256 of the existing committed N1 registration |
| `files` | Map from artifact IDs to exact `{path, sha256}` specifications |
| `draws` | Artifact ID for the original ordered JSON array of draws |
| `banks` | One producer-input specification per original draw |
| `members` | Complete fixed model/recipe roster, including unavailable members |
| `gamers` | Explicit predeclared gamer member IDs; empty means UNMEASURED |
| `bootstrap`, `seed` | Explicit exploratory uncertainty inputs passed unchanged to the existing library |

File paths are relative POSIX paths below the public input root. Traversal,
absolute paths, backslashes, symlinks and Windows reparse entries are refused.
Files are read lazily, checked against their byte SHA256 and reused without
directory discovery. Unused declared files are refused and never read. The
run manifest's raw SHA256 is supplied independently on the command line.

This is a bounded developer entry point, not an arbitrary-code sandbox or a
cryptographic custody attestation. A hash verifies bytes. Root independently
establishes public origin, compatible source context, prospective cohort and
commitment chronology. The code does not infer those facts from a filename or
claim scientific adequacy from a digest.

### Draws and reference bank

Draws retain their existing `population`, `role`, `outer_weight`, `bank_cluster`
and `task`. Both LEG and VALUE must be present. Roles/population are checked
before any reference artifact is read. The final protected holdout is not an
accepted role. The producer's `HELDOUT_REFERENCE` role names this public
development comparison bank, as in the existing producer contract.

Each `banks` element has exactly:

```json
{
  "population_index": 0,
  "plan": "plan-artifact-id",
  "source_pins": "source-pins-artifact-id",
  "manifest": "producer-manifest-artifact-id",
  "raw_chunks": {"chunk-id": "raw-jsonl-artifact-id"},
  "binding": {
    "plan_digest": "sha256:...",
    "source_pins_digest": "sha256:...",
    "manifest_digest": "sha256:..."
  }
}
```

The builder reconstructs `ValidatedEvidence` from these original raw bytes and
rechecks it with `validate_for`. A serialized reference dictionary, a claimed
calibration PASS or a point-label table cannot substitute. Missing or failed
registered calibration refuses the run. Unresolved questions use the existing
whole-question common mask and remain reported for every model.

### Original model artifacts

Each `members` element has exactly `id`, `recipe`, `predictions`, `fit_receipt`,
`commitments`, `commitment_receipt`, `train_sha256`, `fit_source`, and `kit`.
The four artifact fields name entries in `files`. Remaining fields are Root's
independently fixed expected model, recipe, TRAIN, source-commit and kit identity.

Predictions use the existing `carbon.development-prediction-input.v1` flat
physical rows. Fit receipts use `carbon.development-carbon-arm-receipt.v1`.
Both must name the same model, scope and original combined input-only view;
the predictions' `source_receipt_digest` must match the actual fit receipt.
No TRAIN labels are read by this command. The declared TRAIN digest, fixture
status, kit and actual fit-source commit must match the fit receipt.

Commitments are the original JSONL written before reference use: each row names
`population_index`, `population`, `role`, `outer_weight`, `bank_cluster` and
the existing indexed `commitment`. All original draws must be covered exactly
once; task/model identities must match. The existing judge verifies commitment
digests and execution semantics. Choices are never recomputed from references.

The original commitment/completion receipt must link the same model, scope,
prediction SHA256 and commitment SHA256 and state that references were not
joined and the sealed holdout was not read. Both existing link spellings,
`model_predictions_sha256` and `predictions_sha256`, are supported; if both are
present they must agree. This preserves the already written default-model and
remaining-cohort receipt formats. Chronology remains Root's independent
pre-reference execution record, not a claim newly created by this command.

The current N1 registration is `c3997852...` for `battery-v3-job-dev-v1`.
Its scalar-error control is **SCALAR-ACCURACY-CONTROL-v1**, not historical v2
or the industry cheap baseline. Guarded419 records, kit or job cannot be
relabelled into that binding. A compatible new registration and producer API
must be implemented prospectively before that context can be diagnosed.

## Outputs and failures

The fresh output directory contains:

- `cohort.json`: complete identities, pinned input inventory and uncertainty settings;
- `members.json`: unchanged per-member LEG results and typed VALUE outcomes;
- `alignment.json`: unchanged N1/control comparison, conditional tau/rho,
  recipe-by-VALUE-question bootstrap, top-three outcomes and exclusions;
- `complete.json`: final file hashes and `COMPLETED_DEVELOPMENT_DIAGNOSTIC`.

Completion means the reduction ran; unavailable metrics remain unavailable.
It never means reference qualification or a score-rule decision. One frozen
bank is not many independent banks; seed fits are not independent recipes.
Unsafe/missed members, NONE and missing predictions retain the library's
existing semantics. No rule, mask, normalization, fallback penalty or
uncertainty implementation is added here.

Input-contract refusals exit 2 with a stable code, no candidate penalty and no
new numerical output directory. Outputs are serialized before writing; an
interrupted write may leave a partial directory without `complete.json`.
Existing directories are never overwritten. Root retains the failure and
uses a fresh output path rather than treating partial files as a completed run.
These are internal developer artifacts, not miner disclosure surfaces.
