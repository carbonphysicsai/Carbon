# Physics Intelligence Design Decisions

**Status:** RATIFIED by project owner in chat on 2026-08-19; specification encoded in `Design_Specs/Physics_Intelligence_System.md`.  
**Implementation status:** SPECIFIED only unless separately recorded in code/tests or `IMPLEMENTED_VS_SPECIFIED.md`.

---

## Decision summary

The scientific-reference canon audit materially strengthened Carbon's architecture. The following decisions are ratified as additive design hardening rather than a redesign of the existing subnet, Landscape, or Specialist Bank.

### D1 — Evaluation information is governed

Repeated miner/agent interaction with scores, diagnostics, leaderboards, priors, mocks, and future Landscape outputs is an adaptive information channel. Hidden-evaluation safety therefore includes an explicit, versioned Evaluation Information Policy in addition to direct seed secrecy.

No universal production leakage threshold is ratified. Exact live policy remains human-owned.

### D2 — Challenge validity and evaluation health are distinct

A Challenge may remain scientifically valid while becoming less useful as a protected discriminator after prolonged adaptive interaction. Carbon may monitor evaluation-health signals and prospectively refresh/retire Challenge versions.

No universal exhaustion threshold is ratified. Historical scores are never silently reinterpreted.

### D3 — Failure evidence is retained

Landscape's valuable substrate is the intervention-outcome record, not only winners. Scientifically valid low-ranked runs, gate failures, reproducible strategy failures, Product Battery failures, and later qualification failures may be retained with provenance/evidence-quality metadata.

Infrastructure failures remain excluded from negative scientific evidence.

### D4 — Landscape knowledge is epistemically typed

Landscape must distinguish at minimum:

- `observed`;
- `predictive`;
- `causal_candidate`;
- `experimentally_supported`.

Observational strategy history is not causal merely because an effect is large, stable, useful, or repeated.

### D5 — Performance and information markets remain separate

Subnet score/emissions reward scientific performance under the registered contract. Port C may later propose targeted bounties/experiments for information value, reproduction, discrimination between hypotheses, transfer testing, or underexplored regions.

Information value, novelty, causal confidence, Landscape similarity, and product value remain outside `S_combined` unless Scoring is explicitly changed.

### D6 — Search diversity is monitored, not casually rewarded

Strategy/population diversity may be useful for Challenge-health analysis and Port C experiment design. Novelty is not ratified as an official score input.

### D7 — Reproducibility is a property of the method

Independent retraining measures whether strategy advantage survives transfer of execution authority. Carbon should preserve environment, pin, resource, and repeat-dispersion evidence where registered protocols collect it.

No repeat-count or variance threshold is ratified here.

### D8 — Qualification is a lifecycle

Commercial specialist status evolves through qualification, deployment, observation/escalation, reassessment, and requalification/restriction/retirement as appropriate. Historical Qualification Records remain immutable evidence of the original claim.

Authorized lifecycle/escalation evidence may inform future qualification and research, but customer data is never assumed available.

### D9 — The intervention-outcome graph is a core compounding asset

Carbon's long-term data advantage is a provenance-rich record linking strategy interventions, physical regimes, execution, protected stress outcomes, reproducibility, Product Battery outcomes, and optional authorized lifecycle evidence.

This graph is not automatically causal and remains private by default.

---

## Ratified invariants

> **Landscape proposes. Registered contracts decide. Independent experiments adjudicate.**

> **Do not collapse performance, novelty, information value, causal confidence, and commercial value into one score.**

> **Physics remains the external authority that no Landscape, market, agent, or product layer can vote away.**

---

## KEEP / WRAP / REPAIR / REPLACE disposition

The audit did **not** justify replacing Carbon's existing architecture.

- **KEEP:** hard physics gates; weighted-geometric score; hidden official realization; mock/official isolation; four Landscape ports; causal-estimate caution; Product Battery separation; fresh product retraining; anti-checkpoint-laundering; immutable versioned scientific contracts.
- **WRAP:** existing feedback-budget and disclosure concepts inside a broader Evaluation Information Policy.
- **REPAIR/EXTEND:** Challenge lifecycle with evaluation-health semantics; Landscape epistemic typing; failure retention; Port C information-value proposals; qualification lifecycle evidence.
- **REPLACE:** none ratified by this review.

---

## Sequencing

These decisions do not reorder the current P0 Wave A-D plan. P0 may add compatible provenance/schema hooks without implementing full Landscape or product lifecycle behavior. Full causal, Port C information-market, and qualification-lifecycle systems remain post-P0 unless Build Out is explicitly revised.

Implementation tickets must read `Design_Specs/Physics_Intelligence_System.md` together with the relevant semantic owner and must not invent scientific/economic thresholds.
