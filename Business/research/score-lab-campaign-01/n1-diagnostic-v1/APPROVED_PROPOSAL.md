# Full N1 binding and compatible control: prospective owner amendment

Status: PROPOSED, NOT ADOPTED. Optimizer owns this proposal. Research independently reviewed the full method with Ryan's explicit communication authorization; its corrections below are incorporated (codex-queue/reports/research-20261015-N1-PROPOSAL-REVIEW.md). Root obtains any reserved owner approval and owns execution. No A05 or final-holdout labels were read to prepare it.

## Decision requested

Authorize the following DEVELOPMENT-only input binding of the unchanged frozen N1 family and a separately named scalar-accuracy diagnostic control. This amends D4/D6 only for the specified full per-case representation, indexed input adaptation, and normalization. It does not add a shortlist family or turn the control into the legacy in-force rule. Register on main before inspecting A05 labels.

This permits the real N1-versus-control score/value measurement. It does NOT by itself permit Stage C adoption: the historical in-force trajectory score and admission gates remain unavailable for this five-scalar job. Root must retain that separate limitation in any owner decision; missing old measurements do not count as failed v2 or as passing admission. The final old-v2 head-to-head cannot honestly be promised from these outputs.

## Immutable inputs and provenance

- Job: battery-v3-job-dev-v1, fresh state, full 30-cycle programme, SOC 10% to 80%, mandatory bands 5/15/25/35/40 C, including zero buyer-weight bands.
- Native family: Business/research/score-lab-campaign-01/owner-dev-v1/candidates-v1.py.txt, SHA256 157b1db5f091910f5602b15c9f5029f0171e6da7e8b6dbc5ffb5aa5c775bd235; decision_relevance_error, _case_error, _best_feasible, and original wrappers. No source edit.
- Public construction TRAIN: 390 rows, SHA256 24fafa81bf528ca11606b64183bd8a54b5dc83c9478878c38b31ed393e1dd352. Actual Root statistics: codex-queue/reports/ROOT_SCORELAB_TRAIN390_OUTPUT_POPULATION_SD_ACTUAL.json, SHA256 de871824a10a84f22dcb7cebab14354fc57c60867339d0bd3c02dcd5838b7981.
- Existing construction algorithm: carbon/development_comparison/carbon_arm.py, source 90d7fd25e5b2cc797b006276e3c43998eb194cb7, population TRAIN standard deviation plus 1e-9. Its proposed use in scoring is NEW and explicit, not prior scientific authority.
- The voltage alternative below is a NEW normalization ASSUMPTION. Its numeric anchor is one 0.05-V switch lattice increment in scripts/dev/score_lab/owner_v3.py task grammar. A design increment is not evidence of measurement resolution or tolerable error.
- The 18 fitted artifacts and all 64-question decisions are already committed before reference evaluation. No member, menu, seed, weights, or prediction is changed by this proposal.

## Observable mapping and scales

For each buyer question q, band b and registered action a, use the objective minutes and four signed margins below. The same limits are applied to predictions and references. Reference FEASIBLE/INFEASIBLE status comes from the registered settled numerical rule, not a fabricated point-sign verdict.

| Component | Signed value | Proposed scale in its own unit |
| --- | --- | --- |
| objective | minutes from SOC 10% to 80% | 16.252337997898938 + 1e-9 min |
| charging temperature | (45 - mT_K) - charging_t_max_c | 10.502085863166549 + 1e-9 K |
| plating | plating_min_v - mEta_mV/1000 | 0.020847034707430122 + 1e-9 V |
| capacity retention | q30_over_q1 - 0.99 | 0.00024803635794775166 + 1e-9 dimensionless |
| peak voltage | 4.2 - v_max_v | max(5.705607631344694e-13 + 1e-9, 0.05) V = 0.05 V |

First four scales use the frozen decimal population-SD values in Root's stdlib statistics.pstdev receipt, each plus 1e-9. Freeze these literals and their receipt, rather than recomputing with NumPy and claiming bitwise equality between implementations. The tiny voltage SD is numerical-scale: using it alone would make a tiny voltage error dominate. The proposed 0.05-V floor is a preregistered diagnostic normalization assumption, NOT a new voltage limit, measurement uncertainty, admissibility tolerance, or claim of physical adequacy. Keep voltage in the error and relevance calculation. Do not drop it to obtain a desired result.

Set near_band = 0.1 and optimum_band = 0.1, dimensionless. These are explicitly unadopted research assumptions anchored to the frozen source's toy example (the optimum default equals near_band), not values learned from evaluation or a scientific guarantee. Freeze these values before labels; no post-label sweep to select a winner.

## Exact full-family rule

Flatten only for evaluating the native function: each (q,b) is a native subquestion with the existing complete 12-action menu and its per-band minute objective. The local feasible optimum is the minimum reference minute objective among feasible actions in that band. Keep the ORIGINAL buyer question q as the paired evidence unit; bands and actions never increase the independent question count.

