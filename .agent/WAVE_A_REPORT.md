# Wave A bounded engineering closeout report

**Date:** 2026-08-29

**Repository:** carbonphysicsai/Carbon

**Audit baseline:** origin/main at 2a8b273a1167588efb4a11159da5224264d5b37a

**Baseline tree:** cb7b23d32e3663bbf00704f1e28c16020bfb9226

**Document status:** documentation-only closeout candidate

## A. Scope, authority, and closeout gate

This report audits the already-ratified and already-merged A12 invariant judge,
its supporting Wave A owner surfaces, and the Wave A board. It changes no
implementation, invariant test, CPU test, fixture, workflow, quality baseline,
dependency, packaging, Build_Out sequencing authority, or Wave B artifact.

The unmodified audit baseline has this authoritative administrative state:

- A12 SPECIFIED / RATIFIED: YES.
- A12 IMPLEMENTED: YES, in the bounded invariant-judge/CI scope.
- A12 TESTED: YES, as bounded engineering evidence.
- A12 WAVE STATUS: todo pending administrative closeout.
- Wave A: incomplete pending administrative closeout.
- Wave B: inactive.

This candidate proposes A12 done and Wave A closed in bounded engineering scope.
Those status changes and this report's final closure ruling become repository
authority only after the exact closeout head is independently reviewed,
explicitly human-authorized, and normally merged. Branch existence, a draft
pull request, local validation, and green pull-request CI do not supply that
authority.

The authorized candidate manifest is exactly:

1. .agent/DECISIONS.md
2. .agent/WAVE.md
3. .agent/WAVE_A_REPORT.md
4. .agent/plans/A12_invariant_ci.md
5. .agent/tickets/A12_invariant_ci.md
6. Design_Specs/Build_Out_Constitutional_Overlay.md
7. agent_pack/README.md
8. docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md

Wave A closure is an engineering process milestone. It is not scientific
qualification, security acceptance, network qualification, commercial
validation, production qualification, LIVE authority, launch authority,
frontier authority, or emission authority.

## B. Exact repository and merge topology

| Object | Exact commit | Exact tree | Ordered parents / relationship | Verification |
|---|---|---|---|---|
| PR #50 base / prior main | 37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1 | 8848085952115672a9f90d255e5feb9bee8116db | Prior main after A11 closeout | PASS |
| PR #50 reviewed head | 6695c279728438befd6404fb81c4f7a27e382a67 | 651c568631465a4902d69036a06c937104660d37 | One commit above 37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1 | PASS |
| PR #50 synthetic merge | 11236c1240fb455d9763be242e902ec0a3cee6c3 | 651c568631465a4902d69036a06c937104660d37 | 1: 37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1; 2: 6695c279728438befd6404fb81c4f7a27e382a67 | PASS |
| PR #50 normal merge | 746e56e42c412bc8ba2eeb4d85ed83396e1a084c | 651c568631465a4902d69036a06c937104660d37 | 1: 37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1; 2: 6695c279728438befd6404fb81c4f7a27e382a67 | PASS |
| PR #51 reviewed head | 33b4626a1ffe7d0c65336336a870a8f4a73ab92f | cb7b23d32e3663bbf00704f1e28c16020bfb9226 | One commit above 746e56e42c412bc8ba2eeb4d85ed83396e1a084c | PASS |
| PR #51 synthetic merge | 4fea54f1f1d4d7261bd6fd242f932d72ce6ee651 | cb7b23d32e3663bbf00704f1e28c16020bfb9226 | 1: 746e56e42c412bc8ba2eeb4d85ed83396e1a084c; 2: 33b4626a1ffe7d0c65336336a870a8f4a73ab92f | PASS |
| PR #51 normal merge / audit baseline | 2a8b273a1167588efb4a11159da5224264d5b37a | cb7b23d32e3663bbf00704f1e28c16020bfb9226 | 1: 746e56e42c412bc8ba2eeb4d85ed83396e1a084c; 2: 33b4626a1ffe7d0c65336336a870a8f4a73ab92f | PASS; GitHub signature verified=true, reason=valid |

PR #50 changed exactly six contract documents:

1. .agent/DECISIONS.md
2. .agent/plans/A12_invariant_ci.md
3. .agent/tickets/A12_invariant_ci.md
4. Design_Specs/Build_Out_Constitutional_Overlay.md
5. agent_pack/README.md
6. docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md

PR #51 changed exactly seven implementation paths:

1. .github/workflows/ci.yml
2. tests/invariants/a12_crosswalk.json
3. tests/invariants/a12_support.py
4. tests/invariants/conftest.py
5. tests/invariants/test_a12_crosswalk.py
6. tests/invariants/test_a12_entrypoint.py
7. tests/invariants/test_a12_invariants.py

The reviewed PR #51 head is ancestral to the audit baseline. Its reviewed-head
tree, synthetic-merge tree, and normal-merge tree are identical.

## C. A12 review and repair chronology

| Finding / stage | Candidate head and tree | Evidence | Disposition |
|---|---|---|---|
| A12-CI-1, ratification command discovery | 4e85e3cd4b1c0ee9ef4910db24cad60e4b7c397e; tree 181530a32c69edd36c868600f930751bc8df15e1 | Review found the bare marker command incompatible with pyproject.toml testpaths rooted at tests/cpu. | Superseded. The canonical command became exactly python -m pytest tests/invariants -m invariant -q. |
| Final ratification | 6695c279728438befd6404fb81c4f7a27e382a67; tree 651c568631465a4902d69036a06c937104660d37 | PR CI run 33230465070 succeeded; independent exact-head review completed. | Normally merged by PR #50 as 746e56e42c412bc8ba2eeb4d85ed83396e1a084c. |
| Initial implementation | 18d4f02895533d3a850217824e44b0d6d587c1b0; tree 73948287e0785a7b9f366887979aed80657c0cce | Run 33240409328: 22 invariant tests, 2310 CPU tests, and quality succeeded. Review found A12-TEST-1, A12-XWALK-1, and A12-R11-1. | Superseded; it carries no current review authority. |
| A12-TEST-1 | Same superseded initial implementation head | The subprocess matrix did not behaviorally exercise the committed fail-closed guard. | Repaired by copying the committed guard into synthetic suites and testing partial deselection, runtime skip, expected xfail, non-strict xpass, and collection-time skip. |
| A12-XWALK-1 | Same superseded initial implementation head | Proof kinds, evidence ceilings, infrastructure inventory, and node resolution were not locked exactly. | Repaired with exact machine equality and node-resolution assertions. |
| A12-R11-1 | Same superseded initial implementation head | The dedicated forbidden-input proof did not cover both numeric and Boolean A5 channels. | Repaired across both public input channels and the complete named forbidden set. |
| First replacement | bf978b6e073c7b431b2fcb68cf9826bf582903a9; tree ebc9e800571aebaaea95e3537a0219445bf6200e | Run 33243707714: 27 invariant tests, 2310 CPU tests, and quality succeeded. | Superseded after A12-XWALK-2. |
| A12-XWALK-2 | Same first replacement head | Review found lexical containment could admit parent-traversal or symlink aliases. | Repaired with strict resolved canonical containment and direct traversal/symlink canaries. |
| Final implementation | 33b4626a1ffe7d0c65336336a870a8f4a73ab92f; tree cb7b23d32e3663bbf00704f1e28c16020bfb9226 | Run 33248924648: invariant job 99091100116 passed 28; CPU job 99091100201 passed 2310; quality job 99091100193 passed; Greptile job 99091103640 reported 5/5 and no blocking failure. | Independently reviewed and normally merged by PR #51 as 2a8b273a1167588efb4a11159da5224264d5b37a. |
| Post-merge verification | 2a8b273a1167588efb4a11159da5224264d5b37a; tree cb7b23d32e3663bbf00704f1e28c16020bfb9226 | Push run 33250521376 succeeded on exact main. | Current engineering evidence; administrative closeout remained intentionally pending. |

