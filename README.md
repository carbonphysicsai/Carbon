<img width="1412" height="62" alt="image" src="https://github.com/user-attachments/assets/1d63753c-a391-44d9-a4b8-ee667545bcae" />

# Carbon

**Discovery + evidence infrastructure for fast physical models**

Carbon is an incentivized experimental system for discovering, independently testing, learning from, and qualifying methods for constructing fast physical models.

Public shorthand:

> **Carbon pays people and agents to find better ways to build fast physics models, then independently tests what survives.**

Company shorthand:

> **Carbon is building the discovery, evidence, and qualification infrastructure for fast physical models.**

P0 starts deliberately narrower: bounded neural-operator training-strategy search, validator-controlled fresh retraining, and protected scientific evaluation. The broader architecture does **not** imply that arbitrary model families or arbitrary participant code are enabled today.

## Development Hub

New contributors can start with the [Carbon Development Hub](docs/development/carbon_hub/index.html), a static-first map of what Carbon is building, why the Wave A-N sequence exists, where the current Wave B/B-03 work sits, and how proposed changes route back to repository authority.

- [Start Here](docs/development/carbon_hub/orientation/START_HERE.md) explains waves, tickets, decisions, PRs, evidence, and maturity in plain language.
- [Hub maintenance contract](docs/development/carbon_hub/orientation/AGENT_MAINTENANCE_CONTRACT.md) defines ticket-start placement, update triggers, regeneration, validation, and PR impact reporting.
- [Development environment](docs/DEVELOPMENT.md) remains the canonical setup and execution guide.

The hub owns orientation—what, why, where, status, dependency, and handoff. The repository's constitution, specifications, active board, tickets, decisions, code, review, tests, and evidence remain authoritative for exact semantics and implementation.

---

## The problem

High-fidelity simulation is foundational to engineering, but repeating it thousands of times can be too expensive for design exploration, uncertainty studies, control loops, digital twins, and increasingly agentic engineering workflows.

Fast learned, reduced, hybrid, and other surrogate models can change those economics. But a low average test error does not establish that a model:

- preserves mandatory physical behavior;
- survives difficult regimes;
- reproduces independently;
- remains valid after the model/data/runtime changes;
- supports the engineering job in which somebody wants to use it.

As fast physical models become easier to create, the bottleneck increasingly moves toward **discovery, independent evidence, bounded qualification, and lifecycle credibility**.

---

## The scientific mechanism

Carbon's owner-recommended system architecture is:

```text
DEFINE THE PHYSICS JOB
        ↓
QUALIFY THE EXAM
        ↓
PEOPLE + AGENTS COMPETE
        ↓
VALIDATORS REBUILD + TEST
        ↓
A VERIFIED FRONTIER ADVANCE WINS
        ↓
TREASURY SETTLES THE REWARD
```

Core rule:

> **Carbon qualifies the exam before the exam qualifies a candidate.**

A qualified Challenge separates the physical job, candidate inputs/outputs, operating envelope, target population, finite sampling design, generator, truth/reference path, measurements, Validation Dossier, and Score Pack rather than allowing one implementation to silently own all of those authorities.

The Score Pack is best understood as a versioned **Evidence Use Contract**. It consumes already-qualified evidence and determines eligibility, mandatory scientific admissibility, score-bearing estimands, and Challenge-bound ranking.

> **Admissibility precedes ranking. Mandatory physical/scientific failure cannot be compensated by soft performance.**

The current P0 45/30/25 profile is one narrow scoring implementation, not Carbon's universal definition of `physics > loss`.

---

## From score to frontier reward

A Challenge score and an economic reward are different operations.

Where sampling or reconstruction variance matters, Carbon's intended frontier architecture compares the incumbent and eligible challengers under a common fresh promotion experiment and a registered `LeaderReplacementPolicy`.

```text
qualified candidate evidence
        ↓
Challenge-bound ScoreResult
        ↓
COMMON FRONTIER PROMOTION EXAM
        ↓
SUPERIOR | NOT_SUPERIOR | INDETERMINATE
        ↓
FrontierAdvanceEvent (if superior)
        ↓
separate settlement
```

> **A new leader is an evidence state, not merely a floating-point inequality.**

> **Carbon rewards verified frontier advances, not permanent incumbency.**

Raw scores from different Challenges are not automatically comparable. The intended Phase-0 breadth mechanism is a small frozen portfolio of qualified Challenges with equal notional reward opportunity, while each Challenge keeps its own scientific ruler.

---

## Bittensor's role

