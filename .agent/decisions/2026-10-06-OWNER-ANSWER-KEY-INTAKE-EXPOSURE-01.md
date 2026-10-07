## 2026-10-06 — OWNER-ANSWER-KEY-INTAKE-EXPOSURE-01: the answer-key distribution host may bind publicly

**Authority.** The owner, 2026-10-06:
- to the Test Lead: "Approve download server";
- confirmed directly in the Carbon Validator session: "Approve as scoped".

The owner chose the name `answers.carbonphysics.ai`. This is the owner's
security call under AGENTS.md §13. It supplements OWNER-SHARED-ANSWER-KEY-01,
VALIDATOR-18's two-host design and OWNER-REHEARSAL-AND-RELEASE-01.

**Scope.** It permits exactly this public bind (`intake.require_exposure`):
1. **The host:** one Hetzner Cloud CX23 at `answers.carbonphysics.ai`,
   about €5.49/month (the owner's spend). Its TLS certificate comes from
   certbot.
2. **Access:** public HTTPS on 443 only (`distribution serve`). Every
   request must be `btauth/1`-signed and come from a hotkey that holds a
   validator permit on the subnet at the finalized block. Anything else is
   refused.
3. **Logging:** every request, admitted or refused, is logged per hotkey
   (`fetch_log`).
4. **What the host holds:** only signed, active batch packages and its own
   logs. It holds no producer root, no solver and no private key (not the
   producer's, not a validator's, not a wallet's).
5. **Direction:** the producer pushes to the host's inbox over a
   key-restricted `rrsync` account. The host never connects back to the
   producer.

**Not permitted here:** any other service, port or host, and serving any
producer-only set (tuning or confirmation). A change to this scope needs a
new owner record.
