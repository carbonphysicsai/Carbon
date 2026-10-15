# LAUNCHPAD-T02-DOOR-PARITY-01

Root's bounded 2026-10-15 assignment implements the original T-02 obligation
in `57c3e019:docs/development/LAUNCHPAD_E2E_SUITE_HANDOFF.md`, under
OWNER-LAUNCHPAD-E2E-SUITE-01. Starting main is
`a8e52e6458927e9b9dfe6af2e94cce39d2537ca0`. Root owns merge and test/host
dispatch; current OWNER-DX-03 retires Hub and historical receipt ceremony.

## Contract and reuse

KEEP the generated operation/setup doors, existing real loopback HTTP and
MCP tool/server fixtures, closed refusal catalog and onboarding service.
Extend the existing parity tests to cover every described operation's malformed
request and applicable request/profile/replay/registration/signer/campaign
refusal, with identical code and next action and no later gate/body reached.
Assert the table's admits_work and listing/route generation contracts. Extend
setup and onboarding parity to every declared step/action while retaining the
intentional browser-only pasted-key exception and existing open-tier rules.

The current tests cover generated success paths, registration refusal, selected
malformed/body refusals, setup schema/route listing and selected onboarding
answers. Those are component evidence, not exhaustive each-gate coverage or
real T-07/F12 acceptance. Do not introduce a new harness or paid test matrix.

Owned implementation paths are `tests/cpu/test_miner_operations_doors.py`,
`test_miner_setup_agent_first.py`, and `test_mcp_onboarding_door.py`, plus this
ticket and its decision. Platform2 confirmed disjoint T-04 ownership; open PR
file inspection found no overlap. T-03, T-04, T-05, T-06 and T-07 remain separate.
No runtime interface change is authorized without a demonstrated bounded defect.

## Plan and evidence

1. Record precise coverage gaps and reuse decisions before test changes.
2. Add table-driven parity and failure controls to existing fixtures, asserting
   refusal before later gates or effects; no chain/provider/signer/model calls.
3. Run only static AST/format/lint/hygiene locally. Root reserves application
   test execution; applicable canonical validation is the new exact-head remote
   CI. No local baseline is claimed.
4. One main-based PR; repair concrete CI/review findings on that PR; deliver
   exact head and actual check conclusions to Root and Platform2.

Completion is conditional on actual applicable CI and independent complete-diff
review closure and Root's merge gate. Tests present or statically parsed are
not tests passed. Maturity ceiling: DEVELOPMENT parity regression coverage;
no real acceptance cell, spend, installed behavior, security acceptance or
scientific/production qualification is earned. Hub impact: none, retired.

## Candidate validation

Static AST parsing, repository-pinned Black 26.5.1/py310 and Ruff 0.16.3
passed for the three changed test modules. No application test or local
baseline ran. The exact-head canonical CPU suite must execute the new
parameter cases; canonical CI and independent review remain pending.

The generated MCP callbacks exercise the shared closed-body/refusal contract;
existing setup SDK schema tests retain transport-level rejection checks.
Onboarding compares its established reason/next_action representation with
MCP's ToolError representation without changing either wire interface.

Independent review found that an unregistered `confirm` is a successful
observation with `confirmed=false`, not a NOT_REGISTERED refusal. The repair
keeps the registered-prepare refusal and separately asserts HTTP200/equal MCP
payload, false registration/confirmation and the exact next action. Runtime
semantics remain unchanged; the repaired head requires fresh remote CI.
