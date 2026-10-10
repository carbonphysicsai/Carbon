# Public practice decision signal (proposal)

**Status:** DEVELOPMENT prototype for PRACTICE-DECISION-SIGNAL-01. The owner
decides whether to expose this in Launchpad. This document changes no practice
score, gate, exam, or LIVE rule.

## Proposed measure and miner view

Use the registered, digest-pinned `practice-decision-set-v2`: six public
ambient/starting-charge conditions and the fixed 35-protocol EV4 grid at each
condition. A model predicts the complete grid; the frozen model-only selector
chooses the protocol it predicts will be feasible and fastest, or abstains.
The public reference checks that choice with the registered uncertainty bands.
The rule and set identities travel with every result.

The proposed practice card places **public decision regret** and **public
false-feasible rate** beside practice accuracy. Regret is the mean of EV4's
decision loss over reference-resolved, reference-feasible conditions: a
feasible pick costs its extra seconds against the best feasible grid point
divided by the registered 120-second useful-improvement unit; a false-feasible
pick costs 10 units and a missed opportunity costs 1 unit. A selected
reference-unresolved point receives the existing Q3 band-pessimistic
diagnostic cost and is counted as unresolved. False-feasible rate counts
reference-infeasible or unresolved selected points over scored conditions;
abstentions and unresolved counts are shown alongside it. An all-infeasible
condition is excluded, while a reference-unavailable condition is unscored,
not a model failure. This is Q3-style feedback, **not** official Q3 or
G-FEAS@0.05. No pass/fail cutoff is proposed.

The miner-visible projection would allow only the practice set version,
practice-only label, aggregate regret, aggregate false-feasible rate,
abstention and unresolved counts, scored/total condition counts, and an
explicit unmeasured reason. It must suppress per-condition and per-candidate
predictions, picks, references, objective values, case IDs, training or exam
seeds, digest preimages, hidden task identities, and the official score or
gate verdict. The card should label six conditions as a small, reusable
public sample that miners may overfit. Showing it requires a separate owner
decision and an implementation of the PRACTICE-QUIZ-01 disclosure contract.

Suggested wording beside accuracy: **"Public practice decisions: mean
regret X EV4 loss units; false-feasible Y/Z scored situations; abstained A;
reference-unresolved U. Feedback only. This public set does not predict the
exam."** The renderer substitutes only aggregate values; it never prints a
chosen protocol or a condition-specific result.

## Boundary and leakage argument

The prototype reads committed public TRAIN v1 for model reconstruction and
the committed practice decision set v2 for inference and reference checking.
The set's `SHA256SUMS` is itself pinned in `practice_safety.py`; a mismatch
refuses measurement. The tool never opens an official quiz, tuning,
confirmation, protected, rotating-pool, or hidden-case file. Its rank
comparison reads only published run-5 aggregate practice and EV4 DEVELOPMENT
value summaries; it does not load their case predictions or references.
Therefore the prototype has no hidden answer bytes to disclose. The future
feedback path must also pass H2's registered disjointness checks against
sealed roles, the rotating pool, TRAIN, PRACTICE and this practice decision
set before claiming that boundary. Public practice remains intentionally
incomplete: its six conditions and 35-point grid differ from each future
hidden quiz draw, and repeated use can teach only this public set. This does
not claim statistical independence or make the public signal an exam proxy.

## Run-5 diagnostic method

Select the eight distinct `first_seed` members of Graphite run 5, including
the default MLP; remove the known prediction alias. Reconstruct each recipe
under its registered battery implementation **1.0**, on public TRAIN, and
infer on all 210 practice decision cases, locally on CPU. The current
compiler's default implementation is 3.0 and yields different recipe
digests; the tool refuses that mismatch. Its in-process JAX rebuild is
permitted only while the version 1.0 and current `domain.py`, `recipes.py`
and `training.py` bytes remain identical; otherwise it fails closed.
Never run a truth solver. Compare the resulting public regret with the
already published practice accuracy and EV4 DEVELOPMENT decision loss on the
same eight members. Use Kendall tau-b and Spearman rho, orienting smaller
loss as better. The EV4 value uses only its six common reference-resolved
scenarios out of twelve. Public practice has five conditions with a known
feasible best out of six under the registered bands; the sixth has only
infeasible and unresolved candidates and stays explicitly unscored. Two
unresolved candidates on a scoreable condition are slower than its known
feasible best, so they cannot change that best. Report the exact coverage,
any ties, and each recipe's aggregate
measures. This is a retrospective, one-seed, eight-member association;
it cannot establish exam predictive power or justify a new score.

Run locally with:

```text
python -m scripts.dev.battery.practice_decision_signal collect --out LOCAL_DIR
python -m scripts.dev.battery.practice_decision_signal report --out LOCAL_DIR
```

`LOCAL_DIR` contains resumable internal aggregate receipts with seed and
recipe identity and must remain local. Only the final aggregate report is
reviewed or committed. No Launchpad UI or runtime data path is changed.

## Public run-5 result

The completed aggregate is in
`docs/development/evidence/practice-decision-signal-run5-v1/report.json`.
All eight historical implementation-1.0 recipe digests matched the committed
run-5 record. All 210 public practice predictions were measurable for each
recipe. Five of six conditions were scoreable on the same reference mask.

| Practice diagnostic, lower is better | Kendall τ-b with EV4 development value | Spearman ρ |
| --- | ---: | ---: |
| Historical v2 practice accuracy loss | −0.473 | −0.539 |
| Proposed public practice decision regret | +0.308 | +0.427 |

On this matched panel, regret ranks recipes closer to EV4 development value
than accuracy does: Δτ = +0.781 and Δρ = +0.966. The default MLP has EV4
development loss 0, public-practice regret 2.039 and one false-feasible pick
in five; the lowest practice-accuracy recipe has EV4 development loss 1.719,
public-practice regret 4.2, two false-feasible picks and one missed
opportunity. The public metric remains imperfect: another proposal with EV4
development loss 0.027 has public regret 4.0. Several public regret values
tie across recipes. Eight distinct recipes at one seed each and five
scoreable public conditions cannot establish predictive power or determine a
Launchpad or scoring change.
