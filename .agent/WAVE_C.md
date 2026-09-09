# Carbon Wave C Board

> **OWNER-C0-REWARD-01 current execution authority:**
> NET-1 merged in PR #120 as 6dad22db26e4b8babadf73c4de2527a17485a2b1.
> NET-2 merged in PR #121 as 97725a1f4c6c8c65234e96770c847622273fc55e.
> NET-3 merged in PR #122 as d55fdeb4d9be6f25f963eac0ed608414dbf0b4e6.
> C-REWARD is now the one active implementation ticket. Continue NET-4A -> NET-4B -> NET-5 -> NET-6 after each accepted merge.
> Treasury remains optional; no public-network operation is authorized.

> **OWNER-DX-03 delivery override:** Follow `.agent/DELIVERY_PROTOCOL.md`.
> Engineering tickets require one applicable automated acceptance and normal
> expected-head merge, without mandatory GPT receipts or extra human delivery
> approvals. Human-reserved science, security, economics, deployment, launch,
> and LIVE authority remain unchanged.

**Status:** active in bounded engineering scope because `.agent/WAVE.md` names
Wave C/C0 and this file as its controlling register.
**Version:** 0.4
**Activation decision:** `OWNER-WAVE-C0-NET1-01`
**Selected ticket:** C-REWARD — `in_progress`
**Primary Hub map_ref:** `WAVE-C/C-REWARD`

## 1. Scope and sequence

C0: NET-1 -> NET-2 -> NET-3 -> C-REWARD -> NET-4A -> NET-4B -> NET-5 -> NET-6.
G2 requires actual disposable-localnet evidence. C1 real science and C2 public
integration retain their existing contracts and archive dependencies. Persistent
direct winner plus burn is supported; treasury and Research Concierge do not
block the network spine. B-E4 remains deferred/non-blocking, effectiveness
UNMEASURED; B-01G remains unfinished/non-blocking.

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
| C-REWARD | Bounded-linear reward core and development scorecard | in_progress | `.agent/evidence/wave_c/c-reward.md` | Codex + reward/protocol engineering | Scientific integration + network/security | NET-3 | MQ-054, MQ-056 | L | C0 |

NET-1: PR #120 expected head 528213a passed run 34405478897 and normally merged
as 6dad22db26e4b8babadf73c4de2527a17485a2b1. Completion comment:
https://github.com/carbonphysicsai/Carbon/pull/120#issuecomment-5608855211.
NET-1 earned bounded read-only SPECIFIED/IMPLEMENTED/TESTED only.
NET-2 passed run 34408587763 and normally merged in PR #121 as
97725a1f4c6c8c65234e96770c847622273fc55e. NET-3 passed run 34411892285 and normally merged in PR #122 as
d55fdeb4d9be6f25f963eac0ed608414dbf0b4e6. C-REWARD is selected, not delivered.
Later tickets are unstarted; materialize them
before implementation. No later ticket is selected.

## 4. Acceptance and maturity

C-REWARD follows `.agent/tickets/C-REWARD_score_reward_core.md`, OWNER-DX-03
and OWNER-C0-VALIDATION-01. Focused network/MCP tests plus all invariants,
quality/package/Hub checks and Merge gate; unknown/shared science retains full
fallback. No public deployment, scientific/security qualification, LIVE,
frontier, settlement or G2 readiness follows from these unit contracts.
After accepted C-REWARD merge, NET-4A is the next dependency-ready ticket.