No owner implementation defect and no new scientific, security, protocol,
economic, or commercial owner decision emerged from the closeout audit.

## D. A12 ticket audit: 24 PASS / 0 FAIL

The criterion text below is preserved in ticket order. Evidence is evaluated
against unmodified current main. Row ceilings are evidence ceilings, not
reinterpretations of the invariant.

| # | Exact criterion text | Current-main evidence and exact node / CI evidence | Bounded evidence ceiling | Result |
|---:|---|---|---|---|
| 1 | **A12-R1 — No seed leakage.** Preserve exactly: official seeds, derived seeds, draw IDs, or reversible identifiers never appear in EvaluationCard, leaderboard, MCP outputs, or miner-visible logs. Include A11 positive-construction redaction as R1/R4 evidence, not a thirteenth A12 invariant. | Crosswalk A12-R1; tests/invariants/test_a12_invariants.py::test_a12_r01_no_seed_leakage_across_public_surfaces; exact owner nodes in section E. | Synthetic in-process projection evidence only; no deployed transport, adaptive leakage, security, or production qualification. | PASS |
| 2 | **A12-R2 — Practice isolation.** Preserve exactly: nominal practice/research execution never accesses official packs, official entropy/seeds, or protected exam data. Current unavailable practice execution proves only a fail-closed boundary. | Crosswalk A12-R2; tests/invariants/test_a12_invariants.py::test_a12_r02_practice_isolation_is_fail_closed; exact owner nodes in section E. | No nominal practice execution backend exists; mock, fixture, scaffold, and estimate boundaries do not prove practice quality or security. | PASS |
| 3 | **A12-R3 — Pinned evaluation.** Preserve exactly: every scored submission is bound to immutable challenge / generator / Score Pack / backend (container digest) versions. | Crosswalk A12-R3; tests/invariants/test_a12_invariants.py::test_a12_r03_scored_fixture_evaluation_is_exactly_pinned; exact owner nodes in section E. | Exact fixture identity and pin enforcement only; no production backend, container enforcement, LIVE, science, or security qualification. | PASS |
| 4 | **A12-R4 — Disclosure allow-list.** Preserve exactly: InternalResult / Model Card fields are never returned on miner-facing APIs unless explicitly allow-listed for the disclosure tier. Include A11 redaction without counting it as a thirteenth invariant. | Crosswalk A12-R4; tests/invariants/test_a12_invariants.py::test_a12_r04_miner_disclosure_uses_positive_allow_lists; exact owner nodes in section E. | Bounded in-process disclosure types only; no transport, authentication, network, gateway, or production security claim. | PASS |
| 5 | **A12-R5 — LIVE requires qualification.** Preserve exactly: LIVE challenges require a complete signed human qualification manifest for that exact challenge version, not merely non-null YAML. Do not claim signer, scientific, or LIVE qualification from tests. | Crosswalk A12-R5; tests/invariants/test_a12_invariants.py::test_a12_r05_live_requires_complete_exact_qualification; exact owner nodes in section E. | Structural exact-version gate evidence only; scientific acceptance, signature verification, signer identity, and key custody remain human-owned. | PASS |
| 6 | **A12-R6 — Execution isolation.** Preserve exactly: miner-supplied strategies run under enforced compute, network, filesystem, and wall-clock limits. Strategy execution isolation is a P0 security invariant; implementation may live in ops docs, but the requirement is here. Current Wave A proves only the negative fail-closed boundary; it does not claim a sandbox or security qualification. | Crosswalk A12-R6; tests/invariants/test_a12_invariants.py::test_a12_r06_production_execution_remains_unavailable_without_sandbox; exact owner nodes in section E. | Negative fail-closed absence proof only; no sandbox, workload isolation, SECURITY_QUALIFIED, or PRODUCTION_QUALIFIED claim. | PASS |
| 7 | **A12-R7 — Infra ≠ science.** Preserve exactly: infrastructure failures (OOM policy kill, node death, queue loss) are never scored as scientific / physics failures and never grant emissions. Preserve typed A7 retry/refund/`FAILED_INFRA` evidence. | Crosswalk A12-R7; tests/invariants/test_a12_invariants.py::test_a12_r07_infrastructure_cannot_be_scored_as_science; exact owner nodes in section E. | Typed fixture-only infrastructure classification, retry/refund, and FAILED_INFRA separation only; named real infrastructure failures and production operations are not integration-tested here. | PASS |
| 8 | **A12-R8 — Determinism.** Preserve exactly: re-running an identical official evaluation under identical versions, seeds, and limits is deterministic within documented tolerances. Current executable proof is limited to exact pinned fixture reproducibility. | Crosswalk A12-R8; tests/invariants/test_a12_invariants.py::test_a12_r08_pinned_fixture_reexecution_is_exactly_reproducible; exact owner nodes in section E. | Exact pinned-fixture reproducibility only; A12 chooses no scientific tolerance and claims no production reproducibility. | PASS |
| 9 | **A12-R9 — No placeholder LIVE.** Preserve exactly: placeholder, fixture, or mock values never enter LIVE configuration or emission weights. A8 non-production/non-emission and future-authority absence are bounded evidence, not an expansion of the invariant. | Crosswalk A12-R9; tests/invariants/test_a12_invariants.py::test_a12_r09_fixture_values_cannot_gain_live_or_emission_authority; exact owner nodes in section E. | Fixture and placeholder rejection only; no frontier, product, receipt, treasury, settlement, chain, weight, or emission types are created. | PASS |
| 10 | **A12-R10 — No silent rescore.** Preserve exactly: historical evaluation records are never silently reinterpreted under newer packs; new pack ⇒ new scoring_version for future runs only. | Crosswalk A12-R10; tests/invariants/test_a12_invariants.py::test_a12_r10_new_pack_cannot_silently_overwrite_history; exact owner nodes in section E. | Bounded process-local insert-only history only; no production-qualified durable store or migration policy. | PASS |
| 11 | **A12-R11 — Forbidden score inputs.** Preserve exactly: prior similarity/alignment, `estimate`, resource forecasts, practice/`light_*` metrics, research information value, exam fee, and mock metrics never enter `S_combined` / Yuma weights. Fee/payment isolation is a required subcase, not a separate row. | Crosswalk A12-R11; tests/invariants/test_a12_invariants.py::test_a12_r11_named_forbidden_signals_cannot_enter_scoring; exact owner nodes in section E. | Closed fixture A5 input boundary and fee separation only; no Yuma or production-weight implementation. | PASS |
| 12 | **A12-R12 — Practice is useful without revealing the realized exam.** Preserve exactly: Carbon measures leakage as incremental ability to infer protected official cases, realized stress composition, exact margins, or unresolved ordering after controlling for physics performance on evaluator-held shadow cases sampled from the declared distribution. Transferable rank improvement can reflect better physics and is not itself a leak. Practice remains declared-incomplete and outside official lifecycle, score, and scheduling authority. Current Wave A does not claim practice usefulness or leakage qualification. | Crosswalk A12-R12; tests/invariants/test_a12_invariants.py::test_a12_r12_practice_is_incomplete_and_has_no_official_authority; exact owner nodes in section E. | Declared-incomplete, non-executing absence proof only; no usefulness, leakage, shadow-case, scientific-adequacy, score, lifecycle, or scheduling claim. | PASS |
| 13 | Add dedicated tests only under `tests/invariants/` and mark every A12 invariant module/test with the already registered `invariant` marker. | All three test modules are canonically contained under tests/invariants and carry module-level pytest.mark.invariant; tests/invariants/test_a12_crosswalk.py::test_a12_crosswalk_resolves_all_dedicated_and_owner_nodes. | Placement and marker proof only; it does not prove any owner behavior by itself. | PASS |
| 14 | Provide a machine-auditable A12-R1 through A12-R12 crosswalk from each row to dedicated assertions and supporting A3–A11 owner tests. | tests/invariants/a12_crosswalk.json; tests/invariants/test_a12_crosswalk.py::test_a12_crosswalk_has_exact_order_and_authority and ::test_a12_crosswalk_resolves_all_dedicated_and_owner_nodes. | Repository-node mapping and exact-contract equality only. | PASS |
| 15 | Exercise public owner surfaces and explicit source/dependency guards; do not copy owner logic, construct success through private state, import legacy authority, or import existing test functions as the aggregate proof. | Dedicated row proofs call public owner surfaces; tests/invariants/test_a12_crosswalk.py::test_a12_suite_has_no_unmapped_or_greenwashing_tests rejects imported owner tests, private-state manufacture, prohibited markers, and prohibited calls. | Static guards plus the bounded dedicated behaviors; no production integration claim. | PASS |
| 16 | Add a dedicated Python 3.11 CI entrypoint running exactly:<br>`python -m pytest tests/invariants -m invariant -q`<br>The explicit directory is mandatory because current `pyproject.toml` roots default pytest discovery at `tests/cpu`; no dedicated tests, a missing or empty `tests/invariants/`, zero `invariant` marker matches, or complete deselection must fail rather than green the job. | .github/workflows/ci.yml Invariant suite job uses Python 3.11 and the exact command; entrypoint nodes for missing, empty, unmarked, zero-match, and complete-deselection cases are listed in sections F–G. Main push run 33250521376 invariant job 99095290077: 28 passed. | Repository CI entrypoint and synthetic fail-closed subprocess evidence only. | PASS |
| 17 | Retain the complete default CPU job and repository no-new-debt quality gate without regenerating `.ci/quality-baseline.json`. | .github/workflows/ci.yml retains CPU tests and Code quality; baseline blob is unchanged; run 33250521376 CPU job 99095290170 and quality job 99095290146 succeeded. | CPU regression and repository quality ratchet only. | PASS |
| 18 | Pass the dedicated invariant lane, the ten supporting owner suites, the full CPU suite, the quality ratchet, `git diff --check`, and the exact repository-governance audit on the same final head. | Pre-edit exact-baseline validation: 28 invariant, identical unfiltered 28, 2052 owner, 2310 full CPU, quality ratchet, diff check, and governance audits passed. Exact final closeout-head validation remains a mandatory pre-commit/PR gate and is not preclaimed here. | Engineering regression and repository-governance evidence only. | PASS |
| 19 | If an invariant exposes an owner implementation defect, preserve the failure and stop A12 closeout until a separate owner repair is reviewed and merged; do not weaken, skip, xfail, deselect, catch, or bypass it. | No owner defect was exposed. tests/invariants/test_a12_crosswalk.py::test_a12_suite_has_no_unmapped_or_greenwashing_tests plus the real-guard cases in section G prevent the named bypass paths from producing green. | Process guard; no claim that future defects cannot occur. | PASS |
| 20 | If an invariant requires a new scientific, security, protocol, or economic decision, stop and request the smallest named owner decision; do not invent a value or future type. | Exact row-contract and ceiling audit required no new owner decision; R6, R8, and R12 explicitly stop below unresolved security/science decisions. | Governance result for this exact audit only. | PASS |
| 21 | Record exact command/results and the twelve-row evidence crosswalk in `.agent/WAVE_A_REPORT.md` only during separately authorized A12 implementation/closeout. | This separately authorized closeout report records the canonical command, exact row table, infrastructure inventory, guard matrix, owner regression, CPU, and quality evidence. | Documentation of evidence; not implementation or merge authority. | PASS |
| 22 | Update `.agent/WAVE.md` only after the exact implementation head passes review, explicit human authorization, and normal merge; do not mark A12 done from contract-ratification evidence. | The reviewed implementation head 33b4626a1ffe7d0c65336336a870a8f4a73ab92f merged normally in PR #51 as 2a8b273a1167588efb4a11159da5224264d5b37a. The closeout branch labels done as proposed until its own separate authority gate is met. | Administrative sequencing proof only. | PASS |
| 23 | Preserve `SCIENTIFICALLY_QUALIFIED`, `SECURITY_QUALIFIED`, `NETWORK_QUALIFIED`, `COMMERCIALLY_VALIDATED`, and `PRODUCTION_QUALIFIED` as `NO` unless separately earned. | Section K and every changed status record preserve all five states as NO. No qualifying artifact or approval is introduced. | No qualification is earned. | PASS |
| 24 | Leave Wave B inactive. Do not alter its board, contract, handoff, activation hashes/gates, or begin B-01. | Wave B protected blobs are unchanged; section M records inactive; no board, contract, handoff, hash, approval, activation record, or B-01 work is in the manifest. | Non-activation and absence proof only. | PASS |

