# C-W1-D1 public/synthetic DEVELOPMENT testnet evidence

**Decision:** `OWNER-C-W1-DEV-TESTNET-01`
**Ticket:** distinct bounded slice under C-W1; official C-W1 remains open
**Profile:** `carbon.public-synthetic-testnet.development.v1`
**Disposition:** PR #183 foundation accepted; operator continuation candidate;
no public transaction executed

## Implemented candidate

- Generalizes the accepted localnet publisher only through exact issuer type,
  intent type, network and runtime bindings; localnet defaults and tests remain.
- Resolves an authenticated NET-2/C-08 request from its durable journal and
  cross-binds the associated C-07 account and active C-06 signed receipt.
- Emits only a short-lived all-burn DEVELOPMENT projection while scientific
  comparison is unresolved. Official `TestnetWinnerWeightIntent` remains
  unconstructible.
- Requires an exact testnet transaction authorization and durably consumes it
  for one intent effect; checks finalized block window, registered publisher,
  burn sink, stake/permit-or-owner, runtime, integer vector, dispatch,
  finalization and row readback through existing owners.
- Retains at most 2 GiB in local review/export storage, records exact evidence
  and export-manifest digests, and explicitly declares host-loss recovery and
  archive acknowledgement false.
- Adds a secret-free operator config and read-only doctor. The doctor cannot
  sign or publish and reports host, Docker, disk, SDK, chain, registration and
  authorization predicates separately.
- Adds a closed controller-produced source handoff and fixed operator
  `run`/`status`/`resume` commands. The operator validates active C-06 evidence,
  C-08 association, the C-07 account, C-03 image/resource identities, exact
  transport/publication context, configured path roots and every export member.
  Export hashing is streamed; duplicate, changed, symlinked or over-limit
  members reject.
- Separates chain-transaction readiness from full host/execution readiness and
  retains observed registration/UID and capability facts on a policy denial.
  A failed chain observation stays unknown. Resume uses no wallet and cannot
  resubmit or rerun numerical work.

## Local evidence before acceptance

```text
pytest C-W1-D1/C-08/NET-4B/NET-6 focused set
87 passed, 8 skipped

operator doctor, shipped incomplete example
Darwin arm64; 8 GiB RAM; Docker unavailable; pinned SDK absent;
netuid and transaction authorization missing; transaction_ready=false;
writes_performed=false; protected_or_official_eligible=false
```

The skips are existing installed-SDK tests on the native environment. They are
not public-chain evidence. The earlier accepted NET-5R/G2 localnet and C-03/
C-07/C-08 service campaigns are reused only for their exact bounded
capabilities and are not rerun or relabeled as public-testnet observations.

PR #183 accepted exact head `324a5276cd6a1ffdc491d04d08ef8b3282a060e8`
in required run `34927991086` and normally merged as
`bd7e5a5423d1148d340b3de3993068b66f5973d9`; accepted and merged tree were
`65e2a3d5abee97e5eaf1538050e0dcfab22cc649`. The focused operator continuation
currently passes 22 C-W1/C-08 CPU tests plus Black/Ruff on changed Python files;
its exact-head repository acceptance and merge remain pending.

## Read-only public-testnet preflight

The exact pinned `bittensor==11.1.0` source/package observed endpoint
`wss://test.finney.opentensor.ai:443`, genesis
`0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105`,
runtime spec 458 and transaction version 1. A scan of available netuids at the
observed finalized state found no registration for the configured public
hotkey. No wallet secret was read and no transaction, registration, funding,
subnet creation, weight publication or spend occurred.

## Unearned claims and execution blocker

The merged PR #183 foundation is `SPECIFIED / IMPLEMENTED / TESTED` in its
bounded scope. The operator continuation is locally implemented/tested but
remains conditional on exact-head CI acceptance and merge. Neither is
scientifically, security, archive, network, protected, production or LIVE
qualified. Separate containers do not prove independent administration. Local
storage does not prove host-loss recovery. A signed receipt or finalized
all-burn row would not prove a candidate winner, reward, payment or epoch result.

Public execution is blocked on a selected existing netuid, observed
registration/UID and weight-setting prerequisites for the named public hotkey,
an eligible authorized Linux host, any exact bounded testnet registration cost,
and a block-bounded one-dispatch owner transaction approval. Ambiguous writes
must reconcile before retry.

AWS deployment is deferred without spend. Hippius is preferred for a future
bounded storage assessment but remains wholly unverified against Carbon's
archive/custody/retention/recovery and acknowledgement contracts.


## 2026-09-15 owner-selected supervised Burgers continuation

PR #185 merged the operator path. Subnet 567, publisher UID 0, new owner/publisher
wallet identities and WSL Ubuntu/Docker supersede the former missing-host/netuid
blockers. Creation finalized at block 8010852 for 1.003183218 test TAO. Historical
wallet and host receipts above are unchanged. The current distinct miner is
unregistered; no new activation, registration or publication was dispatched.

The executable v2 subset and prospective time-range repair are frozen in
`docs/development/CW1_BURGERS_AGENT_SESSION.md`. Numerical engineering validation
completed 36 reference workers, three real JAX training replicas (96 updates),
three isolated predictions and 72 measurements. One prior worker failed before
training updates; its evidence and the original cohort remain retained. Recorded
controller wall time totals 403.21 seconds, excluding software tests/CI. This is
not model inference, an authenticated miner result, a scientific pass or a winner.

The supervised service, exact unqualified admission, disclosure projection and
source builder are an engineering candidate until normal automated acceptance
and merge. Focused canonical session/C-08/C-W1 checks passed 31 tests. Model-run
approval/credential and distinct miner registration remain external inputs.
All-burn authorization remains separate from activation and creation. Primary
Hub map is `WAVE-C/C-W1`; competition successor is defined, not activated.
