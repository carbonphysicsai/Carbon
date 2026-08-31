# Ticket B-02B - Candidate assembly, ParameterCatalog, and Strategy compilation

**Wave:** B candidate
**Status:** done
**Depends on:** B-02A, B-07R, A2
**Build Out:** C2/C9 Wave B semantic construction seam
**Master questions:** MQ-005, MQ-008, MQ-015, MQ-024
**Authority:** current A2 contract; `Miner_MCP_Wave_B_Research_Contract.md` §§4-5
**Owner-approved integration:** `Design_Specs/Science_GTM_Wave_Integration_Plan.md` §4; `docs/context/SCIENCE_GTM_OWNER_DECISION_RECORD_2026-08-27.md`

> **Closeout:** PR #64 normally merged exact reviewed implementation head
> `68189e7068715a5d8054f0f7e64dc981ae1c37aa` as
> `b10b6e74fb3f8ab8a7427a6763c7db4f41341083` with exact reviewed/merge tree
> `45273c527684b94afeb2f01b66a774b5426b6e0e`. Exact-head CI `33362051770`,
> Greptile 5/5 on check `99413062552` with zero unresolved threads, and
> exact-main CI `33368352662` passed. This is bounded engineering completion
> only; all scientific, security, production, and LIVE states remain `NO`.

**Merged contract:** `Design_Specs/Candidate_Assembly_and_Strategy_Compiler_Contract.md`<br>
**Plan:** `.agent/plans/B-02B_strategy_compilation.md`<br>
**Evidence:** `.agent/evidence/wave_b/b-02b.md`

## Goal

Turn the ratified inert Strategy v1 envelope into an exact, Challenge-bound construction plan without broadening execution to arbitrary participant code.

## Definition of Done

- [x] Before implementation, produce `Design_Specs/Candidate_Assembly_and_Strategy_Compiler_Contract.md`; record material engineering decisions and applicable domain notifications; pass applicable validation and exact-head CI; repair every valid Greptile finding with zero Greptile threads unresolved; and merge the exact reviewed tree normally. A documented invalid finding may be closed with rationale, and any tree change requires rereview. No affirmative human/domain response or silence gate applies to agent-authorized engineering choices. Real scientific values, security acceptance, rights, economics, qualification, LIVE, launch, and production authority remain separately human-owned and fail closed.
- [x] Define `CandidateAssemblyContract`, `ParameterCatalog`, catalog entries,
      compiler identity, typed compile rejection,
      `ResolvedTrainingSamplingPolicy`, `TrainingSamplingPolicyRef`, and
      `ResolvedConstructionPlan`. `R_strategy` denotes the resolved policy
      object; the ref content-addresses its canonical bytes.
- [x] Bind every executable lever to a stable public `surface_id`, type, unit,
      domain, dependency, compatibility rule, consumer, and policy-agnostic
      static resource dimensions/contributions/impact tags.
- [x] Compile one Strategy to one canonical fully resolved plan or fail closed.
- [x] Reject unknown, unused, incompatible, coerced, silently defaulted, silently clamped, and unsupported parameters.
- [x] Make every permitted default explicit in the plan and plan hash.
- [x] Permit only catalog-registered, Challenge-bounded training sampling,
      curriculum, and augmentation levers. Compile their exact values into
      `R_strategy` / `TrainingSamplingPolicyRef`; bind the Challenge-owned
      training support plus registered abstract training-randomness purposes
      and role-key labels, but no entropy domain or seed material. Each nominal
      execution context selects its authorized entropy domain and derives its
      own draws beneath the same policy semantics.
- [x] Bind exact Strategy, Challenge, catalog, assembly, compiler, dependency, environment, and backbone identities.
- [x] Prove canonical plan identity across two nominal fixture consumers
      representing the later practice and official-shaped roles; B-07F owns
      the fixture-official adapter and B-GATE owns integrated parity proof
      after B-07C and B-07F exist.
- [x] Include one fixture registered hybrid-backbone or learned-component slot without accepting participant-defined graphs or code.
- [x] Define a closed fixture-only compatibility taxonomy for Challenge-owned
      learned-component roles, covering at least warm start, preconditioner
      action, coarse correction, residual correction, subdomain operator, and
      nonlinear initial guess. The ratified contract may narrow or rename the
      exact runtime literals, but it must preserve distinct role semantics and
      reject unknown or role-confused components.
- [x] Bind each learned-component entry to its exact consumer, input/output
      contract, state and side-effect policy, fixed-versus-trainable boundary,
      implementation and environment pins, applicability ref, limitations,
      resource impact, and fallback/acceptance seam where that seam exists.
- [x] Preserve the post-launch decision boundary for the final hybrid product
      qualification object. Wave B defines reconstructible component identity
      and interface compatibility only; component evidence, labels, unit tests,
      or claimed invariants cannot qualify an assembled solver/model system.
- [x] Permit a fixture closed set of versioned structural-component surfaces
      with exact executable semantics, physical-assumption/applicability refs,
      fixed-versus-trainable boundaries, implementation pins, limitations,
      resource impacts, and public falsification refs. Prove that component
      labels and claimed invariants carry construction authority only and
      cannot satisfy gates or enter score.
- [x] Emit exact static resource requirements without deciding policy
      admissibility; B-02C owns policy evaluation and enforcement and cannot
      mutate compiler semantics.
- [x] Add catalog confusion, collision, downgrade, stale-ref,
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
