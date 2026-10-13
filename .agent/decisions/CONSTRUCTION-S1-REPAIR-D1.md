# CONSTRUCTION-S1-REPAIR-D1

Ticket: CONSTRUCTION-CONTRACT-01-S1-REVIEW-REPAIR.
Status: PROPOSED_WORKING_DECISION; selected for bounded implementation.
Primary Hub map_ref: WAVE-C/C-02.

Problem: S1 accepts supplied descriptors without authentication, resolves immutable composition pins using current-only admission, and lacks compiled independent field-effect controls.

Decision: resolve and authenticate exact composition/variant descriptors through their registered immutable versions and digests. Keep current-only dv.registered admission unchanged. Pass the selected Composition as the internal budget adapter selection, revalidating it at the same compile boundary; string "composed" retains the existing current-composition selection. Fixture directories must be explicit and use the same authentication logic. Test independent compiled-route ablations and corrupted descriptor/pin/record/choice/pool controls.

Alternatives: trusting caller descriptors cannot bind registered permissions; changing dv.registered would broaden ordinary admission; costing by current composition breaks selected historical identity; direct trainer-flag-only tests cannot observe compile/record routing. These are rejected.

Locations: development_composition.py, battery/training_budget.py and test_construction_contract.py; exact tracked implementation/head and PR will follow. No registered documents, implementation-version pins or variant admission rules change. Reversible by reverting the corrective PR; an alternate resolver or budget dispatch can supersede only these paths and tests.

Human input: no new scientific/economic value needed for these repairs. Central human-supplied delivery/Hub versus main-policy seam remains unresolved for affected closeout/merge; keep the stronger supplied predicate intact and route through Test Lead/PR Head. This record selects engineering mechanics, not objective precedence or security acceptance.

Notification: Test Lead verified team route receives the decision and exact repair PR/rereview handoff; no unverified domain session is impersonated. Lead may supersede the engineering decision. No approval, merge, spend or host action is granted.
