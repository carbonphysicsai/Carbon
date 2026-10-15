# Completed-menu consumer: minimal semantic control contract

Status: STATIC SPECIFICATION; fixtures described, not implemented or run here.
Research supplies no adapter, executor, new statistic or scientific value.
Optimizer owns implementation; Root owns scope/main registration and TEST.

This contract targets protocol
`NEW_COVERED_COMPLETED_MENU_RESEARCH_V2_PROTOCOL.json`, SHA256
`ebe45085d2dd5a7f89ff9bf243ff00551e69a972959b8d24e46659ef2c9427bb`,
and source bindings SHA256
`c6249c49f12360f10322aec6246b2991591e1e725bb33b7521772e02d8b1e532`.
It supplements that proposal without changing its menus, anchors, population,
folds, cost assumptions or scoring formulas. The original de523 proposal and
RESEARCH_V1/D11 evidence remain preserved. Actual new mapping code will need
its own source digest and exact checks before execution.

## Existing components and boundaries

Reuse the bound lexical prediction/reference/r1-row readers, native
`decision.measure` and `exam.case_components/case_error`, the unchanged
`v2_label` and strict covered-reference precheck, `bank.classify`,
`bank._v2_question`, `public_v2_replay.outcomes`, `score_proof` statistics,
and `owner_dev_v1.select_top_three/selected_regret_minutes` where their full
preconditions hold. Importing helpers must not invoke an old `main()`.

The old D11 main entrypoint requires 385 cases and the 122-case interval
evidence; it is incompatible with this eight-question/33-case protocol. The
new mapping must not weaken those old checks or fake an old evidence object.
Passing controls will establish only the new consumer's bounded behavior.

Toy fixtures must use isolated temporary artifacts, explicit FIXTURE status,
and the existing toy-reference/prediction factories. Fixture hashes cannot
stand in for the committed public-input pins or a Root execution receipt.
No real model, raw public outcomes, V outcome, solver, provider or host is
needed to construct these controls. No fixture can activate qualification.
No test execution is authorized while OPERATOR remains open.

## Controls that must discriminate broken consumers

