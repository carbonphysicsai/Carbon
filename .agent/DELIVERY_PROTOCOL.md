# Carbon Delivery Protocol

**Status:** owner-authorized delivery policy, effective 2026-09-06
**Decision:** OWNER-DX-03
**Applies to:** current and future engineering tickets, including open PRs

The owner directs: follow the ticket, test the changes, and ship. This policy
supersedes GOV-REVIEW-01 and older delivery-process requirements in tickets,
plans, Wave records, agent handoffs, and Hub instructions. Historical receipts
remain historical evidence. Scientific, security, economic, legal, deployment,
qualification, and LIVE acceptance remain human-reserved and unchanged.

## 1. Ticket to merge

1. Read the ticket and relevant authority. Keep working code under
   KEEP -> WRAP -> REPAIR -> REPLACE. Implement the ticket's Definition of Done.
2. Use one branch and one PR per ticket by default. Develop coherent slices
   with focused tests. Continue through slices without asking for permission
   at each checkpoint unless the owner requested a stop.
3. Record material decisions and update affected documentation. Batch Hub
   maintenance before acceptance. Do not create a contract-only PR, a separate
   plan, or a review checkpoint merely because a ticket has multiple modules.
   Split independently shippable work when an actual dependency or owner
   instruction requires it; explain the split in the PR.
4. Check the change for correctness and add regression tests for defects.
   An independent agent review is optional. There is no mandatory human
   reviewer, GPT receipt, bot approval, model score, clean-pass quota, or
   fresh-context full-diff review loop. Fix concrete defects; verify repairs
   with focused tests and inspect the affected interactions.
5. Finish the candidate, mark the PR ready, and run the applicable automated
   acceptance once. Required tests must pass. Merge the tested revision with
   the expected-head guard; do not merge code that changed after its checks.
6. Confirm GitHub reports the merge. Post one brief completion comment with
   the ticket, test result/CI link, remaining limitations, and next ticket.
   Close the ticket in its bounded engineering scope and continue when the
   owner authorized end-to-end execution. No second approval prompt, receipt
   schema, evidence-seal commit, or post-merge full-CI wait is required.

A valid bug, failed required test, actual merge conflict, or unresolved
human-reserved decision can stop the affected work. A review receipt, prose
formatting issue, bot outage, or incomplete historical ceremony cannot.
Never suppress a failing test, invent a pass, or relabel qualification.

### 1.1 Enforce properties by construction

When a value must satisfy a property before it is used, prefer a design where an
object that does not satisfy it cannot be constructed, over one that checks the
property at the point of use. A check is a thing that can be incomplete or
bypassed; a type that cannot be built from unvalidated input has nothing to get
wrong later, and its error lands where the mistake was made rather than wherever
the value is eventually written.

The transferable part is a question to ask, not a pattern to apply:

> **What establishes this property, and what happens when someone constructs the
> object differently?**

If the answer is a flag, a naming convention, a comment, or a re-check inside the
consumer, the property is true but unenforced. Three workstreams reached this
independently on 2026-09-21, each by a different route: a second call site found
by tracing (`#256`), a hand-maintained list found by going stale (`#258`), and a
validator found by a test failing on the wrong branch (`#257` lineage). None was
found by agreeing with the principle in advance.

A useful check on whether a design actually achieved it: a *valid* value, passed
in its raw underlying form, should still be refused. Nothing about that value is
wrong; it is refused because it did not come through validation, which is exactly
the property a check at the point of use cannot establish.

Two corollaries that recur:

- **The generic-error branch is the highest-risk surface in a validator.** It is
  the path nobody designs, so it is where unvalidated input goes to be logged or
  echoed. Prefer a specific refusal that names the mistake, and inspect what the
  catch-all does with what it was handed.
- **A closed schema and a positive format check answer different questions.** A
  closed shape is a complete structural guarantee against a hostile caller and
  says nothing about an honest user making the most natural mistake available to
  them. Passing one is not evidence about the other.

This is an engineering standard, not a new delivery gate. It adds no required
review, check, or approval, and nothing here blocks a merge.

### 1.2 A claim must report its basis

**A green that cannot say what it checked is not a result.** When a check,
report, or monitor concludes success, it should also carry what it examined -
how many items, which properties were compared, which could not be - so that a
conclusion drawn from nothing reads as drawn from nothing instead of as a pass.

The defect this prevents is an **absence of evidence converted into evidence of
a conclusion**. It runs in both directions, which is why each instance looks like
a different bug rather than like the last one:

```text
observing    "cannot see"      must not become   "nothing is there"
verifying    "cannot check"    must not become   "mismatched"
reporting    "nothing failed"  must not become   "passed"
```

