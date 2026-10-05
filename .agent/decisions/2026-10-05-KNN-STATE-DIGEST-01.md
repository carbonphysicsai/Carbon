## 2026-10-05 — KNN-STATE-DIGEST-01: battery KNN gets a versioned state digest, and `params_sha256` keeps its meaning

**Authority.**
- The Test Lead approved this fix (2026-10-05). It was queued in
  NOOP-CAPABILITY-AUDIT-01 §2 and §6, inside the owner-approved Graphite test
  wave (OWNER-GRAPHITE-TEST-WAVE-04, -05 and -06).
- Identity for counting and rewarding is the rebuilt artifact
  (OWNER-GRAPHITE-TEST-WAVE-04 §1).

Everything below is an engineering choice within that delegated authority.
No construction contract, admission rule, scientific value, gate, score or
tolerance changes. There is no live run and no spend.

**The defect.** `recipes.KNN.fit` reports `params_sha256` as the digest of the
stored TRAIN targets only. The neighbour count changes predictions but not
that digest, so two KNNs that predict differently shared one trained-parameter
identity.

**Decisions.**

1. **A new digest, and the old one unchanged.**
   - `state_sha256`, with `state_schema` set to `carbon.battery.knn-state.v1`,
     binds `k`, `train_fraction`, the unit inputs and the targets.
   - The digest covers a canonical JSON header (schema, `k`,
     `train_fraction`, and the dtype and shape of both arrays), then a zero
     byte, then the little-endian float64 bytes of the inputs and targets.
   - `params_sha256` stays bit-identical to the exam-design campaign's KNN
     (`test_promoted_recipes_match_the_campaign_recipes_bit_for_bit`), so a
     recorded value keeps its meaning (invariant 10).

2. **Placement: a separate module, so no Level-0 identity moves.**
   - The digest lives in `carbon/battery/knn_state.py`. That module is not in
     `contracts.IMPLEMENTATION_MODULES` and not in the practice worker's
     `STAGED_MODULES`.
   - `compile.rebuild` adds it to a KNN's fit statistics. `compile.py` is in
     neither list either.
   - `recipes.py` is untouched. The Level-0 implementation, recipe,
     built-record and program pins (#611) and the run-5 baseline are
     unchanged, and nothing is re-pinned.
   - **Trade-off.** The GPU pod and practice worker program does not stage
     the module, so its fit statistics carry no `state_sha256`. Emitting it
     there would mean staging the module, which moves the program digest.
     That would need its own versioned re-pin and is not done here.

3. **Identity: `knn_state.trained_identity(stats)`.**
   - A fit that carries the digest is identified by
     `("carbon.battery.knn-state.v1", state_sha256)`.
   - Every other fit, and every record written before this change, keeps
     `("params_sha256", params_sha256)`.
   - An unknown `state_schema` is refused. It is never read as another
     scheme.

4. **Consumers.**
   - **Changed.** The no-op audit's battery adapter
     (`tests/cpu/test_construction_noop_audit.py`) now reads
     `trained_identity`. The `architecture.neighbours` / `knn` entry left
     `KNOWN_NO_OPS`, so the audit now requires the neighbour count to change
     the artifact.
   - **No other identity reads `params_sha256`.** No WAVE-04 §1 counter in
     the Graphite, attack-campaign or validator code reads it:
     - the run-5 alias check compares prediction bytes;
     - the Level-1 attack adapter digests the gate outcome.
   - **Not identity.** Practice feedback shows `params_sha256` as a fit
     statistic only, and that disclosure is unchanged.

**No execution.** This record dispatches, provisions and spends nothing.
