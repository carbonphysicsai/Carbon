## 2026-10-13 — OWNER-INTAKE-EXPOSURE-02: testnet public battery intake through a Cloudflare Tunnel (trusted-proxy exposure)

**Authority.** The owner, directly in the Carbon Validator session on 2026-10-13, verbatim:

> OWNER-INTAKE-EXPOSURE-02 — accepted, for the testnet public intake, at the scope in PUBLIC_INTAKE_01 §7.
>
> I accept the trusted-proxy and tunnel exposure design as implemented and tested in #1267. Go-live is gated on all of the following, in order:
>
> 1. The offline ingress check passes before the intake starts.
> 2. §5.3 passes as a hard go/no-go, with the URL unpublished until it does: the forged-header test and the edge rules. Any miss is a rollback (6.6), not a judgement call.
> 3. #1255 merges only after a go.
>
> On the forged-header test specifically: the pass condition is the intake's own 429 with body {"refused":"rate"}. A 429 from Cloudflare's edge, a Cloudflare error page, or any other body is INCONCLUSIVE and is not a pass — record it as a third outcome, not a green tick. Establish what Cloudflare's own 429 looks like on this zone first, so the real test has a negative control, and either run the test before the dashboard rate rule is enabled or keep the probe under the edge threshold. Say which was done in the record.
>
> No stand-in VM and no stand-in exposure record. I understand that this means the first real-Cloudflare test happens on the AX42, with the URL unpublished and rollback ready.
>
> This acceptance covers the testnet public intake only. Mainnet exposure is a separate acceptance and I have not given it.

The PR Head put the same acceptance to him directly and he confirmed it in that
session on 2026-10-13, before this record was merged: this exposes an endpoint
to the public internet, and such an acceptance is not recorded on a relay alone.

**Decision.**
1. **The listener.** valV2's battery intake on the AX42 may be reached from the internet through a Cloudflare Tunnel at `intake.carbonphysics.ai`, in PLT-15's `exposure: {via: trusted_proxy, header: CF-Connecting-IP, record: OWNER-INTAKE-EXPOSURE-02}` mode (#1267, merged at `1966b271e`). The bind stays loopback.
2. **Routes and Challenge** are unchanged from OWNER-INTAKE-EXPOSURE-01: `GET /carbon/v1/battery/intake` and `POST /carbon/v1/mcp` (`battery_submit`, `battery_status`). Testnet 567, battery only.
3. **Limits:** PUBLIC_INTAKE_01 §4 (the edge allow-list, the body cap, the per-IP rate rule, the cache bypass), plus the intake's own limits.
4. **Go-live gate,** strictly in order:
   - (1) the offline ingress check;
   - (2) §5.3 as a hard go/no-go while the URL is unpublished, where any miss means rollback per §6.6;
   - (3) #1255 merges only after a go.
5. **The forged-header test has three outcomes:**
   - **PASS** only on the intake's own `429 {"refused":"rate"}`;
   - **FAIL** when all requests succeed, meaning the forged identity is honoured, which means rollback;
   - **INCONCLUSIVE** on any other 429, error page or body. That's not a pass. Re-test after fixing the probe.
   - A negative control first establishes Cloudflare's own 429 on this zone.
   - The record states whether the test ran before the dashboard rate rule was enabled, or under the edge threshold.

**Residual risks accepted** (PUBLIC_INTAKE_01 §7):
- inbox exhaustion under a distributed flood, which fails closed with 503;
- the listener on the host that holds the validator's private state (already on file in -01);
- Cloudflare terminating TLS and seeing the plaintext of signed submissions.

**Not covered:** mainnet exposure (a separate acceptance, not given); stand-in hosts or records (none).