| ID | Fixture / perturbation | Required observable behavior | Defect this must catch |
| --- | --- | --- | --- |
| C01 | Instrument commitment creation and every truth reader in the actual producer path. Repeat with commitment write failing. | Derived real-model quantities, exact model/case identities, invalid-coverage accounting and payload digest are written and closed before the first reference/label reader call. On write failure, no truth reader runs. | A commitment created only after value/reference access, or a decorative `references_opened=false` field. |
| C02 | Change only reference/VALUE fixture content while holding all model payloads fixed; separately change a model payload. | Real prediction-commitment bytes remain identical under truth-only changes and differ under model changes. Constructed controls are not included as real predictions in this commitment. | Truth-conditioned real-model preprocessing or fake chronology assertions. |
| C03 | Use all 33 exact registered input IDs and eight new/native mappings. Remove one ID, duplicate one, alias two new questions to one native context, put one case under a wrong context, or introduce one foreign ID. | Refuse/withhold with explicit coverage or binding reason before analysis; never borrow a nearby case, join by integer row index, expand to old 35-action menus or quietly omit the missing action. | Prefix-only joins, partial menus, duplicate collapse and old-ID leakage. |
| C04 | A hash-bound toy bundle/old manifest contains an unselected V field with a deliberately undecodable value, placed before its case ID or requested D object. Change an expected digest independently. | Unselected outcomes are lexically skipped; a decoder spy fails if the poisoned fragment reaches full-value decoding. Digest mismatch refuses before payload decoding. | Whole-corpus `json.load`, V decoding during filtering, and post-decode integrity checks. |
| C05 | Use the two fixed folds, then swap only VALUE predictions/outcomes. Capture the actual objects delivered to each score callback. Repeat with a cross-fold case alias. | LEG scores, ranks, selected IDs and selection digest are unchanged under VALUE-only changes. No callback receives VALUE references, predictions or metadata. Cross-fold alias refuses; reverse orientation applies the same rule. | Scoring against VALUE, VALUE tie-breaking, overlapping physical rows and a callback with an overly broad metadata dictionary. |
| C06 | One registered menu has an out-of-claim, absent, pending, nonfinite or unresolved reference; place that defect in an unselected or dominated action and repeat across models with different predictions. | The entire question is excluded identically for every model/control before classification or scoring. No action pruning, candidate failure, zero value or model-specific question mask. Exact reasons and offered/excluded identities remain. | Relying on `bank.classify`'s dominated-unresolved shortcut instead of the strict owner precheck. |
| C07 | Change the fixed anchor only to unresolved, then to reference-infeasible with a feasible alternative, then make every action settled-infeasible. | Respectively INCOMPLETE, RESCUE and NONE are retained as strata under the existing classifier. None enters scalar SCORED value; the anchor is not replaced by the feasible/best action. | Claiming an input-low anchor is safe, silently choosing a different fallback, or dropping NONE from offered P. |
| C08 | Keep all references settled and the anchor feasible; separately introduce an incorrect source, r1 rule, joined margin, duplicate source row or changed native-contract/calibration digest. | Positive fixture reaches existing V2 helpers. Invalid source/rule/join/digest refuses rather than acquiring feasibility through a model prediction or an unrelated constraint failure. Preserve strict 15-mV boundary and existing rule/units. | Trusting a status string, bypassing source identity, mixing mV/V, or stale calibration. |
| C09 | Mark every reference unavailable, or leave one orientation with no LEG or no VALUE questions; use constant/tied scores or losses. | Emit the registered null/insufficient or undefined-statistic outcome. Report original P8 and class counts/mass, conditional SCORED support and fixed fold counts. Never rebalance, redraw, replace anchors or output tau=0 as a substitute for undefined. | A forced finite result, moving questions between folds, or claiming a conditional mean over the full population. |
| C10 | Supply the frozen raw cohort, its recipe/fit groups and separately declared controls; duplicate an ID, spoof a recipe, give a control a raw-model ID, or omit a model's one required payload. | Validate membership/group binds and keep controls out of learned-member tau/counts. Missing predictions invalidate/withhold the member's complete comparison with a reason; they do not alter its reference question mask. Report matched compared IDs for every rule/cohort. | Inflated real/independent sample counts, candidate-dependent coverage or hidden cohort differences. |
| C11 | Registered admitted score-side members include exact ties at the third pick and at the top-half boundary; vary only VALUE or lexical names. Also provide fewer than three admitted scores or one missing admitted score. | Call the existing top-three selector. Ties follow its fixed LEG/lexical rule and are reported; gamer screening uses competition rank and floor(n/2), not lexical placement. Insufficient score coverage cannot shrink n or replace a chosen member using VALUE. | Cherry-picking the best of tied members, hiding a gamer through tie ordering, or changing the denominator. |
| C12 | One of the selected three lacks one VALUE result or reports an unresolved verification. Add an excellent unselected member; alter a bound selection body without its digest. | Withhold the entire affected fixed comparison/vector with its reason; do not average a favorable subset, choose a fourth member, insert zero or reinterpret reference uncertainty as unsafe. Tampered selection refuses. | Value-driven replacement, partial-vector bias, fabricated regret and unauthenticated selection. |
| C13 | The same fixed menu/predictions are sent directly to existing `bank._v2_question` and through mapping glue, with cap/kappa/unit exactly as registered. Cover a useful verified pick, unsafe-only shortlist, abstention and a menu shorter than the cap. | Preserve existing G/U/n and detailed attempt accounting exactly. Unsafe verifications are charged; abstention falls back with G=0 and n=0; fewer offered actions do not cause padding or phantom charges. No new unsafe/abstention penalty. | A lookalike rewritten value formula, charged-only-safe attempts, shortlist padding or interpreting k as a required length. |
| C14 | On a settled feasible-anchor menu let anchor objective B and best objective T be symbolic seconds, B>=T. Verify a best design; separately verify no feasible improvement. | Gross regret is B-120*G-T, then divided by 60 for minutes. Best verified gives zero gross regret; no feasible improvement gives B-T. Verification cost remains in U=G-0.1*n and is reported separately. Negative U is legitimate; gross regret must not become negative or absorb an invented cost shift. | Seconds/minutes errors, double-counted costs, dropping legitimate negative utility or an arbitrary score-to-error offset. |
| C15 | Change menu size while holding each question's mean native case error fixed; use two completed questions with unequal action counts. | Recomputed accuracy is case-mean within each new question, then unit-weight question mean over LEG only. It is labelled a diagnostic baseline, not literal recorded v2 or the strongest cheap arm. | Accidental action-count weighting, changing the registered P measure or a false in-force/cheap-comparator claim. |
| C16 | A dependency spy rejects any call to a solver, model rebuild/inference, provider, holdout loader, old D11 main or 122-case evidence constructor. Give an existing output destination. | No forbidden dependency is called; old entrypoints are not used by relabelling their configs. Existing output/evidence is never overwritten. No LIVE/reward/qualification or rule-adoption result is manufactured. | Scope widening hidden inside thin glue, historical evidence rewriting and a development result entering production authority. |