**Ticket audit denominator:** 12 invariant-row criteria + 6 dedicated-suite
and CI criteria + 6 failure/closeout-governance criteria = **24 PASS / 0
FAIL**.

## E. Exact A12-R1 through A12-R12 evidence crosswalk

The machine crosswalk is exactly ordered A12-R1 through A12-R12, and every
contract is text-equal to Design_Specs/Build_Out.md section 2. Dedicated nodes
are unique, owner nodes resolve canonically below tests/cpu, and proof kinds
and ceilings are machine-locked.

| Row and title | Dedicated test node | Proof kind | Supporting owner evidence | Exact bounded evidence ceiling | Result |
|---|---|---|---|---|---|
| A12-R1 — No seed leakage | tests/invariants/test_a12_invariants.py::test_a12_r01_no_seed_leakage_across_public_surfaces | behavioral+structural-negative | tests/cpu/test_no_leakage.py::test_public_projection_omits_all_private_and_reconstruction_fields<br>tests/cpu/test_card_store.py::test_public_projection_is_allow_listed_and_has_no_private_graph<br>tests/cpu/test_mcp_skeleton.py::test_poll_covers_every_state_and_reads_card_only_when_published<br>tests/cpu/test_leaderboard.py::test_cursor_and_public_representations_contain_no_hidden_material<br>tests/cpu/test_observability.py::test_forbidden_material_has_no_positive_construction_path | Synthetic in-process projection evidence only; no deployed transport, adaptive leakage, security, or production qualification. | PASS |
| A12-R2 — Practice isolation | tests/invariants/test_a12_invariants.py::test_a12_r02_practice_isolation_is_fail_closed | behavioral+structural-negative | tests/cpu/test_seeding.py::test_every_context_type_crossing_rejects_for_every_entry_point<br>tests/cpu/test_mcp_skeleton.py::test_alias_deferred_and_unknown_tools_are_unavailable_without_capture<br>tests/cpu/test_traineval_stub.py::test_source_import_graph_and_calls_exclude_forbidden_owners | No nominal practice execution backend exists; mock, fixture, scaffold, and estimate boundaries do not prove practice quality or security. | PASS |
| A12-R3 — Pinned evaluation | tests/invariants/test_a12_invariants.py::test_a12_r03_scored_fixture_evaluation_is_exactly_pinned | behavioral | tests/cpu/test_registry.py::test_matching_digest_is_computed_from_actual_file_bytes<br>tests/cpu/test_seeding.py::test_every_pinned_identity_field_changes_seed_and_commitment<br>tests/cpu/test_scoring_engine.py::test_score_input_pin_mismatch_rejects_before_gate_evaluation<br>tests/cpu/test_submission_fsm.py::test_queue_admission_is_atomic_no_fee_and_pins_exact_binding<br>tests/cpu/test_traineval_stub.py::test_service_preflight_rejects_profile_pack_and_environment_mismatch | Exact fixture identity and pin enforcement only; no production backend, container enforcement, LIVE, science, or security qualification. | PASS |
| A12-R4 — Disclosure allow-list | tests/invariants/test_a12_invariants.py::test_a12_r04_miner_disclosure_uses_positive_allow_lists | behavioral+structural-negative | tests/cpu/test_scoring_engine.py::test_public_scoring_surface_is_small_and_keeps_evidence_types_private<br>tests/cpu/test_card_store.py::test_public_projection_is_allow_listed_and_has_no_private_graph<br>tests/cpu/test_mcp_skeleton.py::test_poll_covers_every_state_and_reads_card_only_when_published<br>tests/cpu/test_leaderboard.py::test_public_allowlist_has_no_identity_time_diagnostics_or_economics<br>tests/cpu/test_observability.py::test_every_valid_event_request_maps_to_one_exact_fresh_snapshot | Bounded in-process disclosure types only; no transport, authentication, network, gateway, or production security claim. | PASS |
| A12-R5 — LIVE requires qualification | tests/invariants/test_a12_invariants.py::test_a12_r05_live_requires_complete_exact_qualification | behavioral | tests/cpu/test_registry.py::test_each_required_slot_missing_blocks<br>tests/cpu/test_registry.py::test_wrong_or_stale_manifest_identity_blocks<br>tests/cpu/test_registry.py::test_successful_activation_and_later_artifact_mutation_fail_closed | Structural exact-version gate evidence only; scientific acceptance, signature verification, signer identity, and key custody remain human-owned. | PASS |
| A12-R6 — Execution isolation | tests/invariants/test_a12_invariants.py::test_a12_r06_production_execution_remains_unavailable_without_sandbox | structural-negative | tests/cpu/test_submission_fsm.py::test_positive_production_gate_still_fails_closed_without_later_seams<br>tests/cpu/test_traineval_stub.py::test_strategy_and_independent_strategy_hash_are_never_observed<br>tests/cpu/test_traineval_stub.py::test_no_ambient_hash_time_random_filesystem_network_or_environment_dependency<br>tests/cpu/test_traineval_stub.py::test_source_import_graph_and_calls_exclude_forbidden_owners | Negative fail-closed absence proof only; no sandbox, workload isolation, SECURITY_QUALIFIED, or PRODUCTION_QUALIFIED claim. | PASS |
| A12-R7 — Infra ≠ science | tests/invariants/test_a12_invariants.py::test_a12_r07_infrastructure_cannot_be_scored_as_science | behavioral | tests/cpu/test_scoring_engine.py::test_partial_or_infra_shaped_input_never_becomes_a_failed_gate<br>tests/cpu/test_submission_fsm.py::test_mandatory_gate_failure_is_completed_science_not_infrastructure<br>tests/cpu/test_submission_fsm.py::test_noncompletion_a5_status_is_operational_retry_then_terminal_refund<br>tests/cpu/test_traineval_stub.py::test_every_infrastructure_cause_maps_by_retry_class_to_exact_a7_operation | Typed fixture-only infrastructure classification, retry/refund, and FAILED_INFRA separation only; named real infrastructure failures and production operations are not integration-tested here. | PASS |
| A12-R8 — Determinism | tests/invariants/test_a12_invariants.py::test_a12_r08_pinned_fixture_reexecution_is_exactly_reproducible | behavioral | tests/cpu/test_seeding.py::test_deterministic_fixture_provider_reproduces_seed_and_commitment<br>tests/cpu/test_scoring_engine.py::test_repeated_scoring_is_exactly_deterministic<br>tests/cpu/test_traineval_stub.py::test_independent_oracle_and_literal_golden_vectors | Exact pinned-fixture reproducibility only; A12 chooses no scientific tolerance and claims no production reproducibility. | PASS |
| A12-R9 — No placeholder LIVE | tests/invariants/test_a12_invariants.py::test_a12_r09_fixture_values_cannot_gain_live_or_emission_authority | behavioral+structural-negative | tests/cpu/test_registry.py::test_fixture_origin_blocks_production_after_status_and_mode_relabelling<br>tests/cpu/test_registry.py::test_placeholder_challenge_version_blocks_production<br>tests/cpu/test_traineval_stub.py::test_completed_outcome_maps_to_a7_publication_and_a6_false_emission<br>tests/cpu/test_leaderboard.py::test_forged_ineligible_provider_candidate_rejects_whole_snapshot | Fixture and placeholder rejection only; no frontier, product, receipt, treasury, settlement, chain, weight, or emission types are created. | PASS |
| A12-R10 — No silent rescore | tests/invariants/test_a12_invariants.py::test_a12_r10_new_pack_cannot_silently_overwrite_history | behavioral | tests/cpu/test_scoring_engine.py::test_any_source_byte_perturbation_changes_pack_identity<br>tests/cpu/test_card_store.py::test_every_material_valid_result_difference_conflicts_without_overwrite | Bounded process-local insert-only history only; no production-qualified durable store or migration policy. | PASS |
| A12-R11 — Forbidden score inputs | tests/invariants/test_a12_invariants.py::test_a12_r11_named_forbidden_signals_cannot_enter_scoring | behavioral | tests/cpu/test_scoring_engine.py::test_forbidden_or_downstream_input_keys_cannot_construct_score_input<br>tests/cpu/test_submission_fsm.py::test_fee_values_cannot_enter_a5_models_or_scoring_signature | Closed fixture A5 input boundary and fee separation only; no Yuma or production-weight implementation. | PASS |
| A12-R12 — Practice is useful without revealing the realized exam | tests/invariants/test_a12_invariants.py::test_a12_r12_practice_is_incomplete_and_has_no_official_authority | structural-negative | tests/cpu/test_mcp_skeleton.py::test_alias_deferred_and_unknown_tools_are_unavailable_without_capture<br>tests/cpu/test_mcp_skeleton.py::test_valid_estimate_calls_provider_once_with_owned_strategy<br>tests/cpu/test_mcp_skeleton.py::test_source_dependency_and_owner_call_guards | Declared-incomplete, non-executing absence proof only; no usefulness, leakage, shadow-case, scientific-adequacy, score, lifecycle, or scheduling claim. | PASS |

