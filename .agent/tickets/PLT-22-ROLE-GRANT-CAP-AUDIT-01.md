# PLT-22: role output caps and grant reservations

Platform queue audit, reviewer Graphite Testing Manager, one PR to main.
Starting main `07314d0bde9138c55452aec06e5448816b2a7b63`. Current authority
files are byte-identical to the PLT-28 authority read at 1e4eba5cd: constitution,
invariants, WAVE, delivery/delegated protocol, Code Authority and Build Out
with overlay. Also read GRAPHITE-01 and the grant, role/provider, preflight
and experiment budget contracts. Primary historical map_ref WAVE-C/C-W1.
Hub is retired. This is DEVELOPMENT audit/testing, never spend permission.

KEEP the actual selection/reservation calculation and enforced monetary cap.
A new session's larger output cap reserves reasoning and output at the same
registered output price. Audit current settings, not historical session
interpretation. Recompute per-role/model full-call reservation and compare
public grant files against their registered token share/run cap. Name missing
workload/provider/rate facts as unresolved, never a successful empty audit.
The grant's run cost is an enforced monetary cap, not an unlimited promise to
complete every maximum-size call. Do not multiply retired turn limits into a
new grant amount. Show capacity lost at the larger cap and preserve typed
refusal before transport when the next full reservation cannot fit.

Open PRs #1257 and #1321 own grant_binding, grants/README and related grant
files. Do not edit those paths or competing branches. The bounded audit uses
new script/test/document paths and reads only public registered source files.
No credentials, host/private ledgers, hidden samples, provider calls, grants
execution, pods, chain or spending are accessed. Amount changes/re-approval
remain HUMAN_INPUT; no owner-approved grant is rewritten.

Plan: canonical money-cap baseline; standalone reproducible audit and report;
tests comparing real reservations plus a cap-increase negative control through
the real pre-transport budget gate; canonical relevant regressions, pinned
formatting/encoding/hygiene and exact-head CI; report/handoff.
Manifest: this ticket; scripts/dev/graphite_grant_cap_audit.py;
tests/cpu/test_graphite_grant_cap_audit.py;
docs/development/graphite/ROLE_OUTPUT_CAP_AUDIT.md;
docs/development/evidence/role-output-cap-audit/audit-v1.json.
Completion is a green exact-head engineering handoff, not owner grant approval
or a claim that every role can run every rung under every grant.
