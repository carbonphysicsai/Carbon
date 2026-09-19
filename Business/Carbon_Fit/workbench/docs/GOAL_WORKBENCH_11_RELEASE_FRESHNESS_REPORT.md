# GOAL-WORKBENCH-11 release freshness and scoped acceptance

Maintenance repair for the packaging and coverage gaps reported after
GOAL-WORKBENCH-10. This changes no scientific behaviour, no authority state and
no Workbench feature.

## Root cause

The tracked Workbench release artifacts did not match the sources tracked
beside them. Two independent defects produced that.

**The bundle was never rebuilt after a merged source change.** `tools/build.py`
inlines `src/scientific_studies.js` and `src/scientific_studies_ui.js` into the
generated HTML. C-CORE-08 (PR #226) changed both and did not regenerate the
release. The arithmetic is exact: those two sources grew by 4290 and 1483
bytes, and the HTML rebuilt 5773 bytes larger than the tracked copy.

**Nothing could detect it.** `test_build_is_deterministic_and_script_safe`
builds, captures those freshly written bytes, builds again and compares the two
results. It proves a build repeats itself. It never compares an untouched
tracked artifact against a fresh rebuild, and it overwrites the artifact under
test on its first line, so an artifact that is stale but deterministic passes.

Attribution, measured by rebuilding each revision and comparing with that
revision's own tracked HTML:

| Revision | Tracked HTML vs rebuild |
|---|---|
| `7887c110` branch point of GOAL-WORKBENCH-10 | stale by 24378 bytes |
| `0d12b7fd` main immediately before the merge | stale by 30151 bytes |
| `8eaf1f04` accepted GOAL-WORKBENCH-10 head | current |
| `ab3e922e` integrated main after the merge | stale by 5773 bytes |

Staleness therefore predates GOAL-WORKBENCH-10 by a wide margin. That ticket
rebuilt from its own branch inputs and reduced the net drift from 30151 bytes
to 5773; the 5773-byte residue is the C-CORE-08 delta its branch never carried.
GOAL-WORKBENCH-10 is not the cause.

The archive was stale in one further respect the byte count does not show: it
never contained `tests/test_scientific_envelope.cjs`, added by the same merged
change.

## Repaired outputs

Regenerated from integrated `main` with the existing generators:

```
python tools/build.py
python tools/build_goal_schema.py
python tools/package_release.py
```

`data/goal_workspace.schema.json` and `data/goal_constants.json` were already
current and are unchanged. Historical archives `v0_2` through `v0_9` are
excluded from packaging and were not touched. No scientific threshold, fixture
identity, rights state, qualification or launch state changed.

## Read-only freshness gate

`tools/check_release_freshness.py` adds the missing condition:

```
tracked artifact bytes == output generated from the tracked source inputs
```

It stages the **tracked** sources into a throwaway directory outside the
repository, regenerates there and compares. It writes nothing to a tracked
file, so a stale or hand-edited artifact is reported rather than quietly
repaired, and a failing run never repins the expected digests.

```
python Business/Carbon_Fit/workbench/tools/check_release_freshness.py
```

Exit status is 0 current, 1 stale with the offending paths listed, 2 when the
check could not run. Archive drift is reported member by member.

Two design points are load-bearing:

- **Packaging provenance is normalised, not compared.** `package_release.py`
  records the Git HEAD that packaged the release. A commit cannot contain its
  own hash, so comparing that field would demand a self-referential repin on
  every commit. It is blanked on both sides, including inside the archived
  manifest, which is why the archive is compared member by member rather than
  as raw bytes.
- **The staged set is the tracked set.** `payloads()` assembles the archive by
  globbing the workbench directory, so generating from the working tree would
  let untracked scratch files reach the comparison. Restricting the source set
  to tracked paths also keeps a developer's local files out of a release.

`tools/package_release.py` now excludes dot-directories and `node_modules` from
the payload glob. The current release contains no such path, so the member set
is unchanged at 205; the exclusion prevents local Git metadata, a virtualenv or
installed packages from being packaged by anyone who builds with them present.

## Coverage

The change classifier files every Workbench path as `CONTRACT_AUTHORITY`, whose
lane runs constitutional invariants and repository authority and never builds
or runs the application. The `Canonical environment` job, which owns the
Workbench suites, requires `RUNTIME_FULL`. A Workbench source or packaging
change could therefore reach `main` having executed none of its own tests.

`scripts/dev/workbench_scope.py` derives one additional requirement from the
changed paths, and `scripts/dev/workbench_release_checks.sh` runs, in order:

1. the release freshness gate;
2. the Workbench JavaScript suites on pinned Node v24.19.0;
3. the source, packaging, freshness and authoring suites.

The freshness gate runs first by necessity: `test_sources.py` regenerates the
artifacts in place to prove determinism, so checking freshness afterwards would
only compare a fresh build against itself.

The requirement lives in its own module rather than in `classify_changes.py`
because that file and `development_scope.py` are digest-pinned by the
`OWNER-CW1-DEVELOPMENT-CI-01` block in the CI workflow. Editing either would
have re-authorised the owner's legacy classifier migration as a side effect of
an unrelated repair. Both files remain byte-identical to their pinned digests,
and a regression test asserts it.

The Merge gate derives the same requirement from the candidate's own module and
accepts the job only as `success` when required and only as `skipped` when not,
so a failed, cancelled or skipped Workbench job cannot pass as success. It is
enforced inline, exactly as the C-03 worker requirement is, so an older
protected-base gate implementation is never handed a job name it does not know.
A candidate predating the module resolves to not required.

Documentation-only and unrelated runtime changes are unaffected.

## Limitations

The browser suites now honour `CARBON_BROWSER_EXECUTABLE` and `CARBON_MOBILE`,
which previously only the two newest suites did; the macOS default is
preserved. Browser evidence is Chromium at desktop and narrow viewports against
the final generated bytes. That is not native Safari, not Mobile Safari, and
not hands-on assistive-technology acceptance, and no such claim is made here.

Nothing in this repair qualifies physics, references, uncertainty, rights,
protected reuse, score, execution or launch. The default offline build remains
offline and the private-service build remains a separate output. The repository
release is not a deployment; publishing the site remains separate and blocked
on its own owner route.
