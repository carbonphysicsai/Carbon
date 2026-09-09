# NET-3 — Candidate commitment, availability and accepted fixture bridge

**Wave:** C0 network foundation
**Status:** `done`
**Depends on:** NET-2
**Primary Hub map_ref:** `WAVE-C/NET-3`
**Evidence:** `.agent/evidence/wave_c/net-3.md`
**Starting main:** 97725a1f4c6c8c65234e96770c847622273fc55e (PR #121).
**Authority:** OWNER-C0-REWARD-01; OWNER-C0-VALIDATION-01; DELIVERY_PROTOCOL.

## Working contract and plan

KEEP A7 Strategy identity, SubmissionService, A8 TrainEvalAPI and A6 publication.
WRAP them in carbon.candidates. Extend the existing NET-2 SQLite journal with
bounded candidate/artifact rows. Resolve authenticated receipts and verify exact
signed body bytes before commitment. Register immutable DEVELOPMENT evaluation
context explicitly; no miner-selected evaluator, ScorePack or acceptance flag.

1. Persist canonical available Strategy artifacts, original receipt provenance,
   challenge/ScorePack/evaluation identity and global per-version artifact reuse.
2. Bind evaluation to A7 admission and run only the injected existing A8 fixture
   evaluator. Adapt successful A7 publication to a nominal fixture-only accepted
   record retaining exact scientific score bytes and aggregate components.
3. Test replay, copies/wallet changes, ordering, altered context, unavailable
   artifacts, completion, mandatory failure, restart and interrupted dispatch.
4. Reconcile authority/Hub, focused canonical acceptance and expected-head merge.

## Definition of Done

- [x] Commitments resolve NET-2 receipts, bind signed bytes and registered context,
      retain original receipt order/hotkey/registration and canonical A7 identity.
- [x] Artifact bytes are available in the same durable bounded journal and checked
      on use. Copies or wallet changes share one artifact evaluation identity;
      commitment alone never earns improvement credit.
- [x] Submission, admission, execution, acceptance and disclosure are distinct.
      Existing A7/A8/A6 own each applicable transition; no second evaluator or
      caller-controlled accepted Boolean and no arbitrary execution path.
- [x] Accepted fixture records retain binary64 score bytes, ScorePack identity,
      original receipt provenance and aggregate component scores. They cannot
      construct real scientific/frontier/LIVE authority.
- [x] Exact replay is idempotent; conflicts fail. Restart preserves committed and
      completed records. Interrupted process-local A7 attempts stay indeterminate
      and cannot be blindly dispatched again. Capacity/errors are bounded.
- [x] Focused chain/transport/candidate/A7/A8 tests, invariants, package/quality,
      Hub and required Merge gate pass. No localnet or real science is claimed.

## Decision NET-3-D1

Use the existing receipt journal as the durable candidate substrate and preserve
A7's canonical Strategy hash. Separate signed receipt order from processing order.
A8 completion enters a fixture-only accepted projection only after A7 publication.
The alternative of a generic accepted flag or a second scoring service would
weaken scientific ownership. Serializing A7 private state would bypass its owner;
interrupted attempts instead require explicit reconciliation. This is a reversible
new namespace/schema with no existing public interface migration. Supersede this
decision and carbon/candidates if changing it; C-REWARD consumes resolved fixture
records, while C1 retains durable real execution/evidence archive dependencies.
No reserved scientific/security value is selected. Development settings: 10,000
candidate artifacts, 64 KiB each, immutable per-version evaluation context.
Hub impact is map_structural; affects WAVE-C, NET-2, SYSTEM/CI and maturity.

After accepted merge C-REWARD is next under standing owner authorization.

## Accepted delivery

PR #122 head f5fef50e02de88cb4e6e0733de4341dfd973ef15 passed run 34411892285
and normally merged as d55fdeb4d9be6f25f963eac0ed608414dbf0b4e6, preserving
tree 918390925c23651195526355dab31ecc0aa39abc. Completion:
https://github.com/carbonphysicsai/Carbon/pull/122#issuecomment-5609589672.
Bounded fixture commitments are SPECIFIED/IMPLEMENTED/TESTED only.
