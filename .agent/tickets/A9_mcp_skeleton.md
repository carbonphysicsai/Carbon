# Ticket A9 — bounded Miner MCP Wave-A control-plane skeleton

**Wave:** A

**Status:** proposed done by this documentation-only closeout; effective only
after independent review, explicit human authorization, and merge

**Build Out:** C9 Wave-A control/disclosure surface; deferred C9/C11 mock/light
execution remains Wave B

**Direct contract dependencies:** public A2, A3, A6 model, and A7 APIs

**Decision authority:** A9-R1--A9-R15 were ratified by the independently
reviewed, explicitly human-authorized PR #32 merge

**Implementation plan:** `.agent/plans/A9_mcp_skeleton.md`

## Current maturity

```text
A9 SPECIFIED / RATIFIED:
YES

A9 IMPLEMENTED:
YES on current main only for the bounded in-process Wave-A
control/disclosure skeleton

A9 TESTED:
YES only for the exact recorded CPU, hostile-input, resource, concurrency,
disclosure, dependency, import, wheel, and quality engineering scope,
including the merged test-proof repairs

A9 SCIENTIFICALLY_QUALIFIED:
NO

A9 SECURITY_QUALIFIED:
NO

A9 NETWORK_QUALIFIED:
NO

A9 COMMERCIALLY_VALIDATED:
NO

A9 PRODUCTION_QUALIFIED:
NO

A9 WAVE STATUS:
done only after this closeout is independently reviewed, explicitly
human-authorized, and merged

A10-A12:
todo
```

Documentation remains neither implementation nor test evidence. The bounded
implementation and recorded engineering evidence below come from the merged
source, canonical tests, fresh package checks, and exact CI history; this
closeout only records that already-merged truth.

## Goal

The merged bounded implementation supplies the smallest in-process miner
control/disclosure boundary that:

- exposes exact public Challenge information;
- uses public provider seams for coarse priors and declarative scaffolds;
- delegates exact dry validation to A2;
- returns a pure non-executing structural/prior estimate;
- delegates submission intake, status, and published-card retrieval to A7;
- consumes query budget before every result lookup; and
- exposes only positive, bounded, requester-authorized public projections.

## Exact Wave-A tools

Register exactly:

```text
get_challenge_info
get_prior
get_mock_scaffold
dry_validate
estimate
submit
get_submission_result
```

Do not register aliases including `info`, `prior`, `scaffold`,
`validate_strategy`, or `submit_strategy`. `light_compare`, `light_train`, and
`list_my_submissions` are unavailable and excluded from Wave A.

## Exact control/disclosure split

Wave A contains no execution. In particular the structural estimate uses no
MockContext, A8 service, fixture-official context, official or fixture Score
Pack, `ScoreInput`, or `InternalResult`, and exposes no floating-point quality
score, predicted official score, rank, predicted card status, predicted gate
result, weight, or emission value.

The exact future `MockExecutionRequest`, `MockRunOutcome`,
`MockTrainEvalService.run_mock`, mock pack identity, mock resource policy, mock
execution/disclosure, `light_compare`, `light_train`, and adaptive-query
security evidence remain a separately ratified Wave-B contract. A8-R15
continues to block that execution-dependent work. It does not block the
separately ratified pure structural/prior estimate.

## Exact public boundaries

- Calls use exact schema version `"1.0"` and an ordered-field `McpCall`; a raw
  dictionary is not the first untrusted boundary, so duplicate fields remain
  detectable.
- Exact frozen/slotted data nominals, slot-declared exact errors with frozen
  supported public payloads, fields, response schema, provider protocols,
  resource policy, root exports, and handler ordering are defined in
  `.agent/plans/A9_mcp_skeleton.md` and A9-R1--A9-R15.
- Trusted composition supplies the same exact A3 registry instance to A9 and
  the injected A7 service; A9 neither inspects nor repairs A7 private state.
- `McpResourceLimits` is mandatory, immutable, finite, and injected with no
  defaults. No query, fee, quota, concurrency, rate, or retry value is invented.
- Missing prior, scaffold, or estimate provider fails with the stable
  tool-unavailable error. The implementation adds no production provider,
  prior publication, scaffold body, or provider cache.
- RequesterIdentity is supplied out of band by trusted composition. Current
  structural equality/requester binding is not authentication; a future
  network adapter owns authentication.
