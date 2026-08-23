# Carbon Build Invariants (Agent Must Enforce)

Aligned with `CONSTITUTION.md`, `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`, `Design_Specs/Build_Out.md` v1.4, and `Design_Specs/Build_Out_Constitutional_Overlay.md`. **Never violate.**

## Current enforceable implementation invariants

1. **No seed leakage.** Official seeds, derived seeds, draw IDs, or reversible identifiers never appear in EvaluationCard, leaderboard, MCP outputs, or miner-visible logs.
2. **Mock isolation.** Mock / light execution never accesses official packs, official seeds, or hidden exam data.
3. **Pinned evaluation.** Every scored submission is bound to immutable challenge / generator / Score Pack / backend/environment versions required by the active specification.
4. **Disclosure allow-list.** InternalResult / Model Card fields are never returned on miner-facing or public APIs unless explicitly allow-listed for the disclosure tier.
5. **LIVE requires qualification.** LIVE challenges require complete human qualification artifacts for that exact challenge version; configuration presence alone is not qualification.
6. **Execution isolation.** Untrusted miner-supplied work must execute under the active specification's compute, network, filesystem, process, and wall-clock constraints before production use.
7. **Infra != science.** Infrastructure failures are never scored as scientific/physics failures and never grant scientific success. Preserve explicit retry/refund/FAILED_INFRA semantics.
8. **Determinism / bounded reproducibility.** Re-running identical official evaluation under identical versions, seeds, and limits is deterministic within documented tolerances.
9. **No placeholder LIVE.** Placeholder, fixture, synthetic, stub, or mock values never enter LIVE scientific configuration, production ranking, frontier promotion, or settlement entitlement.
10. **No silent rescore.** Historical evaluation records are never silently reinterpreted under newer packs/contracts; material scientific contract change is prospective/versioned.
11. **Forbidden score inputs.** Prior similarity, `estimate`, `light_*`, mock metrics, exam fee, customer payment, or sponsor size never enter official scientific score unless an explicit future scientific contract lawfully defines a different metric role.
12. **Free path imperfect.** Free/mock/practice signal may be useful but must remain intentionally incomplete relative to the official exam.
13. **A8 fixture execution is not production evidence.** The A8 fixture path, until explicitly qualified otherwise in a later wave, cannot create production score authority, leaderboard entitlement, frontier events, settlement obligations, or product qualification.
14. **A5 does not own frontier or treasury policy.** ScoreEngine executes current registered scoring semantics only; future promotion/portfolio/treasury logic is downstream and separate.
15. **A7 does not own frontier or treasury state.** Submission lifecycle/retry/refund/cancellation must not be expanded into scientific frontier promotion or treasury settlement by convenience.

## Constitutional scientific invariants

16. **The exam must be qualified before it may qualify candidates.** Generator determinism alone is not enough.
17. **The scientific task owns the population.** `P(x)`, sampling/proposal `Q(x)`, and evidence/score weighting `w(x)` remain separate semantics where applicable.
18. **Admissibility precedes ranking.** Mandatory scientific failure cannot be compensated by soft performance.
19. **Measurement definition, qualification, and use are separate authorities.** A representation or governing equation does not automatically certify a measurement.
20. **Reference failure != candidate failure.** Truth/reference infrastructure has its own failure semantics.
21. **Challenge scores are non-comparable by default.** Do not build cross-Challenge normalization as scientific meaning without an explicit qualified policy.
22. **A new leader is an evidence state.** Ordinary score inequality alone does not authorize future frontier promotion when common/fresh comparable evidence is required.
23. **Scientific outcome != economic settlement.** Treasury/network transport cannot create, erase, or alter scientific merit.
24. **Construction and official evaluation are separate security domains.** Future `ModelConstructionStrategy`, `ConstructionProgram`, or arbitrary participant execution never gains grading authority.
25. **Agent autonomy expands hypotheses, not authority.** Landscape, priors, Physics Intelligence, and construction agents may propose; registered contracts and independent experiments decide.
26. **Rank nominates; evidence qualifies.** Competition rank is not automatic Product Qualification.
27. **Component qualification does not automatically compose.** System/router/product claims require their own evidence path.
28. **Physics Intelligence must earn prospective value.** Retrospective correlations are not automatically causal or decision-authoritative.

## Business / publication invariants

29. **Commercial pressure does not rewrite scientific truth.** Customer payment, investor priority, sales urgency, or sponsor reward cannot weaken the registered scientific ruler after outcomes are observed.
30. **OpCo revenue != Alpha value by declaration.** Network value requires an explicit useful-work/economic bridge.
31. **Business architecture != traction.** A designed product, price, margin, network advantage, or revenue scenario is not a commercial actual.
32. **Publications are explanatory only.** Papers, README, decks, and investor materials never override protocol, science, business, or implementation authority.

## Agent implementation notes

- Read `CONSTITUTION.md` before every new ticket/wave.
- Read `Design_Specs/Build_Out_Constitutional_Overlay.md` for A8 onward.
- Prefer tests that fail CI if enforceable invariants break.
- Prefer `HUMAN_INPUT` / `None` / blocked states over guessed scientific or economic decisions.
- Do not implement later-wave abstractions merely because they exist in the Agentic Master Plan.
- Do not use a caller-supplied `emission_capable` Boolean as proof of authority; capability/provenance should be structural where the active design requires it.