**Semantic denominator:** exactly 12 contracts, 12 unique dedicated row proofs,
and 12 PASS. A11 positive-construction redaction supports R1/R4 and is not a
thirteenth invariant.

## F. Exact sixteen-test infrastructure inventory

The infrastructure denominator is exactly 16 unique marked tests: four
crosswalk/anti-greenwashing proofs and twelve entrypoint controls.

| # | Exact infrastructure node | Function | Result |
|---:|---|---|---|
| 1 | tests/invariants/test_a12_crosswalk.py::test_a12_crosswalk_has_exact_order_and_authority | Locks authority, order, contracts, proof kinds, ceilings, and inventory. | PASS |
| 2 | tests/invariants/test_a12_crosswalk.py::test_a12_crosswalk_resolves_all_dedicated_and_owner_nodes | Resolves all dedicated and owner nodes under canonical roots. | PASS |
| 3 | tests/invariants/test_a12_crosswalk.py::test_a12_suite_has_no_unmapped_or_greenwashing_tests | Requires complete mapping and rejects prohibited greenwashing paths. | PASS |
| 4 | tests/invariants/test_a12_crosswalk.py::test_a12_crosswalk_canonical_containment_rejects_aliases | Rejects parent traversal, symlink escape, and noncanonical node aliases. | PASS |
| 5 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_accepts_marked_passing_test | Positive marked-pass control. | PASS |
| 6 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_propagates_marked_failure | Ordinary assertion failure remains nonzero. | PASS |
| 7 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_target_is_missing | Missing target cannot green. | PASS |
| 8 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_target_is_empty | Empty target cannot green. | PASS |
| 9 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_only_tests_are_unmarked | Unmarked-only target cannot green. | PASS |
| 10 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_zero_marker_matches | Zero marker matches cannot green. | PASS |
| 11 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_fails_when_collection_is_completely_deselected | Complete deselection cannot green. | PASS |
| 12 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_partial_deselection | The committed guard rejects partial deselection. | PASS |
| 13 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_runtime_skip | The committed guard rejects runtime skip. | PASS |
| 14 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_expected_xfail | The committed guard rejects expected xfail. | PASS |
| 15 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_non_strict_xpass | The committed guard rejects non-strict xpass. | PASS |
| 16 | tests/invariants/test_a12_entrypoint.py::test_invariant_entrypoint_real_guard_fails_collection_time_module_skip | The committed guard rejects collection-time module skip. | PASS |