- A9 retains no request/result/provider cache or history and creates no second
  submission store.

## Challenge, provider, submit, and result behavior

- Challenge information performs exact-key lookup without listing and exposes
  only exact `challenge_key`, `lifecycle_status`, `fixture_origin`,
  `effectively_live`, and `allowed_backbones`, plus the `"1.0"` response
  framing version. Draft is unavailable; a fixture is visible only when its
  exact loaded record has exact fixture status, `fixture_origin is True`, and
  exact A3 `assess_live_eligibility(..., fixture_mode=True).eligible is True`;
  its `effectively_live` is false. Live is visible and only A3
  `is_effectively_live` supplies its Boolean, including false. No visibility
  is an admission or qualification claim.
- Priors are coarse, public, versioned, hashed, non-executable, non-binding,
  one-channel, and use only closed `STRUCTURAL_STEER`, `AVOID`, `EXPLORE`, and
  `NOT_INCLUDED` directive kinds. Actual content and closed vocabulary remain
  owner inputs.
- Scaffolds remain separate, exact-ID/version/hash/Challenge-bound,
  declarative, owned, A2-valid, optionally prior-referenced metadata, and
  explicitly execution-deferred. A9 never fills/derives them from priors or
  calls A8.
- Submit calls only exact A7 `submit` followed by exact A7 `get_status` and
  returns a `SubmitReceipt` containing that exact `SubmissionStatusView`.
  It is a lifecycle acknowledgement, not proof of queueing, acceptance,
  payment, provenance, execution, score, validity, rank, weight, or emission.
- Result retrieval consumes query budget before A7 lookup, calls `get_status`
  first, and calls `read_published` only for exact `PUBLISHED`. Other states
  return status and no card. Not-found and wrong requester collapse to one
  stable public error.

## Bounded implementation Definition of Done

- [x] The implementation branch starts from the reviewed ratification merge
      after a fresh exact main/tree/status/CI/ticket/concurrency check; only A9
      is marked `in_progress` in that separately authorized task.
- [x] `carbon/mcp/` contains exactly `__init__.py`, `model.py`, `providers.py`,
      and `service.py` for A9, with no server or network adapter.
- [x] Exact frozen/slotted data nominal types, slot-declared fixed-payload
      errors, and enums implement all fields and closed values ratified by
      A9-R3--A9-R7/A9-R13, rejecting subclasses at public boundaries.
- [x] Exact `"1.0"` call/response framing is enforced with no normalization,
      default, or version negotiation.
- [x] Ordered `McpField` tuples preserve and reject duplicate, unknown,
      missing, non-string, and over-limit fields before dictionary conversion;
      exact-string unknown tools remain tool-unavailable rather than acquiring
      a semantic field schema; raw-envelope construction is storage-only and
      all checks occur inside `McpService.call` after required admission.
- [x] Mandatory injected `McpResourceLimits` bounds exact-built-in iterative
      request capture, response nodes/sequences/strings,
      `max_response_integer_bits`, aggregate bytes, and every exact-top-level
      concurrent call with no default values.
- [x] Capture accepts only the ratified exact built-ins, creates fresh ownership,
      preserves graph topology for exact A2/A7 delegation, bounds cycles,
      aliases, huge integers, UTF-8, and containers, and never invokes hostile
      `repr`/`str`.
- [x] The exact seven tools are registered; every otherwise well-formed,
      resource-admissible exact-string alias plus `light_compare`,
      `light_train`, and `list_my_submissions` returns stable tool unavailable
      without downstream calls.
- [x] Exact A3 delegation performs exact-key projection with no scan/list:
      missing and draft are Challenge-unavailable; only an exact consistent
      fixture with `fixture_origin is True` and exact A3
      `assess_live_eligibility(..., fixture_mode=True).eligible is True` is
      visible with effective-LIVE false; a fixture that loads but has a false
      assessment is unavailable without reason exposure; live is visible with
      only exact A3 supplying both effective-LIVE true and false cases;
      malformed, unknown-lifecycle, and internally inconsistent records are
      unavailable; responses expose only the five allowed Challenge fields.
- [x] Exact prior/scaffold/estimate provider protocols are injected, absence is
      stably unavailable, and provider exceptions or malformed outputs within
      response meters fail closed as integration errors; a first-detected
      response-meter breach remains a resource error.