Bittensor supplies the open economic substrate and optimizer market. Carbon supplies the scientific objective, independent judge, frontier rule, and evidence-bound settlement semantics.

```text
Carbon:    What counts as a real advance?
Bittensor: Who can find it?
```

Bittensor consensus does not determine physical truth.

A separately governed treasury-neuron architecture is the leading settlement design for decoupling normalized network transport from Carbon's Challenge-specific frontier accounting. That architecture remains subject to localnet/testnet/security qualification before production claims.

---

## P0: prove the judge first

The current launch implementation remains intentionally bounded:

1. miners/agents submit a schema-constrained neural-operator training strategy;
2. validators independently retrain on validator-controlled data;
3. protected evaluation runs mandatory physics/scientific checks plus registered soft objectives;
4. invalid, infrastructure-failed, scientifically inadmissible, indeterminate, and valid-ranked outcomes remain distinct;
5. rich evidence is retained internally while miner/public disclosure is budgeted;
6. winning a competition does **not** make an artifact a qualified engineering product.

The first authoritative Burgers Challenge is being repaired around a narrow fixed-viscosity `u0 -> u(T)` task with independently qualified truth and appropriate final-state physical measurements. Earlier PoC behavior remains historical evidence rather than being retroactively relabeled as qualified science.

---

## What Carbon can become

Carbon standardizes the **job and scientific exam**, not the terminal model ideology.

Its search freedom can widen over time:

```text
parameters
    ↓
recipes / training strategies
    ↓
architectures / model compositions
    ↓
model-construction methods
    ↓
construction algorithms
```

The invariant is producer-independent reconstruction and protected official evaluation. Current neural P0 uses fresh validator retraining; broader reconstruction protocols and heterogeneous model families are later architecture, not current runtime capability.

> **Model class is a hypothesis. Registered external evidence is the judge.**

---

## The business

Carbon's company/business architecture is intentionally separate from the scientific judge.

The locked hybrid model is:

```text
SERVICES
        ↓
ENTERPRISE PLATFORM
        ↓
NETWORK MARKETPLACE
        ↓
QUALIFICATION + LIFECYCLE
        ↓
PHYSICS INTELLIGENCE
```

> **Services get Carbon into the customer. Platform makes the relationship recurring. The network makes discovery scalable. Qualification increases contract value. Lifecycle increases retention. Physics intelligence compounds the moat only if it earns prospective value.**

### Product ladder

```text
LAND
Evidence Audit / Challenge Feasibility / truth integration
        ↓
EXPAND
Sponsored Discovery / Model Development / Qualification / deployment
        ↓
RECUR
Lifecycle / requalification / support / Enterprise Evidence Platform
        ↓
SCALE
API / OEM / Frontier Market / usage / rights-permitted licensing
        ↓
COMPOUND
Physics Intelligence and experiment allocation only after prospective validation
```

The preferred first commercial wedge is **Carbon Evidence Audit**: bring an existing fast physical model and the engineering job it is meant to support; Carbon independently evaluates what survives, where it fails, and what stronger evidence or remediation would be required.

The preferred first network-differentiated product is **Sponsored Discovery**: a sponsor brings an authorable physical-modeling problem; Carbon qualifies the research objective, opens competitive search, independently determines whether the frontier moved, and delivers the resulting evidence/candidate path.

A scientifically negative Audit or a Sponsored Discovery program with no frontier advance can still be a successful commercial delivery if Carbon honestly delivered the contracted evidence program.

---

## Company and network economics

Carbon OpCo and the Carbon subnet are related but distinct economic systems.

```text
CARBON OPCO
enterprise contracts
services / software / licenses / qualification / support
        ↕ explicit reviewed bridges
CARBON NETWORK
miners / validators / frontier rewards / Alpha / treasury
```

The company must be commercially viable without assuming speculative Alpha appreciation. Enterprise customers may buy through conventional fiat procurement.

> **OpCo revenue does not automatically create Alpha value.**

The network earns economic relevance when commercially valuable scientific work genuinely uses miners, validators, sponsor-funded rewards, or network-native services. Direct financial-engineering mechanisms require separate legal/economic/governance review.

---

## Commercial and scientific authority remain separate

Commercial terms may determine:

- which customer problem to pursue;
- privacy/deployment mode;
- rights and licensing;
- deliverables and customer acceptance;
- pricing and payment;
- support/lifecycle terms.

They may **not** lower the evidence required for the same scientific claim, manufacture a frontier winner, or turn a competition result into a product qualification.

> **Rank nominates. Evidence qualifies.**

---

## Current maturity

Carbon distinguishes architecture from evidence.

