# LAUNCHPAD-T02-PARITY-01

Root assigns Product the original T-02 audit and missing parity assertions.
KEEP the single operation/setup tables and current HTTP/MCP fixtures; REPAIR
their incomplete coverage in place. No replacement harness, runtime redesign,
extra execution quota or real-infrastructure acceptance claim is introduced.

The shared operation tests already enumerate every operation's successful
gate order and registration refusal. Their malformed-request example covers
one operation and they do not enumerate refusal at every applicable gate.
Setup lists all schemas/routes but compares only selected refusals; onboarding
compares status/prepare answers and separately tests other behaviors. Add the
missing table-driven cross-door assertions rather than count these components
as the original T-02 completion predicate.

Preserve native closed response contracts: onboarding uses `next_action` and
MCP ToolError text, operation/setup refusals use `next_step`. Compare their
semantic code/action at each actual adapter boundary without changing a public
interface just to simplify a test. Browser-only inference key input remains an
explicit exception; MCP keeps keys by owner-only file path.

Static local checks are authorized; application tests are not dispatched by
Product locally. New exact-head remote CI and independent review must supply
the validation. Root alone owns merge and installed acceptance; Platform2 owns
T-04/T-07 and consumes this bounded result. No reserved owner decision is set.
