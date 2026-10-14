# ScoreLab finish-line contract and combined experiments

ScoreLab's current real-data readiness is **INSUFFICIENT_EVIDENCE**. This
command checks the registered public receipts and reports each missing item,
its supplier, its dependency and the smallest next action:

```sh
python -m scripts.dev.score_lab.finish_line \
  Business/research/score-lab-campaign-01/finish-line/READINESS_MANIFEST.json \
  --root . --out /tmp/scorelab-readiness.json
```

Exit 2 means evidence is insufficient. Exit 0 means only that the manifest's
engineering predicates are satisfied. It never qualifies a Challenge, picks
a score, adopts weights, authorizes spending or executes a final holdout.
All fifteen stage entries are mandatory; deleting a blocked entry cannot
manufacture readiness. Unknown/missing inputs, changed digests and unmet
coverage remain distinct. Prerequisite failures propagate to dependent stages.

The checker reads small, digest-bound JSON receipts under explicit public
repository roots. It has no model, solver, network, training or holdout loader.
The final-holdout interface accepts only custodian, commitment digest and
reveal policy. No content path is accepted in that interface. The manifest is
a registered research plan, not an untrusted claim that an experiment passed;
its predicates and any scientific adequacy values require domain review.

## What is actually available

| Input | Existing real public evidence | Combined synthetic experiment |
| --- | --- | --- |
| Model identity | 137 exact raw-bundle joins; 99 declared recipe digests; 122 fit digests | Six fixed MODEL traits and two PROBE traits per profile |
| Family, seed, training cohort | Not established. A seed field is present but its role is unproved. A fit digest is not universally a weight digest | Explicit toy identities; no independent trained-family claim |
| Accuracy | Legacy a/r/g/m/n/p on 415 original public D cases | Candidate A proxy on analytic score questions |
| Quiz decision / verification | Q3 and VERIFY-R absent for the 142-member replay; cannot be reconstructed as zero | Q, verified-pick and V2 proxies on the same score-side question law |
| Physics, robustness | Partial descriptive probes from a separate 148-bundle study; no proven cohort-wide join | Declared trait values; B9/B15/B16 aliases are synthetic, not physical units |
| Uncertainty, gradients | Complete matched real measurements absent | Toy sigma, Gaussian CRPS, finite-difference signs and honesty wrappers |
| Buyer value | Public EV4 full35 admission: 0/24; no common D/V mask | Analytic loss on disjoint target, shifted and extrapolated questions |
| Cheap control and cost | Frozen D-only trace map; complete acquisition/construction cost absent | Cached scalar map with uncharged anchors, no own physics measurements |

`finish-line/PUBLIC_INPUTS.json` and `PUBLIC_BUNDLE_CROSSWALK.json` retain the
inventory aide's source bindings. The 137 records are not 137 independent
families, and the five constructed controls do not turn them into 142 trained
models. The distinct 148-bundle physics study is not silently pooled into it.

The inventory also indexes the supplied public standalone L4 MLP specimen:
one model, two identical reconstructed states and two four-case inference
replays. Source, TRAIN digest, model identity and measured operation cost are
recorded. It adds no paired decision-value, quiz or physics evidence. The two
reconstructions are not two independent model families; unknown budget fields
remain HUMAN_INPUT. The inventory reads metadata only, not the model states.

The proposed first real target is the owner's battery-v3 ambient-indexed map,
with protocol and cooling per 5/15/25/35/40 C band. Its committed round-2 law
still has `runtime_registration: false` and null P/Q/outer-w. The manifest
binds those actual fields. The public EV4 CV-onset proxy remains a different
job. The owner/domain lead must finish the intended job, role law and utility
registration before the real research search can run.

## Combined matrix

```sh
python -m scripts.dev.score_lab.campaign_combined run \
  Business/research/score-lab-campaign-01/combined-matrix/REGISTRATION.json \
  /path/to/pinned-developer-candidates.py /new/output/directory
```

Run through `scripts/dev/canonical.sh` on the canonical Linux environment.
The registration above is the historical experiment's frozen input and binds
its original producer source. After a producer change, prepare and commit a
new prospective registration with current source hashes before any new run;
do not replace that historical registration or imply the old run used new code.
The source file is the existing Validator-supplied trusted developer input,
pinned by SHA-256 before import; this does not provide hostile miner-code
execution. The complete catalogue and source identities are committed before
the experiment. Existing controls execute first and a failed control stops
the run. The launcher reserves a whole cell before dispatch, enforces per-cell
CPU/address-space/wall limits, records failures and stops at the first cap or
error. A partial run is reported as partial, never a favourable subset.

