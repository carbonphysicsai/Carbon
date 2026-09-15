# Carbon Protected Exam Standard: CPES-1

**Version:** 0.2, 12 September 2026

**Status:** proposed simplification for domain reconciliation and qualification. This revision replaces the v0.1 universal frozen-round workflow in the research proposal. It does not change current runtime authority, select production parameters, approve security, or activate disclosure. Existing scientific, A4, data, lifecycle, disclosure and reward contracts remain controlling until their owners accept explicit amendments.

**Related:** [profiler integration](PROTECTED_EXAM_PROFILER_INTEGRATION.md), [control registry](PROTECTED_EXAM_CONTROLS.json), [prior reference-reuse review](PROTECTED_REFERENCE_REUSE.md).

## Owner and miner explanation

Submit a strategy whenever you are ready. Carbon locks the submitted method before choosing its protected test cases, reconstructs it, and checks the result. Carbon can share reference answers with other submissions that were already locked before the cases became knowable. Carbon adds a bounded wait only where measured savings and the qualified operating profile justify it. For public-data Challenges, Carbon publishes a retired answer key after no pending work can exploit it. A new submission cannot take that disclosed exam.

**One security minimum; optional reference-sharing delay.** Reference cost may justify more reuse machinery and waiting. It cannot justify weaker protection on cheap Challenges or waiver of any mandatory physical requirement.

## 1. What changes from v0.1

| Earlier proposal | Revised proposal |
|---|---|
| A scheduled frozen group is the universal workflow. | Preserve continuous submissions. Lock an internal set of compatible queued jobs before case selection; a set may contain one job. |
| Hold all feedback until the group finishes. | Distinguish result summaries from answer-key publication. Early summaries require qualified non-influence of pending jobs; otherwise hold that pack's summaries. |
| Retired answers remain private unless separately considered. | Declare publication policy before competition. Prefer automatic release of public-data answer keys when a verified retirement condition permits it; confidential assets use authorized audit access. |
| A large cohort is the preferred cost solution. | Compare no intentional wait, existing-queue sharing, and bounded-wait sharing on actual arrivals, costs and delays. Choose the simplest supported profile. |

Retain P1-P8. P5 now expresses immutable membership, controlled disclosure and retirement rather than prescribing a miner-facing calendar. All existing attack concerns remain; their expected results must follow this edition. There is no default adaptive cross-pack reuse or persistent hidden reservoir.

## 2. The same minimum for every Challenge

| ID | Requirement |
|---|---|
| P1 | Qualify and commit the physical job, population, SamplingPlan, reference, measurements, score/resource policy, admission, randomness and disclosure rules before cases become knowable. Retain independently ordered commitments and aborted work. |
| P2 | Bind producer choices before case selection and seal independently reconstructed artifacts before protected inference. No mutable dependencies or unauthorized post-exposure adaptation. |
| P3 | Use an approved unpredictable, verifiable case-selection procedure with the event and all seed-affecting metadata fixed in advance. No favorable redraws, selective event choice or retry-seed shopping. |
| P4 | Isolate construction, reference, inference, grading and public/client surfaces. Protect answers and roots from candidates. Name the privileged-operator trust boundary; require an appropriate independent integrity path. |
| P5 | Bind each pack to its eligible committed jobs. Reject later admissions, control summaries, and publish plaintext only after verified retirement and disclosure eligibility. No hotkey exception. |
| P6 | Bind reference assets, predictions and decisions to their exact identities and qualified evidence. Reference/infrastructure failure is not candidate physics failure. Mandatory physical failure cannot be offset by accuracy or cost. |
| P7 | Qualify finite-case resolution for the admitted candidate field, reconstruction variability and repeated comparison/promotion policy. Capacity is not permission to test unlimited variants. |
| P8 | Test adversarial use, cross-service leakage, corruption and recovery on the actual stack. Preserve failures, revocation and incident history. Unknown evidence or a demonstrated unresolved bypass blocks affected official use. |

