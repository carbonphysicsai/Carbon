# Physics Intelligence Implementation Map

**Status:** planning/context only — does not override `Design_Specs/Build_Out.md` sequencing.  
**Normative design:** `Design_Specs/Physics_Intelligence_System.md`.

---

## Goal

Translate the ratified physics-intelligence hardening into bounded implementation work without broad rewrites or premature post-P0 construction.

The design is intentionally split into **P0-compatible hooks** and **post-P0 systems**.

---

# 1. P0-compatible hooks

These should be incorporated into the existing Wave A/B/C tickets when those tickets are implemented or repaired. They do not require full Landscape.

## PI-A1 — Evaluation/disclosure policy provenance

**Natural owners:** bounded public schema/tier in A6; permanent submission and
evaluation binding in A7; integrated policy-provenance retention in the later
evidence store; A9 MCP + A11 observability.

**Specs:** `Miner_MCP.md`, `Trustless_Verification.md`, `Physics_Intelligence_System.md`.

Add schema/provenance support for a versioned evaluation/disclosure policy identifier so official results can be attributed to the information policy under which they were exposed.

Acceptance direction:

- miner/public outputs remain allow-listed;
- bounded A6 publishes exact `schema_version = "1.0"` and
  `disclosure_tier = "phase0_budgeted"`; richer internal policy provenance
  remains later-evidence-owned rather than widening A6's four-field record;
- changing disclosure granularity is explicit/versioned;
- no seed/draw leakage introduced;
- mock/official isolation unchanged.

**Do not:** invent a production leakage threshold or block P0 on a not-yet-ratified scalar information budget.

## PI-A2 — Failure-retention semantics

**Natural owners:** bounded exact-result retention in A6; permanent submission
and strategy identity/hash binding in A7; provenance-complete strategy/model
evidence retention in the later evidence owner.

**Specs:** `Physics_Intelligence_System.md`, `Build_Out.md` infra-vs-science invariant.

Ensure scientific outcomes are not discarded merely because they fail a gate
or rank poorly. Bounded A6 retains every exact A5 result, including mandatory
gate failures, without implying reward. A7 supplies its permanent submission
and strategy identity/hash binding; the later evidence owner retains the
richer official evidence for later Landscape ingestion.

Acceptance direction:

- `FAILED_INFRA` remains excluded from negative scientific evidence;
- scientific/gate failures can be persisted as evidence objects;
- no emissions reward is implied by retention;
- disclosure to miners remains budgeted separately.

## PI-A3 — Challenge-health observability hooks

**Natural owner:** A11 observability, with Challenge registry linkage from A3.  
**Specs:** `Physics_Intelligence_System.md`.

Record future-compatible metrics/provenance needed to assess evaluation health without implementing automated exhaustion decisions.

Potential telemetry classes:

- score distribution / saturation;
- strategy-family diversity where safely measurable;
- mock/official correlation audit inputs;
- disclosure-policy version;
- Challenge version age / submission volume.

**Do not:** automatically rotate or retire LIVE Challenges in P0.

---

# 2. Post-P0 Landscape implementation

## PI-L0 — Full-distribution evidence ingestion

**Target phase:** Landscape L0.  
**Owner:** `Landscape_Agent.md` implementation.

Extend CardLake/FeatureStore ingestion from winner/frontier-oriented analysis to eligible official evidence across the score distribution, including scientifically meaningful failures.

Required properties:

- provenance quality metadata;
- infra-failure exclusion;
- Challenge/evaluation-policy lineage;
- private-by-default row-level data.

## PI-L1 — Challenge evaluation-health analytics

**Target phase:** Landscape L1.

Implement descriptive health analytics only. Output is `healthy` / review signals for human/governance review, not autonomous mutation of scientific contracts.

No production state-transition thresholds may be invented by coding agents.

## PI-L2 — Epistemic type system

**Target phase:** Landscape L2.

Implement machine-readable knowledge status:

```text
observed
predictive
causal_candidate
experimentally_supported
```

Required controls:

- status stored with evidence object/version;
- rendering/API layer preserves epistemic language;
- no silent upgrade;
- causal-candidate publication retains assumptions/confounder metadata;
- withdrawable/versioned estimates remain possible.

## PI-L3 — Information-value opportunity proposals

**Target phase:** Landscape L3 / Port C.

Create a private opportunity object for proposed discriminating/reproduction/coverage experiments.

Conceptual shape:

```text
InformationExperimentProposal {
  proposal_id,
  question,
  uncertainty_target,
  supporting_evidence_ids,
  proposed_intervention_space,
  expected_information_rationale,
  epistemic_status,
  challenge_family,
  governance_status
}
```

This object proposes research; it does not modify `S_combined`, emissions, or LIVE Challenge thresholds.

## PI-L4 — Registered experimental-support promotion

**Target phase:** after Port C experiment workflow exists.

Permit epistemic promotion to `experimentally_supported` only from registered experiment evidence meeting ratified criteria.

Landscape does not self-certify the promotion criteria.

---

# 3. Product / qualification implementation

## PI-P1 — Qualification lifecycle state machine

**Owner:** Specialist Bank implementation.

Add lifecycle states such as:

```text
candidate
qualified
restricted
requalification_required
retired
```

Historical Qualification Records remain immutable.

## PI-P2 — Reassessment trigger framework

Represent versioned reasons for reassessment without inventing scientific thresholds.

Examples:

- material model/recipe change;
- deployment environment change;
- context-of-use expansion;
- new failure evidence;
- qualification-relevant security/reproducibility issue.

## PI-P3 — Escalation evidence contract

Define optional, privacy-controlled ingestion of escalation outcomes.

Requirements:

- explicit authorization / customer policy;
- provenance;
- no raw customer data assumed available;
- separation between private product evidence and public/miner disclosure;
- evidence may inform future research/qualification but cannot retroactively mutate an old Qualification Record.

---

# 4. Economic invariants for all implementation tickets

1. Official `S_combined` remains governed only by `Scoring.md`.
2. Novelty is not silently added to score.
3. Information value is not silently added to score.
4. Causal confidence is not silently added to score.
5. Product value/PB status is not silently added to subnet score.
6. Port C proposals require authorized governance before economic action.
7. Competition remains possible without buying a commercial product or privileged information feed.

---

# 5. Security/scientific invariants for all implementation tickets

1. No official seed/draw leakage.
2. No mock-to-official privilege crossing.
3. No Landscape mutation of registered scientific contracts.
4. No causal-certainty language from observational evidence.
5. No scientific negative evidence from infrastructure failures.
6. No customer lifecycle telemetry without explicit authorization.
7. No silent historical rescore/requalification.
8. No automatic LIVE/retire transition from agent-invented thresholds.

---

# 6. Suggested execution order

The current Wave A board remains authoritative. When those tickets are reached:

```text
A3 registry       → reserve Challenge-health / policy provenance hooks
A6 card store     → bounded PI-A1 public schema/tier + exact-A5 PI-A2 retention
A9 MCP            → enforce versioned disclosure policy surface
A11 observability → PI-A3
A12 invariants    → regression coverage for the above
```

Then, post-P0:

```text
L0 → PI-L0
L1 → PI-L1
L2 → PI-L2
L3 → PI-L3
L4+ → PI-L4
Specialist waves → PI-P1 → PI-P2 → PI-P3
```

This map deliberately avoids creating parallel implementation architecture. Prefer KEEP → WRAP → REPAIR → REPLACE against the existing components.
