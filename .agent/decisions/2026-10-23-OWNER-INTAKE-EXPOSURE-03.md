# OWNER-INTAKE-EXPOSURE-03: the one public testnet validator's intake, through the Cloudflare Tunnel

Date: 2026-10-23
Status: **ACCEPTED by the owner, directly in the Carbon Validator's session.** The owner chose "Accept as scoped" to the question: "Do you accept OWNER-INTAKE-EXPOSURE-03 for testnet only: the 4090 validator's public submission address through the Cloudflare tunnel at intake.carbonphysics.ai, with exactly two routes open (the submission info page, and submitting a model or checking its status, for the 4 launch Challenges), the same go-live steps as before, and the 4 named risks (…)?"
Scope: `codex-queue/reports/VALIDATOR_INTAKE_EXPOSURE_03_SCOPE_20261023.md`, sha256 `da4b004120898e2eeb11b0c891436fac1bef2f45636937b4765a053a0f881951`.
Builds on: OWNER-INTAKE-EXPOSURE-02 (the same trusted-proxy design, #1267, PLT-15) and OWNER-ONE-PUBLIC-VALIDATOR-01.

## Accepted (testnet 567 only)

1. **The listener:** the one public validator's construction intake, on the team's monthly dedicated RTX 4090 host. It is reached from the internet only through a Cloudflare Tunnel at `intake.carbonphysics.ai`, in `exposure: {via: trusted_proxy, header: CF-Connecting-IP, record: OWNER-INTAKE-EXPOSURE-03}` mode. The bind stays loopback.
2. **The routes, an exact allow-list:** `GET /carbon/v1/construction/intake` and `POST /carbon/v1/mcp` (`construction_submit` and `construction_status` only), for F08, F02, Motor and Cooling. Everything else returns 404.
3. **The limits:** PUBLIC_INTAKE_01 §4, plus the intake's own limits.
4. **The go-live gate, strictly in order:**
   1. the offline ingress check;
   2. §5.3 as a hard go/no-go while the URL is unpublished, plus the added checks (internal routes 404, tool allow-list, end to end on all four Challenges). Any miss means rollback (§6.6);
   3. the endpoints entry merges only after a go.
5. **The forged-header test** has the three outcomes of EXPOSURE-02 (PASS only on the intake's own `429 {"refused":"rate"}`), with a negative control first. The record says how the edge rule was handled.
6. The AX42 tunnel is retired before the hostname moves.

## Residual risks accepted by name

1. The listener runs on the host that holds the sealed exam copies and the validator's private state.
2. Cloudflare terminates TLS and can read submitted recipes in transit.
3. Inbox exhaustion under a distributed flood fails closed with 503.
4. The host is rented, so the provider has physical access.

## Not covered

Mainnet exposure; stand-in hosts or records; any route beyond the two above; any later change to the host, routes or limits (that needs a new acceptance).
