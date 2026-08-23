# Carbon Constitutional Authority Map

**Status:** OWNER-CANONICAL repository constitution on `main`.  
**Purpose:** provide one unambiguous authority and maturity map across Carbon's scientific design, implemented protocol, agentic development plan, business architecture, network economics, and publications.  
**Rule:** this document resolves *which layer owns which decision*. It does not silently promote unimplemented architecture to implemented status.

---

# 1. Carbon identity

> **Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.**

Public shorthand:

> **Carbon pays people and agents to find better ways to build fast physics models, then independently tests what survives.**

Business identity:

> **Carbon is building the discovery, evidence, and qualification infrastructure for fast physical models.**

The first bounded implementation searches neural-operator `TrainingStrategy` objects. The long-term scientific object is broader: `ModelConstructionStrategy` / future `ConstructionProgram` producing a `FastPhysicalModel` or physical-decision system under a registered reconstruction and evaluation contract.

---

# 2. Constitutional authority planes

Carbon has separate authorities. No plane may silently absorb another.

```text
SCIENTIFIC CONSTITUTION
what evidence and scientific claims are allowed to mean
        ↓
NORMATIVE PROTOCOL / DOMAIN SPECS
what implemented protocol semantics must do
        ↓
BUILD / AGENTIC DEVELOPMENT PLAN
what gets built, in what order, at what maturity
        ↓
IMPLEMENTATION + TEST EVIDENCE
what actually exists and has been tested

BUSINESS CONSTITUTION
what the company may sell, price, contract, finance, and claim commercially
        ↓
COMMERCIAL OPERATING SYSTEM
how engagements, rights, privacy, delivery, and GTM work

PUBLICATIONS
explain the above; never become authority over them
```

---

# 3. Scientific authority

## 3.1 Current integrated scientific canon

Canonical integrated scientific constitution:

- `docs/context/SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`

The older:

- `docs/context/SCIENTIFIC_REFERENCE_CANON.md`

is retained as a **bibliographic/evidence annex from an earlier generation**, not the final integrated constitutional authority where its architectural framing conflicts with v4.

Core scientific laws include:

1. The producer never controls the official grade.
2. The exam is committed before protected instances become knowable.
3. No individual validator is a trusted scientific authority.
4. Scientific thresholds are qualified, versioned protocol inputs, not runtime opinions.
5. **Admissibility precedes ranking.** Mandatory scientific failure cannot be compensated by soft performance.
6. Mock practice is useful but intentionally cannot reproduce the official exam.
7. The scientific task owns the target population; the generator implements a qualified realization.
8. `P(x)`, `Q(x)`, and `w(x)` are separate semantics.
9. **The exam must be qualified before it may qualify candidates.**
10. Measurement definition, measurement qualification, and measurement use are separate authorities.
11. A Score Pack is an Evidence Use Contract; the engine executes registered decisions and does not invent them.
12. Challenge scores are non-comparable across Challenges by default.
13. A new leader is an evidence state, not a floating-point inequality.
14. Frontier promotion uses scientifically comparable/common fresh evidence where required.
15. Carbon rewards verified frontier advances, not permanent incumbency.
16. Scientific winner determination and economic settlement are separate authorities.
17. Treasury cannot create, erase, or alter a scientific frontier event.
18. Construction and official evaluation are separate security domains.
19. Construction-method producers do not define official measurements proving their own success.
20. Agent autonomy expands hypothesis generation, not scientific authority.
21. Physical representation does not certify physics.
22. Product qualification is bounded to an exact artifact/system, context, evidence identity, and limitations.
23. Component qualification does not automatically compose into system qualification.
24. Physics Intelligence must earn value prospectively; retrospective pattern mining alone is not authority.
25. **Canon informs hypotheses. Carbon experiments adjudicate them.**

---

# 4. Normative protocol authority

Current implemented/runtime semantics remain domain-owned by the present `main` specifications until a migration explicitly changes them.

Primary owners include:

- `SPEC.md` — system/runtime doctrine;
- `Design_Specs/Scoring.md` — current scoring semantics;
- `Design_Specs/Data_Management.md` + `Design_Specs/Trustless_Verification.md` — current seed/data authority;
- `Design_Specs/Generator_Creation.md` + `Design_Specs/Generator_Validation.md` — generator and exam qualification;
- `Design_Specs/Miner_MCP.md` — miner-facing contract;
- `Design_Specs/Launch_Bar.md` — readiness/stop-ship;
- `Design_Specs/Build_Out.md` — current sequencing authority;
- `.agent/` — current ticket/status evidence.

Where current runtime documents lag the integrated scientific constitution, agents must use:

- `Design_Specs/Build_Out_Constitutional_Overlay.md`

as the migration guard. The overlay **does not authorize a speculative implementation**; it identifies seams that must be preserved or explicitly migrated.

---

# 5. Implementation maturity

At the time of this constitutional reconciliation:

```text
A-1  done
A0   done
A1   done
A2   done
A3   done
A4   done
A5   done
A6   done
A7   done
A8   not implemented
A9   not implemented
A10  not implemented
A11  not implemented
A12  not implemented
```

A0–A7 are real implementation/test accomplishments in their recorded bounded scopes. They are **not** declarations of production scientific qualification.

A8 remains the next Wave-A implementation seam. No documentation change may relabel it as implemented before code, tests, review, merge, and board evidence exist.

