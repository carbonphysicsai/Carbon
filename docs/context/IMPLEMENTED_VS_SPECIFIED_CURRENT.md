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
| A8 | Yes | Yes | Yes | No | Bounded fixture-official, deterministic, process-local TrainEval stub on current `main`, including the reviewed conformance repair; no real/mock/LIVE/production or qualification authority |
| A9 | Yes | Yes | Yes | No | Exact seven-tool bounded in-process Wave-A control/disclosure skeleton; tested only for the recorded engineering scope, with no scientific, security, network, commercial, or production qualification |
| A10 | Pending merge | No | No | No | Documentation-only contract candidate for a bounded in-process fixture leaderboard projection; no official or LIVE board |
| A11 | Yes | No | No | No | observability/redaction pending |
| A12 | Yes | No | No | No | Wave-A invariant closeout pending |

Exact implementation/test evidence remains in `.agent/WAVE.md` and historical ledger.

The bounded A9 implementation provides exactly `get_challenge_info`,
`get_prior`, `get_mock_scaffold`, `dry_validate`, `estimate`, `submit`, and
`get_submission_result` as an in-process Wave-A control/disclosure skeleton.
It provides no transport, authentication, production providers, production
policy, mock/light execution, adaptive loop, end-to-end integration,
qualification, or production authority.

A10 documentation-only contract-ratification candidate maturity:

```text
A10 SPECIFIED / RATIFIED: pending merge of this documentation PR
A10 IMPLEMENTED: NO
A10 TESTED: NO
A10 SCIENTIFICALLY_QUALIFIED: NO
A10 SECURITY_QUALIFIED: NO
A10 NETWORK_QUALIFIED: NO
A10 COMMERCIALLY_VALIDATED: NO
A10 PRODUCTION_QUALIFIED: NO
A10 WAVE STATUS: todo
```

The candidate contract is limited to a bounded, in-process, fixture-only
projection for one exact Challenge. It provides no HTTP, REST, GraphQL, web UI,
HTML, filesystem or network publication, persistence, scheduler, chain access,
or current-time behavior. An absent official publication feed means the
official board is unavailable, not an empty authoritative board. Production
publication feed; official and LIVE publication; public identity and
anonymization; timestamps; official score precision and cadence; frontier
nomination or promotion; `FrontierRecord`; `FrontierAdvanceEvent`; Product
Qualification; commercial rank; settlement; chain; weights; emissions; A11
logging/metrics; and A12 aggregate invariants remain separately deferred.
Production must remain fail closed.

The empty `carbon/leaderboard` package seam is not A10 implementation. The
historical HTML generator and legacy validator, Landscape, score-to-weight, and
emission paths are archaeology, not current A10 authority or evidence. Where
earlier A10 ticket/Build Out shorthand admitted public hotkey or anonymized
identity, timestamps, `get(submission_id)`, or an ambiguous official-or-fixture
board, it was `DOCUMENTATION_LAG`. The candidate does not promote the legacy
artifacts to `IMPLEMENTED` or `TESTED`.

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
| miner MCP research loop | Yes — bounded Wave-A control plane; broader loop remains design | Yes — exact seven-tool bounded in-process control/disclosure skeleton | No | Bounded control plane implemented and tested; transport, authentication, production providers, mock/light execution, adaptive loop, and end-to-end integration remain unimplemented and unqualified |
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

- the full Miner MCP or any A10–A12 implementation is present; A10 contract
  ratification remains pending merge of documentation only;
- A9 has network or production qualification;
- A8 is a real miner-code, mock/light, LIVE, production, scientifically qualified, or security-qualified backend;
- an A8 fixture result creates frontier, Product Qualification, treasury/settlement, leaderboard, weight, chain, or emission authority;
- a qualified LIVE Burgers exam exists;
- frontier/treasury production settlement exists;
- generalized ConstructionProgram execution is production-ready;
- network advantage is empirically proven;
- designed business products are paid traction.

---

# 8. Current one-line status

> **Carbon has an integrated constitutional architecture and a tested bounded A0–A9 software foundation. A9 implements only the exact seven-tool in-process Wave-A control/disclosure skeleton. A10 has a documentation-only, fixture-only contract candidate pending merge and remains `todo`, unimplemented, untested, and unqualified; official/LIVE publication, frontier, Product Qualification, chain, weights, emissions, and production authority remain explicit future work.**
