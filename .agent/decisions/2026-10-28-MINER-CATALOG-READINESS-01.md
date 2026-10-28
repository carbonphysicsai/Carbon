# Miner catalog readiness and owner recovery

Classification: **IMPLEMENTATION_LAG** within the owner's current launch-readiness
and C2/C4 app acceptance assignment. Base: frozen
`a0f9286b26671fab28fb99c5e27902000aa9326e`, tree
`0a67d2de418adacd4aaad972acb611623f75989f`.

`docs/MINING.md` promises that an installed catalog entry can practise and that
setup reports installation progress with a retry. The miner's `catalog_state`
instead counts receipt-file and GPU material-directory existence.
`catalog_build` can consequently report COMPLETE and skip an explicit retry
after a child image is removed. Practice independently validates the child and
refuses it. This is a readiness/recovery defect, not scientific admission.

Working decision: reuse the existing pure bound-receipt/context and complete
material validators, then observe the distinct admitted immutable child IDs
with `present_library_worker_images`. Share that result with setup progress and
the Challenge picker. Status reads metadata only; no builds, downloads, starts,
full worker doctor, arbitrary image tags, or new verification framework. Invalid
cache/material and unknown Docker observations cannot establish readiness.

The explicit owner-confirmed miner catalog installer may opt into the existing
`install_pinned_library_worker_image(..., rebuild_missing=True)` mechanism.
Preserve its strict old-receipt validation, atomic verified replacement,
failure preservation and idempotence. Default callers and hostile offline
overlay policy keep their existing behavior. No science, scoring, model,
worker execution policy, library version or qualification changes.

Acceptance: with valid material/cache/context and all expected exact images,
the existing installed counts and COMPLETE/retry behavior remain true. Removing
one child while retaining its valid receipt makes every public readiness reader
count that entry missing and allows the existing retry. The owner installer
reconstructs it from its exact closure, verifies the replacement before updating
the receipt, and subsequent retries reuse it. Corrupt receipts, changed context
or material, unknown/partial image observations and failed replacement never
report ready or silently repair authority. Status itself never starts work.

Validation: reuse already measured source-equivalent catalog baselines, recording
INT's exact module evidence; no local Python, formatter, test or image compute.
Focused canonical tests/quality and a real missing-child/retry/idempotence check
run only after INT releases the test host. Cooling provides non-author source
review and later real app/recovery acceptance. Four real own-agent practices
use admitted versions and their published ready recipes, without custom science
or threshold values. Frozen a0 full-test clones remain untouched.

Source/package identities can change with this repository revision even though
no scoring-producer FILES or worker/model implementation is edited. Real
installation evidence must name its actual source, parents and child images;
old images, caches or receipts must never be relabeled as the successor.
Development Hub remains frozen by the current AGENTS instruction.

Baseline reuse reported by INT (component-equivalent, not one combined run):
exact a0 `test_catalog_gpu_twins_staged.py` 5 passed; source-same b0cd
`test_catalog_after_update.py` 15 and `test_control_center_capabilities.py` 15
passed; source-same full77 `test_catalog_install_wheelhouse_default.py` 7,
`test_library_bundle_two_parents.py` 5 and `test_library_environment_cache.py`
21 passed. The source-equivalence caveat includes the global catalog GPU refs
that moved in Physics. No local validation ran. The frozen a0 full CPU run
subsequently measured 32122 passed; its separate invariant citation-parser
failure remains recorded and belongs to the independently assigned scanner fix.
