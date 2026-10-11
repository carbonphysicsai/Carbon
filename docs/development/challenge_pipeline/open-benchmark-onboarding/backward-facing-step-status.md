backward-facing-step: UNDETERMINED_WITHOUT_VERIFIED_EXIT_EVIDENCE
Reports source-backed draft/gap/snapshot progress. No stage exit is adjudicated from file presence; independent stage acceptance remains with #970 owners.

S0_brief Brief: ARTIFACTS_PRESENT_EXIT_NOT_VERIFIED (1/1 artifacts read)
  Owner: Owner picks; Codex researches
  docs/development/challenge_pipeline/open-benchmark-onboarding/backward-facing-step-brief.json: READ
  Still required: A one-page brief naming the buyer role, the decision and the value at stake, with sources or labelled assumptions.
S1_packet Design packet: ARTIFACTS_PRESENT_EXIT_NOT_VERIFIED (1/1 artifacts read)
  Owner: Codex drafts; Test Lead reviews
  docs/development/challenge_pipeline/open-benchmark-onboarding/backward-facing-step-packet.md: READ
  Still required: The ten sections of COMMON_DESIGN_PACKET_V1 filled with source-linked facts; every value without an owner decision or evidence is OPEN with owner, needed decision and held-closed behavior.
S2_solver_package Solver package: NO_PERMITTED_EVIDENCE_TO_VERIFY_EXIT (0/0 artifacts read)
  Owner: Data Collection builds and measures
  Still required: A pinned reference package with an accepted image and manifest identity, measured per-case cost and memory, and conservation checks within packet tolerances.
S3_feasibility_value_panel Feasibility and value panel: ARTIFACTS_PRESENT_EXIT_NOT_VERIFIED (1/1 artifacts read)
  Owner: Codex packets the value case; Data Collection measures; Test Lead judges; owner sets final thresholds
  docs/development/challenge_pipeline/open-benchmark-onboarding/backward-facing-step-panel.json: READ
    buyer_decision.status: HUMAN_INPUT
    strata_basis.status: HUMAN_INPUT
    boundary_designs.status: HUMAN_INPUT
  Still required: Value criteria V1-V5, validity criteria T1-T5 and cost criteria C1 onward evidenced for the Challenge, with a keep, reframe or replace decision recorded.
S4_question_law Question law: ARTIFACTS_PRESENT_EXIT_NOT_VERIFIED (1/1 artifacts read)
  Owner: Codex proposes; owner accepts
  docs/development/challenge_pipeline/open-benchmark-onboarding/backward-facing-step-law.json: READ
    P.status: HUMAN_INPUT
    Q.status: HUMAN_INPUT
    w.status: HUMAN_INPUT
    action_set.status: HUMAN_INPUT
    question.status: HUMAN_INPUT
    question.buyer_decision.status: HUMAN_INPUT
    k.status: HUMAN_INPUT
    NONE_FEASIBLE.status: HUMAN_INPUT
    bank.status: HUMAN_INPUT
    startup_cost.status: HUMAN_INPUT
  Still required: A non-runtime law sheet (population, action lattice, strata, near rule) whose HUMAN_INPUT values the owner has accepted or declined; the four-check design-value prerequisite met before any new hidden bank.
S5_bank Bank: NO_PERMITTED_EVIDENCE_TO_VERIFY_EXIT (0/0 artifacts read)
  Owner: Carbon Validator (producer, bank adapters, VALIDATOR-28 family sources); Data Collection supplies each family's reference package and panel; the owner approves startup spend
  Still required: A sealed hidden bank prepared on the hidden host from a pinned validator image, never on a host every agent session can read.
S6_readiness Readiness gate: NO_PERMITTED_EVIDENCE_TO_VERIFY_EXIT (0/0 artifacts read)
  Owner: Graphite Testing Manager runs; Test Lead reviews and waives
  Still required: launch_ready true at that exact SHA: no FAIL, NOT_BUILT or REVIEW_REQUIRED; waivers are stage-bound and measurement-only; reports committed through PR Head.
S7_stage_a Graphite stage A (L0 and L1): NO_PERMITTED_EVIDENCE_TO_VERIFY_EXIT (0/0 artifacts read)
  Owner: Executor runs; Launchpad lanes; Test Engineer bindings; Test Lead decides
  Still required: The checklist runs complete with a lessons entry, evidence digest and spend count per run; L0 confirmations through the Launchpad; refused-capability extracts collected; stage report to the Test Lead.
S8_stage_b Graphite stage B (L2 and L3 on the dev-ladder): NO_PERMITTED_EVIDENCE_TO_VERIFY_EXIT (0/0 artifacts read)
  Owner: Executor runs; Carbon Validator owns VALIDATOR-25; owner approves spend
  Still required: Per the stage B plan: runs complete with lessons entries and a stage summary.
S9_stage_c Graphite stage C (L4, graph only): NO_PERMITTED_EVIDENCE_TO_VERIFY_EXIT (0/0 artifacts read)
  Owner: Executor runs; Level 4 engineer owns the rebuild path; owner approves spend
  Still required: Per the wave plan section 4a: the stage C Constructor and Attacker runs complete with lessons entries.
S10_tested Tested Challenge: NO_PERMITTED_EVIDENCE_TO_VERIFY_EXIT (0/0 artifacts read)
  Owner: Test Lead
  Still required: TESTED when ALL hold: (1) the readiness gate is launch_ready at every enabled level (no FAIL; waivers expired or closed); (2) a sealed hidden bank exists, with exposure accounting; (3) Graphite stages are complete at every enabled level, with real Launchpad confirmations scored by a validator, and every Attacker finding dispositioned (fixed, or accepted with a reason); (4) score-value alignment is measured on confirmed recipes (a Q1 report exists), and a negative result is allowed but must trigger a scoring iteration; (5) control detection (T3) meets its target at the chosen k and E; (6) the incentive canary shows the best model weighted (INCENTIVE-CANARY-01); (7) the stage-end report is filed; (8) the cheap-baseline comparison (V4) is done: the models' decisions are compared, at matched admissibility, with the strongest cheap method a buyer would otherwise use; (9) the Challenge PASSES VALUE: (a) a real buyer decision with at least two sources; (b) on held-out contested questions the best Carbon model's buyer-unit regret is lower than the strongest cheap baseline's at matched admissibility, paired bootstrap 95% interval excluding 0; (c) at least 100x faster than the reference per decision query; (d) sourced or assumption ranges for value and volume; (e) at an equal time and compute budget, a model-screen-then-solver-verify workflow finds a better design than the solver alone (readiness D2 equal-cost harness).
