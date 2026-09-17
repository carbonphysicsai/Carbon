# C-W1-D1 public/synthetic DEVELOPMENT testnet profile

**Decision:** `OWNER-C-W1-DEV-TESTNET-01`
**Profile:** `carbon.public-synthetic-testnet.development.v1`
**Map ref:** `WAVE-C/C-W1`
**Scope:** bounded engineering and public-testnet demonstration only

## Dependency amendment

The official C-W1 path is unchanged and remains blocked on C-09, an eligible
real C-EA2 acknowledgement, qualified signed C1 evidence, and its remaining
scientific/security/network predicates. This prospective profile is a separate
DEVELOPMENT consumer of already accepted capabilities:

```text
NET-2 + C-08 authenticated request association
  + C-01/C-03 isolated execution
  + C-06/C-07 signed DEVELOPMENT account
  + C-10 disagreement/quarantine semantics
  + NET-4B/NET-6 checked weight publication lifecycle
    -> C-W1-D1 public/synthetic DEVELOPMENT testnet demonstration
```

Dependency classification for this profile:

| Class | Required capabilities |
|---|---|
| A — required now | public/permission-cleared inputs; authenticated request and replay protection; isolated C-03 limits; exact C-06/C-07 association; cancellation/failure/quarantine; signed DEVELOPMENT evidence; bounded local review/export retention; exact public-testnet context, registered publisher UID, runtime capabilities, explicit transaction authorization, durable dispatch/finalization/readback |
| B — protected/official only | eligible real C-EA1/C-EA2 acknowledgement; provider durability and host-loss recovery; protected data custody; official C-09 result; qualified science/reference/measurement/repeat policy; independent security acceptance; production signer and activation |
| C — optional/provider research | AWS deployment; Hippius compatibility and qualification; B-E4; treasury |

Class B and C items cannot be laundered through this profile. DEVELOPMENT
receipts retain every official, protected, score, archive, network and reward
eligibility field as false. The profile issues its own short-lived,
one-dispatch permission only after the source receipt is active and the exact
authenticated request-to-account association resolves.

## Frozen behavior

- Data: public/synthetic and permission-cleared only.
- Reconstruction: accepted C-03 Linux x86-64 CPU profile; one worker, two CPUs,
  4 GiB memory/no swap, 256 tasks, 512 MiB scratch, 600-second productive
  deadline, five-second cancellation grace and 30-second cleanup confirmation.
- Evidence retention: at most 2 GiB of local DEVELOPMENT evidence with an
  operator-generated export manifest. Same-host storage is explicitly not
  host-loss recoverable and creates no archive acknowledgement.
- Publication: testnet only; exact endpoint/genesis/netuid/runtime/publisher;
  one approved `SubtensorModule.set_mechanism_weights` dispatch, mechanism zero,
  zero TAO value transfer, and finalized row readback.
- Scientific disposition: unresolved/unqualified. Until a qualified comparison
  selects a winner, the only permitted complete vector is 100% to the verified
  subnet-owner burn sink. Signing and publication do not make it scientific.

AWS is deferred and non-blocking here. Its merged v2 package and evidence are
preserved without spending authorization. Hippius is the owner's preferred
future storage provider, but identity, integrity, encryption/custody,
retention/deletion/recovery, availability, cost, failure semantics and C-EA1
acknowledgement compatibility are all unverified. That later study is not a
dependency of C-W1-D1.

## Stop boundary

Public dispatch requires an eligible Linux host, the exact pinned SDK/runtime,
a selected existing public-testnet subnet, the named hotkey registered there,
observed UID/permit-or-owner/stake capability, testnet funding if registration
requires it, and an exact owner transaction record. Missing values stop chain
writes only; they do not reopen the official path or authorize a new subnet.

## Operator execution boundary after PR #183