- [x] Prior projections are one-channel, exact-version/hash/Challenge-bound,
      coarse, closed-directive-only, and contain none of the prohibited prior
      fields or canaries.
- [x] Scaffold projections are exact-version/hash/Challenge-bound, separately
      verified by exactly one canonical A2 call as valid, freshly owned,
      optionally prior-referenced metadata, and always execution-deferred with
      no provider/caller alias; a supplied scaffold selector must equal the
      returned exact scaffold ID.
- [x] `dry_validate` delegates exactly once to current A2 and returns a fresh
      exact public validation result without adding admission or execution.
- [x] `estimate` accepts the same captured graph domain as dry validation,
      calls exact A2 once after provider/Challenge/prior prerequisites, returns
      an A9-owned exact-validation/empty-directive result without calling the
      provider when `ok=False`, calls the provider exactly once only with an
      exact A2-valid dict and `ok=True`, preserves the exact provider validation
      and directive subset, uses the fixed disclaimer, and fails closed without
      exact providers.
- [x] Tests prove resource-admissible supported exact-built-in non-dict roots
      return exact A2 `strategy.type` inside `StructuralEstimate`, invalid
      fields/keys/values and cyclic graphs preserve the exact A2 result, every
      captured A2-invalid estimate has empty directives and zero provider
      calls, a valid Strategy calls the provider once, and estimate performs no
      execution, MockContext/A8 call, fixture/official context or Score Pack use,
      ScoreInput/InternalResult construction, or quality/score/rank/card/gate/
      weight/emission prediction.
- [x] `submit` delegates only to exact A7 `submit` then `get_status`, preserves
      exact capacity-permitted `REJECTED`/`RECEIVED` and duplicate-open
      idempotence, preflights the maximum canonical receipt response envelope
      before A7 mutation, and returns the exact status in `SubmitReceipt`.
- [x] A9 never calls A7 validation, admission, fee-start, retry, cancellation,
      execution, completion, publication, or A6 storage methods and creates no
      duplicate fee/lifecycle effect.
- [x] Every result poll consumes exact query budget after request validation
      but before any A7 lookup; exhaustion is stable and exposes no retry-after,
      queue position, or completion-time estimate; an exact gate budget error
      becomes a fresh fixed public budget error with chaining suppressed, and
      a non-exact-`None` gate return fails integration before A7 lookup; no
      post-consume outcome refunds the budget.
- [x] Result retrieval calls A7 `get_status` first, calls A7 `read_published`
      only for exact `PUBLISHED`, returns exact A6 `EvaluationCard` only then,
      and covers every current A7 state.
- [x] Not-found and wrong-requester retrieval collapse to the same stable
      public error without revealing which condition occurred.
- [x] Every exact public error is nominal and slot-declared with an immutable
      supported public payload (excluding interpreter-owned exception runtime
      metadata); it has the ratified fixed code/message, suppresses chaining,
      accepts no diagnostic fields, and leaks no values, paths, provider or
      owner exceptions, configured limits, secrets, contexts, packs, or state.
- [x] RequesterIdentity exists only out of band, is freshly reconstructed for
      downstream calls, and is documented/tested as structural binding rather
      than authentication.
- [x] Responses expose no private A6/A7 store/record, InternalResult,
      StrategyHash, ChallengeKey from submission storage, attempt/fee/retry/
      handle/pin history, context, seed, pack, path, private cause, fine score,
      margin, stress breakdown, private/free-form diagnostic, or
      owner-unsupplied timestamp; exact A6 `public_diagnostics` stays empty.
- [x] A9 retains zero request, response, provider, or result history/cache and
      creates no second submission store; provider publications remain
      provider-owned and A7 retains its existing process-local state.
- [x] Source/dependency tests enforce use of only public A2/A3/A6-model/A7 APIs
      and exclude A4/A5/A6-store/A7-store/A8/A10+, legacy, PoC, neurons, MCP/
      HTTP SDKs, Bittensor, Torch, JAX, NumPy, chain, weight, and emission code.
- [x] `carbon.mcp.__all__` is exactly the ratified surface with no owner-type
      re-export or compatibility alias.
