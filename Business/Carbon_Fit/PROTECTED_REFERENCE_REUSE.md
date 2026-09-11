# Protected reference reuse: design and qualification review

**Status:** proposed architecture and threat model, not production security acceptance. See [authority](README.md). No reservoir, cache, entropy provider or reuse limit is activated here.

## 1. The claim we can investigate

Carbon can investigate computing a qualified answer once and sharing it across a bounded, registered comparison cohort. This may reduce repeated reference expenditure. It does not make fresh physical solves cheap and does not prove that a persistent hidden answer bank is safe.

Separate four properties: numerical/reference adequacy; artifact integrity; confidentiality from named adversaries; and validity under adaptive reuse. Hashes do not prove the solver ran correctly. Encryption does not prevent a privileged plaintext consumer from copying an answer. A secret seed does not prevent learning about fixed cases through repeated feedback.

The existing [verification specification](../../Design_Specs/Trustless_Verification.md) and [reference runtime](../../Design_Specs/Runtime_Julia_Truth_Oracle.md) remain controlling. Cache reuse is conditional on the scientific population, SamplingPlan, reference identity, protected execution and disclosure policy. A content hash alone grants neither eligibility nor rights.

## 2. Distinguish cache classes

| Class | Potential reuse | Principal constraint |
|---|---|---|
| Static infrastructure | Pinned solver images, kernels, meshes where task-independent, qualified code | No hidden data in public build artifacts; pin numerical semantics |
| Authorized construction data | Training-only reference assets where the construction policy permits | Do not substitute for fresh training data where required; no evaluation-role crossover |
| Frozen-cohort evaluation answers | Same registered protected pack across committed candidates | Freeze eligible construction/artifact identities before cohort feedback; retain independent reconstruction |
| Persistent hidden reservoir | Sampling protected cases over successive rounds | Separate population, sampling, adaptive-disclosure, retirement and secrecy qualification |
| Qualification/witness assets | Repeated authorized audit checks | Disclosed checks do not become an undisclosed exam by relabeling |

Each asset binds canonical physical case, reference method/configuration, implementation and environment, units/coordinates/query semantics, precision, uncertainty and diagnostics, applicability, rights, qualification and failure status. Operational eligibility must be checked at use time against current revocation/qualification policy while historical evidence stays immutable. Fail closed on mismatch, revoked access, corruption, unavailable truth or unsupported scope. No silent weaker reference fallback.

## 3. Candidate-first cohort proposal

Prefer investigating this route before indefinite reservoir reuse:

1. Domain owners define and qualify the Challenge population, finite SamplingPlan, reference, measurements, mandatory pack, resource profile and disclosure policy. Commit the exam contract before protected instances become knowable. Candidate outcomes cannot select those terms.
2. Close the eligible candidate cohort. Bind strategies/construction plans and required dependencies. Prevent adaptation from any cohort-result feedback. Reconstruction remains under validator control with its own randomness/information policy.
3. Acquire protected official entropy through the separately authorized provider policy and generate the registered cases. Do not treat a future public beacon alone as a confidential seed: if public material determines cases, participants can reproduce them. Generation timing and candidate commitment must align with the existing A4 contract.
4. A controlled reference worker computes and qualifies/binds the exact answers, then stores them for this cohort. Reference work can overlap reconstruction only when the information/dependency boundaries permit it.
5. The evaluator executes every eligible candidate's registered mandatory evidence against the same bound pack, retaining required replicas and uncertainty. Candidate code receives only the necessary case inputs, not reference answers or seed-store access.
6. Release only the registered result projection. Expire active reuse after the authorized cohort/use window; retain audit evidence under controlled retention. New adaptive cohorts use fresh independently registered evidence unless a separately qualified reuse policy permits otherwise. Frontier promotion uses its own registered common evidence, not automatic reuse of screen results.

This is a proposal, not a statement that current P0/A4 implements cohort sharing. Cases derived afresh after cohort commitment avoid some precomputation problems but do not remove host trust, finite-sample uncertainty or disclosure risk. Include the cost of producing those fresh batches in cadence and economics.

## 4. Precomputed reservoir alternative

Precomputation can move costly reference creation off the response path. It requires the task, population and generation policy to be committed before instances become knowable. Bind the resulting reservoir and its eligible contents before later candidate-result-informed selection. Candidate commitment and any subsequent selection entropy have separate roles.

Later randomness can select from a committed reservoir; it cannot prove that earlier cases were generated using future entropy. Private construction of the reservoir, distribution conformance, selection/replacement rules, coverage, duplication and censoring must all earn evidence. Selection without replacement from a finite reservoir is not automatically equivalent to independent fresh population draws.

Before this route, domain owners must resolve the relation between reservoir provenance, A4 provider-derived entropy, generation timing and official exam identity. No implementer may replace A4 with an ad hoc seed or secret/key mixture under the name of caching. If current contracts do not support it, require an explicit prospective amendment and qualification.

