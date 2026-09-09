# Carbon Wave C Board

> **OWNER-DX-03 delivery override:** Follow `.agent/DELIVERY_PROTOCOL.md`.
> Engineering tickets require one applicable automated acceptance and normal
> expected-head merge, without mandatory GPT receipts or extra human delivery
> approvals. Human-reserved science, security, economics, deployment, launch,
> and LIVE authority remain unchanged.

**Status:** active in bounded engineering scope because `.agent/WAVE.md` names
Wave C/C0 and this file as its controlling register.
**Version:** 0.1
**Activation decision:** `OWNER-WAVE-C0-NET1-01`
**Selected ticket:** NET-1 — `in_progress`
**Primary Hub map_ref:** `WAVE-C/NET-1`

## 1. Scope and sequence

Wave C preserves the owner-ratified order:

```text
C0 network foundation (NET-1 through NET-6) -> G2 LOCALNET_READY
-> C1 real scientific vertical
-> C2 temporary direct-weight testnet integration -> G3
```

Only NET-1 is selected. NET-2 through NET-6, every existing ticket-local C1
and evidence-archive contract, and C2 remain unselected and unstarted. The
existing C/D ticket files retain their own Definitions of Done. The separate
Research Concierge remains independently enableable and non-blocking to the
network spine under `OWNER-ROADMAP-02`; its engineering acceptance contract is
unchanged and it may remain disabled.

## 2. NET-0 prerequisite dispositions

NET-0 is a boundary prerequisite family, not a completed implementation ticket.
This transition does not mark it complete or claim security acceptance.

| Requirement | Controlling source | Disposition for NET-1 | Operation still prevented |
|---|---|---|---|
| Carbon/chain ownership and one-way dependency | `OWNER-NET-01`; launch v1.0.4 §§2, 4.1; Build Out Protocol Extension §4 | Settled for a local read-only adapter. Bittensor owns network identity/metagraph/UID state; Carbon owns science and consumes only Carbon-owned adapter types. SDK objects stay inside `carbon.chain`. | None for local read-only snapshots. SDK objects remain forbidden in scientific scoring/evaluation authority. |
| Minimal read-only topology | `OWNER-NET-01`; `Design_Specs/Architecture_Rationale.md` adapter rationale; Build Out C0 | Delegated reversible choice: process-local explicit adapter construction with no import-time client, wallet, network, or key access. | Production nodes, background refresh, service topology, deployment, and operator SLOs remain unavailable for NET-6. |
| Threat-model boundary | MQ-054/MQ-056; `AGENTS.md` security rules; `OWNER-NET-01` | NET-1 may translate controlled read-only SDK responses and classify provider failures without credentials, signing, transport, or publication. Tests must prove containment and absence of write capability. | NET-2 authentication/replay, privileged calls, write operations, custody, rotation, and production security acceptance remain blocked in their owning tickets. |
| Network/snapshot identity | NET-1 responsibility in launch v1.0.4 and Build Out | NET-1 must bind network, endpoint/provider context, netuid, observed chain identity, and snapshot identity so hotkey/UID mappings are never timeless or interchangeable. | Cross-snapshot identity claims without exact context are rejected. |
| Temporary testnet policy | `OWNER-NET-01`; MQ-055; launch v1.0.4 §5 | Structural intent separation, exact provenance, expiry, and explicit non-paying no-winner behavior are settled planning boundaries but are outside NET-1. | NET-4B/C2 publication remains unavailable until reward-window and sink identity/custody inputs plus their required evidence exist. |
| Quorum/stake/custody/economic values | MQ-056/MQ-057; `OWNER-NET-01` reserved inputs | Not needed for local read-only adapter development and not selected here. | Validator agreement, chain publication, settlement, deployment, and economic activation remain unavailable. |

## 3. Selected C0 ticket board

Only the active ticket is materialized on this initial board. NET-2 through
NET-6 retain the roadmap order above but remain unselected, unstarted, and
outside this transition; their ticket-local contracts must be created
prospectively when selected rather than inferred from roadmap prose.

| ID | Deliverable | Status | Evidence | Driver | Accountable reviewer | Depends on | Master questions | Effort | Target |
|---|---|---|---|---|---|---|---|---|---|
| NET-1 | Pinned read-only ChainAdapter, network/metagraph snapshots, wallet/hotkey and UID association, and classified provider failures | in_progress | `.agent/evidence/wave_c/net-1.md`; `.agent/plans/NET-1_chain_adapter.md` | Codex + network/protocol engineering | Network/protocol + security | B-GATE | MQ-054, MQ-056 | M | C0 |

Effort ranges reuse launch v1.0.5 and remain provisional. NET-1 is M (two to
three primary-lane days); later values are planning estimates, not approval
gates or dates.

## 4. NET-1 acceptance and maturity ceiling

NET-1 follows `.agent/tickets/NET-1_chain_adapter.md`. It may earn only bounded
`SPECIFIED`, `IMPLEMENTED`, and `TESTED` states for local read-only translation.
It cannot earn `SECURITY_QUALIFIED`, `NETWORK_QUALIFIED`, `PRODUCTION_QUALIFIED`,
LIVE, testnet, mainnet, weight, transaction, custody, or settlement authority.

After NET-1 passes its recorded Definition of Done, applicable ready-revision
acceptance, `Merge gate`, and normal expected-head merge, NET-2 is the next
dependency-ready network ticket. This task does not begin NET-2.
