# NET-5 — Reproducible disposable localnet integration

**Wave:** C0 network foundation
**Status:** `done`
**Depends on:** NET-4B
**Primary Hub map_ref:** `WAVE-C/NET-5`
**Evidence:** `.agent/evidence/wave_c/net-5.md`
**Starting main:** 0e6b5e001302b349135785756c633530853684c2 (PR #125).
**Authority:** OWNER-C0-REWARD-01, OWNER-DX-03, OWNER-C0-VALIDATION-01;
constitution/invariants, Build Out/overlay/protocol extension, launch v1.0.6;
NET-1 through NET-4B, A7/A8 fixture and A6 disclosure owners.

## Working contract and dependency plan

KEEP the existing scientific acceptance, authenticated journal, reward ledger,
intent issuer and guarded publisher. Add reproducible Docker orchestration,
strictly local runtime setup and an integration harness using real SDK/chain
operations with throwaway development accounts. Source pin v445 / d3f40e4 is
independent of Bittensor 11.1.0. Pin the amd64 image by digest. Establish the
container's internal network, process-owned loopback RPC relays and observed genesis before
key construction/signing; recheck genesis/runtime at privileged boundaries.

1. Add bounded local setup and runtime evidence capture. Public SDK intents or
   tightly allow-listed public Intent extensions retain SDK policy; no arbitrary
   raw weights, global monkey-patch, chain storage injection or fake recipients.
2. Exercise authentic submissions, immutable candidates and existing A7/A8/A6
   acceptance with independently registered synthetic challenge fixtures, shared
   winners and no winner. If fixed fixture support needs extension, keep a closed
   fixture allow-list, unchanged scientific formula/thresholds and exact pins.
   Prevent multiple evaluation contexts from creating duplicate reward registers
   for the same immutable challenge version.
3. Publish complete winner/burn vectors; record transaction identities, inclusion,
   finality, applicable reveal, rows and epoch outcomes separately. Test restart,
   duplicate dispatch, UID replacement, provider outage, recovery and stale weights.
4. Preserve adversarial reward scenarios and incentives without optimality claims.
5. Run the exact runtime where available (GitHub's existing Docker runner if the
   local Windows daemon is unavailable), retain diagnostics and accurate evidence.
   Complete independent work if the environment blocks execution; G2 stays not
   ready without its required observations. NET-6 owns full operator lifecycle.

## Definition of Done

- [ ] Exact SDK/source/image/runtime pins, explicit endpoints/genesis/netuid,
      disposable role separation, isolated topology and pre-sign mismatch rejection.
- [ ] Reproducible authenticated candidate -> unchanged accepted fixture -> reward
      -> nominal localnet intent -> guarded SDK chain path, treasury entirely absent.
- [ ] Independent challenge accounting/shared winner/all-burn, accepted baseline,
      copy and identity reset protections; no caller-controlled accepted flag.
- [ ] Actual chain inclusion/finality, applicable reveal, stored row, verified Burn
      mode and sink semantics, epoch observations and quantified target discrepancies,
      or precise environmental/capability failures with the remaining operator command.
- [ ] Duplicate dispatch, restart, UID replacement, provider outage/backfill/recovery
      and stopped-publisher exposure have executable tests and clearly labeled evidence.
- [ ] Delayed/dripped gains, copying/coordinated identities, plateau and treasury
      absence/failure remain explicit non-strategy-proof development diagnostics.
- [ ] Focused meaningful development tests and applicable automated acceptance pass;
      shared evaluator/fixture changes retain full regression where required.
      Hub/authority reconciled before guarded merge. G2 disposition is evidence-based.

## NET-5-D1

Use the immutable v445 amd64 localnet image on an internal Docker network with
only loopback RPC exposure. No valuable network bridge or public service. An
isolated chain may lack external timelock beacons or MEV services; capability
absence is measured and must not be bypassed. Plain weights are a valid supported
configuration; signing/reveal behavior follows the actual observed runtime.

Existing A8 is a single closed fixture profile. Any additional synthetic exam
identity is a finite, pinned fixture-only extension of that owner, not a second
evaluator or generic execution mode. No thresholds or coefficients change.
Scientific qualification, production SLOs/security, public activation and G2 are
not inferred from synthetic tests. B-E4 and B-01G remain non-blocking.

## Bounded delivery predicate

OWNER-C0-REWARD-01 explicitly permits independent engineering delivery when an
actual runtime capability blocks one operation. This ticket can close in that
bounded scope after canonical tests/acceptance and expected-head merge while
retaining unresolved runtime assertions. That closure does not mark the full
shared-winner localnet path or G2 complete. Actual observations and the precise
shielded-registration failure are archived in `.agent/evidence/wave_c/net-5-runtime/`.
NET-6 must preserve this distinction and the remaining executable command.

## NET-5-D2 — Exact fixture migration acceptance scope

Under OWNER-C0-VALIDATION-01, use the complete focused network suite (including
all existing A7/A8, scoring and new NET-5 setup/three-exam tests), all invariants,
quality, package, Hub and required image/Merge checks. The selector recognizes
only the exact before/after bytes of the two A8 fixture-owner files and two new
fixed fixture packs. Any other evaluator, pack, threshold, dependency or unknown
path change retains full regression. This is a finite synthetic identity
extension with unchanged scoring contracts, not a general science exemption.

Broader run 34427443255 was stopped after review found a test-only batch-ID
collision across challenges. It is not a successful full-regression receipt.
The repaired test uses challenge-specific IDs just like the actual runtime
harness; conflicting replay remains rejected. A prior invariant-marker omission
also remains recorded as a failed run. No assertion is removed or weakened.
This scope avoids repeating unrelated long CPU tests for that test repair.
Alternatives: another full suite adds unrelated coverage; globally exempting A8
would lose the science fallback and is rejected. To supersede, change the exact
migration predicate in scripts/dev/select_cpu_profile.py and its regression tests.
No reserved scientific/security decision is selected. G2 remains NOT_READY.

Bounded delivery merged in PR #126 as 95fa1e42dbf8d5fdcfde80d440eb38229b2764db. Acceptance run 34429639429 passed. Full shared-winner runtime and G2 remain unearned.
