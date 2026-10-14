# GRAPHITE-TARGET-BINDING-01: prospective public targeted-artifact context

Status: selected bounded engineering continuation of PKT-15; full PKT-15
remains BLOCKED_INCOMPLETE. Root Test Lead explicitly selected this slice
after GRAPHITE_VERIFY_PATH_NEXT.md; starting main is
1ac383afa65f74d1cf4aa80f6f23bfc01198910f. One isolated branch and one PR.
Root owns engineering merge. No host execution, provider, key, private store,
holdout/sealed material, science policy, escape triage or qualification.

## Working contract

KEEP legacy family sessions and their historical schemas, seven executable
L4 families, six unavailable seams, and all prior verdict meanings. This
slice does not implement a verification worker or replace NoVerifyPods.

Add an explicit prospective public-target mode, initially battery L4 only.
Operator CLI inputs name a vetted public import root, one bundle directory
component and an independently supplied expected manifest digest; either all
three are supplied or none. They never come from miner tool arguments.
The original Constructor v3 bundle is read only. Before reading additional
files, validate the directory boundary, regular-file/no-link constraints,
closed manifest and expected digest. Restrict files to delivery's fixed
bundle names, bound reads, check every byte digest and refuse protected or
official material. No untrusted path from a manifest is followed. Capture
bytes once; subsequent rebuilds use that immutable snapshot, never reopen
the mutable source. Runtime filesystem intake requires a secure no-follow
directory-descriptor path; unsupported hosts fail closed. CI exercises the
real POSIX boundary, including ancestor and file symlinks.

Validate the same challenge, construction contract, registered L4 variant,
submission envelope/document digests and built-artifact identity through the
existing staging and producer-independent metadata rebuild. Reuse delivery
and build identity; no input program is executed. No recipe-wording identity
or source-supplied execution Boolean grants artifact or runtime authority.

Mint an immutable validated TargetBinding holding closed public identity
pins and captured bytes. Raw mappings and directly constructed stand-ins
are refused by consumers. Resolve L4 documents only from that bound snapshot;
normalize target reconstruction into the existing built-record shape.
The target's fixed pin accompanies the brief, session/report, verifier,
specimen and resume. A resume cannot change target or add/drop targeted mode.
Targeted evidence/specimens use prospective schemas and exact target pins;
unbound historical evidence is not reinterpreted as targeted evidence.

Targeted artifact judgement stays UNDETERMINED/unscored without an actually
wired trusted worker/rebuild path. A supplied session receipt, ordinary pod
mapping, fixture or substituted build record cannot close that seam. Preserve
existing exposure, infrastructure and miner-local isolation classifications;
do not suppress a real path finding behind the unavailable model backend.
Report family-attempt coverage separately from unavailable targeted runtime
verification. No claim of exact submitted-artifact attack acceptance follows
from loading the target or compiling its metadata.

## Plan, manifest and registered controls (before implementation)

1. Record contract/decision and synthetic control inventory; baseline existing
   L4 tests at the starting main (43 native passes; POSIX Graphite baseline is
   canonical-only on this Windows host).
2. Implement bounded immutable target intake and staged metadata resolver;
   prove positive capture and each negative path/data/identity control.
3. Wire prospective CLI/session/verify/specimen/resume context and explicit
   runtime seam; prove real entrypoint consumption and unchanged legacy cases.
4. Refresh source-pinned role audit prospectively as v3; preserve exact v1/v2
   bytes and historical provenance. Current-source regeneration still must
   detect a stale pin. No grant, pricing or budget arithmetic changes.
5. Run focused controls, legacy interactions, hygiene/style/encoding and one
   actual canonical candidate run. Report scope and unresolved backend holds.

Expected changed paths:
- this ticket and .agent/decisions/2026-10-13-GRAPHITE-TARGET-BINDING-01.md;
- carbon/agent_campaign/attack/target_binding.py (new);
- carbon/agent_campaign/graphite/phase4.py;
- carbon/agent_campaign/graphite/phase4_remint.py (actual specimen CLI delegate;
  added prospectively before editing after tracing command_remint);
- carbon/agent_campaign/attack/verify.py;
- carbon/agent_campaign/attack/adapters/battery_level4.py;
- tests/cpu/test_graphite_target_binding.py (new);
- tests/fixtures/graphite/target_binding_controls.json (new);
- docs/development/graphite/TARGETED_ARTIFACT_BINDING.md (new);
- docs/development/evidence/role-output-cap-audit/audit-v3.json (new);
- tests/cpu/test_graphite_grant_cap_audit.py and
  docs/development/graphite/ROLE_OUTPUT_CAP_AUDIT.md.

The registered fixture inventory is TEST_ONLY and uses synthetic public
stage/control bytes, never actual Constructor/private/host evidence. Its
positive case binds the same metadata artifact; negative cases cover graph
byte mutation, alternate target, wrong challenge/variant/contract, missing
envelope, path traversal/absolute path, symlink ancestors/files, changed
resume/specimen pin, spoofed worker receipt and diagnostic promotion. Also
retain legacy family/oracle/INFRA/isolation and exact audit stale-pin controls.

No overlap at start on these implementation paths. Platform #1343 retains
pods.py/bootstrap.py/pod_control.py/provider transport; none is edited here.
Hub impact: retired/frozen under current DELIVERY_PROTOCOL; no maintenance.
Maturity ceiling: SPECIFIED/IMPLEMENTED/TESTED software binding only. Actual
runtime, fresh/GPU/D4/historical evidence and mainnet parity stay unavailable.
Conditional completion: bounded DoD, actual exact-head canonical acceptance,
Root merge and brief closeout; no full PKT-15 or host qualification claim.
