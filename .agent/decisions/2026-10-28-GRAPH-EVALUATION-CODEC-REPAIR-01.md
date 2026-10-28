# GRAPH-EVALUATION-CODEC-REPAIR-01

Status: delegated implementation, remote validation pending.
Classification: IMPLEMENTATION_LAG. Base:
`f3ce2c172e7b458da0b6f8f6770180439221387b`, tree
`953f1bb80c50f0aa8dd84f45b739396926573a71`.
Branch: `codex/graph-evaluation-codec-fix`; frozen f3ce, the candidate,
earlier failed tasks and held PhysicsNeMo work remain unchanged.

## Actual defect and bounded choice

The owner-authorized real PUBLIC/SYNTHETIC DEVELOPMENT task
`rtsk_735a0d6993fba557e8249a1dd72c3bf9b6559bea27fb0d699a6b4406450a6d54`
reconstructed on the GPU and inferred on the CPU. Original and source-free
bank-regrade custody passed, but selected evaluation refused before repeat
workers with `bundle_state_archive_invalid`. The original/regrade state,
recipe and allowlist were independently verified byte-identical. The exact
same state passes `physical_graph_state_v2.load` and fails the unconditional
plain `paired_inference.load` imported from `bundle_graph_state`.

Preserved evidence archive SHA256:
`57c24a6acb34b828b865945e874a797a9cd5debab31177f099d5dde1cf37cab0`,
with all 92 inner hashes independently verified by the GPU operator. Actual
state SHA256 remains
`acfb309b0e6e93fd4afdb93bcc96805aebeb05c6f8c1504b89652d05091484ee`.
The read-only actual-loader diagnostic SHA256 is
`6b79fbfac8e719f879fa854157e419a0f74e54aa79e086db3c1436551ac8965a`.
The task is not evidence of COUNTED success. No header, SQL, task marker,
receipt or failed artifact is edited or retried to manufacture acceptance.

The Lead approved a bounded repair of this existing registered-adapter seam
under the owner's launch-readiness and portability instructions. Current
CONSTITUTION/INVARIANTS, WAVE direct-assignment direction, delivery/delegated
protocols, lean construction target and launch handoff govern this work.
No scientific, security, economic, official-image or launch qualification is
delegated by this engineering repair.

KEEP all existing state codecs, inference program constants, plain bundle
defaults, validation rules and query procedures. REPAIR the trusted-controller
dispatch through one `registered_inference_contract` in the existing graph
worker. It uses `graph_adapters.for_version` and the exact published adapter
block to select both the strict loader and the existing fixed inference query
(program, input name, staged modules, provenance and dtype). The existing
synthetic declaration remains a closed known contract. State-header markers
and device/library/version guesses do not select an implementation. Unknown
or altered declarations fail closed through existing typed refusals.

Actual callers traced: selected evaluation has one `infer_frozen_pair` caller
(`_inference_pair_raw`); paired inference validates state, then executes two
fresh children; reconstruction, CPU source-free regrade and pool single-call
timing also select the graph program. These routes now reuse the registered
contract. Bundle inference retains its original loader, program, input name
and defaults. Per-case/batched repeat selection remains the caller's registered
procedure. Existing source, recipe, allowlist, image, shape/dtype, resource,
operation/ledger identity and receipt checks remain active.

No tolerance, score, threshold, policy value, data population, model family,
official eligibility, registration or mainnet authority changes. In particular
Motor's native repeat rule remains its existing exam rule; a float64 tensor
does not select a different tolerance. Source/wheel/context and target image
identities must refresh. No adapter producer `FILES`, shared pack manifest,
dependency lock or scoring kernel bytes change in this slice; old images and
packs cannot be relabeled. The operator must verify actual identities and use
a fresh task after review/validation.

## Evidence plan and limits

Measured untouched f3ce canonical baseline supplied by Codex-INT:
65 passes across paired_inference, single_call_timing and single_call_layer_b
in 19.95s, no skips/failures; existing graph_route_v2 92 passes and
graph_pool_counted_e2e 25 passes reused from the final f3ce gate.
The small graph_regrade_pieces baseline was requested separately because its
old wiring fixtures used empty material rather than registered metadata.

New CPU tests freeze synthetic parameters through actual producers, execute
the actual fixed source-free programs in subprocesses, and compare predictions
to the registered interpreter for plain bundle, decoded single and ensemble
float32/float64 state. Both repeat procedures and the derived single-call
program run. Loaders and numerical predictions are not mocked. Only carrier
accounting is explicitly synthetic; evidence stays TEST_ONLY_LOCAL_RUNNER and
official_eligible false. Corrupt state and unknown adapter declarations must
refuse before execution. Existing query-wiring assertions remain; their setup
now supplies real registered material.

Remote focused queue, one test process and BLAS/OMP/MKL threads set to one:

```text
python -m pytest -q tests/cpu/test_registered_graph_pair_execution.py tests/cpu/test_paired_inference.py tests/cpu/test_graph_regrade_pieces.py tests/cpu/test_graph_route_v2.py tests/cpu/test_f08_f02_graph_adapters.py tests/cpu/test_battery_graph_adapter.py tests/cpu/test_single_call_timing.py tests/cpu/test_single_call_layer_b.py tests/cpu/test_graph_pool_counted_e2e.py tests/cpu/test_pool_dual_e2e.py tests/cpu/test_regrade_retained_entry.py tests/cpu/test_regrade_two_parents.py
python -m pytest -q tests/invariants/test_score_offchain_boundary.py tests/invariants/test_score_variants_unreachable.py tests/invariants/test_b07b_research_task_boundaries.py tests/invariants/test_c07_orchestration_boundaries.py tests/invariants/test_c08_miner_mcp_boundaries.py tests/invariants/test_producer_digest_survives_checkout.py
```

Run pinned Black26.5.1/Ruff0.16.3 and diff/changed-path checks on exact heads.
No local Python, numerical execution, tests, formatter, builds or VM operation.
Cooling owns GPU operations; Codex-INT owns canonical testing/integration.
After independent source review and canonical acceptance, the sole GPU
operator must rebuild genuine target images and submit a fresh task. Verify
that exact task's real load/predict/repeat/speed/count path; a stale Ladder row
or a fixture gate is not the real proof. Dedicated4090/official qualification,
crown/weights and mainnet acceptance remain separate missing evidence.

Hub primary map_ref remains the lean construction/common scoring route.
This corrects its existing adapter-to-evaluator dependency; the Hub remains
frozen under current delivery instructions. Existing LEAD/PROGRESS logs carry
milestones, with no new tracker. Current maturity is implemented source pending
review/validation, not tested or qualified.
