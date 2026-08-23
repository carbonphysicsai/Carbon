# Carbon — Current Implemented vs Specified Ledger

**Status:** OWNER-CANONICAL maturity ledger after 2026-08-23 constitutional reconciliation.  
**Purpose:** provide a concise current-state map that separates architecture, implementation, testing, qualification, and commercial maturity.  
**Relationship to `Implemented_vs_Specified`:** the older ledger remains detailed historical evidence. This file is the current concise status reference.

---

# 1. Status vocabulary

```text
SPECIFIED
architecture/contract is defined

IMPLEMENTED
code materially implements the bounded contract

TESTED
recorded tests establish the bounded engineering behavior

SCIENTIFICALLY_QUALIFIED
human/scientific evidence supports the intended scientific claim

SECURITY_QUALIFIED
dedicated security review/qualification supports the intended threat model

NETWORK_QUALIFIED
network/testnet/settlement path is qualified for its intended economic role

COMMERCIALLY_VALIDATED
real customer evidence supports the product/business claim

PRODUCTION_QUALIFIED
all required scientific/security/operational/economic gates for production use are complete
```

No state implies a later state.

---

# 2. Wave-A ticket maturity

| Ticket | Specified | Implemented | Tested | Production-qualified | Current statement |
|---|---:|---:|---:|---:|---|
| A-1 | Yes | Yes | N/A | N/A | Orientation/audit complete historically |
| A0 | Yes | Yes | Yes | No | Package/layout bounded foundation |
| A1 | Yes | Yes | Yes | No | CI/default CPU evidence infrastructure |
| A2 | Yes | Yes | Yes | No | P0 `TrainingStrategy` schema + dry validation |
| A3 | Yes | Yes | Yes | No | Challenge registry + exact qualification/hash gate |
| A4 | Yes | Yes | Yes | No | Seed/context/domain separation + leakage boundary |
| A5 | Yes | Yes | Yes | No | Fixture-capable ScoreEngine + synthetic Score Pack only |
| A6 | Yes | Yes | Yes | No | Bounded internal store + allow-listed public projection |
| A7 | Yes | Yes | Yes | No | Bounded process-local submission/FSM/fee mechanics |
| A8 | Yes/documented | **No** | **No** | No | Next implementation ticket; fixture TrainEval seam |
| A9 | Yes | No | No | No | MCP integration pending |
| A10 | Yes | No | No | No | public leaderboard pending |
| A11 | Yes | No | No | No | observability/redaction pending |
| A12 | Yes | No | No | No | Wave-A invariant closeout pending |

Exact implementation/test evidence remains in `.agent/WAVE.md` and historical ledger.

---

# 3. Scientific-system maturity

| Capability | Specified | Implemented | Scientifically qualified | Current status |
|---|---:|---:|---:|---|
| qualified task/population architecture | Yes | partial/skeleton | No | integrated constitution + future Wave B/D work |
| `PhysicalSystemSpec` binding | Yes | partial | No | architectural support; not universal runtime completion |
| `InstanceDistributionContract` / `SamplingPlan` | Yes | No canonical full runtime | No | required in future authoring migration |
| qualified generator | Yes | prototype/legacy pieces | No | requires Dossier/conformance evidence |
| Challenge-specific `ReferencePolicy` | Yes | partial/adapters | No | no universal truth backend |
| `MeasurementContract` | Yes | partial/design | No | future first-class runtime binding |
| Score Pack Evidence Use Contract | Yes target | A5 bounded current form | No LIVE pack | migration must preserve A5 engine boundary |
| producer-independent reconstruction | Yes | partial/legacy fresh retraining | No | real Wave C qualification pending |
| one qualified LIVE Challenge | Yes target | No | No | not yet earned |
| Burgers repaired authoritative Challenge | Yes direction | No production path | No | fixed-ν/Cole–Hopf direction only |

---

# 4. Frontier / economic maturity

| Capability | Specified | Implemented | Network-qualified | Current status |
|---|---:|---:|---:|---|
| ordinary Challenge score/rank | Yes | bounded A5/A6 path | No | current implementation foundation |
| `FrontierRecord` / baseline | Yes | No canonical production path | No | future Wave H |
| common frontier-promotion exam | Yes | No | No | future Wave H |
| `FrontierAdvanceEvent` | Yes | No | No | future Wave H |
| frozen `ChallengeSetEpoch` portfolio | Yes | No | No | future Wave H |
| `SettlementObligation` | Yes | No | No | future Wave I |
| treasury-neuron settlement | candidate architecture | No | No | localnet/testnet qualification required |
| sponsor-funded event-bound rewards | Yes business/design | No production path | No | future commercial/network integration |

---

# 5. Agentic architecture maturity

| Capability | Specified | Implemented | Qualified | Current status |
|---|---:|---:|---:|---|
| bounded `TrainingStrategy` search | Yes | A2 schema; real search runtime incomplete | No | P0 foundation |
| miner MCP research loop | Yes | partial/pending A9 | No | Wave A pending |
| Landscape evidence memory | Yes | no canonical production system | No | Wave E |
| model-family-neutral reconstruction | Yes direction | No | No | Wave J |
| `ModelConstructionStrategy` | Yes ontology | No | No | future Wave K |
| `ConstructionProgram` | Yes future ontology | No | No | future Wave K/L |
| generalized `ReconstructionProtocol` | Yes direction | No | No | future Wave L |
| isolated construction worker | Yes architecture | No | No | future Wave L |
| prospective Physics Intelligence | Yes research/product direction | No validated system | No | Wave N; must prove lift |

---

# 6. Product/business maturity

| Product/capability | Designed | Commercially validated | Current status |
|---|---:|---:|---|
| Evidence Audit | Yes | No recorded paid validation in repo | preferred first SKU |
| Challenge Feasibility | Yes | No | designed |
| Sponsored Discovery | Yes | No | network-differentiated target product |
| Model Development | Yes | No | designed |
| Qualified Model Program | Yes | No | depends on product qualification runtime |
| Lifecycle / Requalification | Yes | No | designed recurring layer |
| Enterprise Evidence Platform | Yes | No | later platformization |
| API/OEM | Yes | No | later distribution rail |
| Frontier Market | Yes | No | later network-marketplace layer |
| Physics Intelligence commercial product | Yes concept | No | forbidden to market as proven until prospective lift exists |

Business architecture is canonical; business traction remains to be earned.

---

# 7. Publication maturity

The public narrative is reconciled to the integrated constitution and Business Canon, but publication descriptions must preserve the maturity boundaries above.

No paper/deck may imply:

- A8–A12 are implemented;
- a qualified LIVE Burgers exam exists;
- frontier/treasury production settlement exists;
- generalized ConstructionProgram execution is production-ready;
- network advantage is empirically proven;
- designed business products are paid traction.

---

# 8. Current one-line status

> **Carbon has an integrated constitutional architecture and a tested bounded A0–A7 software foundation. A8–A12 and the qualified scientific, frontier, treasury, generalized-agentic, and commercial-validation layers remain explicit future work.**
