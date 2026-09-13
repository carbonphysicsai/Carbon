# C-03 — Isolated reconstruction worker

**Wave:** C1 real scientific execution foundations
**Status:** `future_reserved`; contract materialized, unselected and unstarted
**Depends on:** C-02; MQ-015 security/threat-model decision
**Owner:** Codex + execution/SRE engineering
**Accountable reviewer:** Security + protocol + Physics/SciML
**Authority:** retained C-03 identity from launch v1.0.3 §6.3; current C1
scope in launch v1.0.4 §4.2; `Design_Specs/Build_Out.md` §§3 and 14;
`docs/context/MASTER_OPEN_DESIGN_QUESTIONS.md` MQ-015

## Goal

Execute the exact C-02 producer-independent reconstruction request as hostile
input inside a pinned, resource-bounded worker without exposing validator or
official-exam material and without acquiring scientific-result authority.

## Boundary and dependencies

C-03 wraps C-02's actual authorized JAX adapter; it does not invent that
adapter, accept arbitrary participant code, or reinterpret a Strategy. C-02
must first bind an authorized repository, immutable revision, reproducible
build and actual training/inference interface. MQ-015 remains
`SECURITY_REVIEW_REQUIRED`: exact real execution capabilities, enforcement
profiles, hardware classes and production security acceptance are human-owned.

The worker must deny network access, mount only a fresh scratch filesystem,
apply registered CPU/GPU/RAM/VRAM, wall-clock, process/PID and output limits,
pin image/environment/dependency identities, isolate cancellation and cleanup,
and expose only bounded redacted diagnostics. A reconstruction worker may
receive only the authorized TRAIN inputs and replica-specific derived
reconstruction randomness required by C-02. It receives no A4 master entropy,
protected EVAL seeds/cases, reference answers, validator secrets or signing
keys.

The first profile proposed for owner/security review is one trusted host,
pinned worker code, untrusted declarative parameters/arrays, CPU-only local
resources, no outbound network, and bounded scratch/output. It is not selected
or security-accepted. MQ-015 must still name threat actors/trust boundary,
image and hardware class, exact CPU/memory/wall/PID/output limits,
filesystem/network enforcement, cancellation/descendant cleanup, audit
evidence and accepted residual risk. Host-root corruption and hardware side
channels remain outside the proposal absent another approved mechanism.

## Failure and lifecycle contract

- Admission validates exact source, plan, environment and resource identities
  before dispatch; unknown or absent policy stays fail closed.
- Cancellation is terminal for that attempt unless the source lifecycle
  authorizes a linked retry or re-execution. Cleanup must terminate descendants,
  revoke scratch access and preserve the source-owned attempt record.
- Timeout, resource exhaustion, worker loss, image/runtime failure and cleanup
  failure are typed infrastructure outcomes. They are never candidate physics
  failures, measurements, scores, receipts or archive acknowledgements.
- Bounded outputs are validated before association. Partial, oversized,
  malformed, cross-attempt or late output cannot replace an accepted result.
- Retry and recovery preserve C-01/C-02/C-EA attempt identities and never
  resample protected work or overwrite history.

## Definition of Done

- [ ] C-02's exact authorized JAX revision/interface and reproducible runtime
  are available; no prototype or forward-pass parity substitutes for them.
- [ ] A threat model names every participant-controlled input, host capability,
  secret/protected boundary, side channel, kill path and residual risk.
- [ ] Canonical service-backed tests prove network denial, scratch-only access,
  CPU/GPU/RAM/VRAM/wall/process/output enforcement, cancellation and complete
  descendant cleanup.
- [ ] Escape, traversal, device, fork/process-bomb, oversized-output, log,
  timing, stale/cross-attempt, retry/replay and abrupt-worker-loss tests fail
  closed without hidden-evaluation leakage.
- [ ] Typed infrastructure failures remain distinct from reconstruction,
  reference, measurement and scientific failure throughout C-01/C-02/C-EA
  association and recovery.
- [ ] Security review accepts the exact bounded execution profile before any
  real or protected workload uses it.

## Authority ceiling

Contract materialization only at this checkpoint. No worker implementation,
real execution, scientific/security qualification, public network, production
or LIVE authority exists.
