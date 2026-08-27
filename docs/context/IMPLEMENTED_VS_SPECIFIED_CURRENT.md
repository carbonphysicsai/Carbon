# Carbon — Current Implemented vs Specified Ledger

**Status:** OWNER-CANONICAL maturity ledger, current through the merged
A11-R1 through A11-R17 contract and the draft A11-R18 sink-snapshot amendment
candidate on 2026-08-27.
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
| A10 | Yes | Yes | Yes | No | Exact bounded in-process fixture leaderboard; fixture-only, non-official, non-LIVE, and tested only for the recorded engineering scope |
| A11 | A11-R1–A11-R17 ratified; A11-R18 is specified only as a draft documentation candidate pending independent review, explicit human authorization, and normal merge | No | No | No | PR #46 is a blocked, non-authoritative draft implementation candidate; immutable A11-owned sink snapshots remain unimplemented and untested on current main |
| A12 | Yes | No | No | No | Wave-A invariant closeout pending |

Exact implementation/test evidence remains in `.agent/WAVE.md` and historical ledger.

The bounded A9 implementation provides exactly `get_challenge_info`,
`get_prior`, `get_mock_scaffold`, `dry_validate`, `estimate`, `submit`, and
`get_submission_result` as an in-process Wave-A control/disclosure skeleton.
It provides no transport, authentication, production providers, production
policy, mock/light execution, adaptive loop, end-to-end integration,
qualification, or production authority.

A10 current bounded maturity:

```text
A10 SPECIFIED / RATIFIED: YES
A10 IMPLEMENTED: YES on current main only for the exact bounded in-process fixture leaderboard
A10 TESTED: YES only for the exact recorded CPU, hostile-input, resource, concurrency, leakage, dependency, import, wheel, and quality engineering scope, including all reviewed repairs
A10 SCIENTIFICALLY_QUALIFIED: NO
A10 SECURITY_QUALIFIED: NO
A10 NETWORK_QUALIFIED: NO
A10 COMMERCIALLY_VALIDATED: NO
A10 PRODUCTION_QUALIFIED: NO
A10 WAVE STATUS: done in the bounded scope after the documentation closeout merged normally in PR #38 as 404c039596b487cf2649bb1d73b80e9b49baaced
```

A11 current contract and amendment-candidate maturity:

```text
A11-R1 through A11-R17:
RATIFIED

A11-R18:
SPECIFIED as this exact candidate;
RATIFIED only after independent review, explicit human authorization, and
normal merge

A11 IMPLEMENTED:
NO on current main

A11 TESTED:
NO on current main

A11 draft implementation:
PR #46 is blocked by P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS and is not
current repository implementation or test authority.

A11 SCIENTIFICALLY_QUALIFIED: NO
A11 SECURITY_QUALIFIED: NO
A11 NETWORK_QUALIFIED: NO
A11 COMMERCIALLY_VALIDATED: NO
A11 PRODUCTION_QUALIFIED: NO

A11 WAVE STATUS:
todo on current main

A12: todo
Wave A: incomplete
Wave B: candidate planning only; inactive
```

PR #39 normally merged A11-R1 through A11-R17 as current main
`4e4a66d29566a2a62a82188adddac76e6e0fb8b8`; those decisions are ratified.
Draft PR #46 is blocked because its sink seam passes shared canonical A11/A5/A7
enum singletons. `P1_GENERIC_DATACLASS_SERIALIZATION_BYPASS` is repaired on
that draft branch, but `P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS` is
confirmed. The earlier `66 PASS / 0 FAIL` implementation audit is withdrawn.
PR #46 test results are branch evidence only and do not make A11 implemented
or tested on current main.

A11-R18 is the next documentation-only owner decision. It selects an immutable
A11-owned sink-snapshot representation: public service requests continue to
accept exact canonical A11/A5/A7 request values, while future sinks receive
only a fresh `SubmissionEventSnapshot`, `BoundaryErrorSnapshot`,
`CounterMetricSnapshot`, or `DurationMetricSnapshot` composed of exact
built-in `str`, `int`, or `None` fields. The existing request enums and
nominals are validated request values, not sink arguments or sink-safe
snapshots. The future exact public surface contains eighteen names, adding
only those four snapshot types. A11-R18 supersedes only the sink-facing
portions of A11-R1, A11-R2, A11-R3, A11-R10, A11-R13, A11-R14, and A11-R16;
all other A11-R1 through A11-R17 behavior and authority ceilings remain in
force.

This documentation candidate adds no A11 implementation, owner
instrumentation, exporter, test, or scientific, security, network, commercial,
or production qualification evidence. It changes no A5/A7 owner source,
A12 artifact, Wave B artifact, dependency, workflow, or quality baseline.

The exact next-move sequence is:

1. independently review and ratify exact A11-R18;
2. normally merge the exact reviewed amendment only after explicit human
   authorization;
3. synchronize PR #46 with the amendment merge;
4. repair PR #46 to implement the snapshot boundary; and
5. independently review the repaired implementation before ready or merge.

Current `main` implements and tests only a bounded, in-process, fixture-only
projection for one exact Challenge. It provides no production provider or
publication feed; official or LIVE leaderboard; public identity,
authentication, hotkey, anonymization, or timestamp publication; durable
persistence; HTTP, REST, GraphQL, web UI, HTML, filesystem or network
transport; official score precision or cadence; adaptive-query security
qualification; cross-Challenge or global ranking; frontier nomination or
promotion authority; `FrontierRecord`; `FrontierAdvanceEvent`; Product
Qualification; commercial rank; settlement; treasury; chain; Bittensor;
weights; emissions; A11 logging/metrics; or A12 aggregate-invariant work. An
absent official publication feed means the official board is unavailable, not
an empty authoritative board. Production remains fail closed.

The historical HTML generator and legacy validator, Landscape,
score-to-weight, and emission paths remain archaeology, not current A10
authority or evidence. Earlier A10 ticket/Build Out shorthand admitting public
hotkey or anonymized identity, timestamps, `get(submission_id)`, or an ambiguous
official-or-fixture board was `DOCUMENTATION_LAG`; none of that behavior entered
the bounded implementation.

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

- the full Miner MCP or any A11–A12 implementation is present, or that draft
  PR #46 is current-main implementation or test authority;
- bounded A10 implementation implies an official/LIVE leaderboard, scientific,
  security, network, commercial, or production qualification, or any later
  frontier, product, settlement, chain, weight, or emission authority;
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

> **Carbon has an integrated constitutional architecture and a tested bounded A0-A10 software foundation. A9 implements only the exact seven-tool in-process Wave-A control/disclosure skeleton. A10 implements and tests only the exact bounded in-process fixture leaderboard; its documentation closeout merged normally in PR #38 as `404c039596b487cf2649bb1d73b80e9b49baaced`. A11-R1 through A11-R17 are ratified, while A11-R18 remains a draft immutable-sink-snapshot amendment candidate. A11 is unimplemented and untested on current main; draft PR #46 is blocked and non-authoritative. A11 and A12 remain `todo`, Wave A remains incomplete, and Wave B remains candidate-only and inactive.**
