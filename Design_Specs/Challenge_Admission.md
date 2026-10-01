# Challenge admission: construction integrity and engineering value

**Protocol:** `carbon.challenge-admission.v1`

**Owner direction:** OWNER-CHALLENGE-ADMISSION-01, 2026-09-30.

**Scope:** a standing requirement before opening a new challenge to rewarded
competition, and before expanding a challenge's construction permissions.
Research-only development may run to obtain the required evidence.

Carbon tests two propositions for each exact challenge and permission profile:
1. A participant cannot exploit a known unresolved defect to receive a high
   score for an unacceptable solution or violate the execution boundary.
2. Higher scores select better outcomes for the declared engineering job,
   with a useful effect and sufficient uncertainty control for the claim.

Both tracks must pass their prospectively approved criteria. A gain in one
cannot compensate for a failure in the other. Passing finite tests supports a
bounded claim; it does not prove the absence of exploits or universal validity.
The existing Validation Dossier, reference qualification, training-budget study,
and human scientific/security/launch decisions remain required.

## 1. Reuse and present implementation

Use the existing challenge generator, reference, construction, submission,
scoring and reporting paths. Level 0 means the actual pinned implementation,
not a generic restricted model. The battery EV1/EV2 programme supplies the
first engineering-value adapter; its Engineering Value Contract and evidence
remain unchanged. EV3 is the proposed model-guided design test, not a result.

`carbon.challenge_readiness` schema v3 requires both tracks and refuses a
launch-approved readiness record without accepted, digest-bound evidence.
`carbon.battery.value.audit` adds a read-only diagnostic of existing EV results.
Neither module executes hostile code, authenticates a reviewer, or activates
an exam. Readiness is a maintainer-held record, never a miner assertion.
The existing LIVE/qualification authority must still verify human decisions.
No generalised construction runtime, new production permission or new score
formula is enabled by this standard.

The four current portfolio records start with both tracks NOT_STARTED under
this new standard. Prior EV results remain supporting DEVELOPMENT evidence;
these states mean the full admission standard has not run, not that EV1 did not
run. Existing readiness catalogue paths stay stable in the v3 schema migration;
git retains the earlier schema bytes. No historical score or result is changed.

## 2. One frozen study sheet per challenge/profile

Before the first counted attempt, record and commit:
- Challenge ID/version and content digests of generator, population, reference,
  score, construction contract, runtime, permission manifest, budget contract,
  decision contract and feedback policy.
- The proposed permission profile and exact capability inventory. A numeric
  freedom level is a planning label; the capability manifest is the authority.
- Intended decisions, units, unacceptable outcomes, physical constraints,
  uncertainty treatment, useful-effect threshold, and relevant subgroups.
- The meaning of high score, score direction and top-model selection policy.
  This threshold cannot come from looking at the test finalists.
- Model panel, independent recipe/architecture groups, seed repetitions,
  negative and positive controls, and candidate search budget.
- Threat model, attacker access, collusion assumptions, repeated-query budget,
  feedback including timing/errors, attack families and resource ceiling.
- TRAIN/research, score-development and sealed confirmation roles; duplicate,
  near-duplicate and semantic contamination checks; access log and custodians.
- Primary estimand, meaningful improvement, confidence/precision target,
  sample-size justification, multiplicity/selection policy, and stopping rules.
- Reconstruction tolerance, recipient-rebuild requirements and permitted
  hardware. Rights determine which materials the recipient can receive.

Unknown science, security or commercial values remain HUMAN_INPUT and block
acceptance. There is no universal 95% agreement, sample count, tau cutoff or
unsafe-rate allowance. The science/security owners approve those values for
this task. Commit the criteria first; a later metadata file may name that prior
commit without a self-referential hash. Review verifies chronology from the
commit and attempt ledger; a hash alone cannot prove preregistration.

## 3. Track A: construction integrity

| Planning level | Additional permitted discovery |
|---|---|
| 0 | Current challenge recipe and registered operations |
| 1 | Custom loss expressions using a bounded operation set |
| 2 | Training schedules, optimisers and permitted TRAIN sampling |
| 3 | Training-time numerical routines such as preconditioners |
| 4 | New architectures exporting through a constrained inference interface |
| 5 | Custom inference in an independently isolated execution stage |

