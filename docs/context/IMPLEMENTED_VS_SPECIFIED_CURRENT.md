# Carbon — Current Implemented vs Specified Ledger

**Status:** OWNER-CANONICAL maturity ledger, current through main
`62f52065b6695fc5f0e1e77562da4b3774eaaf3e`, tree
`0cc4fc8661663b29d954eb617323cc4fefc6c9cb`, the signed normal merge of A12 /
Wave-A closeout PR #52 on 2026-08-29.
**Purpose:** provide a concise current-state map that separates architecture, implementation, testing, qualification, and commercial maturity.
**Relationship to `Implemented_vs_Specified`:** the older ledger remains detailed historical evidence. This file is the current concise status reference.

> **Wave-B development-governance transition.** Current main records A12
> `done`, Wave A closed in bounded engineering scope, Wave B inactive, and
> B-01 `todo` and unauthorized. This documentation-only candidate proposes
> Wave B active in bounded development scope only after this exact governance
> change is independently reviewed, green, and normally merged. B-01 remains
> unstarted and becomes the next authorized `todo` ticket only after that
> merge; no Wave B implementation exists yet.
>
> Prior multi-role approval, exact-byte approval-bundle, and separate
> activation-closeout prerequisites are superseded for development by the
> executive record in `.agent/DECISIONS.md`. Material decisions must be
> recorded and the designated SciML / Technical Lead notified through issue
> #42, but silence is non-blocking. Reserved scientific, security, rights,
> economic, launch, deployment, LIVE, frontier, product, settlement, chain,
> weight, emission, and production decisions remain human-owned and unearned.

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
| A11 | Yes; A11-R1–A11-R18 ratified | Yes | Yes | No | Exact bounded in-process operational observability merged normally in PR #46 as `e2496e92eeae31befdaa430501bb9f00b0e6339e`; independently audited `66/66 PASS`; no scientific, security, network, commercial, or production qualification |
| A12 | Yes; A12-R1–A12-R12 ratified in PR #50 | Yes, exact bounded invariant-judge/CI scope | Yes, exact recorded engineering scope | No | Implementation merged in PR #51; `28` invariant tests, `24/24` ticket audit, and `9/9` Wave-A acceptance audit; A12 is `done` in bounded engineering scope on current main after closeout PR #52 |

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

A11 current bounded maturity:

```text
A11-R1 through A11-R18: RATIFIED

A11 IMPLEMENTED:
YES on current main for the bounded in-process engineering scope

A11 TESTED:
YES only for the exact recorded engineering scope

PR #46:
merged normally as e2496e92eeae31befdaa430501bb9f00b0e6339e

A11 SCIENTIFICALLY_QUALIFIED: NO
A11 SECURITY_QUALIFIED: NO
A11 NETWORK_QUALIFIED: NO
A11 COMMERCIALLY_VALIDATED: NO
A11 PRODUCTION_QUALIFIED: NO

A11 WAVE STATUS:
done

A12: done in its bounded invariant-judge/CI scope
Wave A: closed in bounded engineering scope
Wave B: inactive on the exact governance base; proposed active in bounded
development scope only after this governance candidate normally merges
B-01: todo and unstarted
Wave B implemented: NO
Wave B tested: NO
```

The exact A11 implementation is reviewed head
`e5ed60c4043abb3bfd2af945b5dd45b8e1996fcb` merged as signed commit
`e2496e92eeae31befdaa430501bb9f00b0e6339e`, with identical reviewed/merge
tree `3d6682803422497efc6bff26451c12d9c306f96c`. Post-merge run
`33199541335` passed `2310` CPU tests and quality. Independent closeout audit
was `66 PASS / 0 FAIL`; fresh focused/related/full results were
`337`/`1330`/`2310`. Fresh wheel
`carbon-0.9.0-py3-none-any.whl` had SHA-256
`ea686e933f6f93c72df281e79a3baebcb05f6789b25d4499ff81e937980e94fe`.
Strict Ruff/Black, the no-new-debt quality gate, and `git diff --check` passed.
The final sink-snapshot construction mechanism is private, identity-bound,
weak, one-shot, and consumed before validation. No new owner decision or
semantic amendment was introduced by closeout.

A12 current bounded maturity:

