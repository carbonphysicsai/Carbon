# Test Lead review: battery Level 1 loss expressions

**Reviewer:** Test Lead. **Date:** 2026-10-05.
**Reviewed:** the Level-1 review packet,
`docs/development/graphite/L1_LOSS_EXPRESSIONS_REVIEW_PACKET.md`
(branch `claude/l1-loss-expressions-packet`, commit 00fc2fe2).
**Recorded by:** the implementing agent, from the coordinator's relay of the
Test Lead's review, verbatim below.

This file is the review record that both registered Level-1 variants name
(`review.record`):
- `carbon/reconstruction/development_variant_policies/battery-l1-loss-expressions-v1.json`;
- `carbon/reconstruction/development_variant_policies/battery-l1-loss-expressions-signed-v1.json`.

## The review, verbatim

"Test Lead review of the L1 packet (claude/l1-loss-expressions-packet,
00fc2fe2): APPROVED to build. Q1 RAISE: depth 32 / 512 nodes; add 1024 to
B10's measurement and widen in a later version if it rebuilds bit-for-bit and
compiles within the deadline. Q2 YES true ablations: one capability id per
operation family (time reductions; max/min/cap/excess; expm1; component
terms; wider constants). Q3 let degenerate losses RUN; flag statically
detectable no-ops as a diagnostic, never a refusal; scored as the candidate's
own result, never refunded. Q4 keep div GENERAL. Q5 JAX-only v1; torch later
with its own rebuild evidence; refusal stays typed. Q6 GPU identity REQUIRED
before citing pod results: local RTX 3060 then one pod inside an existing
grant; until both pass, L1 pod results carry 'rebuild: CPU-verified only'.
Addition: run the left-out signed operations (sub, neg, exp, constant leaves)
as a separate, separately-ablatable arm battery-l1-loss-expressions-signed-v1
in the ATTACK panel only, proving R1 on non-finite paths. Q7/Q8 owner-routed
(now answered: WAVE-04 §1 and §2)."

## The owner answers it cites

- **Q7: OWNER-GRAPHITE-TEST-WAVE-04 §1.** Anything that counts, limits,
  deduplicates or rewards distinct constructions identifies them by the
  rebuilt artifact's digest, never by recipe or expression text. At Level 1
  nothing is keyed on the expression digest; it is a diagnostic only.
- **Q8: OWNER-GRAPHITE-TEST-WAVE-04 §2.** For the test wave, the frozen
  rule's tail coverage is accepted as the instrument for U1 (metric-aimed
  training) and U2 (tail sacrifice) at Level 1. This is a TESTING acceptance
  only, not a scientific qualification of the rule. U1 and U2 results stay
  alignment findings, measured as τ/ρ, regret, false-feasible and tail
  metrics, and reported.

## Where each answer is implemented

The implementation is the Level-1 build (GRAPHITE-L1-BUILD-01,
`.agent/decisions/2026-10-05-GRAPHITE-L1-BUILD-01.md`).

| Answer | Implementation |
|---|---|
| Q1 | `carbon.battery.level1`: depth 32, 512 nodes, arity 16. The 1024-node measurement is in `docs/development/graphite/L1_REBUILD_MEASUREMENT.json`: 3/3 bit-identical across fresh processes, a 2000-step fit in 69.7 s on CPU. It is not enabled |
| Q2 | Six capability ids in the valid variant: the core and one permission per family, each ablated on its own in the climb |
| Q3 | `level1.diagnostics` flags no-ops; nothing is refused for them; tests show they are scored as the candidate's own result |
| Q4 | `div` is a / (b + ε) over any arguments |
| Q5 | `applies_to` mlp and deeponet; a non-JAX backend is refused by code |
| Q6 | Every Level-1 built record, result and report row carries `rebuild: CPU-verified only` |
| Signed arm | `battery-l1-loss-expressions-signed-v1`, registered as arm `signed`, used in the attack panel only |
