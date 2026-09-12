# CPES-1: profiler and Engineering integration

**Status:** proposed integration requirements for the Carbon Fit research branch. No production code or browser enforcement is included. Current workbench v0.1 remains an offline scenario calculator. The following fields and states are planning vocabulary, not new official result or authority types.

Related: [minimum standard](PROTECTED_EXAM_STANDARD.md), [machine-readable controls and attack cases](PROTECTED_EXAM_CONTROLS.json).

## 1. A protection gate before an operating recommendation

Add **Case protection** as a mandatory subsection of the existing **Exam** check. Do not replace or average the existing six checks. Reference adequacy, physical requirements and case protection remain separate prerequisites.

The intended decision order is:

    scope the physical job
    -> inspect scientific and protection support
    -> identify designs eligible for further review
    -> compare operating costs for those designs
    -> request exact domain qualification before official operation

The offline tool may show hypothetical cost comparisons while support is missing, but must label them **CONDITIONAL SCENARIO; NOT CLEARED FOR OFFICIAL USE**. It must not choose an insecure design as the recommended live operating profile because it has a higher exams/day result.

Suggested review outputs:

| Planning state | Meaning |
|---|---|
| UNASSESSED | Required case-protection inputs/evidence are missing. |
| PROTECTION_BLOCKED | A control fails, a known exploit remains, or a required deployment assumption lacks support. |
| READY_FOR_DOMAIN_REVIEW | The reviewer has a complete proposal and evidence package; no security or scientific qualification follows. |

Only the existing authorized registry/evidence path can establish the eligibility of a real profile. A browser checkbox, imported JSON, user-entered qualification ID, or producer-signed receipt cannot mint approval. Exact identity, scope, signer authority, validity and revocation must be verified outside the editable client draft.

## 2. Minimum review record

Extend the existing ScopedJobProposal/ReferenceRolePlan/OpportunityReview design rather than add an alternate scientific engine. Store:

- proposed CPES profile and exact task/reference/environment identities;
- P1-P8 control evidence references, responsible reviewers and unresolved issues;
- commitment and randomness/provider procedure, event timing, and custody topology;
- candidate-lock and execution-lock implementation; role-isolation and output-binding evidence;
- cohort admission/cutoff/release policy, maximum admitted field, candidate/replica/attempt policy, and source of each value;
- cache scope, reference-asset eligibility checks, retirement/replenishment and incident policy;
- statistical comparison/promotion policy and source support for its candidate field;
- attacker model, public/practice/intake/notification surfaces, privileged-host assumptions and audit independence;
- attack campaign references, deployment identity, remaining risks and requalification triggers.

Do not store actual seeds, answer files, hidden case identifiers, leaked test payloads or confidential customer cases in the workbench, client brief or public repository. The draft captures public-safe descriptions and opaque authorized references.

The control registry supplies null placeholders for unsupplied production values. Unknown group size, reveal policy or provider acceptance blocks the real profile. It need not prevent a harmless offline development calculation.

## 3. Cost and cadence changes

Keep one validator's supplied compute as the planning unit. Security review and independent audits may require other accountable actors; do not confuse that with assuming additional validators or free duplicate compute.

Keep three records separate:

1. **Upfront qualification:** threat-model review, cryptographic/entropy review, isolation testing, leakage experiments and initial approval risk/cost.
2. **Recurring work:** commitment/proof verification, closed-group scheduling, isolated execution, required audits, reference attempts/replenishment, logging/receipts, cache reads and incident/abort reserve.
3. **Client workload:** latency, accuracy, cost and rights for deployed use.

For the actual admitted rounds, account for total recurring work as:

    sum(candidate reconstruction + allowed training-reference work
        + inference/measurements + candidate-scoped security overhead)
    + sum(fresh round reference work + round-scoped security/audit work)
    + required separate promotion work + recorded failed/aborted work

Convert only matched resource units. Model queues and round-fill delay separately from active compute. A post-cancellation partial cohort still incurs the reference work already performed. Do not assume every attempted candidate or reserved seat produces a completed independent proposal.

