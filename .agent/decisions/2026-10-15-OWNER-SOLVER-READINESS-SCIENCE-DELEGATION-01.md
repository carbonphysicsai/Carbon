## 2026-10-15 — OWNER-SOLVER-READINESS-SCIENCE-DELEGATION-01: the engineering team derives the science values needed to make the solver data ready

**Authority.** The owner, 2026-10-15, directly in a Claude Code session
(hello@carbonphysics.ai). Verbatim:

> For now, you are taking the work of those other teammates. My initial thought
> is that we need to get these challenges to a point we are CONFIDENT in the
> solver data that we need to go get so that we can spin up a massive hourly
> machine to go knock out a bunch of them at once. My goal is to get as many of
> these challenges to THAT point as we can.

> I delegate science values to you and the team. Use the challenge brief and
> customer problem to derive the optimal values

**What is delegated.** For the Challenge families in the solver-readiness
program (f02, f06, f08, f13, f17, and any later family the program takes on),
Claude and the agent team it directs set the DEVELOPMENT science values the
reference-data path needs, where the repository records them as HUMAN_INPUT:

- numerical verification and convergence acceptance bands (mesh, time,
  frequency, mode, resolution, PML/padding, lead length, conservation);
- reduced-route versus full-route and cross-tool agreement tolerances, and
  decision-agreement thresholds;
- question-law values: population P, proposal Q, weights w, bank size B, batch
  size n, k, bands, tie rules and NONE_FEASIBLE handling;
- the numerical-adequacy choices a family needs to freeze its decks (for example
  the f06 grid, the f13 port-lead treatment, the f17 high-Pe transport scheme).

**How a value is set.**

1. Derive it from the family's Challenge packet
   (`docs/development/challenge_pipeline/round1/<family>.md`) and the customer
   problem it states: the buyer's decision, its limits and units, and what error
   would flip that decision. Where the repository already holds a numeric
   recommendation, start from it and adopt it unless the derivation shows it is
   wrong; say which.
2. Record each value with its basis in a dated decision file, one per family
   (`.agent/decisions/2026-10-15-<FAMILY>-SCIENCE-VALUES-01.md` or later).
3. Set an acceptance value before looking at the result it judges. Where a
   result was already observed, the record says so. A value is never loosened
   to make an observed result pass; a result that fails stays a finding.
4. Values are versioned and prospective. Already-sealed evidence keeps its
   original contract.

**What this does not change.** These are DEVELOPMENT values. This record grants
no scientific qualification, no Tier 2 or Tier 3 credibility claim, no LIVE
status, no reward, and no spend. Hidden and sealed material, mainnet, network
activation and every money figure stay with the owner. A paid run still needs
its own grant. The owner may change or revoke any delegated value by a later
record.
