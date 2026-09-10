# NET-4B stable implementation evidence

Status: selected; canonical acceptance and merge pending.
Starting main: ba88aa8bb6360fc101ec4bc3afc5c0f4408ccd5f (PR #124).
Ticket: `.agent/tickets/NET-4B_verified_publication.md`.
Primary Hub map_ref: WAVE-C/NET-4B. Decision: NET-4B-D1.
Notification: https://github.com/carbonphysicsai/Carbon/issues/42#issuecomment-5610295276.

## Expected manifest and reuse

Add carbon.chain publication compiler, dispatch journal, publisher/heartbeat and
narrow SDK extension; deterministic and installed-SDK tests, invariant checks
and WEIGHT_PUBLICATION operator contract. KEEP NET-1 reader, NET-2/3 journals,
C-REWARD and NET-4A authority; no scientific or dependency changes. Extend the
explicit focused network test manifest. Record actual NET-4A delivery and selected
NET-4B in canonical authority before regenerating Hub.

## Candidate diagnostics

Native command: `.local/diagnostic-env/Scripts/python.exe -m pytest tests/cpu/test_net4b_publication.py -q`.
Result: 35 passed, 14.63s. Seven installed-SDK contracts explicitly skip without
the optional SDK on Windows; canonical CI requires that SDK and cannot skip them.
Native results are diagnostics, not canonical or localnet evidence.

Final combined native diagnostic command adds test_net4b_sdk, NET-4B/NET-1
invariants, test_net4a_intents and test_select_cpu_profile: 108 passed, seven
explicit installed-SDK skips, 19.02s. Black/Ruff pass for all changed Python files.

Tests cover complete winner/burn/all-burn, shared winners, dust tolerance,
min/max clipping constraints, owner sink and stake/permit/rate checks, recycled
identity, final-vector and pre-sign changes, transaction-before-wire ordering,
exact dispatch replay, ambiguous restart without resend, bounded backfill,
outage/recovery, commit-finality-versus-reveal, heartbeat decay and funding-end
burn, changed post-finalization exposure and separate settlement observation.

Installed-SDK tests bind exact reviewed 11.1.0 SetWeights.build and RpcSubstrate
submit/reporting ASTs, exercise actual Client.plan/execute rebuilding and Policy,
the actual timelock encryptor, signed-hash hook ordering and finalized capability
capture. Runtime source is pinned separately at v445 /
d3f40e44bda9019c606aeb0c907bb52ba7fe386c; source inspection verifies Burn versus
Recycle, owner incentive routing, mechanism limits and LastUpdate-at-commit.
These are source/contracts, not an executed localnet or observed epoch.

## Conditional delivery and limits

Applicable canonical NETWORK_FOUNDATION acceptance retains all invariants,
quality/package/authority, installed SDK and affected subsystem regressions,
Hub/browser and Merge gate. Required failures must be repaired. Delivery requires
the unchanged expected head and normal guarded merge; actual run/head/merge
receipt stays external. No second post-merge full suite is required.

SDK objects/signing stay in carbon.chain, public networks fail closed, treasury
is absent. No science/security qualification, runtime burn proof, G2 or LIVE
claim. Exclusive publisher credentials, trustworthy local provider/runtime and
unexplained interrupted dispatch remain operator/security boundaries. Intent
expiry never erases stored chain weights. NET-5 is next and must supply actual
runtime inclusion/finality, applicable reveal, burn/epoch and recovery evidence.

## Canonical fingerprint repair

Run 34420527086 on 700ae35 passed 180 invariants and 1,847 focused tests;
one installed-SDK source fingerprint failed because native Python 3.12 adds
an empty `type_params` AST field absent from canonical Python 3.11. The pinned
wheel source is unchanged. Recomputing its canonical shape reproduces the
observed hash exactly. Normalize only that empty field and pin all three
reviewed function hashes to the 3.11 shape; meaningful SDK statements and
nonempty generic parameters remain checked. Actual encryption, execution
rebuilding, policy and hash-before-wire SDK tests passed in the failed run.
This repair requires a new applicable acceptance, not a claimed prior pass.

Run 34420869013 exposed a second fingerprint-generation detail: parsing an
entire class retains indentation inside RpcSubstrate.submit's multiline
docstring, while inspect.getsource followed by dedent removes it. Recomputed
all three references from exact method line slices using the same dedent and
AST normalization as the installed-source test. The observed submit hash is
reproduced from the pinned wheel; no SDK statement or semantic assertion was
removed. All other focused tests and 180 invariants again passed; the clean
image job passed. Both failed runs remain historical failed evidence.