The committed producer writes `REGISTERED_PLAN.json` and `START.json` before
the first worker. Workers consume that frozen plan copy. At normal completion
or a recorded worker/cap stop it writes `IDENTITY.json`, binding the start,
actual producer/source/candidate digests and all generated artifacts. Fresh
output can be passed directly to `combined_readout`; no external identity or
export wrapper is required. Readout refuses an incomplete run or a changed
start binding. The original 96-cell export and its legacy identity remain
unchanged; the compatibility reader continues to accept that historical form.

The matrix crosses three deterministically selected existing profiles, all
32 subsets of five optional wrappers, four existing physics modes, and sixteen
base score proxies. The ten unchanged candidates are supplemented by A-only,
Q-only and A+Q diagnostic ablations, each with/without the existing strict
G-FEAS comparison. Ablation weights and gate values come literally from
registries v5/v9. All are synthetic assumptions; none is adopted.

Every cell uses the same uncertainty-aware buyer workflow, including the
existing honesty example's decline threshold. This is a prospectively
registered toy job. Scores are computed once per unique complete score input
and replayed for the four value views. Replay rejects altered input. Score
callbacks receive score-side references, predictions and metadata only.

Cheap-containing cells under GATE/FLOOR/BLEND are unscored because the cached
cheap method has no measured physics. Missing traits are not set to zero,
and an unscored cell is not called a gate failure. Actual gates and FLOOR
ordering continue to use the existing candidate rules. Raw score/admission
and value outcomes are retained, including known-bad probe ranks.

Paired component effects compare each setting with the no-component baseline
at the same profile, candidate, physics mode and common value mask. A missing
pair has a null effect, never zero. CPU receipts count scorer evaluations
separately from cached value-view replay; no model inference or solver occurs.
Cached map acquisition is uncharged, so this is not a matched full-workflow
cost comparison or evidence that Carbon beats an industry baseline.

## What a score search can and cannot establish

The completed bounded matrix and reproducible summary are in
`Business/research/score-lab-campaign-01/combined-matrix/READOUT.md`.
The readiness checker recognizes its source-bound interaction receipt while
keeping the other real-input and final-search prerequisites separate.

The fixed matrix examines interactions; it does **not** search weights.
`core.registry_rule` already consumes `score_tuning`'s registered families.
The finish-line manifest requires a prospective family/grid, search budget,
objective, independent validation and complete attempted-rule log before a
real search. Adding more fixed proxies is not proof that the family has enough
capacity to represent value.

`finish_line.capacity_witnesses` tests a necessary condition for a score that
is a nondecreasing function of its supplied higher-is-better features, at fixed
eligibility. Identical features with different value cannot be strictly ordered;
a lower-value member dominating every feature cannot be ranked correctly by
that family. This covers nonnegative weighted sums/geometric combinations
within their monotone domain. It says nothing about other features, changed
gates or nonmonotone models. Absence of a witness does not prove capacity.

`finish_line.measurement_ceiling` reuses `score_proof.value_ceiling` on complete
common-mask losses. Its Spearman-Brown and bivariate-normal assumptions remain
explicit. This is a reliability diagnostic, not a universal maximum tau and
not a proof that a particular feature family can attain it.

Direct V2 utility, `G - kappa*n`, is a separate family. Its ability to represent
buyer value depends on matching the exact task, units, fallback, verification
count/cost, admission and abstention semantics. The combined toy loss also has
an unsafe-shortlist penalty and uncertainty decline; merely naming a candidate
V2 does not make those objectives identical.

## Remaining execution

The manifest keeps local engineering gaps separate from collection and owner
decisions. Existing reference-failure and block adapters are merged and
fixture-tested; complete measurement-design experiments remain to execute.
Goodhart/feedback results exist on limited frozen toy studies; the final
combined family still needs its matched search. Championship statistics exist;
the ScoreLab competition producer still needs its explicit caller policy and
paired synthetic design. A large full A-G campaign needs completed grammar,
registered sampling/weights, a measured pilot and an operator-bound cost cap.

The current public EV4 blockers are 223 reference-applicability cases, nine
decision-changing mesh160 pending cases, four in-band unresolved cases and
five original missing/failed references. Completing the fourteen pending or
missing solves alone does not resolve applicability or the four method cases.
No menu pruning, new band or hidden-data substitution is allowed.

Independent validation must be registered and untouched before the score
search. Previously inspected public EV4 V is not fresh confirmation. The Test
Engineer retains the final generator commitment
`e24780aa066f9ed362322a4c0c224bd5c4dc9e9389b968d016ed250022b2b210`;
only the final frozen rule list may reach its custodian-run holdout. The owner
still decides whether any resulting rule is adopted.
