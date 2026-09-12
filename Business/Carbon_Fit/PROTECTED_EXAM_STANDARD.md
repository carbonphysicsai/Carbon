# Carbon Protected Exam Standard: CPES-1

**Version:** 0.1, 12 September 2026

**Status:** proposed minimum for owner/domain ratification. This document specifies what a qualifying implementation must demonstrate. It does not approve security, choose production parameters, change A4, select a runtime ticket, deploy a cache, or activate an exam. The present workbench cannot enforce this standard.

**Scope:** incentive-bearing lean exams and separate frontier-promotion exams, including authorized shared reference assets. Client physical data requires additional rights and confidentiality review. Public practice remains a separate, non-authoritative service.

## Owner explanation

Carbon commits the exam rules before drawing the questions. Miners lock their methods before those questions can be known. A frozen group takes one common exam, and Carbon computes its reference answers once for that group. Carbon releases no performance feedback until the group closes. Later revisions take fresh exams. Isolated execution and independent audit must support the result. Missing protection evidence blocks official use; a throughput benefit cannot compensate for it.

## 1. Default policy: one frozen group, one exposure round

The recommended first profile is **FROZEN_COHORT_PRIVATE_CASES**. Group means a closed list of candidate commitments, not all registered miners and not a count of validator identities.

Within a group, permit reuse of the exact qualified reference assets for its committed candidates and required replicas. Close admissions before the authorized entropy event. Close all candidate work before releasing the registered performance projection. Retire the pack from new candidate admissions after the group. Preserve controlled evidence for replay and audit.

Do not permit a new or revised candidate to enter an exposed pack under a different account, validator, job ID, or later round. A per-hotkey once-only rule is not the protection boundary. Assume participants pool their observations and can control multiple identities. Legitimate separately committed candidates from one participant may enter the same group under the published admission policy; this does not imply unlimited submissions or sufficient statistical precision.

No persistent hidden reservoir or adaptive reuse across groups belongs to this default profile. A future exception requires a separate prospectively qualified population, custody, reuse, statistical, and disclosure contract. A client or profiler setting cannot enable the exception.

Fresh generation does not guarantee zero accidental overlap with prior cases. Science must examine effective support, collisions, near-duplicate families, and conditioning on prior disclosures. A changed seed is insufficient evidence of freshness. Do not invent rejection sampling or exclusions to repair collisions during operation.

## 2. Eight mandatory protection controls

| ID | Required control | Evidence required before official use |
|---|---|---|
| P1 | Commit the rules before cases become knowable. | Exact policy/configuration identity and externally anchored or independently witnessed ordering; tests against backdating, equivocation, and post-result changes. |
| P2 | Lock candidate behavior before case exposure. | Bound strategy, compilation, dependencies, permitted construction data and randomness; producer-independent reconstruction; artifact and runtime sealing before protected inputs enter candidate inference. |
| P3 | Draw cases by a fixed, auditable randomness procedure. | Qualified provider and derivation, fixed future event, verification and secrecy evidence, and failure rules that do not allow selecting favorable randomness. |
| P4 | Restrict case and answer access. | Tested execution isolation, minimal job-scoped authorization, protected secrets/reference stores, no unauthorized egress or cross-attempt state, and a reviewed privileged-operator trust boundary. |
| P5 | Share only within the frozen group; close feedback. | Global pack/admission ledger, common mandatory evidence, closed disclosure contract, cohort-wide release barrier, and tested retirement/reuse rejection. |
| P6 | Establish execution and scientific integrity. | Qualified generator/reference/measurements, bound predictions/results, reconstruction and audit evidence independent of the producer, and typed handling of failed or unavailable references. |
| P7 | Bound query volume and selection risk. | Prospectively set admission/resource limits and a statistical resolution policy covering the full competing field and repeated promotions. Sybil accounting cannot substitute for this evidence. |
| P8 | Qualify attacks and rehearse incident response. | Independent review of the exact deployment, adversarial tests, cross-service leakage assessment, append-only abort history, revocation/quarantine drills and explicit requalification triggers. |

All eight controls are prerequisites for the proposed profile. An unknown control remains an official-use blocker. A claimed pass, a checkbox, a hash, or a signed statement from the producer is not qualification evidence.

### P1: what must be committed

Bind the physical system, target population, SamplingPlan, generator/reference/measurement versions, mandatory pack, scoring rules, candidate assembly and resource policies, reconstruction repetitions, admission limits, group-close event, release policy, randomness algorithm/event selection, retry/cancellation rules, and audit/promotion policy.

