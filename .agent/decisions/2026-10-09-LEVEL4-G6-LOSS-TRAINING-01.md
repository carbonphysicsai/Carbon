## 2026-10-09 — LEVEL4-G6-LOSS-TRAINING-01: how battery trains a submitted loss graph

**Authority.** These are engineering decisions within the G6 loss slot v1
(the Test Lead's ruling of 2026-10-08, `docs/development/graphite/level4/PHASE1_PLAN.md`
§4.5) and LEVEL4-LOSS-OVERRIDE-01. The Level 4 engineer session made them
under the delegated decision protocol and notified the Test Lead. They are
development and testnet only.

**Decided.**
1. **The record carries the declaration.** The development-variant mechanism
   gains a Challenge-neutral `RECORD_BOUNDS` registry: a widened capability
   may name keys of its bounds that its built record carries
   (`carbon/reconstruction/development_variants.py`). Battery's Level 4 names
   `loss_override`. The rebuild reads the variant's declaration from the
   record alone. A variant that does not state the key adds nothing, so v1
   and v2 records are unchanged. A record without it admits no loss graph:
   G4 refuses one as `loss_not_permitted`, which is the candidate's.
2. **Carbon's plain mean, and no other loss term.** Under a loss graph, the
   loss is the graph's, mapped per case and reduced by Carbon's mean
   (`loss.per_case_mean`). Battery's own loss-term settings weight, select or
   reshape cases:
   - `important_region_weight`, `relative_loss`, `time_weighting`;
   - `h1_weight`, `h2_weight`, `spectral_weight`;
   - `curriculum`, `hard_example_weight`.

   Each must stay at its neutral catalog default (`level4_model.NEUTRAL`).
   Otherwise the submission is refused (`loss_graph_with_loss_terms`, the
   candidate's), never silently ignored. This follows `loss_override` being
   one choice among `none | terms | graph`.
3. **Battery's implementation modules are not edited.** `recipes.py` and
   `training.py` determine battery's implementation digest, and so every
   recipe digest (`implementation_versions`, invariant 10). Two pieces live
   in `carbon/battery/level4_model.py` instead:
   - the classic path's written-out loop, `classic_fit`, which already lived
     there and gains `objective=`;
   - a copy of `training.train` with only the loss replaced
     (`objective_train`), for the general path.

   A test pins the copy: with battery's own case loss as its objective, it
   reproduces `training.train`'s parameters bit for bit.

**Evidence (native CPU diagnostic; CI canonical).**
- A loss graph lowered from battery's own per-case loss trains to exactly
  the parameters of training on the JAX function it was lowered from. This
  holds on the classic path (scaffold MLP) and the general path (panel
  DeepONet), in process and in the isolated worker program.
- The trained state is self-contained, with the loss graph and the
  declaration in it.

**Not decided here.**
- **The aux limit.** `loss.AUX_LIMIT` stays `HUMAN_INPUT`, so no auxiliary
  output is admitted.
- **F4.** The loss graph runs inside the compiled training step, so the
  TRAINING-BUDGET-01 cost calculator counts it once it costs development
  recipes. It does not cost them yet, which is the existing open item in the
  variant's `compute_budget` bound.
- **Frozen or live rules.** No frozen or live rule declares an override.
  Adopting one is the owner's decision.