Seven instances were found on 2026-09-21 across two executors, and the surfaces
were unrelated enough that none resembled its predecessor: a decision recorded in
an authority document reported as implemented; a verification record listing
properties as verified because the list was hardcoded rather than compared; a
comparison where absent-on-both-sides matched; a pod runner tested on a
development host that supplied binaries the target image lacks; a local validator
reporting zero errors for a block it had skipped; four hub-impact declarations
satisfied by an incidental marker word rather than by their stated reason; and a
status watcher reporting a pull request green from an API response that contained
no checks at all.

Every one produced a conclusion with no attached basis, and every one was true as
stated. That is what makes the failure mode durable: it survives review by people
looking for false statements, because nothing said is false. The question to ask
is not "is this true?" but **"what is this true *of*, and is that the thing being
claimed?"**

The remedy is structural rather than a handled edge case. Build the basis into
the success path, and treat a read that returned nothing as *no information*
rather than as a pass. This is an engineering standard, not a delivery gate.

### 1.3 A wait that cannot say what it is waiting for is not waiting

> **An unsatisfiable wait presents as patience.**

A watcher pinned to a SHA that is no longer the head polls forever. From outside,
"not yet" and "never" look identical: no error, no failure, just a pull request
that quietly does not merge. The expected-head guard worked exactly as designed;
the watcher's silence was the defect.

The transferable part is a question, asked before the wait starts and again each
time the wait is reported:

> **Can the thing I am waiting for still become true? If I cannot answer that, I
> am not waiting - I am stuck.**

What follows from it:

- State the condition before waiting, in terms that can be *evaluated* rather
  than described.
- A pinned identifier that no longer exists is a **reported condition, not a
  continued wait**. Say so and stop.
- When the blocker is someone else, verify that they are actually the blocker.
  Re-read the state; do not infer it from the last thing that was known.
- A report that says "waiting" must say what for, and how its arrival would be
  recognised. A report that says only "waiting" cannot be distinguished from one
  that should say "stuck".

Three instances on 2026-09-22, and the shape is only visible once they are put
beside each other: **six pull requests green and unmerged** across two lanes,
because their watchers held stale SHAs copied from a template; **a pull request
reported as waiting on two other workstreams** while it was red on a single Ruff
diagnostic, so it was waiting on its own author and nobody checked; and
**sessions idle for two hours after ending a turn**, which from outside is
indistinguishable from sessions working.

Each looked like patience, which is why none of them raised an alarm. A failure
that announces itself gets fixed; this one is quiet by construction, and the
quiet is the symptom.

The remedy is the same shape as 1.1: make the unsatisfiable wait impossible to
express rather than remembering not to write one. A waiter should re-read the
condition it pinned, and stop with a report the moment that condition becomes
unreachable - a head that moved, a pull request already merged or closed, a
check that completed without success. `scripts/dev/merge_on_green.py` is the
worked version for the case that produced these, and its decision function is
tested against each terminal state precisely because "still waiting" is the one
answer that must never be returned for a condition that cannot come true.

This is an engineering standard, not a delivery gate. It adds no required check
and blocks no merge.

## 2. Validation budget


**OWNER-CW1-DEVELOPMENT-CI-01 (2026-09-17):** Ryan authorizes bounded
non-paying DEVELOPMENT competition acceptance, including the C-W1-D3 migration.
The exact runtime paths and subsystem test manifest live in
`scripts/dev/development_scope.py`; no general development-prefix exemption exists.
Run all invariants, all-test collection, affected measurement/scoring/signed-source/
lifecycle/reward and tooling regressions, package/outside-tree checks, canonical
doctor, quality, applicable JAX tests, public-source validation, Hub and Merge gate.
Mixed official/shared scientific, worker/reference, broader runtime or unknown
changes retain full CPU regression. Exact dependency/environment changes retain
full acceptance. Clean image builds follow actual `.devcontainer`, dependency,
interpreter and packaging inputs; an unknown document or CI routing change alone
does not cause a rebuild. Actual worker/reference/shared lifecycle changes retain
their isolated-service campaign. Reuse accepted isolation evidence for unchanged
boundaries. This supersedes older blanket full-runtime wording only in this scope.

**OWNER-C0-VALIDATION-01 (2026-09-09, prospective):** The owner authorizes
skipping the full 30+ minute CPU regression on each NET delivery when the
executor judges it unnecessary. Known network paths use an explicit tested
network/subsystem manifest; all invariants, collection, quality, package,
Hub and required Merge gate assertions remain. Unknown paths, shared
scientific changes and resolved dependency changes retain full regression.
This supersedes the blanket runtime-PR CPU sentence below for that bounded
profile; it does not turn failures into passes or weaken test semantics.

