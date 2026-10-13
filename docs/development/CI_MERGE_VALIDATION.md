# Exact head and merge validation (PLT-12)

The required gate validates an exact PR head and its clean merge with an exact
main base. It keeps head acceptance alongside integration acceptance instead
of treating a green head as evidence about later main changes.

The workflow resolves head, base and GitHub's proposed merge from one PR
snapshot and verifies current main. It fetches the immutable merge object,
requires ordered parents `[base, head]`, and compares its tree with Git's
clean `merge-tree` result. Missing identities, an unconfirmed merge, conflict,
wrong parents or a substituted tree fail closed. This does not merge main
into an executor's branch or push any Git ref.

Preflight still classifies and checks the exact head. Every existing acceptance
lane runs on both head and merge, with the same pinned actions, toolchains,
scope requirements, six-shard CPU/image layouts and time limits. Both results
are required. Unknown paths retain full runtime acceptance. The protected-base
classifier and aggregate gate remain controlling. The new receipt helper uses
the protected base after migration; its first introduction has an exact-byte
digest fallback while an old base genuinely lacks the helper. This retains
the existing repository-local trust boundary: a candidate-controlled workflow
is not independently secured infrastructure.

`ci-merge-identities-<attempt>` holds immutable head/base/merge SHAs, trees and
ordered parents. `ci-merge-result-<attempt>` retains these identities, the
required job inventory, actual job IDs/results for each revision, and:

- `PASSED`: both acceptance groups passed;
- `HEAD_ONLY_FAILURE`: head failed and merge passed;
- `MERGE_ONLY_FAILURE`: head passed and merge failed;
- `HEAD_AND_MERGE_FAILURE`: both failed;
- `INCOMPLETE`: required evidence is missing, ambiguous or still pending.

The separate `gate_result` records freshness/identity refusal or acceptance.
The completed attempt's receipt is retained even for a failed group or moved
base. Missing, skipped, cancelled or neutral required jobs cannot pass.
The aggregate still requires every original applicable job. The final check
re-reads head and base; a change invalidates the run's handoff. Receipt names
include the attempt so a prior verdict cannot masquerade as the current
attempt's verdict.
Each acceptance job's name also binds the immutable merge SHA. Failed-job
retries select the latest execution of each required slot for that same pair,
retaining earlier successful slots without repeating them. The identity
artifact is selected by preflight's explicit output, including when preflight
was retained from a prior attempt. A re-run that resolves a newer merge cannot
reuse jobs tagged for the older merge; the new pair needs full validation.

## Base guard and activation

The versioned main ruleset now requests
`strict_required_status_checks_policy: true`. It keeps the same required
`Merge gate` from Actions app 15368, normal PR merge commits, no bypass actors,
and all other controls. GitHub's [strict status-check rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
requires an up-to-date branch at merge time. The [PR merge API](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request)
provides an expected head SHA but no expected base SHA. Reading main just
before that API call alone would leave a race.

PR Head/the owner must authorize the administrative ruleset update. Review its
exact delta with `scripts/dev/apply_github_ruleset.py --dry-run`. The one-time
activation sets only the existing rule's strict flag, keeping all required
checks, their Actions app, and all other controls. Verify the effective live
rules after that administrative write. Both Merge gate and the merge watcher
fail closed as `BASE_RULE_NOT_ACTIVE` until the rule is confirmed active.
The ordinary apply tool retains its successful-Merge-gate guard, so it cannot
bootstrap this first activation while that gate is correctly refusing the
missing policy. The owner can adopt the narrow flag change through GitHub's
ruleset settings; after adoption, the normal exact-main/head guarded apply
tool reconciles and verifies the complete artifact as before. No administrative
write is performed by this ticket's coding session. Committing the desired
rule does not establish live enforcement. `merge_on_green.py` requires a current completed CI receipt and
an effective strict Actions `Merge gate` rule before it can return MERGE,
then retains the API's expected-head guard. It never passes `--admin`.

Strict mode can require branch updates and another acceptance after any merge
advances main. PR Head owns synchronization and merge order. This trades CI
throughput for server-enforced base safety. A merge queue is a possible later
optimization, requiring its own policy/CI migration; it is not enabled here.
The stricter rule must be activated before treating PLT-12 as complete. After
activation, retry only the failed gate when the pair is unchanged; a moved
base requires synchronization/re-validation by PR Head.

## Validation

Run canonical focused tests:

```bash
./scripts/dev/canonical.sh --focused tests/cpu/test_ci_merge.py tests/cpu/test_merge_on_green.py tests/cpu/test_github_ruleset.py tests/cpu/test_change_classifier.py tests/cpu/test_workbench_scope.py tests/cpu/test_julia_scope.py
```

The synthetic Git fixture deliberately separates head from a newer base:
head passes its imported-value assertion, while their clean merge fails it.
It checks merge-only attribution, both SHA identities, conflicts and refused
head-only substitution. Other mutations remove/duplicate a required shard,
skip/cancel its result, move head/base, or leave the strict rule inactive.
These tests establish bounded engineering behavior, not security acceptance,
scientific qualification, production readiness or release authority.
