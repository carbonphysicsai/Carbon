# How we ship now

One page. Pull request, green checks, merge. No bypass.

Written 2026-10-30 from the repository's own rules and workflows. Items marked **not yet proven** have not been run end to end on GitHub.

## The rule

`main` accepts changes only through a pull request whose required check, **Merge gate**, is green. The repository ruleset "Carbon main merge gate" enforces it: pull request required, `Merge gate` status required, no deletion, no non-fast-forward push. Its bypass list is empty. A push straight to `main` is refused.

Merge commits only. The repository allows merge commits and turns off squash and rebase merges.

## The flow

1. **Branch and change.** Work on a branch cut from the current `main`. Keep one ticket per pull request.
2. **Open the pull request against `main`.** Draft pull requests skip the checks, so mark it ready when it is.
3. **Preflight classifies the change by path** and picks the scope. The classifier is `scripts/dev/classify_changes.py`. Unknown paths fall back to the full scope.

   | Scope | Examples of paths | Required to be green |
   |---|---|---|
   | `DERIVED_DOCUMENTATION` | derived documentation | preflight, derived_documentation |
   | `CONTRACT_AUTHORITY` | `docs/development/*.md` rule documents | preflight, contract_authority |
   | `RUNTIME_FULL` | `carbon/`, `tests/`, `scripts/`, `docs/MINING.md`, `.github/workflows/`, `.ci/quality-baseline.json`, `pyproject.toml` | preflight, canonical (six shards), dev_image |

4. **The scope's jobs run.** The `canonical` job runs the whole suite in six shards on GitHub's Linux runners. Shard 0 also runs the quality ratchet (`scripts/check_quality.py`). Jobs the scope does not need must show as skipped.
5. **Merge gate** reads those results (`scripts/dev/check_merge_gate.py`, from the protected base) and goes green only if every required job succeeded and every other job was skipped.
6. **Review.** A fresh, exact-head review of the whole diff, repaired to zero findings, then a distinct human approval, as `AGENTS.md` section 9 and `.agent/DELIVERY_PROTOCOL.md` describe.
7. **Merge** with a normal merge commit, guarded on the exact reviewed head. Then confirm the push-triggered **Main smoke** run on the new `main` is green.

## After the merge

- **Main smoke** runs on every push to `main` (`.github/workflows/main-smoke.yml`). It runs the invariant tests and the public import. It was red from 2026-10-19 until the numpy fix landed in `418ce0de6`; it is green on that commit.
- Releases and worker images follow their own workflows (`release-rehearsal.yml`, `release-worker-images.yml`). They are not part of the merge.

## What is not yet proven

- **A `RUNTIME_FULL` pull request going fully green on GitHub.** The quality baseline (`.ci/quality-baseline.json`) dates from 2026-08-19. The ratchet counts every diagnostic not in that baseline as new, so it reports about 185 Ruff and 48 Black entries as new on current `main`. It stays red until the baseline is refreshed from a clean checkout of current `main`.
- **Which other tests fail on GitHub's runners.** The local and Targon gates are not the GitHub gate.

## How to refresh the quality baseline

On a clean checkout of the exact commit (the generator refuses a dirty tree, and it counts untracked Python files), with the pinned tools (Ruff 0.16.3, Black 26.5.1):

```bash
python scripts/check_quality.py --update-baseline --source-commit "$(git rev-parse HEAD)"
```

Commit the rewritten `.ci/quality-baseline.json` in its own pull request. New debt is still blocked afterwards, because the ratchet compares against the refreshed baseline.

## When something is red

Read the failing job's log first. Do not bypass the ruleset to get around a red check. Fix the cause, or say plainly in the pull request which check is red and why.
