# READINESS-GAPS-01: registered producer evidence for S3 and H2

**Decision ID:** READINESS-GAPS-01-D1

**Ticket:** READINESS-GAPS-01
**Status:** development implementation in PR #924; no real-panel registration or policy adoption

## Problem and decision

S3 needs measured reference margins for every gate, while H2 needs case inputs from protected and public roles. Those inputs cannot be inferred from committed readiness reports or stored in this repository. The recommended approach is to register only the challenge, role/gate roster, units, owner-set fragility boundaries, and SHA-256 digest in the repository. The producer supplies the exact private panel at run time. The readiness command verifies the digest and computes aggregate S3 measures or an H2 overlap verdict without serializing case inputs or witnesses.

Missing registration or panel remains `NOT_BUILT`; malformed evidence fails. Producer-panel runs require `--no-history`, and a requested JSON report must be written outside the repository. V3 remains review-only. The Test Lead supplied development working values on 2026-10-09: at least five matched seeds per arm, paired improvement against the incumbent, a bootstrap 95% lower bound clearing `DEVELOPMENT_RULE["equivalence_margin_rel"]`, and promotion blocked by a mandatory gate failure on any seed. Owner adoption into a frozen rule and the remaining evidence details are pending.

## Alternatives and bounds

Committing panel rows would expose protected material. Guessing margins, fragility boundaries, or a seed count would create unapproved science. Inferring H2 clearance from role names or an empty overlap result without a complete roster would turn absence of evidence into a pass. These alternatives are rejected.

The H2 check verifies the registered role roster against the committed Challenge role registry and compares every supplied group. Correct classification of sealed roles and extraction of the source cases still require producer custody-journal verification. The digest pins the supplied panel; it does not prove its scientific provenance. No real registration is added in this PR, so no Challenge receives a new real-panel PASS.

## Impact and reversal

Implementation is in `carbon/challenge_pipeline/readiness/evidence_checks.py`, the readiness CLI/runner, and `items.json`; the evidence format and operator preconditions are in `docs/development/challenge_pipeline/readiness/READINESS_GAPS_01.md`. It adds optional CLI inputs and changes S3/H2 from pending placeholders to fail-closed automated checks. Existing runs without registered evidence remain `NOT_BUILT`; historical reports are not reinterpreted. The formats are versioned and can be superseded prospectively without rewriting old evidence.

If a lead rejects this approach, replace the S3/H2 registration and panel adapters and their toy tests, and restore the pending item mapping until the replacement exists. Test Lead still owns fragility boundaries, and the owner retains adoption of V3 into a frozen rule and the use of real readiness evidence.
