# Ticket B-02B - Candidate assembly, ParameterCatalog, and Strategy compilation

**Wave:** B candidate
**Status:** in_progress
**Depends on:** B-02A, B-07R, A2
**Build Out:** C2/C9 Wave B semantic construction seam
**Master questions:** MQ-005, MQ-008, MQ-015, MQ-024
**Authority:** current A2 contract; `Miner_MCP_Wave_B_Research_Contract.md` §§4-5
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

> **Current-ticket state:** B-07R's exact completion predicate passed on PR
> #62 and exact-main CI. B-02B is selected `in_progress` in its dedicated
> working-contract worktree. Runtime implementation begins only after the exact
> reviewed contract normally merges and exact-main CI passes, in a separate
> dedicated implementation worktree.

**Working contract:** `Design_Specs/Candidate_Assembly_and_Strategy_Compiler_Contract.md`<br>
**Plan:** `.agent/plans/B-02B_strategy_compilation.md`<br>
**Evidence:** `.agent/evidence/wave_b/b-02b.md`

## Goal

Turn the ratified inert Strategy v1 envelope into an exact, Challenge-bound construction plan without broadening execution to arbitrary participant code.

## Definition of Done

- [ ] Before implementation, produce `Design_Specs/Candidate_Assembly_and_Strategy_Compiler_Contract.md`; record material engineering decisions and applicable domain notifications; pass applicable validation and exact-head CI; repair every valid Greptile finding with zero Greptile threads unresolved; and merge the exact reviewed tree normally. A documented invalid finding may be closed with rationale, and any tree change requires rereview. No affirmative human/domain response or silence gate applies to agent-authorized engineering choices. Real scientific values, security acceptance, rights, economics, qualification, LIVE, launch, and production authority remain separately human-owned and fail closed.
- [ ] Define `CandidateAssemblyContract`, `ParameterCatalog`, catalog entries,
      compiler identity, typed compile rejection,
      `ResolvedTrainingSamplingPolicy`, `TrainingSamplingPolicyRef`, and
      `ResolvedConstructionPlan`. `R_strategy` denotes the resolved policy
      object; the ref content-addresses its canonical bytes.
- [ ] Bind every executable lever to a stable public `surface_id`, type, unit,
      domain, dependency, compatibility rule, consumer, and policy-agnostic
      static resource dimensions/contributions/impact tags.
- [ ] Compile one Strategy to one canonical fully resolved plan or fail closed.
- [ ] Reject unknown, unused, incompatible, coerced, silently defaulted, silently clamped, and unsupported parameters.
- [ ] Make every permitted default explicit in the plan and plan hash.
- [ ] Permit only catalog-registered, Challenge-bounded training sampling,
      curriculum, and augmentation levers. Compile their exact values into
      `R_strategy` / `TrainingSamplingPolicyRef`; bind the Challenge-owned
      training support plus registered abstract training-randomness purposes
      and role-key labels, but no entropy domain or seed material. Each nominal
      execution context selects its authorized entropy domain and derives its
      own draws beneath the same policy semantics.
- [ ] Bind exact Strategy, Challenge, catalog, assembly, compiler, dependency, environment, and backbone identities.
- [ ] Prove canonical plan identity across two nominal fixture consumers
      representing the later practice and official-shaped roles; B-07F owns
      the fixture-official adapter and B-GATE owns integrated parity proof
      after B-07C and B-07F exist.
- [ ] Include one fixture registered hybrid-backbone or learned-component slot without accepting participant-defined graphs or code.
- [ ] Define a closed fixture-only compatibility taxonomy for Challenge-owned
      learned-component roles, covering at least warm start, preconditioner
      action, coarse correction, residual correction, subdomain operator, and
      nonlinear initial guess. The ratified contract may narrow or rename the
      exact runtime literals, but it must preserve distinct role semantics and
      reject unknown or role-confused components.
- [ ] Bind each learned-component entry to its exact consumer, input/output
      contract, state and side-effect policy, fixed-versus-trainable boundary,
      implementation and environment pins, applicability ref, limitations,
      resource impact, and fallback/acceptance seam where that seam exists.
- [ ] Preserve the post-launch decision boundary for the final hybrid product
      qualification object. Wave B defines reconstructible component identity
      and interface compatibility only; component evidence, labels, unit tests,
      or claimed invariants cannot qualify an assembled solver/model system.
- [ ] Permit a fixture closed set of versioned structural-component surfaces
      with exact executable semantics, physical-assumption/applicability refs,
      fixed-versus-trainable boundaries, implementation pins, limitations,
      resource impacts, and public falsification refs. Prove that component
      labels and claimed invariants carry construction authority only and
      cannot satisfy gates or enter score.
- [ ] Emit exact static resource requirements without deciding policy
      admissibility; B-02C owns policy evaluation and enforcement and cannot
      mutate compiler semantics.
- [ ] Add catalog confusion, collision, downgrade, stale-ref,
      ignored-parameter, hostile-value, static-resource-metadata,
      learned-component-role-confusion, component-to-gate-bypass,
      arbitrary-graph rejection, and installed-wheel tests.

## Human input

SciML, protocol, and security owners supply or approve the real allowed
backbones, hybrid assembly, structural components and their physical
applicability, parameter domains/units, training support, and policy family.
Until then, affected real capabilities remain unavailable while bounded fixture
contract engineering may continue under delegated governance. B-02C owners
supply resource policy and operational rails. Fixtures remain
non-authoritative. The exact product/system qualification identity for hybrid
systems remains a post-launch owner decision.

## Must not

Accept imports, source, executables, arbitrary dependencies, paths or URIs,
network, deserialization, raw/custom datasets, miner seeds, official `P`, `Q`,
`w`, evaluation/stress/reference/gate/scorer controls, or unregistered
composition. Do not decide resource-policy admissibility inside the compiler.
A registered `R_strategy` is a training policy, not an evaluator control. Do
not treat a learned component as a qualified assembled engineering system.
