## 2026-10-07 — OWNER-AX42-DOOR-PRIVATE-01: the AX42 validator door stays private

**Authority.** The owner, 2026-10-07. The decision was relayed verbatim by the
Test Lead session to the Launchpad Acceptance session. It answers
`docs/development/LAUNCHPAD_ACCEPTANCE_PLAN.md` §8, decision 2 (PR #769):

> grant full, AX42 stays private, approve all

**Context.** Rehearsal 3a's valV2 validator door, on the AX42, binds to
loopback. The owner's PC reaches it through the tunnel account with
`ssh -L 18467:127.0.0.1:8467`. The plan asked whether that door should get a
public TLS exposure, so that an endpoint could be published for every miner.

**Decision.**
1. **The door is not exposed publicly.** It stays loopback-only and is reached
   only through the owner's tunnel.
2. **`scripts/dev/miner_launchpad/published_endpoints.json` stays empty.**
   - The tunnel target is not published. A loopback address that works only
     for hosts holding the tunnel key would mislead every other miner.
   - Rehearsal miners name it in setup Review as their own intake, with its
     pinned receiver (LAUNCHPAD-ACCEPT-03 and -04).
3. **A future public testnet door goes on a separate, validator-only host,**
   after a security review.
   - The Test Lead brings that proposal to the owner after rehearsal 3a.
   - Exposing it and publishing its endpoint will need their own owner
     records.

**Scope.**
- This changes nothing on the AX42.
- It changes no intake or validator code, and no chain, scientific or
  economic value.
- OWNER-INTAKE-EXPOSURE-01 and OWNER-ANSWER-KEY-INTAKE-EXPOSURE-01 are
  unchanged.

**No execution** happens through this record.
