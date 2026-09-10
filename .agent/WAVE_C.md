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
> engineering without changing G2. C-AUTH1 is the active implementation ticket.
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
**Selected ticket:** C-AUTH1 — `in_progress`
**Next selected ticket:** C-EA0
Selection follows C-AUTH1 acceptance and normal merge.
**Primary Hub map_ref:** `WAVE-C/C-AUTH1`

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
continues through C-AUTH1, with C-EA0 placed before consumers rely on archive
semantics. NET-5R is a separate unselected compatibility repair; the unchanged
failing registration command must not be rerun without a new hypothesis.

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
| C-01 | Durable execution state and queue | done | `.agent/evidence/wave_c/c-01.md` | Codex + execution engineering | Execution + scientific integration | A7, B-GATE | MQ-048, MQ-051 | M | C1 |
| C-AUTH1 | Goal-driven authoring and Burgers V1 import | in_progress | `.agent/evidence/wave_c/c-auth1.md` | Codex + scientific authoring | Scientific integration | C-01 | MQ-045, MQ-048 | L | C1 |
| C-EA0 | Evidence capture contract | todo | none | Codex + evidence architecture | Execution + Operations + data/security + scientific integration | C-AUTH1, C-01, B-GATE | MQ-048, MQ-051 | M | C1 |

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
4c9e8040df3c81ecb167534424df770eb4d77d61. Later C0 tickets are unstarted.
NET-5R is materialized but unselected. C-AUTH1 is bounded offline engineering
only; its public workbench evidence is not scientifically qualified. C-EA0 stays
future-reserved until C-AUTH1 acceptance and normal merge.

## 4. Acceptance and maturity

NET-6 follows `.agent/tickets/NET-6_network_operations.md`, OWNER-DX-03
and OWNER-C0-VALIDATION-01. Focused network/MCP tests plus all invariants,
quality/package/Hub checks and Merge gate; unknown/shared science retains full
fallback. No public deployment, scientific/security qualification, LIVE,
frontier, settlement or G2 readiness follows from these unit contracts.
The final G2 disposition and concrete C1/C2/archive handoff are in
`.agent/plans/C0_G2_C1_C2_HANDOFF.md`. C-AUTH1 is selected under the prospective
sequencing amendment; C-W1 still follows real C1, C-EA2 and its G2 dependency and
is not selected.
The remaining C0 operation is tested shielded-registration compatibility followed
by the existing full localnet scenario. B-E4 and unfinished B-01G remain non-blocking.
