# COOLING-POOL-TRUTH-LAYOUT-01

## Contract and authority

This is an `IMPLEMENTATION_LAG` repair within the owner's launch verification
assignment. The source and tests start from
`2050255f5fe3dd3aebeb46ab0b916995b70980ee`. Root assigned the bounded repair
after Codex-INT independently confirmed the native/model-space mismatch.
Scientific gates, tolerances, targets, model tables, constants, historical
results and qualification authority do not change.

## Finding and working decision

The proof-grid script reads pool solver truth in native output space. Its
per-answer gate binding consumes model output space, which differs for
registered encoded Cooling versions. Passing the native reference directly to
the encoded gate reader can turn an invalid native pressure or peak into a
valid decoded prediction.

Repair only the operator script's truth-preflight boundary. Convert temporary
copies of the truth-bearing target specifications through the existing
registered binding's model-space conversion, then call the unchanged gate
checker. Keep the original native specifications for the grid, plugin and
oracle, so they retain their existing single conversion. A malformed native
reference that cannot be encoded must stop with `TruthCheckStop`.

The alternative of changing the shared model gate reader would alter valid
production model-output semantics. Changing stored native truth rows would
also double-encode the oracle. Neither is needed. The chosen repair introduces
no Challenge/version/device dispatch and edits no scoring producer files.

## Validation and limits

The existing exact a0 baseline passed `test_pool_proof_grid_raw.py` (28 tests)
and `test_pool_plugin.py` (26 tests). Their relevant source and test blobs are
unchanged through the starting head. New regressions use synthetic native
references and actual registered encoding/gate functions. They must cover
invalid native peak/pressure, valid encoded and native contracts, missing
truths, unchanged source specifications and oracle single-conversion behavior.

All new formatting and tests run remotely. The maintained classifier assigns
the Python change `RUNTIME_FULL`; its new combined tree needs the required
canonical acceptance. The frozen starting run is not evidence for this
changed code. No protected solver data, study, copy, scientific selection,
qualification, publication or launch action is performed by this repair.