Commitments prove bindings, not physical accuracy. A valid signature identifies a signer, not honest computation. A container or encrypted store does not hide plaintext from its privileged operator. One-validator compute planning is not single-person scientific trust. Do not accept a hostile-host claim by adding a disclaimer; provide the approved independent audit or stronger integrity boundary.

## 3. One queue, optional waiting

### Default: no intentional batch-fill wait

Use the existing submission, admission and execution owners. The service returns a durable immutable submission receipt. Structural admission checks remain separate from scientific evaluation. Duplicate/copy and retry handling follows existing identity policy and cannot buy fresh lottery draws.

At an authorized dispatch point, the scheduler may select compatible already-committed jobs under an outcome-independent rule. All jobs sharing a pack must use the same applicable Challenge version, evidence policy, reference and resource-comparison semantics. Lock membership before the fixed case-selecting event is knowable. If only one compatible job is ready, proceed with one; do not wait for the whole network.

The schedule and event-mapping rule must be fixed and auditable. Queue order may determine eligible work but must not supply miner-controlled seed material. Operators may not choose among already-observed events or invent a new draw after failure. A new arrival enters a subsequent eligible job group without asking the miner to resubmit.

### Optional: a bounded wait for expensive references

A qualified Challenge operating profile may authorize a finite intentional wait and supported maximum group size. Publish those terms, capacity and admission treatment before accepting affected work. Close at the declared bound even when the group is underfilled, provided the registered comparison remains valid. An empty group follows a predeclared no-work disposition before case selection.

Record assigned work, existing age, closure and result expectations without exposing hidden performance. Do not keep extending a wait because more miners might arrive. A late submitter gets the next available assignment; receipt is not a guarantee of immediate admission or a new fee. Economic/refund terms remain domain-owned.

Both modes use the same internal membership and evidence mechanisms. Bounded waiting is not a second miner protocol. Each Challenge operates independently within the one validator's actually allocated compute; no global cross-Challenge release barrier. Shared infrastructure and related cases still require cross-Challenge isolation and disclosure checks.

### Execution and comparison

The approved provider supplies A4-compatible material. Reconstruction receives only permitted TRAIN data and randomness. The current root can precede finished weights; do not claim final weights were sealed before A4 acquisition if they were not. Seal the artifact/runtime before evaluation input. Generate and bind the qualified reference answers once for this pack, then reuse them for its committed jobs and required replicas.

Every positive official result requires its full registered mandatory evidence. Same-case retries retain identity; stochastic repetitions follow the registered policy. Stop only under the applicable typed failure rules. Retain reference non-convergence, disagreement and failed/aborted compute; do not substitute easier cases.

Compare incumbent and contender on registered common fresh evidence where required. A different pack's raw score is not automatically comparable to an earlier record. New packs do not reset Challenge baselines, reward credit, funding obligations or copied-artifact identities. There is no new prize merely because a pack closes.

## 4. Result summaries and answer keys have different release rules

### Result summary

Return the registered summary after the candidate's result passes its required checks, without imposing a blanket delay for unrelated jobs. For jobs sharing a pack, early summary release additionally requires qualified evidence that it cannot alter pending producer choices, candidate state, external inputs, retry/seed selection, cancellation eligibility or result construction. This includes reward/leaderboard and timing signals, not just an API response.

Absent that evidence, hold summaries for the affected pack until all relevant work is terminal. A fixed recipe alone is insufficient if callbacks or a corrupt execution path can still change predictions. Do not introduce a discretionary early-release toggle or assume this property from a signature. Existing economic-batch ordering remains separate from summary availability.

### Answer-key publication

For a public-data Challenge, publish according to the prospectively approved policy when all of these statements hold:

1. **No pending answer-dependent work:** required reconstructions, predictions and evidence for every authorized use are durably bound, or the attempt is irreversibly closed under its failure policy. No late write, replacement prediction, new repetition, conditional retry or answer-informed resubmission can improve a historical result.
2. **No new protected use:** retire the pack and its equivalent assets for new official admissions across all affected jobs and Challenges. Retain public replay as replay, not fresh scientific evidence. Expiry of a clock or changing an identifier is not retirement.
3. **No linked live disclosure:** publication cannot reveal or enable derivation of active cases, shared roots, sensitive data or another active reference family. Check lineage, not only filenames. Pending independent confirmation remains unexposed.
4. **Rights and evidence checks pass:** the predeclared public rights, exact disclosure allow-list, integrity review and incident conditions permit release. Customer-confidential assets are not made public because computation ended.
5. **A durable release record exists:** commit the exact permitted case/answer bundle and bound result evidence, record eligibility and publish through the approved path. A stale approval or editable browser field cannot release data.

