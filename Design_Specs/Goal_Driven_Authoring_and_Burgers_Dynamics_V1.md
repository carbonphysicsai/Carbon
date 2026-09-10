# Goal-driven authoring and Burgers Dynamics V1

**Ticket:** C-AUTH1

**Status:** bounded development implementation; scientific and network authority
remain unavailable

**Source workbench release:**
`sha256:7805f87c3b4745454ec9c8fa852a20de6731d8f85e1356eb5d91a708cdafa7ac`

**Burgers Dynamics V1 package:**
`sha256:4fa6828a38050bd34fd76019fa472bdcd141a7f788ac09103544e4de0ffcd716`

**Corrected execution freeze:**
`sha256:f6624238cb5c07fc15ce0b94477336041fb1ef879454aa2d39e0e6f53eeb2788`

## 1. Boundary and ownership

C-AUTH1 adds a closed goal-intake compiler and a public-development Burgers
generator. The compiler emits a proposal. It does not call the registry,
execute a strategy, qualify a reference, activate a ScorePack, archive evidence,
publish a result, or authorize a network action. Existing Carbon owners remain
canonical:

- `carbon.authoring` owns physical, population, sampling, training-support and
  case-reference contracts;
- `carbon.generators` owns deterministic physical generation;
- `carbon.seeding` owns role/domain derivation;
- `carbon.reference`, `carbon.measurement`, and `carbon.scoring` retain their
  existing authority;
- D-03/D-04 still own reference qualification; and
- C-EA0 through C-EA3 still own capture, custody, retention and archive
  acknowledgement.

The supplied workbench scheduler and approximately 193 MB of derived field
artifacts are deliberately not imported.

## 2. Intake and canonical proposal

`python -m carbon.authoring compile-goal INPUT OUTPUT_DIRECTORY` accepts either
the closed `goal-authoring/1` intake or a workbench package whose intake and
package digests verify under `carbon-authoring-v1`. The only supported template
is `periodic_viscous_burgers_1d_v1`. Unknown fields in the intake, non-finite
numbers, changed science literals, duplicate JSON keys, oversized input, digest
tampering and unsupported templates fail closed.

The result is canonical sorted JSON with a domain-separated content digest. It
is written to `objects/<digest>.json` and the stable `proposal.json` alias using
exclusive creation. Exact replay returns `ALREADY_PRESENT`; differing bytes at
either identity fail with `goal_authoring.output_conflict`.

The proposal describes one competition, Burgers Dynamics V1. Dynamics is the
active primary goal report. Transport, Front Resolution and Dissipation are
prepared inactive specialist reports over the same population and references;
they are not separate pools. Weights are emitted as reduced rational
numerator/denominator pairs, never binary-float policy identities.

Every capability flag is false. The proposal status is
`DEVELOPMENT_PROPOSAL`, the score status is
`NEW_DEVELOPMENT_SCORE_PROPOSAL_NOT_A5_ACTIVATION`, and all reference candidates
are `NOT_QUALIFIED`.

## 3. Exact Burgers development law

The generator preserves the supplied synthetic periodic, unforced,
positive-viscosity one-dimensional Burgers law

`u_t + d_x(u^2/2) = nu*u_xx`

on a domain of length `2*pi`. Initial fluctuations contain only Fourier modes
1 through 12. Three shape families cross four effective-Reynolds intervals to
form 12 equal-mass cells:

- harmonic;
- a localized packet projected from 4096 periodic points onto exactly 12
  modes; and
- multiscale.

For every case, `A` is uniform on `[0.15, 0.35)`, `mean/A` is uniform on
`[-1, 1)`, and effective Reynolds number is log-uniform in one of
`[0.5,1)`, `[1,2)`, `[2,4)`, or `[4,8)`. The generator sets
`nu=A/(Re*k_rms)`, `t_c=min(1/(A*k_rms),1/(nu*k_rms^2))`, and `T=4*t_c`.

The complete public plan is exactly 72 TRAIN parents (two builds, three per
cell per build), 48 EVAL parents (four per cell), and 120 STRESS parents (ten
per cell). Only an exact A4 `MockContext` is accepted. Separate TRAIN, EVAL and
STRESS role keys are used. Official and qualification contexts cannot enter
this generator. Every emitted record is marked development-only and explicitly
ineligible for protected evaluation.

## 4. Query, measurement and score proposals

Candidate queries contain only `initial_field`, `viscosity`,
`requested_times`, and `domain_length`. Initial values are evaluated from the
declared 12-mode trigonometric representation at the requested points. A
point-query is not silently replaced by a low-pass projection.

The measurement proposal retains raw field, maximum-compression,
peak-dissipation and energy-half-time errors, phase windows, censoring state,
physics defects and numerical uncertainty. Compression extrema use fourfold
periodic trigonometric interpolation of the derivative. Physics eligibility
precedes quality aggregation. The development uncertainty gate is:

- pass when `defect + uncertainty <= limit`;
- fail when `defect - uncertainty > limit`; and
- indeterminate otherwise.

An unresolved numerical budget is evaluator failure, not candidate failure.
The new score proposal combines one-half population-weighted mean performance
with one-half maximum-cell empirical 90% CVaR reliability only after mandatory
physics. It does not alter A5 history or activate payment eligibility.

## 5. References, controls and JAX handoff

The dealiased conservative Fourier ETDRK4 method is the primary development
reference candidate. The stabilized Cole-Hopf Gaussian-expectation method is
an independent development witness. Neither is qualified. Spectral 32/64/128,
heat, memorizer and the two small kernel builds remain development diagnostics,
not representative miners or accepted baselines.

The actual authorized JAX source repository, immutable revision and real
training/inference API remain missing. The required interface input includes
its entry points and signatures, accepted array shapes/dtypes, state and frozen
artifact representation, dependency/build identity and typed failure behavior.
C-02 must implement Carbon's thin trusted adapter around whatever interface that
pinned source actually exposes; it must not require the SciML lead or upstream
repository to adopt Carbon-authored function names. The adapter must provide the
following semantic capabilities inside Carbon:

1. fit from TRAIN-labelled arrays only;
2. freeze an artifact with exact reconstruction identity; and
3. infer requested points for the four-field candidate query.

No neural-operator capability, scientific qualification, testnet eligibility,
archive acknowledgement, production status, public-network action, payment or
LIVE maturity follows from C-AUTH1.
