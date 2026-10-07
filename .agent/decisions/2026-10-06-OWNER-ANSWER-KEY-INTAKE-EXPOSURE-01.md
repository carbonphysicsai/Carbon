## 2026-10-06 — OWNER-ANSWER-KEY-INTAKE-EXPOSURE-01: the answer-key distribution host may bind publicly

**Authority.** The owner, 2026-10-06:
- to the Test Lead: "Approve download server";
- confirmed directly in the Carbon Validator session: "Approve as scoped".

The owner chose the name `answers.carbonphysics.ai`. This is the owner's
security call under AGENTS.md §13. It supplements OWNER-SHARED-ANSWER-KEY-01,
VALIDATOR-18's two-host design and OWNER-REHEARSAL-AND-RELEASE-01.

**Scope.** It permits exactly this public bind (`intake.require_exposure`):
1. **The host:** one Hetzner Cloud server at `answers.carbonphysics.ai`, the
   owner's spend. It was first approved as a CX23, about €5.49/month. The
   owner then approved a **CPX12** (1 vCPU, 2 GB, x86, Ubuntu 24.04, IPv4 and
   IPv6, about USD 13.49/month), because CX23 to CX53 were out of stock
   (2026-10-07, relayed by the Test Lead). Its TLS certificate comes from
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

**Amendment, 2026-10-07 (host type only).** The host is a Hetzner Cloud CPX12.
The scope above, items 2 to 5, is unchanged: public HTTPS on 443 only,
permit-holder `btauth/1` fetches, per-hotkey logs, no root, solver or private
key on the host, and push-only from the producer. The producer pushes over
key-only SSH on the public interface; Hetzner's private network is not used.

**Amendment, 2026-10-07 (the public training pool).** OWNER-AUTO-PUBLISH-RETIRED-01
adds one public, read-only path to this host: `GET /carbon/v1/training/<challenge>[/<file>]`.
It serves only signed training files of retired bank cases, each verified
before it is served, with every request logged. Items 2 to 5 are unchanged
for answer-key packages: they still go only to permit holders, signed and
logged per hotkey.
