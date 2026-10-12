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