Publish public-safe terms before accepting submissions. Commit confidential terms with a reviewed hiding-and-binding construction and make them accessible to authorized independent reviewers. Do not publish low-entropy descriptors or seeds as bare hashes and assume this hides them. A mutable repository branch, URL, staff timestamp, or object path is not an immutable externally ordered commitment.

Record a scheduled round even if it aborts. Preserve unavailable-beacon, failed-reference and canceled-round receipts. Operators cannot erase unsuccessful draws and report only favorable completed rounds. Availability controls and independent monitoring must constrain selective aborts; a commitment alone does not prevent refusal to execute.

### P2: two locks, not one

**Submission lock:** before the case-selecting event, fix all producer choices that affect the candidate. Include content-addressed dependencies, preprocessing, data permissions, initialization/batch policy, construction instructions, and inference behavior. A URL whose contents can change does not qualify. Do not fetch miner-controlled data or services after this lock.

**Execution lock:** the trusted reconstruction path builds the artifact under that committed recipe. Seal the artifact, preprocessing, runtime, and inference-state policy before evaluation inputs reach candidate inference. Reference generation may overlap reconstruction only if the isolation/data-flow contract permits it. Construction receives only its allowed training material, never evaluation roots, answers, or protected evaluation-derived signals.

Current A4 can derive training/evaluation roles from provider material held in the protected domain. This proposal does not claim that sealing final weights precedes acquisition of that root. The requirement is to freeze producer behavior before root realization and keep evaluation material out of reconstruction. A future stronger two-entropy/late-evaluation-seal design requires explicit A4 reconciliation, not an implicit change here.

Inference accepts only the registered physical inputs and emits the registered predictions. Prohibit persistent cross-case learning, writable communication between attempts, and post-exposure fitting unless a separate task contract explicitly qualifies that behavior. Within-case trajectory state remains allowed where the physical job requires it. Test model loaders, callbacks, preprocessors and host tooling, not only network weights.

### P3: randomness and Const's recommendations

The user-supplied screenshots request precommitment of evaluation/configuration changes and verifiable randomness, including time-lock and block-hash approaches. They do not establish a complete protocol or evidence about any participant's conduct. CPES-1 adopts the two underlying requirements: **prior commitment and auditable, unpredictable case selection**.

The recommended provider candidate for qualification is a **fixed future verifiable threshold-beacon event combined with previously committed private material inside an approved BeaconProvider**. The public beacon constrains selection; the private material preserves active-case confidentiality. The cryptographic/security owners must specify and review the combination, commitment scheme, entropy assumptions, custody, and verification evidence. This document specifies no new cryptographic formula or production suite.

Required conditions:

- Commit the exact beacon network/public-key identity, event-selection rule, private-material commitment, round identity, and deterministic derivation before submissions close. Select exactly the committed event, not one of several observed values.
- Commit private material before the future public event; do not choose secrets, salt, draw IDs, or round identities after seeing that event. Bind all seed-affecting metadata prospectively. Candidate contents, hotkeys, validator identities, retries and arrival order must not influence case selection.
- Check provider proofs and canonical encodings. Keep A4's existing exact 32-byte OfficialEntropy and role-separated HKDF boundary. Availability, provider composition and observation timing remain separately qualified inputs.
- Keep the official root out of untrusted construction/inference. A public beacon by itself is not a private seed when the rest of the derivation and generator are public.
- Do not implement naive multi-party reveal/XOR with an unhandled last-revealer abort. No optional secret contribution may change the completed draw. The review must address withholding, selective abort, provider outage and replay.
- With unavailable or unverifiable material, stop the affected round under its recorded failure policy. Do not substitute a clock, retry-dependent nonce, staff RNG, or another convenient block. Reuse the same authenticated event on a transport retry. A new round follows the published rule and preserves the old abort record.

A chain-block source is an alternative only after its manipulation, withholding, finality/reorganization and source-selection risks satisfy the same review. We do not claim one beacon is universally optimal. Profile the qualified candidates on security assumptions, availability, latency and integration cost; reject those that fail the protection requirements before optimizing cost.

**Time locks are optional mechanisms, not the standard itself.** They can bind a scheduled disclosure of appropriate committed material. They do not erase the sender's knowledge, establish an unbiased generation law, or prove execution. An automatic decryption time cannot expose an active pack while slow candidates remain open. The release rule must end those attempts before exposure or reject that time-lock design. No current seed-publication rule changes through this document. Public replay of retired secret material needs explicit prospective rights/security/entropy approval and must not expose linked active packs or roots. For confidential client cases, use the authorized independent-audit path rather than promising public plaintext disclosure.

### P4: minimum custody and insider boundary

