# Carbon Wave C Board

> **OWNER-C0-REWARD-01 current execution authority:**
> NET-1 merged in PR #120 as 6dad22db26e4b8babadf73c4de2527a17485a2b1.
> NET-2 merged in PR #121 as 97725a1f4c6c8c65234e96770c847622273fc55e.
> NET-3 merged in PR #122 as d55fdeb4d9be6f25f963eac0ed608414dbf0b4e6.
> C-REWARD merged in PR #123 as 505f08cde173eab197aa397a09536bb6bf576065.
> NET-4A merged in PR #124 as ba88aa8bb6360fc101ec4bc3afc5c0f4408ccd5f.
> NET-4B merged in PR #125 as 0e6b5e001302b349135785756c633530853684c2.
> NET-5 merged in PR #126 as 95fa1e42dbf8d5fdcfde80d440eb38229b2764db.
> NET-6 merged in PR #127 as 6dd1bab569f6a8c5f597fd2cd5ed931b4d44eade.
> C-01 merged in PR #129 as 4c9e8040df3c81ecb167534424df770eb4d77d61.
> C0 engineering delivery is closed in bounded scope; G2 is LOCALNET_READY only
> for the exact standard-profile disposable v445 localnet.
> OWNER-C1-C2-BURGERS-01 authorizes dependency-ready offline C1/C2
> engineering without changing G2. C-AUTH1 merged in PR #130 and C-EA0 merged
> in PR #131 as a3ca8cd111689329832131eac1460d579c7828b3. PR #132 merged
> NET-5R's eight-block repair as 675427ec8852579aa9d336bbec94e28be7b62810.
> PR #133 merged the standard-profile and D4 specification checkpoint as
> 2a71a392380cb4df0e0597a92674882de7801c70.
> D5 run 34497456242 failed because its public nonce observation advanced the
> signing cache. D6 removed that observer effect, and full/standard run
> 34518806217 passed the complete auditable predicate at candidate
> 97a2405776a3f520076e03a89ea8b7b4086d9ad2. NET-5R is done; fast/public
> capability remains unearned.
> Treasury remains optional; no public-network operation is authorized.

> **OWNER-DX-03 delivery override:** Follow `.agent/DELIVERY_PROTOCOL.md`.
> Engineering tickets require one applicable automated acceptance and normal
> expected-head merge, without mandatory GPT receipts or extra human delivery
> approvals. Human-reserved science, security, economics, deployment, launch,
> and LIVE authority remain unchanged.

**Status:** active in bounded engineering scope because `.agent/WAVE.md` names
Wave C/C0 and this file as its controlling register.
**Version:** 1.5
**Activation decision:** `OWNER-WAVE-C0-NET1-01`
**Selected ticket:** C-02 — `in_progress`
**Active ticket:** C-02
**Next selected ticket:** none. The owner-supplied immutable JAX bundle selects
only a bounded DEVELOPMENT adapter; later isolation, scientific, archive and
public-network work remains unselected.
PR #146 merged the initial adapter as
`d9fadf7f9cbb9b3a2a4ffa1ec9b0c906826be8ca`; the selected continuation adds
artifact/prediction hardening and frozen DEVELOPMENT repeats only. C-02 remains
`in_progress`, C-03 remains unselected, and no production repeat count exists.
**Last completed ticket:** C-EP3, merged in PR #145 after head
`ff1d4603cf6889bb3e9cf7f4a589524ade5c6b8c` passed run `34721794618`
**Primary Hub map_ref:** `WAVE-C`

C-EA1 passed canonical acceptance in run `34558389185` at accepted head
`a779af066f4bf9bc36b6d6ab23914fa19191e1de` and normally merged in PR #136 as
`0e0714c8260ca482a0ba2b743b2eaefd50508da1`.

## 1. Scope and sequence

C0: NET-1 -> NET-2 -> NET-3 -> C-REWARD -> NET-4A -> NET-4B -> NET-5 -> NET-6.
G2 requires actual disposable-localnet evidence. C1 real science and C2 public
integration retain their existing contracts and archive dependencies. Persistent
direct winner plus burn is supported; treasury and Research Concierge do not
block the network spine. B-E4 remains deferred/non-blocking, effectiveness
UNMEASURED; B-01G remains unfinished/non-blocking.