- [x] Canonical focused coverage exists only at
      `tests/cpu/test_mcp_skeleton.py`, including optional-dependency isolation
      and installed-wheel/outside-tree import.
- [x] Full default CPU regression passes without changing A0--A8 behavior,
      tests, fixtures, dependencies, lockfiles, packaging, CI, quality baseline,
      business/publication files, or A10+ implementation.
- [x] Ruff, Black, and repository no-new-debt checks pass with every changed
      Python file clean; evidence remains bounded engineering evidence and
      creates no scientific, security, network, commercial, production,
      leaderboard, frontier, treasury, chain, weight, or emission claim.

## Closure evidence matrix

Rows 1--29 refer, in order, to the verbatim checked criteria above. The audit
changed only each checkbox marker; it did not add, remove, merge, split, or
rewrite criterion text. `tests/cpu/test_mcp_skeleton.py` is the canonical A9
test unless another path is stated as supporting owner evidence.

| # | Control / owner boundary | Exact current source path and symbol | Canonical A9 evidence; supporting owner evidence | Result and bounded exclusion |
|---:|---|---|---|---|
| 1 | A9-R15 implementation gate | `.agent/WAVE.md`; git topology rather than a Python symbol | Implementation commit `c9c324d1192c9c52009b15970e371d076a0b3e89` has sole parent ratification merge `47a62b2397b4125bb608eb69bf0e3dc6360c519d`; its six-path manifest includes the only A9 status transition. | **PASS.** Historical branch/start authority only; it does not authorize A10 or make this closeout effective before merge. |
| 2 | A9-R14 module and dependency boundary | `carbon/mcp/__init__.py`, `carbon/mcp/model.py`, `carbon/mcp/providers.py`, `carbon/mcp/service.py` | `test_source_dependency_and_owner_call_guards`; `test_installed_outside_tree_isolated_import`; `test_fresh_wheel_outside_tree_import` | **PASS.** Exactly four files and no server/network adapter. |
| 3 | A9-R3--R7 and A9-R13 exact nominals | `carbon/mcp/model.py`: the seven error classes, `McpTool`, `PriorDirectiveKind`, request/publication/response dataclasses, `_copy_*`, `_canonical_submission_state` | `test_exact_exports_enums_and_public_layout`; `test_raw_envelopes_are_storage_only_frozen_and_slotted`; seven-case `test_errors_have_exact_fixed_nonserializable_payloads`; `test_validated_public_nominals_reject_subclasses_and_forged_enums`; `test_submission_wrappers_own_status_and_reject_cross_binding` | **PASS.** Nominal engineering boundary only; frozen wrappers do not authenticate values or make nested graphs deeply immutable. |
| 4 | A9-R3 exact framing | `carbon/mcp/service.py`: `_SCHEMA_VERSION`, `McpService._frame_and_decode`, `_project_*`; `carbon/mcp/model.py`: response constructors | `test_outer_and_structural_call_validation`; `test_exact_exports_enums_and_public_layout` | **PASS.** Exact `"1.0"`; no transport/version-negotiation claim. |
| 5 | A9-R3/R4 ordered call boundary | `carbon/mcp/model.py`: `McpField`, `McpCall`; `carbon/mcp/service.py`: `McpService._frame_and_decode`, `_capture_request_values`, `_FIELD_SCHEMAS` | `test_raw_envelopes_are_storage_only_frozen_and_slotted`; `test_outer_and_structural_call_validation`; `test_call_field_limit_precedes_entry_scan`; `test_field_names_precede_value_access_and_tool_dispatch`; `test_alias_deferred_and_unknown_tools_are_unavailable_without_capture` | **PASS.** In-process framing only; no raw network envelope exists. |
| 6 | A9-R4 resource owner boundary | `carbon/mcp/model.py`: `McpResourceLimits`; `carbon/mcp/service.py`: `_RequestMeter`, `_ResponseMeter`, `_Projector`, `McpService.call` permit | `test_resource_limits_require_exact_positive_u64`; six-dimension `test_each_request_resource_dimension_is_enforced`; `test_valid_shaped_provider_response_limit_is_resource`; `test_response_container_cardinality_is_committed_before_children`; `test_concurrency_precedes_internal_validation_and_releases`; `test_submit_response_preflight_precedes_a7_mutation`; two-dimension `test_submit_preflights_all_maximum_receipt_string_bounds` | **PASS.** Values remain mandatory injected policy, not production limits/rates/fees. |
| 7 | A9-R4 ownership/capture boundary; A2/A7 retain semantic authority | `carbon/mcp/service.py`: `_request_key`, `_capture_request_values`, `_copy_owned_request_graph`, `_Projector.graph` | `test_request_container_cardinality_is_committed_before_children`; four-case `test_capture_rejects_unsupported_values_without_rendering`; `test_capture_preserves_aliases_and_cycles_for_a2`; `test_alias_and_cycle_node_accounting_is_identity_aware`; `test_request_utf8_surrogate_is_invalid_after_metering`; supporting A2 `test_mapping_cycle_is_rejected`, `test_list_cycle_is_rejected`, `test_shared_acyclic_container_is_valid`, `test_arbitrary_value_is_rejected_without_calling_user_display_methods` | **PASS.** Bounded exact-built-in capture, not arbitrary-object containment. |
| 8 | A9-R1/R3 exact tool registry | `carbon/mcp/model.py`: `McpTool`; `carbon/mcp/service.py`: `_TOOL_BY_NAME`, `_FIELD_SCHEMAS`, `McpService._dispatch` | `test_exact_exports_enums_and_public_layout`; nine-case `test_alias_deferred_and_unknown_tools_are_unavailable_without_capture` | **PASS.** Seven tools only; aliases, light tools, and listing remain unavailable. |
| 9 | A9-R5; public A3 registry boundary | `carbon/mcp/service.py`: `McpService._visible_challenge`, `_get_challenge_info`, `_project_challenge_info` | `test_fixture_challenge_projection_is_minimal_and_does_not_enumerate`; `test_challenge_projection_uses_pre_assessment_record_snapshot`; `test_draft_and_false_fixture_assessment_are_unavailable`; `test_live_true_and_false_are_both_visible`; supporting A3 `test_complete_fixture_requires_explicit_fixture_mode`, `test_fixture_mode_requires_fixture_origin`, `test_successful_activation_and_later_artifact_mutation_fail_closed`, `test_diagnostics_do_not_expose_artifact_path_or_bytes` | **PASS.** Visibility is not admission, provenance authentication, or qualification. |
| 10 | A9-R2/R6/R7/R8/R13 provider seams | `carbon/mcp/providers.py`: `PriorProvider`, `ScaffoldProvider`, `EstimateProvider`; `carbon/mcp/service.py`: `_provider_prior`, `_get_mock_scaffold`, `_estimate`, `_project_prior`, `_project_scaffold`, `_project_estimate` | `test_provider_absence_precedes_missing_challenge`; `test_provider_exception_and_cross_binding_fail_closed`; `test_valid_shaped_provider_response_limit_is_resource`; `test_provider_projection_follows_declared_field_precedence`; `test_scaffold_selector_and_a2_invalid_output_fail_integration`; `test_valid_estimate_calls_provider_once_with_owned_strategy`; `test_estimate_provider_must_preserve_validation_identity` | **PASS.** No production provider, publication policy, cache, or fallback is supplied. |
| 11 | A9-R6 prior model/publication boundary | `carbon/mcp/model.py`: `PriorRef`, `PriorDirectiveKind`, `PriorDirective`, `PublishedPrior`; `carbon/mcp/service.py`: `_project_prior`, `_Projector.prior_ref`, `_Projector.directive` | `test_exact_exports_enums_and_public_layout`; `test_prior_is_validated_bound_and_fresh`; `test_provider_exception_and_cross_binding_fail_closed`; `test_response_directive_token_alias_is_charged_once_and_preserved`; `test_response_enum_value_limit_precedes_hidden_name_corruption` | **PASS.** Coarse closed metadata only; no Strategy, score, free text, weight, seed, rank, or emission channel. |
| 12 | A9-R7 scaffold/A2 validation boundary | `carbon/mcp/model.py`: `ScaffoldRef`, `PublishedScaffold`; `carbon/mcp/providers.py`: `ScaffoldProvider`; `carbon/mcp/service.py`: `_get_mock_scaffold`, `_project_scaffold` | `test_scaffold_challenge_binding_precedes_later_fields`; `test_scaffold_selector_detachment_topology_and_exact_a2_call`; `test_scaffold_a2_mutation_cannot_change_returned_snapshot`; `test_scaffold_selector_and_a2_invalid_output_fail_integration` | **PASS.** Declarative metadata only; execution remains deferred and A8 is not called. |
| 13 | A9-R9; public A2 owns schema validation | `carbon/mcp/service.py`: `McpService._dry_validate`, `_project_dry_validation`; public owner `carbon/schema` `dry_validate` | `test_dry_validate_delegates_once_and_reconstructs`; supporting A2 `test_non_object_root_is_rejected`, `test_each_top_level_field_is_required`, `test_unknown_and_legacy_top_level_fields_are_rejected`, `test_mapping_cycle_is_rejected`, `test_validation_is_non_mutating_and_does_not_normalize_or_default` | **PASS.** Adds no admission, execution, normalization, or scientific claim. |
| 14 | A9-R8 structural-estimate boundary | `carbon/mcp/providers.py`: `EstimateProvider`; `carbon/mcp/service.py`: `McpService._estimate`, `_project_invalid_estimate`, `_project_estimate` | ten-case `test_invalid_estimate_preserves_a2_result_and_skips_provider` (`none-root`, `bool-root`, `int-root`, `finite-float-root`, `string-root`, `list-root`, `missing-fields`, `invalid-key`, `partial-missing-fields`, `invalid-field-value`); `test_cyclic_estimate_reaches_a2_and_skips_provider`; `test_valid_estimate_calls_provider_once_with_owned_strategy`; validation/directive identity, precedence, and mutation tests | **PASS.** Exactly one A2 call; zero provider calls/empty directives for every covered invalid path; one provider call only for exact A2-valid input. |
| 15 | A9-R8/A9-R14 plus A8-R15 execution exclusion | `carbon/mcp/service.py`: `McpService._estimate`; all four A9 source files | The criterion-14 estimate tests; `test_source_dependency_and_owner_call_guards` positive import/owner-operation/prohibited-token assertions | **PASS.** Structural/prior estimate only: no A8, MockContext, pack, `ScoreInput`, `InternalResult`, score, rank, gate, weight, or emission behavior. |
| 16 | A9-R10; exact public A7 intake/status boundary | `carbon/mcp/service.py`: `McpService._preflight_receipt`, `_submit`, `_project_receipt` | `test_submit_preserves_a7_rejected_received_and_duplicate_behavior`; `test_submit_response_preflight_precedes_a7_mutation`; two-dimension `test_submit_preflights_all_maximum_receipt_string_bounds`; `test_submit_binds_receipt_to_pre_status_submission_id_snapshot`; submit owner-failure tests; supporting A7 `test_submit_creates_received_with_carbon_generated_uuid4`, `test_within_budget_invalid_strategy_receives_terminal_rejected_id`, `test_open_duplicate_precedes_record_capacity_and_creates_nothing`, `test_concurrent_exact_open_duplicates_commit_once` | **PASS.** Receipt is lifecycle acknowledgement only, not acceptance/payment/execution proof. |
| 17 | A9-R2/R10; A7/A6 own lifecycle, fees, execution, publication, and storage | `carbon/mcp/service.py`: `McpService._submit`; all four A9 source files | `test_source_dependency_and_owner_call_guards` exact allowed-symbol manifest, forbidden owner-operation attributes, and prohibited-type tokens; `test_submit_preserves_a7_rejected_received_and_duplicate_behavior`; supporting A7 `test_within_budget_invalid_strategy_receives_terminal_rejected_id`, `test_open_duplicate_precedes_record_capacity_and_creates_nothing`, `test_start_charge_is_atomic_and_replay_has_no_envelope`, `test_read_published_is_gated_and_requester_bound` | **PASS.** No duplicate owner effect and no A6-store call. |
| 18 | A9-R11/R12 query-policy boundary | `carbon/mcp/providers.py`: `QueryBudgetGate.consume`; `carbon/mcp/service.py`: `McpService._get_submission_result` | `test_poll_gate_precedes_lookup_and_requires_exact_none`; `test_query_budget_error_is_fresh_and_subclasses_fail_integration`; two-case `test_query_gate_cannot_mutate_exported_tool_singleton`; result/error paths verify consume has no refund branch | **PASS.** No retry-after, queue estimate, completion estimate, default budget, or refund policy. |
| 19 | A9-R11; public A7 status/publication and public A6 card boundary | `carbon/mcp/service.py`: `McpService._get_submission_result`, `_begin_submission_result`, `_finish_submission_result`, `_Projector.card` | all-state `test_poll_covers_every_state_and_reads_card_only_when_published`; `test_poll_rejects_missing_or_cross_bound_published_card`; two-case `test_poll_revalidates_status_enum_before_projecting_card`; `test_card_declared_field_semantics_precede_later_limits`; supporting A7 `test_read_published_is_gated_and_requester_bound`, `test_status_is_minimal_fresh_and_requester_bound` | **PASS.** A9 never reads A6 directly and returns no card before exact `PUBLISHED`. |
| 20 | A9-R11/R13 public error collapse; A7 retains distinct internal outcomes | `carbon/mcp/model.py`: `McpSubmissionUnavailableError`; `carbon/mcp/service.py`: `McpService._get_submission_result` exception mapping | `test_poll_collapses_not_found_and_wrong_requester`; `test_poll_canonical_owner_errors_are_not_publicly_distinguished`; supporting A7 requester-bound status/read tests | **PASS.** Public caller cannot distinguish missing from wrong requester. |
| 21 | A9-R13 stable public-error boundary | `carbon/mcp/model.py`: all seven `Mcp*Error` classes and `_FixedLiteral`; `carbon/mcp/service.py`: `McpService.call` and exact owner/provider translations | seven-case `test_errors_have_exact_fixed_nonserializable_payloads`; four-case `test_capture_rejects_unsupported_values_without_rendering`; two-case `test_submit_maps_canonical_owner_boundary_failures`; `test_provider_exception_and_cross_binding_fail_closed`; `test_poll_canonical_owner_errors_are_not_publicly_distinguished`; two-case `test_poll_maps_canonical_owner_boundary_failures` | **PASS.** Fixed payload excludes supported diagnostics; interpreter-owned exception runtime metadata is explicitly outside the immutability claim. |
| 22 | A9-R12; A7 `RequesterIdentity` is structural binding only | `carbon/mcp/service.py`: `_requester`, `McpService.call`, `_submit`, `_get_submission_result` | `test_outer_and_structural_call_validation`; freshness/equality assertions in `test_poll_gate_precedes_lookup_and_requires_exact_none`; `test_poll_collapses_not_found_and_wrong_requester`; supporting A7 `test_status_is_minimal_fresh_and_requester_bound`, `test_read_published_is_gated_and_requester_bound` | **PASS.** No authentication, signature, session, hotkey, or network-identity claim. |
| 23 | A9-R11/R13; A6 owns positive public-card projection | `carbon/mcp/model.py`: `SubmissionResult`, `_validate_card`; `carbon/mcp/service.py`: `_Projector.card`, `_finish_submission_result` | all-state `test_poll_covers_every_state_and_reads_card_only_when_published`; `test_poll_rejects_missing_or_cross_bound_published_card`; `test_card_declared_field_semantics_precede_later_limits`; `test_source_dependency_and_owner_call_guards`; supporting A6 `test_public_projection_is_allow_listed_and_has_no_private_graph`, `test_private_canaries_and_later_owner_fields_are_absent_from_public_card`, `test_repeated_reads_are_distinct_and_mutation_isolated` | **PASS.** Only exact A6 public fields cross; `public_diagnostics` remains empty. |
| 24 | A9-R13 retention/side-effect boundary; providers and A7 own persistence | `carbon/mcp/service.py`: `McpService.__slots__`, `call`; no other A9 state holder | `test_service_surface_has_no_cache_history_or_store`; `test_prior_is_validated_bound_and_fresh`; `test_scaffold_selector_detachment_topology_and_exact_a2_call`; all-state `test_poll_covers_every_state_and_reads_card_only_when_published`; supporting A7 `test_status_is_minimal_fresh_and_requester_bound`, `test_repeated_published_reads_are_fresh_and_fee_free`; supporting A6 `test_repeated_reads_are_distinct_and_mutation_isolated` | **PASS.** Transient permit accounting and mandatory query consume are not history stores. |
| 25 | A9-R14 public dependency/source-policy boundary | All four `carbon/mcp` files and their exact import records | `test_static_source_string_accepts_only_bounded_exact_forms`; `test_static_bound_source_strings_resolve_bounded_name_bindings`; 18-case `test_source_runtime_escape_policy_rejects_prohibited_syntax`; four safe controls in `test_source_runtime_escape_policy_allows_safe_controls`; `test_source_dependency_and_owner_call_guards` | **PASS.** Detects literal/recursive-add/simple-bound/chained/self-rebound/getattr import keys and terminates cycles; this bounded AST policy is not a sandbox or arbitrary Python control-flow/security proof. |
| 26 | A9-R14 exact public surface | `carbon/mcp/__init__.py`: ordered 34-name `__all__` | `test_exact_exports_enums_and_public_layout`; `test_installed_outside_tree_isolated_import`; `test_fresh_wheel_outside_tree_import` | **PASS.** No owner-type re-export or compatibility alias. |
| 27 | A9-R14 canonical-test/package-isolation boundary | `tests/cpu/test_mcp_skeleton.py`; packaged `carbon/mcp` files | `test_installed_outside_tree_isolated_import`; `test_fresh_wheel_outside_tree_import`; supporting `tests/cpu/test_optional_backends.py` and `tests/cpu/test_package_installation.py` | **PASS.** Fresh wheel/import evidence is package engineering evidence, not production security. |
| 28 | A9-R15 regression/scope gate | Current main tree `f934ea4f3c4f63b26e890a26f4c941f73519b73b`; implementation six-path and repair one-path manifests | Focused 143; seven related owner files 935; combined eight-file suite 1078; full default suite 1727; post-merge push run `32809955531` on exact current main | **PASS.** No A0--A8 behavior/fixture/dependency/packaging/CI/baseline or A10+ implementation change is attributed to A9 closeout. |
| 29 | A9-R15 bounded maturity/quality gate | No closeout Python symbol; quality authority is `scripts/check_quality.py` with `.ci/quality-baseline.json` | Exact current-main run `32809955531`, quality job `97687282932`: Ruff `757/776`, Black `62/68`, removed debt 19/6, one repair Python file, no new debt, all changed Python clean; closeout validation has zero changed Python files | **PASS.** Engineering completion creates none of the disallowed qualification, leaderboard, frontier, treasury, chain, weight, or emission claims. |