Together, section E's 12 unique row proofs and these 16 unique infrastructure
tests equal the canonical lane's exact 28-test denominator. No node is
unmapped and the two sets are disjoint.

## G. Exact twelve-case fail-closed entrypoint matrix

Every case invokes the canonical argument shape in an isolated synthetic
repository. The five real-guard cases copy the committed
tests/invariants/conftest.py bytes.

| # | Synthetic case | Expected exact observation | Guard ruling | Result |
|---:|---|---|---|---|
| 1 | One marked passing test | Exit 0; 1 passed | Required positive control greens. | PASS |
| 2 | One marked failing test | Exit 1; 1 failed | Ordinary failure propagates. | PASS |
| 3 | tests/invariants target missing | Exit 4; file or directory not found | Missing suite fails. | PASS |
| 4 | tests/invariants target empty | Exit 5; no tests ran | Empty suite fails. | PASS |
| 5 | Target contains only an unmarked test | Exit 5; 1 deselected | Unmarked-only suite fails. | PASS |
| 6 | Target contains only a differently marked test | Exit 5; 1 deselected | Zero invariant matches fail. | PASS |
| 7 | Collection hook removes the complete marked set | Exit 5; 1 deselected | Complete deselection fails. | PASS |
| 8 | Committed guard sees one marked pass plus one deselected unmarked test | Exit 1; 1 passed, 1 deselected | Partial deselection fails. | PASS |
| 9 | Committed guard sees runtime skip | Exit 1; 1 skipped | Runtime skip fails. | PASS |
| 10 | Committed guard sees expected xfail | Exit 1; 1 xfailed | Expected xfail fails. | PASS |
| 11 | Committed guard sees non-strict xpass | Exit 1; 1 xpassed | Non-strict xpass fails. | PASS |
| 12 | Committed guard sees collection-time module skip | Exit 1; 1 skipped | Collection-time skip fails. | PASS |