NET-5-D2 applies the same bounded principle to the exact finite synthetic A8
identity extension: checked before/after hashes, all A7/A8/scoring and NET-5
regressions, unchanged invariant/quality/package/Hub/image/Merge assertions.
Any other shared scientific change retains full regression.

NET-1's first broad run on `253403f` passed 4,865 CPU tests (including the
installed SDK) and all 169 invariants; two bootstrap tests failed because
their environment inherited the chain group. Their repair explicitly tests
both dev-only and dev-plus-chain environments. Focused repair acceptance is
appropriate: no resolved dependency changed from main (only two existing
11.1.0 constraints were tightened). The classifier verifies that exact
manifest-only migration byte-for-byte; other dependency changes stay full.
The initial broad run remains failed historical evidence, not a green receipt.

During development, run focused ticket and affected-subsystem tests. Use the
canonical wrapper when available. A missing local Docker installation is
infrastructure unavailability, not a reason to repeat the same failed command
or to block implementation; GitHub's pinned environment supplies acceptance.
Native-host tests are diagnostics, not canonical qualification.

For a ready runtime PR, CI runs the CPU regression suite, invariant tests,
quality ratchet, package/import checks, and applicable Hub validation. Unknown
paths retain full runtime acceptance. Contract-only and generated-doc changes
retain their existing lighter classified suites. Test semantics remain intact.

The clean development-image build runs for environment, dependency, workflow,
or canonical-runner changes and unknown paths. Ordinary Python implementation
and test changes use the pinned canonical runner without rebuilding the image.
The aggregate Merge gate rejects failed or skipped required jobs.

Draft PR updates do not start acceptance. Marking a draft ready starts its
first acceptance run. Ready PR code pushes start acceptance for that revision.
PR title/body edits, review submissions, and comments do not start full CI.
The standalone Hub workflow is manual; CI owns normal Hub acceptance once.

A local `validate_hub.py` run is **partial by default**, and it still prints
`Validation passed`. The diff and change-event coverage is skipped without
`HUB_DIFF_BASE_SHA`, and the live pull-request block - which checks the PR body's
hub-impact declaration and binds it to the exact checked-out head - is skipped
without `GITHUB_EVENT_PATH` and `HUB_LIVE_PR_PATH`. Each skip is announced as a
warning, not an error, so a local pass is evidence only about the checks that
ran; reporting it as a clean Hub result while CI fails states a true fact about a
different validation run. To reproduce a CI Hub failure, check out the exact PR
head and supply all three variables, building the live-PR and event payloads from
the real pull request. See 1.2.

A `HUB_IMPACT_NONE` declaration must state **why the hub's semantics remain
accurate**, not which paths are untracked. The validator requires a concrete
scoped reason and looks for reason markers in the text, so a declaration arguing
only about path coverage can pass on an incidental word while expressing the
wrong claim. Write the reason the hub's purpose, placement, status, dependencies,
boundaries, maturity and primary links are unchanged, and confirm that a passing
check passed for that reason. `HUB_IMPACT_NONE` is unavailable on a
`map_structural` path regardless of the reason given.
Main smoke checks detect integration failures after merge; they are not a
second full acceptance or a ticket-closeout ceremony.

Batch changes before pushing a ready candidate. Do not rerun a green workflow
for reassurance, rewrite a PR body to force CI, create an empty commit, or
repeat a successful job after an infrastructure failure. Retry the failed job.
After a real code/test/environment change, validate the new revision. Docs and
status notes do not require another substantive code review. Do not copy a
success from different executable inputs and claim the new code passed.

## 3. Merge control and evidence

The intended repository rule is one required status check: `Merge gate` from
GitHub Actions, with zero required approvals and no last-push approval.
Thread-resolution bookkeeping is not an additional gate; actual unresolved
bugs and explicit owner blocks still require disposition. Use normal merge
commits and retain the API's inexpensive expected-head race guard.

Do not require a base refresh solely because main advanced. Inspect the
integration impact; reconcile conflicts or changed dependencies and validate
those changes. The merge guard prevents merging a different PR revision; it
does not prove scientific qualification or conflict-free semantic integration.

CI obtains revision identities from GitHub/Git. Do not ask a human to copy
head/tree/base SHAs, review counters, or rerun totals into a PR. The PR needs a
ticket/scope explanation, test summary, risks, and Hub impact where relevant.
Legacy receipt fields are historical metadata and are not merge authority.

The versioned intended rule remains `.github/rulesets/main.v1.json`; the file
format version is unchanged. The apply tool must verify live settings after
an administrative write. A committed artifact is not proof of live enforcement.
No receipt or merge operation grants scientific, security, production, LIVE,
network, frontier, settlement, weight, or emission authority.
