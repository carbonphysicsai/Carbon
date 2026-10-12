# Heat conduction kit — Elmer

**PROPOSED reusable bundle; not a qualified family.** Buyer precedent: f02
burst-energy choice. Reuse `scripts/dev/reference_packages/elmer/` source lock
(Elmer 26.2.1), f02 decks/controls/export and
`docs/development/challenge_pipeline/code-verification/`.

## Once per applicable kit version

- Image identity: historical heat receipt names
  `sha256:6fab746f31257236da9e91b5be681bfbd2d25bd69f5dcd9a2e350394e8bcb675`.
  Owner acceptance covers hex808/BDF2 heat discretisation, MMS end time
  **0.375**, not a symmetry endpoint. Current image-store presence UNKNOWN.
- Law/output template: `E_in(t) - E_stored(t) - E_out(t)` with separately
  predicted, independently extracted cumulative joules, plus initial/peak
  temperature and registered two-sided interface T/normal-q probes. Declare
  outward signs, zero-energy absolute floors and initial-state subtraction.
  Superposition is on linear traces, **not maxima**. Full fields stay out.
- Observer proof: quadrature and storage/Robin integrals must close on the
  reference; refine the actual peak, time-grid and interface traces. MMS field
  convergence does not establish an accurate maximum or balanced interface.
- Public kit: reuse f02 generator/domain/representation hooks and onboarding
  tools. A new release still needs research, hypothesize, train, generate,
  evaluate, compute, model and agent provisions; solver access alone is not it.
- Comparator: multi-input spatial impulse response, RC/POD/state-space ROM and
  exact cache where applicable, not a weak one-node average model. Reuse
  `cheap-baselines/f02.md` and ready comparators.
- Equal budget: reuse ledger/arm interfaces and
  `equal-budget-registration-v2-f02-menu.json` only for its exact menu. New
  geometry/material questions need a new registration, including ROM basis
  acquisition and all verification calls.

## Per Challenge / reuse invalidators

Geometry, layered interfaces/contact law, property provenance, source waveform,
initial/Robin conditions, envelope, P/Q/w, buyer units, question law, TRAIN/panel
splits and refinement/observer uncertainty remain specific. Temperature-dependent
properties, radiation, phase change or new element/time schemes need additional
verification and adequacy; do not carry constant-property linear identities over.
Conjugate-fluid cooling belongs to the CFD kit, not this MMS acceptance.

Minimal outputs follow the §3.3 **proposal**, not an adopted f02 migration.
The interface/energy outputs are plausibly same-solve postprocessing, but their
CPU/export/prediction cost is NOT_MEASURED. New law thresholds, validity and
Tier-2 buyer-tool agreement are HUMAN_INPUT. First reuse gate: exact image +
matching formulation and observer proof, then the public winnability pilot.
Sources: [source register](../sources.md), [pilot](../winnability-pilot.md).
