## 2026-10-04 — OWNER-GRAPHITE-DEV-LEVELS-01: what a development-only level may widen — Carbon-drafted surfaces, and Level 3 a declarative menu only

**Authority.** The owner (Ryan), 2026-10-04, in the Test Engineer's session.
OWNER-GRAPHITE-TEST-WAVE-03 (`.agent/decisions/2026-10-04-OWNER-GRAPHITE-TEST-WAVE-03.md`,
carbonphysicsai/Carbon#574) §1 states these two answers and says they are
recorded with W1's foundation PR. This file is that record.

**Context.** WAVE-03 §1 lets a level above a Challenge's miner-facing
contract be served to Carbon's own registered Graphite campaigns through a
development-only contract variant, held outside
`capability_registry.CONTRACTS` and pinned by its own digest. The six accepted
battery level proposals (`carbon/challenge_pipeline/proposals/battery-…-v1/`)
widen nothing beyond the live contract: Levels 1, 2 and 5 list capabilities
that are already rebuildable, Levels 3 and 4 are empty, and Level 1 keeps
`loss_expressions` excluded. So they do not supply the Level 1–3 surfaces, and
two questions were put to the owner.

**F1. Where a development level's surfaces come from.**
- **The question.** The accepted proposals widen nothing past the live
  contract. May a development-only variant, which is never served to miners,
  widen to a surface Carbon drafts?
- **The owner's answer, verbatim:** "Drafted surfaces OK"
- **What it means.**
  - For development-only variants (never served to miners), each level may
    widen to a surface Carbon drafts.
  - The draft is reviewed by the Test Lead and recorded as a registered,
    versioned policy, with its bounds.
  - No technical-owner acceptance is needed for internal use.
  - Opening any surface to miners still needs that acceptance.

**F2. What Level 3 may be.**
- **The question.** Admission §3's Level 3 is "Training-time numerical
  routines such as preconditioners". How far may a development-only Level 3
  go before the security owner accepts isolation?
- **The owner's answer, verbatim:** "Declarative menu only"
- **What it means.** Level 3 is a fixed, bounded menu, held as data. It runs
  no participant code until the security owner accepts isolation.

**Unchanged.**
- A level tested internally is never opened to miners to gather acceptance
  data. Opening a level to miners is still a locked, released contract that
  the owners choose (WAVE-03 §1).
- Running hostile executables (Levels 4–5) still needs the security owner's
  isolation acceptance (WAVE-03 §3). This decision grants none.
- The climb procedure applies to every variant: an expansion record for it,
  Carbon's reconstruction shipped with it, matched panels, ablations and
  combined-permission attacks.

**Where it is implemented.** GRAPHITE-DEV-VARIANTS-01
(`.agent/decisions/2026-10-05-GRAPHITE-DEV-VARIANTS-01.md`) and
`carbon/reconstruction/development_variants.py`. That PR ships only the
mechanism, with an empty registry. Real Level 1–3 surfaces come in later work,
after the Test Lead reviews them.

**No execution and no spend.** This record creates no grant and runs nothing.
`.agent/DECISIONS.md` is not edited.