At each implemented level run the same legitimate panel and attack budget.
Include single-permission ablations and combined-permission attacks. Passing
components separately does not establish safe composition. Unsupported levels
are NOT_RUN, never a pass; do not open them to miners to gather acceptance data.
A challenge may be admitted at Level 0. Expansion needs a new exact profile,
new evidence and a useful-benefit justification.

Required attack families, each with a known-vulnerable specimen demonstrating
that the detector/test can fire:
- Hidden assets, embedded weights/tables, undeclared dependencies and network
  access, model loaders, malformed outputs, nonfinite values and parser abuse.
- Case/seed inference, repeated-query learning, colluding submissions, public
  leaderboard/card/error/timing feedback, cross-version information and near
  duplicates. Better transferable physics alone is not leakage.
- Score scaling/averaging/denominator exploitation, always-abstain/always-safe
  predictors, boundary optimism, rare catastrophic errors and subgroup sacrifice.
- Batch/order/state switching, run identification, cross-attempt residue,
  caches, checkpoints and candidate-directed evaluator behaviour.
- Hidden preprocessing/compilation, child processes, device/host memory,
  inference/solver hybrids, resource escapes and selective crash/retry abuse.
- Construction-to-evaluator access, answer-key/log/artifact exfiltration,
  score modification, invalid artifacts, and inference-domain escape.

Use disposable hosts, synthetic canaries and no production credentials. Runtime
isolation is required for hostile executable tests; in-process fixture tests
prove the fixture boundary only. Pin and inspect the actual worker/transport,
not just a helper. Stop on escape or answer-key exposure, invalidate affected
secrecy claims, repair, rerun affected attacks and use fresh confirmation cases.

The attacker wins with any high-scoring unacceptable model, any accepted
mandatory failure, or a forbidden authority/resource access. A cheap valid
method is a useful discovery. Declare whether pretrained assets, public solvers
and hybrids are permitted, then test the declared rule; code inspection cannot
prove that arbitrary code contains no encoded prior knowledge.

Keep the full attempt ledger, including unsuccessful attacks, crashes, retries,
timeouts, exclusions and budget consumed. A timeout is neither an attack pass
nor a physics failure. Record attempted coverage and untested surfaces. Count
attempts as experiments, not independent Bernoulli samples of all possible
attacks; zero discovered exploits does not give an exploit-free confidence bound.

Rebuild promising legitimate methods with fresh seeds, including a second
operator and permitted hardware. Test that a recipient rebuilds from the actual
delivery package without miner help and continues training where promised.
Training a changed model requires new evaluation; old evidence remains bound
to the old artifact. Shared infrastructure evidence may be reused only with
matching pins and a recorded applicability analysis; challenge-specific score
exploitation and integration tests must still run.

## 4. Track B: engineering value

Use the Engineering Value Contract to define the task before selecting models.
The evaluator computes engineering outcomes from an independently justified
reference. A training residual is not a ground-truth test. Record common-mode
solver/measurement limitations and reference refinement/witness checks.

Run both fixed-choice decisions (EV1/EV2) and model-guided design search (EV3):
- Hold optimiser, constraints, evaluation/query budget and tie policy constant.
- Select using model outputs only; commit proposals before reference verification.
- Verify every proposal including failures; account for abstentions and retry
  budgets. A solver-backed candidate is allowed only if the contract permits it
  and accounts for its inference work.
- Compare to declared reference-backed/baseline decisions at equal budgets.
  Call a best-known design best-known, never a global optimum.

Separate scientific admissibility from ranking. Report gate-failing models,
but exclude them from the primary ranking of eligible real models. Keep
reference-derived synthetic controls out of real-model correlation and state
that they are constructed attacks, not evidence of model generalisation.

Do not count training seeds as independent model families. Predeclare family
clusters and account for dependence across recipes, seeds, cases, geometries,
conditions and reference uncertainty. Use a qualified clustered/joint uncertainty
method or conservative bounds. Report leave-family-out sensitivity where
applicable. A descriptive tau does not establish a useful monotonic relationship;
include decision effect sizes, top-model/top-k selection value and uncertainty.
Equal increments in score need not mean equal increments in engineering value.

Prevent missing-result bias:
- Report scheduled, attempted, resolved, unresolved, failed and excluded counts
  per model, subgroup and condition; include the reasons.
