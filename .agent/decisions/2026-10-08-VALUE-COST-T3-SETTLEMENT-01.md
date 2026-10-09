# VALUE-COST-T3-SETTLEMENT-01 — digest-bound settled candidate verdicts

**Ticket:** VALUE-COST-T3-SETTLEMENT-01. **Status:** working engineering decision.

The existing report treats any reference-band candidate as making a whole
question unresolved. That discards settled two-rung verdicts and questions
whose remaining uncertainty cannot change the buyer's decision. The producer
export will optionally name a nonempty refinement rule ID and the method
`two-rungs-same-side-change-below-band.v1`. Each question then includes an
explicit settled list (possibly empty), indexed in registered band order where
applicable. Both fields are covered by the sealed export digest. Data
Collection verifies the rungs; `design_search` checks identity, structure and
consistency with already resolved references, but does not infer a verdict.

The power path tests whether hypothetically making every still-unresolved
candidate feasible changes the selected winner. If it cannot, the known
winner stands. With no known feasible candidate, a remaining unresolved
candidate still blocks NONE_FEASIBLE. One mandatory NONE_FEASIBLE band fixes
the whole indexed map. A model's own pick of a still-unresolved candidate is
unscored for that model, and its aggregate unscored mass is visible. The old
export without a named rule continues through the old interpretation.

Implementation is confined to `carbon/design_search/reference_resolution.py`,
the producer adapter, plain/indexed power paths, task-freeze pin, toy tests,
and the producer runbook. Alternative choices were to fabricate a narrow
margin outside the band or alter generic score judgments; both could change
scientific meaning outside the diagnostic and were rejected. This optional
format is reversible before producer adoption. A future mismatch with Data
Collection's export needs an explicit format migration; the smallest change
would be the adapter's settled-field parsing. No human-reserved threshold or
qualification decision is selected.