```text
A12-R1 through A12-R12:
SPECIFIED / RATIFIED: YES
ratified in PR #50 from reviewed head
6695c279728438befd6404fb81c4f7a27e382a67 by normal merge
746e56e42c412bc8ba2eeb4d85ed83396e1a084c

A12 IMPLEMENTED: YES
only for the exact bounded invariant-judge and CI scope merged in PR #51

A12 TESTED: YES
only for the exact recorded invariant, owner-regression, CPU, and quality
engineering scope

A12 SCIENTIFICALLY_QUALIFIED: NO
A12 SECURITY_QUALIFIED: NO
A12 NETWORK_QUALIFIED: NO
A12 COMMERCIALLY_VALIDATED: NO
A12 PRODUCTION_QUALIFIED: NO

A12 WAVE STATUS: done in its bounded invariant-judge/CI scope
Wave A: closed in bounded engineering scope
Wave B: inactive on the exact governance base; proposed active in bounded
development scope only after this governance candidate normally merges
B-01: todo and unstarted
Wave B implemented: NO
Wave B tested: NO
```

The exact denominator is the twelve numbered cross-cutting invariants in
`Design_Specs/Build_Out.md` section 2. A11 redaction is evidence under no seed
leakage/disclosure; fee/payment isolation is evidence under forbidden score
inputs; and A8 non-emission is evidence under no placeholder LIVE. They do not
create extra rows. The implemented lane has exactly `28` tests: `12` unique
row-dedicated tests in exact A12-R1 through A12-R12 order and `16`
infrastructure tests that prove crosswalk equality, canonical resolution,
marker/entrypoint integrity, fail-closed behavior, and containment. The
supporting owner regression passes `2052` tests; the complete default CPU suite
passes `2310`. The independent closeout audit passes all `24/24` ticket
criteria and all `9/9` Build Out section 12 Wave-A acceptance bullets. No
implementation repair or new owner decision was exposed by closeout.

The canonical entrypoint is exactly
`python -m pytest tests/invariants -m invariant -q`. The explicit directory is
required because `pyproject.toml` roots default pytest discovery at
`tests/cpu`; no normative bare-marker command remains. The lane fails closed
for a missing or empty suite, zero marker matches, complete deselection,
crosswalk drift, mapping drift, or prohibited bypass. Push CI run
`33250521376` passed the `28` invariant tests in `4.22s`, all `2310` CPU tests
in `59.52s`, and Code quality at `Ruff 757/776; Black 62/68`, removed debt
`19/6`, five changed Python files clean, and no new debt.

Exact-current-main GitHub Actions run `33255939632`, attempt 2, passed on
GitHub-hosted Ubuntu: `28` invariant tests, `2310` CPU tests, and unchanged
quality at `Ruff 757/776; Black 62/68`, removed debt `19/6`, zero changed
Python files, and no new debt.

The reviewed implementation head is
`33b4626a1ffe7d0c65336336a870a8f4a73ab92f`; PR #51 normally merged it as
`2a8b273a1167588efb4a11159da5224264d5b37a`, tree
`cb7b23d32e3663bbf00704f1e28c16020bfb9226`. PR #52 then normally merged
the bounded A12/Wave-A closeout as current main
`62f52065b6695fc5f0e1e77562da4b3774eaaf3e`, tree
`0cc4fc8661663b29d954eb617323cc4fefc6c9cb`. This evidence earns only bounded
`IMPLEMENTED: YES` and `TESTED: YES`; it does not qualify the underlying
scientific, execution-isolation, security, network, commercial, or production
systems beyond the exact structural and engineering assertions tested.

**Historical pre-implementation chronology below — superseded for current
state.** It is preserved to retain the full reconciliation, amendment, and
defect chain; its draft/candidate/current-main statements describe those
historical checkpoints, not the current maturity above.

PR #39 normally merged A11-R1 through A11-R17 at historical ratification merge
`4e4a66d29566a2a62a82188adddac76e6e0fb8b8`; those decisions remain ratified.
That merge is PR #47's original base, PR #45's first parent, and ancestral to
present main; it was not current main after that historical rebaseline.
At that historical checkpoint, draft PR #46 was blocked because its sink seam
passed shared canonical A11/A5/A7 enum singletons.
`P1_GENERIC_DATACLASS_SERIALIZATION_BYPASS` is repaired on
that draft branch, but `P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS` is
confirmed. The earlier `66 PASS / 0 FAIL` implementation audit is withdrawn.
PR #46 test results are branch evidence only and do not make A11 implemented
or tested at that checkpoint.

The historical checkpoint's `origin/main` was `644c6c38139e9215e5ccc8d3c8e8bc62e843dbb3`,
tree `15637ab89613daeec20f2f46bdefd045cb0ed7c6`, subject `Merge pull request
#48 from carbonphysicsai/agent/science-gtm-wave-integration`, with ordered
parents `bf6e2e8910f90b345ded44bdebb63fca73646b0d` and
`dec7ba8f1ac5d98c48c492abbdbeb8816e25e25e`, signature `verified=true`,
`reason=valid`. The immediately preceding PR #45 merge is
`bf6e2e8910f90b345ded44bdebb63fca73646b0d`, tree
`b6365e31b09339826b7568565bb28c7c32007fac`, with ordered parents
`4e4a66d29566a2a62a82188adddac76e6e0fb8b8` and
`74f8edb04b3b806f4edc75de3ba8c4c6273815fb`, signature verified and valid.

