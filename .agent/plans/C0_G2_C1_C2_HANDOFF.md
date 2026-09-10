# C0 evidence-backed G2 disposition and C1/C2 handoff

**Disposition:** G2 NOT_READY. This is an engineering evidence assessment, not
human launch approval. NET-1 through NET-6 and C-REWARD are merged in bounded scope. PR #127
passed canonical acceptance and the distinct operator rehearsal. These cannot fill the
missing shared-winner runtime evidence. No public deployment occurred.

| G2 requirement | Evidence and remaining boundary |
|---|---|
| Chain identity/SDK boundary | NET-1, PR #120; SDK 11.1.0 and exact lock, finalized contextual identity and installed-source contracts |
| Authentic submission and accepted fixture integration | NET-2/3, PR #121/122; signed domain/context, durable receipt/replay, existing A7/A8/A5 acceptance |
| Reward/disclosure | C-REWARD, PR #123; zero opening, Q12 gain/age/restart, multi-challenge shared winner and adversarial tests; A6 allow-list/coefficients/3-decimal display |
| Complete vectors/signing/recovery | NET-4A/4B, PR #124/125; snapshot-bound final integer check, durable ambiguous dispatch and heartbeat; no public intent authority |
| Actual local runtime | NET-5, PR #126; immutable v445 image, isolated observed genesis, actual all-burn inclusion/finality/row and epoch MinerBurned under verified Burn mode |
| Restart/outage | NET-5 run 34425822745 observed exact replay, restarted journals, actual provider pause and recovery; NET-6 adds operator lifecycle and backup/restore |
| Shared-winner / replacement UID chain effects | NOT OBSERVED. Required shielded miner registration failed with SDK Stale/expired; exact inner/carrier identities and finalized read-only reconciliation retained |
| Operator readiness | NET-6 PR #127; runtime run 34431662096 observed node restart, external-key restored publisher, heartbeat/shutdown and complete logical backup/restore; canonical acceptance run 34432281140 passed |

Application multi-challenge winner targets work in deterministic tests with
preserved per-challenge burn and aggregated shared winners. The actual runtime
has proven the all-burn path, not the complete winner path. Integer conformance
has an explicit L1 tolerance ceil(N * 10^12 / 65535); consensus/stake outcomes
and wallet receipts are separate observations. MinerBurned=1 under Burn denotes
the measured miner fraction, not proof that owner cuts/dividends or all network
emissions burned. Treasury is absent and remains optional.

## Exact remaining operation

Resolve required shielded BurnedRegister compatibility between the pinned SDK
11.1.0 and v445 fast localnet without bypassing SDK policy or issuing unchecked
extrinsics. Preserve inner and carrier hashes, era/nonce, inclusion and finalized
readback. Timing/key rotation is only a hypothesis; no cause is established.
Then execute the existing full scenario:

```sh
CARBON_UV_GROUPS=chain ./scripts/dev/bootstrap.sh
CARBON_LOCALNET_MODE=full ./scripts/dev/localnet.sh .carbon-artifacts/localnet
```

Its prerequisite is a functioning canonical Linux amd64 Docker host and a tested
compatibility resolution, not treasury funding, production credentials, paid
inference or five new human approvals. The current Windows host lacks a working
Docker daemon; GitHub Linux has already supplied actual runtime evidence. Do not
retry the unchanged failing registration or relabel operator-only success as G2.

## Concrete next C1 and C2 contracts

The exact first C1 ticket is `.agent/tickets/C-01_durable_execution_state.md`,
materialized from the existing durable-state/queue/recovery scope. Its A7/B-GATE
implementation dependencies are delivered; C1 execution is not selected while
G2 remains unresolved. C-02 then reuses its existing real declarative JAX
reconstruction DoD and B-02B/B-03/B-E1 dependencies. C-06/C-07 retain signed
receipts, protected execution and orchestration requirements. No synthetic C0
receipt is real scientific evidence.

C-EA0 depends on B-GATE plus the current C1 execution design and its original
capture/attempt/custody/retention/acknowledgement owner decisions. C-EA1 still owns
PostgreSQL metadata and encrypted/versioned objects under an approved fault and
custody model. C-EA2 still gates real finalization on verified archive durability;
C-EA3 still owns recovery/availability qualification. NET-6 SQLite backup neither
replaces these tickets nor satisfies their DoDs.

The exact first C2 ticket is `.agent/tickets/C-W1_testnet_eligibility.md`;
it is not dependency-ready until the real C1 receipt and required C-EA2 archive
acknowledgement exist. C-W2, C-W3 and C-W4 retain their existing expiry/sink,
agreement/publication/recovery and Alpha Report responsibilities. Current owner
authorization does not activate a public network or infer missing testnet policy.

B-E4 remains OPTIONAL / DEFERRED / NON-BLOCKING; empirical prior effectiveness
UNMEASURED. B-01G remains actually unfinished and non-blocking. Neither returns
to the C0/C1/C2 launch critical path. Scientific, frontier, security and launch
qualification remain unearned by changing the payment route.
