# PLT-23 confirmed non-creation reservation release

Working contract, DEVELOPMENT recovery/accounting implementation.
Base: main `4b652cd85e85200b7eaec57b453172555d641795`.
Scope: local PLT-23, reassigned to Product by Root Test Lead under the owner's
team delegation. Current OWNER-DX-03 applies; Hub retired; Root owns guarded
engineering merges. No provider request, real ledger edit, launch, spend,
credential, private-bank or holdout read is authorized to this builder.

Authority: queue's confirmed-non-creation requirement; existing operator
`IntentState.REJECTED` means definitive provider refusal with nothing created;
standing grant/cap records remain unchanged. Data Collection's public contract
map and Root's delegated working decision distinguish this from NOT_FOUND.

KEEP the shared ledger, both lock order, append-only history, original attempt
count, owner caps/reserves, ambiguous-create recovery, charge accounting and
the pre-dispatch NOT_EXECUTED path. REPAIR only the loss of definitive refusal
information when EXECUTED is reduced to an executed Boolean in pod_jobs.

Positive causality: ComputeService writes REJECTED only for the initial create
failure EXECUTED with resources_may_remain=false. Its resend path preserves MAY
for every second failure. Post-create rate/teardown failures remain BOUND with
resource history. A proof requires the original typed create failure, exact
job/spec/provider/store origin/request identity, current authoritative REJECTED
intent, and no ever-bound/adopted/duplicate resource, resend or known charge.
Reconciliation is an evidence read and identity check, never a Boolean supplied
by the caller. The proof and release are retained in the private receipt and
weekly ledger. Unknown provenance or changed state refuses.

New pod-job claims bind the spec and compute-store origin under the existing
locks. A release must match that original binding and retain the per-grant
attempt; it cannot refund a slot or permit a relaunch of the same job id.
Append the audited zero-pending settlement once. Identical repeated proof is
idempotent; conflicting proof, stale state, another job/root, known charge or
resource, and concurrent settlement/claim conflicts fail closed. Legacy rows
without origin binding remain held; no retrospective source identity is guessed.

NOT_FOUND is explicitly not proof: its existing post-grace absence observation
still raises MAY_HAVE_EXECUTED and permits late tagged resources. No wait,
finality threshold, stock rule, reserve, rate, dollar figure or economic authority
is changed. The three reported real ambiguous failures remain held pending an
authoritative vendor non-creation fact or a separately owner-approved rule.
This is a scoped evidence gap, not permission to infer never-created from empty
listings, timeout, missing handle, termination or resources_may_remain alone.

Prospective review repair PLT23-ACCOUNTING-01: a second unfinished same-job
caller could dispatch after the first caller's pre-dispatch history read but
before its ordinary zero settlement. The automatic run/check lifecycle now
holds a shared-ledger per-job execution flock before claim through finish.
The full existing POD_JOB_STORE/job-id digest keys it across backend/store roots.
Files stay stable, never unlinked; FD close releases all exits; no nested
acquisition. Waiting callers recheck terminal claims before launch. Different
jobs remain concurrent. Order: execution, grant, weekly, then SQLite fence;
grant/weekly/store locks are never held across provider work. External operator
reconcile never dispatches; no lower-level reentrant adapter is introduced.
The deterministic actual-run control pauses after history read, proves the
same lock busy to another process and another job free, then verifies another
backend/store caller cannot launch after zero settlement. Ambiguous history
remains held. This is a concurrency repair, not new economic authority.

Expected manifest: this decision, carbon/agent_campaign/{pod_jobs.py,
grant_runs.py,pod_job_noncreation.py}, focused synthetic receipt/store/ledger
CPU tests, and docs/development/compute/pod-jobs.md. Fresh open-PR scan found no
target overlap; PLT-22 #1325 is disjoint. PLT-20 stock selection stays excluded.

Baseline diagnostics: Linux fcntl available through WSL. Initial collection
failed on Windows Git-worktree path syntax; explicit Linux Git paths corrected
that. The wider baseline then passed 19 and failed importing unavailable NumPy
in a Phase-4 introspection test; that run is not PASS. Dependency-light ledger
baseline passed 7 tests with real Linux locks. Proof/ledger/shared-run diagnostics
passed 33 tests with that unrelated NumPy-dependent case deselected. The actual
launcher/service/recovery/finish synthetic transport slice passed 3 tests.
These are noncanonical diagnostics. Canonical Linux CI supplies full acceptance.

Validation: positive definitive rejection and explicit NOT_EXECUTED; negative
MAY/NOT_FOUND/no-handle/empty-list/created-then-terminated/duplicate/charge;
copied proof and root/claim mismatch; repeated release/relaunch; stale state,
corrupt provenance, lock races and conserved attempts/costs. No tests weaken.
Completion: one main-based PR with implementation, tests and stable scope
evidence, Data Collection metadata/recovery review, actual exact-head required
checks/Merge gate, and Root's guarded merge. No host/economic qualification.

Reversible: remove the new release path or prospectively version its binding.
Historical legacy rows retain their interpretation. A downgrade must refuse
unknown release/binding metadata rather than silently resurrect or erase costs.
