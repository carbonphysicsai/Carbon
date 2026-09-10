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
> C0 engineering delivery is closed in bounded scope; G2 remains NOT_READY.
> OWNER-C1-C2-BURGERS-01 authorizes dependency-ready offline C1/C2
> engineering without changing G2. C-AUTH1 merged in PR #130 and C-EA0 merged
> in PR #131 as a3ca8cd111689329832131eac1460d579c7828b3. PR #132 merged
> NET-5R's eight-block repair as 675427ec8852579aa9d336bbec94e28be7b62810.
> NET-5R remains active after the standard-runtime full attempt passed both
> registrations and shared-winner evidence but stopped before recycled-UID
> evidence. G2 remains NOT_READY.
> Treasury remains optional; no public-network operation is authorized.

> **OWNER-DX-03 delivery override:** Follow `.agent/DELIVERY_PROTOCOL.md`.
> Engineering tickets require one applicable automated acceptance and normal
> expected-head merge, without mandatory GPT receipts or extra human delivery
> approvals. Human-reserved science, security, economics, deployment, launch,
> and LIVE authority remain unchanged.

**Status:** active in bounded engineering scope because `.agent/WAVE.md` names
Wave C/C0 and this file as its controlling register.
**Version:** 1.0
**Activation decision:** `OWNER-WAVE-C0-NET1-01`
**Selected ticket:** NET-5R — `in_progress`
**Next selected ticket:** none. C-EA1 remains `todo`, unstarted and input-blocked
until its reserved human operating inputs are approved.
**Primary Hub map_ref:** `WAVE-C/NET-5R`

## 1. Scope and sequence

C0: NET-1 -> NET-2 -> NET-3 -> C-REWARD -> NET-4A -> NET-4B -> NET-5 -> NET-6.
G2 requires actual disposable-localnet evidence. C1 real science and C2 public
integration retain their existing contracts and archive dependencies. Persistent
direct winner plus burn is supported; treasury and Research Concierge do not
block the network spine. B-E4 remains deferred/non-blocking, effectiveness
UNMEASURED; B-01G remains unfinished/non-blocking.

`OWNER-C1-C2-BURGERS-01` prospectively amends sequencing only: dependency-ready
offline C1/C2 engineering may proceed while G2 is NOT_READY. G2 continues to gate
the readiness claim and every chain-dependent execution. The active offline order
has delivered C-AUTH1 and C-EA0 before consumers rely on archive semantics.
C-EA1 is the next contract consumer but its real archive implementation remains
fail closed on the reserved human inputs. NET-5R's first repair merged in PR
#132. The exact standard profile then passed a one-shot registration diagnostic
and a full attempt reached shared-winner readback/epoch before a plain SDK nonce
transition rejected `SwapHotkey` as Stale. The changed public-transport-refresh
candidate is focused-tested; NET-5R remains selected and no later ticket is
selected.

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
| NET-5R | Shielded registration compatibility repair | in_progress | `.agent/evidence/wave_c/net-5r.md` | Codex + network/protocol engineering | Network/protocol + security | NET-5, SDK 11.1.0, runtime v445 | MQ-054, MQ-056 | M | C0/G2 |
| C-01 | Durable execution state and queue | done | `.agent/evidence/wave_c/c-01.md` | Codex + execution engineering | Execution + scientific integration | A7, B-GATE | MQ-048, MQ-051 | M | C1 |
| C-AUTH1 | Goal-driven authoring and Burgers V1 import | done | `.agent/evidence/wave_c/c-auth1.md` | Codex + scientific authoring | Scientific integration | C-01 | MQ-045, MQ-048 | L | C1 |
| C-EA0 | Evidence capture contract | done | `.agent/evidence/wave_c/c-ea0.md` | Codex + evidence architecture | Execution + Operations + data/security + scientific integration | C-AUTH1, C-01, B-GATE | MQ-048, MQ-051 | M | C1 |
| C-EA1 | Durable evidence archive | todo | none | Codex + evidence architecture | Operations + data/security + scientific integration | C-EA0 + approved reserved inputs | MQ-048, MQ-051 | L | C1 |

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
NET-5R remains in progress, G2 remains NOT_READY and no later
ticket is selected. C-AUTH1
and C-EA0 remain bounded offline engineering only; the public
workbench evidence is not scientifically qualified and C-EA0 creates no archive
runtime. C-EA1 is unstarted and input-blocked.

## 4. Acceptance and maturity

NET-6 follows `.agent/tickets/NET-6_network_operations.md`, OWNER-DX-03
and OWNER-C0-VALIDATION-01. Focused network/MCP tests plus all invariants,
quality/package/Hub checks and Merge gate; unknown/shared science retains full
fallback. No public deployment, scientific/security qualification, LIVE,
frontier, settlement or G2 readiness follows from these unit contracts.
The current G2 disposition and concrete C1/C2/archive handoff are in
`.agent/plans/C0_G2_C1_C2_HANDOFF.md`. NET-5R owns only the compatibility repair;
C-W1 still follows real C1, C-EA2 and its G2 dependency and is not selected.
The remaining G2 operation requires the changed source-backed SDK transport-
refresh candidate or an upstream equivalent to pass the existing full localnet
identity scenario. B-E4 and unfinished B-01G remain non-blocking.
