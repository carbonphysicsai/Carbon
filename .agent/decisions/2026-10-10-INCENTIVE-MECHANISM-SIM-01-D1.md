## 2026-10-10 — INCENTIVE-MECHANISM-SIM-01-D1: conditional comparison surrogate

**Authority:** owner-assigned development analysis; `.agent/tickets/INCENTIVE-MECHANISM-SIM-01.md`. **Status:** implemented analytical working decision, not a score, promotion or economic-policy change.

**Decision:** use the committed 27-row public Graphite run-5 practice panel to calculate a pinned median within-recipe seed spread. Treat that spread as an *assumed* window-mean score noise scale in a Gaussian agent-based simulation. Preserve the development rule's margin, case minimums, alpha and important-region block, but approximate the 4,000-draw percentile bootstrap with a normal interval for the broad sweep. Represent current paired same-case comparison and an explicitly counterfactual unpaired mode. Emit only aggregate predictions; keep all scientific and economic values as declared assumptions.

**Why:** there is no committed independent multi-window exam-noise panel, and an exact 4,000-draw comparison in every strategy/window/replicate would obscure the conditional sensitivity question behind cost. Public seed spread is an auditable proxy; it cannot be called a measured exam variance. A deterministic summary model makes the sweep reproducible and testable without solver or hidden evidence.

**Alternatives rejected:** inventing a hidden-window variance; treating practice seed noise as calibrated exam noise; applying the simulated result to a validator; allowing raw score inequality to pay a miner; claiming target weights as observed emissions; selecting margin/decay/allocation from these curves.

**Where:** `scripts/dev/incentive_mechanism_sim.py`, `docs/development/incentive-mechanism-sim/`, and synthetic tests. The Validator canary may compare its controlled observations with the registered-margin, paired, current-halving prediction slice. Material mismatch should revise this analysis prospectively; it cannot revise historical scientific or economic records.

**Owner input retained:** challenger margin, reward decay, emission split, per-party rate control, policy adoption and any LIVE use.