The canonical suite also contains no skip, skipif, xfail, deselection,
exception-swallowing, imported-owner-test, private-state-manufacture, or
weakened-proof path.

## H. Build_Out section 12 Wave A acceptance: 9 PASS / 0 FAIL

The Design_Specs/Build_Out.md checkboxes remain untouched because that file is
sequencing specification authority. This table records current-main evidence
for the exact nine bullets.

| # | Exact Wave A acceptance criterion | Current-main source evidence | Exact test evidence | Result |
|---:|---|---|---|---|
| 1 | CI green on schema, seed/mock guards, and scoring engine unit tests. | carbon/schema/strategy.py::dry_validate; public derivation boundaries in carbon/seeding/derive.py; carbon/scoring/engine.py::ScoreEngine. | tests/cpu/test_no_leakage.py::test_private_seed_remains_inert_a2_strategy_json<br>tests/cpu/test_seeding.py::test_every_context_type_crossing_rejects_for_every_entry_point<br>tests/cpu/test_scoring_engine.py::test_fixture_golden_scoring_result_is_exact_binary64<br>Push CI run 33250521376 succeeded. | PASS |
| 2 | Registry blocks LIVE without a qualification manifest. | carbon/registry/gate.py::ChallengeRegistry. | tests/cpu/test_registry.py::test_each_required_slot_missing_blocks<br>tests/cpu/test_registry.py::test_wrong_or_stale_manifest_identity_blocks<br>tests/cpu/test_registry.py::test_successful_activation_and_later_artifact_mutation_fail_closed | PASS |
| 3 | Exact seven A9 tools respond; aliases and deferred light/list tools reject. | carbon/mcp/model.py::McpTool; carbon/mcp/service.py::McpService.call. | tests/cpu/test_mcp_skeleton.py::test_exact_exports_enums_and_public_layout<br>tests/cpu/test_mcp_skeleton.py::test_alias_deferred_and_unknown_tools_are_unavailable_without_capture | PASS |
| 4 | A9 dry_validate delegates to A2 and estimate remains non-executing/structural only. | carbon/mcp/service.py::McpService. | tests/cpu/test_mcp_skeleton.py::test_dry_validate_delegates_once_and_reconstructs<br>tests/cpu/test_mcp_skeleton.py::test_valid_estimate_calls_provider_once_with_owned_strategy<br>tests/cpu/test_mcp_skeleton.py::test_source_dependency_and_owner_call_guards | PASS |
| 5 | A9 submit returns exact A7 lifecycle status; fee≠score and duplicate-open idempotence tested. | carbon/mcp/service.py::McpService and the A7 submission service. | tests/cpu/test_mcp_skeleton.py::test_submit_preserves_a7_rejected_received_and_duplicate_behavior<br>tests/cpu/test_submission_fsm.py::test_open_duplicate_after_validation_queue_run_and_score_returns_same_id<br>tests/cpu/test_submission_fsm.py::test_fee_values_cannot_enter_a5_models_or_scoring_signature | PASS |
| 6 | Result polling consumes query budget before A7 lookup and returns an exact A6 card only for PUBLISHED. | carbon/mcp/service.py::McpService. | tests/cpu/test_mcp_skeleton.py::test_poll_gate_precedes_lookup_and_requires_exact_none<br>tests/cpu/test_mcp_skeleton.py::test_poll_covers_every_state_and_reads_card_only_when_published | PASS |
| 7 | Card store: budgeted read allow-list tested; unauthorized hotkey denied. | carbon/cards/store.py::CardStore.read_budgeted. | tests/cpu/test_card_store.py::test_public_projection_is_allow_listed_and_has_no_private_graph<br>tests/cpu/test_card_store.py::test_authorization_denial_occurs_before_public_projection | PASS |
| 8 | Fixture-official TrainEvalAPI stub only; cannot mark emission-ready. | carbon/traineval/stub.py::FixtureStubBackend; carbon/traineval/service.py::FixtureTrainEvalService. | tests/cpu/test_traineval_stub.py::test_exact_closed_models_profile_policy_and_capability<br>tests/cpu/test_traineval_stub.py::test_completed_outcome_maps_to_a7_publication_and_a6_false_emission<br>tests/cpu/test_traineval_stub.py::test_source_import_graph_and_calls_exclude_forbidden_owners | PASS |
| 9 | Leakage tests for EvaluationCard/leaderboard fields. | Public projection, card, and leaderboard owner surfaces. | tests/cpu/test_no_leakage.py::test_public_projection_and_serializer_have_exact_allow_list<br>tests/cpu/test_card_store.py::test_public_projection_is_allow_listed_and_has_no_private_graph<br>tests/cpu/test_leaderboard.py::test_public_allowlist_has_no_identity_time_diagnostics_or_economics<br>tests/cpu/test_leaderboard.py::test_cursor_and_public_representations_contain_no_hidden_material | PASS |

