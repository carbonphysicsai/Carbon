# LAUNCHPAD-T04-SERVICE-INTERACTIONS-01

Status: IN_PROGRESS. Executor: Platform2. Starting base:
a8e52e6458927e9b9dfe6af2e94cce39d2537ca0.

Authority: Ryan directs completion of the full Launchpad handoff and T02-T05;
Root assigns Platform2 T04, new disjoint service-interaction module. Original
handoff at57c3e019f7f7de6deb274ffd5283395c91dfaa50,
docs/development/LAUNCHPAD_E2E_SUITE_HANDOFF.md T04. The owner record
2026-10-15-OWNER-LAUNCHPAD-E2E-SUITE-01 section3 controls actual execution order.
Root remains sole merge/host/test/spend/exposure actuator.

## Working contract

KEEP the existing production journey, real HTTP/MCP door adapters, campaign
host, ledger, loopback intake/validator and scripted provider fixtures.
Add stages9-15 in tests/service/test_launchpad_extended_journey.py, importing
existing fixtures/helpers instead of cloning an executor. No paid calls,
actual chain, production signer, external listener or protected material.

Cover commitment digest/ordering and same-tempo refusal; no-receiver warning
and receiver mismatch before signing; two receiver-paired throwaway intakes,
one refusing and one admitting with both durable journals and independent
outcomes; registered levels1-3 and target-not-served refusal; L4 missing parts;
Torch scope refusal before dispatch with JAX unchanged; typed old-revision
submit refusal; budget status matching the existing budget checker on both doors.
Existing actual service6d evidence is reused for overlap; new controls address
missing interactions rather than repeat an entire paid end-to-end suite.

Manifest: this ticket, .agent/decisions/2026-10-15-LAUNCHPAD-T04-SERVICE-01.md,
new service test module, and the minimum CI discovery line (serialized with
T03's ci.sh writer if needed). Any existing sharedfixture edit waits until
Platform3 PR1376 is merged/files released and exact boundary is coordinated.
No edits to Platform3's13currentpaths, T02tests, T03script/report or T05reader.
Hub impact: historical map_ref SYSTEM/AGENT-EXECUTION; ownerDX03 retires Hub work.

## Plan and validation

1. Read existing service fixture, component controls and current runtime gates.
2. Record contract/engineering decision; confirm peer path/CI ownership.
3. Implement substantive missing service interactions through actual HTTP and
   MCP clients, with state/signature/journal/dispatch negative controls.
4. Static AST/format/lint/diff checks; actual canonical execution through
   authorized remote CI or Root-dispatched canonical wrapper only.
5. Repair valid CI/review findings in this same PR; Root normal exact-head
   merge after applicable checks and independent correctness review.

No native static result is labelled behavioral validation. Fixture service
results earn engineering test evidence only. Real F05-F15, images, client
installation, owner-block receipts, security or mainnet qualification remain
separate. T04 automated levels do not run or approve deferred real level cells.
Baseline runtime execution is not yet dispatched; current Root TEST selection
is not a worker-owned test lease. Remote canonical CI will supply exact-head
validation without duplicate host dispatch.

## Current semantic reconciliation

DOCUMENTATION_LAG: the original handoff predates new-launch composition.
Bare construction_level1-3 hints currently bind the registered composition;
they must not regain legacy downgrade semantics. Stage12 therefore checks
current hints against the actual writer capture and separately drives explicit
historical variant-admission fixtures through served/parts pre-sign gates.
No production admission code is monkeypatched outside test fixtures, and no
real ladder acceptance is claimed. Root was notified before this adaptation.
The existing preparation fixture is reused with its manifest argument adapted
only inside each historical test; no sharedfixture source edit is required.