---

# 6. A0–A7 compatibility ruling

A0–A7 are constitutionally retained.

The reconciliation finding is:

> **No A0–A7 component must be discarded merely because the integrated architecture broadened. Their current contracts are bounded P0 foundations that future layers must wrap, extend, or migrate explicitly.**

Required interpretation:

- A0 package layout remains valid infrastructure.
- A1 CI remains valid evidence infrastructure.
- A2 `TrainingStrategy` is the P0 subtype of the broader future construction-strategy family.
- A3 Challenge identity/qualification binding remains required; future population/truth/measurement identities extend rather than bypass it.
- A4 seed/domain separation remains required and does not by itself establish semantic decontamination.
- A5 scoring remains the current bounded engine; future Score Pack migration must preserve `admissibility -> ranking`, evidence eligibility, and no economic-policy invention inside the engine.
- A6 internal/public disclosure separation remains required and becomes more important for private/customer/auditor projections.
- A7 submission/FSM/infra-vs-science separation remains required; future frontier and treasury states are downstream and must not be collapsed into A7 scientific scoring.

---

# 7. Agentic development authority

Canonical end-to-end development plan:

- `Design_Specs/Agentic_Development_Master_Plan.md`

It spans:

```text
A0–A12
→ Waves B–D: qualified single-Challenge execution
→ Wave E: Landscape / evidence memory
→ Wave F: product qualification / specialist systems
→ Wave G: commercial/private/sponsored interfaces
→ Wave H: frontier promotion + portfolio
→ Wave I: treasury/network settlement
→ Wave J: model-family neutrality
→ Wave K: agentic construction discovery
→ Wave L: reconstruction protocol / isolated construction workers
→ Wave M: product/system qualification + lifecycle
→ Wave N: prospectively validated Physics Intelligence
```

The alphabet after Wave G is a constitutional planning map, not permission to implement ahead of earlier gates.

---

# 8. Generalized agentic construction doctrine

The long-term search ladder is:

```text
parameters
→ recipes / training strategies
→ architectures / compositions
→ construction methods
→ construction algorithms / ConstructionProgram
```

Stable abstractions:

```text
TrainingStrategy
    is a bounded P0 subtype of
ModelConstructionStrategy

fresh validator retraining
    is the P0 form of
producer-independent ReconstructionProtocol

trained neural operator
    is one subtype of
FastPhysicalModel
```

Hard rule:

> **Carbon can widen what participants are allowed to discover without changing who controls the grade.**

Hard security rule:

> **Construction and official evaluation are separate security domains.**

---

# 9. Business authority

Canonical business authority lives under `Business/`.

Primary documents:

- `Business/Business_Canon.md`
- `Business/Business_Plan.md`
- `Business/Product_and_Revenue_Architecture.md`
- `Business/Commercial_Operating_Model.md`
- `Business/Go_To_Market.md`
- `Business/Investor_Positioning_and_Market.md`
- `Business/Financial_Engine.md`
- `Business/Network_and_Alpha_Value.md`
- `Business/Design_Questions.md`

Business law:

> **Build a real company, not a token-dependent story.**

> **Commercial pressure does not rewrite scientific truth.**

Business may choose customers, products, pricing, rights, privacy, deployment, fundraising, and commercial settlement. It may not change the scientific ruler after results are known.

---

# 10. Company / network separation

```text
CARBON OPCO
enterprise revenue / services / software / licenses / support
        ↕ explicit reviewed bridges
CARBON NETWORK
miners / validators / frontier rewards / Alpha / treasury
```

OpCo revenue does not automatically create Alpha value.

Preferred value path:

> **Create Alpha value by making the subnet economically useful and increasingly necessary to valuable scientific work.**

No buyback, revenue-share, burn, or similar direct financial mechanism is constitutional by default; each requires explicit legal/economic/governance adoption.

---

# 11. Publication authority

Publications explain Carbon and must map claims to maturity.

Canonical publication-control folder:

- `docs/publications/`

Claim ladders:

```text
EXTERNAL PREMISE
!= CARBON DESIGN
!= IMPLEMENTATION
!= CARBON EVIDENCE
!= REPLICATION
!= PRODUCTION QUALIFICATION
```

and:

```text
BUSINESS DESIGN
!= CUSTOMER DISCOVERY
!= PAID PILOT
!= REPEATABLE SERVICE
!= RECURRING REVENUE
!= PLATFORMIZATION
!= NETWORK LEVERAGE
```

A paper, deck, README, or investor narrative never overrides code/spec authority.

---

# 12. Stop-ship reconciliation rule

If an agent, engineer, scientist, business lead, or publication author finds a material conflict between:

- integrated scientific constitution;
- current runtime spec;
- implemented code;
- agentic sequencing;
- business promise;
- public claim;

then the affected work **stops at that boundary** until the conflict is classified as:

```text
NO CONFLICT
DOCUMENTATION LAG
IMPLEMENTATION LAG
MIGRATION REQUIRED
NEW OWNER DECISION REQUIRED
```

Never repair coherence by pretending a future state is already implemented.

---

# 13. Constitutional north star

> **Define the physical job. Qualify the exam. Let people and agents compete. Reconstruct independently. Admit only scientifically valid evidence. Promote only verified frontier advances. Settle rewards without rewriting the science. Productize the evidence without weakening it. Expand agent autonomy only outside the judge.**
