# Packet buyer-field reconciliation

PACKET-RECONCILE-01. Development tooling only. KEEP the ten-section packet
generator; this additive checklist checks its buyer claims against explicitly
bound public sources and recorded owner/Test-Lead decisions. It changes no
packet, law, runtime value, qualification, registration or historical result.

```text
python -m carbon.challenge_pipeline.onboarding.reconcile --manifest docs/development/challenge_pipeline/packet-reconcile/battery-v3-manifest.json
python -m carbon.challenge_pipeline.onboarding.reconcile --manifest docs/development/challenge_pipeline/packet-reconcile/motor-manifest.json --format json
python scripts/dev/onboarding/reconcile_examples.py --check
```

The checklist includes consistent, contradicted, stale/missing/ambiguous
clauses **and every unbound buyer field**. Normal exit 1 means review work
remains; 2 means a malformed request. `--report-only` emits the same findings
without making unresolved review work a failed shell invocation. No input is
mutated. JSON carries every source path, expected/observed digest, reviewed
selector and extracted value; matching nothing is never a pass.

## Extraction and authority

An explicit manifest binds one packet and up to 40 public documents (SOURCE,
OWNER_DECISION or TEST_LEAD_DECISION). Up to 200 named checks compare a buyer
field against one to eight independently bound clauses. The packet cannot
corroborate itself. Active decision identities are reviewed inputs, never
inferred from the latest filename or greatest numerical value.

Numeric selectors use literal prefix/suffix delimiters that name scope and
units, optionally restricted to one exact `##` section. Equality is exact
decimal equality; there is no invented tolerance or unit conversion. Literal
selectors match case-insensitive, whitespace-normalized whole phrases with
word boundaries, then return a **reviewed declared token**. This catches
scope drift without pretending a language parser can prove entailment.
Caller-supplied regexes are refused. A missing or duplicate match stays open.

Source/packet digest drift is STALE_PIN, not agreement: inspect the changed
document and refresh the reviewed binding prospectively. Never repin merely
to suppress a discrepancy. All cited-source assertions need a retained public
excerpt; this command does not fetch a website or certify published research.
Additional external sources can be bound through public retained source
notes, with their origins and limitations documented. Valid source bytes do
not establish physical truth or applicability.

The manifest kinds identify **claimed provenance**, not authentication,
scientific authority or automatic approval. A phrase-to-token mapping itself
needs review. Output `authority_granted` is always false. `checklist_clear`
only describes complete, consistent bindings across the fixed buyer-field
inventory; it never means a scientifically qualified or launch-ready packet.

## Existing-Challenge examples and deliberate gaps

- Battery v3: four safety limits, time-as-objective, discharge diagnostic
  scope and buyer-mix weighting against OWNER-BATTERY-AMBIENT-MAP-03.
- Motor: 6/12 N·m floors, 5% relative ripple and 0.05 N·m cogging against
  OWNER-FIRST-THREE-CUSTOMER-ROUND-01. No requirement is lowered.
- Cooling cell: 85 C at the lid-side TIM2 case plane and buyer vapour chamber
  against OWNER-DESIGN-VALUE-01. No full-plate problem is introduced.

These 14 critical checks are consistent today. **None of the three full buyer
checklists is clear:** other buyer fields have no reviewed extraction binding
yet. Unbound means tool coverage is incomplete, not that the packet text is
necessarily absent or wrong. The checklist distinguishes those cases; it
does not fabricate corroboration to make a report green. The source notes,
buyer role/value/geometry/P/Q and exclusions can be bound incrementally by
their owners without changing scientific requirements.

Reports retain the exact source revision. The original three packets and
older decisions remain byte-preserved history. A conflicting independent
source is a reference/requirements finding, never a model failure. Human
review resolves active scope or applicability; this tool never chooses the
convenient interpretation or silently rewrites sealed evidence.

## Tests and limits

Existing battery/motor/cooling examples, changed numeric limits, observer
scope, charge-versus-discharge substring traps, ambiguous clauses, stale
pins, unbound coverage, self-corroboration, malformed selectors and nonpublic
paths are tested. Native checks are diagnostics; pinned GitHub acceptance
applies to the submitted head. No solver, hidden data, secret, operator store,
cloud action, spend or EV5/journal access. Hub retired.
