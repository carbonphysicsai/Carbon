# Research environment standard

**Decision:** OWNER-RESEARCH-ENVIRONMENT-01 (2026-09-27)
**Applies to:** every Challenge with a construction contract, now and in future
**Enforced by:** `carbon/challenge_kit/standard.py` and
`tests/cpu/test_research_environment_standard.py`

## The rule

> The research environment MUST be enabled with everything miners need to
> research, hypothesize, train, test and iterate.

A miner who cannot generate data, train with the validator's own runtime, and
score their own attempts cannot do the work Carbon pays for. So every mining
environment is built complete from the start, and whatever is missing is
recorded as a named gap with a next step.

## What "everything" means

| Provision | A miner must have |
|---|---|
| `research` | The objective, population and sampling description, reference method description, public datasets and documentation. |
| `hypothesize` | The Challenge's full construction vocabulary, including research-only entries and why each is gated. |
| `train` | The validator's own construction runtime: the same pinned JAX environment and training code. |
| `generate` | The Challenge's public generator **and reference solver**, runnable in the sandbox with the miner's own seeds under the published population. Miners can make as much training and test data as they need. |
| `evaluate` | Practice scoring with the exam's own gates and metrics, on public or miner-generated cases, repeatable. |

## What the rule does not change

The rule covers what a miner can **use**. It does not widen what a submission
may **declare**, and it does not touch who grades.

- **Official evaluation stays private.** Official seeds, derived seeds, draw ids
  and reversible ids never reach any sandbox (invariants 1, 2 and 12;
  OWNER-CHALLENGE-KIT-01). Miners learn the population; they never see or
  steer the exam's draw.
- **Practice is not the exam.** Practice scoring uses the exam's gates on
  practice cases. It grants no reward, frontier or qualification (invariant 12).
- **Submission exclusions stay scoped to submissions.** A miner may run the
  reference solver to learn from it. A submitted model may not *call* the
  reference solver at prediction time, and a submission may not choose how
  the exam's reference answers are made (OWNER-BATTERY-TESTNET-03).
- **Seed separation is not decontamination.** Whether generated data lets a
  miner reconstruct the exam population remains a scientific judgement
  (Constitution §7.2), not something this standard settles.

## How to build a new Challenge's environment

1. Add the Challenge's entry to `ENVIRONMENTS` in
   `carbon/challenge_kit/standard.py` in the same PR that adds its construction
   contract. The test fails otherwise.
2. For each provision, point at the code that provides it (`module:symbol`),
   or declare a `Gap` with its reason and next step.
3. For `generate`, follow the Burgers kit: ship the validator's own generator
   and solver bytes into the miner research image, miner seed roots and mock
   seeding only, with a test showing no official seed material is present.
4. Close a gap by replacing it with `Provided(...)` in the PR that builds it.

## Retired Challenges

A Challenge the registry marks RETIRED owes no research environment. It is
declared `Retired(decision, provided)` as a whole, never per provision:

- **It is not a gap.** A gap is work owed; retired is work no longer owed.
  `gaps()` never reports it, and `Retired` cannot be built holding a `Gap`.
- **It stays readable.** `provided` keeps what it provided and through which
  symbols, and those symbols must still import, so evidence recorded while it
  was offered keeps its meaning (invariant 10).
- **It is prospective.** Retiring changes what is offered from now on, not how
  any recorded result is read.
- **It matches the registry.** A Challenge is `Retired` here exactly when the
  registry marks it RETIRED; a test fails if the two disagree.

## Current state (2026-09-27)

| Challenge | research | hypothesize | train | generate | evaluate |
|---|---|---|---|---|---|
| burgers-dynamics-v1 (retired; provided all five while offered) | retired | retired | retired | retired | retired |
| battery-fastcharge-ageing-development-v1 | provided | provided | provided | **gap** | provided (200 public PRACTICE cases) |

**Battery `generate` gap.** Nothing miner-facing runs the pinned PyBaMM
reference, so miners get only TRAIN v1 and the 200 PRACTICE cases. Next step:
`carbon/challenge_kit/battery.py`, following the Burgers kit.

**Training data for submissions is fixed per Challenge version.** A
submission cannot ask Carbon for extra training cases; that would reward
budget over method. Carbon may instead publish a larger TRAIN version for
everyone when a Challenge stalls and its budget allows (see
OWNER-RESEARCH-ENVIRONMENT-01 items 5 and 6).