Separate the reference service, reconstruction worker, candidate inference worker, result evaluator, public/practice APIs, and client intake by tested permissions and data flows. Candidate workers have no answer-store mount, root seed, vault credentials, arbitrary outbound network access, or cross-job writable channel. Use job-scoped, expiring authorization and qualified cleanup, including shared memory, temporary files, device memory, backups, caches and crash/log paths. Encryption in transit and at rest supplements these controls; it does not replace them.

Only authorized trusted components get reference plaintext. Do not give arbitrary validator hosts a global answer bank and describe it as confidential from their operators. A host administrator who can read plaintext can copy it; a signature from that same host does not establish independent correctness. Single-validator compute planning is not a single-person trust assumption.

Before operation, name every trusted operator/component and the assumed corruption/collusion boundary. Require independent execution-integrity evidence appropriate to that boundary, through an approved audit/replay or other qualified verification design. The producer cannot also be the sole evaluator/custodian of its result. Separate service accounts under one administrator do not constitute independent operators. Independent reference-method evidence and independent execution audit are different requirements.

Fully colluding custodians and auditors, or compromise of the declared trusted computing base, remain outside a trust-minimized claim unless a separately qualified design addresses them. Confidential computing and cryptographic verification are possible later mechanisms, not implied capabilities. An unsupported hostile-host claim is a blocker, not a disclosure footnote that waives protection.

For MMS, the solution expression, hidden coefficients, derivative graph, reference closure and generated source code may reveal the answer. For cached CFD, include case descriptors, mesh identities and solver artifacts in the exposure audit. For experimental/customer data, include public overlap, rights and who already knew the selected cases. The same eight controls apply to each reference type, with role-specific tests.

### P5: group release and cache lifecycle

A group closes on a predeclared schedule. Do not wait for all network miners or let a last participant extend the cutoff after seeing randomness. Registration changes do not reopen the group. The admitted field and waitlist follow the public resource/admission policy rather than an outcome-dependent ranking.

Every eligible nonzero candidate completes the same registered mandatory pack and reference treatment. A conclusive mandatory physical failure may terminate remaining work under the existing scientific contract; no unfinished or shallow exam produces a positive result. Do not change an individual candidate's cases, reference fidelity, weights, stress mass or measurements.

Release no score, rank, case-level error, partial gate outcome or private diagnostic before all admitted attempts reach their registered terminal states and results have passed the required evidence checks. Status, timing, timeout, artifact size and cache-hit behavior are also potential signals; expose only the reviewed operational projection. Reference work does not enter public practice, the website, notifications, or Landscape exports.

In the default profile, a pack serves one closed feedback round. Use cached answers inside it after checking case/reference identity, qualification, revocation and custody. Repetitions and audits do not increase the number of independent physical cases. No new candidate enters it after release, even if a miner has not seen it before or runs on another validator. Required replay uses the same bound artifact and evidence, not a new opportunity to optimize after exposure.

Retirement ends eligibility for new official admissions, not forensic retention. Preserve encrypted audit assets under approved retention. Do not relabel a known pack as fresh by changing its identifier. Do not publish or delete related secrets without checking other active uses and rights. Later disclosure does not authorize resurrecting the pack as protected evidence.

### P6: correct evidence, not just secret files

A cryptographically intact answer can still be scientifically wrong. Qualify the generator, reference, measurements and comparison resolution for the exact physical claim. A cache inherits that qualification and its limitations; hashing does not create it. Require exact artifact/prediction/pack/result binding and evidence that the committed execution produced those predictions.

Retain numerical failures, uncertainty, witness disagreement, unavailable references, and population censoring. Use registered same-case retries or qualified escalation, not easier replacement cases. A deterministic retry must not mint new entropy. Statistical reconstruction repetitions use the precommitted randomness policy, not best-of-many seed selection. Infrastructure or reference failure cannot become candidate physics failure or automatic success.

Round rankings nominate candidates. Where a frontier advance needs independent confirmation, freeze both incumbent and contender and apply their registered common fresh promotion exam. Do not promote by comparing historical scores from different packs. Preserve mandatory physics and unresolved decisions.

### P7: finite field and admission

Before operation, qualify the maximum admitted candidate field, attempt/replica rules, practical decision resolution, and repeated-promotion error control. Public/private case overlap and many precommitted candidate hypotheses remain statistical concerns even without adaptive feedback.

No numeric group size, fee, sampling law, evidence count, score precision, retry allowance, confidence level or security risk tolerance is selected here. Require owner-supplied, qualified values. A profiler recommendation outside the supported field must return a blocker. Fees, stake, one-hotkey limits and novelty filters are not proofs against collusion; none may change the scientific exam. Do not filter official evidence depth using Landscape forecasts.

### P8: qualification and incident response