Every positive fixture needs at least one perturbation that changes the actual
input read by the production path. Asserting a caller flag or recomputing the
implementation in a test oracle is insufficient. Reuse existing tests for
unchanged helpers; add only the producer wiring/mapping controls they do not
already cover. The implementation owner supplies the eventual exact TEST
command and observed results; this document records neither.

## Native-rule domain counterexample: N4 on the two-action menu

The frozen `top_region_ranking` function in candidate source
`157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235`
contains `if len(res) < 3: continue` (function begins at line 356).
New menu `covered-completed-v2:D-T24-S0.33` has exactly two actions and is in
fold A. Therefore an unchanged N4 call on A skips an admitted LEG question.

**C17 must-fail control:** supply a complete settled two-action question in
the fixed LEG set. Detect/report that N4 did not cover it; do not present the
result as a complete equal-question-weight LEG score. Mark the full-LEG N4
diagnostic unmeasured/incomplete unless an already registered compatible form
is evidenced. Do not add a third action, drop/reassign this question, alter N4,
or fill a synthetic score. N4 on the other orientation may be structurally
supported, but still needs its own actual coverage receipt. This limitation
does not block the N2/V2/accuracy diagnostic route.

Compare N4's existing `detail.questions` **exactly** with the cardinality of the
fixed retained LEG question set after the common reference/anchor precheck.
In the fully admitted A fixture that is four expected versus three returned;
both the count mismatch and the skipped native question must be reported.
N2's `detail.questions` and V2's `detail.scored_questions` likewise must match
their complete retained LEG set whenever a full-LEG score is claimed. A
reference-excluded question is excluded for every rule before this check; it
must not be restored or selectively dropped to repair a rule's native domain.
A partial-domain native result can be retained as a labelled diagnostic, but
cannot enter the full-LEG comparison as though coverage were complete.

Likewise, full-family preservation does not authorize filling N1 scales,
missing registry legs or unmeasured physics from toy defaults. Exact full-rule
inputs unavailable means UNMEASURED. D6 adoption eligibility is distinct from
these fixed-proxy shadow diagnostics and remains as registered.

## Completion meaning and output contract

Each orientation's readout must bind protocol/source/input/commitment/selection
identities and list offered/classified/excluded questions, complete menus,
anchors, original P mass, the shared SCORED mask, actual compared cohorts and
controls, LEG scores/coverage, fixed top-three IDs, complete VALUE vectors,
gross regret minutes, verification counts and U separately, undefined/null
outcomes and adverse findings. A selected-regret helper's generic first line
must not replace the newer protocol's precise conditional-estimand first line.

Model quantities precede truth access in the producer's observable ordering;
that is not independent chronology or execution attestation. Root's actual
source/environment/TEST/guard receipts stay separate. Unknown runtime or
important-region guards never become PASS from stored prediction shapes.

The minimum consumer can produce a descriptive result or honest insufficiency.
It does not decide production admission, close the v3 observer gap, validate
the full battery job, establish a cheap-baseline win, promote a rule or reveal
holdout material. No surviving v3 form remains a legitimate KEEP_V2_QUIZ_SHADOW
finish under R1, with no gratuitous holdout reveal.
