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

The expected bytes are captured from the repository before anything runs, and
only the *source* inputs are staged. The declared artifacts are deliberately not
copied into the comparison tree: if they were, a generator that exits zero
without writing would leave the previous file in place and the comparison would
credit it as freshly produced. Each generator must produce the artifacts it
declares, as regular files, before anything downstream consumes them, and
membership is established from Git so a stray file on disk is never treated as
release content.

Three design points are load-bearing:

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

- **Archive structure is validated, not just member payloads.** Reducing an
  archive to a name/payload mapping read through `namelist` hides two things
  that change what extraction produces: a duplicated member name, where only one
  entry survives the mapping, and a member re-typed as a link while its bytes
  stay identical. Entries are walked through `infolist`, duplicate names,
  directory entries, unsafe paths and non-regular member types are rejected, and
  each member's mode participates in the comparison.

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

## Review repairs

Three findings were raised against the first revision of this repair. All three
reproduced against the reviewed checker and are closed here.

**A generator that exited zero without writing could pass.** The comparison tree
was staged with the existing artifacts copied in, so a no-output generator left
the previous file in place and it was compared against itself. Reproduced by
changing a source, replacing the HTML generator with one that exits zero writing
nothing, and regenerating the manifest and archive: the checker reported
`Workbench release artifacts are current` with exit 0 while the tracked HTML did
not match the changed source. The gate now captures the expected bytes first,
stages only source inputs, and requires every declared artifact to exist as a
regular file after its generator runs.

**Archive comparison dropped structure.** `archive_members` read by filename
into a dictionary, so duplicate entries collapsed and member metadata was
ignored. Both reproductions compared equal to the legitimate archive: two
entries sharing one path with different payloads, and a regular file re-typed
with symlink metadata and identical bytes. Neither claims the committed archive
is malicious; they show the integrity gate accepted structurally altered input.
Entries are now validated before comparison and original bytes are preserved
when validation fails.

**A missing CI requirement read as "not required".** The Merge gate defaulted an
empty derived value to false even when the scope module was present, and
compared against `${PREFLIGHT_WORKBENCH:-false}`, conflating an explicit false
with an absent decision. A present module must now produce exactly one explicit
boolean from both preflight and the independent gate derivation; missing, empty,
malformed or duplicate output fails. The compatibility path applies only when
the module is genuinely absent, and an absent module may not accompany a
preflight requirement. The live run did execute and pass the Workbench job; this
was a negative case the gate should reject.

A follow-up review found the first version of that requirement parser still
accepted two malformed emissions. Duplicate detection keyed on whether the
stored value was still empty, so an empty first record let a second one
through, and the read loop dropped a final line written without a trailing
newline, leaving a trailing duplicate unexamined. Both reproduced at exit 0.
Record presence is now tracked independently of the value, and an unterminated
final line is read and acted on rather than discarded.

The acyclic provenance exception is unchanged in scope: only
`integration_revision_at_packaging` is excluded from equality, and its shape is
now validated rather than accepted unread.
