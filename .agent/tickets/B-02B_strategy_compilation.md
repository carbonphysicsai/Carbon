# Ticket B-02B - Candidate assembly, ParameterCatalog, and Strategy compilation

**Wave:** B candidate
**Status:** todo
**Depends on:** B-02A, B-07R, A2
**Build Out:** C2/C9 Wave B semantic construction seam
**Master questions:** MQ-005, MQ-008, MQ-015, MQ-024
**Authority:** current A2 contract; `Miner_MCP_Wave_B_Research_Contract.md` §§4-5

## Goal

Turn the ratified inert Strategy v1 envelope into an exact, Challenge-bound construction plan without broadening execution to arbitrary participant code.

## Definition of Done

- [ ] Before implementation, produce `Design_Specs/Candidate_Assembly_and_Strategy_Compiler_Contract.md`, obtain independent protocol/SciML/security review and explicit human ratification, and merge that contract normally; record the exact contract commit in the implementation plan.
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
      ignored-parameter, hostile-value, static-resource-metadata, and
      installed-wheel tests.

## Human input

SciML, protocol, and security approve allowed backbones, hybrid assembly,
structural components and their physical applicability, parameter
domains/units, training support, and policy family. B-02C owners approve
resource policy and operational rails. Fixtures remain non-authoritative.

## Must not

Accept imports, source, executables, arbitrary dependencies, paths or URIs,
network, deserialization, raw/custom datasets, miner seeds, official `P`, `Q`,
`w`, evaluation/stress/reference/gate/scorer controls, or unregistered
composition. Do not decide resource-policy admissibility inside the compiler.
A registered `R_strategy` is a training policy, not an evaluator control.
