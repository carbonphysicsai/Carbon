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

## 2. Validation budget

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