Scientific maturity should distinguish external premise, Carbon design, implementation, Carbon evidence, replication, and production qualification.

Business maturity should distinguish:

```text
DESIGN
→ CUSTOMER DISCOVERY
→ PAID PILOT
→ REPEATABLE SERVICE
→ EXPANSION
→ RECURRING REVENUE
→ PLATFORMIZATION
→ NETWORK LEVERAGE
```

The business architecture on `main` is owner-canonical strategy. It is **not** itself evidence of paid customers, recurring revenue, validated pricing, proven margins, or product-market fit.

Likewise, owner-recommended integrated scientific architecture may be ahead of current runtime migration. Current runtime specifications and repository code remain authoritative for implemented behavior until intentionally changed.

---

## Repository map

### Business canon and company plan

| Document | Role |
|---|---|
| [Business/README.md](./Business/README.md) | Business authority/read-order map |
| [Business/Business_Canon.md](./Business/Business_Canon.md) | Durable business constitution |
| [Business/Business_Plan.md](./Business/Business_Plan.md) | Integrated company plan |
| [Business/Product_and_Revenue_Architecture.md](./Business/Product_and_Revenue_Architecture.md) | Product ladder and revenue rails |
| [Business/Go_To_Market.md](./Business/Go_To_Market.md) | ICPs, sales motions, GTM |
| [Business/Investor_Positioning_and_Market.md](./Business/Investor_Positioning_and_Market.md) | Category, market and investor positioning |
| [Business/Financial_Engine.md](./Business/Financial_Engine.md) | Financial modeling discipline and unit-economics architecture |
| [Business/Network_and_Alpha_Value.md](./Business/Network_and_Alpha_Value.md) | OpCo/network/Alpha value boundary |
| [Business/Commercial_Operating_Model.md](./Business/Commercial_Operating_Model.md) | Rights, privacy, deliverables and commercial execution |
| [Business/Design_Questions.md](./Business/Design_Questions.md) | Open decisions for business lead |

### Technical/runtime documentation

| Document | Role |
|---|---|
| [SPEC.md](./SPEC.md) | Current protocol/runtime architecture where implemented |
| [Design_Specs/Build_Out.md](./Design_Specs/Build_Out.md) | Current implementation sequencing |
| [Design_Specs/Miner_MCP.md](./Design_Specs/Miner_MCP.md) | Miner/agent interfaces |
| [Design_Specs/Scoring.md](./Design_Specs/Scoring.md) | Current P0 scoring authority |
| [Design_Specs/Generator_Validation.md](./Design_Specs/Generator_Validation.md) | Validation Dossier / exam qualification architecture |
| [Design_Specs/Data_Management.md](./Design_Specs/Data_Management.md) | Official data and role separation |
| [Design_Specs/Trustless_Verification.md](./Design_Specs/Trustless_Verification.md) | Evaluation/seeding trust boundaries |
| [Design_Specs/Specialist_Bank.md](./Design_Specs/Specialist_Bank.md) | Product qualification path |
| [docs/context/SCIENTIFIC_REFERENCE_CANON.md](./docs/context/SCIENTIFIC_REFERENCE_CANON.md) | Scientific reference/evidence map currently on main |
| [docs/context/BUSINESS_REFERENCE_CANON.md](./docs/context/BUSINESS_REFERENCE_CANON.md) | Canonical business companion |

### Publications

| Document | Role |
|---|---|
| [docs/publications/README.md](./docs/publications/README.md) | Publication authority/reconciliation map |
| [docs/publications/PUBLICATION_RECONCILIATION_2026-08-23.md](./docs/publications/PUBLICATION_RECONCILIATION_2026-08-23.md) | Current cross-paper reconciliation record |

---

## Development

```bash
git clone https://github.com/carbonphysicsai/Carbon.git
cd Carbon
# Open the repository in the committed Carbon Dev Container / canonical Ubuntu environment.
./scripts/dev/bootstrap.sh
./scripts/dev/doctor.sh
./scripts/dev/ci.sh
```

[`docs/DEVELOPMENT.md`](./docs/DEVELOPMENT.md) and
[`docs/development/ENVIRONMENT.md`](./docs/development/ENVIRONMENT.md) govern
setup. `./scripts/dev/ci.sh` is the normal pre-PR gate; do not reconstruct an
alternate pip/pytest environment. Optional science and network dependency
groups are non-default and may be enabled only when the active ticket owns
them.

---

*Carbon: define the job, qualify the exam, open the search, keep the producer out of the official grade, and qualify only what the evidence supports.*