Capacity planning must include a finite lifetime, retained audit storage, new reference production, exhaustion and emergency retirement. Do not divide generation cost by an unbounded number of future submissions.

## 5. Custody and adversaries

| Actor or failure | Boundary to test |
|---|---|
| Website visitor/miner | No cache endpoint, signed object URL, reference key, seed, hidden case ID or detail in intake responses |
| Submitted construction/model | No reference mount, vault credential, network egress or cross-attempt writable state; exact allow-listed execution and outputs |
| Ordinary staff/compromised intake service | Separate identities, stores, keys and networks; no rights escalation from customer intake to official evidence |
| Reference/evaluator operator with plaintext/root access | Explicit trusted-party boundary; storage encryption cannot hide live plaintext from this actor |
| Colluding participants/repeated submitters | Cohort commitment, disclosure accounting and attacks against cumulative feedback |
| Storage/backup compromise | Encryption, separate key custody, minimal access, auditable access and bounded retention |
| Integrity attack/reference poisoning | Independent provenance/qualification checks, immutable identity, signed/authenticated receipts where owned, mismatch rejection |
| Timing/log/artifact leakage | No protected case diagnostics, cache hit/miss detail, reversible identifiers, crash dumps or secrets in public surfaces |

Do not distribute the answer vault to arbitrary decentralized validator hosts and claim secrecy from their operators. A plausible initial topology is controlled reference/evaluation custody with validators receiving scoped receipts or performing approved audits. This is a trust-minimized architecture proposal; network correctness, audit independence and operations still need qualification.

Confidential-computing/attested execution or cryptographic protocols may reduce specific trust assumptions later, but no such option is integrated or qualified by this document. Their threat model, plaintext boundaries, performance and side-channel limitations require separate review. Merely using a container, TLS, a cloud vault or several validators proves none of these properties.

## 6. Controls to qualify

Keep seed material in a restricted secret store, answer assets in an encrypted private store and keys under a separate least-privilege service identity. Authorize each access by exact role and exam/case context; opaque IDs are not authorization. Eliminate candidate access to host credentials, object-store keys, unrestricted loaders and writable persistent channels. Share no official material with the client website, notifications or research/practice service.

Retain enough private provenance for replay/audit. Expose only reviewed opaque commitments, not raw seeds or unsalted hashes of low-entropy case descriptors that support enumeration. Security owners select a reviewed hiding-and-binding commitment scheme; this proposal does not specify custom cryptography or alter A4. Publication after retirement also requires review because reused populations, data rights or linked exams may remain sensitive.

A candidate necessarily processes the physical inputs it predicts. Seed secrecy alone therefore cannot hide an input from the running model. Protect the answer path, prevent egress, freeze the candidate before exposure and budget what leaves the execution domain. Test inference, reconstruction, logs, errors, caches, temporary files and outputs as a combined system.

[OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [Cryptographic Storage](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html) and [Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) supply implementation review guidance, not a Carbon security certificate.

## 7. Adaptive reuse and scientific validity

[Dwork et al., Generalization in Adaptive Data Analysis and Holdout Reuse](https://arxiv.org/abs/1506.02629) and [Blum and Hardt, The Ladder](https://arxiv.org/abs/1502.04585) establish that repeated adaptive feedback needs statistical treatment even when a holdout is not published. Their guarantees apply to their algorithms and assumptions, not automatically to Carbon's physical gates or noisy reconstruction.

Do not import an arbitrary noise level, score rounding, query quota, cooldown or reservoir size and call reuse qualified. Public precision/rate limits can be controls, but secrecy and transfer-generalization evidence require a registered campaign. Challenge-health signals may trigger review under policy; they cannot silently change current cases or scoring. Keep public/practice cases, screening/cohort material and fresh promotion/product evidence in their authorized roles.

## 8. Proposed qualification campaign and release blockers

Use synthetic/development assets first. Test enumeration and membership inference, cumulative feedback attacks, collusion, exfiltration, raw hash/seed leakage, timing differences, debug outputs, backup access, key rotation/revocation, provenance mismatch, reference disagreement and typed outage recovery. Compare attacks against evaluator-held shadow cases unavailable to the attacker so ordinary learning of declared physics is not confused with learning protected realizations.

Science must verify finite-population/stratum coverage, uncertainty, reference quality, failure/censoring and decision resolution. Operations must verify cold generation, permitted amortization, storage and refresh costs. Security must approve the named trust model, disclosure/use limits and incident/retirement response from evidence. Those numerical limits remain unselected.

Block release for an unresolved custody assumption, unapproved entropy/commitment sequence, unauthorized asset reuse, inadequate reference, uncharacterized adaptive leakage, missing retirement capacity or an incomplete mandatory evidence path. A suspected exposure quarantines affected active assets and related pending decisions under the owning incident policy; it does not erase history or create candidate scientific failure.
