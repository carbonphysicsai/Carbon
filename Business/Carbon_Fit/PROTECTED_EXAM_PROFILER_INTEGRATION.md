# CPES-1 v0.2: continuous-loop profiler and Engineering integration

**Status:** proposed integration requirements, not implementation or acceptance. Read [CPES-1 v0.2](PROTECTED_EXAM_STANDARD.md) with [its controls](PROTECTED_EXAM_CONTROLS.json). This revision supersedes v0.1's universal scheduled-round and blanket-feedback-barrier requirements in the research proposal. Current domain contracts remain controlling pending explicit reconciliation.

## 1. Smallest useful implementation

Preserve the existing miner interaction: submit an immutable strategy, obtain a receipt and execution expectation, retrieve the permitted result. No miner reveal transaction, universal freeze calendar or new prize per exam pack.

Add Case protection under the existing Exam review, not as a new averaged score. Keep UNASSESSED, PROTECTION_BLOCKED and READY_FOR_DOMAIN_REVIEW as planning states only. The existing registry/evidence authority, not an editable draft, establishes real eligibility.

Show three comparable operating proposals using the same security floor:

| Proposal | Added batch-fill wait | Reference behavior |
|---|---|---|
| Fresh/no-sharing comparison baseline | None | Independent fresh pack per appropriate evaluation job; required paired comparison stays common. |
| Default internal queue sharing | None | Reuse one fresh pack only among compatible jobs already committed before case selection. |
| Optional bounded-wait sharing | Finite, evidence-supported, published bound | Accumulate permitted jobs, then lock membership before case selection; run a valid underfilled group at the bound. |

The first is an analysis baseline, not an additional permanent service mode. Shared reference does not change candidate evidence depth. Persistent adaptive reservoirs remain outside this default.

## 2. What the profiler must calculate

Use one validator's declared resources and observed compatible proposal supply. Retain CPU/GPU classes, memory and concurrent-worker entitlements; do not convert unrelated device times without support.

For each proposed wait policy, produce:
- actual group sizes, not just configured maxima;
- fresh reference cases, reference attempts and required witness/escalation work;
- complete eligible candidate comparisons, distinct proposals and repeated reconstructions separately;
- recurring total work, cost per eligible completion and abandoned/incomplete work;
- queue time, intentional fill wait, reference readiness, execution time and total feedback latency separately;
- public answer-key availability delay separately from the result-summary delay;
- best-supported progress or time-to-target from independent campaign evidence, when available;
- implementation and upfront qualification cost/risk in a separate record.

The continuous no-wait queue is the relevant baseline. Do not claim its opportunistic savings again as a benefit of adding a wait. Larger admitted fields may require different evidence: use the qualified reference/evidence cost for each field, not an unchanged convenient pack.

The toy break-even `((b-1)*R-H)/b` applies only to a full, homogeneous group with unchanged evidence obligations. A real cost model sums actual groups, all required candidate work and failure costs. Underfilled groups pay the actual reference bill. A configured maximum is not a predicted group size. The old `ceil(n/b)*R` calculator remains explicitly hypothetical until its demand/scheduling assumptions hold.

Do not choose a production wait value from a cost slider. First exclude scientifically/security-ineligible proposals, then compare recurring cost and end-to-end latency against owner-supplied service requirements. Measure discovery impact under matched resource budgets; no invented monetary value for delay. If those data are absent, return a conditional Pareto comparison and the next measurement, not a universal optimum.

## 3. Answer-publication review

Add one declared mode per proposal: public archive after verified retirement, or confidential evidence with authorized audit. Publication rights are independent of reference price. No source rating or cheap reference automatically authorizes disclosure.

Capture public-safe references for: intended archive contents; required-use closure; prediction/result binding; pack retirement; cross-pack/cross-Challenge lineage; rights and disclosure approval; release execution and incident handling. Do not store active seeds, answers, candidate secrets or private customer cases in the workbench.

The backend must derive release eligibility from the authoritative ledger and verified permissions. A client Boolean, arbitrary evidence URL or user-entered signature cannot mint approval. The public archive projection must be separate from active A6/MCP protected results. Existing root-secrecy law remains until its owner approves an exact scoped amendment.

Result summaries and plaintext answers have different conditions. Early summaries require proven non-influence on pending jobs under the approved execution and reward/disclosure path. Without it, hold the affected pack's summaries. Plaintext publication requires the stronger retired-answer condition in CPES-1. Never publish on a timer merely because a worker was expected to finish.

## 4. Reuse existing owners

| Owner/seam | Minimum change |
|---|---|
| Challenge registry and Dossier | Bind supported execution/publication profile, candidate field, freshness/overlap and exact qualification references. |
| A4/Data Management/Trustless Verification | Qualify provider/event assignment and any retired-data derivation disclosure. Keep existing root types and role separation; no custom cryptographic composition from this ticket. |
| NET-3/A7/assembly | Preserve immutable methods and copy/retry semantics. Reconcile fixed per-version evaluation context with future multiple pack identities before runtime changes. |
| Execution queue | Bind eligible group membership before case knowability; default to no intentional fill wait; enforce any permitted wait/closure independently per Challenge. |
| Reference and evidence services | Bind exact truth assets and predictions, reuse only within eligibility, preserve failures and retire assets against new protected use. |
| A6/disclosure and audit | Control result projection and separate safe archive release; verify atomic release eligibility and preserve independent execution evidence. |
| Scientific comparison and rewards | Retain common fresh comparison where required; no historic-score substitution, baseline reset or reward created merely by pack completion. |
| Workbench/website | Surface conditional economics and protection blockers without granting authority or collecting protected material. |

One platform provider and one execution queue policy should serve compatible Challenges. Do not create a per-physics cryptosystem, a second reward engine or a global assessment barrier. Single-validator compute does not waive independent integrity/audit evidence or assume extra validators for free.

## 5. Bounded development and acceptance

First integrate planning fields and the cost comparison with synthetic/public fixtures. Map exact runtime transitions and unresolved owners. Do not deploy a vault, call a real entropy provider, enable public answer release or alter official scoring as a side effect.

Required faithful-stack tests include late/colluding admission, mutable dependency changes, shared-pack early feedback, cancellation/retry influence, prediction writes racing release, retired-pack alias/reentry, disclosure of an active parent key, near-duplicate future-case exposure, confidential-data release, underfilled batches, deadline stalling, selective abort and cross-Challenge interference.

The registry retains all 26 original attack IDs, with v0.2 expected behavior, and adds four retirement/operating tests. They remain NOT_EXECUTED. Package/arithmetic tests are not substitutes for them.

Use equal-resource traffic/load and discovery experiments to compare no-wait and bounded-wait policies. Freeze scientific requirements before profiling. Confirm policy choices on held-out traffic/physics campaigns, including low supply, bursty supply and malicious churn. Select study size and acceptance through owners, not prototype defaults. Repeat after Wave C with matched hardware and timing, then with fresh unexposed scientific evidence.

## 6. Authority and handoff

Continue through #139/#142 and the selected Engineering board. This research revision does not select an active runtime ticket, change mainnet dependencies or authorize deployment. The existing v0.1 workbench source remains a conversation artifact, not executable repository assets. Its import schema needs an explicit migration; old missing protection fields remain unassessed.

Source basis: CPES-1 v0.1 at `1fa7341768838469116cdb070d3691550f444db0`; latest owner instruction preferring continuous mining and safe retired-answer transparency. No production values, qualified security findings or live throughput measurements are supplied by this revision.