That historical main run `33093494970` succeeded. CPU job `98592266955` recorded
`1973 passed in 44.41s`; code-quality job `98592266774` recorded
`Ruff 757/776`, `Black 62/68`, removed debt `19/6`, changed Python files `0`,
and no new debt. At that checkpoint, `.agent/WAVE.md` was exact blob
`6369a373630392955ea2d58f258f06482173578c`: A10 is `done`; A11 and A12 are
`todo`; Wave A remains controlling and incomplete; Wave B remains inactive.

PR #45 merged candidate-only Wave B v0.3 scientific-hardening planning and
touches only `.agent/DECISIONS.md` among the six R18 documents. PR #48 merged
Science-GTM future-ticket integration and touches none of the six. Neither
merge widens A11-R18, activates Wave B, implements A11, or creates scientific,
security, network, commercial, or production authority.

PR #47 began from `4e4a66d29566a2a62a82188adddac76e6e0fb8b8`; initial R18 commit
`9de896dea92e5378d99ef205cd21a29ef9f57fd3` was corrected at reviewed head
`76ef2b194132bd2e07677d4ac1cf6baa83509faf`. Old synthetic
`7ab62b646ba1dee248e090cbd2490511a4b1d87a` and CI run `33039977702` are
stale old-base evidence only. Current-base drift is confirmed, but there is no
R18 semantic conflict and no new owner decision.

Normal synchronization merge `cf9a773520645053e6d745c28aede15356fef80a`,
tree `b06e2aa7a0bf28700449010d320d09317201d155`, subject `merge: synchronize
A11-R18 with current main`, has ordered parents corrected reviewed head
`76ef2b194132bd2e07677d4ac1cf6baa83509faf` then current main
`644c6c38139e9215e5ccc8d3c8e8bc62e843dbb3`. The one rebaseline commit is
`docs: rebaseline A11-R18 against current main`, with that synchronization merge
as its sole parent. Its generated SHA/tree are recorded after creation in PR
#47 publication metadata. Its sequential and cumulative manifest is exactly the
following six A11-R18 documents:

```text
M .agent/DECISIONS.md
M .agent/plans/A11_logging.md
M .agent/tickets/A11_logging.md
M Design_Specs/Build_Out_Constitutional_Overlay.md
M agent_pack/README.md
M docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md
```

Every incoming PR #45/#48 path outside those six is byte-identical to current
main. The R18 semantic contract is unchanged.

```text
P1_SNAPSHOT_TYPE_MUTATION_SCOPE_OVERCLAIM:
CORRECTED

P2_PUBLIC_SNAPSHOT_CONSTRUCTION_AMBIGUITY:
CORRECTED
```

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

Relative to the synchronized historical main, that documentation candidate added no A11 implementation, owner
instrumentation, exporter, test, or scientific, security, network, commercial,
or production qualification evidence. It changes no A5/A7 owner source,
A12 artifact, Wave B artifact, dependency, workflow, or quality baseline.

The exact next-move sequence at that historical checkpoint was:

1. independently review and ratify exact A11-R18;
2. normally merge the exact reviewed amendment only after explicit human
   authorization;
3. synchronize PR #46 with the amendment merge;
4. repair PR #46 to implement the snapshot boundary; and
5. independently review the repaired implementation before ready or merge.

At that historical checkpoint, `main` implemented and tested only a bounded,
in-process, fixture-only
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

- the full Miner MCP is present, or that the bounded A12 invariant-judge lane
  proves the underlying scientific/security properties, supplies later-wave
  authority, or exceeds its exact structural and engineering assertions;
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

> **Carbon current main
> `62f52065b6695fc5f0e1e77562da4b3774eaaf3e`, tree
> `0cc4fc8661663b29d954eb617323cc4fefc6c9cb`, has an integrated
> constitutional architecture and a tested bounded A0–A12 software foundation.
> PR #52 records A12 done and Wave A closed in bounded engineering scope. This
> governance candidate proposes Wave B active only after its exact reviewed,
> green, normal merge, with `.agent/WAVE_B.md` v0.4 controlling and B-01 still
> `todo` and unstarted. No Wave B implementation or testing exists yet.
> Development no longer requires the prior approval bundle or separate
> activation closeout; material decisions require non-blocking lead
> notification. Every scientific, security, network, rights, commercial,
> production, LIVE, launch, frontier, product, settlement, chain, weight, and
> emission maturity state remains unearned.**