`OWNER-C1-C2-BURGERS-01` prospectively amends sequencing only: dependency-ready
offline C1/C2 engineering may proceed independently of G2. G2's narrow standard-
profile result does not authorize public or chain-dependent C2 execution. The active offline order
has delivered C-AUTH1 and C-EA0 before consumers rely on archive semantics.
C-EA1 is complete only under `OWNER-C-EA1-SYNTHETIC-01`'s closed synthetic
development profile. Real admission and every production archive input remain
fail closed. `OWNER-C1-CONTRACTS-01` materializes C-03, C-08, C-09 and the exact
C1 dependency graph without activating or implementing another ticket.
NET-5R's first repair merged in PR
#132, and PR #133 merged its standard-profile/D4 specification checkpoint as
`2a71a392380cb4df0e0597a92674882de7801c70`. The exact standard profile then
passed a one-shot registration diagnostic.
D4 run 34489505489 passed the complete behavioral predicate. D5 run 34497456242
then failed because its next-index evidence read advanced the signing transport
cache. D6 replaced that stateful read with exact finalized `System.Account`
evidence. Canonical full/standard run 34518806217 passed at exact candidate
`97a2405776a3f520076e03a89ea8b7b4086d9ad2`, including auditable exclusive
handover. NET-5R is done and G2 is `LOCALNET_READY` only for that exact standard-
profile disposable v445 localnet. Fast-profile and public-network capability
remain unearned. PR #136 implemented C-EA1 without selecting C-EA2.

## 2. NET-0 development disposition

NET-0 remains a boundary family, not an invented completed implementation ticket.
`.agent/plans/C0_score_reward_program.md` owns current topology, threat model,
identity, development settings and unresolved production boundaries. NET-1
satisfies local read-only identity prerequisites. NET-2 owns application auth;
privileged publication still requires later runtime/genesis/sink checks. Missing
production custody, quorum, science or economics blocks only that operation.

## 3. Selected C0 ticket board