**Acceptance denominator:** exactly **9 PASS / 0 FAIL**. These results prove
the recorded bounded Wave A owner behaviors, not any later qualification.

## I. Wave A board closeout

The ancestry audit resolves every cited evidence commit as an ancestor of
current main 2a8b273a1167588efb4a11159da5224264d5b37a. Earlier rows remain
bounded by their existing records; this report does not widen them.

| Row | Current-main status | Exact retained merged evidence | Ancestral to audit baseline | Candidate result |
|---|---|---|---|---|
| A-1 | done | Orientation closeout ab765b07bc8c41106194ce6d06b4a2bd1c03f9a1; audited snapshot 0eed4e92609b4f26bd095a90f8cba9b7376fbe09 | PASS | done, existing bounded orientation scope |
| A0 | done | 0b2eec30250f1767cc434836e189cca219154d4d | PASS | done, existing bounded package scope |
| A1 | done | Implementation merge 819da3c163c2fb9476a6881aab8740cc6984066e; closeout e696cc43ace96a963f00bb28394da03d35eb267e | PASS | done, existing bounded CI scope |
| A2 | done | Implementation merge bfc0b97e1b16625141de3950428bc2fdf69f42ea; closeout e6fb20b1dc361ded442fcf41d118cea5f2c775cd | PASS | done, existing bounded schema scope |
| A3 | done | Implementation merge 69b938d1c4fd0aca58276940d15df50b1b68e5d1; closeout c5f2dfbda64e4375e3d3f26f7a463ca98cabd07a | PASS | done, existing bounded registry scope |
| A4 | done | Implementation merge 120eab02e406bda280d9c361bbbb7d8ef7a08330; closeout 3d80e09549964251833b0d8a70093cfceb51a501 | PASS | done, existing bounded seeding/leakage scope |
| A5 | done | Implementation merge 6f813e979ef6edde2b8f1821d1ac26f62938633a; closeout dfd9bcc74434d2ddb5fc1862a9bdfd7ba5c64450 | PASS | done, existing bounded fixture-scoring scope |
| A6 | done | Implementation merge 5c7c3a924d305a386ed92d6f054981761d5c74b7; closeout ba0b2b3dffd114d02fd5f6a71af08052a3e0a1ed | PASS | done, existing bounded process-local card scope |
| A7 | done | Implementation merge 5b7b38a4db3b0a7bbf2d97ae872a28a3d885d77d; closeout 6a3fe0f8e34602af5a4eaeaa8ae145d967537724 | PASS | done, existing bounded process-local lifecycle/fee scope |
| A8 | done | Ratification 872be272fe80df19c28611388fc4e1ebcd7b4900; implementation d0011e959622b65f6ae737db7477062104bafa33; corrective repair b30c3f5fc2a53df0611d5e8b80120fbf4b64531c; closeout adcf0578052bba2c0cf9aa24e7a07ebfe87ca46d | PASS | done, fixture-official non-production/non-emission stub only |
| A9 | done | Ratification 47a62b2397b4125bb608eb69bf0e3dc6360c519d; implementation 97d835f495cb7e3f194364cb4e674e2416531936; corrective repair 0099a198bf19845390a0a12825eac0eeef06ffd2; closeout f308281e69580216d5ebf5ec94a9d6c069cf1a56 | PASS | done, exact seven-tool in-process skeleton only |
| A10 | done | Implementation merge 3b2d96e287f06c24cc4d57b46dfc418359a9e97f; closeout 404c039596b487cf2649bb1d73b80e9b49baaced | PASS | done, bounded fixture/process-local leaderboard only |
| A11 | done | Ratification 4e4a66d29566a2a62a82188adddac76e6e0fb8b8; implementation merge e2496e92eeae31befdaa430501bb9f00b0e6339e; closeout 37074e9f0663d36ce1f7655aaedfc7ad4fb6a3c1 | PASS | done, bounded in-process observability only |
| A12 | todo pending administrative closeout | Ratification merge 746e56e42c412bc8ba2eeb4d85ed83396e1a084c; implementation merge 2a8b273a1167588efb4a11159da5224264d5b37a; 24/24 ticket, 12/12 rows, 28/28 lane, 9/9 acceptance | PASS | proposed done, bounded invariant-judge/CI scope only |

The candidate board denominator is therefore:

- **14 done**
- **0 todo**
- **0 in_progress**
- **0 blocked**

That 14/14 result becomes repository authority only after exact-head
independent review, explicit human authorization, and normal merge of the
closeout pull request. Before that merge, current main still records A12 todo
and Wave A incomplete.

## J. Local and GitHub validation evidence

### J.1 Pre-edit local validation on the exact audit baseline

These runs occurred after creating agent/a12-closeout at exact baseline
2a8b273a1167588efb4a11159da5224264d5b37a and before editing. Durations are
therefore explicitly labeled **PRE-EDIT** and are not misrepresented as
closeout-head results.

| Gate | Exact command / scope | Actual result |
|---|---|---|
| Canonical invariant lane | python -m pytest tests/invariants -m invariant -q | **PRE-EDIT:** 28 passed in 3.98s |
| Unfiltered invariant collection | python -m pytest tests/invariants -q | **PRE-EDIT:** the identical 28 nodes; 28 passed in 3.96s; zero deselected, skipped, xfailed, or xpassed |
| Exact supporting-owner regression | tests/cpu/test_no_leakage.py, test_seeding.py, test_registry.py, test_scoring_engine.py, test_card_store.py, test_submission_fsm.py, test_traineval_stub.py, test_mcp_skeleton.py, test_leaderboard.py, and test_observability.py | **PRE-EDIT:** 2052 passed in 35.62s |
| Full default CPU suite | python -m pytest -q | **PRE-EDIT:** 2310 passed in 36.10s |
| Repository quality ratchet | scripts/check_quality.py against base 2a8b273a1167588efb4a11159da5224264d5b37a and .ci/quality-baseline.json | **PRE-EDIT:** PASS; Ruff 757 checked / 776 baseline; Black 62 checked / 68 baseline; removed debt Ruff 19 / Black 6; zero changed Python files; no new debt |
| Whitespace | git diff --check | **PRE-EDIT:** PASS |
| Audit denominators | exact ticket, crosswalk, guard, acceptance, board, manifest, and protected-blob audits | **PRE-EDIT:** 24/24, 12/12, 16/16, 12/12, 9/9, and existing-evidence ancestry PASS; no defect or owner-decision condition |