PR #183 accepted and merged the profile/issuer/publication/preflight foundation.
The continuation adds one closed controller-to-operator handoff and fixed
`run`, `status` and `resume` commands. The handoff resolves the exact C-08
authenticated request, C-07 account and C-06 active signed receipt, streams and
hashes the bounded export without loading an artifact-sized member into the
controller, and binds its authenticated testnet context to the configured
publication context. All referenced journals must remain under the configured
retention root and all exported bytes under the configured export root.

`run` performs fresh read-only readiness before wallet access, records one
short-lived intent immediately before publication, and uses the existing
checked SDK publisher. `status` never accesses the wallet or network. `resume`
opens no wallet and reconciles only a previously journaled hash; it cannot
dispatch, sign or repeat C-08/C-03/C-07/C-06 work.

## Unselected score-based successor

The smallest later competition slice can KEEP C-05 measurement outputs, C-10
quarantine and C-REWARD's deterministic activation/takeover/decay arithmetic.
It must first add a separately authorized DEVELOPMENT-only comparison and
eligibility bridge from active signed evidence. C-REWARD's current fixture
ledger cannot be relabeled for that role, and an unresolved or quarantined
receipt cannot name a winner. No such successor is selected or implemented by
this continuation.

## C-W1-REVEAL-01 — decoded reveal and bounded recovery

**Working decision:** IMPLEMENTATION_LAG, selected 2026-09-16 under the existing
C-W1-D1 continuation; primary map `WAVE-C/C-W1`, `HUB_UPDATE_REQUIRED`.
Starting base: `405a820bfdd5a38aa2d498e3dbde3fa15449379f` (accepted PR #194).

The real runtime-460 reveal event at finalized block 8017851 is decoded by the
pinned SDK as tuple attributes. The adapter accepted only list/dictionary forms,
so the durable read cursor passed a valid event without recording it. Independent
read-only queries observed the exact all-burn row and empty pending commitments;
those observations do not permit hand-editing the journal to declare success.

KEEP the signed source, frozen cohort, transaction identities, fee guards and
existing publisher. REPAIR exact event matching to accept the SDK tuple shape
alongside supported list/dictionary shapes, with exact subnet and hotkey checks.
Add an explicit `resume --rescan-reveal` recovery option: only for a previously
finalized timelocked commitment whose reveal is unresolved; restart event reads
at its retained finalized inclusion plus one, retain the existing 256-block limit,
and persist the cursor through the existing journal owner. Subsequent ordinary
`resume` calls continue from that cursor. Existing terminal records are unchanged.
No caller-supplied block, event, transaction result or stored row is accepted.

This read-only recovery grants no signing, wallet, resend, science-rerun or new
transaction authority. It keeps exact row/exposure checks and historical journal
events. Repeated explicit rescans may repeat reads but cannot repeat dispatch.
Automatic unbounded backfill and direct journal edits were rejected: the former
changes operator latency/budget semantics; the latter bypasses chain evidence.

Plan and expected manifest: `carbon/chain/sdk_weights.py` event decoder;
`carbon/chain/publisher.py` bounded rescan; DEVELOPMENT execution/operator option
plumbing; focused SDK/publisher/operator regression tests; this plan, ticket,
runbook/session/transaction observations, boards and generated Hub. No dependency,
worker, evaluator, metric, scoring or reward-policy change is intended.

Validation: focused canonical baseline and regressions; wrong subnet/hotkey,
malformed event, tuple/list/dict, advanced cursor, 256-block continuation,
terminal/no-dispatch behavior, walletless operator forwarding; all invariants and
applicable classified CI. After tested repair, use the supported rescan on the
existing source and let the journal record actual reveal and row observations.
Normal expected-head merge and bounded execution closeout follow OWNER-DX-03.

Reversibility: remove the optional recovery argument and tuple normalization to
supersede this implementation; retain already recorded observations and receipts.
No human-reserved scientific/economic value is selected and no new transaction is
requested. Completion remains conditional on passing acceptance, normal merge
and observed `ROW_VERIFIED`. All qualification and official-path ceilings remain.