For i=(q,b,a), let e_i be the arithmetic mean of the five absolute prediction errors divided by their scales. For each reference margin j, define boundary_i = max_j exp(-abs(m_ij)/(s_j*0.1)). If the reference action is feasible and a feasible local optimum exists, optimum_i = exp(-abs(t_i-t_best(q,b))/(s_time*0.1)); otherwise optimum_i = 0. Define w_i=max(boundary_i,optimum_i). This is exactly the frozen native rule, including its reference-only relevance weights.

Let W=sum_i w_i over the common included LEG bank ONLY, and n be the number of original included LEG buyer questions. Never pool the 32 LEG and 32 VALUE questions for n, W, weights, or score calculation. Define the nonnegative per-question contribution c_q=(n/W)*sum_(b,a in q) w_i*e_i. Then mean_q(c_q)=sum_i(w_i*e_i)/W, and S_N1=1/(1+mean_q(c_q)) exactly. With W=0, n=0, or any derived non-finite/overflowed error, weight, contribution or reduction, withhold the metric with its typed reason. Preserve the untransformed contributions for paired comparison; do not average transformed per-question scores.

Original physics wrapper mode is explicitly off; neighbourhood_weight=0 and neighbours=[]; no added wrapper or extra leg. Per-case contributions are a registered algebraic representation of the entire N1 rule, not its point-error component alone. Normalization W is specific to this frozen bank; no championship carry-forward authority is implied.

If any included reference margin is exactly zero for every case, boundary_i=1 and N1 reduces to the unweighted error control. Near-constant voltage at the protocol ceiling may cause this. Report that degeneracy/null result honestly; do not remove the constraint or retune after labels.

## Named compatible diagnostic control

SCALAR-ACCURACY-CONTROL-v1 uses the SAME five e_i components/scales and identical complete common bank, without relevance weights: E0=mean_i e_i; S0=1/(1+E0). With a fixed 60 actions/bands per original question, its per-question contribution is mean_(b,a) e_i. It is a control only, not an eleventh candidate or a reconstruction of INFORCE-G-FEAS/A-Q>@0.05, historical v2, or their legacy trajectory gates.

## Coverage, missingness, P/Q and value

- Validate every required prediction quantity for every original offered question/band/action before invoking the native iterator. Missing/non-finite predictions make that whole member unscorable; never improve its score by silently skipping missing actions.
- Reference availability/applicability/refinement is decided independently of models. An unresolved required action-condition excludes the WHOLE question by EXCLUDE_COMMON. Do not change the common mask by a model's pick. Keep raw offered, excluded and scored counts and all reasons.
- NONE_FEASIBLE stays in P. It remains part of the accuracy bank when all reference margins/statuses are resolved; native optimum relevance is zero in a band with no feasible action. Do not redraw or discard it to improve alignment.
- P and Q never share a score, mask-normalizer, bootstrap denominator or reported measure. LEG and VALUE remain separate: score/select on LEG; evaluate the frozen top-3 on VALUE. No VALUE-based model replacement or score refitting.
- Outer question weights are unit weights. The five-band buyer mix enters only the registered VALUE objective. All mandatory bands and constraints remain checked even when buyer weight is zero.
- Reuse owner_v3.judge for per-band 0.5-minute deadzone (zero within; full difference beyond) and buyer-weighted regret. Unsafe picks, missed opportunity, NONE and reference failure remain typed. No invented finite penalty or safe-survivor mean. Report complete outcome vectors and shares; if a top-3 regret comparison lacks finite eligible outcomes, mark that comparison unavailable instead of substituting a model.
- The 18 models are six recipe clusters, not 18 independent recipes. Bootstrap recipe clusters for score/value alignment and preserve the one-bank limitation. There are 64 P questions, not 1152 independent questions. Report uncertainty and sample limits; no tau-significance adoption gate.
- If a score/value tau can only be computed among members with complete finite VALUE outcome vectors, label it conditional on that member subset and report the denominator and whole-member exclusion reasons beside it. Never call that a full-panel alignment result. Keep all offered members in typed safety/missed/NONE outcome shares. VALUE eligibility must not prefilter LEG ranking or replace a selected top-3 member; an unavailable top-3 comparison remains unavailable.
- No old admission gate becomes PASS from absent evidence. This amendment authorizes a diagnostic comparison only. D7 final holdout remains untouched, one authorized reveal in Test Engineer custody; no reward, LIVE, production or scientific qualification follows.

## Implementation and verification after approval

One bounded adapter PR, source-digest-bound, reusing the frozen family and existing owner_v3 judgement. Tests must compare the complete native N1 call against the grouped contribution reduction on unequal relevance weights, multiple indices, NONE, zero-voltage degeneracy and randomized toy banks. Negative tests cover omitted/non-finite predictions, incomplete references/common masking, unit/scales drift, changed source digest, active wrappers, P/Q pooling and changed index/menu. Root executes tests and actual public data; author does static/source work only. Freeze registration before A05 evaluation; append actual evidence and limitations without rewriting history.