- Do not compare means on different case masks as though they were paired.
  Use common cases for a diagnostic and a preregistered unresolved-outcome
  sensitivity/bounding analysis for the admission decision.
- Candidate failure cannot become a missing reference. Reference failure cannot
  become a candidate penalty. Insufficient coverage returns INCONCLUSIVE.
- All-tied outcomes, no feasible designs, all-abstain behaviour or an unmeasurable
  component cannot establish score-to-value alignment. Expand the prospective
  study design if it cannot exercise the claimed engineering outcomes.

Keep unsafe decision counts/rates, subgroup/tail failures and worst observed
errors separate from mean regret and correlation. Apply the approved safety
criterion before soft ranking. When claiming a bounded unsafe rate, publish its
one-sided uncertainty bound and effective sample basis, not just zero failures.
Never let many easy examples dilute a mandatory critical failure.

Freeze the model panel, winning score formula and analysis before confirmation.
Give an independent evaluator custody of fresh cases and hold back whole relevant
families/conditions, not only different seeds. Development and attack discovery
may iterate; final confirmation happens once for the chosen claim. A failed or
revealed confirmation requires a new study/version and a fresh confirmation set.
Record the total number of formulas/models tried. EV2's published verification
conditions cannot serve as untouched final confirmation for EV3 or admission.

## 5. Decision and evidence package

For each track: NOT_STARTED, IN_PROGRESS, FAILED, INCONCLUSIVE or ACCEPTED.
FAILED means a registered criterion failed. INCONCLUSIVE means evidence cannot
resolve it. Both block admission at the tested profile. No unrun check passes.

The scientific and security reviewers examine the methods and retained records;
they do not accept a collection of green strings. They check preregistration
chronology, real execution provenance, completeness, statistical sufficiency,
control sensitivity, open attacks and applicability to the exact pins. Acceptance
records name the reviewer, exact report digest and scope. The file validator
checks bindings and completeness, not the truth of an attestation or identity.
Existing human qualification/activation mechanisms remain separate.

Required outputs:
1. Frozen study sheet and raw ledger with material/artifact identities.
2. Both reports: attempted coverage, observed results, uncertainty, failed
   controls/attacks, untested surfaces, costs and reproducibility limitations.
3. Machine-readable readiness record with both accepted reports and their
   review decisions; or explicit blockers.
4. Customer-safe evidence: score against decision outcomes with uncertainty,
   concrete successes/failures, the tested envelope, tail/unsafe outcomes,
   effect size, compute cost, reproduction instructions and claim limits.
   No live hidden cases/seeds, sensitive exploits or private client material
   enter the public report. Use authorised retired examples and aggregates.

Retest after material changes to any pinned field or discovery of a new exploit.
Preserve prior results. Record which unchanged evidence remains applicable;
do not carry acceptance across changed score/runtimes/permissions by filename.
Release review requires this evidence in addition to the existing qualification
manifest and training-budget study. This engineering patch adds the readiness
record gate and protocol requirement; it does not claim a new deployed runtime
interlock or that a challenge has passed.

## 6. Executable checks and current follow-up

```
python -m carbon.challenge_readiness validate
python -m carbon.challenge_readiness validate --require-admission
python -m carbon.battery.value.audit --results docs/development/evidence/ev1-2026-09-25/results.json
python -m pytest tests/cpu/test_challenge_admission.py tests/cpu/test_engineering_value_audit.py tests/cpu/test_challenge_readiness.py
```

The first command validates the records, including any retained evidence files.
Without `--require-admission`, zero exit means valid records, not accepted
challenges: inspect `admission_blockers`. The admission flag fails on missing
acceptance or an empty record set; it is the prospective release-preflight command.
The EV audit command audits the existing experiment without changing
its results. It supplies denominators, ineligible exclusions and recipe sensitivity,
not a qualification decision. Canonical CI owns engineering acceptance.

Next execution: prepare the battery study sheet from EV1/EV2 and freeze a revised
EV3 with fresh confirmation conditions; specify approved effect/uncertainty and
unsafe-decision criteria; run Level 0 attacks through the actual isolated worker;
implement only the next bounded experimental permission profile. No arbitrary
miner-code run is authorised without the required isolation and budget scope.