Once these conditions are true, public release should be a mechanical operation under the approved profile, not an optional choice to publish only attractive results. Delays, refusals and aborted packs need an auditable reason and disposition under the precommitted policy. Numerical failure does not erase the attempted cases; release their permitted failure evidence after safe closure.

The public bundle should contain permitted physical inputs and query semantics, qualified reference outputs and uncertainty/diagnostics, generator/reference/measurement identities, the public recipe for replay, commitments and allowed result evidence. Release case-scoped derivation material only where an explicit reviewed amendment permits it. Never release an OfficialEntropy root or parent key simply because this pack ended.

Separate three claims: the files match their commitments; the cases follow the committed sampling procedure; the committed candidate actually produced its predictions. The first does not prove the second or third. Public replay/proof or approved independent audit must support the claims Carbon makes. Do not describe private selection as publicly verified when the public transcript only proves file integrity.

### Future learning from published answers

Retired public examples may help miners learn the declared physics. That is intended, subject to the construction-data contract; public release does not automatically authorize uploading those records into validator training. Future protected tests must retain the qualified freshness and information-separation properties.

Changing a seed does not prevent exact repeats or near-duplicate families. A disclosed result is not automatically harmless in a small or highly correlated case space. The qualification campaign must test overlap, finite-support exhaustion and transfer from accumulated released packs. If exclusions or a new sampling law are needed, register them prospectively. Do not silently reject inconvenient cases or weaken physical standards. Decline or narrow a continuous public-release profile whose evidence cannot support it.

## 5. Prior commitment and verifiable randomness

The screenshots supplied by the owner motivate prior commitments and verifiable selection. This revision retains those requirements without attributing a complete protocol to their authors or assessing another subnet.

Prefer one reviewed platform provider rather than bespoke cryptography per Challenge. A fixed future threshold beacon plus previously committed private material remains a candidate for qualification where active-case confidentiality requires it. The crypto owners must specify the construction, event binding, secrecy, audit and withholding/abort behavior; no custom formula is authorized here. A block-hash alternative must satisfy the same bias, event-choice, finality and availability review.

A public beacon is not a secret seed when the remaining derivation is public. Public post-commit case selection is a possible different threat model, but this revision does not silently authorize it or declare current A4 secrecy requirements obsolete.

Time locks are optional. They can assist scheduled disclosure but do not erase the creator's knowledge or prove correct execution. Do not schedule irreversible plaintext release on an optimistic completion time. Default to verified retirement before release; a time-lock design must independently guarantee that no open work or related secret can be exposed.

Current A4/Data Management rules keep protected realization material private. Retired public-data disclosure therefore needs an explicit separate archive projection and domain amendment before any production release. Keep active protected APIs unchanged. Public artifact replay can precede a more ambitious public derivation-replay capability; name the remaining independent-auditor trust assumption.

## 6. Cost decides whether to wait, not whether to protect

Security and scientific adequacy are eligibility conditions. Among supported operating profiles, compare no intentional wait with additional bounded waits on matched resources and candidate streams.

Use full recurring work: permitted training labels, reconstruction, candidate evaluation, reference realization and required witnesses, retries/escalations, evidence/audit/disclosure work, abandoned work and replenishment. Keep upfront qualification cost/risk separate. Do not silently monetize fraud risk or trade an unmet control against saved compute.

For a simple fully populated batch comparison only, assume the same adequate reference pack would cost R for each standalone candidate, b committed candidates may share one such pack, and the batch adds H units of work beyond their standalone controls. Then:

    reference/control saving per candidate = R - (R + H)/b
                                           = ((b - 1)*R - H)/b