Audit disposition: **29 PASS / 0 FAIL; 29 checked / 0 unchecked.** The
formerly missing estimate-invalid-input and positive dependency/source-policy
proofs are present in the repaired canonical test blob
`f2f5d35dafa88b56f3beb50f24cc565c32bddec1` merged by PR #34.

## Residual limitations

- The service is an in-process control/disclosure skeleton. It has no MCP
  transport, server, network hosting, authenticated requester identity,
  signature/hotkey/session proof, or production authorization adapter.
- Resource limits and query policy are mandatory injected values; A9 chooses
  no production rates, quotas, windows, fees, retry policy, concurrency value,
  or workload-containment regime.
- Prior, scaffold, and estimate publications remain provider-owned. A9 ships
  no production provider, publication policy/content, scaffold body, prior
  vocabulary, mock pack, or production scaffold.
- Structural estimate and scaffold validation execute no miner code. Wave-B
  mock/light execution, A8 integration, real training, adaptive-query
  resistance, sandbox containment, and arbitrary malicious-Python analysis
  remain deferred.
- The static dependency detector proves only its documented bounded AST policy
  over the four current source files. It is not a Python sandbox, a proof over
  arbitrary control flow, malicious-code containment, or security
  qualification.
- The fresh wheel and isolated imports prove package/install/import behavior
  only. They do not prove end-to-end seed secrecy, official-exam replay
  resistance, network readiness, or production security.
- A10--A12, the leaderboard, frontier, treasury, settlement, chain, weights,
  emissions, and all scientific, security, network, commercial, and production
  qualification remain unimplemented or unqualified as applicable.

## Exclusions

Do not add production provider content/policy, a scaffold body, a mock pack,
mock/light execution, real training, a network server, authentication, default
limits/fees/quotas/rates, A10+, or any scientific/security/network/commercial/
production qualification claim. The historical documentation ratification task
did not check any criterion above; this closeout checks them only from the
merged source, canonical-test, package, history, CI, and quality evidence
mapped here.

**Canonical focused test:** `pytest tests/cpu/test_mcp_skeleton.py -q`
