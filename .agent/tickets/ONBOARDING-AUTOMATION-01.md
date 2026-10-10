# ONBOARDING-AUTOMATION-01 — deterministic packet drafts

Owner workload, 2026-10-10. Implement an offline short-brief-to-ten-section
packet generator; exercise battery v3 and motor v2 against their existing
packets. One PR; no solver, build, spend, hidden/AX42 access or registration.
Base: 93875b7dc68bed83562db199427a1cb91d7639a4.

KEEP COMMON_DESIGN_PACKET_V1 and existing packets; WRAP with deterministic
drafting and explicit gap reporting. New types are tooling inputs, not runtime
authoring/qualification contracts. A citation is checked against exact file
bytes and excerpt, but proves neither applicability nor approval. Unsupported
brief statements remain HUMAN_INPUT recommendations. All reserved behavior
stays closed. DoD: ten sections, pinned source basis, bounded closed inputs,
missing-input owner/decision/held behavior, regeneration comparisons and tests.
Native diagnostics only; canonical acceptance is CI. Hub retired by OWNER-DX-03.
Maturity ceiling: implemented/tested drafting, never a tested Challenge.

Follow-on owner-authorized tickets: 02 law, 03 panel, 04 read-only status;
one independently reviewable PR each. Motor comparator waits for re-export.