For b > 1, this toy cost break-even requires R > H/(b - 1). This does not establish acceptable waiting, selection precision or security. If the no-wait queue already shares references, use that real baseline rather than claiming its savings again. If a larger candidate field requires more cases or audits, use its actual R_b rather than R.

Illustration only: b=4, H=12 matched cost units. R=2 loses 1.5 units/candidate; R=40 saves 27; R=400 saves 297. No runtime, currency price, group size or security threshold is selected by those numbers.

For real proposals, replay the same admitted demand and compute limits and sum costs over actual groups, including underfilled, failed and empty groups. Divide long-run total cost by eligible completions rather than assuming perfect fill or averaging per-batch ratios. Keep distinct reference cases, solver attempts and candidate predictions separate.

Then check end-to-end feedback latency and supported discovery progress. Extra intentional waiting can reduce total queue delay when reference work is the bottleneck; it can worsen it when references are cheap. Measure rather than assume either. If the value of delay is unknown, report cost-versus-delay alternatives rather than inventing a dollar penalty or a unique optimum.

Adopt bounded waiting only after the evidence supports its incremental recurring saving, declared service requirements, adequate scientific resolution and acceptable effect on discovery. When evidence cannot distinguish alternatives, prefer no additional waiting and less implementation burden. An expensive job that fails these requirements needs funding, a narrower scope, another qualified reference design or a separate campaign offer; it cannot force complexity onto all mining.

## 7. Profiler output and implementation boundary

Each proposed Challenge reports: publication/audit mode; protection evidence and blockers; no-wait baseline; supported internal group size; any added wait; new reference cases and attempts per period; recurring cost; complete comparisons and feedback latency; discovery uncertainty; upfront qualification separately. No universal fit score or unsigned approval field.

Extend existing components: registry binds the profile, submission fixes methods, queue binds eligible membership and any wait, reference/evidence owners bind/cache/retire assets, A6/disclosure controls summaries and the separate approved archive. No extra miner reveal step, calendar ceremony, reward engine, global Challenge clock or custom per-physics cryptographic service.

NET-3's recorded implementation has an immutable per-version DEVELOPMENT evaluation context. Supporting multiple packs inside a Challenge is an explicit lifecycle/identity migration, not just adding a database column. Codex must map it and preserve replay, duplicate, scientific-comparison and reward semantics.

Mandatory implementation probes include late-admission rejection, mutable-code rejection, early-summary non-influence, no post-release prediction/retry acceptance, lineage-based disclosure blocking, retired-pack reuse rejection, underfilled-cost accounting, stalled-member closure, hostile operator/candidate evidence paths, and independent multi-Challenge scheduling. Registry checks are not executed attacks.

## 8. Evidence and sources

**External results:** drand documents verifiable randomness and time-lock assumptions; Dwork et al. and Blum/Hardt establish adaptive-reuse concerns under their models. These results do not qualify Carbon's deployment.

**Carbon hypothesis:** continuous submission plus internal pre-exposure sharing can preserve fairness with less miner friction; bounded waiting pays only in some reference-cost/demand regimes.

**Proposed Carbon experiment:** paired no-wait/queue-sharing/bounded-wait load and discovery studies with identical evidence obligations, plus held-out attack and retired-disclosure campaigns. The cost illustration is arithmetic, not an executed mining experiment.

**Qualified Carbon evidence:** none created by this revision. Upfront security, disclosure, numerical and statistical qualification remain required for the exact profile.

Source basis: Carbon research commit `1fa7341768838469116cdb070d3691550f444db0`; main reference `150ab9313c4cc7cd23e032aebd78bce829db7675`; original CPES v0.1 and its integration/control register; NET-3 commitment contract; Data Management and Trustless Verification. Owner's latest instruction selects the simpler design direction, not any unresolved production value or security acceptance.

Primary external sources, checked 12 September 2026:
- https://docs.drand.love/docs/cryptography/
- https://docs.drand.love/docs/timelock-encryption/
- https://arxiv.org/abs/1506.02629
- https://proceedings.mlr.press/v37/blum15.html