Run the attack cases in the companion registry on a faithful development stack, with adversarial candidate code, corrupt-provider/custodian scenarios and held-out attack campaigns. Separate software conformance evidence from measured attack resistance. Use evaluator-held shadow cases to distinguish useful physics learning from incremental inference of protected realizations.

Any demonstrated unauthorized answer/case access, post-lock mutation, favorable-redraw path, result substitution, or feedback-driven reentry blocks the affected profile until repaired and retested. Statistical leakage bounds and residual-risk acceptance require preregistered owner criteria. Absence of a found exploit is not proof of zero risk.

On suspected exposure or integrity compromise: quarantine the implicated pack, credentials and pending decisions; stop new admissions, disclosure and finalization through existing authority boundaries; retain evidence; record scope and notify the responsible owners. Retry on the same pack only where the incident policy proves it remains eligible. Otherwise rebuild affected work through a new authorized round. Do not erase historical results or retroactively label a miner scientifically failed. Economic sanctions, compensation and final historical disposition remain their owners' decisions.

## 3. Round sequence

| Phase | Permitted transition |
|---|---|
| Policy committed | All scientific, access, admission, entropy and release terms fixed before case knowability. |
| Group locked | Candidate recipes/dependencies and eligible membership immutable before the fixed future event. |
| Randomness verified | Approved provider consumes the fixed event and bound private material; protected services realize role-separated material. |
| Artifacts sealed | Independent reconstruction completes or reaches a typed terminal failure; valid artifacts/runtime identities sealed before protected inference. |
| Common exam executed | Qualified reference answers reused inside the group; predictions/results retained; all mandatory evidence or conclusive failure recorded. |
| Results closed and released | All attempts terminal, required integrity/evidence checks complete, public-safe projection released. |
| Pack retired | No new official candidates; controlled replay/audit retained. A later adaptive round gets fresh evidence. |

These are explanatory phases, not new serialized A7 states. Reference generation and reconstruction may overlap only under their approved dependency/isolation policy. Runtime enforcement must reject an illegal transition rather than record it as a warning.

## 4. Authority, provenance and adoption

This proposal translates the screenshot recommendations into a Carbon-specific minimum; it does not authenticate the speakers or adjudicate the other subnet. It extends the prior protected-cohort proposal with explicit controls and profiler blocking rules. Existing constitutional laws remain controlling.

The source baseline was Carbon main `150ab9313c4cc7cd23e032aebd78bce829db7675`; the research branch before this change was `d6b81d17dc1f65d467ef877d2d99693988da70dc`. A4 defines role derivation, not a qualified provider. A new hybrid provider, release rule, global cohort lifecycle, and any public retired-seed disclosure require explicit domain reconciliation. No code change or browser field grants that authority.

**External results:** the sources below explain randomness, time locks, adaptive reuse and access-control limits. **Carbon hypothesis:** fresh closed cohorts can reduce reference cost while making the exposure boundary easier to qualify. **Proposed experiment:** adversarial qualification of this exact protocol and comparison of its measured overhead/feedback delay with the existing research model. **Qualified Carbon evidence:** none from this policy package.

## 5. Primary/official technical sources

- Carbon `CONSTITUTION.md`, `.agent/INVARIANTS.md`, `Design_Specs/Trustless_Verification.md`, and `Business/Carbon_Fit/PROTECTED_REFERENCE_REUSE.md`: current authority and proposed cohort limits, inspected 12 September 2026.
- drand, Cryptography and Security Model: https://docs.drand.love/docs/cryptography/ and https://docs.drand.love/docs/security-model/ . Threshold beacon guarantees depend on the scheme, implementation and corruption assumptions; no Carbon provider qualification follows.
- drand, Timelock Encryption: https://docs.drand.love/docs/timelock-encryption/ . Timed decryption with stated network/cryptographic limitations; the sender still knows its own plaintext.
- RFC 5869: https://www.rfc-editor.org/rfc/rfc5869 . Extract-and-expand role derivation is not an entropy source or confidentiality guarantee for a public input.
- Dwork et al., Generalization in Adaptive Data Analysis and Holdout Reuse: https://arxiv.org/abs/1506.02629 . Adaptive-reuse guarantees concern the paper's algorithms and assumptions, not this proposed exam.
- Blum and Hardt, The Ladder: https://arxiv.org/abs/1502.04585 . Leaderboard selection/feedback evidence; not permission to replace Carbon's mandatory scientific requirements.
- OWASP, Authorization and Cryptographic Storage: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html and https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html . Access control and encryption are complementary and threat-model dependent.
- Bittensor, commit-weights: https://www.bittensor.com/docs/tx/commit-weights . Weight commit-reveal concerns weights; it does not by itself commit or protect Carbon's exam.
