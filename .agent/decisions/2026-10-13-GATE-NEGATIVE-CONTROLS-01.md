# GATE-NEGATIVE-CONTROLS-01 working engineering decision

Use a prospective, separate controlled-readiness result rather than silently
rescore historical readiness reports or promote successful toy controls into
physical evidence. P1, P2 and A4 have public code/registration inputs and can
be exercised without a host probe or protected reference. Invoke CHECKS at
runtime for both signs, not a cached predicate or a fabricated result.

Bind the control spec, negative input and checker source identity in every
result. Refusal must be FAIL with the expected reason; an exception or another
missing dependency is not proof that the intended check discriminates.
No cached control receipt survives a checker change. Positive result must
also execute and pass; an always-failing check earns nothing.

Report missing physical noise/margin definitions as HUMAN_INPUT. Arithmetic
can describe within-noise margins, not choose qualification thresholds.
The strongest alternative, automatically wrapping every test as a negative
control, was rejected: subprocess failures/skips are not known-bad detection,
and containment/private checks would cross this ticket's custody/host bounds.

Reversible: remove the added control annotation/summary; existing checks,
registered values, review evidence and dated histories remain unchanged.
Validator owns comprehensiveness and scientific use; Test Lead owns framing.
The unresolved delivery/Hub policy affects handoff/closeout, not safe code.

## Prospective owner resolution, 2026-10-13

The owner subsequently ruled in Test Lead turn
01a1368e-0cc2-7d43-9475-0e6102b81e31: "Scrap hub maintenance and human/GPT
receipts.Follow how Claude was merging." The initial hold above is historical;
current DELIVERY_PROTOCOL applies, without Hub work or receipt ceremonies.
Keep canonical checks and real domain constraints; PR Head still owns merging.
