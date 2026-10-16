# T07 transport private malformed-branch diagnostics

Status: working contract; direct Root assignment, 2026-10-15.
Starting main: c22c988be3d6663fd0fabe4737b9e05947203e74.
Primary map_ref: WAVE-C/NET-2; Hub retired by OWNER-WORKFLOW-SPEED-01.

The original T07 submit was refused TRANSPORT_MALFORMED after a finalized
manual commitment. Its key is consumed. A read-only normal-client body shape
passes, but original wire headers and the origin's rejecting branch are unknown.
Proxy header overflow is a hypothesis, not a finding.

KEEP the canonical parser, existing first-failing-check order, 16-header and
4096-character guards, signature input, nonce transactions, limits and response.
REPAIR private observability only. Annotate existing malformed exceptions with
a closed internal branch; the intake's existing private stderr logger emits
one bounded record per branch per intake lifetime. Include only a closed enum,
a header count saturated at 17, count-over-limit and aggregate-budget status.
Unexamined budgets are null. No header name/value, body, signature, token,
request identity, path, exception text, trace or local is retained or returned.

Plan: contract/decision first; annotate existing raises; reuse intake.log with
bounded thread-safe best-effort emission; focused synthetic negative/positive
regressions; pinned formatting/lint/AST; Root canonical validation/review/merge.
The writer runs no application imports/tests, network probes, host work or
signer action. Root alone may deploy/observe the existing authorized route.
Baseline and focused canonical execution are requested from Root.

Expected manifest: this ticket; matching decision; carbon/transport/models.py,
gateway.py, store.py; carbon/battery/intake.py; new
 tests/cpu/test_transport_private_diagnostics.py.
No open PR overlaps these paths at ticket start. One branch, one PR to main.

DoD: each existing malformed category is distinguishable internally; original
public codes/status and acceptance/refusal boundaries survive. Unknown/private
attributes cannot inject text. Concurrent/repeated failures emit at most one
line per enum branch; failed logging cannot mask the original refusal. Test
real intake refusal logging and valid admission without a network listener,
plus exact 16/17 and 4096/4097 limits, ordering and nonce/ref provenance.

Canonical commands for Root: ./scripts/dev/canonical.sh pytest -q
 tests/cpu/test_transport_private_diagnostics.py tests/cpu/test_net2_transport.py
 tests/cpu/test_battery_intake.py tests/cpu/test_battery_intake_trusted_proxy.py
followed by changed-scope required CI and relevant disclosure/invariant checks.

Security-sensitive dedicated engineering review required. Maturity ceiling is
implemented/tested observability; no security qualification, failure cause,
scientific result, submit admission or verdict follows from source alone.
Conditional closeout: Root confirms unchanged-head checks/review and normal
merge. The original T07 campaign still needs an actual diagnosed fix, a Root-
authorized next submission intent and its real verdict. No automatic resend.
