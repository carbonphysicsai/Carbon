# Battery-v3 N1 diagnostic binding v1

**DEVELOPMENT diagnostic only.** This is the owner-approved, prospective
five-scalar/indexed input binding of the complete frozen N1 family. It does
not adopt a score, enable a championship, qualify the reference, reconstruct
the historical v2 rule or unlock the final holdout.

## Registered inputs

The byte-identical `APPROVED_PROPOSAL.md` and `TRAIN_SCALE_RECEIPT.json`, plus
`OWNER_APPROVAL.json` with only CRLF-to-LF normalization, preserve the exact
approved scope and public construction-only statistics. The approval's original
raw digest and normalized-copy digest are both registered; its JSON document
is unchanged. `registration.json` fixes the input mapping,
scale literals and algorithm, voltage floor, relevance bands, inactive original
wrappers and restrictions. The adapter pins its raw SHA256:
`c3997852ea0ca66e392ebc4849c76f34b7e3d929bf35eb9a5c2f605e114b8c4e`.

The frozen ten-family source remains byte-identical at SHA256
`157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`.
The existing checked-byte loader imports it. Its full wrapped native N1 call
supplies the authoritative score; the adapter reuses its point-error and
feasible-optimum helpers to expose grouped contributions. Algebraic equivalence
does not imply bitwise equality. The reported operation-count/ulp check is an
engineering arithmetic check, not a physical tolerance or takeover margin.

The unchanged producer builder verifies every offered source/rung/observer,
complete calibration and raw delivery mapping. The adapter additionally binds
each constructed `ValidatedEvidence` to Root's independently prebound plan,
source-pin and manifest digests. A raw dictionary or calibration flag is refused.
The same strict reference-only `owner_v3.reference_mask` determines whole-question
coverage for every model. Numerical failure stops reference use; this adapter
cannot authorize continuation or relax the 4.2-V limit.

## Root's invocation after main registration and adequate references

There is no solver, model fit, host dispatch or hidden-material loader here.
Root must register this PR on main **before A05 label inspection**. This file
does not substitute for that chronology or for actual reference adequacy.
The public producer's `HELDOUT_REFERENCE` role means the development comparison
panel, not the separately protected final holdout in owner D7.

Use `scripts.dev.score_lab.owner_v3_n1`:

```python
# Root supplies these objects from the EXISTING authenticated producer build.
# Each row is {"draw": original_draw, "evidence": validated_producer_evidence}.
# Each independent binding is keyed by draw["task"]["task_digest"] and has
# exactly plan_digest, source_pins_digest and manifest_digest.
from scripts.dev.score_lab import owner_v3_n1 as diagnostic

leg_result = diagnostic.score_leg(
    leg_rows,
    predictions_by_task,
    producer_bindings=leg_bindings,
    expected_registration_digest=diagnostic.REGISTRATION_SHA256,
    population="P",
    scope="PUBLIC_DEVELOPMENT",
)
value_result = diagnostic.judge_values(
    value_rows,
    original_commitments_by_task,
    producer_bindings=value_bindings,
    expected_registration_digest=diagnostic.REGISTRATION_SHA256,
    population="P",
    scope="PUBLIC_DEVELOPMENT",
)
report = diagnostic.alignment(
    legs_by_member,
    values_by_member,
    recipe_of=frozen_recipe_identity_by_member,
    gamers=registered_gamer_member_ids,
    bootstrap=explicit_exploratory_replicates,
    seed=explicit_public_analysis_seed,
)
```

`predictions_by_task[task_digest]` uses the same shape as the producer's
references: five ordered dictionaries `{index_value, values}`; `values` maps
`(candidate, condition_id)` to all five scalar quantities. Root maps the saved
prediction export's `(band, candidate, condition)` rows to this shape without
fitting or changing them. The original pre-reference commitments remain the
input to `judge_values`; do not rerun selection using references.

`score_leg` accepts LEG rows only and checks all roles before reading reference
values. VALUE rows cannot enter its denominator, relevance weights or scores.
The current public registration supports P; Q discovery support is still
unregistered and refused. Fixture-only Q can test population separation, never
become evidence of a registered public Q law. Every measure retains its
population identity. All twelve actions and all five mandatory bands, including
zero buyer-weight bands, contribute to the error bank. Buyer mix is used only
by the registered VALUE objective.

## Interpretation and failure semantics

- N1's contributions are `n_LEG/W_LEG * sum_band_action(w_i*e_i)` per original
  buyer question. Never average per-question transformed scores. Bands/actions
  are not independent cases. Empty/zero/nonfinite reductions are unavailable.
- The separately named `SCALAR-ACCURACY-CONTROL-v1` uses the same five errors and
  scales without relevance weights. It is neither INFORCE-G-FEAS/A-Q nor an
  eleventh shortlist candidate. Voltage remains in error and relevance: if a
  zero reference margin makes all weights one, report N1/control equality.
- Missing or invalid predictions withhold the whole member, including coverage
  on excluded questions. Unresolved references exclude the whole question for
  all models and never impose a candidate penalty. NONE stays in P.
- `judge_values` reuses the existing owner-D2 per-band minute deadzone and
  any-band hard-breach handling; no finite unsafe/missed penalty is invented.
- `alignment` selects each rule's top three from its complete LEG score roster
  FIRST, reusing `owner_dev_v1.select_top_three`. Its historical field names
  `admitted_count` and `admitted` describe only this mechanical diagnostic pool;
  they do not establish scientific admission. A selected unsafe/missed member
  makes the top-three VALUE comparison unavailable, with no replacement.
  With no registered gamer members, the explicit adversarial screen is
  UNMEASURED with no pass flag; the reused selector's vacuous boolean is not
  evidence of attack coverage. No gamer cohort is invented.
- Tau/rho are conditional on the explicitly listed members with complete safe
  VALUE vectors over the common reference-adequate FEASIBLE_EXISTS stratum.
  Every offered member's typed outcome counts remain reported. This is not a
  full-P value scalar or a whole-panel alignment claim when members are excluded.
- The existing `score_proof` bootstrap resamples recipe clusters and VALUE
  questions; LEG scores and the bank are fixed. Its joint interval and paired
  delta against the named control are exploratory, conditional on this bank.
  Eighteen seed fits are six recipe clusters; one bank is not many independent
  banks. No ulp-scale ordering benefit establishes physical value.
- Legacy trajectory/admission measurements remain UNMEASURED. This diagnostic
  cannot produce a Stage-C/D winner, keep-v2 decision, adoption or qualification.
  Old registration and historical evidence remain unchanged.

The functions return internal developer evidence including task identities and
typed per-question outcomes. They are not miner disclosure APIs. Author tests
are synthetic; Root alone runs actual TEST/data work and owns all spending.
