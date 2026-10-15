# LAUNCHPAD-T04-SERVICE-01

Ticket: LAUNCHPAD-T04-SERVICE-INTERACTIONS-01. Decision: REUSE_AND_EXTEND.
Selected by Platform2 under Ryan's full-handoff completion instruction and
Root's bounded T04 assignment; Root notified directly. No reserved owner
scientific/economic/security value is selected.

The existing production service journey covers a real loopback submit and
sealed verdict but predates several newer capabilities. Component tests do
not establish their interactions through both product doors. Reuse its
BatteryLaunchpad/Script/preparation and loopback fixtures in a new disjoint
service module. Preserve the existing fixture's behavior. Compare actual
HTTP and MCP results plus durable journal, signer and dispatch side effects.

A second executor, mocked result-only door parity, expanded host exposure,
and paid acceptance reruns are rejected: they would not test the intended
shared path. CI discovery must explicitly include the new module; source
presence alone cannot satisfy testing. Serialize any sharedci.sh edit with
T03 and any existing journeyfixture edit with Platform3 until1376release.

Reversible: remove the new module and its discovery line; no runtime schema,
scientific contract, permission gate or history migration changes. If valid
service controls expose a runtime defect, record and notify its exact bounded
scope before repairing; do not weaken the control or invent a successful cell.
Maturity ceiling: IMPLEMENTED/TESTED engineering only after actual validation.
