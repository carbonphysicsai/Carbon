# RES-13: literature priors for Graphite's Level 5 candidates

**DEVELOPMENT RESEARCH, 2026-10-13. Recommendations only.** No candidate was
implemented, trained, executed or qualified for this report. No solver runs,
spend, private inputs or sealed material. The owner and Test Lead retain all
permission, budget, threshold and acceptance decisions.

## Owner readout

Keep the cheap-first measurement order. Monotone fade has the strongest
conditional prior for enforcing the intended output shape. Targeted loss
expressions deserve a small ablation, but a physics-informed battery paper is
not evidence for Carbon's particular CV/ramp/hot-cell weighting. Self-scaled
quasi-Newton methods have striking optimization results, with a much weaker
case for improvement under Carbon's budget over its existing L-BFGS.

**None of the reviewed studies establishes the exact candidate's improvement
in plating-margin error or verified design value on Carbon's shifted tasks.**
Do not book a reuse-value gain from an in-distribution accuracy improvement.
Here, *neutral* means no positive shifted-value forecast is justified; it does
not assert that the true effect is zero.

| Exact candidate | Prior for its immediate purpose | Prior for shifted design value | Numerical anchor and its limitation |
|---|---|---|---|
| Nonnegative capacity decrements along one ageing trajectory | **Helps, conditional** on the output being irreversible fade under a fixed measurement protocol | **Neutral / unmeasured**; can **hurt** if measured recovery is a legitimate target | S2 reports a monotonicity-loss ablation in capacity-normalized units, but it is a soft penalty, not this head; S3 documents recovery |
| Declarative CV-transition, ramp and hot-cell loss weighting | **Neutral for this exact expression family**; broader physics regularization is established | **Neutral / unmeasured** | S2's weighting curve contains both an improvement and a deterioration; S4 reaches millivolt terminal-voltage accuracy using a different, much larger construction |
| Self-scaled BFGS/Broyden polish versus available L-BFGS | **Helps optimization, conditional**; fixed-budget benefit is unmeasured | **Neutral / unmeasured** | S5 compares these families directly with L-BFGS, but on a PDE, at unequal elapsed times; S6 records premature termination and instability |

## Working contract, provenance and evidence rules

This is the single-document deliverable for **L5-CANDIDATE-PRIOR-ART-01**. Its
scope is established practice, reported effects, failure modes and shift
evidence for the three proposals. The source boundary is public literature and
committed public documentation, searched through the report date. It is a
targeted primary-source review, not a systematic review or meta-analysis;
absence here means **not established by the inspected evidence**, not that no
paper exists. Papers' code and data were inspected as availability statements,
not executed or reanalysed. No pooled estimate or inferred confidence interval.

The repository interpretation is pinned to main
`e9a28008b3975c3aaa93b710b6f623221241c2eb`:

- [Level 5 proposal record](https://github.com/carbonphysicsai/Carbon/blob/e9a28008b3975c3aaa93b710b6f623221241c2eb/docs/development/graphite/level5/L5_CANDIDATES_2026-10-12.md): all proposed gains remain UNMEASURED. Its capacity-component value **0.0786** and **400-case** objective are agent-reported observations, not independently verified effect sizes here. Each is a reported point with low/base/high equal to that point; neither has a published uncertainty band or an established conversion into Ah in this record.
- [Loss-expression review packet](https://github.com/carbonphysicsai/Carbon/blob/e9a28008b3975c3aaa93b710b6f623221241c2eb/docs/development/graphite/L1_LOSS_EXPRESSIONS_REVIEW_PACKET.md): its current header says REVIEWED AND BUILT as a development variant, while the miner-facing contract excludes the field. Historical draft text below the header is not current permission. Training-expression reconstruction evidence is not evidence of buyer gain.
- [Business authority](https://github.com/carbonphysicsai/Carbon/blob/e9a28008b3975c3aaa93b710b6f623221241c2eb/Business/Business_Canon.md) and [invariants](https://github.com/carbonphysicsai/Carbon/blob/e9a28008b3975c3aaa93b710b6f623221241c2eb/.agent/INVARIANTS.md): no commercial claim, scientific acceptance or toolkit widening follows from this research. Population P, sampling Q and weighting w are not changed. Reference-relative error is not physical validation.

**Number convention.** Each individual published point below is transcribed as
low = base = high = the printed point; reported study spread is recorded
separately where available. This is a transcription convention, not a
zero-width confidence interval or a claim of no reported uncertainty. Arrows
compare reported points; they are not uncertainty ranges. Cross-condition
ranges are labelled as such. None establishes uncertainty on an isolated
Carbon-candidate contrast. Every Carbon
effect forecast in Ah, plating-margin mV, verification cost or shifted utility
has **low/base/high = HUMAN_INPUT / HUMAN_INPUT / HUMAN_INPUT**. No numerical
production prior or minimum useful gain is selected.

## Primary-source effect ledger

### S1. Battery ageing: established composite physics-informed approach

[Wang et al., Nature Communications (2024), equations 8-9, Table 2 and
transfer experiments](https://www.nature.com/articles/s41467-024-48779-z)
combine a learned degradation equation, data fit and a soft monotonicity
penalty. Dataset-level SOH MAPE pairs (MLP -> PINN) are XJTU **2.60% -> 0.85%**,
TJU **1.72% -> 1.21%**, HUST **0.83% -> 0.65%**, MIT **0.83% -> 0.78%**.
These are same-inference-architecture composite-method comparisons, not an
isolated monotone-head or CV-loss ablation. MAPE is relative to SOH, not an
absolute capacity error. Figure 4b has **10** repeats with mean/SD marks;
these are not an isolated-candidate effect interval.

Cross-dataset gains use target-labelled fine-tuning, including experiments
with **one** labelled target battery; they do not establish frozen-model reuse.
The paper acknowledges capacity regeneration as an exception to monotonicity.
Its XJTU measurements and implementation are public via
[Zenodo](https://doi.org/10.5281/zenodo.10963339) and
[PINN4SOH](https://github.com/wang-fujin/PINN4SOH). No reanalysis here.

### S2. Battery ablations and a negative weighting result: limited confidence

[Eltamaly and Almutairi, Scientific Reports (2026), PDF Tables 4-6,
Sections 4.3.1 and data availability](https://www.nature.com/articles/s41598-026-56439-z.pdf)
report SOH RMSE (%): without monotonicity **0.63**, without physics loss
**0.87**, full hybrid **0.29**. Derived differences are **0.34** and **0.58**
percentage points. Monotonicity penalizes latent irreversible degradation,
not instantaneous measured capacity. Frozen NASA-trained transfer RMSE is
**0.41** on Oxford and **0.47** on local LFP. Table 4's Std. entries are
**+/-0.021 / +/-0.035 / +/-0.042** (NASA/Oxford/LFP; five initializations),
not paired-effect CIs. The weighting sweep reports
lambda/RMSE/violation-count: **0/0.52/17**, **0.1/0.39/6**, **0.5/0.29/0**,
**1/0.34/0**, **5/0.61/0**. Stronger weighting can worsen accuracy despite
removing violations.

Treat these as reported, weak priors: Table 5's full **0.29** is below both
shifted Table 4 errors without a clearly specified common aggregation;
Table 6's zero-physics **0.52** differs from Table 5's **0.87**. Do not combine
them as one controlled contrast. Local LFP data are proprietary; datasets
are available on request. No full public replication or Carbon-output
validation. The physics loss also differs from CV/ramp weighting.

### S3. A real failure of the universal no-recovery claim

[Lewerenz et al., Journal of Energy Storage (2019), capacity recovery after
rest](https://doi.org/10.1016/j.est.2019.01.004) experimentally distinguish
reversible and irreversible capacity loss in prismatic NMC/graphite cells.
Rest can recover measured capacity through lithium redistribution and
anode-overhang effects. The inspected abstract does not provide a usable
recovery-size uncertainty range: **HUMAN_INPUT**. This is a reason to bind a
monotonicity rule to the exact state and measurement protocol, not to claim
that ageing cells can never show a higher measured capacity.

### S4. Electrochemical surrogates: comparable units, different observable

[Hassanaly et al., PINN surrogate of Li-ion battery models, Part II,
v2 (2024), abstract and Sections 3-4](https://arxiv.org/html/2312.17336v2)
report terminal-voltage errors of approximately **2 mV** for SPM and
**10 mV** for P2D in data-sparse construction. Their approach combines
hierarchical training, data and conservation regularization. A base P2D PINN
can approach a trivial near-zero-current solution; strict potential initial
conditions alone do not cure it. This demonstrates that adding plausible
physics does not automatically yield a good surrogate.

Parameter-dependent predictions and unseen parameter checks are studied;
this is not evidence for temperature/SOC/fast-charge-protocol reuse of a
frozen Carbon model. Terminal voltage does not identify local anode plating
overpotential: the same unit **mV** does not make these errors interchangeable.
The likelihood's fitted noise scale is not a held-out margin-error metric.
The [PINNSTRIPES repository](https://github.com/NREL/PINNSTRIPES) is public;
no reproduction here.

### S5. Exact optimizer families: large PDE gains, unequal cost

[Kiyani et al., arXiv v3 (2025), Table 2, Burgers Case 2](https://arxiv.org/html/2501.16371v3)
report relative L2 error / training seconds after **1,000 Adam + 50,000
polish iterations**, float64:

| Optimizer | Error | Seconds |
|---|---:|---:|
| L-BFGS | 2.05e-3 | 713 |
| SSBFGS | 9.62e-8 | 1,293 |
| SSBroyden | 7.57e-8 | 1,354 |

Derived optimizer-condition range: approximately **21,310-27,081-fold**
smaller error at **1.81-1.90-fold** time (endpoints from the two rows; no
central estimate or statistical interval). This is iteration-matched, not
time-matched. Relative PDE L2 is not Ah or margin mV. Table 1's float32
SSBFGS/SSBroyden errors are **4.04e-5 / 3.60e-5**, with no L-BFGS row;
Figure 4 reports a precision plateau. These separately trained PDE examples
do not test a frozen battery model on shifted tasks. Table 2 row/caption
disagree on Wolfe versus strong Wolfe; retain that reproducibility gap.

### S6. Why a second-order finish can fail

[Rathore et al., ICML (2024)](https://proceedings.mlr.press/v235/rathore24a.html),
[accessible manuscript Sections 7 and Appendix E](https://arxiv.org/html/2402.01868),
observe L-BFGS stopping with gradient norms around **1e-2 to 1e-3** when line
search returns no useful step. Replacing its search with Armijo alone can
destabilize L-BFGS. Their remedy NysNewton-CG is a different optimizer,
requiring **5/20/322 times** L-BFGS per-iteration time on
convection/reaction/wave. These are problem-specific reported ratios,
not the cost of Carbon's self-scaled candidate. A smaller training loss is
neither a guarantee of generalization nor a reason to ignore exhausted
budgets, precision problems or stalled/failed runs.

## What each prior means for Carbon's measurement

**Monotone capacity fade.** Established battery practice supports separating
irreversible fade from recoverable measured capacity; soft constraints have
published benefits. The exact hard decrement architecture is not measured by
S1 or S2. Its mathematical shape guarantee can help only if the registered
target follows that law along checkpoint age within the same case. It says
nothing about capacity ordering across protocols, temperatures or cells.
Nonnegative decrements alone also do not prevent the accumulated capacity
from going below zero. Report shape compliance separately from native-unit
capacity error, late-age/knee error and shifted verified decisions. A smooth,
monotone but biased curve is a necessary negative control. This is a
measurement recommendation, not a new gate.

**Physics-aware expressions.** The current candidate weights decision-relevant
portions of supervised traces; it does not necessarily observe concentrations,
currents or PDE residuals. It cannot inherit S4's conservation claims. Give
each expression a matched original-loss comparator and isolate ramp/CV/hot
weighting rather than bundling new architecture, data and optimizer. Report
plating-margin error and false-feasible decisions separately from trace fit.
Check whether improving a weighted region sacrifices a different constraint
or stratum. A no-op expression and a tail-sacrificing expression are useful
controls. Source S2 supplies a caution, not a recommended lambda for Carbon.

**Quasi-Newton polish.** The comparator is the served L-BFGS polish, with the
same starting parameters, data, precision and total construction allowance.
Count line-search objective/gradient evaluations, memory and failed attempts;
iteration count alone gives an unfair budget comparison. The candidate's
smooth full-batch premise must be checked against the actual expression:
cap/max/excess terms can have kinks. This interaction is visible in Carbon's
loss-expression review packet; it is not a measured failure of the proposed
optimizer. Include an unchanged incumbent polish and a deliberately stalled
finish; a lower training objective with unchanged shifted decisions is a
neutral value outcome. No new optimizer implementation is proposed here.

## Unit bridge, missing evidence and disposition

For a fixed initial capacity Q0 and target SOH = Q/Q0,
RMSE(Q) = Q0 * RMSE(SOH); capacity-loss RMSE has the same scale if Q0 is
known exactly. Thus a reported percent-SOH RMSE r corresponds algebraically
to Q0*r/100 Ah. This is a unit identity, **not an ASSUMPTION about Carbon's
gain**. MAPE cannot be turned into an Ah RMSE by that rule. Terminal-voltage
errors cannot be turned into plating-margin errors without the local
electrochemical quantities and an independently checked propagation route.

| Missing item | Why the literature cannot supply it | Measurement/decision owner |
|---|---|---|
| Capacity and plating-margin effect in native Carbon units | Output definitions, scaling and isolated exact-candidate contrasts do not match | Graphite Testing Manager measures; Test Lead interprets |
| Frozen-model near-variant benefit | Fine-tuning, chemistry transfer and independently retrained PDEs answer different questions | Test Lead defines public shifted strata; owner sets reuse value |
| Equal-budget verified design gain over current method and cheap arm | Published fit metrics omit Carbon's action set, verification budget and admissibility | Existing value experiment; no P/Q/w change here |
| Trustworthy uncertainty on the effect | Printed points and incompletely accessible study data do not establish dependence or sampling error for Carbon | Paired public measurements; thresholds HUMAN_INPUT |
| Safe new permissions and construction cost | A literature success is not a deterministic rebuild, attack suite or containment test | Runtime/security lane and owner, outside this research |

Recommended disposition: keep all three as **testable hypotheses**, retain the
proposal's cheap-first order, and avoid promoting quasi-Newton polish on the
size of a PDE headline. The document specifies priors; it earns no candidate
TESTED, scientific qualification, product claim, Level 5 permission or
production threshold. Hub impact: none; the Hub is frozen under current
AGENTS.md. Reuse: KEEP the existing proposals, variant boundary and evidence
semantics; no edits to their files. Completion means this one cited document
is reviewable with documentation checks; adoption and measured candidate
success remain separate.
