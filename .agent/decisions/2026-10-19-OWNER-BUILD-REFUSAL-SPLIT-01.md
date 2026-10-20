# OWNER-BUILD-REFUSAL-SPLIT-01: a Carbon capability gap doesn't count against the miner

Date: 2026-10-19
Status: APPROVED by the owner (option 1). Confirmed in the Test Lead's session and relayed to the Carbon Validator, who records it and draws the classification.

## Question and answer (verbatim)

- **Raised by:** the Carbon Validator, while approving e90cdc3c6 (`CANDIDATE_BUILD_REFUSED`).
- **Put to the owner by Test Lead:** "when a validator can't build a miner's submission because Carbon itself doesn't support something in it yet, should that count against the miner?"
  - Option 1: "Don't count it: no use of the 10-submissions-per-exam allowance, and any fee is refunded."
  - Option 2: "Count it like any failed build."
- **Owner's answer (verbatim):** "1. And we add the capability."

## Related, same session: the private-exam cap

- **The owner kept 1 submission per epoch.** He said, verbatim: "10 just seems low. 1 per epoch is good. But seems like more than 10 okay depending on the cost to add data".
- **He then approved the Validator's proposal:** **C = 20 per miner per exam version, with daily rotation, for every Challenge.** The fallback is Battery at C = 10 rotating every 12 h. Owner, verbatim: "Approve for now."
- **These values are revisable.**
- **Sources:** the proposal is `codex-queue/reports/PRIVATE_EXAM_CAP_PROPOSAL_20261019.md`; the decision is recorded in `OWNER-EXAM-CAP-ROTATION-01`.
- **This supersedes C = 10,** which was the cap at the time the question above was put.

## Decided (owner)

- **A build refusal caused by a Carbon capability gap**, meaning an op or construct Carbon hasn't implemented yet, **doesn't count against the miner.** It uses none of the per-miner graded-submission cap (C = 20 per exam version, below), and any fee is refunded.
- **Each gap is added as a capability, not kept as a refusal.** It goes on Launchpad's op list.
- **Neither kind is retried.**
- **A refusal caused by the candidate's own construct** (a malformed graph, over caps, a policy rule) keeps `CANDIDATE_BUILD_REFUSED` semantics.

Build refusals happen before any grading, so neither class discloses anything about a sealed exam.

## Classification (Validator), over `build_refusal.CODES`

**`CARBON_CAPABILITY_GAP`** (no charge, add the capability):
- aten_arguments_not_supported, aten_input_kind_not_supported, aten_node_kind_not_supported;
- aten_op_not_allowlisted, aten_op_not_lowered, aten_result_metadata_not_supported, aten_tuple_index_not_supported;
- aten_scatter_index_not_static, aten_scatter_shape_or_dtype_not_supported;
- dynamic_shape, named_function_not_allowlisted, op_not_allowlisted, op_not_supported_v0;
- dtype_not_allowed, constant_dtype_not_allowed;
- **plus `unspecified`, and any code not in the registry.** Ambiguity is resolved in the miner's favour, because a build refusal leaks nothing and costs no exam wear.

**`CANDIDATE_BUILD_REFUSED`** (the candidate's construct or a containment/determinism rule):
- aten_scatter_index_out_of_bounds, aten_scatter_registered_resource_bound;
- bundle_graph_caps_refused, bundle_graph_invalid, bundle_graph_oversized;
- bundle_state_oversized, bundle_state_parameter_count_invalid, bundle_state_parameter_invalid, bundle_state_source_invalid;
- cap_exceeded, constant_bytes_mismatch, constant_malformed, constant_not_base64;
- graph_call_cycle, input_names_mismatch, integer_constant_out_of_range;
- named_function_arity, named_function_refused;
- op_not_allowed_in_role, op_refused, open_constants, oversized_document;
- parameter_kind_mismatch, parameter_kind_unknown, parameter_not_default, parameters_not_allowlisted;
- prng_impl_not_allowed, result_count_mismatch, role_mismatch, role_unknown;
- shape_malformed, value_id_invalid, value_undefined.

**Rules:**
- **A new code joins the registry with its class stated.** An unclassified code is treated as a gap.
- **A missing or malformed refusal file stays `FAILED_INFRA`,** unchanged.
- **Moving a code between classes is a recorded change,** never silent.

## Implementation note (2026-10-19)

- **The split is implemented** at `45efddb64` (`build_refusal.CODES` as {code: class}, the GAP outcome naming its op).
- **Accounting rule for the counters still to be built:** the per-miner cap (`OWNER-EXAM-CAP-ROTATION-01`) counts **graded** submissions only, so a build refusal is excluded by definition.
- **When a fee exists,** a `CARBON_CAPABILITY_GAP` outcome refunds it.

## Classification change (Carbon Validator, 2026-10-19, Launchpad v6 lowering `df7b01c8d`)

**New codes:**
- **GAP:** aten_index_not_static, aten_index_shape_or_dtype_not_supported. These mirror the scatter codes already classed as gaps.
- **CANDIDATE:** aten_index_out_of_bounds. The miner's index lies outside the tensor.
- **CANDIDATE:** key_dtype_outside_init. A policy rule: PRNG keys are allowed in the init role only.
- **CANDIDATE:** allowlist_version_mismatch. The miner pinned an allowlist other than the one served, which the staging contract's G3 row marks as the candidate's. If a rotation makes a miner's pin stale, that is handled by a grace window at rotation, not by reclassifying the code.

**`*_registered_resource_bound` is split, not moved:**
- **Why:** the check (`lower_torch.py` near lines 711 and 840) mixes two causes.
  - `largest_intermediate_bytes` measures the miner's own tensor, so it is the candidate's.
  - `nodes_executed` and `constant_bytes` are inflated by Carbon's unrolled emission: 2 + 7 nodes per update for scatter, one node per index run for index. A native op would need one node, so this part is Carbon's gap.
- **Codes:**
  - aten_scatter_registered_resource_bound and aten_index_registered_resource_bound stay **CANDIDATE**. They are raised only when the miner's tensor exceeds `largest_intermediate_bytes`.
  - aten_scatter_lowering_expansion_bound and aten_index_lowering_expansion_bound are **GAP**. They are raised when only the unrolled node or constant cost exceeds the caps, and they go on Launchpad's op list as "native scatter/gather".
- **Order:** check the miner's tensor first, so that if both causes apply the code is CANDIDATE.
- **Shipping:** v6 is prospective and not served, so the split ships with v6 and no interim class is needed.
- **Cap values are unchanged.** The same registered `CAPS` still refuse the graph, so containment holds. Only the label and the accounting differ.

## Policy item: `dot_general` precision HIGHEST (Carbon Validator, 2026-10-19)

- **Admitted, with conditions.** `precision ∈ {DEFAULT, HIGHEST}` is allowed. Any other non-default value stays `parameter_not_default`, which is CANDIDATE.
- **Why:** HIGHEST asks for full fp32 accumulation. It narrows the numerical freedom rather than widening it, it discloses nothing, and its extra cost is already captured by the per-case inference_cost.
- **Conditions:**
  - the Carbon interpreter executes HIGHEST as fp32 accumulation, never TF32 or bf16 passes;
  - the JAX-vs-PyTorch backend parity tests include a HIGHEST `dot_general` case.
- **Until both hold,** the code stays refused.
