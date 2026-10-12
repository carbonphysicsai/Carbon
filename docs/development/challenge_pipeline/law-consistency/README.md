# Packet → question-law consistency

LAW-CONSISTENCY-CHECK-01. An additive source-bound typed projection checker,
not an NLP approver, sampler, score rule or scientific acceptance gate.
KEEP the existing packet source verifier and JSON law proposals.

```text
python -m carbon.challenge_pipeline.onboarding.law_consistency --bindings docs/development/challenge_pipeline/law-consistency/battery-v3-bindings.json
python scripts/dev/onboarding/law_consistency_examples.py --check
```

Each reviewed binding identifies a facet, typed packet value, retained packet
excerpt/digest and exact law JSON pointer. Verify source bytes before comparing.
Changed or missing sources stay UNRESOLVED_SOURCE. A changed law pin/schema
also stays unresolved; never repin solely to suppress an unexpected change.
Normal exit 1 means a contradiction or unbound facet, 2 malformed input;
`--report-only` emits the same findings without failing the shell invocation.

## Eight separate facets and precise differences

Check objective, hard limits, observer scope, P, Q, w, boundary policy and
NONE_FEASIBLE independently. Every unbound facet remains on the checklist.
P cannot substitute for diagnostic Q; band value weights are not an outer
population law. Source values remain owner/Test-Lead choices, not suggestions
the checker installs. Source-bound HUMAN_INPUT/null projections describe
explicit pending decisions, never permission to infer a value.

The recursive diff gives an exact pointer, expected packet projection, actual
law value and state (value/type/length mismatch, extra or missing field).
An absent JSON path is not explicit null. Boolean true is not numeric 1;
numeric int/float encodings are equal only at the same value. There is no
tolerance, unit guessing or best-effort role coercion. Typed unit/operator
objects can be checked as a whole; unit translations in reviewed projections
must be explicit, not an inferred scientific conversion.

The source clause's typed translation is a **reviewed input**. Verified
excerpt bytes do not prove semantic entailment, physical truth, applicability
or actual buyer acceptance. This is the same boundary as packet reconciliation,
using the existing packet verifier rather than importing/copying an unmerged
tool. Standalone data contracts keep both PRs independent against main.

## Existing-Challenge examples

The retained examples use battery v3, motor and f02 current packet/law files:

- Battery: four safety limits, absence of a hard session-time cap, discharge
  diagnostic scope, unregistered P, separate Q no-redraw, buyer-mix band value
  and forward NONE_FEASIBLE no-redraw.
- Motor: 6/12 N·m anchors and 0.05 N·m zero-current cogging anchor. No buyer
  requirement is reduced or made soft.
- f02: 95 C anchor and the existing 24-context support, not a new draw law.

Fifteen projections agree today. **The full checklists are not clear:** each
example explicitly reports remaining unbound facets (including boundary
projection where the packet does not provide a typed binding). This is a
tool-coverage gap, not automatic proof of a missing/wrong packet or law.
Owners can review additional bindings incrementally without changing physics
to make checks green. Generic fixtures cover all eight facets and deliberately
mutate objective, limits, observer, P/Q, boundary and NONE_FEASIBLE.

This command does not edit a packet or law. New versioned owner decisions
require prospective reviewed bindings; historical packets/results retain
their original identities. A discrepancy is a requirements/reference finding,
never a candidate-model failure. No threshold, refinement width, k, E, weight,
sampling law, runtime adoption or readiness state is decided here.

Tests also cover ambiguous missing/null behavior, non-finite values, partial
coverage, stale provenance and nonpublic paths. Native diagnostics are not
canonical acceptance. No solver, spend, hidden/AX42 data, EV5/journal or live
contract changes. Hub retired.
