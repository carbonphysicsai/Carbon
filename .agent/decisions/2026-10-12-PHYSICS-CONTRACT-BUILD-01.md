## 2026-10-12 — PHYSICS-CONTRACT-BUILD-01-D1: reference provenance and unresolved evidence

Ticket: PLT-01. Working engineering decision, 2026-10-12.

KEEP the Validator's registered-law checker. REPAIR its advertised validity
exclusion and finite/shape checks; retain residual-only APIs as wrappers over
readings that count UNRESOLVED points. Candidate incompleteness cannot reduce
a gate's denominator and then be described as a pass.

Reference pairs are loaded from the owner's explicitly PUBLIC calibration
directory. Verify the image against the accepted PyBaMM image, the overlay
against the repository lock, and the plan and every record against the
MANIFEST hashes. Validate law axis, fixed other inputs and each law's step.
Missing/failing reference evidence stays UNRESOLVED. Member quantiles may
illustrate diagnostics but never substitute for reference calibration.

The alternative of caller-supplied `verified: true`, inferred image presence,
or a tolerance estimated from good models is rejected: none establishes the
required reference basis. A mismatch requires a corrected Data Collection
manifest or a new owner-approved reference pin, not a silent fallback.

B9 is also computed directly from raw public curves paired with the reference,
without using the checker or its tolerance. This establishes a model/reference
discrepancy where positive; it does not declare a universal real-cell law.
The Validator and owner retain scientific interpretation and adoption.

Locations: carbon/challenge_validator/physics_contract.py;
carbon/battery/physics_contract.v1.json;
scripts/dev/battery/physics_calibration.py and physics_screen.py; their tests;
docs/development/evidence/physics-contract-01/. These DEVELOPMENT-only additions
are reversible together and have no downstream runtime consumers. PLT-02 may
add prospective outputs; B11–B14 remain outside PLT-01.

Superseding path: change the loader's manifest adapter for Data Collection's
published format, or the declarative proposal and screening evidence for an
owner/Validator law decision. No existing records are rewritten. Required
human inputs: law adoption, scientific envelope, quantile, margin and gate rate.
The PR names Carbon Validator as reviewer; no separate message is sent.

## Public panel arrival and RES-06 reconciliation

The published nested manifest binds 800 OK records, 700 physical pairs,
the source contract bytes, generator, command, plan, jobs and record file.
The loader checks those identities and every record's simulator provenance;
the existing acceptance-link loader verifies the owner's MMS acceptance.
The manifest digest is 7d4529df11998aadb6c16f6d87fcccde64fe24009aed1089f6959c8f1e31785b.
No failed provenance check is adapted into a pass.

KEEP the published inputs and solves. REPAIR the adapter for their actual
schema. WRAP the same c1/c2 0.05-step pairs with the new prefix_invariance
law: B15 first; B16 card metric only; 120 s excluded. The raw historical
contract remains bound; its existing pair-law semantics must equal the
current proposal. This prospective projection does not rewrite any record.
Cached readings bind checker, adapter, contract, plan, manifest, count and
member identities; a changed checker requires a new local public-model run.
Controls reuse the existing control_predictions implementation on verified
references. Partial member readings stay UNRESOLVED. B1-B3 reference existing
exam gates; B9 remains diagnostic; gates never substitute for verified decisions.
The smallest reversal removes the two prefix entries and their projection;
the original pair-law references and historical single-point report survive.

The first combined run exhausted shared WSL memory while holding historical
curves and compiled rebuilds. REPAIR the diagnostic runner with separate
cache generation: discover the same decided member names one public bundle
at a time, release compiled programs between rebuilds, and checkpoint each
member's readings. No model setting, seed, law arithmetic or reference changes.
Cache v2 additionally binds the builder bytes and a complete flag; incomplete
matching caches can resume construction but cannot produce a screen. Tests
exercise completion refusal and skipping completed members. This is a local
resource repair, not a qualification or candidate-failure decision.

Main's later score-proof amendment adds an always-abstain screen control.
Freeze this study's roster to the original public bundles, original five
controls and original decision file. The report wrapper refuses missing
declared members and ignores later screen-only additions. This preserves
registry-v9 panel comparisons without editing the score-proof lane or
silently expanding historical evidence. A regression adds an upstream-only
control and verifies that it cannot widen this study.
