# Guarded419 stage128 construction/validation consumer

DEVELOPMENT source tooling. The fixed 128 inputs are 105 construction and 23
internal validation offers. This module does not acquire data, fit a model,
choose thresholds or release T128. TRAIN9 f970 and historical 390/18 remain
unchanged.

`guarded419_train128.build(evidence, *, expected_binding_digest,
expected_manifest_digest, scope)` accepts only Packets' real nominal
`ValidatedT128Evidence` through its `validate_for`. That upstream object
requires original T9 delivery and complete compatible CAL15 evidence. No dict,
PASS field or missing-CAL substitute can construct the consumer result.

Each reused T9 anchor keeps its original raw ID/schema/observer in source
proofs. The mapped stage128 job and source index are explicit. Extraction uses
the same registered five-output reducer, with operative all-181-phase tracking.
Every missing, failed or unresolved offer remains in the ledger with null
outputs. Finite buyer-infeasible construction examples are not filtered away.

The immutable result exposes `construction_jsonl`, `validation_jsonl` and a
digest-bound receipt. Construction and validation have different record
schemas; passing validation or mixed bytes to the shared construction loader
fails. `load_construction` independently checks the receipt and fixed input-only
inventory, then computes observed support from accepted construction labels
only and calls `carbon_arm.load_train`. It returns kit, Train and support;
it never fits. Only construction enters later Network normalization.

`validation_report` consumes all offered validation predictions with an
independently pinned digest. It reports per-quantity mean absolute errors in
native units, explicit paired counts and every reference-unavailable,
abstained or invalid outcome. It computes no mixed-unit scalar and sets no
validation threshold. Validation cannot influence fitting or normalization.

The CAL nominal interface is currently an upstream dependency. Structural
tests deliberately inspect UNSEALED raw mappings and exercise missing-CAL
refusal through the real producer. They cannot mint a qualified split. A
synthetic shared-loader/schema check is not evidence that CAL or the full
positive consumer path passed. That positive test must use the CAL owner's
real nominal fixture after integration; no monkeypatched prerequisite or
fabricated PASS is accepted.

Root owns all tests, execution, public labels, source integration, resources
and merges. There is no EVAL reference, hidden/holdout, qualification, score
adoption, reward or LIVE effect from these files.
