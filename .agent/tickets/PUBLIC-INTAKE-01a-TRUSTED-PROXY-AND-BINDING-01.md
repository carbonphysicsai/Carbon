# PLT-15 — PUBLIC-INTAKE-01a TRUSTED-PROXY-AND-BINDING-01

Owner-selected priority, 2026-10-13, Platform queue PLT-15. One SECURITY PR
to main; reviewer Carbon Validator. Starting base
`ad870e7d5d30f2840247f40e81c685091bd89b9b`. Open-PR file scan found no overlap
on battery intake or validator-service code/tests. The owner's new NEXT
authorizes this priority while LP-03/#1254 completes its independent CI.

Authority: CONSTITUTION.md, INVARIANTS.md, current delivery/delegated-decision
protocols, VALIDATOR-01's bounded neutral door, OWNER-INTAKE-EXPOSURE-01 and
the Validator's public `shared/operator/PUBLIC_INTAKE_01.md` sections 3 and 9.
WAVE.md's research campaign is closed; the queue selects this bounded work.
Security acceptance OWNER-INTAKE-EXPOSURE-02 remains owner-owned after merge.
No exposure, tunnel operation, external submission or deployment is authorized.

## Working decisions and plan

KEEP hardened parsing, the existing NET-2 receiver-required verifier, snapshot
authentication, journals, body/deadline limits, neutral screen, commitment
admission and isolation. WRAP intake configuration with an optional closed
`exposure: {via: trusted_proxy, header, record}`. Header is a valid HTTP field
name; the trusted TCP peer is strictly loopback (127.0.0.1 or ::1), as the
design registers. The proxy must overwrite that header at the TLS boundary.
No arbitrary header, remote TCP peer, duplicate header, IP list, port, scoped
address or malformed value supplies identity. Canonicalize valid IP literals
so alternate IPv6 spellings cannot create new buckets. Direct mode ignores
identity headers and retains its existing behavior.

The deployment cache is keyed by path and mode, so a changed configuration
does not rebuild an already cached daemon. Check the effective executable
target's canonical CarrierBackend type and mandatory commitment mode before
the listener starts too; a stale cached private daemon is refused by the same
closed codes. This is a bounded REPAIR of the exposure guard, with no cache
rewrite or change to private evaluation. Tests exercise the final serve path.

The design allows the IPv6 local hop too. A final canonical bind check found
`::1` was accepted by configuration but the shared listener's default IPv4
socket could not bind it. Select AF_INET6 for IPv6 literals; keep existing
IPv4/hostname behavior. An actual IPv6 listener/health-probe test guards this
REPAIR alongside the existing IPv4/TLS/connection regressions.

Every publicly served intake, including the loopback tunnel, requires the
owner's exposure record, the isolated carrier and commitment enforcement;
configuration can tighten this policy but cannot disable it. Direct public
binds retain their TLS requirement. Proxy mode refuses non-loopback binds.
Facts reveal only `exposure.via`, with no header, record or new private data.

Both request buckets and per-client connection limits use the validated
identity before body reads/authentication. Before headers exist, proxy sockets
still count against the existing global connection cap and socket deadline;
they cannot be assigned a per-client bucket yet. Direct sockets retain their
early per-peer cap. Global bounds, body/in-flight limits and other public
doors remain unchanged. This prospective mode fixes IMPLEMENTATION_LAG; it
does not grant security qualification or override the owner's exposure gate.

F2 is KEEP: the verifier already sets `require_receiver=True` on every
authenticated tool. Add wrong/missing-receiver regressions, including status
and replayed bodies, without changing the signature protocol or published
endpoint registry. F3 uses the daemon's existing commitment admission;
prove an unbound submission cannot execute, and unavailable readers retain
infrastructure semantics. No chain reads, key access or signer operations in
agent validation: synthetic fixed snapshots/readers and existing test keys only.

1. Canonical baseline intake/client, deployment, daemon and service regressions.
2. Implement configuration/identity/limits and service-preflight/probe support.
3. Add spoof/refusal, proxy-bucket/connection, startup-guard, receiver/binding,
   legacy and miner-surface import-closure tests. Preserve existing assertions.
4. Canonical focused/affected/invariant regression, pinned quality, hygiene
   before each push and exact-head classified CI/Merge gate on the same PR.

Canonical baseline: 147 tests passed. Final local canonical acceptance:
633 tests passed with no skips, including 33 new proxy/binding/guard tests,
existing intake and loopback service end-to-end tests, deployment/daemon,
remote submissions, NET-2/remote transport and all invariants. The HTTP tests
hold four synthetic client connections and prove a different proxied client
still receives service; header refusals perform no body read. No existing
test or assertion was removed or weakened. Pinned Black 26.5.1/Ruff 0.16.3
and `git diff --check` passed.

Regression command from the isolated native-Linux clone:
`CARBON_UV_GROUPS="science-jax chain archive mcp" ./scripts/dev/canonical.sh python -m pytest tests/cpu/test_battery_intake_trusted_proxy.py tests/cpu/test_battery_intake.py tests/cpu/test_battery_intake_service_e2e.py tests/cpu/test_battery_validator_deployment.py tests/cpu/test_battery_validator_daemon.py tests/cpu/test_battery_validator_service.py tests/cpu/test_battery_remote_submission.py tests/cpu/test_net2_transport.py tests/cpu/test_remote_transport.py tests/invariants -ra`
Main advanced to `e6ce153a20394c7803586d350f99a0c858c874f6` during this run;
the intake, client, deployment and service dependencies did not change.
No base merge was needed for an unrelated main advance.

Reversible: remove the optional mode to return to the guarded direct listener;
commitment enforcement for public exposure is intentionally not relaxable.
Maturity ceiling: implemented/tested security controls; not SECURITY_QUALIFIED,
production or LIVE. Owner acceptance and Launchpad operator/outside-network
checks remain pending and are not blockers for delivering these code controls.
Historical map_ref WAVE-A/A6 (disclosure), affects NET-2 authenticated ingress.
Hub maintenance is retired; no generated Hub or WAVE selection edits.
Completion: one delivered PR, green exact-head CI/Merge gate, Ready for PR Head
with Carbon Validator, <=15-line untracked report and PLT-15 DONE, then stop.