The exact final closeout head must separately pass the canonical and unfiltered
invariant lanes, the 2052 supporting-owner regression, the 2310 default CPU
suite, the quality ratchet, git diff --check, status/report consistency,
manifest, protected-blob, topology, and remote-head checks before it is pushed.
This report does not invent those future results.

### J.2 Exact GitHub evidence already on main

| Run / job | Exact head | Actual result |
|---|---|---|
| PR #51 final-head run 33248924648 | 33b4626a1ffe7d0c65336336a870a8f4a73ab92f | completed / success |
| Invariant job 99091100116 | same reviewed head | 28 passed |
| CPU job 99091100201 | same reviewed head | 2310 passed |
| Code-quality job 99091100193 | same reviewed head | success; no new debt |
| Greptile job 99091103640 | same reviewed head | 5/5; no blocking failure |
| Post-merge push run 33250521376 | 2a8b273a1167588efb4a11159da5224264d5b37a | completed / success |
| Invariant job 99095290077 | same current-main head | 28 passed in 4.22s |
| CPU job 99095290170 | same current-main head | 2310 passed in 59.52s |
| Code-quality job 99095290146 | same current-main head | Ruff 757/776; Black 62/68; removed debt Ruff 19 / Black 6; five changed Python files clean; no new debt |

The draft closeout pull request's exact-head GitHub run and its three jobs are
a later no-drift gate. They must be reported in the pull-request evidence and
final task record; they cannot be preclaimed in this candidate report.

## K. Maturity matrix

| Authority dimension | Current main before closeout merge | Candidate branch | State after exact reviewed, authorized normal merge |
|---|---|---|---|
| A12 SPECIFIED / RATIFIED | YES | YES, unchanged | YES |
| A12 IMPLEMENTED | YES, bounded invariant-judge/CI scope | YES, unchanged; no implementation edit | YES, bounded invariant-judge/CI scope |
| A12 TESTED | YES, bounded engineering evidence | YES, unchanged; closeout validation adds repository evidence only | YES, bounded engineering evidence |
| A12 SCIENTIFICALLY_QUALIFIED | NO | NO | NO |
| A12 SECURITY_QUALIFIED | NO | NO | NO |
| A12 NETWORK_QUALIFIED | NO | NO | NO |
| A12 COMMERCIALLY_VALIDATED | NO | NO | NO |
| A12 PRODUCTION_QUALIFIED | NO | NO | NO |
| A12 WAVE STATUS | todo | proposed done | done |
| Wave A | incomplete pending administrative closeout | proposed closed in bounded engineering scope | closed in bounded engineering scope |
| Wave B | inactive | inactive | inactive |

Neither implemented nor tested means scientifically, security, network,
commercially, or production qualified. The closeout does not change that
interpretation.

## L. Explicit unearned capabilities and remaining risks

This closeout earns none of the following:

- a sandbox or enforced production workload isolation for miner-supplied code;
- production compute, network, filesystem, or wall-clock enforcement;
- a selected scientific determinism tolerance or production reproducibility;
- practice usefulness, a leakage threshold, evaluator-held shadow-case
  adequacy, or leakage/scientific qualification;
- a nominal practice/research execution backend;
- a real production TrainEvalAPI backend or container enforcement;
- deployed transport, authentication, network, gateway, or production
  security;
- scientific acceptance of a qualification manifest, cryptographic signature
  verification, signer identity, or key custody;
- integration proof for real OOM policy kills, node death, queue loss, or
  production retry/refund operations;
- a production-qualified durable historical store or migration policy;
- Yuma weights, production weights, emission eligibility, settlement,
  treasury, chain, receipt, product, or frontier authority;
- LIVE, launch, or publication authority.

The remaining risks are deliberately held at their named owner boundaries.
Future changes can still regress owner behavior, so the canonical A12 lane
must continue to fail closed and any newly exposed implementation defect or
owner-decision requirement must stop the relevant acceptance path. These
qualification and future-system gaps are not unresolved Wave A administrative
closeout conditions.

## M. Wave B non-activation ruling

Wave B is inactive before, during, and after this closeout. Closing Wave A does
not automatically activate Wave B, does not authorize B-01, and does not make
.agent/WAVE_B.md the active controlling register.

This candidate does not:

- alter .agent/WAVE_B.md, .agent/WAVE_B_CODEX_HANDOFF.md, or
  Design_Specs/Miner_MCP_Wave_B_Research_Contract.md;
- alter a Wave B ticket, board, contract, handoff, evidence record, or
  activation gate;
- record named protocol, science, security, rights, or technical owner
  approval;
- compute or record activation SHA-256 hashes;
- create an activation or activation-closeout decision;
- begin, simulate, or partially perform B-01 or any other Wave B work.

Separate Wave B activation prerequisites remain unsatisfied: independent
review of the Wave B contract set; named owner-role approval; exact repository
hash recording for the reviewed board, contract, and handoff; a separately
reviewed prospective activation change naming Wave B and its controlling
register without mutating the reviewed artifacts; and the later post-merge
activation closeout required before B-01. This report merely preserves those
boundaries and does not fulfil them.

## N. Final bounded closure ruling

Against exact unmodified main 2a8b273a1167588efb4a11159da5224264d5b37a:

- the A12 ticket audit is **24 PASS / 0 FAIL**;
- the semantic invariant audit is **12 PASS / 0 FAIL** in exact A12-R1 through
  A12-R12 order;
- the lane denominator is exactly **12 unique dedicated + 16 unique
  infrastructure = 28 marked tests**;
- the fail-closed entrypoint matrix is **12 PASS / 0 FAIL**;
- the Build_Out section 12 Wave A acceptance audit is **9 PASS / 0 FAIL**;
- every retained A-1 and A0–A11 board evidence commit is ancestral to current
  main;
- A12's merged and post-merge evidence passes, yielding the candidate board
  result **14 done / 0 todo / 0 in_progress / 0 blocked**;
- no owner implementation defect and no new owner decision was found.

The proposed final ruling is:

> A12 is done only in the bounded invariant-judge/CI scope, and Wave A is
> closed only as a bounded engineering process milestone.

This ruling becomes authoritative only after the exact closeout head passes
all final local and GitHub no-drift gates, is independently reviewed, receives
explicit human authorization, and is normally merged. It does not become
authoritative from this branch or its draft pull request.

After that exact reviewed, authorized normal merge, **no unresolved Wave A
closeout condition remains**. All scientific, security, network, commercial,
production, LIVE, launch, frontier, and emission claims remain unearned, and
Wave B remains inactive.