| ID | Deliverable | Status | Evidence | Driver | Accountable reviewer | Depends on | Master questions | Effort | Target |
|---|---|---|---|---|---|---|---|---|---|
| NET-1 | Pinned read-only adapter and contextual identities | done | `.agent/evidence/wave_c/net-1.md` | Codex + network/protocol engineering | Network/protocol + security | B-GATE | MQ-054, MQ-056 | M | C0 |
| NET-2 | Authenticated application transport and durable receipts | done | `.agent/evidence/wave_c/net-2.md` | Codex + network/protocol engineering | Network/protocol + security | NET-1 | MQ-054, MQ-056 | M | C0 |
| NET-3 | Candidate commitment and accepted fixture bridge | done | `.agent/evidence/wave_c/net-3.md` | Codex + network/protocol engineering | Network/protocol + scientific integration | NET-2 | MQ-054, MQ-056 | M | C0 |
| C-REWARD | Bounded-linear reward core and development scorecard | done | `.agent/evidence/wave_c/c-reward.md` | Codex + reward/protocol engineering | Scientific integration + network/security | NET-3 | MQ-054, MQ-056 | L | C0 |
| NET-4A | Nominal publication intents | done | `.agent/evidence/wave_c/net-4a.md` | Codex + network/protocol engineering | Network/protocol + security | C-REWARD | MQ-054, MQ-056 | M | C0 |
| NET-4B | Verified complete-vector publication and recovery | done | `.agent/evidence/wave_c/net-4b.md` | Codex + network/protocol engineering | Network/protocol + security | NET-4A | MQ-054, MQ-056 | L | C0 |
| NET-5 | Reproducible disposable localnet integration | done | `.agent/evidence/wave_c/net-5.md` | Codex + network/protocol engineering | Network/protocol + security | NET-4B | MQ-054, MQ-056 | L | C0 |
| NET-6 | Disposable operator lifecycle and recovery | done | `.agent/evidence/wave_c/net-6.md` | Codex + network/protocol engineering | Operations + security | NET-5 | MQ-054, MQ-056 | L | C0 |
| NET-5R | Shielded registration compatibility repair | done | `.agent/evidence/wave_c/net-5r.md` | Codex + network/protocol engineering | Network/protocol + security | NET-5, SDK 11.1.0, runtime v445 | MQ-054, MQ-056 | M | C0/G2 |
| C-01 | Durable execution state and queue | done | `.agent/evidence/wave_c/c-01.md` | Codex + execution engineering | Execution + scientific integration | A7, B-GATE | MQ-048, MQ-051 | M | C1 |
| C-EP1 | DEVELOPMENT per-job evaluation packs | done | `.agent/evidence/wave_c/c-ep1.md` | Codex + execution/scientific integration | Execution + scientific integration + data/security | NET-3, C-01, A4, A5, A6, A7, A8 | MQ-048, MQ-051 | M | C1 development |
| C-EP2 | Variant-A measurement and offline Variant-B decision | done | `.agent/evidence/wave_c/c-ep2.md` | Codex + measurement/execution engineering | Execution + scientific integration + data/security | C-EP1 | MQ-048, MQ-051 | M | C1 development |
| C-EP3 | Public-reference input acquisition and component probe | done | `.agent/evidence/wave_c/c-ep3.md` | Codex + scientific measurement engineering | Physics/SciML + scientific integration | C-EP2, C-AUTH1 | MQ-045, MQ-048 | S | C1 development |
| C-AUTH1 | Goal-driven authoring and Burgers V1 import | done | `.agent/evidence/wave_c/c-auth1.md` | Codex + scientific authoring | Scientific integration | C-01 | MQ-045, MQ-048 | L | C1 |
| C-EA0 | Evidence capture contract | done | `.agent/evidence/wave_c/c-ea0.md` | Codex + evidence architecture | Execution + Operations + data/security + scientific integration | C-AUTH1, C-01, B-GATE | MQ-048, MQ-051 | M | C1 |
| C-EA1 | Durable evidence archive | done | `.agent/evidence/wave_c/c-ea1.md` | Codex + evidence architecture | Operations + data/security + scientific integration | C-EA0 + OWNER-C-EA1-SYNTHETIC-01 | MQ-048, MQ-051 | L | C1 |
| C-02 | Real declarative reconstruction | in_progress | `.agent/tickets/C-02_real_reconstruction.md` | Physics/SciML + reconstruction engineering | Scientific integration + execution | B-02B, B-03, B-E1, C-01 | MQ-045, MQ-048 | L | C1 |
| C-03 | Isolated reconstruction worker | todo | `.agent/tickets/C-03_isolated_reconstruction_worker.md` | Codex + execution/SRE engineering | Security + protocol + Physics/SciML | C-02 | MQ-015, MQ-048 | L | C1 |
| C-04 | Protected reference runtime | todo | `.agent/plans/C1_DEPENDENCY_GRAPH.md` | Scientific reference + execution engineering | Physics/SciML + security | C-03, B-04, B-E2 | MQ-045, MQ-048 | L | C1 |
| C-05 | Real measurement and Score Pack | todo | `.agent/plans/C1_DEPENDENCY_GRAPH.md` | Scientific measurement engineering | Physics/SciML + statistics | C-02, C-04, B-05 | MQ-045, MQ-048 | L | C1 |
| C-06 | Signed evaluation receipt | todo | `.agent/plans/C1_DEPENDENCY_GRAPH.md` | Scientific integration + receipt engineering | Security + Physics/SciML | C-01, C-02, C-04, C-05 | MQ-048, MQ-051 | L | C1 |
| C-07 | Real validator orchestration | todo | `.agent/plans/C1_DEPENDENCY_GRAPH.md` | Validator orchestration engineering | Scientific integration + security | C-01, C-02, C-03, C-04, C-05, C-06 | MQ-048, MQ-051 | L | C1 |
| C-08 | Authenticated miner MCP end to end | todo | `.agent/tickets/C-08_authenticated_miner_mcp_e2e.md` | Codex + API/protocol engineering | Protocol + security + scientific integration | NET-2, C-07, A9 | MQ-051, MQ-054 | L | C1/C2 |
| C-EA2 | Archive before finalization | todo | `.agent/tickets/C-EA2_archive_before_finalization.md` | Evidence archive + validator integration | Operations + data/security + scientific integration | C-EA1, C-07 | MQ-048, MQ-051 | L | C1 |
| C-09 | Official testnet publication provider | todo | `.agent/tickets/C-09_official_testnet_publication_provider.md` | Codex + publication/protocol engineering | Protocol + scientific integration + security | A10, C-06, C-07, C-EA2 | MQ-048, MQ-054 | L | C1/C2 |
| C-W1 | Exact real testnet eligibility provenance | todo | `.agent/tickets/C-W1_testnet_eligibility.md` | Network/protocol + scientific integration | Security + Physics/SciML | C-09, C-EA2 | MQ-048, MQ-054 | M | C2 |

