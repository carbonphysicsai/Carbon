## 2026-10-05 — GRAPHITE-ATTACKER-COOLING-API-01: cooling's vectors as a pure public API

**Amends:** GRAPHITE-ATTACKER-COOLING-L0 and GRAPHITE-ATTACKER-COOLING-SF-01
(`.agent/decisions/2026-10-04-GRAPHITE-ATTACKER-COOLING-L0.md`,
`.agent/decisions/2026-10-05-GRAPHITE-ATTACKER-COOLING-SF-01.md`). Those
records are not edited; this one adds to them.

**Authority:** the owner-approved cooling adapter scope (OWNER-GRAPHITE-ATTACKER-01,
OWNER-GRAPHITE-TEST-WAVE-01..03). The Carbon Validator's gate-audit harness
(VALIDATOR-09) asked to reuse the cooling attack vectors by import instead of
copying them. Engineering decisions inside that scope; no scientific value,
threshold, tolerance, weighting or validator behaviour is chosen or changed.
The validator itself is not touched.

**Files:** `carbon/agent_campaign/attack/adapters/cooling.py`,
`tests/cpu/test_attack_cooling_vectors.py`,
`carbon/challenge_pipeline/lessons/2026-10-05-attacker-cooling-vector-api.json`.

### COOL-API-D1 — The API

- `VECTOR_NAMES`: `cooling_optimism`, `flow_imbalance_masking`,
  `pressure_underprediction`, `group_sacrifice`, `selective_fault`,
  `mandatory_failure`. Each is the attack example of the family of the same
  name, and the tuple is part of `ADAPTER_VERSION`.
- `apply_vector(name, references, *, important=None) -> predictions`: pure (no
  file, store or network), takes case id to a PRACTICE-shaped record
  (`inputs.inlet_c`, `outputs.peak_c`, `outputs.profile_c`,
  `outputs.pressure_drop_pa`) and returns a fresh prediction set. `important`
  defaults to the frozen rule's own group (reference peak at least
  `T_IMPORTANT_C`, 85), computed from the references passed in.
- `faulted_cases(name, case_scores, *, k=None, important=None)`: the
  `selective_fault` selection (`FAULT_SELECTIONS`: worst k, hot group, above
  own mean, worse half, none, all) over the caller's per-case error. `k`
  applies to `worst_k` only (default a tenth, at least one). `hot_group` needs
  `important`, because scores carry no reference peak. That keyword was added
  to the requested signature.
- `UnknownVector` (an unknown vector or selection) and `VectorError` (a
  `ValueError`, typed by `code`): `fault_pattern` (selective_fault passed to
  `apply_vector`), `malformed_reference`, `malformed_important`,
  `no_important_case`, `malformed_case_score`, `malformed_k`,
  `k_not_applicable`, `important_required`.

### COOL-API-D2 — The refactor, byte for byte

The transforms (`_rise_scaled`, `_shifted`, `_pressure_scaled`,
`_redistributed`, `_reversed_profiles`, `_corrupt`) now take the reference set
as their first argument. The families and controls pass the adapter's own
public PRACTICE references (`_references()`, the records behind
`_oracle_predictions()`). The transforms need each case's inlet, so they take
records rather than bare predictions. `_faulted_cases` delegates to
`faulted_cases` with the scaffold's errors. The face-at-inlet edit moved to
module level, so `mandatory_failure` and the family share it. Before the
refactor, a test pinned the digests of seven families' attacks and oracle
evidence and specimen readings, `selective_fault`'s attacks, both control
splits and every fault selection on the scaffold, as recorded at `b327ac12d`.
The pin held after the refactor, so the refactor left the emitted output
unchanged. COOL-API-D4 then moves `group_sacrifice` on purpose.

### COOL-API-D3 — What it is not

A vector applied to a caller's references is a transform, not a verdict. Only
the caller's harness grades it. The API reads no file, so it cannot reach
counted, study, confirmation, private or sealed material. An audit-hook test
binds this, and the adapter's own audit-hook test still passes.

### COOL-API-D4 — `group_sacrifice` made a real sacrifice (v3)

The Carbon Validator's read-only review of #621 found that `cooling_optimism`
and `group_sacrifice` used the same transform. Both set the hot group 20% low
and left the rest exact, so their predictions were byte-identical, and a
per-vector catch count would count one attack twice. The Validator's review is
credited with the finding.

`group_sacrifice`'s attack example is now
`hot_group_rise_twenty_percent_low_rest_compensating` (`_sacrificed`, pure).
The hot group's rise above the inlet is still 20% low. Every other case's rise
goes up by `1 + f`, where `f = 0.2 * sum(hot rises) / sum(other rises)` is
computed from the reference set passed in. The signed peak errors therefore
sum to zero, and the mean signed peak bias is held at zero up to round-off:
about 2e-15 K on the public PRACTICE references, with 30 hot cases out of 100.
The old `rest_exact` attack was the optimism attack again, so it was replaced
rather than kept. `group_sacrifice` also refuses an empty hot group
(`no_important_case`) and a set with no representative rise to compensate
(`no_representative_case`).

- **Verdict:** the family still HOLDS at the real boundary, and its specimen
  (`pooled_group_scorer`) still FIRES. The set is eligible, its overall score
  is 0.341 and the hot group's score is 0.564, reported apart.
- **Versions:** the attack is emitted output, so `ADAPTER_VERSION` moves to
  `cooling-l0.v3`. The controls are unchanged, so `CONTROLS_VERSION` stays
  `cooling-l0.v2`.
- **Byte pin:** the v2 pin is kept, and the test asserts that the only digests
  to move from it are `group_sacrifice`'s attack and its evidence and specimen
  readings. Every other family, both control splits and every fault selection
  are unchanged.
- **New tests:** no two vectors give the same predictions, on the real
  references or on a synthetic set. A mutation that maps `group_sacrifice`
  back to optimism's transform turns that guard red, and the direction guard
  as well.
