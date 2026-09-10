# NET-6 — Disposable network operations and recovery

**Wave:** C0 network foundation
**Status:** `in_progress`
**Depends on:** NET-5
**Primary Hub map_ref:** `WAVE-C/NET-6`
**Evidence:** `.agent/evidence/wave_c/net-6.md`
**Starting main:** 95fa1e42dbf8d5fdcfde80d440eb38229b2764db (PR #126).
**Authority:** OWNER-C0-REWARD-01, OWNER-DX-03, OWNER-C0-VALIDATION-01;
constitution/invariants, Build Out/overlay, launch v1.0.6, NET-1 through NET-5,
NET-2 receipt journal, NET-3 accepted fixture owner, reward ledger and A6 disclosure.

## Working contract and dependency plan

KEEP the existing chain isolation, journal, reward/intent and publisher owners.
WRAP them with explicit operator lifecycle. No new evaluator, accepted flag,
SDK default network, arbitrary import factory, treasury or public service.

1. Implement read-only health and consistent SQLite backup/restore with explicit
   context/schema/digest checks, bounded input and no overwrite of existing state.
   Preserve every receipt, nonce, accepted provenance, credit age and pending
   dispatch. A backup checksum is integrity evidence, not external authentication.
2. Add an exclusive process lease, explicit signal shutdown and guarded five-second
   development heartbeat/reconnect/backfill. Check actual isolated container,
   expected genesis/runtime and journal context before reading an external key.
   Health must retain stale stored-weight exposure and pending liabilities.
3. Reuse fixed fixture registration for restoring the publisher from its private
   journal. Provide explicit local configuration and disabled public configuration
   schemas. Never infer real parameters or supply production credentials.
4. Supply reproducible node startup/shutdown, private state retention, operator
   commands, journal/capacity recovery, backup/restore and pinned upgrade workflow.
5. Test operator contracts and, if available, an independently labeled all-burn
   operations rehearsal. Do not rerun unchanged failed miner registration, skip it
   into a full-localnet pass, or turn operator tests into G2/science qualification.
6. Preserve precise G2 NOT_READY and a concrete compatibility/C1/C2 handoff, with
   C-EA0 through C-EA3 dependencies and existing scientific DoDs unchanged.

## Definition of Done

- [x] Executable explicit operator config, one publisher lease, startup/shutdown,
      external secret input and endpoint/genesis/runtime mismatch rejection.
- [x] Read-only allow-listed health, pending dispatch/stale exposure/capacity status,
      reconnect and bounded reconciliation before new issuance.
- [x] Consistent backup and atomic no-overwrite restore preserve all logical journal
      state across crash/restart; tamper/context/schema/path failures are tested.
- [x] Operator runbook and reproducible pinned node/runtime/image/SDK upgrade commands;
      public-network configuration remains inert with unresolved inputs explicit.
- [ ] Meaningful focused tests, all applicable canonical acceptance and Hub checks;
      actual operator-runtime observations or exact environmental failure retained.
- [x] Evidence-backed G2 disposition and exact C1/C2/archive handoff, without claiming
      unavailable shared-winner runtime or real scientific evidence.

## NET-6-D1

Use an OS-owned advisory file lock on the canonical journal path; crashes release
ownership without deleting a lock inode or guessing from reused PIDs. Backups use
SQLite's consistent backup API and explicit schema/context manifests. Restore to
a new destination only; no automatic reset, pruning, replay or liability deletion.

The operator runs only against the inspected pinned internal Docker container.
Loopback relays are process-owned and may reuse explicitly configured local ports
so a restart preserves the complete journal context. A separate external file
supplies only a throwaway publisher key after chain verification. No import-time
SDK/network/key access. Public schemas stay disabled and reject activation.

Alternatives rejected: PID-only locks, raw SQLite file copies during writes,
arbitrary adapter factories, live reconfiguration and automatic ambiguous resend.
All weaken ownership or provenance. Changes are reversible by replacing the
operator wrapper; journal history remains owned by the existing modules. Supersede
this decision in this ticket and carbon/chain/operations.py if necessary.

NET-5's all-burn/recovery evidence is earned; required shielded miner registration
is incompatible in the observed setup. Shared-winner/recycled-UID runtime proof
and G2 readiness remain unearned. Production custody/quorum/science/security and
public deployment inputs block their operations only. B-E4 stays optional/deferred/
non-blocking and UNMEASURED; B-01G remains unfinished/non-blocking.

Actual operator run 34431662096 passed on the pinned isolated runtime. The final
canonical engineering acceptance and merge remain pending; the remaining DoD
checkbox is not satisfied by native diagnostics or that separate runtime lane.
