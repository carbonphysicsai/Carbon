## 2026-10-11 — SCORE-PROOF-PICKABLE-02: pickability is known-bad placement plus adversarial divergence (corrects PICKABLE-01)

**Authority.** The owner, verbatim, relayed by the Test Lead: "correct the
pickable check."

**Transparency.** This changes a pre-registered selection criterion **after
the selection was seen**. The 2026-10-11 selection (r8.1, registry v6) found
no pickable rule under PICKABLE-01:
- the registered adversarial members (8 Track A rebuild-identity
  constructions and EV5's two Mode X MLPs) decide well on the selection
  fold's questions;
- so placing them high is the correct value ordering there;
- and adversarial divergence was 0 for every rule.

**Decision.**
- **Pickable** (in force, `PICKABILITY_IN_FORCE = "divergence"`): no
  screened pool has a known-bad control in its top half, and none has
  adversarial divergence (an adversarial member scoring at or above a member
  of better value, `score_proof.adversarial_divergence`). Legs must also be complete.
  This replaces PICKABLE-01's adversarial placement screen; its known-bad
  placement screen is kept.
- **Selection only.** The confirmation's own FAIL-able screens, the gate
  recall, the sequential design and the sealed questions are untouched. The
  confirmation still refuses a rule its `--selection` report does not mark
  pickable.
- **Both criteria are reported side by side.** `selection.json` carries
  `pickable_by_criterion` (`placement`, PICKABLE-01's, superseded; and
  `divergence`, in force) and `pickable`, the criterion in force.
  `selection.md` lists the pickable rules under each, best pooled tau first,
  with gate recall.
- **The selection is rerun** with registry v7 (SCORE-PROOF-01 amendment 7)
  before any pick. The pick is frozen afterwards, before the confirmation
  unlock.

**Maturity.** DEVELOPMENT only; no rule adopted.