The v0.1 calculator's `ceil(n/b)*R` is a batching scenario bound. For a real proposal, `b` must not exceed supported admission/reuse/selection limits, and actual closed rounds determine reference production. A large `b` reduces amortized reference work but does not qualify reuse or increase the number of independent cases. Account for low proposal supply, unavailable references, and stalled group closure.

Reports should show **protected complete comparisons per validator-compute-day**, time to permitted feedback, and supported progress/time-to-target. Unprotected, incomplete, duplicate or unaudited attempts must not inflate the headline. Keep operational failures visible without converting them to scientific failures.

## 4. Integration by existing owner

| Existing owner | Required work; no implied implementation permission |
|---|---|
| Challenge/Validation Dossier owners | Bind CPES profile, qualification evidence, finite candidate field, physical-case support/collisions and censoring. |
| A4 / Data Management / Trustless Verification | Resolve the production provider, event timing, private-material combination, canonical bindings and any future retired-material disclosure. Retain the current typed 32-byte root and role derivation. |
| Candidate commitment / assembly / reconstruction owners | Pin producer inputs, reject mutable dependencies, isolate permitted training data and seal the built artifact before protected inference. |
| Wave C execution/reference/evidence owners | Enforce case/answer isolation, exact TruthAsset reuse, global round membership, release barrier, typed failures and integrity/audit receipts through existing lifecycle types. |
| Miner MCP / disclosure / Landscape owners | Prevent early or cross-service leakage; expose only registered projections; do not use predicted quality to vary scientific evidence. |
| Frontier promotion owner | Use its qualified fresh common confirmation and repeated-decision policy; no promotion from cost scenarios or unrelated historical score comparisons. |
| Workbench / website Engineering (#139) | Add the planning gate, conditional arithmetic labels, public-safe evidence references and import-forgery tests. Keep client data collection isolated from official evidence. |
| Security and Operations | Approve named trust assumptions from evidence, set custody/key/retention procedures, qualify incident/abort behavior and measure recurring overhead. |

This proposal does not select a Wave C ticket, move a roadmap dependency, reopen B-E4 or make its optional utility campaign a launch requirement. Actual incentive-bearing use still needs the existing scientific/security acceptance, now with this proposed concrete protection evidence. Engineering must route any incompatible lifecycle/provider behavior through a prospective contract amendment.

## 5. Engineering acceptance and red-team handoff

The companion registry contains 26 attack scenarios. Each specifies the attempted violation and expected result. Engineering must implement and execute them on the exact proposed stack. Static checks on the registry are not attack tests.

Required study order:

- Test immutable ordering and transition rules with synthetic cases, including group close, partial failure, duplicate/retry, late reentry, cancellation and exposure.
- Test the approved cryptographic provider/commitment primitives and their composition, including failure/withholding and malformed/proof mismatches.
- Exercise malicious candidate/loader/callback code against reconstruction, reference, inference, metadata, temporary state, network and public surfaces.
- Attempt colluding-account reuse, oracle construction, pack membership and cumulative feedback inference. Use independent shadow cases and hold out attack variants for confirmation.
- Test corrupt-operator/result-substitution paths against the actual audit or stronger verification design. A signed lie must not pass merely because the producer owns a valid key.
- Rehearse compromise of keys, cache, root host, reference service and client intake; verify quarantine propagates to affected pending decisions while preserving history.
- Measure full-path cost and feedback latency with the controls enabled. Repeat after Wave C on matched cases/hardware/clocks and separately on unexposed confirmation cases.

Owner-supplied error/leakage risk criteria determine the statistical study size. Do not copy toy study counts, zero observed exploits, or benchmark throughput into a production qualification claim.

## 6. Smallest remaining decisions

The proposed policy defaults are explicit: frozen cohorts, one feedback exposure round per pack, shared exact references inside that group, no adaptive cross-group reuse, and no unqualified persistent reservoir. To activate an implementation, owners still need to approve the provider/commitment/custody design, evidence-supported admission/attempt/release limits, independent audit and statistical resolution, plus deployment and incident procedures. Those values are absent, not silently delegated to a miner or the profiler.

## 7. Adoption status for this delivery

Documentation, machine-readable requirements and Engineering handoff only. No deployed backend, local workbench UI or seeding/scoring implementation changed. The standard and integration requirements can merge as a proposal without representing any of the missing security decisions as approved.