NET-1: PR #120 expected head 528213a passed run 34405478897 and normally merged
as 6dad22db26e4b8babadf73c4de2527a17485a2b1. Completion comment:
https://github.com/carbonphysicsai/Carbon/pull/120#issuecomment-5608855211.
NET-1 earned bounded read-only SPECIFIED/IMPLEMENTED/TESTED only.
NET-2 passed run 34408587763 and normally merged in PR #121 as
97725a1f4c6c8c65234e96770c847622273fc55e. NET-3 passed run 34411892285 and normally merged in PR #122 as
d55fdeb4d9be6f25f963eac0ed608414dbf0b4e6. C-REWARD passed run 34416168621 and merged in PR #123 as
505f08cde173eab197aa397a09536bb6bf576065. NET-4A passed run 34417436723 and merged in PR #124 as
ba88aa8bb6360fc101ec4bc3afc5c0f4408ccd5f. NET-4B passed run 34421219713 and merged in PR #125 as
0e6b5e001302b349135785756c633530853684c2. NET-5 passed run 34429639429 and merged in PR #126 as 95fa1e42dbf8d5fdcfde80d440eb38229b2764db. NET-6 passed run 34432281140 and normally merged in PR #127 as 6dd1bab569f6a8c5f597fd2cd5ed931b4d44eade.
Completion receipt: https://github.com/carbonphysicsai/Carbon/pull/127#issuecomment-5612097862.
C-01 passed canonical RUNTIME_FULL acceptance and normally merged in PR #129 as
4c9e8040df3c81ecb167534424df770eb4d77d61. C-AUTH1 passed canonical
RUNTIME_FULL, Hub and merge-gate acceptance in run 34449303309 and normally
merged in PR #130 as 5d3c6cbca14bf3422960d9a7fe3ce7a1bcfa2ed4.
C-EA0 accepted head 62fbaad81081d87e70c8f438642b6529b6f93aff passed canonical run 34455987632 and normally
merged in PR #131 as a3ca8cd111689329832131eac1460d579c7828b3. NET-5R's
first repair merged in PR #132 as 675427ec8852579aa9d336bbec94e28be7b62810.
Standard runs 34473145103/34473508494 bound the profile and passed one
registration; full run 34474220953 passed both registrations and shared-winner
evidence but failed before recycled-UID evidence on a plain SDK nonce transition.
NET-5R D6 run 34518806217 passed the complete auditable full/standard predicate;
G2 is LOCALNET_READY for the exact standard profile only. C-AUTH1 and C-EA0
remain bounded offline engineering only; the public workbench evidence is not
scientifically qualified. C-EA1 accepted head
`a779af066f4bf9bc36b6d6ab23914fa19191e1de` passed canonical run
`34558389185` and normally merged in PR #136 as
`0e0714c8260ca482a0ba2b743b2eaefd50508da1`. Its runtime is limited to the
exact synthetic development profile and cannot acknowledge real evidence or
satisfy C-EA2. C-03, C-08 and C-09 are contract-only; C-EA2 and every later
runtime ticket remain unselected and dependency-blocked.

C-EP1 accepted head `e0fbb6208cf0bf95910d51e7a3c996b09387a14e`
passed RUNTIME_FULL run `34708322417` and normally merged in PR #143 as
`d783c2c7209c7eea2d46dd395c4eaaf8094a9e71`. C-EP2 corrected head
`89f06eda74b15dd336e57a512f228c6b37cca77d` then passed RUNTIME_FULL run
`34718392697` and normally merged in PR #144 as
`96099aeac9e5022bda9d94730b1d7d955cb6c1d5`. Its conservative recommendation
remains `COLLECT MISSING INPUTS FIRST`. C-EP3 then passed RUNTIME_FULL run
`34721794618` at head `ff1d4603cf6889bb3e9cf7f4a589524ade5c6b8c` and
normally merged in PR #145 as
`a02ca5f46eda2283db7808d9646c1ef24715ec4a`. The owner's supplied immutable
JAX bundle selects bounded DEVELOPMENT C-02 integration; sharing and every
later real vertical remain structurally unavailable.

## 4. Acceptance and maturity

NET-6 follows `.agent/tickets/NET-6_network_operations.md`, OWNER-DX-03
and OWNER-C0-VALIDATION-01. Focused network/MCP tests plus all invariants,
quality/package/Hub checks and Merge gate; unknown/shared science retains full
fallback. No public deployment, scientific/security qualification, LIVE,
frontier, settlement or G2 readiness follows from these unit contracts.
The current G2 disposition and concrete C1/C2/archive handoff are in
`.agent/plans/C0_G2_C1_C2_HANDOFF.md`. NET-5R owns only the compatibility repair;
C-W1 still follows real C1, C-EA2 and its G2 dependency and is not selected.
The G2 predicate is satisfied only by the retained standard-profile run and does
not generalize to the failed fast profile or public networks. B-E4 and unfinished
B-01G remain non-blocking.
