# Scorelab exploratory findings (OPT-15)

**DEVELOPMENT, 2026-10-13.** These are toy and previously public EV4
diagnostics. They select no rule, threshold, population or Challenge. The V2
definition was read from PR #1253 at head
`f0debc9f65caf4d3ac206b10adec3e7898673338`; its values remain
HUMAN_INPUT. The definition bytes were unchanged at #1253 head `dd63e807a`;
the later change amended `BANK_SPEC.md`. Every numeric cost below is a lab
assumption.

## Analytic sweep

The complete toy grid varies space size, number of optima, coupled-constraint
tightness, condition shift and verification cost. Each profile has ten model
members and four falsification probes, with eight disjoint scoring and eight
value questions. The reference objective and feasible minimum are algebraic;
no numerical solver supplies truth. Bootstrap resamples recipe clusters and
value questions (200 replicates in this note). The small member and question
counts leave broad intervals, so point τ differences are exploratory.

The Validator's read-only `candidates.py` (SHA-256
`85c0503dffb2690df810556e117ec04900527358de1c6e2155431ddfa5023b4b`)
was also run across **all 32** toy
profiles with the three-verification buyer workflow, benefit unit 1, the two
assumed verification costs 0.02/0.2, and 100 bootstrap replicates. The
candidate-file digest is recorded in the JSON output. These are lab proxies,
including for the three registry families; public replay instead uses exact
registry code. Median τ / count of negative point τ among 32:

| Candidate family | Median τ | Negative profiles |
| --- | ---: | ---: |
| In-force proxy | 0.131 | 13 |
| V9 envelope proxy | 0.312 | 7 |
| V10 sign + envelope proxy | 0.179 | 8 |
| V2 rev 2, k=1, κ=0.05 | 0.129 | 10 |
| V2 rev 2, k=3, κ=0.1 | 0.431 | 1 |
| V2 rev 2, k=5, κ=0.25 | 0.306 | 1 |
| N1 decision relevance error | 0.121 | 12 |
| N2 verified regret on pick | 0.164 | 11 |
| N3 safe pick × gain | 0.126 | 10 |
| N4 top region ranking | 0.047 | 13 |

The k=1 and k=5 rows are **workflow mismatch probes** against a buyer who
verifies k=3; none of these point estimates selects a rule. For the k=3 V2
proxy, small-grid median τ was 0.249 versus 0.467 on the sampled continuous
space, and tight-constraint median was 0.173 versus 0.511 for loose. This
is a constructed population, so the full sweep is a falsification tool rather
than evidence that V2 wins a real Challenge.

Under a **matched V2 buyer workflow** (top three shortlisted and verified,
benefit unit 1, verification cost κ = 0.1 per action, 16 profiles across the
other four knobs):

| Score family | Median point τ | Profiles with τ < 0 | Profiles with 95% lower bound > 0 | Median top-1 regret to analytic oracle |
| --- | ---: | ---: | ---: | ---: |
| Registry v9 `A` | 0.059 | 6/16 | 2/16 | 0.203 toy benefit units |
| Historical in-force family `G-FEAS/A-Q>@0.05` | 0.158 | 5/16 | 1/16 | 0.203 toy benefit units |
| V2 rev-2 with the stated κ, k, u and an explicit toy G-FEAS gate | 0.423 | 1/16 | 1/16 | 0.198 toy benefit units |

The largest shift is **small-grid versus continuous**: median τ for the
V2 candidate is 0.274 versus 0.458, while v9 `A` is −0.092 versus 0.489.
Tight constraints lower V2's median τ from 0.476 to 0.140; shifted contexts
lower it from 0.458 to 0.260. A toy V2 rule can rank more consistently when
its shortlist/solve accounting matches the buyer workflow, but this does not
demonstrate that a real bank is winnable. On the default one-pick workflow,
the same V2 settings have 16/32 negative point τ: **the buyer job must be
registered before comparing score rules.**

## Public EV4 replay

The digest-checked public copy contains 100 registered EV4 members. Scoring
uses 12 public development scenarios; value uses the eight verification
scenarios resolved for every member (12 offered). With 200 crossed bootstrap
replicates, registry v9's single legs give:

| Rule | τ | Exploratory 95% interval | Top-1 regret to best of 100 (EV4 decision-loss units) |
| --- | ---: | ---: | ---: |
| `A` | 0.334 | [0.058, 0.456] | 1.255 |
| `R` | 0.333 | [0.031, 0.452] | 0.089 |
| `P` | 0.375 | [0.046, 0.466] | 1.252 |

The similar τ does not mean the same top choice: `R` has lower top-1 regret
on this pool. This is retrospective EV4
CV-onset proxy evidence, **not** battery-v3 buyer value or fresh confirmation.

EV4 supplies no Q3 leg for the historical A/Q composite and no full-output
score bundle for the RES-08 bilinear arm. Their EV4 score ranks are left
unmeasured. The prospective V2 rule refuses this EV4 job as an unregistered
V2 bank. PR #1253's bank spec notes that only two nominal and one shifted EV4
question survive V2's complete-reference, feasible-fallback admission; these
old questions cannot serve as a V2 confirmation bank.

## Implication for Challenge/question design

The toy score's alignment changes with action grammar, constraint coupling,
condition shift and verification workflow. A candidate Challenge needs a
registered, complete question bank with headroom beyond a frozen cheap arm,
then separate fresh confirmation. Scorelab makes these failure modes cheap to
probe; it cannot replace producer reference solves or the sealed final gate.

Sources: `score_tuning.py`, `score_proof.py`, `decision.py`, the committed
RES-07/08/09 public research under `Business/research/value-metric-*`, and
PR #1253's `definition.v2.json` and `BANK_SPEC.md`. Raw public bundles and
derived per-member cache remain local and uncommitted.
